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

def _extract_score(ocr_response: AnnotateImageResponse) -> Optional[float]:
    texts = ocr_response.text_annotations
    if not texts:
        return None

    candidates = []
    # texts[0] は全体のテキストなので、それ以降を個別の候補とする
    for annotation in texts[1:]:
        text = annotation.description
        if "点" not in text:
            continue
        # 数字の部分が含まれているかチェック（例：9.500 や 10.000 など）
        if not re.search(r"\d+[.,]?\d*", text):
            continue

        area = _calc_area(annotation.bounding_poly)
        # カンマをドットに置換してから数値部分を抽出
        score_match = re.search(r"\d+[.,]?\d*", text.replace(",", "."))
        if score_match:
            try:
                score = float(score_match.group().replace(",", "."))
                candidates.append((score, area, text))
            except ValueError:
                continue

    if not candidates:
        logging.warning("❗ スコア候補が見つかりませんでした")
        return None

    # 面積が大きい順にソート（より大きい領域＝信頼度が高いと仮定）
    candidates.sort(key=lambda x: x[1], reverse=True)
    logging.debug(f"✅ スコア候補一覧: {candidates}")
    return candidates[0][0]

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
    resp = supabase.table("corrections").select("field").eq("user_id", user_id).single().execute()
    return resp.data.get("field") if resp.data else None

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
