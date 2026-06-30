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
section (2026-06-30 verification run). The query windows / step sizes here
are new and have NOT been run against a live trial yet.
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
    (real-time polling, not query_range, since this needs to observe live
    state as it happens immediately after teardown) until both named
    instances report state="closed", or max_wait_seconds elapses.

    Returns (recovery_time_seconds_or_None, was_open_during_window_bool).
    """
    max_wait_seconds = max_wait_seconds or config.RECOVERY_WAIT_TIMEOUT_SECONDS
    deadline = time.monotonic() + max_wait_seconds
    was_open = False
    poll_start = time.monotonic()

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
