"""
10_cost_analysis.py — Real cost efficiency analysis using Langfuse token data.

Streams the Langfuse observations export (6+ GB) to extract actual inputUsage /
outputUsage per GENERATION call, links each trace to its (model, mode, client_id)
by fingerprint-matching against the local results JSONs, applies per-model pricing,
and reports:

  - Mean input / output / total tokens per case (model × mode)
  - Mean cost per case
  - F1 per dollar  (efficiency metric)
  - Cost per correct classification

Requires ijson:  pip install ijson

Usage:
    python 10_cost_analysis.py
    python 10_cost_analysis.py --run-id 1          # default
    python 10_cost_analysis.py --obs-file <path>   # override observations file
    python 10_cost_analysis.py --skip-stream       # skip streaming (use cached token index)
"""
from __future__ import annotations

import argparse
import csv
import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import ijson
import pandas as pd

# ---------------------------------------------------------------------------
# Per-model pricing: USD per 1 million tokens.
# Verify against current provider pricing before publishing.
# ---------------------------------------------------------------------------
PRICING: dict[str, dict[str, float]] = {
    # OpenAI  (https://openai.com/pricing)
    "gpt-4o-mini":              {"input": 0.150, "output": 0.600},
    "gpt-4o-mini-2024-07-18":   {"input": 0.150, "output": 0.600},
    "gpt-5.1":                  {"input": 1.25,  "output": 10.00},
    "gpt-5.1-2025-07-08":       {"input": 1.25,  "output": 10.00},
    # xAI Grok  (https://x.ai/api)
    "grok-4":                   {"input": 2.00,  "output": 6.00},
    "grok-4-0709":              {"input": 2.00,  "output": 6.00},
}

