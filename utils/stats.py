from typing import Optional
from supabase_client import supabase
from utils.rating_predictor import predict_next_rating
from utils.constants import SCORE_EVAL_COUNT


def build_user_stats_message(user_id: str) -> Optional[str]:
    # スコア取得（最新SCORE_EVAL_COUNT件）
    resp = supabase.table("scores") \
        .select("score, created_at") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .limit(SCORE_EVAL_COUNT) \
        .execute()

    score_list = [s["score"] for s in resp.data if s.get("score") is not None]
    if not score_list:
        return None

    latest_score = score_list[0]
    max_score = max(score_list)

    # ユーザー情報（DBの avg_score, avg_rating, score_count を使用）
    user_info = supabase.table("users") \
        .select("avg_score, avg_rating, score_count") \
        .eq("id", user_id) \
        .single() \
        .execute()

    avg_score = user_info.data.get("avg_score") if user_info.data else None
    avg_rating = user_info.data.get("avg_rating") or "---"
    score_count = user_info.data.get("score_count") or 0

    # レーティング予測情報（Pythonで動的に計算）
    rating_info = predict_next_rating(score_list) if avg_score is not None else {}

    # 成績メッセージ構築
    msg = (
        "\U0001F4CA あなたの成績\n"
        f"・レーティング: {avg_rating}\n"
        f"・平均スコア: {avg_score or '---'}\n"
        f"・最新スコア: {latest_score or '---'}\n"
        f"・最高スコア: {max_score or '---'}\n"
        f"・登録回数: {score_count} 回\n"
    )

    user_info = supabase.table("users") \
        .select("avg_score, avg_rating, next_up_score, next_down_score, score_count") \
        .eq("id", user_id).single().execute()

       next_up_score = user_info.data.get("next_up_score")
    if next_up_score is not None and next_up_score <= 100:
    msg += f"・次の曲でレーティングを上がるには{next_up_score} 点が必要！\n"

       next_down_score = user_info.data.get("next_down_score")
    if next_down_score is not None and 75 <= next_down_score <= 100:
       msg += f"・おっと！次の曲が{next_down_score} 点未満でレーティングが下がってしまうかも！\n"

