#!/usr/bin/env python3
"""
Scenario 1: Service Termination
================================
Injects a timeout toxic with timeout=0 on both inventory-proxy and payment-proxy.
A 0 ms timeout causes Toxiproxy to close the connection immediately, simulating
complete service unavailability from order-service's perspective.

Expected behaviour under each resilience pattern:
  none            — all downstream calls fail instantly; order fails
  circuit-breaker — CB opens after threshold; fast-fails subsequent calls
  bulkhead        — semaphore exhausted; callers rejected immediately
  combined        — CB + bulkhead both activate; maximum isolation

Usage:
    python chaos-scripts/scenarios/service_termination.py [--duration SECONDS]

Options:
    --duration  How long to hold the fault before auto-removing (default: manual, 0 = keep)
"""

import argparse
import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from toxiproxy_client import add_toxic, remove_toxic, ensure_proxies

TOXIC_NAME = "service-termination"
TARGETS = ["inventory-proxy", "payment-proxy"]


def apply() -> None:
    print("[service_termination] Applying: timeout=0 on inventory-proxy + payment-proxy")
    ensure_proxies()
    for proxy in TARGETS:
        add_toxic(
            proxy=proxy,
            toxic_name=TOXIC_NAME,
            toxic_type="timeout",
            attributes={"timeout": 0},
            toxicity=1.0,
        )
        print(f"  ✓ timeout toxic active on '{proxy}'")
    print("[service_termination] Fault ACTIVE — both downstream services appear terminated")


def remove() -> None:
    print("[service_termination] Removing faults...")
    for proxy in TARGETS:
        remove_toxic(proxy, TOXIC_NAME)
        print(f"  ✓ toxic removed from '{proxy}'")
    print("[service_termination] Fault CLEARED — services restored")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--duration", type=int, default=0,
                        help="Seconds to hold fault (0 = manual removal, default: 0)")
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
