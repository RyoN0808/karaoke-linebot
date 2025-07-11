import os
from linebot.v3.messaging import Configuration, ApiClient
from linebot.v3.messaging.api.rich_menu_api import RichMenuApi
from linebot.v3.messaging.models import (
    RichMenuRequest,
    RichMenuArea,
    RichMenuBounds,
    URIAction,
    MessageAction
)

def create_and_link_rich_menu(user_id: str, rich_menu_api: RichMenuApi):
    """
    リッチメニューを作成し、指定ユーザーに紐付け（またはデフォルト設定）します。

    :param user_id: LINEのuser_id（sub）
    :param rich_menu_api: RichMenuApiのインスタンス
    :return: 作成したリッチメニューID
    """
    # 📐 リッチメニュー定義
    rich_menu_request = RichMenuRequest(
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
        ]
    )

    # ✅ リッチメニュー作成
    resp = rich_menu_api.create_rich_menu(rich_menu_request)
    rich_menu_id = resp.rich_menu_id

    # 🖼️ 画像アップロード
    with open("static/richmenu.png", "rb") as f:
        rich_menu_api.set_rich_menu_image(
            rich_menu_id=rich_menu_id,
            file=f,
            content_type="image/png"
        )

    # 👥 適用
    if user_id:
        rich_menu_api.link_rich_menu_to_user(user_id=user_id, rich_menu_id=rich_menu_id)
    else:
        rich_menu_api.set_default_rich_menu(rich_menu_id=rich_menu_id)

    return rich_menu_id
