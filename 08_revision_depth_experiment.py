"""
08_revision_depth_experiment.py -- Revision-depth ablation (intrinsic mode only).

Tests whether performance changes as MAX_REVISIONS increases beyond the
baseline of 2.  Runs intrinsic governance across a range of revision caps on
the test set, varying only the revision ceiling.

Completely self-contained: defines its own graph builder so no existing code
is modified.

Outputs:
  results/revision_depth/{model}/run_{run_id}/depth_{N}/{client_id}.json
  results/revision_depth/{model}/run_{run_id}/summary.csv

Usage:
    python 08_revision_depth_experiment.py                         # depths 0-10, gpt-4o-mini
    python 08_revision_depth_experiment.py --depths 0 2 5 10       # custom depths
    python 08_revision_depth_experiment.py --model gpt-4o-mini --run-id 1
    python 08_revision_depth_experiment.py --force                 # re-run from scratch

Cost note: depth=N means up to 2*(N+1) LLM calls per client (analyst + review
each loop).  Most clients APPROVE early so actual call counts are much lower.
Depths 0-10 add roughly 4-5x the cost of a single intrinsic run.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

import tools as _tools

load_dotenv()

BASE_RESULTS_DIR = Path("results") / "revision_depth"


# ---------------------------------------------------------------------------
# Graph builder — does NOT import from graph.py
# ---------------------------------------------------------------------------

def build_depth_graph(max_revisions: int):
    """Build an intrinsic graph with a configurable revision cap.

    Structurally identical to graph.py's intrinsic mode; only the revision
    cap differs.  Uses a closure so each compiled graph is independent and
    thread-safe.

    Args:
        max_revisions: Maximum revision loops allowed.  0 = no revisions,
            the analyst result is finalised after the first review regardless
            of decision.
    """
    from langgraph.graph import END, StateGraph

    from agents import (
        finalise_node,
        forensics_scout_node,
        make_analyst_node,
        make_revision_node,
        make_self_review_node,
        news_scout_node,
    )
    from state import AgentState

    _cap = max_revisions  # captured in closure — each graph instance has its own cap

    def _should_revise(state) -> str:
        if (
            state.get("review_decision") == "REJECT"
            and state.get("revision_count", 0) < _cap
        ):
            return "revision"
        return "finalise"

    graph = StateGraph(AgentState)
    graph.add_node("dispatch", lambda state: {})
    graph.add_node("forensics_scout", forensics_scout_node)
    graph.add_node("news_scout", news_scout_node)
    graph.add_node("analyst", make_analyst_node())
    graph.add_node("review", make_self_review_node(""))  # intrinsic, no injected rules
    graph.add_node("revision", make_revision_node())
    graph.add_node("finalise", finalise_node)

    graph.set_entry_point("dispatch")
    graph.add_edge("dispatch", "forensics_scout")
    graph.add_edge("dispatch", "news_scout")
    graph.add_edge("forensics_scout", "analyst")
    graph.add_edge("news_scout", "analyst")
    graph.add_edge("analyst", "review")
    graph.add_conditional_edges("review", _should_revise)
    graph.add_edge("revision", "review")
    graph.add_edge("finalise", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _depth_col(n: int, suffix: str) -> str:
    return f"d{n}_{suffix}"


def _build_summary_columns(depths: list[int]) -> list[str]:
    max_depth = max(depths)
    cols = ["client_id", "model"]
    for n in depths:
        cols += [
            _depth_col(n, "initial_score"),
            _depth_col(n, "score"),
            _depth_col(n, "confidence"),
            _depth_col(n, "review_decision"),
            _depth_col(n, "revision_count"),
        ]
        # Track per-revision scores up to this depth's cap
        for r in range(1, max_depth + 1):
            cols.append(_depth_col(n, f"score_rev{r}"))
    return cols


def _get_results_dir(model: str, run_id: str) -> Path:
    return BASE_RESULTS_DIR / model / f"run_{run_id}"


def _get_summary_file(model: str, run_id: str) -> Path:
    return _get_results_dir(model, run_id) / "summary.csv"


def _ensure_dirs(model: str, run_id: str, depths: list[int]) -> None:
    for n in depths:
        (_get_results_dir(model, run_id) / f"depth_{n}").mkdir(parents=True, exist_ok=True)


def _save_state(model: str, run_id: str, depth: int, client_id: str, state: dict) -> None:
    path = _get_results_dir(model, run_id) / f"depth_{depth}" / f"{client_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)


def _append_summary_row(summary_file: Path, columns: list[str], row: dict) -> None:
    write_header = not summary_file.exists() or summary_file.stat().st_size == 0
    with open(summary_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _deduplicate_summary(summary_file: Path, columns: list[str]) -> None:
    """Merge duplicate rows per client_id, keeping the best (non-ERROR) value per column.

    Root cause: when a depth errors mid-run, the row is written with ERROR in that
    depth's review_decision.  On restart, _load_completed_clients excludes that client,
    so it re-runs and appends a second row.  This function merges duplicates so only
    the cleanest data survives into the next run.
    """
    if not summary_file.exists():
        return
    df = pd.read_csv(summary_file, dtype=str)
    n_before = len(df)
    if not df.duplicated("client_id").any():
        return

    def _best_value(series: pd.Series) -> object:
        """Return first non-empty, non-ERROR value; fall back to ERROR, then last."""
        for v in series:
            if pd.notna(v) and str(v).strip() not in ("", "nan", "ERROR"):
                return v
        for v in series:
            if pd.notna(v) and str(v).strip() == "ERROR":
                return v
        return series.iloc[-1]

    merged = (
        df.groupby("client_id", sort=False)
        .agg(_best_value)
        .reset_index()
    )
    # Restore original column order
    merged = merged.reindex(columns=[c for c in columns if c in merged.columns])
    merged.to_csv(summary_file, index=False)
    print(f"  Deduped summary.csv: {n_before} rows -> {len(merged)} rows "
          f"({n_before - len(merged)} duplicates removed)\n")


def _load_completed_clients(summary_file: Path, depths: list[int]) -> set[str]:
    if not summary_file.exists():
        return set()
    review_cols = [_depth_col(n, "review_decision") for n in depths]
    with open(summary_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        completed = set()
        for row in reader:
            if all(row.get(col, "") not in ("", "ERROR") for col in review_cols):
                completed.add(row["client_id"])
    return completed


def _extract_summary(state: dict, max_depth: int) -> dict:
    final = state.get("final_output", {})
    initial = state.get("initial_analyst_output", {})
    history = state.get("revision_history", [])
    revision_scores = {
        f"score_rev{r}": history[r - 1].get("risk_score") if r <= len(history) else None
        for r in range(1, max_depth + 1)
    }
    return {
        "initial_score": initial.get("risk_score"),
        "score": final.get("risk_score"),
        "confidence": final.get("confidence"),
        "review_decision": state.get("review_decision", ""),
        "revision_count": state.get("revision_count", 0),
        **revision_scores,
    }


def _create_langfuse_handler(client_id: str, depth: int):
    if not os.getenv("LANGFUSE_SECRET_KEY"):
        return None
    from langfuse.langchain import CallbackHandler
    return CallbackHandler(
        trace_context={
            "name": f"depth_{depth}/{client_id}",
            "session_id": f"{client_id}_depth_{depth}",
            "metadata": {"client_id": client_id, "depth": depth},
            "tags": [f"depth_{depth}", client_id],
        },
    )


def _run_single(client_id: str, depth: int, app) -> dict:
    import openai

    handler = _create_langfuse_handler(client_id, depth)
    config = {"callbacks": [handler]} if handler else {}

    wait = 30
    for attempt in range(4):
        try:
            result = app.invoke(
                {"client_id": client_id, "revision_count": 0},
                config=config,
            )
            return dict(result)
        except openai.RateLimitError:
            if attempt == 3:
                raise
            print(
                f"       [rate limit] {client_id}/depth_{depth} — "
                f"waiting {wait}s (attempt {attempt + 1}/3)"
            )
            time.sleep(wait)
            wait *= 2


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Revision-depth ablation: intrinsic mode with varying MAX_REVISIONS."
    )
    parser.add_argument(
        "--depths",
        nargs="+",
        type=int,
        default=list(range(11)),  # 0–10
        help="Revision caps to test (default: 0 1 2 3 4 5 6 7 8 9 10).",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        help="LLM model (default: LLM_MODEL env or gpt-4o-mini).",
    )
    parser.add_argument(
        "--run-id",
        default="1",
        help="Replicate identifier (default: 1).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Parallel client workers (default: 3).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run all clients, ignoring previous results.",
    )
    args = parser.parse_args()

    depths = sorted(set(args.depths))
    model = args.model
    run_id = args.run_id
    max_depth = max(depths)

    os.environ["LLM_MODEL"] = model
    _tools.configure_dataset("test_")

    client_list_file = Path("test_client_list.csv")
    if not client_list_file.exists():
        print("ERROR: test_client_list.csv not found. Run 01_build_dataset.py --dataset test first.")
        sys.exit(1)

    client_ids = pd.read_csv(client_list_file)["client_id"].tolist()
    total = len(client_ids)

    summary_file = _get_summary_file(model, run_id)
    summary_columns = _build_summary_columns(depths)

    _ensure_dirs(model, run_id, depths)

    if args.force:
        if summary_file.exists():
            summary_file.unlink()
        completed = set()
    else:
        _deduplicate_summary(summary_file, summary_columns)
        completed = _load_completed_clients(summary_file, depths)
        if completed:
            print(f"Resuming: {len(completed)}/{total} clients already complete.\n")

    if os.getenv("LANGFUSE_SECRET_KEY"):
        print("Langfuse tracing: ENABLED\n")
    else:
        print("Langfuse tracing: disabled\n")

    print(
        f"Model: {model}  |  Run: {run_id}  |  Depths: {depths}  |  "
        f"Clients: {total}  |  Workers: {args.workers}\n"
    )

    # Compile one graph per depth (each has its own _cap closure)
    apps: dict[int, object] = {}
    for n in depths:
        print(f"  Building graph: max_revisions={n} ...")
        apps[n] = build_depth_graph(n)
    print()

    csv_lock = threading.Lock()
    counter_lock = threading.Lock()
    clients_run = 0
    experiment_start = time.time()

    def _process_client(cid: str, position: int) -> None:
        nonlocal clients_run
        client_start = time.time()
        print(f"[{position:>3}/{total}] {cid}  starting")

        summaries: dict[int, dict] = {}

        for n in depths:
            try:
                state = _run_single(cid, n, apps[n])
                _save_state(model, run_id, n, cid, state)
                s = _extract_summary(state, max_depth)
                print(
                    f"       {cid}  depth={n:<2}  "
                    f"initial={str(s['initial_score']):>3}  "
                    f"final={str(s['score']):>3}  "
                    f"review={s['review_decision']:<7}  "
                    f"revisions={s['revision_count']}"
                )
            except Exception as e:
                err = str(e)
                print(f"       {cid}  depth={n:<2}  ERROR — {err}")
                _save_state(model, run_id, n, cid, {"client_id": cid, "error": err})
                s = {
                    "initial_score": None, "score": None, "confidence": None,
                    "review_decision": "ERROR", "revision_count": 0,
                    **{f"score_rev{r}": None for r in range(1, max_depth + 1)},
                }
            summaries[n] = s

        row: dict = {"client_id": cid, "model": model}
        for n in depths:
            s = summaries[n]
            row[_depth_col(n, "initial_score")] = s["initial_score"]
            row[_depth_col(n, "score")] = s["score"]
            row[_depth_col(n, "confidence")] = s["confidence"]
            row[_depth_col(n, "review_decision")] = s["review_decision"]
            row[_depth_col(n, "revision_count")] = s["revision_count"]
            for r in range(1, max_depth + 1):
                row[_depth_col(n, f"score_rev{r}")] = s.get(f"score_rev{r}")

        with csv_lock:
            _append_summary_row(summary_file, summary_columns, row)

        elapsed = time.time() - client_start
        with counter_lock:
            clients_run += 1
            done = clients_run
        total_elapsed = time.time() - experiment_start
        avg_per_client = total_elapsed / done
        remaining = (total - len(completed) - done) * avg_per_client
        print(
            f"       {cid}  done  {elapsed:.1f}s  |  "
            f"avg {avg_per_client:.1f}s/client  |  "
            f"~{remaining / 60:.0f}m remaining\n"
        )

    pending = [(cid, i) for i, cid in enumerate(client_ids, 1) if cid not in completed]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_process_client, cid, pos): cid for cid, pos in pending}
        for future in as_completed(futures):
            cid = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"[FATAL] {cid} — {e}")

    total_elapsed = time.time() - experiment_start
    print("=" * 60)
    print(
        f"Experiment complete: {clients_run} clients run in "
        f"{total_elapsed / 60:.1f} minutes."
    )
    print(f"Results:  {summary_file}")
    print(f"Details:  {_get_results_dir(model, run_id)}/depth_{{N}}/")
    print(f"\nRun 09_analyze_revision_depth.py to see accuracy by depth.")

    # Quick stats
    if summary_file.exists():
        df = pd.read_csv(summary_file)
        print()
        for n in depths:
            score_col = _depth_col(n, "score")
            review_col = _depth_col(n, "review_decision")
            rev_col = _depth_col(n, "revision_count")
            if score_col not in df.columns:
                continue
            valid = df.dropna(subset=[score_col])
            if len(valid) == 0:
                continue
            consensus = (valid[review_col] == "APPROVE").mean() if review_col in valid.columns else float("nan")
            avg_rev = valid[rev_col].mean() if rev_col in valid.columns else float("nan")
            errors = (df.get(review_col, pd.Series()) == "ERROR").sum()
            print(
                f"  depth={n:<2}  ({len(valid):>3} complete)  "
                f"avg_score={valid[score_col].mean():>5.1f}  "
                f"consensus={consensus:>4.0%}  "
                f"avg_revisions={avg_rev:.2f}"
                + (f"  errors={errors}" if errors else "")
            )


if __name__ == "__main__":
    main()
