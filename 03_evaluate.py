"""
03_evaluate.py -- Evaluate experiment results and log to MLflow.

Loads the experiment results (summary.csv + per-client JSONs), computes
quantitative metrics in Python, and logs everything to MLflow for
side-by-side comparison between governance modes.

Three levels of evaluation:
  Level 1 -- Score Accuracy:  range accuracy, MAE
  Level 2 -- Classification:  precision, recall, F1 (binary: guilty/innocent)
  Level 3 -- Per-Group:       breakdown by trap type (the thesis question)
  Bonus   -- Reasoning Quality: LLM-judged evidence coverage via mlflow.evaluate()

Usage:
    python 03_evaluate.py                # evaluate latest results
    python 03_evaluate.py --run-name v1  # custom run name prefix

MLflow UI (after running):
    mlflow ui
    # Open http://localhost:5000
    # Select experiment "aml-governance"
    # Tick both runs (intrinsic + hierarchical) -> click "Compare"
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import mlflow
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CLASSIFICATION_THRESHOLD = 50  # score >= 50 → predict guilty
EXPERIMENT_NAME = "aml-governance"

MODES = ["int", "hier", "ctx"]
MODE_LABELS = {
    "int": "intrinsic",
    "hier": "hierarchical",
    "ctx": "context_engineered",
}

# Display-friendly group ordering
GROUP_ORDER = [
    "control_guilty",
    "control_innocent",
    "fp_trap:charity",
    "fp_trap:payroll",
    "fp_trap:high_roller",
    "fp_trap:structurer",
    "fn_trap:sleeper",
    "fn_trap:smurf",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_and_merge(summary_file: Path, ground_truth_file: Path) -> pd.DataFrame:
    """Load summary.csv and ground_truth.csv, merge on client_id."""
    summary = pd.read_csv(summary_file)
    # Drop duplicate rows produced when a failed client is re-run on resume.
    # The last row for each client_id is the successful one.
    summary = summary.drop_duplicates(subset="client_id", keep="last")
    ground_truth = pd.read_csv(ground_truth_file)

    # Normalise is_money_laundering to int (0/1)
    ground_truth["is_money_laundering"] = (
        ground_truth["is_money_laundering"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map({"true": 1, "1": 1, "false": 0, "0": 0})
    )

    merged = summary.merge(ground_truth, on="client_id", how="inner")

    # Create a combined group label for per-group analysis
    merged["group_label"] = merged.apply(
        lambda r: f"{r['group']}:{r['trap_subtype']}"
        if pd.notna(r["trap_subtype"]) and r["trap_subtype"] != ""
        else r["group"],
        axis=1,
    )

    return merged


def load_reasoning(results_dir: Path, mode: str) -> dict[str, str]:
    """Load final_output.reasoning from per-client JSON files.

    Returns {client_id: reasoning_text}.
    """
    mode_dir = results_dir / MODE_LABELS[mode]
    reasoning = {}
    if not mode_dir.exists():
        return reasoning
    for path in mode_dir.glob("*.json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        final = data.get("final_output", {})
        if isinstance(final, dict) and "reasoning" in final:
            reasoning[path.stem] = final["reasoning"]
    return reasoning


# ---------------------------------------------------------------------------
# Metric computation (Python -- handles custom trap-group logic)
# ---------------------------------------------------------------------------
def compute_metrics(df: pd.DataFrame, prefix: str) -> dict:
    """Compute all metrics for one governance mode.

    Args:
        df: Merged DataFrame (summary + ground truth).
        prefix: Column prefix -- "int" or "hier".

    Returns:
        Dict of metric name -> value.
    """
    score_col = f"{prefix}_score"
    conf_col = f"{prefix}_confidence"
    review_col = f"{prefix}_review_decision"
    revision_col = f"{prefix}_revision_count"

    initial_col = f"{prefix}_initial_score"

    # Drop rows where this mode errored
    valid = df.dropna(subset=[score_col]).copy()
    valid[score_col] = valid[score_col].astype(float)
    if initial_col in valid.columns:
        valid[initial_col] = pd.to_numeric(valid[initial_col], errors="coerce")
    n = len(valid)

    if n == 0:
        return {"n": 0}

    # ── Level 1: Score accuracy ──
    in_range = (valid[score_col] >= valid["expected_risk_min"]) & (
        valid[score_col] <= valid["expected_risk_max"]
    )
    range_accuracy = in_range.mean()
    mae = (valid[score_col] - valid["expected_risk_min"]).clip(lower=0).mean()
    # MAE from midpoint of expected range
    midpoint = (valid["expected_risk_min"] + valid["expected_risk_max"]) / 2
    mae_midpoint = (valid[score_col] - midpoint).abs().mean()

    # ── Level 2: Binary classification ──
    predicted_guilty = valid[score_col] >= CLASSIFICATION_THRESHOLD
    actual_guilty = valid["is_money_laundering"] == 1

    tp = int((predicted_guilty & actual_guilty).sum())
    fp = int((predicted_guilty & ~actual_guilty).sum())
    tn = int((~predicted_guilty & ~actual_guilty).sum())
    fn = int((~predicted_guilty & actual_guilty).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    classification_accuracy = (tp + tn) / n

    # ── Behavioural ──
    rejection_rate = (valid[review_col] == "REJECT").mean()
    avg_revisions = valid[revision_col].mean()
    avg_confidence = valid[conf_col].mean() if conf_col in valid.columns else None
    # Consensus: governance loop reached APPROVE (reviewer signed off).
    # Cases that hit MAX_REVISIONS still with REJECT are unapproved outputs.
    consensus_rate = (valid[review_col] == "APPROVE").mean()
    # Cost proxy: both modes share 3 base LLM calls; each revision cycle adds 2.
    expected_llm_calls = 3.0 + 2.0 * avg_revisions
    # Score shift: how much the governance loop moved the score (final - initial).
    # Positive = escalated, negative = de-escalated, zero = unchanged.
    if initial_col in valid.columns:
        shifted = valid.dropna(subset=[initial_col])
        avg_score_shift = (shifted[score_col] - shifted[initial_col]).mean() if len(shifted) else None
    else:
        avg_score_shift = None

    metrics = {
        "n": n,
        "range_accuracy": range_accuracy,
        "mae_midpoint": mae_midpoint,
        "classification_accuracy": classification_accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "rejection_rate": rejection_rate,
        "avg_revisions": avg_revisions,
        "avg_confidence": avg_confidence,
        "consensus_rate": consensus_rate,
        "expected_llm_calls": expected_llm_calls,
        "avg_score_shift": avg_score_shift,
    }

    # ── Level 3: Per-group breakdown ──
    for group_label in valid["group_label"].unique():
        g = valid[valid["group_label"] == group_label]
        g_in_range = (g[score_col] >= g["expected_risk_min"]) & (
            g[score_col] <= g["expected_risk_max"]
        )
        g_pred_guilty = g[score_col] >= CLASSIFICATION_THRESHOLD
        g_actual_guilty = g["is_money_laundering"] == 1
        g_correct = (g_pred_guilty == g_actual_guilty).mean()

        safe_label = group_label.replace(":", "_")
        metrics[f"group/{safe_label}/range_accuracy"] = g_in_range.mean()
        metrics[f"group/{safe_label}/classification_accuracy"] = g_correct
        metrics[f"group/{safe_label}/avg_score"] = g[score_col].mean()
        metrics[f"group/{safe_label}/mae_midpoint"] = (
            (g[score_col] - (g["expected_risk_min"] + g["expected_risk_max"]) / 2)
            .abs()
            .mean()
        )
        metrics[f"group/{safe_label}/consensus_rate"] = (
            g[review_col] == "APPROVE"
        ).mean()
        metrics[f"group/{safe_label}/n"] = len(g)

    return metrics


def build_evaluation_df(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-client computed columns to the merged DataFrame."""
    out = df.copy()

    for prefix in MODES:
        score_col = f"{prefix}_score"
        initial_col = f"{prefix}_initial_score"
        if score_col not in out.columns:
            continue

        midpoint = (out["expected_risk_min"] + out["expected_risk_max"]) / 2

        # In range?
        out[f"{prefix}_in_range"] = (
            (out[score_col] >= out["expected_risk_min"])
            & (out[score_col] <= out["expected_risk_max"])
        ).astype(int)

        # Absolute error from midpoint
        out[f"{prefix}_abs_error"] = (out[score_col] - midpoint).abs()

        # Binary prediction
        out[f"{prefix}_predicted_guilty"] = (
            out[score_col] >= CLASSIFICATION_THRESHOLD
        ).astype(int)

        # Correct classification?
        out[f"{prefix}_correct"] = (
            out[f"{prefix}_predicted_guilty"] == out["is_money_laundering"]
        ).astype(int)

        # Did governance reach consensus (reviewer signed off with APPROVE)?
        review_col = f"{prefix}_review_decision"
        out[f"{prefix}_consensus_reached"] = (
            out[review_col] == "APPROVE"
        ).astype(int)

        # Score shift: how much the governance loop moved the score
        if initial_col in out.columns:
            out[f"{prefix}_score_shift"] = (
                pd.to_numeric(out[score_col], errors="coerce")
                - pd.to_numeric(out[initial_col], errors="coerce")
            )

    return out


