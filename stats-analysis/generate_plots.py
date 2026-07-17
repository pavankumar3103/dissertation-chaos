"""
Phase 11 — Step 6: Generate boxplots (profile x scenario) for each core metric,
plus a recovery-time boxplot, for use in the dissertation results chapter.

Run: python3 generate_plots.py
"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

IN_CSV = Path(__file__).resolve().parent / "clean_trials.csv"
OUT_DIR = Path(__file__).resolve().parent / "outputs" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROFILE_ORDER = ["none", "retry", "bulkhead", "circuit-breaker", "combined"]
SCENARIO_ORDER = ["service_termination", "latency_injection", "partial_failure", "cascading_failure"]

METRIC_LABELS = {
    "gatling_error_rate": "Error Rate",
    "gatling_p99_ms": "p99 Latency (ms)",
    "gatling_mean_requests_per_sec": "Mean Throughput (req/s)",
    "peak_process_cpu_usage": "Peak CPU Usage",
    "peak_jvm_heap_used_bytes": "Peak JVM Heap (bytes)",
}


def main():
    df = pd.read_csv(IN_CSV)
    df["resilience_profile"] = pd.Categorical(df["resilience_profile"], categories=PROFILE_ORDER, ordered=True)
    df["chaos_scenario"] = pd.Categorical(df["chaos_scenario"], categories=SCENARIO_ORDER, ordered=True)

    sns.set_theme(style="whitegrid")

    for metric, label in METRIC_LABELS.items():
        g = sns.catplot(
            data=df, x="resilience_profile", y=metric, col="chaos_scenario",
            kind="box", col_wrap=2, height=4, aspect=1.3, order=PROFILE_ORDER,
        )
        g.set_axis_labels("Resilience Profile", label)
        g.set_titles("{col_name}")
        for ax in g.axes.flat:
            ax.tick_params(axis="x", rotation=30)
        g.fig.suptitle(f"{label} by Resilience Profile and Chaos Scenario", y=1.02)
        out_path = OUT_DIR / f"{metric}_by_profile_scenario.png"
        g.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(g.fig)
        print(f"Saved {out_path}")

    # Recovery time (only trials where breaker opened)
    cb_open = df[df["cb_was_open_during_trial"] == True]  # noqa: E712
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.boxplot(data=cb_open, x="resilience_profile", y="cb_recovery_time_seconds",
                order=["retry", "circuit-breaker", "combined"], ax=ax)
    sns.stripplot(data=cb_open, x="resilience_profile", y="cb_recovery_time_seconds",
                  order=["retry", "circuit-breaker", "combined"], color="black", alpha=0.5, ax=ax)
    ax.set_title("Circuit-Breaker Recovery Time (trials where breaker actually opened)")
    ax.set_xlabel("Resilience Profile")
    ax.set_ylabel("Recovery Time (s)")
    out_path = OUT_DIR / "cb_recovery_time.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
