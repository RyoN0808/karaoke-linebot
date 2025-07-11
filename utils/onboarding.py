import logging
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import ReplyMessageRequest, TextMessage
from supabase_client import supabase
from utils.user_code import generate_unique_user_code
from utils.richmenu import create_and_link_rich_menu
import os

logging.basicConfig(level=logging.INFO)

def get_welcome_message(user_name: str) -> str:
    return (
        f"{user_name}さん、こんにちは！\n"
        "友だち追加ありがとうございます🎉\n\n"
        "このアカウントでは、カラオケの **平均点とレーティング** を算出できます！\n"
        "使い方はとっても簡単!\n"
        "🎤 採点画面の写真を送るだけ！📸\n\n"
        "✅ スコアを5件以上登録すると、レーティングが表示されます！\n\n"
        "📈「成績確認」→ ランク＆平均スコアの確認\n"
        "🛠「修正」→ 登録済みのスコアを訂正できます\n\n"
        "ぜひお試しください！✨"
    )

def handle_user_onboarding(line_sub: str, user_name: str, messaging_api: MessagingApi, reply_token: str):
    """
    LINE Login で取得した sub を Supabase users.id に使い、
    リッチメニューの紐付けとウェルカムメッセージを送信します。
    """
    try:
        # 1) Supabase にユーザー登録 or 既存か確認
        user_code = generate_unique_user_code()
        exists = supabase.table("users").select("id").eq("id", line_sub).execute()
        if not exists.data:
            logging.info(f"Supabase に新規ユーザー登録: {line_sub}")
            supabase.table("users").insert({
                "id": line_sub,
                "name": user_name,
                "user_code": user_code,
                "score_count": 0
            }).execute()
        else:
            logging.info(f"ユーザー {line_sub} は既に登録済み")

        # 2) リッチメニュー紐付け
        #    WebhookHandler からは MessagingApi が渡されているはずなので再生成不要
        logging.info(f"ユーザー {line_sub} にリッチメニューを紐付け")
        create_and_link_rich_menu(line_sub, messaging_api)

        # 3) ウェルカムメッセージ送信
        welcome = get_welcome_message(user_name)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=welcome)]
            )
        )
        logging.info(f"オンボーディング完了: {line_sub}")

    except Exception:
        logging.exception(f"❌ Onboarding failed for {line_sub}")