# ---------------------------------------------------------------------------
# Reasoning quality evaluation (mlflow.evaluate with LLM judge)
# ---------------------------------------------------------------------------
REASONING_JUDGE_PROMPT = """\
You are an AML compliance expert evaluating the quality of a risk assessment's \
reasoning. You will receive:

1. The agent's reasoning text (the assessment to evaluate).
2. The ground truth context (what the correct assessment should reference).

## Scoring Criteria (1-5)

1 = Ignores key evidence, relies on assumptions or generic statements. \
Misses obvious red flags or exculpatory evidence entirely.

2 = References some data points but misses critical signals. For example, \
mentions transaction volume but ignores adverse news intelligence, or vice versa.

3 = Covers the main evidence from both quantitative metrics and qualitative \
news, but fails to address conflicting signals or does not weigh them \
against each other.

4 = Thorough coverage of both quantitative and qualitative evidence. \
Addresses conflicting signals and explains how they were weighed. \
Cites specific numbers and article claims.

5 = Comprehensive: cites specific metric values (e.g., "Fan-In=25"), \
quotes or paraphrases specific article claims, explicitly addresses \
ALL conflicts between quantitative and qualitative evidence, and \
clearly explains which evidence was decisive and why.

## Important

- A high score requires citing SPECIFIC data, not just saying "the data shows...".
- Addressing conflicting evidence is mandatory for scores above 3.
- For cases where quantitative data is clean but qualitative intelligence \
is adverse (or vice versa), the reasoning MUST acknowledge this tension.
"""


