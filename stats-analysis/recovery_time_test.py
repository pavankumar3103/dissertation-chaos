"""
Phase 11 — Step 5b: Circuit-breaker recovery time comparison.

Separate from the main per-cell design because only 3 of the 5 profiles
ever have the breaker open (none/bulkhead have no circuit breaker logic,
so n=0 for them here). Pooled across scenarios (not broken out per-scenario)
because per-scenario n would be too small (e.g. only 3 'retry' trials total
across ALL scenarios combined) for a meaningful test.

Caveat carried forward from descriptive_stats.py: 'retry' has only n=3 here,
despite retry-only having no active circuit breaker per Phase 6 — this is
flagged, not hidden. Results involving 'retry' in this specific test should
be read with that small-n caveat attached.

Run: python3 recovery_time_test.py
"""
import pandas as pd
from scipy import stats
import scikit_posthocs as sp
from pathlib import Path

IN_CSV = Path(__file__).resolve().parent / "clean_trials.csv"
OUT_DIR = Path(__file__).resolve().parent / "outputs"
OUT_DIR.mkdir(exist_ok=True)
ALPHA = 0.05


def main():
    df = pd.read_csv(IN_CSV)
    cb_open = df[df["cb_was_open_during_trial"] == True].copy()  # noqa: E712

    counts = cb_open["resilience_profile"].value_counts()
    print("Trial counts (breaker actually opened):")
    print(counts.to_string())

    groups = [g["cb_recovery_time_seconds"].values for _, g in cb_open.groupby("resilience_profile", observed=True)]
    h_stat, p_value = stats.kruskal(*groups)
    print(f"\nKruskal-Wallis on cb_recovery_time_seconds across profiles: H={h_stat:.3f}, p={p_value:.5f}")
    print(f"Significant at alpha={ALPHA}: {p_value < ALPHA}")

    if p_value < ALPHA:
        dunn = sp.posthoc_dunn(cb_open, val_col="cb_recovery_time_seconds", group_col="resilience_profile", p_adjust="holm")
        print("\nDunn's post-hoc (Holm-adjusted p-values):")
        print(dunn.round(5).to_string())
        dunn.to_csv(OUT_DIR / "recovery_time_posthoc.csv")

    summary = {
        "h_stat": h_stat, "p_value": p_value, "significant": p_value < ALPHA,
        "n_retry": int(counts.get("retry", 0)),
        "n_circuit_breaker": int(counts.get("circuit-breaker", 0)),
        "n_combined": int(counts.get("combined", 0)),
        "caveat": "retry n=3 is very small; interpret any retry-involving pairwise result cautiously.",
    }
    pd.Series(summary).to_csv(OUT_DIR / "recovery_time_omnibus.csv")


if __name__ == "__main__":
    main()
