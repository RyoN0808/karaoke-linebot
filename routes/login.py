import os
import time
import requests
import secrets, hashlib, base64  # ✅ 追加: ランダム値やハッシュ計算に使用
from flask import Blueprint, request, redirect, jsonify, session
from jose import jwt as jose_jwt
from jwcrypto import jwt as jw_jwt, jwk

# === 0. Blueprint 定義 ===
login_bp = Blueprint("login", __name__, url_prefix="/login")

# === 1. 環境変数読み込み ===
LINE_CLIENT_ID = os.getenv("LINE_LOGIN_CLIENT_ID")
LINE_REDIRECT_URI = os.getenv("LINE_LOGIN_REDIRECT_URI")
LINE_JWT_KID = os.getenv("LINE_JWT_KID")
if not LINE_CLIENT_ID or not LINE_REDIRECT_URI or not LINE_JWT_KID:
    raise Exception("LINE_LOGIN_CLIENT_ID, LINE_LOGIN_REDIRECT_URI, LINE_JWT_KID を設定してください")
private_key_content = os.getenv("PRIVATE_KEY_CONTENT")
if not private_key_content:
    raise Exception("PRIVATE_KEY_CONTENT not set")

# === 2. JWK秘密鍵オブジェクト生成 ===
jwk_key = jwk.JWK.from_pem(private_key_content.encode("utf-8"))

# === 3. client_assertion 生成関数 ===
def generate_client_assertion():
    now = int(time.time())
    payload = {
        "iss": LINE_CLIENT_ID,
        "sub": LINE_CLIENT_ID,
        "aud": "https://api.line.me/",  # ✅ audは末尾スラッシュ付き（LINE公式仕様）:contentReference[oaicite:14]{index=14}
        "exp": now + 300  # 有効期限5分
    }
    token = jw_jwt.JWT(
        header={"alg": "RS256", "typ": "JWT", "kid": LINE_JWT_KID},
        claims=payload
    )
    token.make_signed_token(jwk_key)
    return token.serialize()

# === 4. ログイン開始エンドポイント ===
@login_bp.route("/line")
def login_line():
    # ✅ 修正: stateをランダム生成しセッションに保存
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    # ✅ 修正: PKCE用 code_verifier と code_challenge を生成・保存
    code_verifier = secrets.token_urlsafe(32)
    session["code_verifier"] = code_verifier
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
    # ✅ 修正: nonceもランダム生成（再生攻撃対策用）
    nonce = secrets.token_urlsafe(16)
    session["nonce"] = nonce

    line_auth_url = (
        "https://access.line.me/oauth2/v2.1/authorize"
        f"?response_type=code&client_id={LINE_CLIENT_ID}"
        f"&redirect_uri={LINE_REDIRECT_URI}"
        f"&state={state}"
        f"&scope=profile%20openid"
        f"&nonce={nonce}"
        f"&code_challenge={code_challenge}&code_challenge_method=S256"
    )
    return redirect(line_auth_url)

# === 5. コールバックエンドポイント ===
@login_bp.route("/line/callback")
def line_callback():
    # 認可コードとstateを受け取る
    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        return "No code provided", 400
    # ✅ 修正: stateパラメータの検証（CSRF対策）
    if not state or state != session.get("oauth_state"):
        return "State mismatch", 400

    # トークンエンドポイントにリクエスト
    token_url = "https://api.line.me/oauth2/v2.1/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": LINE_REDIRECT_URI,
        "client_id": LINE_CLIENT_ID,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": generate_client_assertion(),
        "code_verifier": session.get("code_verifier")  # ✅ PKCE: 対応するcode_verifierを送信
    }
    token_res = requests.post(token_url, headers=headers, data=data)
    print("token_res status:", token_res.status_code)
    print("token_res body:", token_res.text)
    if token_res.status_code != 200:
        return f"Failed to get token: {token_res.text}", 400

    tokens = token_res.json()
    id_token = tokens.get("id_token")

    # === 6. IDトークン検証 ===
    # ✅ 修正: LINEの検証エンドポイントを使用してIDトークンを検証
    verify_res = requests.post("https://api.line.me/oauth2/v2.1/verify", data={
        "id_token": id_token,
        "client_id": LINE_CLIENT_ID,
        "nonce": session.get("nonce")  # nonceを使用した場合は送信
    })
    if verify_res.status_code != 200:
        return f"IDトークン検証失敗: {verify_res.text}", 400
    user_info = verify_res.json()

    # （オプション）不要になったセッション情報の削除
    session.pop("oauth_state", None)
    session.pop("code_verifier", None)
    session.pop("nonce", None)

    return jsonify({
        "message": "LINE IDトークン検証成功",
        "line_user_id": user_info.get("sub"),
        "user_info": user_info
    })
