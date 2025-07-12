# utils/musicbrainz.py

import requests
import time
from supabase_client import supabase

MUSICBRAINZ_BASE_URL = "https://musicbrainz.org/ws/2"

def search_artist_in_musicbrainz(artist_name: str):
    """
    MusicBrainz API でアーティストを検索し、結果を Supabase に保存する。
    """
    time.sleep(1)  # polite usage per MusicBrainz policy

    params = {
        "query": artist_name,
        "fmt": "json"
    }
    headers = {
        "User-Agent": "KaraokeScoreApp/1.0 (ryo.nakada00.tech@gmail.com)"
    }

    response = requests.get(f"{MUSICBRAINZ_BASE_URL}/artist/", params=params, headers=headers)
    response.raise_for_status()
    data = response.json()

    # 最初の結果を使用（必要ならフィルタリング可）
    if not data.get("artists"):
        return None

    artist_data = data["artists"][0]
    musicbrainz_id = artist_data["id"]
    name_normalized = artist_data["name"]

    # ジャンルタグがあれば取得
    genre_tags = []
    if "tags" in artist_data:
        genre_tags = [tag["name"] for tag in artist_data["tags"]]

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
