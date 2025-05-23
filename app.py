import os
import time
import logging
from datetime import datetime
from flask import Flask, request, abort
from dotenv import load_dotenv
from google.cloud import vision
from supabase_client import supabase

from linebot.v3 import WebhookHandler
from linebot.v3.webhooks import MessageEvent, FollowEvent, TextMessageContent
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import ReplyMessageRequest, TextMessage
from linebot.exceptions import InvalidSignatureError
from linebot import LineBotApi

from utils.user_code import generate_unique_user_code
from utils.stats import build_user_stats_message
from utils.onboarding import handle_user_onboarding
from utils.gpt_parser import parse_text_with_gpt
from utils.richmenu import create_and_link_rich_menu
from utils.ocr_utils import (
    _extract_score, is_correction_command, get_correction_menu,
    is_correction_field_selection, set_user_correction_step,
    get_user_correction_step, clear_user_correction_step,
    validate_score_range
)
from utils.field_map import get_supabase_field

# --- 初期設定 ---
app = Flask(__name__)
env_file = os.getenv("ENV_FILE", ".env.dev")
load_dotenv(dotenv_path=env_file)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

DEBUG = os.getenv("DEBUG", "False").lower() == "true"
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
line_bot_api_v2 = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
user_send_history = {}

# --- ルーティング ---
@app.route("/", methods=["GET"])
def index():
    return "✅ Flask x LINE Bot is running!"

@app.route("/create-richmenu", methods=["GET"])
def create_richmenu():
    try:
        return f"✅ リッチメニュー作成成功｜ID: {create_and_link_rich_menu()}"
    except Exception as e:
        return f"❌ リッチメニュー作成失敗: {e}", 500

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception:
        logging.exception("❌ Webhook error")
        abort(400)
    return "OK"

# --- イベント処理 ---
@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        profile = messaging_api.get_profile(user_id)
        name = profile.display_name or "unknown"
        handle_user_onboarding(user_id, name, messaging_api, event.reply_token)

@handler.add(MessageEvent)
def handle_event(event):
    msg = event.message
    if hasattr(msg, "content_provider") and msg.content_provider.type != "none":
        handle_image(event)
    elif isinstance(msg, TextMessageContent):
        handle_text(event)

# --- 画像処理 ---
def handle_image(event):
    image_path = None
    try:
        user_id = event.source.user_id
        now = time.time()
        history = user_send_history.setdefault(user_id, [])
        history[:] = [t for t in history if now - t < 80]
        history.append(now)
        if len(history) > 2:
            _reply(event.reply_token, "⚠️ 一度に送れる画像は最大2枚までです。")
            return

        content = line_bot_api_v2.get_message_content(event.message.id)
        image_path = f"/tmp/{event.message.id}.jpg"
        with open(image_path, "wb") as f:
            for chunk in content.iter_content():
                f.write(chunk)

        client = vision.ImageAnnotatorClient()
        with open(image_path, "rb") as f:
            texts = client.text_detection(image=vision.Image(content=f.read())).text_annotations

        score = _extract_score(texts)
        parsed = parse_text_with_gpt(texts[0].description if texts else "")
        parsed["score"] = score

        if score is None:
            _reply(event.reply_token, "⚠️ スコアが読み取れませんでした。画像を確認してください。")
            return
        if not validate_score_range(score):
            _reply(event.reply_token, "⚠️ スコアは30.000以上100.000未満で入力してください。")
            return

        now_iso = datetime.utcnow().isoformat()
        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            profile = messaging_api.get_profile(user_id)
            user_name = profile.display_name or "unknown"

            u = supabase.table("users").select("score_count,user_code").eq("id", user_id).maybe_single().execute().data or {}
            supabase.table("users").upsert({
                "id": user_id,
                "name": user_name,
                "user_code": u.get("user_code") or generate_unique_user_code(),
                "score_count": (u.get("score_count") or 0) + 1,
                "last_score_at": now_iso
            }).execute()

            supabase.table("scores").insert({
                "user_id": user_id,
                "score": score,
                "song_name": parsed.get("song_name"),
                "artist_name": parsed.get("artist_name"),
                "comment": None,
                "created_at": now_iso
            }).execute()

            stats = build_user_stats_message(user_id) or "⚠️ 成績情報取得失敗"
            reply = f"✅ スコア登録完了！\n点数: {score}\n曲名: {parsed.get('song_name') or '---'}\nアーティスト: {parsed.get('artist_name') or '---'}\n\n{stats}"
            _reply(event.reply_token, reply)

    except Exception:
        logging.exception("❌ Image processing error")
        _reply(event.reply_token, "❌ 画像処理に失敗しました。再送信してください。")
    finally:
        if image_path and os.path.exists(image_path):
            os.remove(image_path)

