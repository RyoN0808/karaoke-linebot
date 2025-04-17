from linebot import LineBotApi
from linebot.models import RichMenu, RichMenuArea, RichMenuBounds, URIAction, MessageAction
import os

def create_and_link_rich_menu(user_id=None):
    line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

    # 📐 リッチメニュー定義
    rich_menu = RichMenu(
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
    rich_menu_id = line_bot_api.create_rich_menu(rich_menu)

    # 🖼️ 画像アップロード
    with open("static/richmenu.png", 'rb') as f:
        line_bot_api.set_rich_menu_image(rich_menu_id, "image/png", f)

    # 👥 適用（user_id が指定されていれば個別に、なければデフォルトに）
    if user_id:
        line_bot_api.link_rich_menu_to_user(user_id, rich_menu_id)
    else:
        line_bot_api.set_default_rich_menu(rich_menu_id)

    return rich_menu_id
