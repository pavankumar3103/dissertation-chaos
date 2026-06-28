"""
Thin wrapper around the Toxiproxy REST API.

Toxiproxy control plane runs at TOXIPROXY_API (default http://localhost:8474).

Proxy layout for this experiment:
  inventory-proxy  :  0.0.0.0:18082  →  inventory-service:8082
  payment-proxy    :  0.0.0.0:18083  →  payment-service:8083
"""

import requests
import sys

TOXIPROXY_API = "http://localhost:8474"

PROXIES = {
    "inventory-proxy": {
        "listen": "0.0.0.0:18082",
        "upstream": "inventory-service:8082",
    },
    "payment-proxy": {
        "listen": "0.0.0.0:18083",
        "upstream": "payment-service:8083",
    },
}


# ── helpers ────────────────────────────────────────────────────────────────


def _url(*parts: str) -> str:
    return TOXIPROXY_API + "/" + "/".join(p.strip("/") for p in parts)


def _ok(resp: requests.Response, action: str) -> dict:
    if resp.status_code not in (200, 201, 204):
        print(f"  [ERROR] {action}: HTTP {resp.status_code} — {resp.text}")
        sys.exit(1)
    return resp.json() if resp.text else {}


# ── proxy lifecycle ────────────────────────────────────────────────────────


def list_proxies() -> dict:
    return requests.get(_url("proxies")).json()


def create_proxy(name: str, listen: str, upstream: str) -> dict:
    payload = {"name": name, "listen": listen, "upstream": upstream, "enabled": True}
    resp = requests.post(_url("proxies"), json=payload)
    # 409 means already exists — that's fine
    if resp.status_code == 409:
        print(f"  [INFO] proxy '{name}' already exists, skipping creation")
        return {}
    return _ok(resp, f"create proxy '{name}'")


def delete_proxy(name: str) -> None:
    resp = requests.delete(_url("proxies", name))
    if resp.status_code == 404:
        print(f"  [INFO] proxy '{name}' not found, skipping delete")
        return
    _ok(resp, f"delete proxy '{name}'")


def reset_proxy(name: str) -> None:
    """Remove all toxics from a proxy without deleting it."""
    resp = requests.get(_url("proxies", name, "toxics"))
    if resp.status_code == 404:
        return
    for toxic in resp.json():
        remove_toxic(name, toxic["name"])


# ── toxic lifecycle ────────────────────────────────────────────────────────


def add_toxic(proxy: str, toxic_name: str, toxic_type: str,
              attributes: dict, toxicity: float = 1.0, stream: str = "downstream") -> dict:
    payload = {
        "name": toxic_name,
        "type": toxic_type,
        "stream": stream,
        "toxicity": toxicity,
        "attributes": attributes,
    }
    resp = requests.post(_url("proxies", proxy, "toxics"), json=payload)
    return _ok(resp, f"add toxic '{toxic_name}' to '{proxy}'")


def remove_toxic(proxy: str, toxic_name: str) -> None:
    resp = requests.delete(_url("proxies", proxy, "toxics", toxic_name))
    if resp.status_code == 404:
        print(f"  [INFO] toxic '{toxic_name}' not found on '{proxy}', skipping")
        return
    _ok(resp, f"remove toxic '{toxic_name}' from '{proxy}'")


def list_toxics(proxy: str) -> list:
    resp = requests.get(_url("proxies", proxy, "toxics"))
    if resp.status_code == 404:
        return []
    return resp.json()


# ── setup / teardown ───────────────────────────────────────────────────────


def ensure_proxies() -> None:
    """Create inventory-proxy and payment-proxy if they don't exist."""
    for name, cfg in PROXIES.items():
        print(f"  → ensuring proxy '{name}' ({cfg['listen']} → {cfg['upstream']})")
        create_proxy(name, cfg["listen"], cfg["upstream"])


def teardown_all() -> None:
    """Remove all toxics then delete both proxies."""
    for name in PROXIES:
        print(f"  → resetting toxics on '{name}'")
        reset_proxy(name)
        print(f"  → deleting proxy '{name}'")
        delete_proxy(name)
