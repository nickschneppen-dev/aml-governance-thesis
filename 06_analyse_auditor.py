"""
06_analyse_auditor.py -- Qualitative analysis of hierarchical auditor reasoning.

Investigates the over-escalation failure mode: for FP cases (innocent clients
incorrectly flagged as GUILTY by the hierarchical mode), examines whether the
auditor's rejection reasoning is driven by quantitative red flags or a genuine
failure to engage with the qualitative evidence (KB articles) that explain them.

Tests two competing hypotheses:

  Hypothesis A — Context-window separation bias:
    The auditor lacks the analyst's evidence chain (separate context window) and
    defaults to salient quantitative signals (fan_in / fan_out / volume) when
    re-evaluating from raw data.  Signature: citations dominated by metric names,
    little or no engagement with KB article content.

  Hypothesis B — Prompt insufficient on FP risk:
    The auditor's system prompt correctly instructs it to check quantitative flags
    but does not adequately prompt it to consider legitimate explanations.
    Signature: citations acknowledge KB content but still treat flags as dispositive.

Output:
  - Per-case breakdown with citation classification
  - Aggregate counts: quantitative-dominant vs qualitative-engaged
  - Representative verbatim quotations for thesis write-up

Usage:
    python 06_analyse_auditor.py
    python 06_analyse_auditor.py --results-dir results/test/gpt-4o-mini/run_1
                                 --ground-truth test_ground_truth.csv
    python 06_analyse_auditor.py --model gpt-4o --run-id 2
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CLASSIFICATION_THRESHOLD = 50

# Quantitative signal keywords in auditor reasoning/citations
QUANT_KEYWORDS = [
    r"\bfan.?in\b",
    r"\bfan.?out\b",
    r"\btotal.?volume\b",
    r"\bavg.?amount\b",
    r"\baverage.?amount\b",
    r"\btransaction.?count\b",
    r"\btx.?count\b",
    r"\bflag\b",
    r"\bthreshold\b",
    r"\bmetric",
    r"\bquantitative\b",
    r"\braw data\b",
    r"\$[\d,]+",        # dollar amounts
    r"\b\d+\s+unique",  # e.g. "25 unique senders"
]

# Keywords that indicate the auditor engaged with KB / qualitative content
QUAL_KEYWORDS = [
    r"\barticle\b",
    r"\bnews\b",
    r"\bknowledge.?base\b",
    r"\bheadline\b",
    r"\balibi\b",
    r"\bexplain",
    r"\blegitimate\b",
    r"\bregistered\b",
    r"\bNGO\b",
    r"\bcharity\b",
    r"\bpayroll\b",
    r"\bcasino\b",
    r"\bIPO\b",
    r"\bmining\b",
    r"\bvend",
    r"\bmedical\b",
    r"\bdealer\b",
    r"\bAUSTRAC\b",
    r"\bASIC\b",
    r"\bATO\b",
    r"\bFair Work\b",
    r"\bACNC\b",
    r"\bregulat",          # regulation / regulatory
    r"\bsector.?wide\b",
    r"\bnot directed\b",
    r"\bcontext\b",
    r"\balternative\b",
]

# Keywords that signal the auditor dismissed the KB explanation
DISMISSAL_KEYWORDS = [
    r"\bno (?:direct|definitive|clear|sufficient) (?:evidence|link|connection|proof)\b",
    r"\black of (?:evidence|documentation|proof|support)\b",
    r"\bnot (?:sufficient|enough|conclusive|compelling)\b",
    r"\binsufficient (?:evidence|explanation|justification)\b",
    r"\bdoes not (?:establish|prove|demonstrate|confirm)\b",
    r"\bcannot (?:rule out|confirm|verify)\b",
    r"\bwarrants? (?:further|additional|greater|more) (?:scrutiny|investigation|review)\b",
    r"\bcaution\b",
    r"\bcautious\b",
    r"\bprecautionary\b",
    r"\berr on the side\b",
]

FP_GROUPS = {"charity", "payroll", "high_roller", "structurer"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _count_matches(text: str, patterns: list[str]) -> int:
    text_lower = text.lower()
    return sum(1 for p in patterns if re.search(p, text_lower))


def _classify_citation(text: str) -> str:
    """Classify one citation string as QUANT, QUAL, MIXED, or DISMISSAL."""
    q = _count_matches(text, QUANT_KEYWORDS)
    ql = _count_matches(text, QUAL_KEYWORDS)
    d = _count_matches(text, DISMISSAL_KEYWORDS)
    if d > 0:
        return "DISMISSAL"
    if q > 0 and ql > 0:
        return "MIXED"
    if q > 0:
        return "QUANT"
    if ql > 0:
        return "QUAL"
    return "OTHER"


def _classify_reasoning(text: str) -> dict:
    """Return keyword hit counts and overall stance for reasoning text."""
    q = _count_matches(text, QUANT_KEYWORDS)
    ql = _count_matches(text, QUAL_KEYWORDS)
    d = _count_matches(text, DISMISSAL_KEYWORDS)
    if d >= 2:
        stance = "DISMISSAL"
    elif q > ql * 2:
        stance = "QUANT_DOMINANT"
    elif ql > q:
        stance = "QUAL_ENGAGED"
    else:
        stance = "MIXED"
    return {"quant_hits": q, "qual_hits": ql, "dismissal_hits": d, "stance": stance}


def _short(text: str, n: int = 200) -> str:
    text = text.strip().replace("\n", " ")
    return text[:n] + "…" if len(text) > n else text


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------
def analyse(results_dir: Path, ground_truth_file: Path) -> None:
    hier_dir = results_dir / "hierarchical"
    summary_file = results_dir / "summary.csv"

    if not hier_dir.exists():
        print(f"ERROR: {hier_dir} not found.")
        return
    if not summary_file.exists():
        print(f"ERROR: {summary_file} not found.")
        return
    if not ground_truth_file.exists():
        print(f"ERROR: {ground_truth_file} not found.")
        return

    summary = pd.read_csv(summary_file).drop_duplicates(subset="client_id", keep="last")
    gt = pd.read_csv(ground_truth_file)
    merged = summary.merge(gt, on="client_id")

    # ── Identify FP errors in hierarchical mode ──
    fp_errors = merged[
        (merged["is_money_laundering"] == False) &
        (merged["hier_score"] >= CLASSIFICATION_THRESHOLD)
    ].copy()

    fp_controls = merged[
        (merged["is_money_laundering"] == False) &
        (merged["hier_score"] < CLASSIFICATION_THRESHOLD)
    ].copy()

    print(f"\n{'=' * 70}")
    print(f"  HIERARCHICAL AUDITOR — FALSE POSITIVE FAILURE ANALYSIS")
    print(f"{'=' * 70}")
    print(f"\n  FP errors (innocent, scored >= {CLASSIFICATION_THRESHOLD}): {len(fp_errors)}")
    print(f"  TN correct (innocent, scored < {CLASSIFICATION_THRESHOLD}): {len(fp_controls)}")
    print()

    # ── Per-case analysis ──
    cases = []

    for _, row in fp_errors.sort_values("trap_subtype").iterrows():
        cid = row["client_id"]
        subtype = row.get("trap_subtype", "unknown")
        hier_score = row["hier_score"]
        int_score = row.get("int_score")

        json_path = hier_dir / f"{cid}.json"
        if not json_path.exists():
            continue

        state = json.loads(json_path.read_text(encoding="utf-8"))
        review = state.get("review_output", {})
        decision = review.get("decision", "N/A")
        reasoning = review.get("reasoning", "")
        citations = review.get("citations", [])
        revision_count = state.get("revision_count", 0)
        revision_scores = [r["risk_score"] for r in state.get("revision_history", [])]
        initial_score = state.get("initial_analyst_output", {}).get("risk_score")
        forensics = state.get("forensics_output", "")

        r_class = _classify_reasoning(reasoning)
        citation_classes = [_classify_citation(c) for c in citations]

        cases.append({
            "client_id": cid,
            "subtype": subtype,
            "initial_analyst_score": initial_score,
            "hier_score": hier_score,
            "int_score": int_score,
            "revision_count": revision_count,
            "revision_scores": revision_scores,
            "decision": decision,
            "reasoning": reasoning,
            "citations": citations,
            "citation_classes": citation_classes,
            "reasoning_stance": r_class["stance"],
            "quant_hits": r_class["quant_hits"],
            "qual_hits": r_class["qual_hits"],
            "dismissal_hits": r_class["dismissal_hits"],
            "forensics_snippet": forensics[:300],
        })

    # ── Print per-case report ──
    stances: dict[str, int] = {}
    for c in cases:
        subtype = c["subtype"]
        stance = c["reasoning_stance"]
        stances[stance] = stances.get(stance, 0) + 1

        print(f"  -- {c['client_id']}  ({subtype}) --")
        print(f"     Analyst initial: {c['initial_analyst_score']}  "
              f"->  Hier final: {c['hier_score']}  "
              f"(Intrinsic: {c['int_score']})  "
              f"Revisions: {c['revision_count']} {c['revision_scores']}")
        print(f"     Auditor decision: {c['decision']}  |  Reasoning stance: {stance}  "
              f"(quant={c['quant_hits']}, qual={c['qual_hits']}, dismissal={c['dismissal_hits']})")
        print(f"     Reasoning: {_short(c['reasoning'], 280)}")
        for i, (cit, cls) in enumerate(zip(c["citations"], c["citation_classes"]), 1):
            print(f"     Citation {i} [{cls}]: {_short(cit, 180)}")
        print()

    # ── Aggregate summary ──
    print(f"{'=' * 70}")
    print(f"  AGGREGATE EVIDENCE-TYPE BREAKDOWN  (n={len(cases)} FP errors)")
    print(f"{'=' * 70}\n")

    total_citations = sum(len(c["citations"]) for c in cases)
    all_citation_classes: list[str] = []
    for c in cases:
        all_citation_classes.extend(c["citation_classes"])

    from collections import Counter
    cit_counts = Counter(all_citation_classes)
    stance_counts = Counter(c["reasoning_stance"] for c in cases)

    print(f"  Reasoning stance (overall):")
    for stance, count in sorted(stance_counts.items(), key=lambda x: -x[1]):
        pct = count / len(cases) * 100
        print(f"    {stance:<22s} {count:>3}  ({pct:.0f}%)")

    print(f"\n  Citation type breakdown (total={total_citations}):")
    for cls, count in sorted(cit_counts.items(), key=lambda x: -x[1]):
        pct = count / total_citations * 100 if total_citations else 0
        print(f"    {cls:<12s}  {count:>3}  ({pct:.0f}%)")

    print(f"\n  Avg score escalation (intrinsic → hierarchical) for FP errors:")
    fp_errors_merged = pd.DataFrame(cases)
    if "int_score" in fp_errors_merged.columns:
        valid = fp_errors_merged.dropna(subset=["int_score"])
        if len(valid):
            avg_shift = (valid["hier_score"] - valid["int_score"]).mean()
            print(f"    {avg_shift:+.1f} points  (n={len(valid)})")

    # ── Hypothesis verdict ──
    print(f"\n{'=' * 70}")
    print(f"  HYPOTHESIS ASSESSMENT")
    print(f"{'=' * 70}\n")

    quant_dom = stance_counts.get("QUANT_DOMINANT", 0)
    dismissal = stance_counts.get("DISMISSAL", 0)
    qual_eng = stance_counts.get("QUAL_ENGAGED", 0)
    mixed = stance_counts.get("MIXED", 0)

    quant_leaning = quant_dom + dismissal
    qual_leaning = qual_eng

    print(f"  Hypothesis A (context-window bias → quantitative default):")
    print(f"    Cases with QUANT_DOMINANT or DISMISSAL reasoning: "
          f"{quant_leaning}/{len(cases)} ({quant_leaning/len(cases)*100:.0f}%)")
    print(f"    These auditors ignore or dismiss the KB explanation in favour of raw flags.\n")

    print(f"  Hypothesis B (prompt under-constrains FP risk):")
    print(f"    Cases where auditor ACKNOWLEDGES qualitative evidence but still escalates: "
          f"{qual_eng + mixed}/{len(cases)} ({(qual_eng+mixed)/len(cases)*100:.0f}%)")
    print(f"    These auditors see the KB context but treat quantitative flags as dispositive.\n")

    # ── Subtype breakdown ──
    print(f"{'=' * 70}")
    print(f"  PER-SUBTYPE STANCE BREAKDOWN")
    print(f"{'=' * 70}\n")

    df = pd.DataFrame(cases)
    if len(df):
        for st in sorted(df["subtype"].dropna().unique()):
            subset = df[df["subtype"] == st]
            stances_here = subset["reasoning_stance"].value_counts().to_dict()
            print(f"  {st} (n={len(subset)}): {stances_here}")
    print()

    # ── Representative quotations ──
    print(f"{'=' * 70}")
    print(f"  REPRESENTATIVE VERBATIM QUOTATIONS FOR THESIS")
    print(f"{'=' * 70}\n")

    for stance_target in ["QUANT_DOMINANT", "DISMISSAL", "MIXED", "QUAL_ENGAGED"]:
        subset = [c for c in cases if c["reasoning_stance"] == stance_target]
        if not subset:
            continue
        ex = subset[0]
        print(f"  [{stance_target}]  {ex['client_id']} ({ex['subtype']})")
        print(f"  \"{_short(ex['reasoning'], 400)}\"")
        for cit in ex["citations"][:2]:
            print(f"    • {_short(cit, 200)}")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Qualitative analysis of hierarchical auditor FP failures."
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Run directory (default: results/test/{model}/run_{run_id}).",
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=None,
        help="Ground truth CSV (default: test_ground_truth.csv).",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        help="Model name (default: LLM_MODEL env or gpt-4o-mini).",
    )
    parser.add_argument(
        "--run-id",
        default="1",
        help="Run ID (default: 1).",
    )
    args = parser.parse_args()

    results_dir = args.results_dir or (
        Path("results") / "test" / args.model / f"run_{args.run_id}"
    )
    ground_truth_file = args.ground_truth or Path("test_ground_truth.csv")

    analyse(results_dir, ground_truth_file)


if __name__ == "__main__":
    main()
