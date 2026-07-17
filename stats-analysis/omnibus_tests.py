"""
Phase 11 — Step 4: Omnibus test (Kruskal-Wallis) per (chaos_scenario x metric),
testing whether resilience_profile has a significant effect on the outcome.

Per Step 3's normality/variance checks, every non-constant metric x scenario
combination failed the normality assumption (data is skewed/bounded, as
expected for latency and error-rate metrics), so Kruskal-Wallis is used
uniformly rather than ANOVA for consistency, even where variances were
roughly equal. The one constant case (gatling_error_rate during
service_termination = 1.0 for every trial, every profile) is reported as-is
with no test run, since there is no variance to explain.

Run: python3 omnibus_tests.py
"""
import pandas as pd
from scipy import stats
from pathlib import Path

IN_CSV = Path(__file__).resolve().parent / "clean_trials.csv"
OUT_DIR = Path(__file__).resolve().parent / "outputs"
OUT_DIR.mkdir(exist_ok=True)

CORE_METRICS = [
    "gatling_error_rate", "gatling_p99_ms", "gatling_mean_requests_per_sec",
    "peak_process_cpu_usage", "peak_jvm_heap_used_bytes",
]
SCENARIOS = ["service_termination", "latency_injection", "partial_failure", "cascading_failure"]
ALPHA = 0.05


def main():
    df = pd.read_csv(IN_CSV)
    rows = []

    for scenario in SCENARIOS:
        sub = df[df["chaos_scenario"] == scenario]
        for metric in CORE_METRICS:
            overall_std = sub[metric].std()
            if overall_std == 0 or pd.isna(overall_std):
                rows.append({
                    "scenario": scenario, "metric": metric,
                    "test": "none (constant)", "H_stat": None, "p_value": None,
                    "significant": None,
                    "note": "Every trial had the same value regardless of profile — no effect to test.",
                })
                continue

            groups = [g[metric].values for _, g in sub.groupby("resilience_profile", observed=True)]
            h_stat, p_value = stats.kruskal(*groups)
            rows.append({
                "scenario": scenario, "metric": metric,
                "test": "Kruskal-Wallis", "H_stat": round(h_stat, 3), "p_value": p_value,
                "significant": p_value < ALPHA,
                "note": "",
            })

    result_df = pd.DataFrame(rows)
    result_df.to_csv(OUT_DIR / "omnibus_test_results.csv", index=False)
    pd.set_option("display.max_colwidth", 60)
    print(result_df.to_string(index=False))

    n_sig = result_df["significant"].sum()
    n_testable = result_df["significant"].notna().sum()
    print(f"\n{n_sig} of {n_testable} testable scenario x metric combinations show a "
          f"significant profile effect (p < {ALPHA}).")


if __name__ == "__main__":
    main()
