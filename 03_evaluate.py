"""
03_evaluate.py -- Evaluate experiment results and log to MLflow.

Loads the experiment results (summary.csv + per-client JSONs), computes
quantitative metrics in Python, and logs everything to MLflow for
side-by-side comparison between governance modes.

Three levels of evaluation:
  Level 1 -- Score Accuracy:  range accuracy, MAE
  Level 2 -- Classification:  precision, recall, F1 (binary: guilty/innocent)
  Level 3 -- Per-Group:       breakdown by trap type (the thesis question)
  Bonus   -- Reasoning Quality: two LLM judges via mlflow.evaluate()
               evidence_coverage    (1-10): how specifically evidence is cited
               conclusion_consistency (1-10): does conclusion follow agent's own evidence?
             Both judges run per-client and are broken down correct-vs-incorrect.

Usage:
    python 03_evaluate.py                                     # evaluate gpt-4o-mini, run 1 (defaults)
    python 03_evaluate.py --model gpt-4o --run-id 1          # different model
    python 03_evaluate.py --run-id 2                         # evaluate replicate 2
    python 03_evaluate.py --run-name v1                      # custom MLflow run name prefix

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

MODES = ["int", "hier", "ctx", "llm", "hier_ctx", "hier_llm"]
MODE_LABELS = {
    "int": "intrinsic",
    "hier": "hierarchical",
    "ctx": "context_engineered",
    "llm": "llm_context",
    "hier_ctx": "hier_context_engineered",
    "hier_llm": "hier_llm_context",
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
# Reasoning quality evaluation (mlflow.evaluate with LLM judges)
#
# Two separate metrics replace the old 1-5 "reasoning_quality":
#
#   evidence_coverage (1-10)
#       Does the agent cite SPECIFIC metric values and SPECIFIC article
#       claims?  The old 1-5 rubric let agents score 4-5 with generic
#       phrases like "the data shows high volume."  This rubric requires
#       exact numbers (e.g., "Fan-In=23") and specific article content
#       to score above 6.
#
#   conclusion_consistency (1-10)
#       Does the agent's stated conclusion (embedded in the input as
#       "[Risk Score: X/100 → HIGH/LOW RISK]") follow from the evidence
#       it cited in its own reasoning?  The judge does NOT know whether the
#       conclusion is factually correct — it only evaluates internal logical
#       consistency.  This catches "fluent but wrong" reasoning where an
#       agent cites an alibi and then concludes HIGH RISK anyway.
#
# After scoring, per-client scores are joined with the correct/incorrect
# classification flag and broken down as:
#   {metric}/correct_mean, {metric}/incorrect_mean, {metric}/gap
# A useful metric should show a positive gap (correct cases score higher).
# ---------------------------------------------------------------------------

EVIDENCE_COVERAGE_PROMPT = """\
You are an expert AML compliance auditor evaluating how specifically an AI \
agent's reasoning cites evidence. You will receive:

1. The agent's reasoning text (prefixed with its stated risk score).
2. The ground truth rationale (what a correct assessment should reference).

## Scoring Criteria (1–10)

1–2  No specific evidence cited. The agent makes assertions without referencing
     any data. Example of a 1: "The high fan-in is suspicious and indicates
     potential money laundering." No metric values, no article references.

3–4  Evidence referenced but vague. Generic phrases only — e.g., "the
     transaction data shows elevated volume" without citing the actual value,
     or "the article raises concerns" without stating what they are. Only ONE
     evidence stream addressed (quantitative OR qualitative, not both).

5–6  Both quantitative metrics and knowledge base content mentioned. At least
     ONE specific value or article claim given. Conflicts between the two
     streams acknowledged but not resolved. A moderate summary.

