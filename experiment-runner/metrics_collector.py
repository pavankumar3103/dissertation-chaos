"""
Phase 10 — Prometheus-backed metrics collection.

Uses the `requests` library, matching chaos-scripts/toxiproxy_client.py's
existing convention (Pavan already has it installed — verified working
against a live Toxiproxy in Phase 7).

All PromQL metric names below (resilience4j_circuitbreaker_state,
resilience4j_circuitbreaker_calls_seconds_count, http_server_requests_seconds_count,
process_cpu_usage, jvm_memory_used_bytes) are not guessed — they're the
exact names Pavan confirmed live against Prometheus's /api/v1/targets and
a real order placed through the gateway, per Phase 9's ELI5 honest-caveats
section (2026-06-30 verification run).

STATUS AFTER THE FIRST FULL 400-TRIAL RUN (2026-07-03):
- get_circuitbreaker_recovery() was broken (fixed below, see its own
  docstring) — it never generated post-fault traffic, so a genuinely-open
  CB could never be observed closing again. 0/100 trials where the CB
  actually opened got a real recovery-time measurement.
- get_resource_consumption() worked correctly for 4 of 5 profiles across
  all 400 trials, but returned nothing for 65/80 circuit-breaker trials —
  not a bug in this function, but a real gap in what Prometheus could
  scrape from order-service during that window (see ELI5_LOG.md's Phase 10
  update on the suspected HikariCP connection exhaustion under
  circuit-breaker's uncapped bulkhead).
- get_order_error_rate() is still an OPEN, undiagnosed issue: only 8/400
  trials got any value at all (the rest returned None because `total`
  came back 0 from the query_range call). This wasn't touched in this
  round of fixes — gatling_error_rate already covers error-propagation
  rate reliably across all 400 trials, so it wasn't blocking, but if this
  matters for a Prometheus-side cross-check later, the PromQL query
  itself (probably a label-matching or timing issue) needs live debugging
  against a real Prometheus instance, which isn't possible from where
  this was written.
"""

import time
from dataclasses import dataclass
from typing import Optional

import requests

import config


class PrometheusQueryError(RuntimeError):
    pass


