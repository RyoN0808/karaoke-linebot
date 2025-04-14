from supabase import create_client
import os
from dotenv import load_dotenv

# .env 読み込み
load_dotenv()

# 接続情報
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

# Supabase クライアント生成
supabase = create_client(url, key)

