"""
Phase 11 — Step 5: Post-hoc pairwise comparisons (Dunn's test, Holm correction)
for every scenario x metric combination where the Kruskal-Wallis omnibus test
was significant (19 of 19 testable combinations, per Step 4).

Dunn's test is the standard non-parametric post-hoc for Kruskal-Wallis
(analogous to Tukey HSD for ANOVA). Holm's method controls the family-wise
error rate across the 10 pairwise comparisons per scenario x metric block
(5 profiles -> C(5,2) = 10 pairs).

Run: python3 posthoc_tests.py
"""
import pandas as pd
import scikit_posthocs as sp
from pathlib import Path

IN_CSV = Path(__file__).resolve().parent / "clean_trials.csv"
OMNIBUS_CSV = Path(__file__).resolve().parent / "outputs" / "omnibus_test_results.csv"
OUT_DIR = Path(__file__).resolve().parent / "outputs"
OUT_DIR.mkdir(exist_ok=True)

ALPHA = 0.05


def main():
    df = pd.read_csv(IN_CSV)
    omnibus = pd.read_csv(OMNIBUS_CSV)
    sig_combos = omnibus[omnibus["significant"] == True]  # noqa: E712

    all_results = []
    for _, row in sig_combos.iterrows():
        scenario, metric = row["scenario"], row["metric"]
        sub = df[df["chaos_scenario"] == scenario]

        dunn = sp.posthoc_dunn(sub, val_col=metric, group_col="resilience_profile", p_adjust="holm")

        # Flatten upper triangle into long form
        profiles = dunn.columns.tolist()
        for i, p1 in enumerate(profiles):
            for p2 in profiles[i + 1:]:
                p_val = dunn.loc[p1, p2]
                all_results.append({
                    "scenario": scenario, "metric": metric,
                    "profile_a": p1, "profile_b": p2,
                    "p_adj_holm": round(p_val, 5),
                    "significant": p_val < ALPHA,
                })

    result_df = pd.DataFrame(all_results)
    result_df.to_csv(OUT_DIR / "posthoc_dunn_results.csv", index=False)

    print(f"Total pairwise comparisons: {len(result_df)}")
    print(f"Significant pairwise differences (p_adj < {ALPHA}): {result_df['significant'].sum()}")
    print("\nSample of results:")
    print(result_df.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
