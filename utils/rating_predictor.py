# utils/rating_predictor.py
from utils.ema import calculate_ema
from utils.rating import get_rating_from_ema

def predict_rating_change(scores: list[float], step: float = 0.1, max_try: int = 100):
    current_ema = calculate_ema(scores)
    current_rating = get_rating_from_ema(current_ema)

    # レーティングの順序としきい値
    rating_levels = ["SS", "SA", "S", "A", "B"]
    rating_thresholds = {
        "SS": 95,
        "SA": 90,
        "S": 85,
        "A": 80,
        "B": 70
    }

    def find_target_rating(score):
        for rating in rating_levels:
            if score >= rating_thresholds[rating]:
                return rating
        return "B"

    # 上に上がれるかチェック
    next_up_score = None
    for i in range(1000):
        new_scores = scores + [rating_thresholds[current_rating] + i * step]
        new_ema = calculate_ema(new_scores)
        new_rating = get_rating_from_ema(new_ema)
        if rating_levels.index(new_rating) < rating_levels.index(current_rating):
            next_up_score = round(new_scores[-1], 3)
            break

    # 下がるケース（極端な低スコアでチェック）
    down_scores = scores + [0.0]
    down_ema = calculate_ema(down_scores)
    down_rating = get_rating_from_ema(down_ema)

    return {
        "current_ema": round(current_ema, 3),
        "current_rating": current_rating,
        "next_up_score": next_up_score,
        "next_rating": get_rating_from_ema(current_ema + 0.1),
        "can_downgrade": down_rating != current_rating
    }
