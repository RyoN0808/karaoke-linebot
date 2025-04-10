import os
from google.cloud import vision

# 認証ファイルパスを環境変数に設定
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "composite-area-455811-r0-50856148de44.json"

def detect_text_from_image(image_path: str):
    client = vision.ImageAnnotatorClient()

    with open(image_path, "rb") as image_file:
        content = image_file.read()

    image = vision.Image(content=content)
    response = client.text_detection(image=image)

    if response.error.message:
        raise Exception(f"API error: {response.error.message}")

    texts = response.text_annotations
    if not texts:
        return "❌ テキストが見つかりませんでした。"

    return texts[0].description

# 試しに使ってみる
if __name__ == "__main__":
    result = detect_text_from_image("uibd4s00000010x2.jpg")
    print("🔍 OCR結果:\n", result)