def _query_range(promql: str, start: float, end: float, step: str = "5s") -> list:
    resp = requests.get(
        f"{config.PROMETHEUS_API_URL}/api/v1/query_range",
        params={"query": promql, "start": start, "end": end, "step": step},
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "success":
        raise PrometheusQueryError(f"query_range failed for {promql!r}: {body}")
    return body["data"]["result"]


def _query_instant(promql: str, at: float) -> list:
    resp = requests.get(
        f"{config.PROMETHEUS_API_URL}/api/v1/query",
        params={"query": promql, "time": at},
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "success":
        raise PrometheusQueryError(f"query failed for {promql!r}: {body}")
    return body["data"]["result"]


@dataclass
class TrialMetrics:
    # error propagation: fraction of /orders calls that failed, per Prometheus's
    # own view (independent corroboration of Gatling's KO count)
    prometheus_error_rate: Optional[float]
    # resource consumption: peak values observed on order-service during the window
    peak_process_cpu_usage: Optional[float]  # 0.0-1.0
    peak_jvm_heap_used_bytes: Optional[float]
    # recovery: seconds from fault removal to circuit breakers reporting
    # "closed" again for both inventoryService and paymentService.
    # None means "never observed open" (profile/scenario combo didn't trip
    # it) vs a value of e.g. 0.0 meaning "already closed at first sample
    # after removal" -- callers must distinguish these, not treat None as 0.
    cb_recovery_time_seconds: Optional[float]
    cb_was_open_during_trial: bool


def _peak(series_result: list) -> Optional[float]:
    values = []
    for series in series_result:
        for _, v in series.get("values", []):
            try:
                values.append(float(v))
            except (TypeError, ValueError):
                continue
    return max(values) if values else None


def get_resource_consumption(service_job: str, start: float, end: float) -> tuple:
    cpu_series = _query_range(
        f'process_cpu_usage{{job="{service_job}"}}', start, end
    )
    heap_series = _query_range(
        f'jvm_memory_used_bytes{{job="{service_job}",area="heap"}}', start, end
    )
    return _peak(cpu_series), _peak(heap_series)


def get_order_error_rate(start: float, end: float) -> Optional[float]:
    """Fraction of POST /orders calls on order-service that did NOT return
    2xx, over [start, end], per Prometheus's http_server_requests metric."""
    total_series = _query_range(
        'sum(increase(http_server_requests_seconds_count{job="order-service",uri="/orders",method="POST"}[5s]))',
        start, end,
    )
    error_series = _query_range(
        'sum(increase(http_server_requests_seconds_count{job="order-service",uri="/orders",method="POST",outcome!="SUCCESS"}[5s]))',
        start, end,
    )
    total = sum(float(v) for series in total_series for _, v in series.get("values", []))
    errors = sum(float(v) for series in error_series for _, v in series.get("values", []))
    if total == 0:
        return None
    return errors / total


def get_circuitbreaker_recovery(
    fault_removed_at: float,
    instance_names: tuple = ("inventoryService", "paymentService"),
    max_wait_seconds: int = None,
) -> tuple:
    """Polls resilience4j_circuitbreaker_state from fault_removed_at onward
    until both named instances report state="closed", or max_wait_seconds
    elapses.

    BUG FIXED (found after the first full 400-trial run, 2026-07-03): this
    used to only poll state passively. Resilience4j's circuit breaker can
    transition OPEN -> HALF_OPEN on a timer alone (automaticTransition...
    Enabled: true), but HALF_OPEN -> CLOSED requires actual calls to
    succeed (permittedNumberOfCallsInHalfOpenState) -- it will NOT close on
    its own without traffic. Since Gatling has already stopped by the time
    this runs, there was never any traffic to drive that transition, so
    every trial where the CB genuinely opened recorded recovery_time as
    None (checked against cb_was_open_during_trial across the full
    dataset: all 100 trials where CB opened showed null recovery; all 300
    where the value was populated were cases where CB never opened in the
    first place and "recovered" trivially/meaninglessly). This version
    actively fires a real probe order through the gateway on every poll
    iteration, specifically so there's something for a half-open CB to
    evaluate.
    """
    max_wait_seconds = max_wait_seconds or config.RECOVERY_WAIT_TIMEOUT_SECONDS
    deadline = time.monotonic() + max_wait_seconds
    was_open = False
    poll_start = time.monotonic()

    probe_body = {"sku": "SKU-001", "quantity": 1, "totalAmount": 9.99}

    while time.monotonic() < deadline:
        all_closed = True
        for instance in instance_names:
            result = _query_instant(
                f'resilience4j_circuitbreaker_state{{name="{instance}",state="closed"}}',
                at=time.time(),
            )
            is_closed = any(float(r["value"][1]) == 1.0 for r in result)
            if not is_closed:
                all_closed = False
                was_open = True
        if all_closed:
            return (time.monotonic() - poll_start), was_open

        # Fire a real probe request so a half-open CB has a call to
        # evaluate. Deliberately ignore the outcome here -- we only care
        # about the CB's resulting *state*, read on the next loop
        # iteration via the query above, not whether this one call
        # succeeded.
        try:
            requests.post(f"{config.GATEWAY_BASE_URL}/orders", json=probe_body, timeout=10)
        except requests.RequestException:
            pass

        time.sleep(2)

    return None, was_open


def collect_trial_metrics(
    trial_start: float,
    trial_end: float,
    fault_removed_at: float,
) -> TrialMetrics:
    error_rate = get_order_error_rate(trial_start, trial_end)
    cpu, heap = get_resource_consumption("order-service", trial_start, trial_end)
    recovery_seconds, was_open = get_circuitbreaker_recovery(fault_removed_at)

    return TrialMetrics(
        prometheus_error_rate=error_rate,
        peak_process_cpu_usage=cpu,
        peak_jvm_heap_used_bytes=heap,
        cb_recovery_time_seconds=recovery_seconds,
        cb_was_open_during_trial=was_open,
    )
