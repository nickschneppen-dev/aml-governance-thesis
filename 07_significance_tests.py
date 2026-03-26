"""
07_significance_tests.py — Statistical significance tests for governance mode comparison.

Three tests:
  1. Cochran's Q      — omnibus test: are any of the 4 modes different?
  2. McNemar's        — pairwise tests with Bonferroni correction
  3. Bootstrap CIs    — 95% confidence intervals on F1 per mode

Usage:
    python 07_significance_tests.py                          # gpt-4o-mini, run_1
    python 07_significance_tests.py --model gpt-4o-mini --run-id 1
    python 07_significance_tests.py --model gpt-5.1 --run-id 1
"""

import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# ── Constants ────────────────────────────────────────────────────────────────

BASE_RESULTS_DIR = Path("results")
THRESHOLD = 0.05
N_BOOTSTRAP = 10_000
RNG_SEED = 42

MODE_LABELS = {
    "int": "Intrinsic",
    "hier": "Hierarchical",
    "ctx": "Context-Eng",
    "llm": "LLM-Context",
}

# ── Helpers ──────────────────────────────────────────────────────────────────


def load_evaluation(model: str, run_id: str) -> pd.DataFrame:
    path = BASE_RESULTS_DIR / "test" / model / f"run_{run_id}" / "evaluation.csv"
    if not path.exists():
        raise FileNotFoundError(f"Evaluation file not found: {path}")
    return pd.read_csv(path)


