#!/usr/bin/env python3
"""
teardown.py — Remove all toxics and proxies from Toxiproxy.

Call this:
  - Between experiment trials to reset state
  - After a scenario crash to ensure clean slate
  - At the end of a test session

Usage:
    python chaos-scripts/teardown.py              # remove toxics, keep proxies
    python chaos-scripts/teardown.py --full       # remove toxics AND delete proxies
"""

import argparse
import sys
import requests
from toxiproxy_client import TOXIPROXY_API, PROXIES, reset_proxy, teardown_all, list_proxies


def reset_toxics_only() -> None:
    """Remove all toxics from known proxies, leaving the proxies themselves in place."""
    print("[teardown] Removing all toxics (proxies kept)...")
    try:
        existing = list_proxies()
    except Exception as exc:
        print(f"[ERROR] Cannot reach Toxiproxy API: {exc}")
        sys.exit(1)

    for name in PROXIES:
        if name in existing:
            reset_proxy(name)
            print(f"  ✓ all toxics removed from '{name}'")
        else:
            print(f"  [skip] proxy '{name}' does not exist")

    print("[teardown] DONE — proxies healthy, no active toxics")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--full", action="store_true",
                        help="Also delete proxies (next run of setup_proxies.py will recreate them)")
    args = parser.parse_args()

    print("=== teardown.py ===")

    # Quick reachability check
    try:
        requests.get(TOXIPROXY_API + "/version", timeout=3)
    except Exception as exc:
        print(f"[ERROR] Cannot reach Toxiproxy API at {TOXIPROXY_API}: {exc}")
        sys.exit(1)

    if args.full:
        print("[teardown] Full teardown — removing toxics AND deleting proxies...")
        teardown_all()
        print("[teardown] DONE — all proxies deleted")
    else:
        reset_toxics_only()


if __name__ == "__main__":
    main()
