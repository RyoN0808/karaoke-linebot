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
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage,
)

from supabase_client import supabase
from utils.ocr_utils import (
    is_correction_command, get_correction_menu,
    is_correction_field_selection, set_user_correction_step,
    get_user_correction_step, clear_user_correction_step,
    _extract_score
)
from utils.ema import calculate_ema
from utils.field_map import get_supabase_field
from utils.gpt_parser import parse_text_with_gpt
from utils.user_code import generate_unique_user_code
import requests
import json

load_dotenv()
app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

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

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    try:
        user_id = event.source.user_id
        message_content = line_bot_api.get_message_content(event.message.id)
        image_path = f"/tmp/{event.message.id}.jpg"
        with open(image_path, "wb") as f:
            for chunk in message_content.iter_content():
                f.write(chunk)

        credentials_info = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
        credentials = service_account.Credentials.from_service_account_info(credentials_info)
        client = vision.ImageAnnotatorClient(credentials=credentials)

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
            profile = line_bot_api.get_profile(user_id)
            user_name = profile.display_name or "unknown"
            now_iso = datetime.utcnow().isoformat()

            user_resp = supabase.table("users").select("score_count, user_code").eq("id", user_id).maybe_single().execute()

            # 安全に data を取得（user_resp や user_resp.data が None でもOK）
            current_data = (user_resp.data if user_resp and user_resp.data else {})
            
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

            reply_msg = (
                f"✅ スコア登録完了！\n"
                f"点数: {parsed['score']}\n"
                f"曲名: {parsed['song_name'] or '---'}\n"
                f"アーティスト: {parsed['artist_name'] or '---'}"
            )
        else:
            reply_msg = "⚠️ スコアが読み取れませんでした。画像を確認してください。"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

    except Exception:
        logging.exception("画像処理中にエラーが発生しました")
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

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    try:
        user_id = event.source.user_id
        text = event.message.text.strip()

        if text == "評価見せて":
            resp = supabase.table("scores").select("score, created_at").eq("user_id", user_id).order("created_at", desc=True).limit(30).execute()
            score_list = [s["score"] for s in resp.data if s.get("score") is not None]
            latest_score = score_list[0] if score_list else None
            max_score = max(score_list) if score_list else None
            ema_score = calculate_ema(score_list) if len(score_list) >= 5 else None

            user_info = supabase.table("users").select("score_count").eq("id", user_id).single().execute()
            score_count = user_info.data["score_count"] if user_info.data else 0

            msg = (
                "\U0001F4CA あなたの成績\n"
                f"・登録回数: {score_count} 回\n"
                f"・最新スコア: {latest_score or '---'}\n"
                f"・最高スコア: {max_score or '---'}\n"
                f"・EMA評価スコア: {ema_score or '---'}"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return

        if is_correction_command(text):
            clear_user_correction_step(user_id)
            line_bot_api.reply_message(event.reply_token, get_correction_menu())
            return

        if is_correction_field_selection(text):
            set_user_correction_step(user_id, text)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📝 新しい {text} を入力してください"))
            return

        field = get_user_correction_step(user_id)
        if field:
            if field == "スコア":
                text = text.translate(str.maketrans("０１２３４５６７８９．", "0123456789."))
                try:
                    text = float(text)
                except ValueError:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 数値として認識できませんでした。半角数字で入力してください。"))
                    return

            latest = supabase.table("scores").select("id").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
            if latest.data:
                score_id = latest.data[0]["id"]
                supabase.table("scores").update({get_supabase_field(field): text}).eq("id", score_id).execute()

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

@app.route("/", methods=["GET"])
def index():
    return "✅ Flask x LINE Bot is running!"

if __name__ == "__main__":
    app.run(debug=True, port=8000)
