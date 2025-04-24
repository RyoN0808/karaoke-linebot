import math
from typing import List, Dict, Optional
from utils import rating
from utils.constants import SCORE_EVAL_COUNT

def predict_next_rating(scores: List[float]) -> Dict[str, Optional[float]]:
    result: Dict[str, Optional[float]] = {}
    total_scores = len(scores)

    if total_scores == 0:
        return result

    # 最新 SCORE_EVAL_COUNT 件中の最古を除いた base_scores を使う
    if total_scores >= SCORE_EVAL_COUNT:
        base_scores = scores[:-1][:SCORE_EVAL_COUNT - 1]
    else:
        base_scores = scores[:]
    base_sum = sum(base_scores)
    new_count = len(base_scores) + 1

    # 現在のランク算出
    current_count = min(total_scores, SCORE_EVAL_COUNT)
    current_scores = scores[:current_count]
    current_avg = sum(current_scores) / current_count
    current_rank = rating.get_rank(current_avg)
    result["current_rating"] = current_rank

    # 次ランクと前ランクを取得
    next_rank = rating.get_next_rank(current_rank)
    lower_rank = rating.get_previous_rank(current_rank)

    # ランクアップ条件の計算
    if next_rank:
        next_threshold = rating.get_threshold(next_rank)
        required_score = math.ceil(next_threshold * new_count - base_sum)
        result["next_up_score"] = required_score
    else:
        result["next_up_score"] = None

    # ランクダウン条件の計算
    if lower_rank:
        current_threshold = rating.get_threshold(current_rank)
        boundary_score = math.floor(current_threshold * new_count - base_sum)
        result["next_down_score"] = max(0, boundary_score)
        result["can_downgrade"] = boundary_score > 0
        if boundary_score == 0 and (current_threshold * new_count - base_sum) <= 0:
            result["next_down_score"] = None
    else:
        result["next_down_score"] = None
        result["can_downgrade"] = False

    return result
