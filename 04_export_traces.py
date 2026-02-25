"""
04_export_traces.py -- Export annotated training traces for Kayba.

Reads AgentState JSON files from a results directory and ground truth CSV,
then writes annotated .md files suitable for Kayba's Agentic Context Engine.

Each .md file includes:
  - Classification metadata (CORRECT/INCORRECT, outcome, scores)
  - Full trace content (forensics, news articles, analyst reasoning, review)
  - Ground truth reference

All traces are exported (not just failures) because:
  - LLM stochasticity means correct reasoning should also be codified
  - Kayba's deduplication handles reinforcement weighting
  - The annotation header distinguishes correct from incorrect for researchers

Usage:
    python 04_export_traces.py
    python 04_export_traces.py --results-dir results/train/gpt-4o-mini/run_1/intrinsic
                               --ground-truth train_ground_truth.csv
                               --output-dir training_traces
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


CLASSIFICATION_THRESHOLD = 50  # score >= 50 → predict GUILTY


def _format_news_summary(summary: dict) -> str:
    """Format structured news extractions for the trace file."""
    lines = [f"Articles Found: {summary.get('articles_found', 0)}"]
    for i, ext in enumerate(summary.get("extractions", []), 1):
        lines.append(f"\n  Article {i}: {ext['headline']}")
        lines.append(f"  Source: {ext['source']}")
        lines.append("  Claims:")
        for claim in ext.get("claims", []):
            lines.append(f"    - {claim}")
    return "\n".join(lines)


def _format_review(review: dict) -> str:
    """Format review output for the trace file."""
    lines = [
        f"Decision: {review.get('decision', 'N/A')}",
        f"Adjusted Score: {review.get('adjusted_risk_score', 'N/A')}",
        f"Reasoning: {review.get('reasoning', '')}",
    ]
    citations = review.get("citations", [])
    if citations:
        lines.append("Citations:")
        for c in citations:
            lines.append(f"  - {c}")
    return "\n".join(lines)


def build_trace_md(state: dict, gt_row: dict) -> str:
    """Build an annotated .md trace file from AgentState + ground truth row.

    Args:
        state: The full AgentState dict from the JSON file.
        gt_row: The ground truth row dict for this client.

    Returns:
        The full .md file content as a string.
    """
    client_id = state.get("client_id", "UNKNOWN")
    final = state.get("final_output", {})
    analyst = state.get("analyst_output", {})
    initial = state.get("initial_analyst_output", {})
    review = state.get("review_output", {})

    agent_score = final.get("risk_score", analyst.get("risk_score"))
    agent_label = final.get("risk_label", analyst.get("risk_label", "unknown"))
    agent_confidence = final.get("confidence", analyst.get("confidence"))
    initial_score = initial.get("risk_score")
    review_decision = state.get("review_decision", "N/A")
    revision_count = state.get("revision_count", 0)

    # Classification outcome
    actual_guilty = str(gt_row.get("is_money_laundering", "")).lower() in ("true", "1")
    predicted_guilty = (agent_score is not None) and (agent_score >= CLASSIFICATION_THRESHOLD)
    correct = predicted_guilty == actual_guilty

    predicted_label = "GUILTY" if predicted_guilty else "INNOCENT"
    actual_label = "GUILTY" if actual_guilty else "INNOCENT"

    outcome_label = "CORRECT" if correct else "INCORRECT"
    if not correct:
        if predicted_guilty and not actual_guilty:
            error_type = "False Positive"
        else:
            error_type = "False Negative"
        outcome_str = f"INCORRECT — {error_type}"
    else:
        outcome_str = "CORRECT"

    group = gt_row.get("group", "")
    trap_subtype = gt_row.get("trap_subtype", "")
    group_display = f"{group}:{trap_subtype}" if trap_subtype else group
    expected_min = gt_row.get("expected_risk_min", "")
    expected_max = gt_row.get("expected_risk_max", "")
    rationale = gt_row.get("rationale", "")

    # ── Header metadata ──
    score_shift = (
        f"{agent_score - initial_score:+d}" if (agent_score is not None and initial_score is not None) else "N/A"
    )
    header = f"""\
---
# AML AGENT TRACE
## Classification Metadata
- **Client ID**: {client_id}
- **Group**: {group_display}
- **Outcome**: {outcome_str}
- **Initial Score**: {initial_score}/100 (first instinct before any review)
- **Final Score**: {agent_score}/100 ({agent_label}) — predicted {predicted_label}
- **Score Shift**: {score_shift} (final minus initial)
- **Agent Confidence**: {agent_confidence}/100
- **Ground Truth**: {actual_label} (is_money_laundering={actual_guilty})
- **Expected Score Range**: {expected_min}–{expected_max}
- **Review Decision**: {review_decision}
- **Revision Count**: {revision_count}
---

"""

    # ── Forensics input ──
    forensics_section = f"""\
## Forensics Input (Quantitative Source of Truth)

{state.get('forensics_output', '_No forensics output recorded._')}

"""

    # ── News articles ──
    news_section = f"""\
## News Intelligence (Raw Articles)

{state.get('news_output', '_No news output recorded._')}

"""

    # ── News scout extractions ──
    news_summary = state.get("news_summary", {})
    if news_summary:
        news_extractions = _format_news_summary(news_summary)
    else:
        news_extractions = "_No extractions recorded._"

    extractions_section = f"""\
