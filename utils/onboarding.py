import logging
from linebot.v3.messaging import MessagingApi
from linebot.v3.messaging.models import TextMessage, ReplyMessageRequest
from utils.user_code import generate_unique_user_code
from utils.richmenu import create_and_link_rich_menu
from supabase_client import supabase

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

def handle_user_onboarding(user_id: str, user_name: str, messaging_api: MessagingApi, reply_token: str):
    """
    LINE sub ID を Supabase users.id に登録し、リッチメニューを紐付け、
    ウェルカムメッセージを送信する完全フロー
    """
    try:
        # Supabase にユーザー登録（または更新）
        user_code = generate_unique_user_code()
        supabase.table("users").upsert({
            "id": user_id,
            "name": user_name,
            "user_code": user_code,
            "score_count": 0
        }).execute()

        # リッチメニューを紐付け
        create_and_link_rich_menu(user_id)

        # ウェルカムメッセージ送信
        welcome_text = get_welcome_message(user_name)
        messaging_api.reply_message(ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=welcome_text)]
        ))

    except Exception:
        logging.exception("❌ Onboarding failed")
