# utils/stats.py
from typing import Optional
from supabase_client import supabase
from utils.rating_predictor import predict_next_rating
from utils.rating import get_rating_from_score


def build_user_stats_message(user_id: str) -> Optional[str]:
    resp = supabase.table("scores").select("score, created_at").eq("user_id", user_id).order("created_at", desc=True).limit(30).execute()
    score_list = [s["score"] for s in resp.data if s.get("score") is not None]
    if not score_list:
        return None

    latest_score = score_list[0]
    max_score = max(score_list)
    avg_score = round(sum(score_list) / len(score_list), 3) if len(score_list) >= 5 else None
    rating_info = predict_next_rating(score_list) if avg_score is not None else {}

    user_info = supabase.table("users").select("score_count").eq("id", user_id).single().execute()
    score_count = user_info.data["score_count"] if user_info.data else 0

    msg = (
        "\U0001F4CA あなたの成績\n"
        f"・レーティング: {rating_info.get('current_rating', '---')}\n"
        f"・平均スコア（最新30曲）: {avg_score or '---'}\n"
        f"・最新スコア: {latest_score or '---'}\n"
        f"・最高スコア: {max_score or '---'}\n"
        f"・登録回数: {score_count} 回\n"
    )

    if (
        "next_up_score" in rating_info
        and rating_info["next_up_score"] is not None
        and rating_info["next_up_score"] <= 100
    ):
        msg += f"・次のレーティングに上がるにはあと {rating_info['next_up_score']} 点が必要！\n"

    elif (
        rating_info.get("can_downgrade") and 
        rating_info.get("next_down_score") and
        rating_info["next_down_score"] <= 100 and 
        rating_info["next_down_score"] >= 75
    ):
        msg += f"・おっと！{rating_info['next_down_score']} 点未満でレーティングが下がってしまうかも！\n"

    return msg
