#!/usr/bin/env python3
"""
Scenario 2: Latency Injection
==============================
Injects a latency toxic (2000ms ± 500ms jitter) on BOTH inventory-proxy and
payment-proxy. This simulates degraded downstream services — slow but not dead.

With the default RestTemplate read timeout in order-service this will surface
as timeout exceptions unless a pattern (bulkhead/CB) intervenes first.

Expected behaviour:
  none            — most requests time out; throughput collapses
  circuit-breaker — CB opens once slow-call threshold breached; fast-fails after
  bulkhead        — concurrent call cap hit; queued callers rejected
  combined        — CB + bulkhead; fastest degradation recovery

Usage:
    python chaos-scripts/scenarios/latency_injection.py [--duration SECONDS]
    python chaos-scripts/scenarios/latency_injection.py --remove
    python chaos-scripts/scenarios/latency_injection.py --latency 3000 --jitter 1000
"""

import argparse
import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from toxiproxy_client import add_toxic, remove_toxic, ensure_proxies

TOXIC_NAME = "latency-injection"
TARGETS = ["inventory-proxy", "payment-proxy"]
DEFAULT_LATENCY_MS = 2000
DEFAULT_JITTER_MS = 500


def apply(latency: int, jitter: int) -> None:
    print(f"[latency_injection] Applying: {latency}ms ± {jitter}ms on inventory-proxy + payment-proxy")
    ensure_proxies()
    for proxy in TARGETS:
        add_toxic(
            proxy=proxy,
            toxic_name=TOXIC_NAME,
            toxic_type="latency",
            attributes={"latency": latency, "jitter": jitter},
            toxicity=1.0,
        )
        print(f"  ✓ latency toxic active on '{proxy}' ({latency}ms ± {jitter}ms)")
    print("[latency_injection] Fault ACTIVE — both downstream services are slow")


def remove() -> None:
    print("[latency_injection] Removing faults...")
    for proxy in TARGETS:
        remove_toxic(proxy, TOXIC_NAME)
        print(f"  ✓ toxic removed from '{proxy}'")
    print("[latency_injection] Fault CLEARED — services restored to normal latency")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--duration", type=int, default=0,
                        help="Seconds to hold fault (0 = manual, default: 0)")
    parser.add_argument("--latency", type=int, default=DEFAULT_LATENCY_MS,
                        help=f"Added latency in ms (default: {DEFAULT_LATENCY_MS})")
    parser.add_argument("--jitter", type=int, default=DEFAULT_JITTER_MS,
                        help=f"Latency jitter in ms (default: {DEFAULT_JITTER_MS})")
    parser.add_argument("--remove", action="store_true",
                        help="Remove the fault instead of applying it")
    args = parser.parse_args()

    if args.remove:
        remove()
        return

    apply(args.latency, args.jitter)

    if args.duration > 0:
        print(f"\n  Holding fault for {args.duration}s...")
        time.sleep(args.duration)
        remove()
    else:
        print("\n  Run with --remove to clear the fault, or run teardown.py")


if __name__ == "__main__":
    main()
