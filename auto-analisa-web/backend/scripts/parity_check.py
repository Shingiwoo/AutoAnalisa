#!/usr/bin/env python3
import argparse, json
import pandas as pd
from app.services.fvg import detect_fvg
from app.services.supply_demand import detect_zones
from app.services.parity import fvg_parity_stats, zones_parity_stats


def main():
    ap = argparse.ArgumentParser(description="Parity checker for indicators")
    ap.add_argument("csv", help="OHLCV CSV with columns: ts,open,high,low,close,volume")
    ap.add_argument("expected_json", help="Reference JSON (keys: fvg, zones)")
    ap.add_argument("--tf", default="15m",
                    help="Timeframe (informational only, choose 15m for FVG; 1h for zones)")
    ap.add_argument("--tol_price", type=float, default=1e-4)
    ap.add_argument("--tol_idx", type=int, default=1)
    ap.add_argument("--min_iou", type=float, default=0.6)
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    with open(args.expected_json, "r") as f:
        ref = json.load(f)

    fvg_ref = ref.get("fvg", [])
    z_ref = ref.get("zones", [])

    fvg_got = detect_fvg(df)
    zones_got = detect_zones(df)

    fvg_stats = fvg_parity_stats(fvg_ref, fvg_got, tol_price=args.tol_price, tol_idx=args.tol_idx)
    z_stats = zones_parity_stats(z_ref, zones_got, tol_idx=args.tol_idx, min_iou=args.min_iou)

    out = {
        "fvg": fvg_stats,
        "zones": z_stats,
    }
    print(json.dumps(out, indent=2))
    # non-zero exit when fail threshold
    ok = (fvg_stats.get("f1", 0) >= 0.9) and (z_stats.get("f1", 0) >= 0.9)
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    main()

