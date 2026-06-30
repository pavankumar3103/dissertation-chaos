"""
Phase 10 — adapter over the existing Phase 7 chaos-scripts.

Deliberately does NOT modify chaos-scripts/ (frozen Phase 7 work, verified
already) — just imports the four scenario modules' apply()/remove()
functions with their documented default parameters and calls them in the
same way Pavan would run them by hand.

Design decision worth flagging explicitly: each scenario's apply() is
called to completion BEFORE the Gatling trial starts, and the fault stays
active for the entire trial duration, then remove() is called after the
trial ends. This matches how the Phase 7 scripts are actually built (e.g.
cascading_failure.apply() blocks through its own internal phase-delay
before returning) and how their docstrings describe expected behaviour
("Fault ACTIVE" for the duration of an external load test) — it does NOT
inject the fault mid-trial against already-ramped traffic. Injecting
mid-trial would need new hooks added to the Phase 7 scripts, which is out
of scope here since those files are frozen unless Pavan asks otherwise.
"""

import importlib
import sys

import config

sys.path.insert(0, str(config.CHAOS_SCRIPTS_DIR))

import toxiproxy_client  # noqa: E402  (path inserted above)

_SCENARIO_DEFAULTS = {
    "service_termination": {},
    "latency_injection": {"latency": 2000, "jitter": 500},
    "partial_failure": {},
    "cascading_failure": {"phase_delay": 10},
}


def _load_scenario(name: str):
    if name not in config.CHAOS_SCENARIOS:
        raise ValueError(f"unknown chaos scenario: {name}")
    return importlib.import_module(f"scenarios.{name}")


def reset_proxies() -> None:
    """Safety net: ensure both proxies exist and have no leftover toxics
    from a previous crashed/interrupted trial before starting a new one."""
    toxiproxy_client.ensure_proxies()
    for proxy_name in toxiproxy_client.PROXIES:
        toxiproxy_client.reset_proxy(proxy_name)


def apply_scenario(name: str) -> None:
    module = _load_scenario(name)
    kwargs = _SCENARIO_DEFAULTS[name]
    module.apply(**kwargs)


def remove_scenario(name: str) -> None:
    module = _load_scenario(name)
    module.remove()
