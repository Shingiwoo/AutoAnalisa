#!/usr/bin/env python3
import argparse
import json
import os
import sys

# Ensure repo root on path when running as script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from autoanalisa.payload.builder import build_payload
from autoanalisa.utils.time import now_tz


def main():
    parser = argparse.ArgumentParser(description="Build AutoAnalisa payload JSON")
    parser.add_argument("symbol")
    parser.add_argument("--market", choices=["spot", "futures"], default="futures")
    parser.add_argument("--contract", choices=["perp", "delivery"], default="perp")
    parser.add_argument("--tfs", default="1D,4H,1H,15m")
    parser.add_argument("--tz", default="Asia/Jakarta")
    parser.add_argument("--outdir", default="payload_out")
    parser.add_argument("--use-fvg", action="store_true")
    parser.add_argument("--risk", type=float, default=None, help="Override risk_per_trade (e.g., 0.008)")
    parser.add_argument("--leverage", type=int, default=None, help="Override leverage (futures) or spot leverage proxy")
    parser.add_argument("--news-json", default=None, help="Path to JSON array of news/events to inject into payload")
    parser.add_argument("--macro-yaml", default=None, help="Path to macro session YAML schedule")
    parser.add_argument("--btc-bias", choices=["bull", "bear", "neutral"], default=None)
    args = parser.parse_args()

    news = None
    if args.news_json and os.path.exists(args.news_json):
        try:
            news = json.load(open(args.news_json))
        except Exception:
            news = None

    # macro session bias
    session_bias = None
    if args.macro_yaml and os.path.exists(args.macro_yaml):
        try:
            from autoanalisa.utils.macro import load_macro_schedule, session_bias_from_schedule
            sched = load_macro_schedule(args.macro_yaml)
            from autoanalisa.utils.time import now_tz
            session_bias = session_bias_from_schedule(sched, now_tz(args.tz), args.tz)
        except Exception:
            session_bias = None

    btc_bias = None
    if args.btc_bias:
        btc_bias = {"bull": "bullish", "bear": "bearish", "neutral": "neutral"}[args.btc_bias]

    payload = build_payload(
        args.symbol,
        args.market,
        args.contract,
        args.tfs.split(","),
        args.tz,
        args.use_fvg,
        override_risk=args.risk,
        override_lev=args.leverage,
        news=news,
        session_bias=session_bias,
        btc_bias=btc_bias,
    )

    os.makedirs(args.outdir, exist_ok=True)
    fn = f"{args.outdir}/{args.symbol}_{now_tz(args.tz).strftime('%Y%m%d-%H%M%S')}.json"
    with open(fn, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(fn)


if __name__ == "__main__":
    main()