# Model name normalisation: API model string -> experiment model label
MODEL_NORM: dict[str, str] = {
    "gpt-4o-mini":              "gpt-4o-mini",
    "gpt-4o-mini-2024-07-18":   "gpt-4o-mini",
    "gpt-5.1":                  "gpt-5.1",
    "gpt-5.1-2025-07-08":       "gpt-5.1",
    "grok-4":                   "grok-4",
    "grok-4-0709":              "grok-4",
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DEFAULT_OBS_FILE   = "1774563890090-lf-observations-export-cmlrfnmjb00doad079zzzs8iz.json"
DEFAULT_TRACES_CSV = "1774563119788-lf-traces-export-cmlrfnmjb00doad079zzzs8iz.csv"
RESULTS_ROOT       = Path("results/test")
GROUND_TRUTH_FILE  = Path("test_ground_truth.csv")
TOKEN_CACHE        = Path(".token_index_cache.pkl")   # cached output of streaming pass

MODE_ORDER = [
    "intrinsic", "hierarchical", "context_engineered",
    "llm_context", "hier_context_engineered", "hier_llm_context",
]
MODE_LABELS = {
    "intrinsic":               "Intrinsic",
    "hierarchical":            "Hierarchical",
    "context_engineered":      "Context-Eng",
    "llm_context":             "LLM-Context",
    "hier_context_engineered": "Hier+Ctx",
    "hier_llm_context":        "Hier+LLM",
}

# ---------------------------------------------------------------------------
# Step 1 — Ground truth
# ---------------------------------------------------------------------------

def load_ground_truth() -> dict[str, bool]:
    gt: dict[str, bool] = {}
    with open(GROUND_TRUTH_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gt[row["client_id"]] = row["is_money_laundering"].strip().lower() in ("true", "1")
    return gt


# ---------------------------------------------------------------------------
# Step 2 — Build fingerprint index from results JSONs
# ---------------------------------------------------------------------------

def _fingerprint(state: dict) -> str:
    """
    Stable, mode-discriminating fingerprint from a result AgentState.
    Uses the first 300 chars of review_output.reasoning — this text differs
    across modes (persona, injected rules) even when classification matches.
    """
    review = state.get("review_output") or {}
    text = review.get("reasoning", "")
    if not text:
        analyst = state.get("analyst_output") or {}
        text = analyst.get("reasoning", "")
    return text[:300]


def build_results_index(run_id: str = "1") -> dict[tuple[str, str], dict]:
    """
    Walk results/test/{model}/run_{run_id}/{mode}/{client_id}.json.
    Returns {(client_id, fingerprint): record_dict}.
    Only loads run_id to prevent cross-replicate fingerprint collisions.
    """
    gt = load_ground_truth()
    idx: dict[tuple[str, str], dict] = {}
    collisions = 0

    pattern = RESULTS_ROOT / "*" / f"run_{run_id}" / "*" / "*.json"
    for path in sorted(RESULTS_ROOT.glob(f"*/run_{run_id}/*/*.json")):
        parts = path.parts
        model  = parts[-4]
        mode   = parts[-2]
        client = path.stem

        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "error" in state:
            continue

        fp = _fingerprint(state)
        if not fp:
            continue

        final       = state.get("final_output") or {}
        pred_score  = final.get("risk_score", 0)
        rev_count   = state.get("revision_count", 0)
        pred_guilty = pred_score >= 50
        correct     = pred_guilty == gt.get(client, False)

        key = (client, fp)
        if key in idx:
            collisions += 1
        idx[key] = {
            "model":          model,
            "mode":           mode,
            "client_id":      client,
            "revision_count": rev_count,
            "correct":        correct,
            "final_score":    pred_score,
        }

    total_modes  = len(set(v["mode"]  for v in idx.values()))
    total_models = len(set(v["model"] for v in idx.values()))
    print(f"  Results index: {len(idx):,} entries | "
          f"{total_models} models, {total_modes} modes | "
          f"{collisions} fingerprint collisions (ignored)")
    return idx


# ---------------------------------------------------------------------------
# Step 3 — Stream observations file for real token counts (via ijson)
# ---------------------------------------------------------------------------

def stream_token_counts(obs_file: str) -> dict[str, dict]:
    """
    Stream the observations JSON file with ijson, extracting GENERATION records.
    Returns {traceId: {model, input_tokens, output_tokens, calls}}.

    Only records where inputUsage > 0 are kept (skips structured-output wrapper
    calls that have type=GENERATION but zero usage).
    """
    token_idx: dict[str, dict] = defaultdict(
        lambda: {"model": None, "input_tokens": 0, "output_tokens": 0, "calls": 0}
    )

    file_size = Path(obs_file).stat().st_size
    gen_total = 0
    gen_with_usage = 0
    last_pct = -1

    print(f"  Streaming {file_size / 1e9:.2f} GB — this takes a few minutes ...")

    with open(obs_file, "rb") as f:
        parser = ijson.items(f, "item")
        for i, record in enumerate(parser):
            if record.get("type") != "GENERATION":
                continue

            input_tok  = record.get("inputUsage")  or 0
            output_tok = record.get("outputUsage") or 0
            gen_total += 1

            if input_tok == 0 and output_tok == 0:
                continue  # wrapper call — no real tokens

            gen_with_usage += 1
            trace_id   = record.get("traceId", "")
            model_name = record.get("model") or ""

            entry = token_idx[trace_id]
            if model_name and not entry["model"]:
                entry["model"] = model_name
            entry["input_tokens"]  += input_tok
            entry["output_tokens"] += output_tok
            entry["calls"]         += 1

            if i % 50_000 == 0 and i > 0:
                try:
                    pos = f.tell()
                    pct = int(pos / file_size * 100)
                    if pct != last_pct:
                        print(f"    {pct:3d}% — {gen_with_usage:,} LLM calls across "
                              f"{len(token_idx):,} traces so far")
                        last_pct = pct
                except Exception:
                    pass

    print(f"  Done — {gen_total:,} GENERATION records; "
          f"{gen_with_usage:,} with real usage; "
          f"{len(token_idx):,} unique traces")
    return dict(token_idx)


# ---------------------------------------------------------------------------
# Step 4 — Parse traces CSV
# ---------------------------------------------------------------------------

def parse_traces_csv(csv_file: str) -> list[dict]:
    """
    Parse the Langfuse traces CSV.
    Returns [{trace_id, client_id, fingerprint}].
    """
    csv.field_size_limit(10_000_000)
    traces = []
    skipped = 0

    with open(csv_file, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            trace_id = row.get("id", "").strip()

            client_id = None
            try:
                inp = json.loads(row.get("input", "{}") or "{}")
                client_id = inp.get("client_id")
            except Exception:
                pass
            if not client_id:
                skipped += 1
                continue

            fp = ""
            try:
                out = json.loads(row.get("output", "{}") or "{}")
                fp = _fingerprint(out)
            except Exception:
                pass

            traces.append({"trace_id": trace_id, "client_id": client_id, "fp": fp})

    print(f"  Traces CSV: {len(traces):,} parsed, {skipped} skipped (no client_id)")
    return traces


# ---------------------------------------------------------------------------
# Step 5 — Match and compute per-trace costs
# ---------------------------------------------------------------------------

def compute_costs(
    traces: list[dict],
    results_idx: dict[tuple[str, str], dict],
    token_idx: dict[str, dict],
) -> pd.DataFrame:
    rows = []
    unmatched_result = 0
    unmatched_tokens = 0
    no_pricing       = 0

    for t in traces:
        key    = (t["client_id"], t["fp"])
        result = results_idx.get(key)
        if result is None:
            unmatched_result += 1
            continue

        tok = token_idx.get(t["trace_id"])
        if tok is None:
            unmatched_tokens += 1
            continue

        # Resolve model for pricing: prefer API model string, fall back to dir name
        api_model   = tok.get("model") or ""
        exp_model   = result["model"]
        norm_model  = MODEL_NORM.get(api_model) or exp_model
        pricing     = PRICING.get(api_model) or PRICING.get(exp_model)
        if pricing is None:
            no_pricing += 1
            continue

        in_tok  = tok["input_tokens"]
        out_tok = tok["output_tokens"]
        cost    = (in_tok * pricing["input"] + out_tok * pricing["output"]) / 1_000_000

        rows.append({
            "model":          norm_model,
            "mode":           result["mode"],
            "client_id":      result["client_id"],
            "revision_count": result["revision_count"],
            "correct":        result["correct"],
            "input_tokens":   in_tok,
            "output_tokens":  out_tok,
            "total_tokens":   in_tok + out_tok,
            "cost_usd":       cost,
            "llm_calls":      tok["calls"],
            "api_model":      api_model,
        })

    matched = len(rows)
    print(f"  Matched {matched:,} | no result match {unmatched_result:,} | "
          f"no token data {unmatched_tokens:,} | no pricing {no_pricing:,}")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Step 6 — Compute and print summary tables
# ---------------------------------------------------------------------------

def f1_score(tp: int, fp: int, fn: int) -> float:
    if tp == 0:
        return 0.0
    p = tp / (tp + fp)
    r = tp / (tp + fn)
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def compute_f1_per_mode(df: pd.DataFrame) -> dict[tuple[str, str], float]:
    """Compute F1 from correct/predicted_guilty fields in the cost dataframe."""
    f1_map: dict[tuple[str, str], float] = {}
    gt = load_ground_truth()

    for (model, mode), grp in df.groupby(["model", "mode"]):
        tp = fp = fn = tn = 0
        for _, row in grp.iterrows():
            pred_guilty = row["final_score"] >= 50 if "final_score" in row else (row["cost_usd"] > 0)
            is_guilty   = gt.get(row["client_id"], False)
            # Use correct flag directly — faster
        # Recompute from correct + predicted using ground truth
        for _, row in grp.iterrows():
            pred_guilty = (row.get("final_score", 0) >= 50)
            is_guilty   = gt.get(row["client_id"], False)
            if pred_guilty and is_guilty:     tp += 1
            elif pred_guilty and not is_guilty: fp += 1
            elif not pred_guilty and is_guilty: fn += 1
            else:                               tn += 1
        f1_map[(model, mode)] = f1_score(tp, fp, fn)

    return f1_map


def print_summary(df: pd.DataFrame) -> None:
    if df.empty:
        print("No matched data — cannot produce summary.")
        return

    # Need final_score for F1 — load from results
    gt = load_ground_truth()

    models  = sorted(df["model"].unique())
    modes   = [m for m in MODE_ORDER if m in df["mode"].unique()]
    modes  += [m for m in df["mode"].unique() if m not in modes]

    # ── Per-model × mode aggregation ─────────────────────────────────────
    agg = (
        df.groupby(["model", "mode"])
        .agg(
            n             = ("client_id", "count"),
            avg_input_tok = ("input_tokens",  "mean"),
            avg_output_tok= ("output_tokens", "mean"),
            avg_total_tok = ("total_tokens",  "mean"),
            avg_cost_usd  = ("cost_usd",      "mean"),
            avg_calls     = ("llm_calls",     "mean"),
            accuracy      = ("correct",       "mean"),
        )
        .reset_index()
    )

    # ── Token tables ─────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("MEAN TOKENS PER CASE  (input / output / total)")
    print("=" * 72)
    header = f"{'Mode':<20}" + "".join(f"{'  '+m:>22}" for m in models)
    print(header)
    print("-" * len(header))
    for mode in modes:
        row = f"{MODE_LABELS.get(mode, mode):<20}"
        for model in models:
            sub = agg[(agg["model"] == model) & (agg["mode"] == mode)]
            if sub.empty:
                row += f"{'—':>22}"
            else:
                r = sub.iloc[0]
                row += f"  {r.avg_input_tok:>7,.0f}/{r.avg_output_tok:>6,.0f}/{r.avg_total_tok:>7,.0f}"
        print(row)

    # ── Cost table ────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("MEAN COST PER CASE (USD)  — verify pricing constants at top of file")
    print("=" * 72)
    header2 = f"{'Mode':<20}" + "".join(f"{'  '+m:>18}" for m in models)
    print(header2)
    print("-" * len(header2))
    for mode in modes:
        row = f"{MODE_LABELS.get(mode, mode):<20}"
        for model in models:
            sub = agg[(agg["model"] == model) & (agg["mode"] == mode)]
            if sub.empty:
                row += f"{'—':>18}"
            else:
                cost = sub.iloc[0]["avg_cost_usd"]
                row += f"  ${cost:>12.4f}"
        print(row)

    # ── Cost efficiency (F1 per dollar) ──────────────────────────────────
    # Compute F1 from the matched subset
    print("\n" + "=" * 72)
    print("COST EFFICIENCY  (F1 / dollar × 1000,  i.e. F1 per $0.001)")
    print("=" * 72)

    # Load final_score from the results JSONs for proper F1 computation
    results_scores: dict[tuple[str, str, str], int] = {}
    for path in RESULTS_ROOT.glob("*/run_1/*/*.json"):
        parts = path.parts
        model = parts[-4]; mode = parts[-2]; client = path.stem
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            if "error" not in state:
                final = state.get("final_output") or {}
                results_scores[(model, mode, client)] = final.get("risk_score", 0)
        except Exception:
            pass

    header3 = f"{'Mode':<20}" + "".join(f"{'  '+m:>20}" for m in models)
    print(header3)
    print("-" * len(header3))
    for mode in modes:
        row = f"{MODE_LABELS.get(mode, mode):<20}"
        for model in models:
            sub = df[(df["model"] == model) & (df["mode"] == mode)]
            if sub.empty:
                row += f"{'—':>20}"
                continue
            tp = fp = fn = 0
            for _, r in sub.iterrows():
                score = results_scores.get((model, mode, r["client_id"]), 0)
                pred  = score >= 50
                truth = gt.get(r["client_id"], False)
                if pred and truth:   tp += 1
                elif pred:           fp += 1
                elif truth:          fn += 1
            f1   = f1_score(tp, fp, fn)
            cost = sub["cost_usd"].mean()
            eff  = (f1 / cost * 0.001) if cost > 0 else 0.0
            row += f"  F1={f1:.3f}  {eff:>6.2f}x"
        print(row)

    # ── Absolute cost comparison ──────────────────────────────────────────
    print("\n" + "=" * 72)
    print("COST TO CLASSIFY ALL 168 TEST CLIENTS  (USD, estimated from mean)")
    print("=" * 72)
    header4 = f"{'Mode':<20}" + "".join(f"{'  '+m:>16}" for m in models)
    print(header4)
    print("-" * len(header4))
    for mode in modes:
        row = f"{MODE_LABELS.get(mode, mode):<20}"
        for model in models:
            sub = agg[(agg["model"] == model) & (agg["mode"] == mode)]
            if sub.empty:
                row += f"{'—':>16}"
            else:
                total = sub.iloc[0]["avg_cost_usd"] * 168
                row += f"  ${total:>10.2f}"
        print(row)

    # ── Token composition: base vs revision overhead ───────────────────────
    print("\n" + "=" * 72)
    print("REVISION OVERHEAD  (% of tokens consumed by revision passes)")
    print("=" * 72)
    header5 = f"{'Mode':<20}" + "".join(f"{'  '+m:>18}" for m in models)
    print(header5)
    print("-" * len(header5))
    for mode in modes:
        row = f"{MODE_LABELS.get(mode, mode):<20}"
        for model in models:
            sub = df[(df["model"] == model) & (df["mode"] == mode)]
            if sub.empty:
                row += f"{'—':>18}"
                continue
            no_rev = sub[sub["revision_count"] == 0]["total_tokens"].mean()
            all_   = sub["total_tokens"].mean()
            if no_rev and all_ and no_rev > 0:
                overhead = (all_ - no_rev) / all_ * 100
                row += f"  {overhead:>6.1f}% overhead"
            else:
                row += f"{'n/a':>18}"
        print(row)

    print()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cost efficiency analysis from Langfuse token data."
    )
    parser.add_argument("--obs-file",    default=DEFAULT_OBS_FILE)
    parser.add_argument("--traces-csv",  default=DEFAULT_TRACES_CSV)
    parser.add_argument("--run-id",      default="1")
    parser.add_argument(
        "--skip-stream", action="store_true",
        help="Load token index from cache (.token_index_cache.pkl) instead of re-streaming.",
    )
    parser.add_argument(
        "--save-cache", action="store_true",
        help="Save token index to cache after streaming (speeds up re-runs).",
    )
    args = parser.parse_args()

    print("\n=== AML Governance — Real Cost Analysis ===\n")

    # ── Token index ──────────────────────────────────────────────────────
    if args.skip_stream and TOKEN_CACHE.exists():
        print(f"Loading token index from cache: {TOKEN_CACHE}")
        with open(TOKEN_CACHE, "rb") as f:
            token_idx = pickle.load(f)
        print(f"  {len(token_idx):,} traces loaded from cache")
    else:
        print("Step 1/4: Streaming Langfuse observations for token counts ...")
        token_idx = stream_token_counts(args.obs_file)
        if args.save_cache:
            with open(TOKEN_CACHE, "wb") as f:
                pickle.dump(token_idx, f)
            print(f"  Token index cached to {TOKEN_CACHE}")

    # ── Results index ────────────────────────────────────────────────────
    print(f"\nStep 2/4: Building results fingerprint index (run {args.run_id}) ...")
    results_idx = build_results_index(args.run_id)

    # ── Traces CSV ───────────────────────────────────────────────────────
    print(f"\nStep 3/4: Parsing traces CSV ...")
    traces = parse_traces_csv(args.traces_csv)

    # ── Match and cost ───────────────────────────────────────────────────
    print(f"\nStep 4/4: Matching traces to results and computing costs ...")
    df = compute_costs(traces, results_idx, token_idx)

    if df.empty:
        print("\nNo traces matched — check that the observations and results files align.")
        sys.exit(1)

    # ── Report ───────────────────────────────────────────────────────────
    print_summary(df)

    # Save detailed per-trace CSV
    out_path = Path("results/cost_analysis.csv")
    df.to_csv(out_path, index=False)
    print(f"Per-trace data saved to {out_path}\n")

    # Quick coverage report
    expected = 168 * len(df["mode"].unique()) * len(df["model"].unique())
    print(f"Coverage: {len(df):,} matched traces out of ~{expected} expected test-set traces")
    api_models = df["api_model"].value_counts().to_dict()
    print(f"API models seen: {api_models}")


if __name__ == "__main__":
    main()
