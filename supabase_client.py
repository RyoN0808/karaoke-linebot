# supabase_client.py

from supabase import create_client
import os
from dotenv import load_dotenv

# .env.dev または .env.production を自動で読み込み
env_file = os.getenv("ENV_FILE", ".env.dev")
load_dotenv(dotenv_path=env_file)

# 接続情報
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

# Supabase クライアント生成
supabase = create_client(url, key)
