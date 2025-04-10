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
artist_nameにビブラートは入りません。
artist_nameはOCR結果の[分析レポート]の近くにあります。

内容が不足している場合は候補を返してください。

出力フォーマット：
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
