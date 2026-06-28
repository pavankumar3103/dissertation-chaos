#!/usr/bin/env python3
"""
setup_proxies.py — Create Toxiproxy proxies for inventory-service and payment-service.

Run once before any experiment trial (or let the experiment runner call it).
Safe to run repeatedly: existing proxies are left untouched.

Usage:
    python chaos-scripts/setup_proxies.py
"""

import sys
import requests
from toxiproxy_client import TOXIPROXY_API, PROXIES, ensure_proxies, list_proxies


def check_api_reachable() -> None:
    try:
        resp = requests.get(TOXIPROXY_API + "/version", timeout=3)
        version = resp.json().get("version", "unknown")
        print(f"[OK] Toxiproxy API reachable — version {version}")
    except Exception as exc:
        print(f"[ERROR] Cannot reach Toxiproxy API at {TOXIPROXY_API}: {exc}")
        print("       Is the Docker stack running? (docker compose up -d)")
        sys.exit(1)


def main() -> None:
    print("=== setup_proxies.py ===")
    check_api_reachable()

    print("\nCreating proxies...")
    ensure_proxies()

    print("\nCurrent proxy state:")
    proxies = list_proxies()
    for name, info in proxies.items():
        status = "enabled" if info.get("enabled") else "DISABLED"
        print(f"  {name:20s}  {info.get('listen'):20s} → {info.get('upstream'):30s}  [{status}]")

    print("\n[DONE] Proxies ready. Order-service traffic now flows through Toxiproxy.")


if __name__ == "__main__":
    main()
