# utils/onboarding.py
import os
import logging
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.messaging.models import ReplyMessageRequest, TextMessage
from utils.user_code import generate_unique_user_code
from supabase_client import supabase
from utils.richmenu import create_and_link_rich_menu

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
    reply_token: str
):
    """
    フォロー時のオンボーディング：
      1) Supabase にユーザー登録／存在チェック
      2) リッチメニュー作成＆紐付け
      3) ウェルカムメッセージ送信
    """
    try:
        # 1) Supabase に登録 or 存在チェック
        user_code = generate_unique_user_code()
        existing = supabase.table("users") \
                           .select("id") \
                           .eq("id", line_sub) \
                           .execute()
        if not existing.data:
            logging.info(f"Supabase に新規ユーザー登録: {line_sub}")
            supabase.table("users").insert({
                "id":          line_sub,
                "name":        user_name,
                "user_code":   user_code,
                "score_count": 0
            }).execute()
        else:
            logging.info(f"ユーザー {line_sub} は既に登録済み")

        # 2) LINE Messaging API クライアント初期化
        channel_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        if not channel_token:
            raise RuntimeError("環境変数 LINE_CHANNEL_ACCESS_TOKEN が設定されていません")
        config     = Configuration(access_token=channel_token)
        api_client = ApiClient(config)
        messaging_api = MessagingApi(api_client)

        # 3) リッチメニュー作成＆ユーザー紐付け
        logging.info(f"{line_sub} にリッチメニューを紐付けます")
        create_and_link_rich_menu(line_sub, messaging_api)

        # 4) ウェルカムメッセージ送信
        welcome_text = get_welcome_message(user_name)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=welcome_text)]
            )
        )
        logging.info(f"オンボーディング完了: {line_sub}")

    except Exception:
        logging.exception(f"❌ Onboarding failed for user {line_sub}")
        # 必要ならここでユーザーへのエラー通知を追加
