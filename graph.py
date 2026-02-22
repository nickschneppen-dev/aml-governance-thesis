"""
graph.py -- LangGraph graph construction for all governance modes.

Three graph variants share identical nodes except for the review step and
optional Analyst skillbook injection:
  - Intrinsic:            Analyst reviews its own work  (self_review_node)
  - Hierarchical:         Independent Auditor reviews   (auditor_node)
  - Context-Engineered:   Intrinsic + Kayba skillbook injected into Analyst

Both the intrinsic and context_engineered modes use self_review_node.
The only difference in context_engineered is the Analyst's system prompt,
which has the Kayba-generated Context Playbook appended.

The skillbook is read from external_agent_injection.txt at graph build time.
Run Kayba's agentic_system_prompting.py first to generate this file.

Usage:
    from graph import build_graph

    app = build_graph("intrinsic")          # or "hierarchical" / "context_engineered"
    result = app.invoke({"client_id": "C1234", "revision_count": 0})
"""

from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, StateGraph

from agents import (
    auditor_node,
    finalise_node,
    forensics_scout_node,
    make_analyst_node,
    make_revision_node,
    news_scout_node,
    self_review_node,
)
from state import AgentState

MAX_REVISIONS = 2
SKILLBOOK_PATH = Path("external_agent_injection.txt")

VALID_MODES = ("intrinsic", "hierarchical", "context_engineered")


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
        mode: One of "intrinsic", "hierarchical", or "context_engineered".

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

    # Load Kayba skillbook for context_engineered mode
    extra_context = ""
    if mode == "context_engineered":
        if not SKILLBOOK_PATH.exists():
            raise FileNotFoundError(
                f"Skillbook not found at {SKILLBOOK_PATH}. "
                "Run Kayba's agentic_system_prompting.py first to generate it."
            )
        extra_context = SKILLBOOK_PATH.read_text(encoding="utf-8")

    # Select review node: hierarchical uses independent auditor; both intrinsic
    # variants use self-review (the experimental variable is the Analyst's prompt)
    review_fn = auditor_node if mode == "hierarchical" else self_review_node

    # Build analyst and revision nodes (with optional skillbook injection)
    analyst_fn = make_analyst_node(extra_context)
    revision_fn = make_revision_node(extra_context)

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
