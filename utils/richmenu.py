import os
import logging
from linebot.v3.messaging import ApiClient, Configuration, MessagingApi, MessagingApiBlob
from linebot.v3.messaging.models import (
    RichMenuRequest, RichMenuArea, RichMenuBounds,
    URIAction, MessageAction
)

def create_and_link_rich_menu(user_id: str | None = None) -> str:
    """
    1) リッチメニューを作成
    2) 画像をアップロード
    3) 全ユーザー or 特定ユーザーに適用
    """
    # 環境変数からチャネルアクセストークン取得
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN is not set")

    config = Configuration(access_token=token)
    with ApiClient(config) as api_client:
        text_api = MessagingApi(api_client)       # JSON API
        blob_api = MessagingApiBlob(api_client)   # 画像などバイナリAPI

        # ―― 1) リッチメニュー本体作成 ――
        rm_request = RichMenuRequest(
            size={"width": 1200, "height": 405},
            selected=False,
            name="スコア投稿メニュー",
            chat_bar_text="メニュー",
            areas=[
                RichMenuArea(
                    bounds=RichMenuBounds(x=0,   y=0, width=400, height=405),
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
        resp = text_api.create_rich_menu(rich_menu_request=rm_request)
        rich_menu_id = resp.rich_menu_id
        logging.info(f"✅ リッチメニュー作成: {rich_menu_id}")

        # ―― 2) 画像アップロード ――
        image_path = os.path.join(os.path.dirname(__file__), "../static/richmenu.png")
        with open(image_path, "rb") as f:
            body = bytearray(f.read())
        blob_api.set_rich_menu_image(
            rich_menu_id=rich_menu_id,
            body=body,
            _headers={"Content-Type": "image/png"}
        )
        logging.info("✅ リッチメニュー画像アップロード完了")

        # ―― 3) 適用設定 ――
        if user_id:
            # 特定ユーザーにのみリンク
            text_api.link_rich_menu_id_to_user(user_id=user_id, rich_menu_id=rich_menu_id)
            logging.info(f"✅ リッチメニュー {rich_menu_id} をユーザー {user_id} にリンク")
        else:
            # 全ユーザー共通のデフォルトリッチメニューに設定
            text_api.set_default_rich_menu(rich_menu_id=rich_menu_id)
            logging.info(f"✅ リッチメニュー {rich_menu_id} を全ユーザーのデフォルトに設定")

        return rich_menu_id
