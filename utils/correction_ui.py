# ✅ correction_ui.py
# フォーム風の一括修正をLINE Botで実現

from linebot.models import (
    TextSendMessage, FlexSendMessage, BubbleContainer, BoxComponent,
    TextComponent, ButtonComponent, MessageAction
)

# 一時的な修正キャッシュ（後で Supabase に切り替え可能）
user_correction_cache = {}

def set_temp_value(user_id, field, value):
    user_correction_cache.setdefault(user_id, {})[field] = value

def get_temp_value(user_id):
    return user_correction_cache.get(user_id, {})

def clear_temp_value(user_id):
    user_correction_cache.pop(user_id, None)

def send_correction_form(reply_token, line_bot_api):
    flex = FlexSendMessage(
        alt_text="修正フォーム",
        contents={
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": "🛠 修正フォーム",
                        "weight": "bold",
                        "size": "xl",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": "修正したい項目を選んでください",
                        "size": "sm",
                        "color": "#888888",
                        "wrap": True
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "📊 点数を修正", "text": "スコア"},
                        "style": "primary",
                        "margin": "md"
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "🎵 曲名を修正", "text": "曲名"},
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "👤 アーティストを修正", "text": "アーティスト"},
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "💬 コメントを修正", "text": "コメント"},
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "✅ 全て入力完了！", "text": "修正完了"},
                        "style": "secondary",
                        "color": "#aaaaaa",
                        "margin": "lg"
                    }
                ]
            }
        }
    )
    line_bot_api.reply_message(reply_token, flex)


# ✅ app.py 側に追加する TextMessage ハンドラの例

