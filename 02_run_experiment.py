"""
02_run_experiment.py -- Run the AML governance experiment.

Invokes the LangGraph pipeline for all 50 clients in both governance modes
(intrinsic and hierarchical).  Results are saved incrementally so that a
crash mid-run loses at most one client's work.

Langfuse tracing is enabled automatically when LANGFUSE_SECRET_KEY is set
in the environment (or .env file).  Every LLM call is traced with the
client_id and governance mode as metadata.

Outputs:
  results/intrinsic/{client_id}.json   -- full AgentState per client
  results/hierarchical/{client_id}.json
  results/summary.csv                  -- wide-format paired comparison (streamed)

Usage:
    python 02_run_experiment.py            # resumable (skips completed clients)
    python 02_run_experiment.py --force    # re-run everything from scratch
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from graph import build_graph

# Load .env before anything else
load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CLIENT_LIST_FILE = Path("client_list.csv")
RESULTS_DIR = Path("results")
SUMMARY_FILE = RESULTS_DIR / "summary.csv"

SUMMARY_COLUMNS = [
    "client_id",
    "int_score",
    "int_confidence",
    "int_review_decision",
    "int_revision_count",
    "hier_score",
    "hier_confidence",
    "hier_review_decision",
    "hier_revision_count",
    "score_delta",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_completed_clients() -> set[str]:
    """Return client IDs already present in summary.csv."""
    if not SUMMARY_FILE.exists():
        return set()
    with open(SUMMARY_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["client_id"] for row in reader}


def _ensure_dirs() -> None:
    """Create output directories if they don't exist."""
    (RESULTS_DIR / "intrinsic").mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "hierarchical").mkdir(parents=True, exist_ok=True)


def _save_state(mode: str, client_id: str, state: dict) -> None:
    """Write the full AgentState dict to a JSON file."""
    path = RESULTS_DIR / mode / f"{client_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)


