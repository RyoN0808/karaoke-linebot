import os
from linebot.v3.messaging.api.rich_menu_api import RichMenuApi
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import (
    RichMenuRequest,
    RichMenuArea,
    RichMenuBounds,
    URIAction,
    MessageAction,
)

def create_and_link_rich_menu(user_id: str, rich_menu_api: RichMenuApi = None) -> str:
    """
    リッチメニューを作成し、画像アップロード・ユーザー／デフォルトへの紐付けまで行います。
    - user_id を渡すと個別ユーザーへ。
    - user_id に None を渡すとデフォルトとして全員に。
    """
    # 1) MessagingApi インスタンスを自前で用意する場合
    if messaging_api is None:
        channel_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        if not channel_token:
            raise ValueError("LINE_CHANNEL_ACCESS_TOKEN が設定されていません。")
        config = Configuration(access_token=channel_token)
        api_client = ApiClient(config)
        messaging_api = MessagingApi(api_client)

    # 2) リッチメニュー定義
    rich_menu = RichMenuRequest(
        size={"width": 1200, "height": 405},
        selected=True,
        name="スコア投稿メニュー",
        chat_bar_text="メニュー",
        areas=[
            RichMenuArea(
                bounds=RichMenuBounds(x=0, y=0, width=400, height=405),
                action=URIAction(uri="line://nv/camera", label="カメラ起動"),
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=400, y=0, width=400, height=405),
                action=MessageAction(label="成績確認", text="成績確認"),
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=800, y=0, width=400, height=405),
                action=MessageAction(label="修正", text="修正"),
            ),
        ],
    )

    # 3) リッチメニュー作成
    resp = messaging_api.create_rich_menu(rich_menu)
    rich_menu_id = resp.rich_menu_id

    # 4) 画像アップロード
    with open("static/richmenu.png", "rb") as f:
        messaging_api.set_rich_menu_image(
            rich_menu_id=rich_menu_id,
            file=f,
            content_type="image/png",
        )

    # 5) 紐付け
    if user_id:
        messaging_api.link_rich_menu_to_user(user_id=user_id, rich_menu_id=rich_menu_id)
    else:
        messaging_api.set_default_rich_menu(rich_menu_id=rich_menu_id)

    return rich_menu_id
