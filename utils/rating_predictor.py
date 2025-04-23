import math
import logging
from typing import List, Dict, Optional
from utils import rating  # rating.py にランク関数がある想定

def predict_next_rating(scores: List[float]) -> Dict[str, Optional[float]]:
    result: Dict[str, Optional[float]] = {}
    total_scores = len(scores)

    if total_scores == 0:
        return result

    # 常に最新スコア30件を対象とし、ランクアップに必要な次の1件のスコアを算出
    if total_scores >= 30:
        base_scores = scores[:-1][:29]  # 最新30件中の最古を除く29件（新しい順）
    else:
        base_scores = scores[:]  # 30件未満の場合はそのまま

    base_sum = sum(base_scores)
    new_count = len(base_scores) + 1

    # 現在のランク計算（30件まで）
    current_count = min(total_scores, 30)
    current_scores = scores[:current_count]
    current_avg = sum(current_scores) / current_count
    current_rank = rating.get_rank(current_avg)
    result["current_rating"] = current_rank

    next_rank = rating.get_next_rank(current_rank)
    lower_rank = rating.get_previous_rank(current_rank)

    # ランクアップ条件
    if next_rank:
        next_threshold = rating.get_threshold(next_rank)
        required_score = math.ceil(next_threshold * new_count - base_sum)
        result["next_up_score"] = max(0, min(100, required_score))
    else:
        result["next_up_score"] = None

    # ランクダウン条件（デバッグ用）
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