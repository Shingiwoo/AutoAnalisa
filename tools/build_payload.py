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
    args = parser.parse_args()

    payload = build_payload(args.symbol, args.market, args.contract, args.tfs.split(","), args.tz, args.use_fvg)

    os.makedirs(args.outdir, exist_ok=True)
    fn = f"{args.outdir}/{args.symbol}_{now_tz(args.tz).strftime('%Y%m%d-%H%M%S')}.json"
    with open(fn, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(fn)


if __name__ == "__main__":
    main()
