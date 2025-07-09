import os
import time
import requests
import tempfile
from flask import Blueprint, request, redirect, jsonify
from jose import jwt as jose_jwt
from jwcrypto import jwt as jw_jwt, jwk

# === 0. Blueprint 定義 ===
login_bp = Blueprint("login", __name__, url_prefix="/login")

# === 1. 環境変数読み込み ===
LINE_CLIENT_ID = os.getenv("LINE_LOGIN_CLIENT_ID")
LINE_REDIRECT_URI = os.getenv("LINE_LOGIN_REDIRECT_URI")
LINE_JWKS_URL = "https://api.line.me/oauth2/v2.1/certs"
LINE_JWT_KID = os.getenv("LINE_JWT_KID")  # 公開鍵登録で発行されたkidを環境変数から取得

# === 2. PRIVATE / PUBLIC KEY を tempfile に書き出し ===
private_key_content = os.getenv("PRIVATE_KEY_CONTENT")
if not private_key_content:
    raise Exception("PRIVATE_KEY_CONTENT not set")
with tempfile.NamedTemporaryFile(delete=False, mode="w") as tmp:
    tmp.write(private_key_content)
    PRIVATE_KEY_PATH = tmp.name

public_key_content = os.getenv("PUBLIC_KEY_CONTENT")
if not public_key_content:
    raise Exception("PUBLIC_KEY_CONTENT not set")
with tempfile.NamedTemporaryFile(delete=False, mode="w") as tmp:
    tmp.write(public_key_content)
    PUBLIC_KEY_PATH = tmp.name

# === 3. client_assertion 生成 ===
def generate_client_assertion():
    with open(PRIVATE_KEY_PATH, "rb") as f:
        key = jwk.JWK.from_pem(f.read())

    now = int(time.time())
    payload = {
        "iss": LINE_CLIENT_ID,
        "sub": LINE_CLIENT_ID,
        "aud": "https://api.line.me/",
        "exp": now + 300,
        "token_exp": 600
    }

    token = jw_jwt.JWT(
        header={
            "alg": "RS256",
            "typ": "JWT",
            "kid": LINE_JWT_KID  # ⭐️ 環境変数からkidをセット
        },
        claims=payload
    )
    token.make_signed_token(key)

    # ⭐️ ここで生成された JWT を確認出力
    token_str = token.serialize()
    print("Generated client_assertion JWT:", token_str)

    return token_str

# === 4. LINE公開鍵取得 ===
def get_line_public_key(kid: str):
    jwks_response = requests.get(LINE_JWKS_URL)
    jwks_response.raise_for_status()
    jwks = jwks_response.json()
    for key in jwks["keys"]:
        if key["kid"] == kid:
            return key
    raise Exception("Public key not found for kid: " + kid)

# === 5. IDトークン検証 ===
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

# === 6. ログイン開始エンドポイント ===
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

# === 7. コールバックエンドポイント ===
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
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": generate_client_assertion()
    }

    token_response = requests.post(token_url, headers=headers, data=data)
    print("token_response status:", token_response.status_code)
    print("token_response json:", token_response.json())

    if token_response.status_code != 200:
        return f"Failed to get token: {token_response.text}", 400

    tokens = token_response.json()
    id_token = tokens.get("id_token")

    try:
        user_info = verify_id_token(id_token)
    except Exception as e:
        return f"IDトークン検証失敗: {str(e)}", 400

    return jsonify({
        "message": "LINE IDトークン検証成功",
        "line_user_id": user_info["sub"],
        "user_info": user_info
    })
