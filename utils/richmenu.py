from linebot.v3.messaging import MessagingApi

# 使用するリッチメニューID
RICH_MENU_ID = "richmenu-81d23e94b05ddc9b1494a4d1e9c412f4"

def create_and_link_rich_menu(user_id: str):
    """
    既存のリッチメニューIDをLINEユーザーに紐付ける
    """
    messaging_api = MessagingApi()  # MessagingApiインスタンス生成

    # ユーザーにリッチメニューを紐付け
    messaging_api.link_rich_menu_to_user(
        user_id=user_id,
        rich_menu_id=RICH_MENU_ID
    )
