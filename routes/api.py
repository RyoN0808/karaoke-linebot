# routes/api.py
from flask import Blueprint, request, jsonify
from jose import jwt as jose_jwt
import requests
import os
from supabase_client import supabase

api_bp = Blueprint("api", __name__, url_prefix="/api")

LINE_CLIENT_ID = os.getenv("LINE_CLIENT_ID")
LINE_JWKS_URL = "https://api.line.me/oauth2/v2.1/certs"

# LINE公開鍵取得（既存の verify_id_token から流用可）
def get_line_public_key(kid: str):
    jwks_response = requests.get(LINE_JWKS_URL)
    jwks = jwks_response.json()
    for key in jwks["keys"]:
        if key["kid"] == kid:
            return key
    raise Exception("Public key not found for kid: " + kid)

def verify_id_token(id_token: str):
    unverified_header = jose_jwt.get_unverified_header(id_token)
    kid = unverified_header["kid"]
    public_key = get_line_public_key(kid)

    payload = jose_jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=LINE_CLIENT_ID,
        issuer="https://access.line.me"
    )
    return payload

@api_bp.route("/me", methods=["GET"])
def get_me():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Missing Authorization header"}), 401

    token = auth_header.replace("Bearer ", "")
    try:
        user_info = verify_id_token(token)
    except Exception as e:
        return jsonify({"error": f"Invalid token: {str(e)}"}), 401

    line_user_id = user_info["sub"]

    # Supabase users テーブルから取得
    user = supabase.table("users").select("*").eq("id", line_user_id).maybe_single().execute()

    return jsonify({
        "line_user_id": line_user_id,
        "user": user.data
    })