def evaluate_reasoning(
    df: pd.DataFrame, results_dir: Path, prefix: str, run_name: str
) -> None:
    """Run mlflow.evaluate() on reasoning text for one governance mode.

    Uses an LLM judge to score reasoning quality on a 1-5 scale.
    Results are logged as an MLflow evaluation artifact.
    """
    mode_label = MODE_LABELS[prefix]
    reasoning_map = load_reasoning(results_dir, prefix)

    if not reasoning_map:
        print(f"  No reasoning JSONs found for {mode_label}, skipping LLM evaluation.")
        return

    # Build evaluation DataFrame
    rows = []
    for _, row in df.iterrows():
        cid = row["client_id"]
        if cid not in reasoning_map:
            continue
        rows.append(
            {
                "client_id": cid,
                "inputs": reasoning_map[cid],
                "ground_truth": row["rationale"],
                "group_label": row["group_label"],
            }
        )

    if not rows:
        print(f"  No matched reasoning for {mode_label}, skipping LLM evaluation.")
        return

    eval_df = pd.DataFrame(rows)

    from mlflow.metrics.genai import make_genai_metric

    reasoning_quality = make_genai_metric(
        name="reasoning_quality",
        definition=(
            "Measures whether an AML risk assessment's reasoning "
            "demonstrates thorough evidence coverage, cites specific "
            "data points, and addresses conflicting signals."
        ),
        grading_prompt=REASONING_JUDGE_PROMPT,
        model=f"openai:/{os.getenv('LLM_MODEL', 'gpt-4o-mini')}",
        parameters={"temperature": 0},
        greater_is_better=True,
        aggregations=["mean", "min", "max"],
    )

    print(f"  Running LLM reasoning evaluation for {mode_label} "
          f"({len(eval_df)} clients)...")

    results = mlflow.evaluate(
        data=eval_df,
        predictions="inputs",
        targets="ground_truth",
        model_type=None,
        extra_metrics=[reasoning_quality],
        evaluators="default",
    )

    # Log aggregate reasoning metrics explicitly
    if results.metrics:
        for key, value in results.metrics.items():
            if "reasoning_quality" in key:
                mlflow.log_metric(key, value)

    print(f"  Reasoning evaluation logged for {mode_label}.")

    return results