def correct_cols(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Return {prefix: binary_correct_array} for all modes present."""
    return {
        prefix: df[f"{prefix}_correct"].values.astype(int)
        for prefix in MODE_LABELS
        if f"{prefix}_correct" in df.columns
    }


# ── Test 1: Cochran's Q ──────────────────────────────────────────────────────


def cochrans_q(correct: dict[str, np.ndarray]) -> tuple[float, float]:
    """
    Cochran's Q test across k binary classifiers on the same n subjects.

    Q = (k-1) * [k*sum(Cj^2) - T^2] / [k*T - sum(Ri^2)]

    where:
        k  = number of modes
        n  = number of subjects
        Cj = column sum for mode j (number correct)
        Ri = row sum for subject i (number of modes correct for that subject)
        T  = grand total of correct classifications
    """
    matrix = np.column_stack(list(correct.values()))  # shape (n, k)
    n, k = matrix.shape

    row_sums = matrix.sum(axis=1)   # Ri
    col_sums = matrix.sum(axis=0)   # Cj
    T = matrix.sum()                # grand total

    numerator = (k - 1) * (k * np.sum(col_sums**2) - T**2)
    denominator = k * T - np.sum(row_sums**2)

    if denominator == 0:
        return 0.0, 1.0

    Q = numerator / denominator
    p = 1 - stats.chi2.cdf(Q, df=k - 1)
    return float(Q), float(p)


# ── Test 2: McNemar's (pairwise + Bonferroni) ────────────────────────────────


def mcnemars_test(a: np.ndarray, b: np.ndarray) -> tuple[float, float, int, int]:
    """
    McNemar's test with Yates' continuity correction.
    Returns (chi2, p_value, b_count, c_count).

    b = cases where A correct, B wrong
    c = cases where A wrong,  B correct
    """
    b_count = int(np.sum((a == 1) & (b == 0)))
    c_count = int(np.sum((a == 0) & (b == 1)))
    n_discordant = b_count + c_count

    if n_discordant == 0:
        return 0.0, 1.0, b_count, c_count

    chi2 = (abs(b_count - c_count) - 1) ** 2 / n_discordant
    p = 1 - stats.chi2.cdf(chi2, df=1)
    return float(chi2), float(p), b_count, c_count


def pairwise_mcnemar(correct: dict[str, np.ndarray]) -> pd.DataFrame:
    """Run all pairwise McNemar's tests with Bonferroni correction."""
    prefixes = list(correct.keys())
    pairs = list(itertools.combinations(prefixes, 2))
    n_comparisons = len(pairs)

    rows = []
    for p1, p2 in pairs:
        chi2, p_raw, b, c = mcnemars_test(correct[p1], correct[p2])
        p_bonf = min(p_raw * n_comparisons, 1.0)
        rows.append({
            "Mode A":          MODE_LABELS[p1],
            "Mode B":          MODE_LABELS[p2],
            "b (A+ B-)":       b,
            "c (A- B+)":       c,
            "chi2":            round(chi2, 3),
            "p (raw)":         round(p_raw, 4),
            "p (Bonferroni)":  round(p_bonf, 4),
            "Significant":     "Yes" if p_bonf < THRESHOLD else "No",
        })

    return pd.DataFrame(rows)


# ── Test 3: Bootstrap CIs on F1 and Accuracy ─────────────────────────────────


def compute_f1(predicted_guilty: np.ndarray, is_ml: np.ndarray) -> float:
    tp = int(np.sum((predicted_guilty == 1) & (is_ml == 1)))
    fp = int(np.sum((predicted_guilty == 1) & (is_ml == 0)))
    fn = int(np.sum((predicted_guilty == 0) & (is_ml == 1)))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def bootstrap_ci(values: np.ndarray, stat_fn, n_bootstrap: int = N_BOOTSTRAP, seed: int = RNG_SEED):
    """Generic bootstrap CI. stat_fn takes an index array and returns a scalar."""
    rng = np.random.default_rng(seed)
    n = len(values)
    point = stat_fn(np.arange(n))
    boot_stats = [stat_fn(rng.integers(0, n, size=n)) for _ in range(n_bootstrap)]
    return point, float(np.percentile(boot_stats, 2.5)), float(np.percentile(boot_stats, 97.5))


def bootstrap_ci_table(df: pd.DataFrame, correct: dict[str, np.ndarray]) -> pd.DataFrame:
    is_ml = df["is_money_laundering"].values.astype(int)
    rows = []
    for prefix, label in MODE_LABELS.items():
        if prefix not in correct:
            continue
        corr = correct[prefix]
        pg   = df[f"{prefix}_predicted_guilty"].values.astype(int)

        acc, acc_lo, acc_hi = bootstrap_ci(corr,  lambda idx: corr[idx].mean())
        f1,  f1_lo,  f1_hi  = bootstrap_ci(pg,    lambda idx: compute_f1(pg[idx], is_ml[idx]))

        rows.append({
            "Mode":        label,
            "Accuracy":    f"{acc:.3f}",
            "Acc 95% CI":  f"[{acc_lo:.3f} - {acc_hi:.3f}]",
            "F1":          f"{f1:.3f}",
            "F1 95% CI":   f"[{f1_lo:.3f} - {f1_hi:.3f}]",
        })
    return pd.DataFrame(rows)


# ── Printing ─────────────────────────────────────────────────────────────────


def print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Statistical significance tests for AML governance modes.")
    parser.add_argument("--model",  default="gpt-4o-mini", help="Model name (default: gpt-4o-mini)")
    parser.add_argument("--run-id", default="1",           help="Run ID (default: 1)")
    args = parser.parse_args()

    df = load_evaluation(args.model, args.run_id)
    correct = correct_cols(df)
    n_modes = len(correct)
    n_pairs = n_modes * (n_modes - 1) // 2

    print(f"\nModel: {args.model}  |  Run: {args.run_id}  |  n={len(df)}  |  Bootstrap iterations: {N_BOOTSTRAP:,}")

    # ── Step 1: Cochran's Q ──────────────────────────────────────────────────
    print_section("STEP 1: Cochran's Q (omnibus test)")
    Q, p_q = cochrans_q(correct)
    sig = "SIGNIFICANT" if p_q < THRESHOLD else "not significant"
    print(f"  Q = {Q:.3f},  df = {n_modes - 1},  p = {p_q:.4f}  ->  {sig} (a=0.05)")
    if p_q < THRESHOLD:
        print("  [PASS] At least one mode differs significantly. Proceeding to pairwise tests.")
    else:
        print("  No significant difference detected across modes.")

    # ── Step 2: Pairwise McNemar's ───────────────────────────────────────────
    print_section(f"STEP 2: Pairwise McNemar's Tests (Bonferroni x{n_pairs})")
    mcnemar_df = pairwise_mcnemar(correct)
    print(mcnemar_df.to_string(index=False))
    n_sig = (mcnemar_df["Significant"] == "Yes").sum()
    print(f"\n  {n_sig}/{n_pairs} pairs significant after Bonferroni correction.")

    # ── Step 3: Bootstrap CIs ────────────────────────────────────────────────
    print_section(f"STEP 3: Bootstrap Confidence Intervals (n={N_BOOTSTRAP:,} iterations)")
    ci_df = bootstrap_ci_table(df, correct)
    print(ci_df.to_string(index=False))

    # ── Save results ─────────────────────────────────────────────────────────
    out_dir = BASE_RESULTS_DIR / "test" / args.model / f"run_{args.run_id}"
    mcnemar_df.to_csv(out_dir / "significance_mcnemar.csv", index=False)
    ci_df.to_csv(out_dir / "significance_bootstrap_ci.csv", index=False)
    pd.DataFrame([{
        "model":                    args.model,
        "run_id":                   args.run_id,
        "n":                        len(df),
        "cochrans_Q":               round(Q, 3),
        "cochrans_p":               round(p_q, 4),
        "cochrans_significant":     p_q < THRESHOLD,
        "n_bonferroni_significant": int(n_sig),
        "n_pairs":                  n_pairs,
    }]).to_csv(out_dir / "significance_summary.csv", index=False)

    print(f"\n  Saved to {out_dir}/significance_*.csv")


if __name__ == "__main__":
    main()