def _append_summary_row(row: dict) -> None:
    """Append a single row to the summary CSV, writing the header if needed."""
    write_header = not SUMMARY_FILE.exists() or SUMMARY_FILE.stat().st_size == 0
    with open(SUMMARY_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _extract_summary(state: dict) -> dict:
    """Pull the fields we need for the summary row from a final state."""
    final = state.get("final_output", {})
    review = state.get("review_output", {})
    return {
        "score": final.get("risk_score"),
        "confidence": final.get("confidence"),
        "review_decision": state.get("review_decision", ""),
        "revision_count": state.get("revision_count", 0),
    }


def _create_langfuse_handler(
    client_id: str, mode: str
):
    """Create a Langfuse callback handler if credentials are configured.

    Returns None if Langfuse is not set up (the experiment still runs,
    just without tracing).
    """
    if not os.getenv("LANGFUSE_SECRET_KEY"):
        return None

    from langfuse.langchain import CallbackHandler

    return CallbackHandler(
        trace_context={
            "name": f"{mode}/{client_id}",
            "session_id": f"{client_id}_{mode}",
            "metadata": {"client_id": client_id, "mode": mode},
            "tags": [mode, client_id],
        },
    )


def _run_single(client_id: str, mode: str, app) -> dict:
    """Invoke the graph for one client and return the final state."""
    handler = _create_langfuse_handler(client_id, mode)
    config = {"callbacks": [handler]} if handler else {}
    result = app.invoke(
        {"client_id": client_id, "revision_count": 0},
        config=config,
    )
    return dict(result)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AML governance experiment.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run all clients, ignoring previous results.",
    )
    args = parser.parse_args()

    # Load client list
    client_ids = pd.read_csv(CLIENT_LIST_FILE)["client_id"].tolist()
    total = len(client_ids)

    # Set up output dirs
    _ensure_dirs()

    # Check what's already done
    if args.force:
        # Wipe summary CSV so we start fresh (JSON files get overwritten)
        if SUMMARY_FILE.exists():
            SUMMARY_FILE.unlink()
        completed = set()
    else:
        completed = _load_completed_clients()
        if completed:
            print(f"Resuming: {len(completed)}/{total} clients already complete.\n")

    # Check Langfuse status
    if os.getenv("LANGFUSE_SECRET_KEY"):
        print("Langfuse tracing: ENABLED\n")
    else:
        print("Langfuse tracing: disabled (set LANGFUSE_SECRET_KEY to enable)\n")

    # Compile both graphs once
    app_intrinsic = build_graph("intrinsic")
    app_hierarchical = build_graph("hierarchical")

    experiment_start = time.time()
    clients_run = 0

    for i, cid in enumerate(client_ids, 1):
        if cid in completed:
            continue

        client_start = time.time()
        print(f"[{i:>2}/{total}] {cid}")

        # ── Intrinsic mode ──
        int_state = None
        int_error = None
        try:
            int_state = _run_single(cid, "intrinsic", app_intrinsic)
            _save_state("intrinsic", cid, int_state)
            int_summary = _extract_summary(int_state)
            print(f"       intrinsic:    score={int_summary['score']:>3}  "
                  f"review={int_summary['review_decision']:<7}  "
                  f"revisions={int_summary['revision_count']}")
        except Exception as e:
            int_error = str(e)
            print(f"       intrinsic:    ERROR - {int_error}")
            _save_state("intrinsic", cid, {"client_id": cid, "error": int_error})
            int_summary = {"score": None, "confidence": None,
                           "review_decision": "ERROR", "revision_count": 0}

        # ── Hierarchical mode ──
        hier_state = None
        hier_error = None
        try:
            hier_state = _run_single(cid, "hierarchical", app_hierarchical)
            _save_state("hierarchical", cid, hier_state)
            hier_summary = _extract_summary(hier_state)
            print(f"       hierarchical: score={hier_summary['score']:>3}  "
                  f"review={hier_summary['review_decision']:<7}  "
                  f"revisions={hier_summary['revision_count']}")
        except Exception as e:
            hier_error = str(e)
            print(f"       hierarchical: ERROR - {hier_error}")
            _save_state("hierarchical", cid, {"client_id": cid, "error": hier_error})
            hier_summary = {"score": None, "confidence": None,
                            "review_decision": "ERROR", "revision_count": 0}

        # ── Compute delta and stream to CSV ──
        if int_summary["score"] is not None and hier_summary["score"] is not None:
            delta = hier_summary["score"] - int_summary["score"]
        else:
            delta = None

        _append_summary_row({
            "client_id": cid,
            "int_score": int_summary["score"],
            "int_confidence": int_summary["confidence"],
            "int_review_decision": int_summary["review_decision"],
            "int_revision_count": int_summary["revision_count"],
            "hier_score": hier_summary["score"],
            "hier_confidence": hier_summary["confidence"],
            "hier_review_decision": hier_summary["review_decision"],
            "hier_revision_count": hier_summary["revision_count"],
            "score_delta": delta,
        })

        elapsed = time.time() - client_start
        clients_run += 1
        total_elapsed = time.time() - experiment_start
        avg_per_client = total_elapsed / clients_run
        remaining = (total - len(completed) - clients_run) * avg_per_client

        print(f"       {elapsed:.1f}s  |  "
              f"avg {avg_per_client:.1f}s/client  |  "
              f"~{remaining / 60:.0f}m remaining\n")

    # ── Final summary ──
    total_elapsed = time.time() - experiment_start
    print("=" * 60)
    print(f"Experiment complete: {clients_run} clients run in "
          f"{total_elapsed / 60:.1f} minutes.")
    print(f"Results: {SUMMARY_FILE}")
    print(f"Details: {RESULTS_DIR}/intrinsic/ and {RESULTS_DIR}/hierarchical/")

    # Quick stats if we have data
    if SUMMARY_FILE.exists():
        df = pd.read_csv(SUMMARY_FILE)
        valid = df.dropna(subset=["int_score", "hier_score"])
        if len(valid) > 0:
            print(f"\n--- Quick Stats ({len(valid)} complete pairs) ---")
            print(f"  Intrinsic    avg score: {valid['int_score'].mean():.1f}")
            print(f"  Hierarchical avg score: {valid['hier_score'].mean():.1f}")
            print(f"  Mean delta (hier - int): {valid['score_delta'].mean():+.1f}")
            print(f"  Clients with delta != 0: "
                  f"{(valid['score_delta'] != 0).sum()}/{len(valid)}")
        errors = df[df["int_review_decision"] == "ERROR"].shape[0] + \
                 df[df["hier_review_decision"] == "ERROR"].shape[0]
        if errors:
            print(f"  Errors: {errors} (check JSON files for details)")


if __name__ == "__main__":
    main()
