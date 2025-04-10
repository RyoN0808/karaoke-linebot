import os
import re
import io
import cv2
import logging
from typing import Optional
from PIL import Image
import numpy as np
from google.cloud import vision
from google.oauth2 import service_account
from google.cloud.vision_v1.types.image_annotator import AnnotateImageResponse

# ==============================
# スコア抽出処理
# ==============================

def _calc_area(bounding_poly) -> float:
    """
    バウンディングポリゴンの頂点情報から、より堅牢な方法で面積を算出する。
    ※頂点が3点以上あることを確認し、各頂点の最小／最大のx,y値から幅と高さを算出。
    """
    if not bounding_poly or not bounding_poly.vertices:
        return 0.0
    vertices = bounding_poly.vertices
    if len(vertices) < 3:
        return 0.0
    xs = [v.x for v in vertices]
    ys = [v.y for v in vertices]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    return width * height

import re

def _extract_score(texts):
    score_candidates = []
    for i, text in enumerate(texts[1:]):  # texts[0] は全文
        desc = text.description.strip()
        vertices = text.bounding_poly.vertices
        width = abs(vertices[1].x - vertices[0].x)
        height = abs(vertices[2].y - vertices[1].y)
        area = width * height

        # スコアっぽい数字を検出（例: 90.499）
        if re.match(r'^\d{2,3}\.\d{1,3}$', desc):
            # 「点」が近くになくてもとりあえず候補に
            score_candidates.append({
                "text": desc,
                "area": area,
                "priority": 0  # 後で調整するための重み
            })

            # 「点」が近くにあれば優先度アップ
            near_texts = texts[max(0, i - 2): i + 3]
            if any("点" in t.description for t in near_texts):
                score_candidates[-1]["priority"] += 1

    if not score_candidates:
        return None

    # 優先度と面積でソート（priority → area）
    best = max(score_candidates, key=lambda x: (x["priority"], x["area"]))
    return float(best["text"])

# ==============================
# 項目ごとのOCR切り出し
# ==============================
SCORE_REGION = (100, 400, 500, 500)
SONG_NAME_REGION = (600, 400, 1000, 450)
ARTIST_NAME_REGION = (600, 450, 1000, 500)

def crop_region(image_path, region):
    img = cv2.imread(image_path)
    if img is None:
        logging.error(f"画像が見つかりません: {image_path}")
        return None
    x1, y1, x2, y2 = region
    cropped = img[y1:y2, x1:x2]
    base, ext = os.path.splitext(image_path)
    temp_path = f"{base}_crop_{x1}_{y1}{ext}"
    cv2.imwrite(temp_path, cropped)
    return temp_path

def crop_regions_for_fields(image_path):
    score_crop = crop_region(image_path, SCORE_REGION)
    song_crop = crop_region(image_path, SONG_NAME_REGION)
    artist_crop = crop_region(image_path, ARTIST_NAME_REGION)
    return score_crop, song_crop, artist_crop

def ocr_image(image_path, client):
    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()

    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description if texts else ""

def extract_text_from_image(image_path):
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path:
        logging.error("GOOGLE_APPLICATION_CREDENTIALS 環境変数が設定されていません")
        return ""
    credentials = service_account.Credentials.from_service_account_file(credentials_path)
    client = vision.ImageAnnotatorClient(credentials=credentials)
    return ocr_image(image_path, client)

# ==============================
# 修正コマンド関連
# ==============================

def is_correction_command(text: str) -> bool:
    return text == "修正" or text.lower() == "fix"

def get_correction_menu() -> str:
    return "🔧 修正したい項目を選んでください：\n[スコア] [曲名] [アーティスト] [コメント]"

def is_correction_field_selection(text: str) -> bool:
    return text in ["スコア", "曲名", "アーティスト", "コメント"]

def set_user_correction_step(user_id, field):
    from supabase_client import supabase
    supabase.table("corrections").upsert({
        "user_id": user_id,
        "field": field,
        "timestamp": "now()"
    }).execute()

def get_user_correction_step(user_id):
    from supabase_client import supabase
    resp = supabase.table("corrections").select("field").eq("user_id", user_id).limit(1).execute()
    if resp.data:
        return resp.data[0].get("field")
    return None


def clear_user_correction_step(user_id):
    from supabase_client import supabase
    supabase.table("corrections").delete().eq("user_id", user_id).execute()

def parse_correction_command(text: str):
    result = {}
    # scoreの正規表現をより柔軟に変更（例：1桁以上、少数部も柔軟にマッチ）
    patterns = {
        "score": r"score[:：]\s*(\d+[.,]?\d+)",
        "song_name": r"(?:曲名|song)[:：]\s*(\S+)",
        "artist_name": r"(?:アーティスト|artist)[:：]\s*(\S+)",
        "comment": r"(?:コメント|comment)[:：]\s*(.+)"
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result[key] = match.group(1).strip()
    return result
