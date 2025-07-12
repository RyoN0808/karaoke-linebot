import logging
import time
from supabase_client import supabase
from utils.musicbrainz import search_artist_in_musicbrainz

def register_artist_if_needed(artist_name: str):
    """アーティストがSupabaseに存在しなければ検索＆登録する"""
    for attempt in range(3):
        try:
            # 🔍 name_raw で既存チェック
            resp = supabase.table("artists").select("*").eq("name_raw", artist_name).maybe_single().execute()
            if resp.data:
                return resp.data

            # 📡 MusicBrainzで詳細取得
            mb_data = search_artist_in_musicbrainz(artist_name)
            if mb_data:
                data = {
                    "name_raw": artist_name,
                    "name_normalized": mb_data["name_normalized"],
                    "musicbrainz_id": mb_data["musicbrainz_id"],
                    "genre_tags": mb_data["genre_tags"]
                }
            else:
                # fallback（通信失敗や見つからない場合）
                data = {
                    "name_raw": artist_name
                }

            # Supabaseにinsert
            inserted = supabase.table("artists").insert(data).execute()
            return inserted.data[0] if inserted.data else data

        except Exception as e:
            logging.warning(f"⚠️ register_artist_if_needed retry {attempt + 1}/3 failed: {e}")
            time.sleep(1)

    logging.error(f"❌ アーティスト登録処理失敗: {artist_name}")
    return {"name_raw": artist_name}
