#!/usr/bin/env python3
"""
Scenario 4: Cascading Failure
================================
Two-phase fault injection to simulate cascading failure propagation:

  Phase 1 (t=0):       Inject latency on inventory-proxy
                        → inventory slowness consumes order-service threads
  Phase 2 (t=DELAY):   Inject latency on payment-proxy
                        → now both paths are degraded simultaneously
                        → without patterns: total system collapse
                        → with CB: inventory CB opens → resources freed
                          before payment becomes a problem

The DELAY between phases (default 10s) is intentional — it gives the
circuit breaker time to observe failures and open before payment degrades.
Under the `none` pattern, thread exhaustion in the inventory path should
spill over to payment requests, demonstrating true cascading.

Usage:
    python chaos-scripts/scenarios/cascading_failure.py [--delay SECONDS] [--duration SECONDS]
    python chaos-scripts/scenarios/cascading_failure.py --remove
"""

import argparse
import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from toxiproxy_client import add_toxic, remove_toxic, ensure_proxies

TOXIC_NAME = "cascading-failure"
LATENCY_MS = 2000
JITTER_MS = 500
DEFAULT_PHASE_DELAY = 10   # seconds between phase 1 and phase 2
DEFAULT_HOLD_DURATION = 0  # 0 = manual teardown


def apply(phase_delay: int) -> None:
    print("[cascading_failure] Phase 1 — injecting latency on inventory-proxy")
    ensure_proxies()

    add_toxic(
        proxy="inventory-proxy",
        toxic_name=TOXIC_NAME,
        toxic_type="latency",
        attributes={"latency": LATENCY_MS, "jitter": JITTER_MS},
        toxicity=1.0,
    )
    print(f"  ✓ latency toxic active on 'inventory-proxy' ({LATENCY_MS}ms ± {JITTER_MS}ms)")

    if phase_delay > 0:
        print(f"\n  Waiting {phase_delay}s for inventory failures to accumulate "
              f"(CB should observe slow calls during this window)...")
        time.sleep(phase_delay)

    print("\n[cascading_failure] Phase 2 — injecting latency on payment-proxy (cascade begins)")
    add_toxic(
        proxy="payment-proxy",
        toxic_name=TOXIC_NAME,
        toxic_type="latency",
        attributes={"latency": LATENCY_MS, "jitter": JITTER_MS},
        toxicity=1.0,
    )
    print(f"  ✓ latency toxic active on 'payment-proxy' ({LATENCY_MS}ms ± {JITTER_MS}ms)")
    print("[cascading_failure] Fault ACTIVE — cascading failure in progress")


def remove() -> None:
    print("[cascading_failure] Removing faults...")
    for proxy in ["inventory-proxy", "payment-proxy"]:
        remove_toxic(proxy, TOXIC_NAME)
        print(f"  ✓ toxic removed from '{proxy}'")
    print("[cascading_failure] Fault CLEARED — both paths restored")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--delay", type=int, default=DEFAULT_PHASE_DELAY,
                        help=f"Seconds between Phase 1 and Phase 2 (default: {DEFAULT_PHASE_DELAY})")
    parser.add_argument("--duration", type=int, default=DEFAULT_HOLD_DURATION,
                        help="Seconds to hold after Phase 2 before auto-removing (0 = manual, default: 0)")
    parser.add_argument("--remove", action="store_true",
                        help="Remove all cascading-failure toxics")
    args = parser.parse_args()

    if args.remove:
        remove()
        return

    apply(args.delay)

    if args.duration > 0:
        print(f"\n  Holding fault for {args.duration}s...")
        time.sleep(args.duration)
        remove()
    else:
        print("\n  Both phases active. Run with --remove to clear, or run teardown.py")


if __name__ == "__main__":
    main()
