def calculate_ema(scores, alpha=0.1):
    ema = None
    for s in scores:
        if ema is None:
            ema = s
        else:
            ema = alpha * s + (1 - alpha) * ema
    return round(ema, 3) if ema is not None else None

