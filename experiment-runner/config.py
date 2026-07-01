"""
Phase 10 — Experiment configuration.

Single source of truth for the 4 x 4 x 20 = 320-trial design described in the
dissertation's experimental design (SKILL.md / Chapter 3 methodology). Every
other module in experiment-runner/ imports its constants from here rather
than hardcoding them, so changing the design (e.g. trials-per-cell during a
pilot run) only requires editing this one file.
"""

import os
from pathlib import Path

# ── repo layout ──────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAOS_SCRIPTS_DIR = REPO_ROOT / "chaos-scripts"
GATLING_DIR = REPO_ROOT / "gatling"
RESULTS_DIR = REPO_ROOT / "experiment-runner" / "results"

# ── experimental design ─────────────────────────────────────────────────

# Must match the Spring profile names in order-service/src/main/resources/
# application-<profile>.yml exactly. "retry" added post-Phase-10-verification
# (2026-07-01) at Pavan's request, to isolate retry-with-backoff's own effect
# instead of only ever seeing it mixed into "combined" -- has the same CB/
# bulkhead-neutralization treatment as "none"/"bulkhead" (see
# application-retry.yml), verified as valid YAML but NOT yet run in a live
# --smoke pass the way the original 4 profiles were.
RESILIENCE_PROFILES = ["none", "circuit-breaker", "bulkhead", "retry", "combined"]

# Must match the module names under chaos-scripts/scenarios/ (Phase 7).
CHAOS_SCENARIOS = ["service_termination", "latency_injection", "partial_failure", "cascading_failure"]

TRIALS_PER_CELL = 20
TOTAL_TRIALS = len(RESILIENCE_PROFILES) * len(CHAOS_SCENARIOS) * TRIALS_PER_CELL  # 5 x 4 x 20 = 400

# ── Gatling load profile (matches OrderSimulation.java defaults, Phase 8) ──

GATLING_TARGET_USERS = 50
GATLING_RAMP_SECONDS = 30
GATLING_SUSTAIN_MINUTES = 5

# Smoke-test overrides (--smoke flag): 1 trial per cell, short load profile,
# so the whole harness can be validated end-to-end in ~15-20 minutes instead
# of committing to the full ~40-hour run blind.
SMOKE_TRIALS_PER_CELL = 1
SMOKE_TARGET_USERS = 5
SMOKE_RAMP_SECONDS = 5
SMOKE_SUSTAIN_MINUTES = 1

# ── service endpoints (host-side, matches docker-compose.yml port mappings) ──

GATEWAY_BASE_URL = "http://localhost:8080"
ORDER_SERVICE_HEALTH_URL = "http://localhost:8081/actuator/health"
INVENTORY_SERVICE_HEALTH_URL = "http://localhost:8082/actuator/health"
PAYMENT_SERVICE_HEALTH_URL = "http://localhost:8083/actuator/health"
GATEWAY_HEALTH_URL = "http://localhost:8080/actuator/health"
TOXIPROXY_API_URL = "http://localhost:8474"
PROMETHEUS_API_URL = "http://localhost:9090"

# ── timing / safety ─────────────────────────────────────────────────────

# How long to wait for order-service to report UP after a profile-switch
# restart before giving up on a cell.
SERVICE_HEALTH_TIMEOUT_SECONDS = 90
SERVICE_HEALTH_POLL_INTERVAL_SECONDS = 2

# Cooldown between trials so one trial's tail traffic / Prometheus scrape
# lag doesn't bleed into the next trial's metrics window.
INTER_TRIAL_COOLDOWN_SECONDS = 10

# How long after chaos removal to keep polling Prometheus/Gatling-derived
# signals for a recovery-time measurement before giving up and recording
# recovery_time_seconds = None (not "0", which would misleadingly imply
# instant recovery).
RECOVERY_WAIT_TIMEOUT_SECONDS = 60

# Minimum stock remaining on SKU-001 before the runner tops it up again via
# the inventory-service restock endpoint. data.sql seeds 1,000,000 units;
# this is a defensive backstop, not the primary supply (see Phase 8 ELI5
# caveats on stock exhaustion masquerading as chaos-induced failure).
MIN_STOCK_THRESHOLD = 5000
RESTOCK_AMOUNT = 500000

# ── output ───────────────────────────────────────────────────────────────

RESULTS_CSV = RESULTS_DIR / "trials.csv"
RESULTS_JSONL = RESULTS_DIR / "trials.jsonl"
RUN_LOG = RESULTS_DIR / "run.log"


def docker_compose_env(resilience_profile: str) -> dict:
    """Environment to pass to a `docker compose` subprocess so order-service
    picks up RESILIENCE_PROFILE on its next (re)create. Starts from the
    current process environment so PATH/HOME/etc. are preserved."""
    env = os.environ.copy()
    env["RESILIENCE_PROFILE"] = resilience_profile
    return env
