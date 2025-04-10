# 日本語の修正項目と Supabase のカラム名の対応表
FIELD_MAP = {
    "スコア": "score",
    "曲名": "song_name",
    "アーティスト": "artist_name",
    "コメント": "comment"
}

# 日本語 → Supabase カラム名 を返す関数
def get_supabase_field(japanese_field: str) -> str:
    return FIELD_MAP.get(japanese_field)
