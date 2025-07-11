import logging
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.messaging.models import ReplyMessageRequest, TextMessage
from utils.user_code import generate_unique_user_code
from supabase_client import supabase
from .richmenu import create_and_link_rich_menu

def get_welcome_message(user_name: str) -> str:
    return (
        f"{user_name}さん、こんにちは！\n"
        "友だち追加ありがとうございます🎉\n\n"
        "このアカウントでは、カラオケの **平均点とレーティング** を算出できます！\n"
        "🎤 採点画面の写真を送るだけ！📸\n\n"
        "✅ スコアを5件以上登録すると、レーティングが表示されます！\n"
        "📈「成績確認」→ ランク＆平均スコアの確認\n"
        "🛠「修正」→ 登録済みスコアの訂正\n\n"
        "ぜひお試しください！✨"
    )

def handle_user_onboarding(
    line_sub: str,
    user_name: str,
    messaging_api: MessagingApi,
    reply_token: str
):
    try:
        # Supabase にユーザー登録（初回のみ）
        code = generate_unique_user_code()
        resp = supabase.table("users").select("id").eq("id", line_sub).execute()
        if not resp.data:
            supabase.table("users").insert({
                "id": line_sub,
                "name": user_name,
                "user_code": code,
                "score_count": 0
            }).execute()
            logging.info(f"Supabase に新規ユーザー登録: {line_sub}")
        else:
            logging.info(f"ユーザー {line_sub} は既に登録済み")

        # リッチメニュー作成＆デフォルト適用
        # └ 新規友だちにも自動的に全ユーザー共通メニューを適用
        create_and_link_rich_menu(user_id=None)

        # ウェルカムメッセージ送信
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
