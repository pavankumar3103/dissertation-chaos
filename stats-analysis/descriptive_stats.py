"""
Phase 11 — Step 2: Descriptive statistics per (resilience_profile x chaos_scenario) cell.

Produces mean/median/std for the core outcome metrics across all 20 cells,
plus a separate recovery-time summary restricted to trials where the circuit
breaker actually opened (cb_was_open_during_trial == True) — recovery time is
meaningless for trials where the breaker never tripped (it's a near-zero
noise-floor value there, not a real "recovery").

Run: python3 descriptive_stats.py
"""
import pandas as pd
from pathlib import Path

IN_CSV = Path(__file__).resolve().parent / "clean_trials.csv"
OUT_DIR = Path(__file__).resolve().parent / "outputs"
OUT_DIR.mkdir(exist_ok=True)

CORE_METRICS = [
    "gatling_error_rate", "gatling_p99_ms", "gatling_mean_requests_per_sec",
    "peak_process_cpu_usage", "peak_jvm_heap_used_bytes",
]

PROFILE_ORDER = ["none", "retry", "bulkhead", "circuit-breaker", "combined"]
SCENARIO_ORDER = ["service_termination", "latency_injection", "partial_failure", "cascading_failure"]


def main():
    df = pd.read_csv(IN_CSV)
    df["resilience_profile"] = pd.Categorical(df["resilience_profile"], categories=PROFILE_ORDER, ordered=True)
    df["chaos_scenario"] = pd.Categorical(df["chaos_scenario"], categories=SCENARIO_ORDER, ordered=True)

    summary = (
        df.groupby(["chaos_scenario", "resilience_profile"], observed=True)[CORE_METRICS]
        .agg(["mean", "median", "std"])
        .round(4)
    )
    summary.to_csv(OUT_DIR / "descriptive_stats_by_cell.csv")
    print("=== Descriptive stats per cell (mean/median/std) ===")
    print(summary.to_string())

    # Recovery time: only meaningful when the breaker actually opened
    cb_open = df[df["cb_was_open_during_trial"] == True]  # noqa: E712
    recovery_summary = (
        cb_open.groupby("resilience_profile", observed=True)["cb_recovery_time_seconds"]
        .agg(["count", "mean", "median", "std", "min", "max"])
        .round(3)
    )
    recovery_summary.to_csv(OUT_DIR / "cb_recovery_time_summary.csv")
    print("\n=== Circuit-breaker recovery time (only trials where CB actually opened, n=45 total) ===")
    print(recovery_summary.to_string())
    print(f"\nNote: 'retry' profile shows {len(cb_open[cb_open['resilience_profile']=='retry'])} trials "
          f"with cb_was_open_during_trial=True despite retry-only having no active circuit breaker logic "
          f"per Phase 6 — flagged as a caveat, not filtered out silently.")


if __name__ == "__main__":
    main()
