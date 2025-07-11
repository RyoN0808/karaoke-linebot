# routes/api.py

from flask import Blueprint, request, jsonify
import os
from jose import jwt as jose_jwt
from supabase_client import supabase

api_bp = Blueprint("api", __name__, url_prefix="/api")

# 環境変数から設定読み込み
LINE_CLIENT_ID = os.getenv("LINE_LOGIN_CLIENT_ID")
LINE_CHANNEL_SECRET = os.getenv("LINE_LOGIN_CLIENT_SECRET")

# IDトークン検証関数
def verify_id_token(id_token: str):
    payload = jose_jwt.decode(
        id_token,
        LINE_CHANNEL_SECRET,
        algorithms=["HS256"],
        audience=LINE_CLIENT_ID,
        issuer="https://access.line.me"
    )
    return payload

# /api/me エンドポイント
@api_bp.route("/me", methods=["GET"])
def get_me():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    id_token = auth_header.split(" ")[1]

    try:
        # IDトークンを検証
        user_info = verify_id_token(id_token)
        line_user_id = user_info["sub"]
    except Exception as e:
        return jsonify({"error": f"Invalid id_token: {str(e)}"}), 401

    # Supabaseからユーザー情報取得
    user = supabase.table("users").select("*").eq("id", line_user_id).maybe_single().execute()
    if not user or not user.data:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "line_user_id": line_user_id,
        "user_info": user_info,
        "db_user": user.data
    })
