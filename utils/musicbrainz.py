import requests
import time
import logging
from requests.exceptions import RequestException
from supabase_client import supabase

MUSICBRAINZ_BASE_URL = "https://musicbrainz.org/ws/2"
USER_AGENT = "KaraokeScoreApp/1.0 (ryo.nakada00.tech@gmail.com)"

def search_artist_in_musicbrainz(artist_name: str):
    """
    MusicBrainz APIでアーティストを検索し、結果をSupabaseに保存する。
    通信失敗時は最大3回まで再試行する。
    """
    for attempt in range(3):
        try:
            time.sleep(1)  # polite usage per MusicBrainz policy

            params = {
                "query": artist_name,
                "fmt": "json"
            }
            headers = {
                "User-Agent": USER_AGENT
            }

            response = requests.get(
                f"{MUSICBRAINZ_BASE_URL}/artist/",
                params=params,
                headers=headers,
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("artists"):
                return None

            artist_data = data["artists"][0]
            musicbrainz_id = artist_data["id"]
            name_normalized = artist_data["name"]

            genre_tags = [tag["name"] for tag in artist_data.get("tags", [])]

            # Supabase に UPSERT
            supabase.table("artists").upsert({
                "musicbrainz_id": musicbrainz_id,
                "name_raw": artist_name,
                "name_normalized": name_normalized,
                "genre_tags": genre_tags
            }, on_conflict=["musicbrainz_id"]).execute()

            return {
                "musicbrainz_id": musicbrainz_id,
                "name_normalized": name_normalized,
                "genre_tags": genre_tags
            }

        except RequestException as e:
            logging.warning(f"⚠️ MusicBrainz API リクエスト失敗 (attempt {attempt + 1}/3): {e}")
            time.sleep(1)

    logging.error(f"❌ MusicBrainz API によるアーティスト検索失敗: {artist_name}")
    return None
