# utils/richmenu.py

from linebot.v3.messaging.models import RichMenuRequest, RichMenuArea, RichMenuBounds, URIAction, MessageAction

def create_and_link_rich_menu(user_id: str, rich_menu_api):
    # ① リッチメニュー作成
    rich_menu = RichMenuRequest(
      size={"width":1200,"height":405},
      selected=True,
      name="スコア投稿メニュー",
      chat_bar_text="メニュー",
      areas=[
        RichMenuArea(
          bounds=RichMenuBounds(x=0,y=0,width=400,height=405),
          action=URIAction(uri="line://nv/camera",label="カメラ起動")
        ),
        # … 他のボタン
      ]
    )
    rich_menu_id = rich_menu_api.create_rich_menu(rich_menu).rich_menu_id

    # ② 画像アップロード
    with open("static/richmenu.png", "rb") as f:
        rich_menu_api.set_rich_menu_image(
            rich_menu_id=rich_menu_id,
            file=f,
            content_type="image/png"
        )

    # ③ ユーザーへ紐付け
    rich_menu_api.link_rich_menu_to_user(
        user_id=user_id,
        rich_menu_id=rich_menu_id
    )
    return rich_menu_id
