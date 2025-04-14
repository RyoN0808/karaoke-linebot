from linebot import LineBotApi
from linebot.models import RichMenu, RichMenuArea, RichMenuBounds, URIAction
import os

def create_camera_richmenu():
    line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

    rich_menu_to_create = RichMenu(
        size={"width": 2500, "height": 843},
        selected=True,
        name="カメラ起動メニュー",
        chat_bar_text="メニュー",
        areas=[
            RichMenuArea(
                bounds=RichMenuBounds(x=0, y=0, width=2500, height=843),
                action=URIAction(label="カメラ起動", uri="line://nv/camera/")
            )
        ]
    )

    rich_menu_id = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
    return rich_menu_id
