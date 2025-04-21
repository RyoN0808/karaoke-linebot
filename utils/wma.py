def calculate_wma(scores: list[float]) -> float | None:
    if not scores:
        return None

    # 直近の30曲を対象にする（最大30）
    scores = scores[-30:]
    weights = list(range(1, len(scores) + 1))  # 1, 2, ..., n

    weighted_sum = sum(s * w for s, w in zip(scores, weights))
    total_weight = sum(weights)

    return round(weighted_sum / total_weight, 3)
