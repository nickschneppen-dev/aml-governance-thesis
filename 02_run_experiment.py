"""
02_run_experiment.py -- Run the AML governance experiment.

Invokes the LangGraph pipeline for all 50 clients in one or more governance
modes.  Results are saved incrementally so that a crash mid-run loses at most
one client's work.

Langfuse tracing is enabled automatically when LANGFUSE_SECRET_KEY is set
in the environment (or .env file).  Every LLM call is traced with the
client_id and governance mode as metadata.

Outputs:
  results/{dataset}/{mode}/{client_id}.json   -- full AgentState per client
  results/{dataset}/summary.csv              -- wide-format paired comparison (streamed)

Usage:
    python 02_run_experiment.py                         # test set, intrinsic + hierarchical
    python 02_run_experiment.py --dataset train --modes intrinsic
    python 02_run_experiment.py --modes intrinsic hierarchical context_engineered
    python 02_run_experiment.py --force                 # re-run everything from scratch
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

import tools as _tools
from graph import build_graph

# Load .env before anything else
load_dotenv()

# ---------------------------------------------------------------------------
# Mode configuration
# ---------------------------------------------------------------------------
# Short prefix used in CSV column names
MODE_PREFIX = {
    "intrinsic": "int",
    "hierarchical": "hier",
    "context_engineered": "ctx",
}

BASE_RESULTS_DIR = Path("results")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_results_dir(dataset: str) -> Path:
    return BASE_RESULTS_DIR / dataset


def _get_summary_file(dataset: str) -> Path:
    return _get_results_dir(dataset) / "summary.csv"


def _build_summary_columns(modes: list[str]) -> list[str]:
    """Build dynamic summary CSV column names for the given modes."""
    cols = ["client_id"]
    for mode in modes:
        p = MODE_PREFIX[mode]
        cols += [
            f"{p}_initial_score",
            f"{p}_score",
            f"{p}_confidence",
            f"{p}_review_decision",
            f"{p}_revision_count",
        ]
    # Add pairwise deltas
    for m1, m2 in itertools.combinations(modes, 2):
        p1, p2 = MODE_PREFIX[m1], MODE_PREFIX[m2]
        cols.append(f"{p1}_{p2}_delta")
    return cols


def _load_completed_clients(summary_file: Path, modes: list[str]) -> set[str]:
    """Return client IDs that completed successfully (at least one mode succeeded)."""
    if not summary_file.exists():
        return set()
    review_cols = [f"{MODE_PREFIX[m]}_review_decision" for m in modes]
    with open(summary_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        completed = set()
        for row in reader:
            # Keep client if any mode succeeded (not ERROR)
            if any(row.get(col, "ERROR") != "ERROR" for col in review_cols):
                completed.add(row["client_id"])
    return completed


def _ensure_dirs(dataset: str, modes: list[str]) -> None:
    """Create output directories if they don't exist."""
    results_dir = _get_results_dir(dataset)
    for mode in modes:
        (results_dir / mode).mkdir(parents=True, exist_ok=True)


def _save_state(dataset: str, mode: str, client_id: str, state: dict) -> None:
    """Write the full AgentState dict to a JSON file."""
    path = _get_results_dir(dataset) / mode / f"{client_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)


