"""
graph.py -- LangGraph graph construction for all governance modes.

Four graph variants share an identical Analyst node. Only the review step
differs, isolating the governance mechanism as the sole experimental variable:
  - Intrinsic:            self-review, no rules        (make_self_review_node())
  - Hierarchical:         independent auditor           (auditor_node)
  - Context-Engineered:   self-review + Kayba rules    (make_self_review_node(kayba))
  - LLM-Context:          self-review + LLM rules      (make_self_review_node(llm))

Rules are injected into the self-review user message, not the Analyst system
prompt. The Analyst produces the same initial report in all modes.

  context_engineered reads:  external_agent_injection.txt
  llm_context reads:         llm_context_rules.txt

Usage:
    from graph import build_graph

    app = build_graph("intrinsic")   # or "hierarchical" / "context_engineered" / "llm_context"
    result = app.invoke({"client_id": "C1234", "revision_count": 0})
"""

from __future__ import annotations

import os
from pathlib import Path

from langgraph.graph import END, StateGraph

from agents import (
    auditor_node,
    finalise_node,
    forensics_scout_node,
    make_analyst_node,
    make_revision_node,
    make_self_review_node,
    news_scout_node,
)
from state import AgentState

MAX_REVISIONS = 2


def _model_artefact_path(prefix: str) -> Path:
    """Return a model-specific artefact path, falling back to the generic name.

    E.g. for LLM_MODEL=gpt-4o-mini and prefix='external_agent_injection':
      tries  external_agent_injection_gpt-4o-mini.txt  first,
      falls back to  external_agent_injection.txt  if not found.
    """
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    specific = Path(f"{prefix}_{model}.txt")
    return specific if specific.exists() else Path(f"{prefix}.txt")

VALID_MODES = ("intrinsic", "hierarchical", "context_engineered", "llm_context")


def _should_revise(state: AgentState) -> str:
    """Conditional edge: route to revision or finalise after review."""
    if (
        state.get("review_decision") == "REJECT"
        and state.get("revision_count", 0) < MAX_REVISIONS
    ):
        return "revision"
    return "finalise"


def build_graph(mode: str) -> StateGraph:
    """Build and compile the LangGraph graph for the given governance mode.

    Args:
        mode: One of "intrinsic", "hierarchical", "context_engineered", or "llm_context".

    Returns:
        A compiled LangGraph application ready to .invoke().

    Raises:
        ValueError: If mode is not one of the supported values.
        FileNotFoundError: If mode is "context_engineered" and the skillbook
            file (external_agent_injection.txt) does not exist.
    """
    if mode not in VALID_MODES:
        raise ValueError(
            f"Unknown mode: {mode!r}. Use one of: {', '.join(VALID_MODES)}."
        )

    # Load external context for modes that inject rules into the Analyst prompt
    extra_context = ""
    if mode == "context_engineered":
        path = _model_artefact_path("external_agent_injection")
        if not path.exists():
            raise FileNotFoundError(
                f"Skillbook not found at {path}. "
                "Run Kayba's agentic_system_prompting.py first to generate it."
            )
        extra_context = path.read_text(encoding="utf-8")
    elif mode == "llm_context":
        path = _model_artefact_path("llm_context_rules")
        if not path.exists():
            raise FileNotFoundError(
                f"LLM-Context rules not found at {path}. "
                "Run 05_generate_llm_context_rules.py first to generate it."
            )
        extra_context = path.read_text(encoding="utf-8")

    # The analyst is identical across all modes — rules are NOT injected here.
    # Only the review step differs, isolating the governance mechanism.
    analyst_fn = make_analyst_node()
    revision_fn = make_revision_node()

    # Select review node: hierarchical uses an independent auditor; all other
    # modes use self-review. For context_engineered and llm_context, the rules
    # are injected into the self-review user message (extra_context != "").
    review_fn = auditor_node if mode == "hierarchical" else make_self_review_node(extra_context)

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("dispatch", lambda state: {})  # fan-out entry point
    graph.add_node("forensics_scout", forensics_scout_node)
    graph.add_node("news_scout", news_scout_node)
    graph.add_node("analyst", analyst_fn)
    graph.add_node("review", review_fn)
    graph.add_node("revision", revision_fn)
    graph.add_node("finalise", finalise_node)

    # Parallel scouts: dispatch fans out to both, analyst joins when both complete
    graph.set_entry_point("dispatch")
    graph.add_edge("dispatch", "forensics_scout")
    graph.add_edge("dispatch", "news_scout")
    graph.add_edge("forensics_scout", "analyst")
    graph.add_edge("news_scout", "analyst")
    graph.add_edge("analyst", "review")

    # Conditional: review → revision (if REJECT + under cap) or finalise
    graph.add_conditional_edges("review", _should_revise)

    # Revision loops back to review
    graph.add_edge("revision", "review")

    # Finalise → END
    graph.add_edge("finalise", END)

    return graph.compile()
