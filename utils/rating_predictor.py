import math
from typing import List, Dict, Optional
from utils import rating  # rating.pyにランク関数がある想定

def predict_next_rating(scores: List[float]) -> Dict[str, Optional[float]]:
    result: Dict[str, Optional[float]] = {}
    total_scores = len(scores)
    if total_scores == 0:
        return result

    # 最新30件に対して処理
    if total_scores >= 30:
        base_scores = scores[-29:]
        new_count = 30
    else:
        base_scores = scores[:]
        new_count = total_scores + 1

    base_sum = sum(base_scores)

    current_count = min(total_scores, 30)
    current_scores = scores[-current_count:]
    current_avg = sum(current_scores) / current_count
    current_rank = rating.get_rank(current_avg)

    # 🔽 ここを追加
    result["current_rating"] = current_rank

    next_rank = rating.get_next_rank(current_rank)
    lower_rank = rating.get_previous_rank(current_rank)

    # ランクアップ判定
    if next_rank:
        next_threshold = rating.get_threshold(next_rank)
        required_score = math.ceil(next_threshold * new_count - base_sum)
        result["next_up_score"] = max(0, required_score)
    else:
        result["next_up_score"] = None

    # ランクダウン判定
    if lower_rank:
        current_threshold = rating.get_threshold(current_rank)
        boundary_score = math.floor(current_threshold * new_count - base_sum)
        if boundary_score < 0:
            boundary_score = 0
        result["next_down_score"] = boundary_score
        result["can_downgrade"] = True if boundary_score > 0 else False
        if boundary_score == 0 and (current_threshold * new_count - base_sum) <= 0:
            result["next_down_score"] = None
    else:
        result["next_down_score"] = None
        result["can_downgrade"] = False

    return result
