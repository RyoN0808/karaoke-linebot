# routes/scores.py

from flask import Blueprint, jsonify, request
from supabase_client import supabase
from routes.login import verify_id_token

scores_bp = Blueprint("scores", __name__, url_prefix="/api")

@scores_bp.route("/scores", methods=["GET"])
def get_scores():
    # 1. Authorizationヘッダからid_token取得
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    id_token = auth_header.split(" ")[1]

    # 2. IDトークン検証（verify_id_token関数を再利用）
    try:
        user_info = verify_id_token(id_token)
    except Exception as e:
        return jsonify({"error": f"Invalid token: {str(e)}"}), 401

    line_user_id = user_info["sub"]

    # 3. Supabaseからスコア履歴取得
    scores = supabase.table("scores") \
        .select("*") \
        .eq("user_id", line_user_id) \
        .order("created_at", desc=True) \
        .limit(50) \
        .execute()

    return jsonify({
        "line_user_id": line_user_id,
        "scores": scores.data
    })
