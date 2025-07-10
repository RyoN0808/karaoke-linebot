import os
import time
import requests
from flask import Blueprint, request, redirect, jsonify
from jose import jwt as jose_jwt

# === 0. Blueprint 定義 ===
login_bp = Blueprint("login", __name__, url_prefix="/login")

# === 1. 環境変数読み込み ===
LINE_CLIENT_ID = os.getenv("LINE_LOGIN_CLIENT_ID")
LINE_REDIRECT_URI = os.getenv("LINE_LOGIN_REDIRECT_URI")
LINE_CHANNEL_SECRET = os.getenv("LINE_LOGIN_CLIENT_SECRET")  # ここ変更

# === 2. client_assertion 生成（HS256）===
def generate_client_assertion():
    now = int(time.time())
    payload = {
        "iss": LINE_CLIENT_ID,
        "sub": LINE_CLIENT_ID,
        "aud": "https://api.line.me/",
        "exp": now + 300  # 有効期限5分
    }

    token = jose_jwt.encode(payload, LINE_CHANNEL_SECRET, algorithm="HS256")

# === 3. access_token verify ===
def verify_access_token(access_token: str):
    verify_url = "https://api.line.me/oauth2/v2.1/verify"
    params = {"access_token": access_token}
    response = requests.get(verify_url, params=params)
    print("access_token verify status:", response.status_code)
    print("access_token verify json:", response.json())
    if response.status_code != 200:
        raise Exception(f"Access token invalid: {response.text}")
    return response.json()

# === 4. ログイン開始エンドポイント ===
@login_bp.route("/line")
def login_line():
    line_auth_url = (
        f"https://access.line.me/oauth2/v2.1/authorize"
        f"?response_type=code"
        f"&client_id={LINE_CLIENT_ID}"
        f"&redirect_uri={LINE_REDIRECT_URI}"
        f"&state=test_state"  # TODO: CSRF対策でランダム生成する
        f"&scope=profile%20openid"
    )
    return redirect(line_auth_url)

# === 5. コールバックエンドポイント ===
@login_bp.route("/line/callback")
def line_callback():
    code = request.args.get("code")
    if not code:
        return "No code provided", 400

    token_url = "https://api.line.me/oauth2/v2.1/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": LINE_REDIRECT_URI,
        "client_id": LINE_CLIENT_ID,
        "client_secret": LINE_CHANNEL_SECRET  # HS256ではclient_secretを使う
    }

    token_response = requests.post(token_url, headers=headers, data=data)
    print("token_response status:", token_response.status_code)
    print("token_response json:", token_response.json())

    if token_response.status_code != 200:
        return f"Failed to get token: {token_response.text}", 400

    tokens = token_response.json()
    access_token = tokens.get("access_token")
    id_token = tokens.get("id_token")

    # === 6. access_token verify ===
    try:
        verify_access_token(access_token)
    except Exception as e:
        return f"Access token verify failed: {str(e)}", 400

    # === 7. IDトークン検証 ===
    try:
        user_info = jose_jwt.decode(
            id_token,
            LINE_CHANNEL_SECRET,
            algorithms=["HS256"],
            audience=LINE_CLIENT_ID,
            issuer="https://access.line.me"
        )
    except Exception as e:
        return f"IDトークン検証失敗: {str(e)}", 400

    return jsonify({
        "message": "LINE IDトークン検証成功",
        "line_user_id": user_info["sub"],
        "user_info": user_info
    })