## News Scout Extractions (Structured Facts)

{news_extractions}

"""

    # ── Analyst assessment ──
    if initial and initial != analyst:
        # Revision occurred — show both initial and final analyst outputs
        analyst_section = f"""\
## Analyst Assessment (Initial — Before Review)

Score: {initial.get('risk_score', 'N/A')}/100 ({initial.get('risk_label', '')}) \
| Confidence: {initial.get('confidence', 'N/A')}/100

{initial.get('reasoning', '_No reasoning recorded._')}

## Analyst Assessment (Final — After Revision)

Score: {analyst.get('risk_score', 'N/A')}/100 ({analyst.get('risk_label', '')}) \
| Confidence: {analyst.get('confidence', 'N/A')}/100

{analyst.get('reasoning', '_No reasoning recorded._')}

"""
    elif analyst:
        analyst_section = f"""\
## Analyst Assessment

Score: {analyst.get('risk_score', 'N/A')}/100 ({analyst.get('risk_label', '')}) \
| Confidence: {analyst.get('confidence', 'N/A')}/100

{analyst.get('reasoning', '_No reasoning recorded._')}

"""
    else:
        analyst_section = "## Analyst Assessment\n\n_No analyst output recorded._\n\n"

    # ── Review decision ──
    if review:
        review_section = f"""\
## Review Decision

{_format_review(review)}

"""
    else:
        review_section = "## Review Decision\n\n_No review output recorded._\n\n"

    # ── Ground truth reference ──
    gt_section = f"""\
## Ground Truth Reference

- **Expected**: {actual_label} risk ({expected_min}–{expected_max})
- **Rationale**: {rationale}

---
"""

    return (
        header
        + forensics_section
        + news_section
        + extractions_section
        + analyst_section
        + review_section
        + gt_section
    )


def export_traces(
    results_dir: Path,
    ground_truth_file: Path,
    output_dir: Path,
) -> None:
    """Export all AgentState JSON files as annotated .md traces.

    Args:
        results_dir: Directory containing {client_id}.json files.
        ground_truth_file: Path to the ground truth CSV.
        output_dir: Directory to write the .md output files.
    """
    if not results_dir.exists():
        print(f"ERROR: Results directory not found: {results_dir}")
        return

    if not ground_truth_file.exists():
        print(f"ERROR: Ground truth file not found: {ground_truth_file}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load ground truth indexed by client_id
    gt_df = pd.read_csv(ground_truth_file)
    gt_index = gt_df.set_index("client_id").to_dict("index")

    json_files = sorted(results_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {results_dir}")
        return

    print(f"Exporting {len(json_files)} traces from {results_dir}")
    print(f"Output: {output_dir}\n")

    n_correct = 0
    n_incorrect = 0
    n_errors = 0
    n_skipped = 0

    for json_path in json_files:
        client_id = json_path.stem

        with open(json_path, encoding="utf-8") as f:
            state = json.load(f)

        # Skip error files
        if "error" in state and "final_output" not in state:
            print(f"  SKIP  {client_id}  (error run)")
            n_errors += 1
            continue

        if client_id not in gt_index:
            print(f"  SKIP  {client_id}  (not in ground truth)")
            n_skipped += 1
            continue

        gt_row = gt_index[client_id]

        md_content = build_trace_md(state, gt_row)

        out_path = output_dir / f"{client_id}.md"
        out_path.write_text(md_content, encoding="utf-8")

        # Classify for summary
        final = state.get("final_output", state.get("analyst_output", {}))
        agent_score = final.get("risk_score")
        actual_guilty = str(gt_row.get("is_money_laundering", "")).lower() in ("true", "1")
        predicted_guilty = (agent_score is not None) and (agent_score >= CLASSIFICATION_THRESHOLD)
        correct = predicted_guilty == actual_guilty

        outcome = "CORRECT  " if correct else "INCORRECT"
        score_str = f"score={agent_score:>3}" if agent_score is not None else "score=N/A"
        print(f"  {outcome}  {client_id}  {score_str}  gt={'G' if actual_guilty else 'I'}")

        if correct:
            n_correct += 1
        else:
            n_incorrect += 1

    total_exported = n_correct + n_incorrect
    print(f"\n{'=' * 50}")
    print(f"Exported: {total_exported} traces  ({n_correct} correct, {n_incorrect} incorrect)")
    if n_errors:
        print(f"Skipped (error runs): {n_errors}")
    if n_skipped:
        print(f"Skipped (not in GT): {n_skipped}")
    print(f"\nFeed {output_dir}/ to Kayba's agentic_system_prompting.py")
    print("Output: external_agent_injection.txt -> copy to this project root")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export annotated AML agent traces for Kayba training."
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/train/gpt-4o-mini/run_1/intrinsic"),
        help="Directory containing {client_id}.json result files "
             "(default: results/train/gpt-4o-mini/run_1/intrinsic).",
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("train_ground_truth.csv"),
        help="Ground truth CSV file (default: train_ground_truth.csv).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("training_traces"),
        help="Directory to write annotated .md files (default: training_traces/).",
    )
    args = parser.parse_args()

    export_traces(
        results_dir=args.results_dir,
        ground_truth_file=args.ground_truth,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
