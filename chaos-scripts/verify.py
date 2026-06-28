#!/usr/bin/env python3
"""
verify.py — Smoke-test the Toxiproxy setup before running experiments.

Checks:
  1. Toxiproxy API is reachable at localhost:8474
  2. Both proxies exist and are enabled
  3. No toxics are currently active (clean state)
  4. Traffic can flow through each proxy port (TCP connect test)

Usage:
    python chaos-scripts/verify.py

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

import socket
import sys
import requests
from toxiproxy_client import TOXIPROXY_API, PROXIES, list_proxies, list_toxics

PASS = "  ✓"
FAIL = "  ✗"

errors: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    tag = PASS if ok else FAIL
    suffix = f"  ({detail})" if detail else ""
    print(f"{tag} {label}{suffix}")
    if not ok:
        errors.append(label)


# ── Check 1: API reachable ─────────────────────────────────────────────────

def check_api() -> bool:
    try:
        resp = requests.get(TOXIPROXY_API + "/version", timeout=3)
        version = resp.json().get("version", "?")
        check("Toxiproxy API reachable", True, f"version {version}")
        return True
    except Exception as exc:
        check("Toxiproxy API reachable", False, str(exc))
        print("\n[FATAL] Toxiproxy is not reachable. Is Docker running?")
        print("  docker compose up -d toxiproxy")
        return False


# ── Check 2: Proxies exist and are enabled ─────────────────────────────────

def check_proxies() -> None:
    try:
        existing = list_proxies()
    except Exception as exc:
        check("list_proxies()", False, str(exc))
        return

    for name, cfg in PROXIES.items():
        if name not in existing:
            check(f"proxy '{name}' exists", False, "run setup_proxies.py first")
        else:
            enabled = existing[name].get("enabled", False)
            check(f"proxy '{name}' exists and enabled", enabled,
                  f"{cfg['listen']} → {cfg['upstream']}")


# ── Check 3: No active toxics ──────────────────────────────────────────────

def check_no_toxics() -> None:
    for name in PROXIES:
        try:
            toxics = list_toxics(name)
            if toxics:
                names = [t["name"] for t in toxics]
                check(f"proxy '{name}' has no active toxics", False,
                      f"active: {names} — run teardown.py")
            else:
                check(f"proxy '{name}' has no active toxics", True)
        except Exception as exc:
            check(f"check toxics on '{name}'", False, str(exc))


# ── Check 4: TCP connectivity through proxy ports ─────────────────────────

def check_tcp(host: str, port: int, label: str) -> None:
    try:
        with socket.create_connection((host, port), timeout=2):
            check(f"TCP connect to {label} ({host}:{port})", True)
    except Exception as exc:
        check(f"TCP connect to {label} ({host}:{port})", False, str(exc))


def check_connectivity() -> None:
    # Proxy ports exposed on localhost: 18082 (inventory), 18083 (payment)
    check_tcp("localhost", 18082, "inventory-proxy")
    check_tcp("localhost", 18083, "payment-proxy")


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== verify.py — Toxiproxy smoke test ===\n")

    print("1. API reachability")
    if not check_api():
        sys.exit(1)

    print("\n2. Proxy existence")
    check_proxies()

    print("\n3. Active toxics (expect none)")
    check_no_toxics()

    print("\n4. TCP connectivity through proxies")
    check_connectivity()

    print()
    if errors:
        print(f"[FAIL] {len(errors)} check(s) failed:")
        for e in errors:
            print(f"       - {e}")
        sys.exit(1)
    else:
        print("[PASS] All checks passed — ready to run experiments")


if __name__ == "__main__":
    main()
