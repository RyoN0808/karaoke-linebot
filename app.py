import os
import logging
import time
from datetime import datetime
from flask import Flask, request, abort
from dotenv import load_dotenv
from google.cloud import vision

from linebot.v3 import WebhookHandler
from linebot.v3.webhooks import MessageEvent, FollowEvent, TextMessageContent
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import ReplyMessageRequest, TextMessage
from linebot.exceptions import InvalidSignatureError
from linebot import LineBotApi

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
from utils.onboarding import handle_user_onboarding

# Flask setup
app = Flask(__name__)

env_file = os.getenv("ENV_FILE", ".env.dev")
load_dotenv(dotenv_path=env_file)

DEBUG = os.getenv("DEBUG", "False").lower() == "true"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

log_level = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")

print(f"[INFO] Loaded env file: {env_file}")

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
line_bot_api_v2 = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

# グローバル：画像送信制御
user_send_history = {}

@app.route("/", methods=["GET"])
def index():
    return "✅ Flask x LINE Bot is running!"

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
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception:
        logging.exception("❌ Webhook processing error")
        abort(400)
    return "OK"

@handler.add(MessageEvent)
def handle_message_event(event):
    message = event.message
    if hasattr(message, "content_provider") and message.content_provider.type != "none":
        handle_image(event)
    elif isinstance(message, TextMessageContent):
        handle_text(event)

@handler.add(FollowEvent)
def handle_follow(event):
    try:
        user_id = event.source.user_id
        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            profile = messaging_api.get_profile(user_id=user_id)
            user_name = profile.display_name or "unknown"
            handle_user_onboarding(user_id, user_name, messaging_api, event.reply_token)
    except Exception:
        logging.exception("❌ Follow event error")

def handle_image(event):
    image_path = None
    try:
        user_id = event.source.user_id
        now = time.time()
        history = user_send_history.setdefault(user_id, [])
        history[:] = [t for t in history if now - t < 80]
        history.append(now)
        if len(history) > 2:
            with ApiClient(configuration) as api_client:
                messaging_api = MessagingApi(api_client)
                messaging_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="⚠️ 一度に送信できる画像は最大2枚までです。少し待ってから再送信してください。")]
                ))
            return

        message_content = line_bot_api_v2.get_message_content(event.message.id)
        image_path = f"/tmp/{event.message.id}.jpg"
        with open(image_path, "wb") as f:
            for chunk in message_content.iter_content():
                f.write(chunk)

        client = vision.ImageAnnotatorClient()
        with open(image_path, "rb") as f:
            content = f.read()
        vision_resp = client.text_detection(image=vision.Image(content=content))
        texts = vision_resp.text_annotations
        raw_text = texts[0].description if texts else ""
        score = _extract_score(texts)
        structured = parse_text_with_gpt(raw_text)

        parsed = {
            "score": score,
            "song_name": structured.get("song_name"),
            "artist_name": structured.get("artist_name")
        }

        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)

            if parsed["score"] is None:
                messaging_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="⚠️ スコアが読み取れませんでした。画像を確認してください。")]
                ))
                return

            if not (30.0 <= parsed["score"] < 100.0):
                messaging_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="⚠️ 点数は30.000以上100.000未満のみ登録できます。")]
                ))
                return

            profile = messaging_api.get_profile(user_id=user_id)
            user_name = profile.display_name or "unknown"
            now_iso = datetime.utcnow().isoformat()

            user_resp = supabase.table("users").select("score_count,user_code").eq("id", user_id).maybe_single().execute()
            curr = user_resp.data or {}
            count = curr.get("score_count", 0)
            user_code = curr.get("user_code") or generate_unique_user_code()

            supabase.table("users").upsert({
                "id": user_id,
                "name": user_name,
                "user_code": user_code,
                "score_count": count + 1,
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
                logging.exception("❌ 成績情報生成エラー")
                stats_msg = "⚠️ 成績情報の取得に失敗しました。"

            reply = (
                f"✅ スコア登録完了！\n"
                f"点数: {parsed['score']}\n"
                f"曲名: {parsed['song_name'] or '---'}\n"
                f"アーティスト: {parsed['artist_name'] or '---'}\n\n"
                f"{stats_msg}"
            )
            messaging_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            ))

    except Exception:
        logging.exception("❌ Image event error")
        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            messaging_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="❌ 画像の処理に失敗しました。もう一度お試しください。")]
            ))

    finally:
        if image_path and os.path.exists(image_path):
            os.remove(image_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)