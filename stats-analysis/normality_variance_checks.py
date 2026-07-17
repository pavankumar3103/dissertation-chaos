"""
Phase 11 — Step 3: Normality (Shapiro-Wilk) and equal-variance (Levene's) checks
per (chaos_scenario x metric), across the 5 resilience_profile groups (n=20 each).

This decides, for each scenario x metric combination, whether a one-way ANOVA
is valid (normal + equal variance) or whether Kruskal-Wallis (rank-based,
no distributional assumptions) should be used instead. Constant columns
(zero variance — e.g. gatling_error_rate is exactly 1.0 for every trial
during service_termination, regardless of profile) are flagged and skipped,
since there is nothing to test: all groups are identical by definition.

Run: python3 normality_variance_checks.py
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
            groups = [g[metric].values for _, g in sub.groupby("resilience_profile", observed=True)]

            # Constant-value check (zero variance overall -> nothing to test)
            overall_std = sub[metric].std()
            if overall_std == 0 or pd.isna(overall_std):
                rows.append({
                    "scenario": scenario, "metric": metric,
                    "shapiro_all_normal": None, "levene_p": None,
                    "equal_variance": None, "recommended_test": "NONE (constant value across all groups)",
                })
                continue

            shapiro_results = []
            for g in groups:
                if len(set(g)) == 1:
                    shapiro_results.append(True)  # constant within group -> treat as degenerate, not "non-normal"
                    continue
                _, p = stats.shapiro(g)
                shapiro_results.append(p > ALPHA)
            all_normal = all(shapiro_results)

            levene_stat, levene_p = stats.levene(*groups)
            equal_var = levene_p > ALPHA

            if all_normal and equal_var:
                rec = "ANOVA"
            else:
                rec = "Kruskal-Wallis"

            rows.append({
                "scenario": scenario, "metric": metric,
                "shapiro_all_normal": all_normal, "levene_p": round(levene_p, 4),
                "equal_variance": equal_var, "recommended_test": rec,
            })

    result_df = pd.DataFrame(rows)
    result_df.to_csv(OUT_DIR / "normality_variance_checks.csv", index=False)
    print(result_df.to_string(index=False))


if __name__ == "__main__":
    main()
