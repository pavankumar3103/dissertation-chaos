"""
Phase 11 — Step 1: Load and clean the 400-trial experiment dataset.

Reads experiment-runner/results/trials.csv, keeps only status=="ok" rows,
validates the 5 (profile) x 4 (scenario) x 20 (trial) balanced design, and
writes a cleaned copy to stats-analysis/clean_trials.csv for all downstream
analysis steps to use as the single source of truth.

Run: python3 load_data.py
"""
import pandas as pd
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = REPO_ROOT / "experiment-runner" / "results" / "trials.csv"
OUT_CSV = Path(__file__).resolve().parent / "clean_trials.csv"

PROFILES = ["none", "retry", "bulkhead", "circuit-breaker", "combined"]
SCENARIOS = ["service_termination", "latency_injection", "partial_failure", "cascading_failure"]

NUMERIC_COLS = [
    "gatling_request_count", "gatling_ok_count", "gatling_ko_count",
    "gatling_error_rate", "gatling_p50_ms", "gatling_p95_ms", "gatling_p99_ms",
    "gatling_mean_response_ms", "gatling_mean_requests_per_sec",
    "prometheus_error_rate", "peak_process_cpu_usage", "peak_jvm_heap_used_bytes",
    "cb_recovery_time_seconds",
]


def load_and_clean() -> pd.DataFrame:
    df = pd.read_csv(RAW_CSV)
    total_rows = len(df)

    df_ok = df[df["status"] == "ok"].copy()
    dropped = total_rows - len(df_ok)

    for col in NUMERIC_COLS:
        df_ok[col] = pd.to_numeric(df_ok[col], errors="coerce")

    df_ok["cb_was_open_during_trial"] = df_ok["cb_was_open_during_trial"].astype(str).str.lower().map(
        {"true": True, "false": False}
    )

    # Validate balanced design
    counts = df_ok.groupby(["resilience_profile", "chaos_scenario"]).size()
    expected_cells = len(PROFILES) * len(SCENARIOS)
    unbalanced = counts[counts != 20]

    dupes = df_ok["trial_id"].duplicated().sum()

    print(f"Raw rows: {total_rows}")
    print(f"Dropped (status != ok): {dropped}")
    print(f"Clean rows: {len(df_ok)}")
    print(f"Expected cells: {expected_cells}, found cells: {len(counts)}")
    print(f"Cells not exactly 20 trials: {len(unbalanced)}")
    if len(unbalanced):
        print(unbalanced)
    print(f"Duplicate trial_ids: {dupes}")

    missing_summary = df_ok[NUMERIC_COLS].isna().sum()
    print("\nMissing value counts per column:")
    print(missing_summary.to_string())

    assert len(df_ok) == 400, f"Expected 400 clean trials, got {len(df_ok)}"
    assert dupes == 0, "Duplicate trial_ids found — investigate before analysis"
    assert len(unbalanced) == 0, "Design is not balanced — investigate before analysis"

    df_ok.to_csv(OUT_CSV, index=False)
    print(f"\nWrote cleaned dataset to {OUT_CSV}")
    return df_ok


if __name__ == "__main__":
    load_and_clean()
