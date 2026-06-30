#!/usr/bin/env python3
"""
Phase 10 — Automated experiment runner.

Drives the full 4 resilience profiles x 4 chaos scenarios x 20 trials = 320
trial experimental design (config.py), or a reduced subset for testing.

USAGE

  # Validate the orchestration logic only — no Docker/Gatling/Prometheus
  # touched. Safe to run anywhere, including a sandbox with none of those
  # installed. Writes to results/dryrun_trials.{csv,jsonl}, never the real
  # results files.
  python run_experiment.py --dry-run

  # End-to-end smoke test: 1 trial per cell (16 trials total), short load
  # profile (5 users / 5s ramp / 1min sustain). Run this FIRST against a
  # real stack before committing to the full ~40-hour run — it's the thing
  # that will surface a Gatling console-format mismatch (see
  # gatling_runner.py's module docstring) or a Prometheus query typo
  # immediately instead of 200 trials in.
  python run_experiment.py --smoke

  # Full run. Resumable: Ctrl-C or a crash, then re-run the same command —
  # already-completed trials (status=ok in results/trials.csv) are skipped.
  python run_experiment.py

  # Debug a single cell without running the whole matrix.
  python run_experiment.py --only-profile bulkhead --only-scenario latency_injection --smoke

PREREQUISITES (this script does not set these up for you):
  - Postgres.app running (see SKILL.md)
  - `docker compose up -d --build` already run at least once, OR pass
    --build to have this script do it
  - JAVA_HOME pointed at Corretto 21 (needed for the `mvn gatling:test`
    subprocess this script shells out to)

This file has NOT been run end-to-end against a live stack — I don't have
Docker/JDK21/Maven in the sandbox I built it in. --dry-run has been
exercised here to validate the loop/resume/CSV logic; --smoke has not.
Treat the first real --smoke run as part of finishing Phase 10, not as a
formality after the fact.
"""

import argparse
import sys
import time
import traceback
from pathlib import Path

import requests

import chaos_control
import config
import docker_control
import gatling_runner
import metrics_collector
import results_store


def log(msg: str) -> None:
    timestamp = results_store.now_utc_iso()
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.RUN_LOG, "a") as f:
        f.write(line + "\n")


def check_and_restock_inventory(sku: str = "SKU-001") -> None:
    try:
        resp = requests.get(f"http://localhost:8082/inventory/{sku}", timeout=5)
        resp.raise_for_status()
        quantity = resp.json().get("quantity")
        if quantity is None:
            log(f"  [restock] could not read quantity for {sku} from response, skipping check")
            return
        if quantity < config.MIN_STOCK_THRESHOLD:
            log(f"  [restock] {sku} stock low ({quantity}), restocking by {config.RESTOCK_AMOUNT}")
            restock_resp = requests.patch(
                f"http://localhost:8082/inventory/{sku}/restock",
                params={"quantity": config.RESTOCK_AMOUNT},
                timeout=5,
            )
            restock_resp.raise_for_status()
    except requests.RequestException as exc:
        # Non-fatal: log and let the trial proceed. If stock really is
        # exhausted, it'll show up as a spike in 409s in this trial's
        # results, which is visible and debuggable rather than silently
        # blocking the whole run on a flaky restock check.
        log(f"  [restock] check failed, continuing without restocking: {exc}")


def run_one_real_trial(profile: str, scenario: str, trial_num: int,
                        target_users: int, ramp_seconds: int, sustain_minutes: int) -> results_store.TrialRecord:
    trial_id = results_store.trial_id_for(profile, scenario, trial_num)
    started_at = results_store.now_utc_iso()

    check_and_restock_inventory()
    chaos_control.reset_proxies()

    log(f"  applying chaos scenario '{scenario}'")
    chaos_control.apply_scenario(scenario)

    trial_start = time.time()
    try:
        gatling_result = gatling_runner.run_trial(
            base_url=config.GATEWAY_BASE_URL,
            target_users=target_users,
            ramp_seconds=ramp_seconds,
            sustain_minutes=sustain_minutes,
        )
    finally:
        trial_end = time.time()
        fault_removed_at = time.time()
        log(f"  removing chaos scenario '{scenario}'")
        chaos_control.remove_scenario(scenario)

    log("  collecting Prometheus metrics + circuit breaker recovery time")
    metrics = metrics_collector.collect_trial_metrics(trial_start, trial_end, fault_removed_at)

    ended_at = results_store.now_utc_iso()

    return results_store.TrialRecord(
        trial_id=trial_id,
        resilience_profile=profile,
        chaos_scenario=scenario,
        trial_num=trial_num,
        started_at_utc=started_at,
        ended_at_utc=ended_at,
        status="ok",
        gatling_request_count=gatling_result.request_count,
        gatling_ok_count=gatling_result.ok_count,
        gatling_ko_count=gatling_result.ko_count,
        gatling_error_rate=gatling_result.error_rate,
        gatling_p50_ms=gatling_result.p50_ms,
        gatling_p95_ms=gatling_result.p95_ms,
        gatling_p99_ms=gatling_result.p99_ms,
        gatling_mean_response_ms=gatling_result.mean_response_ms,
        gatling_mean_requests_per_sec=gatling_result.mean_requests_per_sec,
        prometheus_error_rate=metrics.prometheus_error_rate,
        peak_process_cpu_usage=metrics.peak_process_cpu_usage,
        peak_jvm_heap_used_bytes=metrics.peak_jvm_heap_used_bytes,
        cb_recovery_time_seconds=metrics.cb_recovery_time_seconds,
        cb_was_open_during_trial=metrics.cb_was_open_during_trial,
        gatling_report_dir=str(gatling_result.report_dir) if gatling_result.report_dir else "",
    )


