from linebot import LineBotApi
from linebot.models import TextSendMessage
from utils.user_code import generate_unique_user_code
from utils.richmenu import create_and_link_rich_menu
from supabase_client import supabase

def get_welcome_message(user_name: str) -> str:
    return (
       f"{user_name}さん、こんにちは！\n"
        "友だち追加ありがとうございます🎉\n\n"
        "このアカウントでは、カラオケの**平均点とレーティング**を算出できます！\n"
        "使い方はとっても簡単!\n"
        "🎤 採点画面の写真を送るだけ！📸\n\n"
        "✅ スコアを5件以上登録すると、レーティングが表示されます！\n\n"
        "📈「成績確認」→ ランク＆平均スコアの確認\n"
        "🛠「修正」→ 登録済みのスコアを訂正できます\n\n"
        "ぜひお試しください！✨"
    )



def handle_user_onboarding(user_id: str, user_name: str, line_bot_api: LineBotApi, reply_token: str):
    try:
        # ユーザー登録
        user_code = generate_unique_user_code()
        supabase.table("users").upsert({
            "id": user_id,
            "name": user_name,
            "user_code": user_code,
            "score_count": 0
        }).execute()

        # リッチメニューの作成と紐付け
        create_and_link_rich_menu(user_id)

        # ウェルカムメッセージ送信
        welcome_text = get_welcome_message()
        line_bot_api.reply_message(reply_token, TextSendMessage(text=welcome_text))

    except Exception as e:
        # 失敗してもログだけ残して無視（致命的でない）
        import logging
        logging.exception("❌ Onboarding failed")
