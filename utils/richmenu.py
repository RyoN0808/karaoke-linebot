import logging
from linebot.v3.messaging import MessagingApi
from linebot.v3.messaging.models import (
    RichMenuRequest, RichMenuSize,
    RichMenuArea, RichMenuBounds,
    URIAction, MessageAction
)

def create_and_link_rich_menu(user_id: str, messaging_api: MessagingApi) -> str:
    """
    リッチメニューを作成し、指定ユーザーに紐付ける。
    """
    try:
        # リッチメニュー定義＆作成
        req = RichMenuRequest(
            size=RichMenuSize(width=1200, height=405),
            selected=True,
            name="スコア投稿メニュー",
            chat_bar_text="メニュー",
            areas=[
                RichMenuArea(
                    bounds=RichMenuBounds(x=0, y=0, width=400, height=405),
                    action=URIAction(label="カメラ起動", uri="line://nv/camera")
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
        resp = messaging_api.create_rich_menu(rich_menu_request=req)
        menu_id = resp.rich_menu_id
        logging.info(f"✅ リッチメニュー作成: {menu_id}")

        # ユーザーへの紐付け
        messaging_api.link_rich_menu_id_to_user(user_id, menu_id)
        logging.info(f"✅ リッチメニュー {menu_id} をユーザー {user_id} に紐付け")

        return menu_id

    except Exception:
        logging.exception("❌ リッチメニュー作成・紐付けで例外発生")
        raise
