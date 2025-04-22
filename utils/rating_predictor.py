import math
from typing import List, Dict, Optional
from utils import rating  # rating.pyにランク判定用の関数・定数がある想定

def predict_next_rating(scores: List[float]) -> Dict[str, Optional[float]]:
    result: Dict[str, Optional[float]] = {}
    total_scores = len(scores)
    if total_scores == 0:
        return result

    # 最新順に扱う（後ろが新しい前提）
    if total_scores >= 30:
        base_scores = scores[-29:]   # 最新29件
        new_count = 30
    else:
        base_scores = scores[:]
        new_count = total_scores + 1

    base_sum = sum(base_scores)

    # 平均スコアと現在ランク
    current_count = min(total_scores, 30)
    current_avg = sum(scores[-current_count:]) / current_count
    current_rank = rating.get_rank(current_avg)

    next_rank = rating.get_next_rank(current_rank)
    lower_rank = rating.get_previous_rank(current_rank)

    # ランクアップの閾値計算
    if next_rank:
        next_threshold = rating.get_threshold(next_rank)
        required_score = math.ceil(next_threshold * new_count - base_sum)
        result["rank_up_score"] = max(0, required_score)
    else:
        result["rank_up_score"] = None

    # ランクダウンの閾値計算
    if lower_rank:
        current_threshold = rating.get_threshold(current_rank)
        boundary_score = math.floor(current_threshold * new_count - base_sum)
        if boundary_score < 0:
            boundary_score = 0
        result["rank_down_score"] = boundary_score
        if boundary_score == 0 and (current_threshold * new_count - base_sum) <= 0:
            result["rank_down_score"] = None
    else:
        result["rank_down_score"] = None

    return result
