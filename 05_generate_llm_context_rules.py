"""
05_generate_llm_context_rules.py -- Synthesise LLM-Context rules from training traces.

Reads all annotated training traces and prompts an LLM to derive generalizable
rules for AML analysis from its own past errors and successes. The output
(llm_context_rules.txt) is then injected into the self-review user message
for the "llm_context" governance mode — not into the Analyst prompt, so the
initial analyst report is identical across all four modes.

This is the methodologically equivalent counterpart to the context_engineered
mode: both modes inject a pre-derived ruleset into the Analyst's system prompt,
and both rulesets are derived from the same 50 training traces. The only
difference is the source of rule generation:
  - context_engineered: Kayba's external ACE pipeline
  - llm_context:        the LLM itself, synthesising rules from its own traces

Usage:
    python 05_generate_llm_context_rules.py
    python 05_generate_llm_context_rules.py --traces-dir training_traces
    python 05_generate_llm_context_rules.py --output llm_context_rules.txt
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# Trace parsing
# ---------------------------------------------------------------------------

def _extract_section(text: str, heading: str) -> str:
    """Return the body of a ## heading section, stopping at the next ## or EOF."""
    pattern = rf"## {re.escape(heading)}\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_metadata(text: str) -> dict[str, str]:
    """Extract key:value pairs from the Classification Metadata block."""
    fields: dict[str, str] = {}
    for line in text.split("\n"):
        m = re.match(r"- \*\*(.+?)\*\*: (.+)", line)
        if m:
            fields[m.group(1)] = m.group(2)
    return fields


def load_trace(path: Path) -> dict:
    """Parse a training trace .md file into structured fields.

    Only extracts the fields needed for rule synthesis — skips raw forensics
    and raw news articles to keep the LLM prompt within context limits.
    """
    text = path.read_text(encoding="utf-8")
    meta = _extract_metadata(text)
    return {
        "client_id": meta.get("Client ID", path.stem),
        "group": meta.get("Group", "unknown"),
        "outcome": meta.get("Outcome", "UNKNOWN"),
        "final_score": meta.get("Final Score", ""),
        "review_decision": meta.get("Review Decision", ""),
        "analyst_reasoning": _extract_section(text, "Analyst Assessment"),
        "review_reasoning": _extract_section(text, "Review Decision"),
        "ground_truth": _extract_section(text, "Ground Truth Reference"),
    }


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in Anti-Money Laundering compliance and AI agent design.

You are reviewing the past performance of an AI AML analyst agent that assessed \
50 training clients for money laundering risk. Your task is to extract \
generalizable rules that will improve the agent's reasoning on future, unseen cases.

Focus on reasoning patterns, not memorising specific clients or scores.\
"""

USER_TEMPLATE = """\
Below are annotated traces from a training run of an AML analyst agent.
Cases are split into two groups:
  1. INCORRECT CASES — where the agent reached the wrong conclusion
  2. CORRECT TRAP CASES — where the agent correctly navigated a difficult scenario

Study both groups to identify:
- What signals the agent over-weighted or under-weighted when it made errors
- What reasoning patterns led to correct conclusions in hard cases

Output as many generalizable rules as the evidence warrants — let the patterns in the data
guide the count rather than hitting an arbitrary number. Aim for completeness over a fixed
target: if the errors cluster around 10 distinct failure modes, 10 focused rules are better
than 25 padded ones; if you identify 30 distinct patterns, include them all.

Format each rule as:
[Rule N]: <clear, actionable statement>
Applies when: <the transaction pattern or news signal that triggers this rule>
Rationale: <why this rule matters — reference the error or success pattern you observed>

Rules must be generalizable — do not reference specific client IDs.

---

## INCORRECT CASES ({n_incorrect} cases — study these carefully)

{incorrect_cases}

---

## CORRECT TRAP CASES ({n_correct_traps} cases — these show what worked)

{correct_trap_cases}

---

Now output your rules:
"""


def _format_case(trace: dict, include_review: bool = True) -> str:
    """Format a single trace as a readable block for the synthesis prompt."""
    parts = [
        f"Client: {trace['client_id']} | Group: {trace['group']} | Outcome: {trace['outcome']}",
        f"Final Score: {trace['final_score']} | Review Decision: {trace['review_decision']}",
        "",
        "ANALYST REASONING:",
        trace["analyst_reasoning"],
    ]
    if include_review and trace["review_reasoning"].strip():
        parts += ["", "REVIEW REASONING:", trace["review_reasoning"]]
    parts += ["", "GROUND TRUTH:", trace["ground_truth"]]
    return "\n".join(parts)


def build_prompt(traces: list[dict]) -> str:
    """Construct the synthesis prompt from the parsed traces."""
    incorrect = [t for t in traces if "INCORRECT" in t["outcome"]]
    # Correct trap cases: any correct case that is not a control group
    correct_traps = [
        t for t in traces
        if "CORRECT" in t["outcome"] and "control" not in t["group"]
    ]

    incorrect_text = "\n\n---\n\n".join(_format_case(t) for t in incorrect)
    correct_trap_text = "\n\n---\n\n".join(
        _format_case(t, include_review=False) for t in correct_traps
    )

    return USER_TEMPLATE.format(
        n_incorrect=len(incorrect),
        incorrect_cases=incorrect_text,
        n_correct_traps=len(correct_traps),
        correct_trap_cases=correct_trap_text,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate self-reflection rules from training traces."
    )
    parser.add_argument(
        "--traces-dir",
        default="training_traces",
        help="Directory containing training trace .md files (default: training_traces)",
    )
    parser.add_argument(
        "--output",
        default="llm_context_rules.txt",
        help="Output file for the generated rules (default: llm_context_rules.txt)",
    )
    args = parser.parse_args()

    traces_dir = Path(args.traces_dir)
    if not traces_dir.exists():
        raise FileNotFoundError(
            f"Traces directory not found: {traces_dir}. "
            "Run 04_export_traces.py first."
        )

    trace_files = sorted(traces_dir.glob("*.md"))
    if not trace_files:
        raise FileNotFoundError(f"No .md trace files found in {traces_dir}.")

    print(f"Loading {len(trace_files)} traces from {traces_dir}/ ...")
    traces = [load_trace(f) for f in trace_files]

    incorrect = [t for t in traces if "INCORRECT" in t["outcome"]]
    correct_traps = [
        t for t in traces
        if "CORRECT" in t["outcome"] and "control" not in t["group"]
    ]
    print(f"  {len(incorrect)} incorrect cases, {len(correct_traps)} correct trap cases")

    prompt = build_prompt(traces)

    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    print(f"Synthesising rules with {model} ...")
    llm = ChatOpenAI(model=model, temperature=0)
    response = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])

    rules_text = response.content

    output_path = Path(args.output)
    output_path.write_text(rules_text, encoding="utf-8")
    print(f"\nRules written to {output_path} ({len(rules_text):,} chars)")
    print("\nPreview (first 600 chars):")
    print(rules_text[:600].encode("ascii", errors="replace").decode("ascii"))


if __name__ == "__main__":
    main()
