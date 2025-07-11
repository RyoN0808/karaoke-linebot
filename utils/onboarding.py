import logging
import os
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, TextMessage, Configuration, ApiClient
from linebot.v3.messaging.api.rich_menu_api import RichMenuApi
from utils.user_code import generate_unique_user_code
from utils.richmenu import create_and_link_rich_menu
from supabase_client import supabase

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
    LINE Login の sub を Supabase の users.id として登録し、
    リッチメニューを紐付け、ウェルカムメッセージを送信します。
    """
    try:
        # 1) Supabase にユーザー登録（初回のみ）
        user_code = generate_unique_user_code()
        existing = supabase.table("users").select("id").eq("id", line_sub).execute()
        if not existing.data:
            logging.info(f"ユーザー {line_sub} を Supabase に新規登録します。")
            supabase.table("users").insert({
                "id": line_sub,
                "name": user_name,
                "user_code": user_code,
                "score_count": 0
            }).execute()
        else:
            logging.info(f"ユーザー {line_sub} は既に登録済みです。")

        # 2) RichMenuApi の準備
        channel_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        if not channel_token:
            raise ValueError("LINE_CHANNEL_ACCESS_TOKEN が設定されていません。")
        config = Configuration(access_token=channel_token)
        api_client = ApiClient(config)
        rich_menu_api = RichMenuApi(api_client)

        # 3) リッチメニューを作成＆ユーザーに紐付け
        logging.info(f"ユーザー {line_sub} にリッチメニューを紐付けます。")
        create_and_link_rich_menu(line_sub, rich_menu_api)

        # 4) ウェルカムメッセージ送信
        welcome_text = get_welcome_message(user_name)
        logging.info(f"ユーザー {line_sub} にウェルカムメッセージを送信します。")
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=welcome_text)]
            )
        )
        logging.info(f"ユーザー {line_sub} のオンボーディングが完了しました。")

    except Exception as e:
        logging.exception(f"❌ Onboarding failed for user {line_sub}: {e}")
