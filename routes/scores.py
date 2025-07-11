# routes/scores.py

from flask import Blueprint, jsonify, request
from supabase_client import supabase
from routes.login import verify_id_token

scores_bp = Blueprint("scores", __name__, url_prefix="/api")

@scores_bp.route("/scores", methods=["GET"])
def get_scores():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    id_token = auth_header.split(" ")[1]
    user_info = verify_id_token(id_token)
    user_id = user_info["sub"]

    scores = supabase.table("scores").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return jsonify(scores.data)