7–8  Specific metric values cited by number (e.g., "Fan-In = 23, above the
     threshold of 20") AND specific article claims referenced by content
     (e.g., "the article identifies the entity as a registered NGO receiving
     donations from 3,000+ donors"). Conflicts explicitly addressed.

9–10 ALL material metrics cited with exact values. Article claims accurately
     quoted or paraphrased by substance (not just "the article says…").
     Every conflict between quantitative and qualitative evidence explicitly
     resolved with evidential logic. States which evidence was decisive and
     why. Notes absence of flags where relevant (e.g., "no volume or fan-in
     threshold was breached, making the knowledge base signal the ONLY risk
     indicator").

## Rules

- Score 1–4 if no specific numeric value is cited anywhere.
- Score 7+ ONLY if the agent cites BOTH a specific number AND a specific
  article claim by substance.
- Score 9–10 ONLY if every conflict is explicitly resolved AND the decisive
  evidence is named.
- Ignore the risk score prefix when scoring — evaluate only the reasoning body.

Respond with ONLY an integer from 1 to 10.
"""

CONCLUSION_CONSISTENCY_PROMPT = """\
You are an expert AML compliance auditor. Your task is to evaluate whether an
AI agent's stated risk conclusion is internally consistent with the evidence
it cited in its own reasoning.

The input begins with "[Stated Risk Score: X/100 → HIGH RISK]" or "LOW RISK".
The reasoning that follows is the agent's own explanation.

CRITICAL: Do NOT evaluate whether the conclusion is factually correct.
          Evaluate ONLY whether the conclusion logically follows from the
          evidence the agent itself cited. An agent that correctly concludes
          LOW RISK after citing strong alibi evidence scores 9–10. An agent
          that cites the same alibi evidence but concludes HIGH RISK also
          scores 1–2 — regardless of which is factually right.

## Scoring Criteria (1–10)

1–2  Direct contradiction. The agent's own reasoning explicitly supports the
     OPPOSITE conclusion. Examples:
     - Agent writes "the article confirms this is a legitimate NGO explaining
       the high fan-in" → then concludes HIGH RISK.
     - Agent cites a leaked intelligence brief naming the subject as a terror
       financier → then concludes LOW RISK.

3–4  Weak inconsistency. The reasoning leans toward one conclusion but the
     stated score points the other way without adequate justification. The
     logical gap is clear but not as stark as 1–2.

5–6  Partial consistency. The conclusion is broadly defensible from the cited
     evidence, but the agent does not clearly explain why it outweighs the
     countervailing signals it acknowledged.

7–8  Clear consistency. The conclusion directly follows from the evidence
     cited. The agent identifies which evidence was decisive and why it
     outweighs the conflicting signals.

9–10 Rigorous consistency. The agent explicitly anticipates and dismisses the
     alternative interpretation using cited evidence. The conclusion is the
     only reasonable inference from the agent's own argument.

## Rules

- If the agent cites only one side of the evidence and reaches the consistent
  conclusion, score 7–10 depending on clarity of reasoning.
- If the agent cites mixed evidence, score based on whether the stated
  rationale for prioritising one side is convincing.
- Do NOT use the ground truth context — it is not provided.

Respond with ONLY an integer from 1 to 10.
"""


def evaluate_reasoning(
    df: pd.DataFrame,
    eval_df: pd.DataFrame,
    results_dir: Path,
    prefix: str,
    run_name: str,
) -> None:
    """Run mlflow.evaluate() with two LLM judges for one governance mode.

    Judges:
      evidence_coverage       — 1-10, specificity of citations
      conclusion_consistency  — 1-10, does conclusion follow agent's own evidence?

    After scoring, breaks down both metrics by correct/incorrect classification
    and logs {metric}/correct_mean, {metric}/incorrect_mean, {metric}/gap
    to the active MLflow run.
    """
    mode_label = MODE_LABELS[prefix]
    score_col = f"{prefix}_score"
    correct_col = f"{prefix}_correct"
    reasoning_map = load_reasoning(results_dir, prefix)

    if not reasoning_map:
        print(f"  No reasoning JSONs found for {mode_label}, skipping LLM evaluation.")
        return

    # Build evaluation DataFrame — inputs include the risk score so the
    # conclusion_consistency judge can see what conclusion was stated.
    rows = []
    for _, row in df.iterrows():
        cid = row["client_id"]
        if cid not in reasoning_map:
            continue
        score = pd.to_numeric(row.get(score_col), errors="coerce")
        if pd.isna(score):
            continue
        score_int = int(score)
        risk_label = "HIGH RISK" if score_int >= CLASSIFICATION_THRESHOLD else "LOW RISK"
        # Prefix reasoning with the stated conclusion so conclusion_consistency
        # can evaluate whether it follows from the cited evidence.
        formatted = (
            f"[Stated Risk Score: {score_int}/100 \u2192 {risk_label}]\n\n"
            f"[Reasoning]:\n{reasoning_map[cid]}"
        )
        # Retrieve the correct/incorrect flag from eval_df
        ev_row = eval_df[eval_df["client_id"] == cid]
        correct_flag = ev_row[correct_col].iloc[0] if (len(ev_row) and correct_col in ev_row.columns) else None
        rows.append({
            "client_id": cid,
            "inputs": formatted,
            "ground_truth": row["rationale"],
            correct_col: correct_flag,
        })

    if not rows:
        print(f"  No matched reasoning for {mode_label}, skipping LLM evaluation.")
        return

    judge_df = pd.DataFrame(rows)

    from mlflow.metrics.genai import make_genai_metric

    judge_model = os.getenv('JUDGE_MODEL', f"openai:/{os.getenv('LLM_MODEL', 'gpt-4o-mini')}")

    evidence_coverage = make_genai_metric(
        name="evidence_coverage",
        definition=(
            "Scores 1-10 how specifically an AML risk assessment cites "
            "quantitative metrics and knowledge base article claims. "
            "Requires exact numeric values and specific article content "
            "to score above 6."
        ),
        grading_prompt=EVIDENCE_COVERAGE_PROMPT,
        model=judge_model,
        parameters={"temperature": 0},
        greater_is_better=True,
        aggregations=["mean"],
    )

    conclusion_consistency = make_genai_metric(
        name="conclusion_consistency",
        definition=(
            "Scores 1-10 whether the agent's stated risk conclusion "
            "(embedded in the input prefix) follows from the evidence "
            "the agent itself cited. Low scores flag fluent-but-wrong "
            "reasoning where the conclusion contradicts the agent's "
            "own evidence."
        ),
        grading_prompt=CONCLUSION_CONSISTENCY_PROMPT,
        model=judge_model,
        parameters={"temperature": 0},
        greater_is_better=True,
        aggregations=["mean"],
    )

    print(f"  Running LLM reasoning evaluation for {mode_label} "
          f"({len(judge_df)} clients) — two judges (1-10 scale)...")

    results = mlflow.evaluate(
        data=judge_df,
        predictions="inputs",
        targets="ground_truth",
        model_type=None,
        extra_metrics=[evidence_coverage, conclusion_consistency],
        evaluators="default",
    )

    # ── Log aggregate metrics ──
    logged_metrics = []
    if results.metrics:
        for key, value in results.metrics.items():
            if any(m in key for m in ["evidence_coverage", "conclusion_consistency"]):
                mlflow.log_metric(key, value)
                logged_metrics.append(f"{key}={value:.2f}")
    if logged_metrics:
        print(f"    Aggregates: {', '.join(logged_metrics)}")

    # ── Correct-vs-Incorrect breakdown ──
    # This is the discriminating test: a useful reasoning metric should score
    # correct cases higher than incorrect ones.
    table_key = "eval_results_table"
    if table_key in results.tables and correct_col in judge_df.columns:
        scored = results.tables[table_key].copy()
        scored["client_id"] = judge_df["client_id"].values
        scored[correct_col] = judge_df[correct_col].values

        for metric_name in ["evidence_coverage/score", "conclusion_consistency/score"]:
            # mlflow metric column names vary slightly by version
            col = metric_name if metric_name in scored.columns else metric_name.split("/")[0]
            if col not in scored.columns:
                continue
            scored[col] = pd.to_numeric(scored[col], errors="coerce")
            correct_scores = scored[scored[correct_col] == 1][col].dropna()
            incorrect_scores = scored[scored[correct_col] == 0][col].dropna()

            short = metric_name.split("/")[0]
            if len(correct_scores) > 0:
                mlflow.log_metric(f"{short}/correct_mean", correct_scores.mean())
            if len(incorrect_scores) > 0:
                mlflow.log_metric(f"{short}/incorrect_mean", incorrect_scores.mean())
            if len(correct_scores) > 0 and len(incorrect_scores) > 0:
                gap = correct_scores.mean() - incorrect_scores.mean()
                mlflow.log_metric(f"{short}/correct_vs_incorrect_gap", gap)
                direction = "+" if gap >= 0 else ""
                print(
                    f"    {short}: correct={correct_scores.mean():.2f} "
                    f"(n={len(correct_scores)})  "
                    f"incorrect={incorrect_scores.mean():.2f} "
                    f"(n={len(incorrect_scores)})  "
                    f"gap={direction}{gap:.2f}"
                )

    print(f"  Reasoning evaluation complete for {mode_label}.")


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
    holdout_group: str | None = None,
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
        if holdout_group:
            mlflow.log_param("holdout_group", holdout_group)

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

        # ── Reasoning quality (LLM judges) ──
        evaluate_reasoning(df, eval_df, results_dir, prefix, run_name)

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
             "Reads results/{dataset}/{model}/run_{run_id}/ and {dataset}_ground_truth.csv.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        help="Model name matching the one used in 02_run_experiment.py "
             "(default: LLM_MODEL env var or gpt-4o-mini).",
    )
    parser.add_argument(
        "--run-id",
        default="1",
        help="Replicate identifier matching the one used in 02_run_experiment.py "
             "(default: 1). Reads results/{dataset}/{model}/run_{run_id}/summary.csv.",
    )
    parser.add_argument(
        "--holdout-group",
        choices=["C1", "C2", "C3", "C4", "D1", "D2"],
        default=None,
        dest="holdout_group",
        help="When evaluating after a holdout experiment, mark this trap group "
             "as OOD in the per-group breakdown. The test set is unchanged; "
             "this flag only adds an annotation to the output.",
    )
    args = parser.parse_args()

    results_dir = Path("results") / args.dataset / args.model / f"run_{args.run_id}"
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
        # Map CLI --holdout-group codes to group_label keys used in GROUP_ORDER.
        _holdout_map = {
            "C1": "fp_trap:charity",
            "C2": "fp_trap:payroll",
            "C3": "fp_trap:high_roller",
            "C4": "fp_trap:structurer",
            "D1": "fn_trap:sleeper",
            "D2": "fn_trap:smurf",
        }
        holdout_label = _holdout_map.get(args.holdout_group) if args.holdout_group else None

        print(f"\n  Per-Group Breakdown:")
        print(f"  {'Group':<25} {'Range Acc':>10} {'Class Acc':>10} "
              f"{'Avg Score':>10} {'MAE':>8} {'Consensus':>10} {'n':>4}  {'Note'}")
        print(f"  {'-' * 90}")
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
            ood_note = "  *** OOD — rules never trained on this type ***" if group_label == holdout_label else ""
            print(
                f"  {group_label:<25} "
                f"{metrics[f'{key_prefix}/range_accuracy']:>9.0%} "
                f"{metrics[f'{key_prefix}/classification_accuracy']:>9.0%} "
                f"{metrics[f'{key_prefix}/avg_score']:>10.1f} "
                f"{metrics[f'{key_prefix}/mae_midpoint']:>8.1f} "
                f"{consensus_str} "
                f"{metrics[f'{key_prefix}/n']:>4.0f}"
                f"{ood_note}"
            )
        if holdout_label:
            print(f"\n  *** {args.holdout_group} ({holdout_label}) is the OOD generalisation test group.")
            print(f"      Rule-synthesis artefacts were not trained on any {args.holdout_group} examples.")
        print()

    # ── Build detailed evaluation CSV ──
    eval_df = build_evaluation_df(df)
    eval_df.to_csv(evaluation_file, index=False)
    print(f"Detailed evaluation saved: {evaluation_file}")

    # ── Log to MLflow ──
    print(f"\nLogging to MLflow (experiment: '{EXPERIMENT_NAME}')...")
    mlflow.set_experiment(EXPERIMENT_NAME)

    # Include model and run_id in the MLflow run name so runs are distinguishable.
    # Format: "{run_name}_{model}_r{run_id}_{mode}" or "{model}_r{run_id}_{mode}".
    run_name_prefix = (
        f"{args.run_name}_{args.model}_r{args.run_id}"
        if args.run_name
        else f"{args.model}_r{args.run_id}"
    )
    for prefix in active_modes:
        log_run(df, eval_df, results_dir, prefix, all_metrics[prefix], run_name_prefix,
                holdout_group=args.holdout_group)

    print(f"\nDone. Run 'mlflow ui' and open http://localhost:5000 to compare runs.")
    print(f"Select both runs -> click 'Compare' for side-by-side view.")


if __name__ == "__main__":
    main()
