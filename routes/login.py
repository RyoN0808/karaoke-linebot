from flask import Blueprint, request, redirect, jsonify
import requests
import os
from jose import jwt

login_bp = Blueprint("login", __name__)

# 環境変数から設定読み込み
LINE_CLIENT_ID = os.getenv("LINE_LOGIN_CLIENT_ID")
LINE_CLIENT_SECRET = os.getenv("LINE_LOGIN_CLIENT_SECRET")
LINE_REDIRECT_URI = os.getenv("LINE_LOGIN_REDIRECT_URI")
LINE_JWKS_URL = "https://api.line.me/oauth2/v2.1/certs"

# LINE公開鍵取得
def get_line_public_key(kid: str):
    jwks_response = requests.get(LINE_JWKS_URL)
    if jwks_response.status_code != 200:
        raise Exception("Failed to get LINE JWKS")

    jwks = jwks_response.json()
    for key in jwks["keys"]:
        if key["kid"] == kid:
            return key
    raise Exception("Public key not found for kid: " + kid)

# IDトークン検証
def verify_id_token(id_token: str):
    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header["kid"]

    public_key = get_line_public_key(kid)

    payload = jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=LINE_CLIENT_ID,
        issuer="https://access.line.me"
    )
    return payload

# LINEログイン開始エンドポイント
@login_bp.route("/login/line")
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

# コールバックエンドポイント
@login_bp.route("/login/line/callback")
def line_callback():
    # 1. 認可コード取得
    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        return "No code provided", 400

    # 2. トークンエンドポイントへPOST
    token_url = "https://api.line.me/oauth2/v2.1/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": LINE_REDIRECT_URI,
        "client_id": LINE_CLIENT_ID,
        "client_secret": LINE_CLIENT_SECRET
    }

    token_response = requests.post(token_url, headers=headers, data=data)
    if token_response.status_code != 200:
        return f"Failed to get token: {token_response.text}", 400

    tokens = token_response.json()
    id_token = tokens.get("id_token")

    # 3. IDトークン検証
    try:
        user_info = verify_id_token(id_token)
    except Exception as e:
        return f"IDトークン検証失敗: {str(e)}", 400

    line_user_id = user_info["sub"]  # LINE UUID

    # ここで Step 3 へ進む（Supabase users 照合/登録）

    return jsonify({
        "message": "LINE IDトークン検証成功",
        "line_user_id": line_user_id,
        "user_info": user_info
    })
