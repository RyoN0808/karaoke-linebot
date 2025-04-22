from typing import Optional

# 既存の関数はそのまま残してOK
def get_rating_from_score(score: float) -> str:
    if score >= 95:
        return "SS"
    elif score >= 90:
        return "SA"
    elif score >= 85:
        return "S"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B"
    else:
        return "C"

# ランクのしきい値（ランクを維持する最低平均スコア）
RANK_THRESHOLDS = {
    "SS": 95,
    "SA": 90,
    "S": 85,
    "A": 80,
    "B": 70,
    "C": 0,  # 最低ランク
}

# ランクの順序（下から上）
RANK_ORDER = ["C", "B", "A", "S", "SA", "SS"]

def get_rank(avg_score: float) -> str:
    return get_rating_from_score(avg_score)

def get_threshold(rank: str) -> float:
    return RANK_THRESHOLDS.get(rank, 0)

def get_next_rank(current: str) -> Optional[str]:
    try:
        idx = RANK_ORDER.index(current)
        return RANK_ORDER[idx + 1] if idx + 1 < len(RANK_ORDER) else None
    except ValueError:
        return None

def get_previous_rank(current: str) -> Optional[str]:
    try:
        idx = RANK_ORDER.index(current)
        return RANK_ORDER[idx - 1] if idx - 1 >= 0 else None
    except ValueError:
        return None