def _append_summary_row(summary_file: Path, columns: list[str], row: dict) -> None:
    """Append a single row to the summary CSV, writing the header if needed."""
    write_header = not summary_file.exists() or summary_file.stat().st_size == 0
    with open(summary_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _extract_summary(state: dict) -> dict:
    """Pull the fields we need for the summary row from a final state."""
    final = state.get("final_output", {})
    initial = state.get("initial_analyst_output", {})
    return {
        "initial_score": initial.get("risk_score"),
        "score": final.get("risk_score"),
        "confidence": final.get("confidence"),
        "review_decision": state.get("review_decision", ""),
        "revision_count": state.get("revision_count", 0),
    }


def _create_langfuse_handler(client_id: str, mode: str):
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
        "--dataset",
        choices=["train", "test"],
        default="test",
        help="Dataset split to run on (default: test). "
             "Selects {dataset}_client_list.csv, {dataset}_knowledge_base.json, etc.",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=list(MODE_PREFIX.keys()),
        default=["intrinsic", "hierarchical"],
        help="Governance modes to run (default: intrinsic hierarchical).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run all clients, ignoring previous results.",
    )
    args = parser.parse_args()

    dataset = args.dataset
    modes = args.modes
    summary_file = _get_summary_file(dataset)
    summary_columns = _build_summary_columns(modes)

    # Redirect tool file paths to the selected dataset
    _tools.configure_dataset(f"{dataset}_")

    client_list_file = Path(f"{dataset}_client_list.csv")
    if not client_list_file.exists():
        print(f"ERROR: {client_list_file} not found. Run 01_build_dataset.py first.")
        sys.exit(1)

    client_ids = pd.read_csv(client_list_file)["client_id"].tolist()
    total = len(client_ids)

    _ensure_dirs(dataset, modes)

    # Check what's already done
    if args.force:
        if summary_file.exists():
            summary_file.unlink()
        completed = set()
    else:
        completed = _load_completed_clients(summary_file, modes)
        if completed:
            print(f"Resuming: {len(completed)}/{total} clients already complete.\n")

    # Check Langfuse status
    if os.getenv("LANGFUSE_SECRET_KEY"):
        print("Langfuse tracing: ENABLED\n")
    else:
        print("Langfuse tracing: disabled (set LANGFUSE_SECRET_KEY to enable)\n")

    print(f"Dataset: {dataset}  |  Modes: {', '.join(modes)}  |  Clients: {total}\n")

    # Compile graphs once per mode
    apps: dict[str, object] = {}
    for mode in modes:
        print(f"Building graph: {mode} ...")
        apps[mode] = build_graph(mode)
    print()

    experiment_start = time.time()
    clients_run = 0

    for i, cid in enumerate(client_ids, 1):
        if cid in completed:
            continue

        client_start = time.time()
        print(f"[{i:>2}/{total}] {cid}")

        summaries: dict[str, dict] = {}

        for mode in modes:
            p = MODE_PREFIX[mode]
            try:
                state = _run_single(cid, mode, apps[mode])
                _save_state(dataset, mode, cid, state)
                s = _extract_summary(state)
                print(
                    f"       {mode:<22s} initial={s['initial_score']:>3}  "
                    f"final={s['score']:>3}  "
                    f"review={s['review_decision']:<7}  "
                    f"revisions={s['revision_count']}"
                )
            except Exception as e:
                err = str(e)
                print(f"       {mode:<22s} ERROR - {err}")
                _save_state(dataset, mode, cid, {"client_id": cid, "error": err})
                s = {"score": None, "confidence": None,
                     "review_decision": "ERROR", "revision_count": 0}
            summaries[mode] = s

        # Build CSV row
        row: dict = {"client_id": cid}
        for mode in modes:
            p = MODE_PREFIX[mode]
            s = summaries[mode]
            row[f"{p}_initial_score"] = s["initial_score"]
            row[f"{p}_score"] = s["score"]
            row[f"{p}_confidence"] = s["confidence"]
            row[f"{p}_review_decision"] = s["review_decision"]
            row[f"{p}_revision_count"] = s["revision_count"]

        # Pairwise deltas
        for m1, m2 in itertools.combinations(modes, 2):
            p1, p2 = MODE_PREFIX[m1], MODE_PREFIX[m2]
            s1, s2 = summaries[m1]["score"], summaries[m2]["score"]
            row[f"{p1}_{p2}_delta"] = (s2 - s1) if (s1 is not None and s2 is not None) else None

        _append_summary_row(summary_file, summary_columns, row)

        elapsed = time.time() - client_start
        clients_run += 1
        total_elapsed = time.time() - experiment_start
        avg_per_client = total_elapsed / clients_run
        remaining = (total - len(completed) - clients_run) * avg_per_client

        print(
            f"       {elapsed:.1f}s  |  "
            f"avg {avg_per_client:.1f}s/client  |  "
            f"~{remaining / 60:.0f}m remaining\n"
        )

    # ── Final summary ──
    total_elapsed = time.time() - experiment_start
    print("=" * 60)
    print(
        f"Experiment complete: {clients_run} clients run in "
        f"{total_elapsed / 60:.1f} minutes."
    )
    print(f"Results: {summary_file}")
    print(f"Details: {_get_results_dir(dataset)}/{{mode}}/")

    # Quick stats if we have data
    if summary_file.exists():
        df = pd.read_csv(summary_file)
        for mode in modes:
            p = MODE_PREFIX[mode]
            score_col = f"{p}_score"
            if score_col not in df.columns:
                continue
            valid = df.dropna(subset=[score_col])
            if len(valid) > 0:
                print(f"\n--- Quick Stats: {mode} ({len(valid)} complete) ---")
                print(f"  Avg score: {valid[score_col].mean():.1f}")
                review_col = f"{p}_review_decision"
                if review_col in valid.columns:
                    print(f"  Consensus rate: "
                          f"{(valid[review_col] == 'APPROVE').mean():.0%}")
            errors = (df.get(f"{p}_review_decision", pd.Series()) == "ERROR").sum()
            if errors:
                print(f"  Errors: {errors}")


if __name__ == "__main__":
    main()