# --- テキスト処理 ---
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    from linebot.v3.messaging.models import TextMessage as V3TextMessage
    from supabase_client import supabase
    from utils.ocr_utils import (
        is_correction_command, get_correction_menu,
        is_correction_field_selection, set_user_correction_step,
        get_user_correction_step, clear_user_correction_step,
        validate_score_range
    )

    user_id = event.source.user_id
    text = event.message.text.strip()

    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)

        try:
            # 名前変更開始
            if text == "名前変更":
                supabase.table("name_change_requests").upsert({
                    "user_id": user_id,
                    "waiting": True
                }).execute()
                messaging_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[V3TextMessage(text="📝 新しい名前を入力してください")]
                ))
                return

            # 名前変更確定
            name_req = supabase.table("name_change_requests").select("*").eq("user_id", user_id).maybe_single().execute()
            if name_req and name_req.data and name_req.data.get("waiting"):
                new_name = text
                supabase.table("users").update({"name": new_name}).eq("id", user_id).execute()
                supabase.table("name_change_requests").delete().eq("user_id", user_id).execute()
                messaging_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[V3TextMessage(text=f"✅ 名前を「{new_name}」に変更しました！")]
                ))
                return

            # 成績確認
            if text == "成績確認":
                try:
                    stats_msg = build_user_stats_message(user_id)
                    messaging_api.reply_message(ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[V3TextMessage(text=stats_msg)]
                    ))
                except Exception:
                    logging.exception("❌ 成績確認の生成に失敗しました")
                    messaging_api.reply_message(ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[V3TextMessage(text="⚠️ 成績情報の取得に失敗しました。")]
                    ))
                return

            # 修正メニュー表示
            if is_correction_command(text):
                clear_user_correction_step(user_id)
                messaging_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[get_correction_menu()]
                ))
                return

            # 修正項目選択
            if is_correction_field_selection(text):
                set_user_correction_step(user_id, text)
                messaging_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[V3TextMessage(text=f"📝 新しい {text} を入力してください")]
                ))
                return

            # 修正入力反映
            field = get_user_correction_step(user_id)
            if field:
                value = text
                if field == "スコア":
                    try:
                        value = float(text.replace("．", ".").replace("。", ".").replace(",", "."))
                        if not validate_score_range(value):
                            messaging_api.reply_message(ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[V3TextMessage(text="⚠️ スコアは30.000以上100.000未満で入力してください。")]
                            ))
                            return
                    except ValueError:
                        messaging_api.reply_message(ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[V3TextMessage(text="⚠️ スコアが数値として認識できませんでした。")]
                        ))
                        return

                latest = supabase.table("scores").select("id").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
                if latest.data:
                    score_id = latest.data[0]["id"]
                    supabase.table("scores").update({
                        get_supabase_field(field): value
                    }).eq("id", score_id).execute()

                    updated = supabase.table("scores").select("*").eq("id", score_id).single().execute()
                    clear_user_correction_step(user_id)

                    data = updated.data or {}
                    msg = (
                        f"✅ 修正完了！\n"
                        f"点数: {data.get('score') or '---'}\n"
                        f"曲名: {data.get('song_name') or '---'}\n"
                        f"アーティスト: {data.get('artist_name') or '---'}"
                    )
                    messaging_api.reply_message(ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[V3TextMessage(text=msg)]
                    ))
                    return

            # 処理対象外
            messaging_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[V3TextMessage(text="⚠️ このメッセージは処理対象外です。")]
            ))

        except Exception:
            logging.exception("❌ テキスト処理エラー")
            messaging_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[V3TextMessage(text="❌ エラーが発生しました。もう一度お試しください。")]
            ))

# --- ヘルパー ---
def _reply(token, text):
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=token, messages=[TextMessage(text=text)])
        )

# --- 実行 ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
