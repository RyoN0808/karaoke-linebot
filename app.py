import logging
import math
from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from supabase_client import supabase
from datetime import datetime
from dotenv import load_dotenv
import os
import traceback
import requests
from google.cloud import vision
from google.oauth2 import service_account
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    ImageMessage,
    QuickReply,
    QuickReplyButton,
    MessageAction,
)
from utils.ocr_utils import (
    crop_regions_for_fields,
    ocr_image,
    is_correction_command,
    get_correction_menu,
    is_correction_field_selection,
    set_user_correction_step,
    get_user_correction_step,
    clear_user_correction_step
)
from utils.ema import calculate_ema
from utils.field_map import get_supabase_field
from utils.gpt_parser import parse_text_with_gpt
import re
import unicodedata


load_dotenv()
print("🔑 OPENAI_API_KEY:", os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

def _extract_score(texts):
    score_candidates = []
    for i, text in enumerate(texts[1:]):  # texts[0] は全文なのでスキップ
        desc = text.description.strip()
        vertices = text.bounding_poly.vertices
        width = abs(vertices[1].x - vertices[0].x)
        height = abs(vertices[2].y - vertices[1].y)
        area = width * height

        if re.match(r'^\d{2,3}\.\d{1,3}$', desc):
            near_texts = texts[max(0, i - 2): i + 3]
            dot_nearby = any("点" in t.description for t in near_texts)

            if dot_nearby:
                score_candidates.append({"text": desc, "area": area})

    if not score_candidates:
        return None

    best = max(score_candidates, key=lambda x: x["area"])
    return float(best["text"])

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    logging.debug("💡 Signature: %s", signature)
    logging.debug("💡 Body: %s", body)

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

        credentials = service_account.Credentials.from_service_account_file(
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        )
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
        logging.debug("🔎 パース結果: %s", parsed)

        if parsed["score"] is not None:
            try:
                profile = line_bot_api.get_profile(user_id)
                user_name = profile.display_name or "unknown"
            except Exception:
                user_name = "unknown"

            now_iso = datetime.utcnow().isoformat()
            user_resp = supabase.table("users").select("score_count").eq("id", user_id).single().execute()
            current_count = user_resp.data.get("score_count", 0) if user_resp.data else 0

            supabase.table("users").upsert({
                "id": user_id,
                "name": user_name,
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

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_msg)
        )

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
# 💬 修正項目選択用のQuickReplyメッセージ
def get_correction_menu_message():
    return TextSendMessage(
        text="🔧 修正したい項目を選んでください：",
        quick_reply=QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="スコア", text="スコア")),
            QuickReplyButton(action=MessageAction(label="曲名", text="曲名")),
            QuickReplyButton(action=MessageAction(label="アーティスト", text="アーティスト")),
            QuickReplyButton(action=MessageAction(label="コメント", text="コメント")),
        ])
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    try:
        user_id = event.source.user_id
        text = event.message.text.strip()

        # ✅ 「評価見せて」対応
        if text == "評価見せて":
            resp = supabase.table("scores")\
                .select("score, created_at")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(30)\
                .execute()

            score_list = [s["score"] for s in resp.data if s.get("score") is not None]
            latest_score = score_list[0] if score_list else None
            max_score = max(score_list) if score_list else None
            ema_score = calculate_ema(score_list) if len(score_list) >= 5 else None

            user_info = supabase.table("users")\
                .select("score_count")\
                .eq("id", user_id)\
                .single()\
                .execute()

            score_count = user_info.data["score_count"] if user_info.data else 0

            msg = (
                "📊 あなたの成績\n"
                f"・登録回数: {score_count} 回\n"
                f"・最新スコア: {latest_score or '---'}\n"
                f"・最高スコア: {max_score or '---'}\n"
                f"・EMA評価スコア: {ema_score or '---'}"
            )

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            return

        # ✅ 修正コマンドが送られたとき
        if is_correction_command(text):
            clear_user_correction_step(user_id)
            line_bot_api.reply_message(
                event.reply_token,
                get_correction_menu_message()
            )
            return

        # ✅ 修正対象項目が選ばれたとき
        if is_correction_field_selection(text):
            set_user_correction_step(user_id, text)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"📝 新しい {text} を入力してください")
            )
            return

                # ✅ 修正内容が送られたとき
        field = get_user_correction_step(user_id)
        if field:
            # スコアだけは半角に変換（全角数値対策）
            if field == "スコア":
                text = text.translate(str.maketrans(
                    "０１２３４５６７８９．", "0123456789."
                ))

                try:
                    text = float(text)
                except ValueError:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="⚠️ 数値として認識できませんでした。半角数字で入力してください。")
                    )
                    return

            latest = (
                supabase.table("scores")
                .select("id")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if latest.data:
                score_id = latest.data[0]["id"]

                # 🔧 修正実行
                supabase.table("scores").update({
                    get_supabase_field(field): text
                }).eq("id", score_id).execute()

                # 🔁 修正後の最新スコアを再取得
                updated = supabase.table("scores").select("*")\
                    .eq("id", score_id).single().execute()

                clear_user_correction_step(user_id)

                # 📨 成形して返信
                updated_data = updated.data
                msg = (
                    f"✅ スコア登録完了！\n"
                    f"点数: {updated_data.get('score') or '---'}\n"
                    f"曲名: {updated_data.get('song_name') or '---'}\n"
                    f"アーティスト: {updated_data.get('artist_name') or '---'}"
                )

                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=msg)
                )
                return


    except Exception:
        logging.exception("❌ テキストメッセージ処理中にエラーが発生しました")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="❌ エラーが発生しました。")
        )

@app.route("/", methods=["GET"])
def index():
    return "✅ Flask x LINE Bot is running!"

if __name__ == "__main__":
    app.run(debug=True, port=8000)
