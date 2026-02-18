"""
agents.py -- Agent node functions for the AML governance system.

Each function takes an AgentState dict and returns a partial state update.
LLM-powered nodes accept an optional RunnableConfig so that callbacks
(e.g. Langfuse tracing) propagate from the graph invocation.

Node types:
  - Deterministic: forensics_scout_node, finalise_node (no LLM)
  - LLM-powered:   news_scout_node, analyst_node, self_review_node,
                    auditor_node, revision_node
"""

from __future__ import annotations

import os

from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

from state import (
    AgentState,
    AnalystOutput,
    NewsSummary,
    ReviewOutput,
)
from tools import tool_analyze_transactions, tool_search_news


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------
def get_llm(temperature: float = 1.0) -> ChatGoogleGenerativeAI:
    """Return the LLM instance used by all agents.

    All agents share the same model to ensure the ONLY experimental variable
    is the governance structure (intrinsic vs. hierarchical), not model
    differences.

    Note: Gemini 3.0+ requires temperature=1.0.  Lower values (e.g. 0.0)
    can cause infinite loops and degraded reasoning performance per Google's
    API documentation.
    """
    return ChatGoogleGenerativeAI(
        model=os.getenv("LLM_MODEL", "gemini-3-pro-preview"),
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

NEWS_SCOUT_PROMPT = """\
You are an AML Intelligence Analyst performing open-source intelligence (OSINT) \
research on a client.

You will receive raw articles from a news search tool.  Your job is to extract \
FACTS from each article -- not opinions, not risk judgments.

Rules:
- Extract factual claims only.  Good: "Individual named in AUSTRAC enforcement \
action."  Bad: "Individual is a criminal."
- Preserve the source attribution for each claim.
- Do NOT assess risk.  Do NOT use words like "suspicious", "risky", or "guilty".
- If an article describes a sector-wide review (not directed at this specific \
entity), note that distinction in your claims.
- Extract ALL claims from the article body, especially those buried in later \
paragraphs.  Do not skip details.
"""

ANALYST_PROMPT = """\
You are a Senior AML Analyst.  You receive two inputs:
1. **Quantitative Metrics** (from the Forensics tool -- these are ground-truth facts).
2. **Qualitative Intelligence** (structured extractions from the News Scout).

Your job is to synthesise both into a risk assessment.

## AML Domain Knowledge (use this to interpret the metrics)

- **Fan-In > 20** (unique senders): May indicate a collection hub (charity, \
donations) OR a mule account receiving structured deposits from many sources.
- **Fan-Out > 80** (unique recipients): May indicate layering/distribution \
(splitting funds across accounts) OR legitimate payroll/vendor payments.
- **Total Volume > $200,000**: Elevated throughput that warrants scrutiny.  \
Could be legitimate for high-turnover businesses (casinos, mining, agriculture).
- **Avg Amount > $1,000**: Consistently large transactions may indicate \
structuring OR legitimate high-ticket business (car sales, medical billing).
- **No risk flags triggered**: Does NOT mean the client is clean.  Some of the \
most dangerous cases (terrorism financing, hawala networks, mule recruitment) \
involve deliberately low volumes that fly under automated thresholds.

## Reasoning Rules

- You MUST consider BOTH quantitative and qualitative evidence.
- If a risk flag fires but the news explains it (e.g., registered NGO explains \
high fan-in), you should weigh that explanation.
- If no risk flags fire but the news contains adverse intelligence (e.g., \
linked to a terror group), you MUST escalate the risk score.
- Conflicting evidence must be explicitly addressed in your reasoning.
- State which evidence you found most decisive and why.

## Output

Return a structured JSON with:
- risk_score (0-100): 0-30 = low, 31-69 = medium, 70-100 = high
- risk_label: must match the score range
- confidence (0-100): how certain you are
- reasoning: cite specific metrics and article claims
"""

SELF_REVIEW_PROMPT = """\
You are the SAME Senior AML Analyst who wrote the report below.  You are now \
reviewing your own work.

You have access to:
1. Your original risk assessment.
2. The RAW quantitative data from the Forensics tool.
3. The RAW news articles from the search tool.
4. The News Scout's structured extractions.

## Review Checklist

- Did I consider ALL the evidence, or did I anchor on the first signal I saw?
- Does my risk score match the evidence?  Would I change it?
- Did I address conflicting evidence explicitly?
- Did the News Scout miss any claims from the raw articles?  If so, do those \
missed claims change my assessment?
- Could I be wrong?  What would change my mind?

## Rules

- Compare your report's claims against the RAW tool outputs.
- If you find a discrepancy or missed evidence, REJECT and explain why.
- If your report is consistent with all the raw data, APPROVE.
- Provide an adjusted_risk_score reflecting your current view (may match \
original if approving).
- Cite specific data points from the raw outputs to support your decision.
"""

AUDITOR_PROMPT = """\
You are an independent AML Compliance Auditor.  You did NOT write the report \
you are reviewing.

You have access to:
1. The Analyst's risk assessment.
2. The RAW quantitative data from the Forensics tool.
3. The RAW news articles from the search tool.
4. The News Scout's structured extractions.

## Audit Checklist

- Does the Analyst's risk_score match the raw evidence?
- Did the Analyst address ALL risk flags from the quantitative data?
- Did the Analyst consider ALL claims from the news articles?
- Did the News Scout miss any claims from the raw articles?  If the Scout \
missed something, did the Analyst catch it anyway?
- Are there any discrepancies between what the Analyst claims and what the \
raw data shows?
- If no automated risk flags fired, did the Analyst still check the \
qualitative evidence for adverse intelligence?

## Rules

- You are an independent check.  Do NOT defer to the Analyst's judgment.
- If the report contradicts the raw tool output, REJECT.
- If the report ignores evidence (quantitative OR qualitative), REJECT.
- If the report is thorough and consistent with all raw data, APPROVE.
- Provide an adjusted_risk_score reflecting YOUR independent assessment.
- Cite specific data points from the raw outputs to support your decision.
"""

REVISION_PROMPT = """\
You are a Senior AML Analyst.  Your previous risk assessment was REJECTED \
by a reviewer.

You have access to:
1. Your original assessment.
2. The reviewer's feedback (including specific citations from the raw data).
3. The RAW quantitative data from the Forensics tool.
4. The RAW news articles from the search tool.
5. The News Scout's structured extractions.

## Instructions

- Carefully read the reviewer's objections and citations.
- Re-examine the raw data in light of the feedback.
- Write a REVISED risk assessment that addresses every point raised.
- You MAY maintain your original score if you can justify it against the \
reviewer's specific citations.  But you must explain why.
- Do NOT simply capitulate.  Use the evidence to reach the best conclusion.
"""


# ---------------------------------------------------------------------------
# Node: Forensics Scout (deterministic)
# ---------------------------------------------------------------------------
def forensics_scout_node(state: AgentState) -> dict:
    """Call tool_analyze_transactions and store the raw output."""
    result = tool_analyze_transactions(state["client_id"])
    return {"forensics_output": result}


# ---------------------------------------------------------------------------
# Node: News Scout (LLM -- fact extraction)
# ---------------------------------------------------------------------------
def news_scout_node(state: AgentState, config: RunnableConfig) -> dict:
    """Call tool_search_news, then use the LLM to extract structured facts."""
    raw_news = tool_search_news(state["client_id"])

    llm = get_llm().with_structured_output(NewsSummary)
    summary: NewsSummary = llm.invoke([
        {"role": "system", "content": NEWS_SCOUT_PROMPT},
        {"role": "user", "content": (
            f"Extract factual claims from the following intelligence report.\n\n"
            f"{raw_news}"
        )},
    ], config=config)

    return {
        "news_output": raw_news,
        "news_summary": summary.model_dump(),
    }


# ---------------------------------------------------------------------------
# Node: Analyst (LLM -- risk assessment)
# ---------------------------------------------------------------------------
def analyst_node(state: AgentState, config: RunnableConfig) -> dict:
    """Synthesise forensics + news into a structured risk assessment."""
    llm = get_llm().with_structured_output(AnalystOutput)

    news_summary_str = _format_news_summary(state["news_summary"])

    output: AnalystOutput = llm.invoke([
        {"role": "system", "content": ANALYST_PROMPT},
        {"role": "user", "content": (
            f"## Quantitative Metrics (Source of Truth)\n\n"
            f"{state['forensics_output']}\n\n"
            f"## Qualitative Intelligence (News Scout Extractions)\n\n"
            f"{news_summary_str}\n\n"
            f"Produce your risk assessment for client {state['client_id']}."
        )},
    ], config=config)

    return {"analyst_output": output.model_dump()}


# ---------------------------------------------------------------------------
# Node: Self-Review (LLM -- intrinsic governance)
# ---------------------------------------------------------------------------
def self_review_node(state: AgentState, config: RunnableConfig) -> dict:
    """The Analyst reviews its own report against the raw data."""
    llm = get_llm().with_structured_output(ReviewOutput)

    output: ReviewOutput = llm.invoke([
        {"role": "system", "content": SELF_REVIEW_PROMPT},
        {"role": "user", "content": _build_review_context(state)},
    ], config=config)

    return {
        "review_output": output.model_dump(),
        "review_decision": output.decision,
    }


# ---------------------------------------------------------------------------
# Node: Auditor (LLM -- hierarchical governance)
# ---------------------------------------------------------------------------
def auditor_node(state: AgentState, config: RunnableConfig) -> dict:
    """An independent Auditor reviews the Analyst's report against raw data."""
    llm = get_llm().with_structured_output(ReviewOutput)

    output: ReviewOutput = llm.invoke([
        {"role": "system", "content": AUDITOR_PROMPT},
        {"role": "user", "content": _build_review_context(state)},
    ], config=config)

    return {
        "review_output": output.model_dump(),
        "review_decision": output.decision,
    }


# ---------------------------------------------------------------------------
# Node: Revision (LLM -- Analyst rewrites after rejection)
# ---------------------------------------------------------------------------
def revision_node(state: AgentState, config: RunnableConfig) -> dict:
    """Analyst revises its report based on reviewer feedback."""
    llm = get_llm().with_structured_output(AnalystOutput)

    review = state["review_output"]
    news_summary_str = _format_news_summary(state["news_summary"])
    analyst_str = _format_analyst_output(state["analyst_output"])

    output: AnalystOutput = llm.invoke([
        {"role": "system", "content": REVISION_PROMPT},
        {"role": "user", "content": (
            f"## Your Original Assessment\n\n"
            f"{analyst_str}\n\n"
            f"## Reviewer Feedback\n\n"
            f"Decision: {review['decision']}\n"
            f"Adjusted Score: {review['adjusted_risk_score']}\n"
            f"Reasoning: {review['reasoning']}\n"
            f"Citations:\n" +
            "\n".join(f"  - {c}" for c in review["citations"]) +
            f"\n\n## RAW Quantitative Data\n\n"
            f"{state['forensics_output']}\n\n"
            f"## RAW News Articles\n\n"
            f"{state['news_output']}\n\n"
            f"## News Scout Extractions\n\n"
            f"{news_summary_str}\n\n"
            f"Write your REVISED risk assessment for client {state['client_id']}."
        )},
    ], config=config)

    return {
        "analyst_output": output.model_dump(),
        "revision_count": state.get("revision_count", 0) + 1,
    }


# ---------------------------------------------------------------------------
# Node: Finalise (deterministic)
# ---------------------------------------------------------------------------
def finalise_node(state: AgentState) -> dict:
    """Copy the approved Analyst output to the final fields.

    If the review provided an adjusted score, use that instead.
    """
    review = state.get("review_output", {})
    analyst = state["analyst_output"]

    # If reviewer adjusted the score and approved, use reviewer's score
    if review.get("decision") == "APPROVE" and review.get("adjusted_risk_score") is not None:
        final_score = review["adjusted_risk_score"]
    else:
        final_score = analyst["risk_score"]

    # Determine label from score
    if final_score <= 30:
        label = "low"
    elif final_score <= 69:
        label = "medium"
    else:
        label = "high"

    return {
        "final_output": {
            "risk_score": final_score,
            "risk_label": label,
            "confidence": analyst["confidence"],
            "reasoning": analyst["reasoning"],
        }
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _format_news_summary(summary: dict) -> str:
    """Format a NewsSummary dict into readable text for the LLM."""
    lines = [f"Articles Found: {summary['articles_found']}"]
    for i, ext in enumerate(summary["extractions"], 1):
        lines.append(f"\n  Article {i}: {ext['headline']}")
        lines.append(f"  Source: {ext['source']}")
        lines.append("  Claims:")
        for claim in ext["claims"]:
            lines.append(f"    - {claim}")
    return "\n".join(lines)


def _format_analyst_output(output: dict) -> str:
    """Format an AnalystOutput dict into readable text."""
    return (
        f"Risk Score: {output['risk_score']}/100 ({output['risk_label']})\n"
        f"Confidence: {output['confidence']}/100\n"
        f"Reasoning: {output['reasoning']}"
    )


def _build_review_context(state: AgentState) -> str:
    """Build the full context string for review nodes.

    Both self_review_node and auditor_node receive IDENTICAL information.
    The only difference is the system prompt (own work vs. independent audit).
    """
    analyst_str = _format_analyst_output(state["analyst_output"])
    news_summary_str = _format_news_summary(state["news_summary"])

    return (
        f"## Analyst's Risk Assessment (Under Review)\n\n"
        f"{analyst_str}\n\n"
        f"## RAW Quantitative Data (Source of Truth)\n\n"
        f"{state['forensics_output']}\n\n"
        f"## RAW News Articles (Full Text)\n\n"
        f"{state['news_output']}\n\n"
        f"## News Scout Extractions (Structured Summary)\n\n"
        f"{news_summary_str}\n\n"
        f"Review the Analyst's assessment for client {state['client_id']}."
    )
