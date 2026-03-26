"""
09_analyze_revision_depth.py -- Analyse results from the revision-depth ablation.

Reads summary.csv from 08_revision_depth_experiment.py and ground_truth, then
computes classification metrics (accuracy, precision, recall, F1) per depth
and per trap group.  Prints a comparison table and optionally logs to MLflow.

Usage:
    python 09_analyze_revision_depth.py                            # gpt-4o-mini, run 1
    python 09_analyze_revision_depth.py --model gpt-4o-mini --run-id 1
    python 09_analyze_revision_depth.py --no-mlflow               # skip MLflow logging
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

load_dotenv()

BASE_RESULTS_DIR = Path("results") / "revision_depth"
GROUND_TRUTH_FILE = Path("test_ground_truth.csv")
GUILTY_THRESHOLD = 50  # score >= 50 → predicted guilty

# Ground-truth group → display label
GROUP_LABELS = {
    "A": "Control Guilty",
    "B": "Control Innocent",
    "C1": "FP: Charity",
    "C2": "FP: Payroll",
    "C3": "FP: High Roller",
    "C4": "FP: Structurer",
    "D1": "FN: Sleeper",
    "D2": "FN: Smurf",
}


def _depth_col(n: int, suffix: str) -> str:
    return f"d{n}_{suffix}"


def _classify(scores: pd.Series) -> pd.Series:
    return (scores >= GUILTY_THRESHOLD).astype(int)


def _metrics(y_true, y_pred) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    n = len(y_true)
    return {
        "accuracy": (tp + tn) / n,
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse revision-depth ablation results."
    )
    parser.add_argument(
        "--model",
        default=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        help="Model used in 08_revision_depth_experiment.py (default: gpt-4o-mini).",
    )
    parser.add_argument(
        "--run-id",
        default="1",
        help="Run ID used in 08_revision_depth_experiment.py (default: 1).",
    )
    parser.add_argument(
        "--no-mlflow",
        action="store_true",
        help="Skip MLflow logging.",
    )
    args = parser.parse_args()

    model = args.model
    run_id = args.run_id

    results_dir = BASE_RESULTS_DIR / model / f"run_{run_id}"
    summary_file = results_dir / "summary.csv"

    if not summary_file.exists():
        print(f"ERROR: {summary_file} not found. Run 08_revision_depth_experiment.py first.")
        return

    if not GROUND_TRUTH_FILE.exists():
        print(f"ERROR: {GROUND_TRUTH_FILE} not found.")
        return

    summary = pd.read_csv(summary_file)
    gt = pd.read_csv(GROUND_TRUTH_FILE)[["client_id", "group", "is_money_laundering"]]
    df = summary.merge(gt, on="client_id", how="inner")

    # Detect which depths are present
    depths = sorted(
        int(col.split("_")[0][1:])
        for col in df.columns
        if col.startswith("d") and col.endswith("_score")
        and not any(c in col for c in ["initial", "rev"])
    )

    if not depths:
        print("No depth columns found in summary.csv.")
        return

    y_true = df["is_money_laundering"].values

    # ── Overall metrics table ──────────────────────────────────────────────
    rows = []
    for n in depths:
        score_col = _depth_col(n, "score")
        if score_col not in df.columns:
            continue
        valid = df.dropna(subset=[score_col])
        y_pred = _classify(valid[score_col]).values
        y_t = valid["is_money_laundering"].values
        m = _metrics(y_t, y_pred)

        review_col = _depth_col(n, "review_decision")
        rev_col = _depth_col(n, "revision_count")
        consensus = (valid[review_col] == "APPROVE").mean() if review_col in valid.columns else float("nan")
        avg_rev = valid[rev_col].mean() if rev_col in valid.columns else float("nan")

        rows.append({
            "depth": n,
            "n": len(valid),
            **m,
            "consensus_rate": consensus,
            "avg_revisions": avg_rev,
        })

    overall = pd.DataFrame(rows)

    print(f"\n{'='*72}")
    print(f"Revision Depth Ablation — {model} — run {run_id}")
    print(f"{'='*72}")
    print(f"\n{'Depth':<7} {'Acc':>6} {'Prec':>6} {'Rec':>6} {'F1':>6} "
          f"{'TP':>4} {'FP':>4} {'TN':>4} {'FN':>4} "
          f"{'Consensus':>10} {'AvgRev':>8}")
    print("-" * 72)
    for _, r in overall.iterrows():
        print(
            f"  {int(r['depth']):<5} "
            f"{r['accuracy']:>6.1%} "
            f"{r['precision']:>6.3f} "
            f"{r['recall']:>6.3f} "
            f"{r['f1']:>6.3f} "
            f"{int(r['tp']):>4} {int(r['fp']):>4} {int(r['tn']):>4} {int(r['fn']):>4} "
            f"{r['consensus_rate']:>10.0%} "
            f"{r['avg_revisions']:>8.2f}"
        )

    # Highlight best F1
    best_depth = overall.loc[overall["f1"].idxmax(), "depth"]
    print(f"\n  Best F1 at depth={int(best_depth)}")

    # ── Per-group accuracy table ───────────────────────────────────────────
    print(f"\n{'Per-group accuracy by depth':}")
    print(f"\n{'Group':<22}", end="")
    for n in depths:
        print(f"  d={n:<2}", end="")
    print()
    print("-" * (22 + 6 * len(depths)))

    group_rows = {}
    for group, label in GROUP_LABELS.items():
        gdf = df[df["group"] == group]
        if gdf.empty:
            continue
        accs = []
        for n in depths:
            score_col = _depth_col(n, "score")
            if score_col not in gdf.columns:
                accs.append(float("nan"))
                continue
            valid = gdf.dropna(subset=[score_col])
            if valid.empty:
                accs.append(float("nan"))
                continue
            y_pred = _classify(valid[score_col]).values
            y_t = valid["is_money_laundering"].values
            accs.append((y_pred == y_t).mean())
        group_rows[label] = accs
        print(f"  {label:<20}", end="")
        for acc in accs:
            print(f"  {acc:>4.0%}" if not np.isnan(acc) else "    --", end="")
        print()

    # ── Score trajectory (avg score per depth) ────────────────────────────
    print(f"\n{'Avg final score by depth (all clients)':}")
    print(f"\n{'Depth':<7} {'Guilty (true)':>14} {'Innocent (true)':>16}")
    print("-" * 40)
    for n in depths:
        score_col = _depth_col(n, "score")
        if score_col not in df.columns:
            continue
        valid = df.dropna(subset=[score_col])
        guilty_scores = valid[valid["is_money_laundering"] == 1][score_col].mean()
        innocent_scores = valid[valid["is_money_laundering"] == 0][score_col].mean()
        print(f"  {n:<5}  {guilty_scores:>14.1f}  {innocent_scores:>16.1f}")

    # ── Save evaluation CSV ───────────────────────────────────────────────
    eval_file = results_dir / "evaluation.csv"
    overall.to_csv(eval_file, index=False)
    print(f"\nEvaluation saved: {eval_file}")

    # ── MLflow logging ─────────────────────────────────────────────────────
    if args.no_mlflow:
        return

    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("aml-governance-revision-depth")

    with mlflow.start_run(run_name=f"{model}_r{run_id}_revision_depth"):
        mlflow.log_param("model", model)
        mlflow.log_param("run_id", run_id)
        mlflow.log_param("depths_tested", str(depths))
        mlflow.log_param("n_clients", len(df))

        for _, r in overall.iterrows():
            n = int(r["depth"])
            mlflow.log_metric(f"d{n}_accuracy", r["accuracy"], step=n)
            mlflow.log_metric(f"d{n}_f1", r["f1"], step=n)
            mlflow.log_metric(f"d{n}_precision", r["precision"], step=n)
            mlflow.log_metric(f"d{n}_recall", r["recall"], step=n)
            mlflow.log_metric(f"d{n}_consensus_rate", r["consensus_rate"], step=n)
            mlflow.log_metric(f"d{n}_avg_revisions", r["avg_revisions"], step=n)
            mlflow.log_metric(f"d{n}_fp", r["fp"], step=n)
            mlflow.log_metric(f"d{n}_fn", r["fn"], step=n)

        mlflow.log_artifact(str(eval_file))
        print(f"MLflow run logged: aml-governance-revision-depth / {model}_r{run_id}_revision_depth")


if __name__ == "__main__":
    main()
