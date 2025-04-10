# 修正フローの状態管理（最初はメモリベース、将来はRedisなどでもOK）
user_correction_state = {}

def is_correction_trigger(text):
    return text.strip() == "修正"

def send_correction_menu(line_bot_api, reply_token):
    # ボタンテンプレートを返す処理
    ...

def handle_correction_selection(text, user_id):
    # 「修正:〇〇」が来たときの処理
    ...

def apply_correction(user_id, new_value, supabase, line_bot_api, reply_token):
    # 入力値を受け取って、DB更新まで実行する処理
    ...
