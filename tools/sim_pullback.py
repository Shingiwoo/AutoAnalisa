#!/usr/bin/env python3
import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from autoanalisa.rules.pullback_v1 import generate_signals


def main():
    p = argparse.ArgumentParser(description="Simulate pullback rules on a payload JSON")
    p.add_argument("payload", help="Path to payload JSON file")
    args = p.parse_args()

    payload = json.load(open(args.payload))
    signals = generate_signals(payload)
    print(json.dumps([s.model_dump() for s in signals], indent=2))


if __name__ == "__main__":
    main()