def run_one_dry_run_trial(profile: str, scenario: str, trial_num: int) -> results_store.TrialRecord:
    """No Docker/Gatling/Prometheus calls — just enough of a delay and
    fabricated-but-clearly-labeled data to exercise the loop, resume, and
    CSV-writing logic."""
    trial_id = results_store.trial_id_for(profile, scenario, trial_num)
    started_at = results_store.now_utc_iso()
    time.sleep(0.01)
    ended_at = results_store.now_utc_iso()
    return results_store.TrialRecord(
        trial_id=trial_id,
        resilience_profile=profile,
        chaos_scenario=scenario,
        trial_num=trial_num,
        started_at_utc=started_at,
        ended_at_utc=ended_at,
        status="ok",
        error_message="DRY RUN — synthetic record, not a real trial",
        gatling_request_count=0,
        gatling_ok_count=0,
        gatling_ko_count=0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                         help="Exercise loop/resume/CSV logic only, no real infra touched.")
    parser.add_argument("--smoke", action="store_true",
                         help="1 trial/cell, short load profile, against a real stack.")
    parser.add_argument("--build", action="store_true",
                         help="Run `docker compose up -d --build` before starting.")
    parser.add_argument("--only-profile", choices=config.RESILIENCE_PROFILES, default=None)
    parser.add_argument("--only-scenario", choices=config.CHAOS_SCENARIOS, default=None)
    parser.add_argument("--trials-per-cell", type=int, default=None,
                         help="Override trial count per cell (default: 20, or 1 with --smoke).")
    args = parser.parse_args()

    profiles = [args.only_profile] if args.only_profile else config.RESILIENCE_PROFILES
    scenarios = [args.only_scenario] if args.only_scenario else config.CHAOS_SCENARIOS

    if args.smoke:
        trials_per_cell = args.trials_per_cell or config.SMOKE_TRIALS_PER_CELL
        target_users, ramp_seconds, sustain_minutes = (
            config.SMOKE_TARGET_USERS, config.SMOKE_RAMP_SECONDS, config.SMOKE_SUSTAIN_MINUTES,
        )
    else:
        trials_per_cell = args.trials_per_cell or config.TRIALS_PER_CELL
        target_users, ramp_seconds, sustain_minutes = (
            config.GATLING_TARGET_USERS, config.GATLING_RAMP_SECONDS, config.GATLING_SUSTAIN_MINUTES,
        )

    total_trials = len(profiles) * len(scenarios) * trials_per_cell

    if args.dry_run:
        csv_path = config.RESULTS_DIR / "dryrun_trials.csv"
        jsonl_path = config.RESULTS_DIR / "dryrun_trials.jsonl"
    else:
        csv_path = config.RESULTS_CSV
        jsonl_path = config.RESULTS_JSONL

    completed = results_store.load_completed_trial_ids(csv_path)
    log(f"Starting run: {len(profiles)} profile(s) x {len(scenarios)} scenario(s) x "
        f"{trials_per_cell} trial(s) = {total_trials} total. "
        f"{len(completed)} already completed (resume). dry_run={args.dry_run} smoke={args.smoke}")

    if not args.dry_run:
        log("Bringing stack up...")
        docker_control.stack_up(build=args.build)
        docker_control.wait_for_full_stack_health()

    run_count = 0
    error_count = 0
    skip_count = 0

    for profile in profiles:
        if not args.dry_run:
            log(f"Switching order-service to resilience profile: {profile}")
            docker_control.switch_resilience_profile(profile)

        for scenario in scenarios:
            for trial_num in range(1, trials_per_cell + 1):
                trial_id = results_store.trial_id_for(profile, scenario, trial_num)
                if trial_id in completed:
                    skip_count += 1
                    continue

                log(f"Trial {trial_id} ({run_count + error_count + skip_count + 1}/{total_trials})")
                try:
                    if args.dry_run:
                        record = run_one_dry_run_trial(profile, scenario, trial_num)
                    else:
                        record = run_one_real_trial(
                            profile, scenario, trial_num, target_users, ramp_seconds, sustain_minutes
                        )
                    results_store.append_result(record, csv_path, jsonl_path)
                    run_count += 1
                except Exception as exc:  # noqa: BLE001 — a single bad trial must not kill the run
                    error_count += 1
                    log(f"  TRIAL FAILED: {exc}")
                    log(traceback.format_exc())
                    error_record = results_store.TrialRecord(
                        trial_id=trial_id,
                        resilience_profile=profile,
                        chaos_scenario=scenario,
                        trial_num=trial_num,
                        started_at_utc=results_store.now_utc_iso(),
                        ended_at_utc=results_store.now_utc_iso(),
                        status="error",
                        error_message=str(exc)[:500],
                    )
                    results_store.append_result(error_record, csv_path, jsonl_path)
                    # best-effort cleanup so one failed trial doesn't leave a
                    # toxic active for every subsequent trial
                    if not args.dry_run:
                        try:
                            chaos_control.remove_scenario(scenario)
                        except Exception:
                            log("  WARNING: cleanup after failed trial also failed — "
                                "check Toxiproxy state manually before continuing.")

                if not args.dry_run:
                    time.sleep(config.INTER_TRIAL_COOLDOWN_SECONDS)

    log(f"Run complete. {run_count} succeeded, {error_count} failed, {skip_count} skipped (already done).")
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
