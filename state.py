"""
state.py -- State schema and structured output models for the AML agent system.

The AgentState TypedDict flows through the LangGraph graph.  Pydantic models
define the structured JSON that LLM agents must return -- ensuring deterministic
parsing for MLflow grading.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic models for structured LLM outputs
# ---------------------------------------------------------------------------

class ArticleExtraction(BaseModel):
    """A single article's factual extraction by the News Scout."""
    headline: str = Field(description="The article headline, verbatim.")
    source: str = Field(description="The publication or agency that published the article.")
    claims: list[str] = Field(
        description=(
            "A list of factual claims extracted from the article body. "
            "Each claim must be an objective statement of fact, NOT an opinion or risk judgment. "
            "Good: 'Individual named in AUSTRAC enforcement action.' "
            "Bad: 'Individual is clearly a money launderer.'"
        )
    )


class NewsSummary(BaseModel):
    """Structured output from the News Scout."""
    articles_found: int = Field(description="Number of articles returned by the search.")
    extractions: list[ArticleExtraction] = Field(
        description="Factual extraction for each article, in the order they appeared."
    )


class AnalystOutput(BaseModel):
    """Structured output from the Analyst."""
    risk_score: int = Field(
        ge=0, le=100,
        description=(
            "Numeric risk score from 0 (no risk) to 100 (certain laundering). "
            "Ranges: 0-30 = low, 31-69 = medium, 70-100 = high."
        ),
    )
    risk_label: str = Field(
        description="One of: 'low', 'medium', 'high'. Must match the risk_score range."
    )
    confidence: int = Field(
        ge=0, le=100,
        description="How confident you are in this assessment (0-100).",
    )
    reasoning: str = Field(
        description=(
            "A structured narrative explaining the risk assessment. "
            "Must reference specific quantitative metrics AND qualitative findings. "
            "Must explain how conflicting evidence was weighed."
        )
    )


class ReviewOutput(BaseModel):
    """Structured output from the Self-Review (Intrinsic) or Auditor (Hierarchical)."""
    decision: str = Field(
        description="Either 'APPROVE' or 'REJECT'. No other values allowed."
    )
    adjusted_risk_score: int = Field(
        ge=0, le=100,
        description=(
            "The reviewer's own risk score (0-100). If APPROVE, this may match "
            "the Analyst's score. If REJECT, this reflects the reviewer's "
            "corrected assessment."
        ),
    )
    reasoning: str = Field(
        description=(
            "Detailed justification for the decision. If REJECT, must cite "
            "specific discrepancies between the Analyst's report and the raw data."
        )
    )
    citations: list[str] = Field(
        description=(
            "Specific quotes or data points from the raw tool outputs that "
            "support the review decision. E.g., 'Raw data shows Fan-In=25 "
            "but Analyst report claims no network anomalies.'"
        )
    )


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    """State that flows through the LangGraph graph.

    Processed per-client: the graph is invoked once per client_id.
    """

    # ── Input ──
    client_id: str

    # ── Raw tool outputs (Source of Truth -- immutable after scouts) ──
    forensics_output: str   # verbatim return from tool_analyze_transactions
    news_output: str        # verbatim return from tool_search_news

    # ── News Scout interpretation ──
    news_summary: dict      # serialised NewsSummary

    # ── Analyst output ──
    initial_analyst_output: NotRequired[dict]  # first assessment, never overwritten by revision
    analyst_output: dict    # serialised AnalystOutput (latest — may be a revision)
    revision_history: NotRequired[list]  # list of AnalystOutput dicts, one per revision in order

    # ── Single-context conversation (intrinsic / context_engineered / llm_context) ──
    # The full message list from the analyst's API call, growing with each turn.
    # self_review_node and make_revision_node append to this list so that the
    # analyst, self-reviewer, and revisions all share one context window.
    # auditor_node does not use this field — hierarchical remains a separate call.
    analyst_conversation: NotRequired[list]

    # ── Governance review ──
    review_output: dict     # serialised ReviewOutput
    review_decision: str    # "APPROVE" or "REJECT" (extracted for routing)
    revision_count: int     # tracks how many times the Analyst has revised

    # ── Final output ──
    final_output: dict      # serialised AnalystOutput (the approved version)
