import logging
from linebot.v3.messaging import (
    MessagingApi, ReplyMessageRequest, TextMessage
)
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

def handle_user_onboarding(
    line_sub: str,
    user_name: str,
    messaging_api: MessagingApi,
    reply_token: str
):
    """
    フォロー時のオンボーディング処理。
    - Supabase へ登録
    - リッチメニュー作成＆紐付け
    - ウェルカムメッセージ送信
    """
    try:
        # 1. Supabase 登録
        user_code = generate_unique_user_code()
        existing = supabase.table("users") \
            .select("id") \
            .eq("id", line_sub) \
            .execute()

        if not existing.data:
            logging.info(f"Supabase に新規ユーザー登録: {line_sub}")
            supabase.table("users").insert({
                "id": line_sub,
                "name": user_name,
                "user_code": user_code,
                "score_count": 0
            }).execute()
        else:
            logging.info(f"ユーザー {line_sub} は既に登録済み")

        # 2. リッチメニュー作成＆紐付け
        logging.info(f"ユーザー {line_sub} にリッチメニューを紐付け")
        create_and_link_rich_menu(line_sub, messaging_api)

        # 3. ウェルカムメッセージ送信
        welcome = get_welcome_message(user_name)
        messaging_api.reply_message(ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=welcome)]
        ))
        logging.info(f"オンボーディング完了: {line_sub}")

    except Exception:
        logging.exception(f"❌ Onboarding failed for user {line_sub}")
        # 必要に応じてユーザーへエラーメッセージを返す、など
