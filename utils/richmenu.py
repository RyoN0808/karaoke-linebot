# utils/richmenu.py
import os
import logging
from linebot.v3.messaging import RichMenuApi, MessagingApi
from linebot.v3.messaging.models import (
    RichMenuRequest,
    RichMenuBounds,
    RichMenuArea,
    URIAction,
    MessageAction
)

def create_and_link_rich_menu(user_id: str, api_client):
    """
    1) リッチメニューを作成
    2) 画像をアップロード
    3) ユーザーへ紐付け
    """
    rich_menu_api = RichMenuApi(api_client)
    messaging_api = MessagingApi(api_client)

    # --- 1) リッチメニュー作成 ---
    request = RichMenuRequest(
        size={"width": 1200, "height": 405},
        selected=False,
        name="スコア投稿メニュー",
        chat_bar_text="メニュー",
        areas=[
            RichMenuArea(
                bounds=RichMenuBounds(x=0, y=0, width=400, height=405),
                action=URIAction(uri="line://nv/camera", label="カメラ起動")
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=400, y=0, width=400, height=405),
                action=MessageAction(label="成績確認", text="成績確認")
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=800, y=0, width=400, height=405),
                action=MessageAction(label="修正", text="修正")
            ),
        ]
    )
    resp = rich_menu_api.create_rich_menu(request)
    menu_id = resp.rich_menu_id
    logging.info(f"✅ リッチメニュー作成: {menu_id}")

    # --- 2) 画像アップロード ---
    # static/richmenu.png はプロジェクトに同梱しておく
    image_path = os.path.join(os.path.dirname(__file__), "../static/richmenu.png")
    with open(image_path, "rb") as f:
        rich_menu_api.set_rich_menu_image(
            rich_menu_id=menu_id,
            file=f,
            content_type="image/png"
        )
    logging.info("✅ リッチメニュー画像アップロード完了")

    # --- 3) ユーザーへ紐付け ---
    messaging_api.link_rich_menu_id_to_user(user_id=user_id, rich_menu_id=menu_id)
    logging.info(f"✅ ユーザー {user_id} へリッチメニュー紐付け完了")

    return menu_id
