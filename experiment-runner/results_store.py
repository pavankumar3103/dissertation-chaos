"""
Phase 10 — Results persistence + resume support.

Two output files, kept in sync, written after every trial (not buffered to
the end) so a crash mid-run loses at most the in-flight trial:

  trials.csv   — flat, one row per trial, for Phase 11's pandas/SciPy work
  trials.jsonl — same data, one JSON object per line, easier to extend with
                 nested fields later without breaking the CSV schema

Resume works by reading trial_id values already present in trials.csv at
startup and skipping them in run_experiment.py's loop — so re-running the
same command after an interruption (crash, Ctrl-C, laptop sleep) continues
where it left off instead of re-running 300 already-good trials.
"""

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import config

FIELDNAMES = [
    "trial_id",
    "resilience_profile",
    "chaos_scenario",
    "trial_num",
    "started_at_utc",
    "ended_at_utc",
    "status",  # "ok" | "error"
    "error_message",
    "gatling_request_count",
    "gatling_ok_count",
    "gatling_ko_count",
    "gatling_error_rate",
    "gatling_p50_ms",
    "gatling_p95_ms",
    "gatling_p99_ms",
    "gatling_mean_response_ms",
    "gatling_mean_requests_per_sec",
    "prometheus_error_rate",
    "peak_process_cpu_usage",
    "peak_jvm_heap_used_bytes",
    "cb_recovery_time_seconds",
    "cb_was_open_during_trial",
    "gatling_report_dir",
]


@dataclass
class TrialRecord:
    trial_id: str
    resilience_profile: str
    chaos_scenario: str
    trial_num: int
    started_at_utc: str
    ended_at_utc: str
    status: str
    error_message: str = ""
    gatling_request_count: Optional[int] = None
    gatling_ok_count: Optional[int] = None
    gatling_ko_count: Optional[int] = None
    gatling_error_rate: Optional[float] = None
    gatling_p50_ms: Optional[float] = None
    gatling_p95_ms: Optional[float] = None
    gatling_p99_ms: Optional[float] = None
    gatling_mean_response_ms: Optional[float] = None
    gatling_mean_requests_per_sec: Optional[float] = None
    prometheus_error_rate: Optional[float] = None
    peak_process_cpu_usage: Optional[float] = None
    peak_jvm_heap_used_bytes: Optional[float] = None
    cb_recovery_time_seconds: Optional[float] = None
    cb_was_open_during_trial: Optional[bool] = None
    gatling_report_dir: str = ""


def trial_id_for(profile: str, scenario: str, trial_num: int) -> str:
    return f"{profile}__{scenario}__{trial_num:02d}"


def ensure_results_dir() -> None:
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def load_completed_trial_ids(csv_path: Path = None) -> set:
    """Reads trials.csv if it exists and returns the set of trial_ids
    already recorded with status == 'ok'. Trials that previously errored
    are NOT considered complete and will be retried."""
    csv_path = csv_path or config.RESULTS_CSV
    if not csv_path.exists():
        return set()
    completed = set()
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "ok":
                completed.add(row["trial_id"])
    return completed


def append_result(record: TrialRecord, csv_path: Path = None, jsonl_path: Path = None) -> None:
    """Writes to config.RESULTS_CSV/JSONL by default. --dry-run passes
    alternate paths (results/dryrun_trials.{csv,jsonl}) so synthetic loop
    validation data never mixes with real trial data."""
    csv_path = csv_path or config.RESULTS_CSV
    jsonl_path = jsonl_path or config.RESULTS_JSONL
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    is_new_file = not csv_path.exists()

    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new_file:
            writer.writeheader()
        writer.writerow(asdict(record))

    with open(jsonl_path, "a") as f:
        f.write(json.dumps(asdict(record)) + "\n")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
