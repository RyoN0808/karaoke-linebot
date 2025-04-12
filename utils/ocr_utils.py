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
from linebot.models import TextSendMessage, QuickReply, QuickReplyButton, MessageAction
# ==============================
# スコア抽出処理
# ==============================

def _calc_area(bounding_poly) -> float:
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

def _extract_score(texts) -> Optional[float]:
    """
    OCRテキストからスコア（例：92.170）を推定。
    「点」が近くにある場合を優先。
    """
    if not texts:
        return None

    candidates = []

    for i, annotation in enumerate(texts[1:]):  # texts[0] は全文
        desc = annotation.description.strip()

        # 数値形式（例：92.170）を持つものだけ対象
        if not re.match(r'^\d{2,3}[.,]\d{1,3}$', desc):
            continue

        # 周囲テキストを確認
        near_texts = texts[max(0, i): i + 4]
        context = " ".join(t.description for t in near_texts)

        # 「点」が近くにある場合に優先度アップ
        priority = 1 if "点" in context else 0

        try:
            score = float(desc.replace(",", "."))
            candidates.append({"score": score, "priority": priority})
        except ValueError:
            continue

    if not candidates:
        logging.warning("❗ スコア候補が見つかりませんでした")
        return None

    # 優先度 → 数値の大きさ で優先ソート
    best = max(candidates, key=lambda x: (x["priority"], x["score"]))
    return best["score"]



# ==============================
# OCR 実行
# ==============================

def ocr_image(image_path, client):
    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()

    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    return response

def extract_text_from_image(image_path):
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path:
        logging.error("GOOGLE_APPLICATION_CREDENTIALS 環境変数が設定されていません")
        return None
    credentials = service_account.Credentials.from_service_account_file(credentials_path)
    client = vision.ImageAnnotatorClient(credentials=credentials)
    return ocr_image(image_path, client)

# ==============================
# 修正コマンド関連
# ==============================

def is_correction_command(text: str) -> bool:
    return text == "修正" or text.lower() == "fix"

def get_correction_menu() -> TextSendMessage:
    return TextSendMessage(
        text="🔧 修正したい項目を選んでください：",
        quick_reply=QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="スコア", text="スコア")),
            QuickReplyButton(action=MessageAction(label="曲名", text="曲名")),
            QuickReplyButton(action=MessageAction(label="アーティスト", text="アーティスト")),
            QuickReplyButton(action=MessageAction(label="コメント", text="コメント")),
        ])
    )

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