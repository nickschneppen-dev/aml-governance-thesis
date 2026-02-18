"""
tools.py -- Deterministic "Hands" for the multi-agent AML system.

Agents MUST call these tools instead of reading files or doing math directly.
All quantitative metrics are pre-computed from the full dataset and are the
Source of Truth within the simulation.

Tools:
  tool_get_client_list  -- Returns the list of client IDs to investigate.
  tool_search_news      -- Returns qualitative evidence (knowledge base).
  tool_analyze_transactions -- Returns quantitative metrics + risk flags.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TRANSACTIONS_FILE = Path("thesis_transactions.csv")
KNOWLEDGE_BASE_FILE = Path("knowledge_base.json")
CLIENT_METRICS_FILE = Path("client_metrics.json")
CLIENT_LIST_FILE = Path("client_list.csv")

# Risk-flag thresholds (calibrated to benchmark data distribution)
THRESHOLD_FAN_IN = 20       # 75th pctl of guilty is 15; >20 = clear outlier
THRESHOLD_FAN_OUT = 80      # Payroll traps avg 107; separates from normal (~30-50)
THRESHOLD_VOLUME = 200_000  # Flags High Rollers ($232k) and top guilty ($328k)
THRESHOLD_AVG_AMOUNT = 1000 # Structurer traps avg $1,157; normal innocent ~$600


# ---------------------------------------------------------------------------
# Tool 1: tool_get_client_list
# ---------------------------------------------------------------------------
def tool_get_client_list() -> str:
    """Return the list of client IDs that need to be investigated.

    This is the Planner's starting point.  The list contains ONLY client IDs
    -- no group labels, risk scores, or any other information that could
    bias the investigation.
    """
    client_df = pd.read_csv(CLIENT_LIST_FILE)
    ids = client_df["client_id"].tolist()
    lines = [f"  {i+1:2d}. {cid}" for i, cid in enumerate(ids)]
    return (
        f"CLIENT LIST ({len(ids)} subjects)\n"
        f"{'=' * 40}\n"
        + "\n".join(lines)
    )


# ---------------------------------------------------------------------------
# Tool 2: tool_search_news
# ---------------------------------------------------------------------------
def tool_search_news(client_id: str) -> str:
    """Fetch qualitative intelligence for a client from the knowledge base.

    Returns the entity type and ALL articles with full body text.
    Does NOT summarise -- the full text is needed so downstream agents
    (Analyst, Auditor) can catch details buried in article bodies.
    """
    with open(KNOWLEDGE_BASE_FILE, "r", encoding="utf-8") as f:
        kb: dict = json.load(f)

    if client_id not in kb:
        return f"[NEWS] No records found for client {client_id}."

    entry = kb[client_id]
    entity_type = entry.get("entity_type", "Unknown")
    articles = entry.get("articles", [])

    header = (
        f"[NEWS] Intelligence Report for {client_id}\n"
        f"{'=' * 50}\n"
        f"Entity Type: {entity_type}\n"
        f"Articles Found: {len(articles)}\n"
    )

    article_blocks: list[str] = []
    for i, art in enumerate(articles, 1):
        block = (
            f"\n--- Article {i} of {len(articles)} ---\n"
            f"Headline: {art['headline']}\n"
            f"Source:   {art['source']}\n"
            f"Body:\n{art['body']}\n"
        )
        article_blocks.append(block)

    return header + "\n".join(article_blocks)


# ---------------------------------------------------------------------------
# Tool 3: tool_analyze_transactions
# ---------------------------------------------------------------------------
def tool_analyze_transactions(client_id: str) -> str:
    """Fetch quantitative metrics for a client.

    Metrics are pre-computed from the full 1.09M-row dataset (not the
    trimmed benchmark CSV) to ensure accurate fan_in/fan_out values.
    These numbers are the Source of Truth -- indisputable facts within
    the simulation.

    Also returns risk flags when metrics exceed calibrated thresholds.
    """
    with open(CLIENT_METRICS_FILE, "r", encoding="utf-8") as f:
        metrics: dict = json.load(f)

    if client_id not in metrics:
        return f"[TRANSACTIONS] No data found for client {client_id}."

    m = metrics[client_id]
    total_volume = m["total_volume"]
    tx_count = m["tx_count"]
    avg_amount = m["avg_amount"]
    fan_in = m["fan_in"]
    fan_out = m["fan_out"]

    # Build report
    report = (
        f"[TRANSACTIONS] Quantitative Analysis for {client_id}\n"
        f"{'=' * 50}\n"
        f"Total Volume:    ${total_volume:>12,.2f}\n"
        f"Transaction Count: {tx_count:>8d}\n"
        f"Avg Amount:      ${avg_amount:>12,.2f}\n"
        f"Fan-In  (unique senders):   {fan_in:>4d}\n"
        f"Fan-Out (unique recipients): {fan_out:>4d}\n"
    )

    # Risk flags
    flags: list[str] = []
    if fan_in > THRESHOLD_FAN_IN:
        flags.append(
            f"** RISK FLAG: HIGH FAN-IN ({fan_in}) ** "
            f"-- This client receives funds from an unusually large number "
            f"of unique senders (threshold: {THRESHOLD_FAN_IN})."
        )
    if fan_out > THRESHOLD_FAN_OUT:
        flags.append(
            f"** RISK FLAG: HIGH FAN-OUT ({fan_out}) ** "
            f"-- This client sends funds to an unusually large number "
            f"of unique recipients (threshold: {THRESHOLD_FAN_OUT})."
        )
    if total_volume > THRESHOLD_VOLUME:
        flags.append(
            f"** RISK FLAG: HIGH VOLUME (${total_volume:,.2f}) ** "
            f"-- Total transaction volume exceeds threshold "
            f"(${THRESHOLD_VOLUME:,})."
        )
    if avg_amount > THRESHOLD_AVG_AMOUNT:
        flags.append(
            f"** RISK FLAG: HIGH AVG TRANSACTION (${avg_amount:,.2f}) ** "
            f"-- Average transaction size exceeds threshold "
            f"(${THRESHOLD_AVG_AMOUNT:,})."
        )

    if flags:
        report += f"\n{'~' * 50}\n"
        report += "\n".join(flags) + "\n"
    else:
        report += f"\n{'~' * 50}\n"
        report += "No automated risk flags triggered.\n"

    return report


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import csv

    # Load ground truth to pick representative test IDs
    with open("ground_truth.csv") as f:
        gt = {r["client_id"]: r for r in csv.DictReader(f)}

    # Pick one ID from each group for demonstration
    test_cases: list[tuple[str, str]] = []
    seen_groups: set[str] = set()
    for cid, row in gt.items():
        key = row["group"] + ("_" + row["trap_subtype"] if row["trap_subtype"] else "")
        if key not in seen_groups:
            seen_groups.add(key)
            test_cases.append((cid, key))

    # 1. Test client list
    print(tool_get_client_list())
    print()

    # 2. Test each tool on representative clients
    for cid, label in test_cases:
        print(f"\n{'#' * 60}")
        print(f"# TEST: {label} -> {cid}")
        print(f"{'#' * 60}")
        print()
        print(tool_analyze_transactions(cid))
        print()
        print(tool_search_news(cid))
        print()
