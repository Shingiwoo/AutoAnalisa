from app.services.validator import normalize_and_validate, compute_rr_min


def test_tp_ascending_and_rr_min_autoadjust():
    p = {
        "support": [100, 99],
        "resistance": [110, 115],
        "entries": [101.0, 100.5],
        "weights": [0.6, 0.4],
        "invalid": 99.5,  # loose stop → low RR
        "tp": [108.0, 112.0],
    }
    p2, warns = normalize_and_validate(p)
    assert p2["tp"][0] < p2["tp"][1]  # ascending
    # Should auto-tighten invalid to reach >= 1.2 when possible
    assert p2["rr_min"] >= 1.1  # allow small tolerance
    assert p2["invalid"] < min(p2["entries"])  # logical stop

