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
