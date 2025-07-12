import logging
import time
from supabase_client import supabase
from utils.musicbrainz import search_artist_in_musicbrainz

def register_artist_if_needed(artist_name: str):
    artist_name = artist_name.strip()
    
    for attempt in range(3):
        try:
            # Supabaseに既に登録されているか確認
            resp = (
                supabase.table("artists")
                .select("*")
                .filter("name_raw", "eq", artist_name)
                .maybe_single()
                .execute()
            )

            if resp and resp.data:
                return resp.data

            # MusicBrainz で検索（Supabaseに未登録の場合のみ）
            mb_data = search_artist_in_musicbrainz(artist_name)
            data = {
                "name_raw": artist_name,
                "name_normalized": mb_data["name_normalized"] if mb_data else None,
                "musicbrainz_id": mb_data["musicbrainz_id"] if mb_data else None,
                "genre_tags": mb_data["genre_tags"] if mb_data else None,
            }

            # アトミックに insert or update（競合を避ける）
            upserted = (
                supabase.table("artists")
                .upsert(data, on_conflict=["name_raw"])
                .execute()
            )

            return upserted.data[0] if upserted.data else {"name_raw": artist_name}

        except Exception as e:
            logging.warning(f"⚠️ register_artist_if_needed retry {attempt + 1}/3 failed: {e}")
            time.sleep(1)

    logging.error(f"❌ アーティスト登録処理失敗: {artist_name}")
    return {"name_raw": artist_name}
