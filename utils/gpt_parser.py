import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
import json

# .env 読み込み（忘れがち！）
load_dotenv()
print("✅ OPENAI_API_KEY:", os.getenv("OPENAI_API_KEY"))

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def parse_text_with_gpt(text: str) -> dict:
    prompt =f"""
以下のカラオケスコアOCR結果から、曲名、アーティスト名をJSONで抽出してください。

⚠️ artist_name に「ビブラート」「ビブラート &」などが含まれていた場合は **絶対に除外** してください。

✅ artist_name は人名に加えて、以下のようなアーティスト名もあります：
・数字から始まる（例：175R, 19, 3B LAB.☆S）
・アルファベットだけ（例：Aimer, BUMP OF CHICKEN）
・カタカナ（例：コブクロ）
・漢字(例:秦基博)

⚠️ 内容が不足している場合は null を返してください。

出力フォーマット（厳守）：
{{
  "song_name": string|null,
  "artist_name": string|null
}}

OCR結果：
{text}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content.strip()
        logging.debug("🧠 GPT構造化出力:\n%s", content)
        return json.loads(content)
    except Exception as e:
        logging.exception("❌ GPT構造化に失敗")
        return {
            "score": None,
            "song_name": None,
            "artist_name": None,
           
        }
