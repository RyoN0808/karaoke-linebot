# utils/rating_predictor.py
from utils.wma import calculate_wma
from utils.rating import get_rating_from_wma

def predict_rating_change(scores: list[float], step: float = 0.1, max_try: int = 100):
    current_wma = calculate_wma(scores)
    current_rating = get_rating_from_wma(current_wma)

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
        new_wma = calculate_wma(new_scores)
        new_rating = get_rating_from_wma(new_wma)
        if rating_levels.index(new_rating) < rating_levels.index(current_rating):
            next_up_score = round(new_scores[-1], 3)
            break

    # 下がるケース（極端な低スコアでチェック）
    down_scores = scores + [0.0]
    down_wma = calculate_wma(down_scores)
    down_rating = get_rating_from_wma(down_wma)

    return {
        "current_wma": round(current_wma, 3),
        "current_rating": current_rating,
        "next_up_score": next_up_score,
        "next_rating": get_rating_from_wma(current_wma + 0.1),
        "can_downgrade": down_rating != current_rating
    }
