import math
import os, sys
# ensure backend/app is importable as 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.services.validator import normalize_and_validate, compute_rr_min, validate_spot2


def test_tp_strict_ascending_and_weights_norm():
    plan = {
        "support": [100, 90],
        "resistance": [120, 130],
        "entries": [101.0, 99.0],
        "weights": [0.7, 0.7],  # invalid sum and length ok
        "invalid": 95.0,
        "tp": [118.0, 112.0],  # not ascending
    }
    fixed, warns = normalize_and_validate(plan)
    assert fixed["tp"][0] < fixed["tp"][1]
    assert abs(sum(fixed["weights"]) - 1.0) < 1e-6
    assert fixed["rr_min"] >= 0.0


def test_rr_min_and_auto_tighten_invalid():
    entries = [100.0, 95.0]
    invalid = 90.0
    tp1 = 110.0
    rr0 = compute_rr_min(entries, invalid, tp1)
    assert math.isclose(rr0, 1.0, rel_tol=1e-6)
    # run normalize to allow auto-tighten to reach >=1.2
    plan = {
        "entries": entries,
        "weights": [0.5, 0.5],
        "invalid": invalid,
        "tp": [tp1, 120.0],
        "support": [],
        "resistance": [],
    }
    fixed, warns = normalize_and_validate(plan)
    assert fixed["rr_min"] >= 1.2
    assert fixed["invalid"] > invalid  # tightened upward


def test_validate_spot2_rewrites_tp_and_propagates_rr():
    spot2 = {
        "rencana_jual_beli": {
            "entries": [
                {"range": [100.0, 101.0], "weight": 0.6},
                {"range": [98.0, 99.0], "weight": 0.4},
            ],
            "invalid": 95.0,
        },
        "tp": [
            {"name": "TP1", "range": [110.0, 111.0]},
            {"name": "TP2", "range": [108.0, 109.0]},  # descending
        ],
    }
    v = validate_spot2(spot2)
    assert isinstance(v, dict) and "fixes" in v
    fixed = v["fixes"]
    # TP should be strictly ascending on first bound
    tps = [t["range"][0] for t in fixed.get("tp", [])]
    assert all(tps[i] < tps[i+1] for i in range(len(tps)-1))
    # rr_min should be present
    assert "metrics" in fixed and fixed["metrics"].get("rr_min", 0.0) >= 0.0
