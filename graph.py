"""
graph.py -- LangGraph graph construction for both governance modes.

Two graph variants share identical nodes except for the review step:
  - Intrinsic:    Analyst reviews its own work  (self_review_node)
  - Hierarchical: Independent Auditor reviews   (auditor_node)

Both reviewers receive IDENTICAL data.  The only variable is the persona.

Usage:
    from graph import build_graph

    app = build_graph("intrinsic")   # or "hierarchical"
    result = app.invoke({"client_id": "C1234", "revision_count": 0})
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from agents import (
    analyst_node,
    auditor_node,
    finalise_node,
    forensics_scout_node,
    news_scout_node,
    revision_node,
    self_review_node,
)
from state import AgentState

MAX_REVISIONS = 2


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
        mode: Either "intrinsic" or "hierarchical".

    Returns:
        A compiled LangGraph application ready to .invoke().
    """
    if mode not in ("intrinsic", "hierarchical"):
        raise ValueError(f"Unknown mode: {mode!r}. Use 'intrinsic' or 'hierarchical'.")

    # Select the review node based on mode
    review_fn = self_review_node if mode == "intrinsic" else auditor_node

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("dispatch", lambda state: {})  # fan-out entry point
    graph.add_node("forensics_scout", forensics_scout_node)
    graph.add_node("news_scout", news_scout_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("review", review_fn)
    graph.add_node("revision", revision_node)
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
