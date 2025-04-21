# utils/rating_predictor.py

from utils.rating import get_rating_from_score  # 関数名に合わせて

def predict_rating_change(scores: list[float], step: float = 0.1, max_try: int = 100):
    if not scores:
        return {}

    current_avg = round(sum(scores) / len(scores), 3)
    current_rating = get_rating_from_score(current_avg)

    # レーティングの順序としきい値
    rating_levels = ["SS", "SA", "S", "A", "B"]
    rating_thresholds = {
        "SS": 95,
        "SA": 90,
        "S": 85,
        "A": 80,
        "B": 70
    }

    # 上に上がれるかチェック
    next_up_score = None
    for i in range(max_try):
        new_score = rating_thresholds[current_rating] + i * step
        new_scores = scores + [new_score]
        new_avg = sum(new_scores) / len(new_scores)
        new_rating = get_rating_from_score(new_avg)
        if rating_levels.index(new_rating) < rating_levels.index(current_rating):
            next_up_score = round(new_score, 3)
            break

    # 下がるケース（極端な低スコアでチェック）
    down_scores = scores + [0.0]
    down_avg = sum(down_scores) / len(down_scores)
    down_rating = get_rating_from_score(down_avg)

    return {
        "current_avg": round(current_avg, 3),
        "current_rating": current_rating,
        "next_up_score": next_up_score,
        "next_rating": get_rating_from_score(current_avg),
    }