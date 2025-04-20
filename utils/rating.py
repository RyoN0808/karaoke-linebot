def get_rating_from_ema(ema: float) -> str:
    if ema >= 95:
        return "SS"
    elif ema >= 90:
        return "SA"
    elif ema >= 85:
        return "S"
    elif ema >= 80:
        return "A"
    elif ema >= 70:
        return "B"
    else:
        return "C"
