from __future__ import annotations
from typing import List, Dict, Tuple


def _match_fvg(ref: Dict, got: Dict, tol_price: float, tol_idx: int) -> bool:
    if (ref.get("type") != got.get("type")):
        return False
    if abs(int(ref.get("i0", 0)) - int(got.get("i0", 0))) > tol_idx:
        return False
    if abs(int(ref.get("i2", 0)) - int(got.get("i2", 0))) > tol_idx:
        return False
    # price band closeness
    if abs(float(ref.get("gap_low", 0.0)) - float(got.get("gap_low", 0.0))) > tol_price:
        return False
    if abs(float(ref.get("gap_high", 0.0)) - float(got.get("gap_high", 0.0))) > tol_price:
        return False
    return True


def fvg_parity_stats(ref: List[Dict], got: List[Dict], tol_price: float = 0.0001, tol_idx: int = 1) -> Dict:
    matched = set()
    tp = 0
    offsets: List[float] = []
    for r in ref:
        found_j = None
        for j, g in enumerate(got):
            if j in matched:
                continue
            if _match_fvg(r, g, tol_price, tol_idx):
                found_j = j
                break
        if found_j is not None:
            matched.add(found_j)
            tp += 1
            try:
                mid_ref = (float(r.get("gap_low", 0.0)) + float(r.get("gap_high", 0.0))) / 2.0
                mid_got = (float(got[found_j].get("gap_low", 0.0)) + float(got[found_j].get("gap_high", 0.0))) / 2.0
                offsets.append(abs(mid_ref - mid_got))
            except Exception:
                pass
    fp = max(0, len(got) - tp)
    fn = max(0, len(ref) - tp)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    match_pct = tp / (len(ref) or 1)
    avg_offset = sum(offsets) / len(offsets) if offsets else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "match_pct": match_pct,
        "avg_offset": avg_offset,
    }


def _interval_iou(a_low: float, a_high: float, b_low: float, b_high: float) -> float:
    left = max(min(a_low, a_high), min(b_low, b_high))
    right = min(max(a_low, a_high), max(b_low, b_high))
    inter = max(0.0, right - left)
    union = max(a_high, b_high) - min(a_low, b_low)
    return (inter / union) if union > 0 else 0.0


def _match_zone(ref: Dict, got: Dict, tol_idx: int, min_iou: float) -> bool:
    if ref.get("type") != got.get("type"):
        return False
    if abs(int(ref.get("i", 0)) - int(got.get("i", 0))) > tol_idx:
        return False
    iou = _interval_iou(float(ref.get("low", 0.0)), float(ref.get("high", 0.0)), float(got.get("low", 0.0)), float(got.get("high", 0.0)))
    return iou >= min_iou


def zones_parity_stats(ref: List[Dict], got: List[Dict], tol_idx: int = 2, min_iou: float = 0.6) -> Dict:
    matched = set()
    tp = 0
    ious: List[float] = []
    offsets: List[float] = []
    for r in ref:
        found_j = None
        for j, g in enumerate(got):
            if j in matched:
                continue
            if _match_zone(r, g, tol_idx, min_iou):
                found_j = j
                break
        if found_j is not None:
            matched.add(found_j)
            tp += 1
            try:
                rr_low, rr_high = float(r.get("low", 0.0)), float(r.get("high", 0.0))
                gg_low, gg_high = float(got[found_j].get("low", 0.0)), float(got[found_j].get("high", 0.0))
                ious.append(_interval_iou(rr_low, rr_high, gg_low, gg_high))
                offsets.append(abs(((rr_low + rr_high) / 2.0) - ((gg_low + gg_high) / 2.0)))
            except Exception:
                pass
    fp = max(0, len(got) - tp)
    fn = max(0, len(ref) - tp)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    match_pct = tp / (len(ref) or 1)
    avg_iou = sum(ious) / len(ious) if ious else 0.0
    avg_offset = sum(offsets) / len(offsets) if offsets else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "match_pct": match_pct,
        "avg_iou": avg_iou,
        "avg_offset": avg_offset,
    }
