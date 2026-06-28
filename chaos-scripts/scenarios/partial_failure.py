#!/usr/bin/env python3
"""
Scenario 3: Partial Failure
=============================
Injects a latency toxic (2000ms ± 500ms) on inventory-proxy ONLY.
Payment-service remains healthy. This tests whether a pattern can isolate
a single dependency failure without affecting the healthy payment path.

This is the most realistic scenario — in production, rarely do all
dependencies fail simultaneously.

Expected behaviour:
  none            — inventory calls time out; order fails at inventory step;
                    payment never reached (cascade via early exit)
  circuit-breaker — CB opens on inventory; fallback fires; payment still healthy
  bulkhead        — inventory semaphore exhausted independently of payment semaphore
  combined        — CB on inventory opens; payment path unaffected

Usage:
    python chaos-scripts/scenarios/partial_failure.py [--duration SECONDS]
    python chaos-scripts/scenarios/partial_failure.py --remove
"""

import argparse
import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from toxiproxy_client import add_toxic, remove_toxic, ensure_proxies

TOXIC_NAME = "partial-failure"
TARGET_PROXY = "inventory-proxy"
LATENCY_MS = 2000
JITTER_MS = 500


def apply() -> None:
    print(f"[partial_failure] Applying: {LATENCY_MS}ms ± {JITTER_MS}ms on inventory-proxy ONLY")
    ensure_proxies()
    add_toxic(
        proxy=TARGET_PROXY,
        toxic_name=TOXIC_NAME,
        toxic_type="latency",
        attributes={"latency": LATENCY_MS, "jitter": JITTER_MS},
        toxicity=1.0,
    )
    print(f"  ✓ latency toxic active on '{TARGET_PROXY}'")
    print("  ✓ payment-proxy untouched (healthy)")
    print("[partial_failure] Fault ACTIVE — inventory slow, payment healthy")


def remove() -> None:
    print("[partial_failure] Removing fault...")
    remove_toxic(TARGET_PROXY, TOXIC_NAME)
    print(f"  ✓ toxic removed from '{TARGET_PROXY}'")
    print("[partial_failure] Fault CLEARED")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--duration", type=int, default=0,
                        help="Seconds to hold fault (0 = manual, default: 0)")
    parser.add_argument("--remove", action="store_true",
                        help="Remove the fault instead of applying it")
    args = parser.parse_args()

    if args.remove:
        remove()
        return

    apply()

    if args.duration > 0:
        print(f"\n  Holding fault for {args.duration}s...")
        time.sleep(args.duration)
        remove()
    else:
        print("\n  Run with --remove to clear the fault, or run teardown.py")


if __name__ == "__main__":
    main()
