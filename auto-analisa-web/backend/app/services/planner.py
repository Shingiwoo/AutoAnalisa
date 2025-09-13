from .rules import make_levels, Features
from .validator import normalize_and_validate


def build_plan(bundle, feat: "Features", score: int, mode: str = "auto"):
    lv = make_levels(feat)
    s1, s2 = lv["support"]
    r1, r2 = lv["resistance"]
    price = float(bundle["15m"].iloc[-1].close)
    pb1, pb2 = max(s1, price * 0.995), max(s2, price * 0.99)
    invalid = min(s2, pb2 * 0.995)
    tp1, tp2 = r1, r2
    if mode == "BO" or (mode == "auto" and price > r1 * 0.995):
        trig = round(r1 * 1.001, 6)
        entries = [trig]
        weights = [1.0]
        out_mode = "BO"
    else:
        entries = [round(pb1, 6), round(pb2, 6)]
        weights = [0.6, 0.4]
        out_mode = "PB"
    bias = "Bullish intraday selama struktur 1H bertahan di atas %.4f–%.4f." % (s1, s2)
    plan = {
        "bias": bias,
        "support": [s1, s2],
        "resistance": [r1, r2],
        "mode": out_mode,
        "entries": entries,
        "weights": weights,
        "invalid": round(invalid, 6),
        "tp": [round(tp1, 6), round(tp2, 6)],
        "score": score,
    }
    # Normalize and compute rr_min
    plan, _warns = normalize_and_validate(plan)
    return plan
