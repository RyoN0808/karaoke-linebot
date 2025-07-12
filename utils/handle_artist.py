import logging
import time
from supabase_client import supabase
from utils.musicbrainz import search_artist_in_musicbrainz

def register_artist_if_needed(artist_name: str):
    from supabase import Client  # 念のため明示

    artist_name = artist_name.strip()

    for attempt in range(3):
        try:
            # filter に変更して name_raw の正確一致を検索
            resp = (
                supabase.table("artists")
                .select("*")
                .filter("name_raw", "eq", artist_name)
                .maybe_single()
                .execute()
            )

            # クエリ失敗チェック
            if not resp or not hasattr(resp, "data"):
                raise ValueError("no data returned")

            if resp.data:
                return resp.data

            # 該当なし → MusicBrainz APIへ
            mb_data = search_artist_in_musicbrainz(artist_name)
            if mb_data:
                data = {
                    "name_raw": artist_name,
                    "name_normalized": mb_data["name_normalized"],
                    "musicbrainz_id": mb_data["musicbrainz_id"],
                    "genre_tags": mb_data["genre_tags"]
                }
            else:
                data = {"name_raw": artist_name}

            # Insert
            inserted = supabase.table("artists").insert(data).execute()
            return inserted.data[0] if inserted.data else data

        except Exception as e:
            logging.warning(f"⚠️ register_artist_if_needed retry {attempt + 1}/3 failed: {e}")
            time.sleep(1)

    logging.error(f"❌ アーティスト登録処理失敗: {artist_name}")
    return {"name_raw": artist_name}
