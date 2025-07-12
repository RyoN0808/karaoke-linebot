# utils/handle_artist.py

import logging
import time
import requests
from supabase_client import supabase
from utils.musicbrainz import search_artist_in_musicbrainz

MAX_RETRIES = 3

def register_artist_if_needed(artist_name: str) -> dict:
    """
    Supabaseに存在しないアーティスト名の場合は、MusicBrainz APIで検索・登録を試みる。
    通信エラー時は最大3回まで再試行。失敗しても Supabase 登録は実行される。
    """
    try:
        # 既にSupabaseに存在するかチェック
        resp = supabase.table("artists").select("*").eq("name", artist_name).execute()
        if resp.data:
            logging.info(f"✅ 既存アーティスト: {artist_name}")
            return resp.data[0]

        # 存在しないので MusicBrainz で検索（最大3回リトライ）
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                mb_data = search_artist_in_musicbrainz(artist_name)
                if mb_data:
                    # Supabase に登録
                    insert_data = {
                        "name": mb_data["name"],
                        "musicbrainz_id": mb_data["id"]
                    }
                    insert_resp = supabase.table("artists").insert(insert_data).execute()
                    logging.info(f"🎶 Supabaseに新規アーティスト登録: {insert_data}")
                    return insert_data
                break  # MBから結果がない場合はループ抜ける
            except requests.exceptions.RequestException as e:
                logging.warning(f"⚠️ MusicBrainz通信失敗（{attempt}回目）: {e}")
                time.sleep(1.5)  # 少し待つ

    except Exception as e:
        logging.exception(f"❌ アーティスト登録処理に失敗: {e}")

    # API失敗 or MusicBrainzに見つからない場合でも Supabase 登録を試みる
    try:
        fallback_data = {"name": artist_name}
        supabase.table("artists").insert(fallback_data).execute()
        logging.info(f"🪪 fallback登録: {artist_name}")
        return fallback_data
    except Exception:
        logging.exception(f"❌ fallback登録も失敗: {artist_name}")
        return {}
