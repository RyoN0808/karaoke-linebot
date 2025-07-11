import logging
import os # 環境変数からアクセストークンを取得するために追加
from linebot.v3.messaging import (
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ApiClient, # ApiClientのインポートを追加
    Configuration, # Configurationのインポートを追加
    RichMenuMessagingApi # RichMenuMessagingApiのインポートを追加
)
from utils.user_code import generate_unique_user_code
from utils.richmenu import create_and_link_rich_menu # richmenu.pyの関数は変更が必要
from supabase_client import supabase

# ロギングの設定（必要に応じて）
logging.basicConfig(level=logging.INFO)

def get_welcome_message(user_name: str) -> str:
    """
    ユーザーへのウェルカムメッセージを生成します。
    """
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
    LINE sub ID を Supabase users.id に登録し、リッチメニューを紐付け、ウェルカムメッセージを送信します。

    Args:
        line_sub (str): LINEユーザーのユニークID (sub)。
        user_name (str): LINEユーザーの表示名。
        messaging_api (MessagingApi): LINE Messaging APIクライアントのインスタンス（メッセージ送信用）。
        reply_token (str): LINEからのReply Token。
    """
    try:
        user_code = generate_unique_user_code()

        # Supabase にユーザー登録（既存なら更新しない、初回のみ登録）
        existing = supabase.table("users").select("id").eq("id", line_sub).execute()
        if not existing.data:
            logging.info(f"ユーザー {line_sub} をSupabaseに新規登録します。")
            supabase.table("users").insert({
                "id": line_sub,
                "name": user_name,
                "user_code": user_code,
                "score_count": 0
            }).execute()
        else:
            logging.info(f"ユーザー {line_sub} は既にSupabaseに登録済みです。")

        # リッチメニュー操作用のAPIクライアントを初期化
        # MessagingApiインスタンスが使用しているApiClientを再利用するのが一般的です。
        # ただし、MessagingApiからApiClientを直接取得するメソッドがないため、
        # ここではConfigurationとApiClientを再構築する例を示します。
        # 実際のアプリケーションでは、ApiClientとConfigurationはアプリケーションの起動時に
        # 一度だけ初期化し、必要なAPIインスタンス（MessagingApi, RichMenuMessagingApiなど）に
        # 渡すように設計するのがベストプラクティスです。
        
        # LINE_CHANNEL_ACCESS_TOKENは環境変数から取得することを推奨
        channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        if not channel_access_token:
            logging.error("LINE_CHANNEL_ACCESS_TOKENが設定されていません。")
            raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is not set.")

        config = Configuration(access_token=channel_access_token)
        api_client = ApiClient(config)
        rich_menu_api = RichMenuMessagingApi(api_client) # RichMenuMessagingApiのインスタンスを作成

        # リッチメニューの作成とユーザーへの紐付け
        # create_and_link_rich_menu関数にrich_menu_apiインスタンスを渡すように変更
        logging.info(f"ユーザー {line_sub} にリッチメニューを紐付けます。")
        create_and_link_rich_menu(line_sub, rich_menu_api)

        # ウェルカムメッセージ送信
        welcome_text = get_welcome_message(user_name)
        logging.info(f"ユーザー {line_sub} にウェルカムメッセージを送信します。")
        messaging_api.reply_message(ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=welcome_text)]
        ))
        logging.info(f"ユーザー {line_sub} のオンボーディングが完了しました。")

    except Exception as e:
        logging.exception(f"❌ Onboarding failed for user {line_sub}: {e}")

