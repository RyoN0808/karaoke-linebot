import os
import re
import io
import logging
from datetime import datetime
from flask import Flask, request, abort
from dotenv import load_dotenv
from google.cloud import vision
from google.oauth2 import service_account
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage

from supabase_client import supabase
from utils.rating import get_rating_from_score
from utils.rating_predictor import predict_next_rating
from utils.ocr_utils import (
    is_correction_command, get_correction_menu,
    is_correction_field_selection, set_user_correction_step,
    get_user_correction_step, clear_user_correction_step,
    _extract_score
)
from utils.field_map import get_supabase_field
from utils.gpt_parser import parse_text_with_gpt
from utils.user_code import generate_unique_user_code
from utils.richmenu import create_and_link_rich_menu
from utils.stats import build_user_stats_message
from linebot.models import FollowEvent
from utils.onboarding import handle_user_onboarding

app = Flask(__name__)

env_file = os.getenv("ENV_FILE", ".env.dev")
load_dotenv(dotenv_path=env_file)

DEBUG = os.getenv("DEBUG", "False").lower() == "true"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")


log_level = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

print(f"[INFO] 読み込まれた env ファイル: {env_file}")

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

@handler.add(FollowEvent)
def handle_follow(event):
    try:
        user_id = event.source.user_id
        profile = line_bot_api.get_profile(user_id)
        user_name = profile.display_name or "unknown"

        handle_user_onboarding(user_id, user_name, line_bot_api, event.reply_token)
    except Exception:
        logging.exception("❌ Followイベント処理に失敗しました")


@app.route("/create-richmenu", methods=["GET"])
def create_richmenu():
    try:
        rich_menu_id = create_and_link_rich_menu()
        return f"✅ リッチメニュー作成成功｜ID: {rich_menu_id}"
    except Exception as e:
        return f"❌ リッチメニュー作成に失敗しました: {str(e)}", 500

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    logging.debug("\U0001F4A1 Signature: %s", signature)
    logging.debug("\U0001F4A1 Body: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logging.error("❌ Signature error!")
        abort(400)
    except Exception:
        logging.exception("❌ Unexpected error!")
        abort(400)

    return "OK"

# ==============================
# グローバルカウント用
# ==============================
import time

# ユーザーごとの画像送信履歴を保存する（メモリ上）
user_send_history = {}

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    try:
        user_id = event.source.user_id
        now = time.time()

        # ユーザー履歴なければ初期化
        if user_id not in user_send_history:
            user_send_history[user_id] = []

        # 直近80秒以内の履歴だけ残す
        user_send_history[user_id] = [
            t for t in user_send_history[user_id] if now - t < 80
        ]

        # 今回の送信を追加
        user_send_history[user_id].append(now)

        # 10秒以内に3枚以上送信してたら拒否
        if len(user_send_history[user_id]) > 2:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ 一度に送信できる画像は最大2枚までです。少し待ってから再送信してください。")
            )
            return

        # ========== ここから通常の画像処理 ==========

        message_content = line_bot_api.get_message_content(event.message.id)
        image_path = f"/tmp/{event.message.id}.jpg"
        with open(image_path, "wb") as f:
            for chunk in message_content.iter_content():
                f.write(chunk)

        client = vision.ImageAnnotatorClient()
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        texts = response.text_annotations
        result_text = texts[0].description if texts else ""
        score = _extract_score(texts)

        structured_data = parse_text_with_gpt(result_text)
        parsed = {
            "score": score,
            "song_name": structured_data.get("song_name"),
            "artist_name": structured_data.get("artist_name"),
        }
        logging.debug("\U0001F50E パース結果: %s", parsed)

        if parsed["score"] is not None:
            # スコアの範囲チェック（30.000〜100.000未満）
            if not (30.000 <= parsed["score"] < 100.000):
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="⚠️ 点数は30.000以上100.000未満のみ登録できます。")
                )
                return

            # ここからDB登録処理
            profile = line_bot_api.get_profile(user_id)
            user_name = profile.display_name or "unknown"
            now_iso = datetime.utcnow().isoformat()

            user_resp = supabase.table("users").select("score_count, user_code").eq("id", user_id).maybe_single().execute()
            current_data = user_resp.data if user_resp and user_resp.data else {}
            current_count = current_data.get("score_count", 0)
            user_code = current_data.get("user_code") or generate_unique_user_code()

            supabase.table("users").upsert({
                "id": user_id,
                "name": user_name,
                "user_code": user_code,
                "score_count": current_count + 1,
                "last_score_at": now_iso
            }).execute()

            supabase.table("scores").insert({
                "user_id": user_id,
                "score": parsed["score"],
                "song_name": parsed["song_name"],
                "artist_name": parsed["artist_name"],
                "comment": None,
                "created_at": now_iso
            }).execute()

            try:
                stats_msg = build_user_stats_message(user_id)
            except Exception:
                logging.exception("❌ 成績確認の生成に失敗しました")
                stats_msg = "⚠️ 成績情報の取得に失敗しました。"

            reply_msg = (
                f"✅ スコア登録完了！\n"
                f"点数: {parsed['score']}\n"
                f"曲名: {parsed['song_name'] or '---'}\n"
                f"アーティスト: {parsed['artist_name'] or '---'}\n\n"
                f"{stats_msg}"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ スコアが読み取れませんでした。画像を確認してください。")
            )

    except Exception:
        logging.exception("❌ 画像処理中にエラーが発生しました")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="❌ 画像の処理に失敗しました。もう一度お試しください。")
        )
    finally:
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception:
            logging.warning("❗ 一時画像ファイルの削除に失敗しました")



            