# ---------------------------------------------------------------------------
# MLflow logging
# ---------------------------------------------------------------------------
def log_run(
    df: pd.DataFrame,
    eval_df: pd.DataFrame,
    results_dir: Path,
    prefix: str,
    metrics: dict,
    run_name: str,
) -> None:
    """Log one governance mode as an MLflow run."""
    mode_label = MODE_LABELS[prefix]
    full_run_name = f"{run_name}_{mode_label}" if run_name else mode_label

    with mlflow.start_run(run_name=full_run_name) as run:
        # ── Params ──
        mlflow.log_param("mode", mode_label)
        mlflow.log_param("model", os.getenv("LLM_MODEL", "gpt-4o"))
        mlflow.log_param("classification_threshold", CLASSIFICATION_THRESHOLD)
        mlflow.log_param("max_revisions", 2)
        mlflow.log_param("n_clients", metrics["n"])

        # ── Metrics (Level 1 + 2 + behavioural) ──
        for key, value in metrics.items():
            if key == "n":
                continue
            if value is not None and isinstance(value, (int, float)):
                mlflow.log_metric(key, value)

        # ── Artifacts ──
        # Save per-client evaluation for this mode
        mode_cols = [
            "client_id",
            "group_label",
            "is_money_laundering",
            "expected_risk_min",
            "expected_risk_max",
            f"{prefix}_initial_score",
            f"{prefix}_score",
            f"{prefix}_score_shift",
            f"{prefix}_confidence",
            f"{prefix}_review_decision",
            f"{prefix}_revision_count",
            f"{prefix}_in_range",
            f"{prefix}_abs_error",
            f"{prefix}_predicted_guilty",
            f"{prefix}_correct",
            f"{prefix}_consensus_reached",
        ]
        existing_cols = [c for c in mode_cols if c in eval_df.columns]
        mode_eval = eval_df[existing_cols].copy()

        artifact_path = results_dir / f"evaluation_{mode_label}.csv"
        mode_eval.to_csv(artifact_path, index=False)
        mlflow.log_artifact(str(artifact_path))

        # ── Reasoning quality (LLM judge) ──
        evaluate_reasoning(df, results_dir, prefix, run_name)

        print(f"  MLflow run logged: {full_run_name} (ID: {run.info.run_id})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate AML governance experiment results."
    )
    parser.add_argument(
        "--run-name",
        default="",
        help="Prefix for MLflow run names (e.g., 'v1' -> 'v1_intrinsic').",
    )
    parser.add_argument(
        "--dataset",
        choices=["train", "test"],
        default="test",
        help="Dataset split to evaluate (default: test). "
             "Reads results/{dataset}/ and {dataset}_ground_truth.csv.",
    )
    args = parser.parse_args()

    results_dir = Path("results") / args.dataset
    summary_file = results_dir / "summary.csv"
    ground_truth_file = Path(f"{args.dataset}_ground_truth.csv")
    evaluation_file = results_dir / "evaluation.csv"

    if not summary_file.exists():
        print(f"ERROR: {summary_file} not found. Run 02_run_experiment.py first.")
        return
    if not ground_truth_file.exists():
        print(f"ERROR: {ground_truth_file} not found. Run 01_build_dataset.py first.")
        return

    # ── Load data ──
    print("Loading results and ground truth...")
    df = load_and_merge(summary_file, ground_truth_file)
    print(f"  {len(df)} clients loaded.\n")

    # ── Compute metrics (skip modes with no data in summary.csv) ──
    all_metrics = {}
    active_modes = [p for p in MODES if f"{p}_score" in df.columns]
    if not active_modes:
        print("No mode results found in summary.csv. Check column names.")
        return

    for prefix in active_modes:
        mode_label = MODE_LABELS[prefix]
        metrics = compute_metrics(df, prefix)
        all_metrics[prefix] = metrics

        print(f"{'=' * 60}")
        print(f"  {mode_label.upper()} MODE")
        print(f"{'=' * 60}")
        print(f"  Range accuracy:          {metrics['range_accuracy']:.1%}")
        print(f"  MAE (from midpoint):     {metrics['mae_midpoint']:.1f}")
        print(f"  Classification accuracy: {metrics['classification_accuracy']:.1%}")
        print(f"  Precision:               {metrics['precision']:.2f}")
        print(f"  Recall:                  {metrics['recall']:.2f}")
        print(f"  F1:                      {metrics['f1']:.2f}")
        print(f"  Confusion: TP={metrics['tp']} FP={metrics['fp']} "
              f"TN={metrics['tn']} FN={metrics['fn']}")
        print(f"  Rejection rate:          {metrics['rejection_rate']:.1%}")
        print(f"  Consensus rate:          {metrics['consensus_rate']:.1%}")
        print(f"  Avg revisions:           {metrics['avg_revisions']:.2f}")
        print(f"  Expected LLM calls/case: {metrics['expected_llm_calls']:.1f}")
        if metrics.get("avg_score_shift") is not None:
            print(f"  Avg score shift:         {metrics['avg_score_shift']:+.1f} (final minus initial)")
        if metrics.get("avg_confidence") is not None:
            print(f"  Avg confidence:          {metrics['avg_confidence']:.1f}")

        # Per-group summary
        print(f"\n  Per-Group Breakdown:")
        print(f"  {'Group':<25} {'Range Acc':>10} {'Class Acc':>10} "
              f"{'Avg Score':>10} {'MAE':>8} {'Consensus':>10} {'n':>4}")
        print(f"  {'-' * 80}")
        for group_label in GROUP_ORDER:
            safe = group_label.replace(":", "_")
            key_prefix = f"group/{safe}"
            if f"{key_prefix}/n" not in metrics:
                continue
            consensus_key = f"{key_prefix}/consensus_rate"
            consensus_str = (
                f"{metrics[consensus_key]:>9.0%}"
                if consensus_key in metrics
                else f"{'N/A':>9}"
            )
            print(
                f"  {group_label:<25} "
                f"{metrics[f'{key_prefix}/range_accuracy']:>9.0%} "
                f"{metrics[f'{key_prefix}/classification_accuracy']:>9.0%} "
                f"{metrics[f'{key_prefix}/avg_score']:>10.1f} "
                f"{metrics[f'{key_prefix}/mae_midpoint']:>8.1f} "
                f"{consensus_str} "
                f"{metrics[f'{key_prefix}/n']:>4.0f}"
            )
        print()

    # ── Build detailed evaluation CSV ──
    eval_df = build_evaluation_df(df)
    eval_df.to_csv(evaluation_file, index=False)
    print(f"Detailed evaluation saved: {evaluation_file}")

    # ── Log to MLflow ──
    print(f"\nLogging to MLflow (experiment: '{EXPERIMENT_NAME}')...")
    mlflow.set_experiment(EXPERIMENT_NAME)

    for prefix in active_modes:
        log_run(df, eval_df, results_dir, prefix, all_metrics[prefix], args.run_name)

    print(f"\nDone. Run 'mlflow ui' and open http://localhost:5000 to compare runs.")
    print(f"Select both runs -> click 'Compare' for side-by-side view.")


if __name__ == "__main__":
    main()