# ==============================
# テキストメッセージの処理
# ==============================
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    try:
        # ----------------------
        # 名前変更（開始）
        # ----------------------
        if text == "名前変更":
            supabase.table("name_change_requests").upsert({"user_id": user_id, "waiting": True}).execute()
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📝 新しい名前を入力してください"))
            return

        # ----------------------
        # 名前変更（確定）
        # ----------------------
        name_req = supabase.table("name_change_requests").select("*").eq("user_id", user_id).maybe_single().execute()
        if name_req and name_req.data and name_req.data.get("waiting"):
            new_name = text
            supabase.table("users").update({"name": new_name}).eq("id", user_id).execute()
            supabase.table("name_change_requests").delete().eq("user_id", user_id).execute()
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"✅ 名前を「{new_name}」に変更しました！"))
            return

        # ----------------------
        # 成績確認
        # ----------------------
        if text == "成績確認":
            try:
                stats_msg = build_user_stats_message(user_id)
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=stats_msg))
            except Exception:
                logging.exception("❌ 成績確認の生成に失敗しました")
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 成績情報の取得に失敗しました。"))
            return

        # ----------------------
        # 修正メニュー表示
        # ----------------------
        if is_correction_command(text):
            clear_user_correction_step(user_id)
            line_bot_api.reply_message(event.reply_token, get_correction_menu())
            return

        # ----------------------
        # 修正項目選択
        # ----------------------
        if is_correction_field_selection(text):
            set_user_correction_step(user_id, text)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📝 新しい {text} を入力してください"))
            return

        # ----------------------
        # 修正値の入力と反映
        # ----------------------
        field = get_user_correction_step(user_id)
        if field:
            value = text
            if field == "スコア":
                value = text.translate(str.maketrans("０１２３４５６７８９．", "0123456789."))
                try:
                    value = float(value)
                except ValueError:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 数値として認識できませんでした。半角数字で入力してください。"))
                    return

            latest = supabase.table("scores").select("id").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
            if latest.data:
                score_id = latest.data[0]["id"]
                supabase.table("scores").update({get_supabase_field(field): value}).eq("id", score_id).execute()

                updated = supabase.table("scores").select("*").eq("id", score_id).single().execute()
                clear_user_correction_step(user_id)

                updated_data = updated.data
                msg = (
                    f"✅ 修正完了！\n"
                    f"点数: {updated_data.get('score') or '---'}\n"
                    f"曲名: {updated_data.get('song_name') or '---'}\n"
                    f"アーティスト: {updated_data.get('artist_name') or '---'}"
                )
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
                return

    except Exception:
        logging.exception("❌ テキスト処理中にエラーが発生しました")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ エラーが発生しました。"))

# ==============================
# ヘルスチェック用
# ==============================
@app.route("/", methods=["GET"])
def index():
    return "✅ Flask x LINE Bot is running!"

if __name__ == "__main__":
    app.run(debug=True, port=8000)