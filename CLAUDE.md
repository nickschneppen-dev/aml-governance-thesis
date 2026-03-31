# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Multi-Agent AML Governance Thesis** — Compares four governance patterns in an agentic system for Anti-Money Laundering (AML) analysis:
1. **Intrinsic Self-Correction** — Analyst reviews its own reasoning (baseline)
2. **Hierarchical Auditor** — Dedicated independent Auditor reviews the Analyst
3. **Context-Engineered** — Intrinsic + Kayba-generated Context Playbook injected into the self-review step
4. **LLM-Context** — Intrinsic + rules synthesised by the LLM itself from its own training traces

The thesis question: does external context injection (Kayba) close the gap between self-correction and independent auditing? And how does LLM-synthesised context compare to externally-generated context?

## Architecture

LangGraph multi-agent system with the following agents:
- **News Scout**: Qualitative intelligence gathering (news, sanctions, PEP lists)
- **Forensics Scout**: Quantitative analysis of transaction data and financial patterns
- **Analyst**: Reasoning agent that synthesises scout findings into risk assessments
- **Auditor**: Governance agent that reviews and validates analyst conclusions (hierarchical mode only)

## Tech Stack

- **Python 3.13** with virtual environment (`.venv`)
- **LangGraph** — agent orchestration and state management
- **LangChain / langchain-openai** — LLM integration (OpenAI and xAI/Grok)
- **Pandas** — data tools for transaction/financial analysis
- **Langfuse** — observability and metrics collection
- **MLflow** — experiment tracking and grading runs

## Development Environment

```bash
# Activate virtual environment
source .venv/Scripts/activate  # Windows Git Bash

# Install dependencies
pip install -r requirements.txt
```

## Dataset Design

Two separate datasets are generated from `AMLNet_August 2025.csv` (~1.09M transactions, 10k users):

- **Test set** (n=168): 60 guilty / 108 innocent — used for final evaluation of all 4 governance modes.
- **Train set** (n=86): 34 guilty / 52 innocent — used to generate Kayba training traces and LLM-context rules. Different clients from test.

Both sets have the same group structure and KB article templates, but different AMLNet client IDs.

### Generating datasets

```bash
# Always generate test first (train excludes test clients)
python 01_build_dataset.py --dataset test
python 01_build_dataset.py --dataset train   # requires test_client_list.csv
```

**Output files per dataset** (prefix = `test_` or `train_`):

| File | Accessible to agents? | Contents |
|---|---|---|
| `{prefix}transactions.csv` | No (too large; metrics are pre-computed) | Raw transaction rows for selected users |
| `{prefix}knowledge_base.json` | Via tool only | Mock "internet" (articles across all clients) |
| `{prefix}client_list.csv` | Via tool only | Client IDs only — no groups, labels, or scores |
| `{prefix}client_metrics.json` | Via tool only | Pre-computed fan_in/fan_out/volume/avg_amount/tx_count from the full 1.09M-row dataset |
| `{prefix}ground_truth.csv` | **NO — evaluation only, never during a run** | Full answer key (group, trap_subtype, is_money_laundering, expected_risk_score, rationale) |

Running `--dataset test` also writes backward-compat bare copies (`knowledge_base.json`, `client_list.csv`, etc.).

**Train vs test client selection:** The `pick()` function uses a `selected` set to avoid duplicates within a run. For the train run, this set is pre-populated with all 50 test IDs, so train always picks the next-best candidates from each group pool. Group B (random bottom-quartile innocents) uses a different random seed per dataset (test: 42, train: 123).

**Key engineered features:** `fan_in`, `fan_out`, `total_volume`, `avg_amount` (computed per user from the full dataset, not the trimmed benchmark CSV).

### Knowledge Base Design

Each client has 2-3 articles with full body text (3-5 sentences). The knowledge base contains **no metadata labels** — no `sentiment`, `alibi`, or `trigger` fields. Agents must read, extract, and weigh evidence from article text only. Each entry has just `entity_type` and `articles` (headline, source, body).

**Mixed signals by design:** Trap cases receive conflicting articles to force reasoning rather than pattern-matching.

| Group | Article 1 | Article 2-3 (conflicting) |
|---|---|---|
| FP traps | Legitimate business/alibi article | Ambiguous sector-wide regulatory scrutiny (not directed at entity) |
| FN Sleeper | Benign community profile (volunteer, retiree, pro bono lawyer) | Damning intelligence buried in body text |
| FN Smurf | Normal student/gig worker life | Mule-network exposure buried in body text |

Controls get consistent signals: Guilty = 2 adverse articles, Innocent = 2 benign articles.

### Controls

| Group | n | Truth | Selection |
|---|---|---|---|
| **A – Control Guilty** | 16 (test) / 8 (train) | GUILTY | `isMoneyLaundering=1`, top by volume. Shell Company + adverse media. |
| **B – Control Innocent** | 16 (test) / 8 (train) | INNOCENT | `isMoneyLaundering=0`, bottom-quartile volume. Individual + neutral news. |

### Group C – False Positive Traps (looks guilty, IS innocent)

Each targets a different AML red flag. One article provides a legitimate explanation; another introduces ambiguous noise (sector-wide reviews, regulatory reminders). Agent must weigh both and correctly downgrade risk.

| Sub-group | n | Red Flag Mimicked | Alibi Entity |
|---|---|---|---|
| **C1 – Charity** | 23 (test) / 12 (train) | High fan-in (~25 unique senders) mimics collection hub | Registered NGO (+ ACNC reviews, governance questions) |
| **C2 – Payroll** | 23 (test) / 12 (train) | High fan-out (~107 unique recipients) mimics layering | Business (+ Fair Work investigations, ABF inspections) |
| **C3 – High Roller** | 23 (test) / 12 (train) | Volume (~$232k) rivals guilty-group throughput | Casino/IPO/mining (+ junket scrutiny, ASIC monitoring) |
| **C4 – Structurer** | 23 (test) / 12 (train) | High avg txn (~$1,157) mimics structured deposits | Vending/medical/dealer (+ ATO cash-business blitz, AUSTRAC reminders) |

Note: C4 exhausts the full AMLNet pool (23+12=35 qualifying clients total).

### Group D – False Negative Traps (looks innocent, IS guilty)

Confirmed launderers whose **quantitative data is unremarkable**. Each gets a benign cover article followed by an article with adverse intelligence **embedded in the body text**. Agents must read article content — not just headlines — and override clean transaction data with qualitative evidence.

| Sub-group | n | Deceptive Pattern | Buried Signal |
|---|---|---|---|
| **D1 – Sleeper** | 22 (test) / 11 (train) | Vol/fan-in/fan-out statistically identical to Control Innocent | Terror financing, hawala, proliferation, bribery, immigration fraud, tax evasion, Interpol Red Notice |
| **D2 – Smurf** | 22 (test) / 11 (train) | High fan-in + small avg amounts looks like student/gig worker | Campus mule rings, gig-economy fronts, scam funnelling, social media recruitment, court convictions |

The Sleepers are the hardest test: avg volume $33k vs Control Innocent $29k — indistinguishable from transaction data alone.

## Agent Rules & Governance Strategy

### 1. The "Brain vs. Hands" Architecture
- **Agents (The Brains):** The Scouts, Analyst, and Auditor are LLMs. They reason, plan, and write narratives.
- **Tools (The Hands):** `tools.py` contains the deterministic logic.
  - **Constraint:** Agents are **forbidden** from reading CSV/JSON files directly or doing math in their context window. They **MUST** call the defined tools.
  - **Forensics Scout:** MUST call `tool_analyze_transactions` to get metrics. It cannot "guess" risk.
  - **News Scout:** MUST call `tool_search_news` to get articles. It cannot "hallucinate" headlines.

### 2. The Governance Logic (Hypothesis)
- **Intrinsic Mode (Baseline):** The Analyst reviews its own draft. We hypothesise it will succumb to "Confirmation Bias" (sticking to its initial finding).
- **Hierarchical Mode:** The Auditor Agent acts as a "Compliance Officer."
  - **The "Trusted Tool" Pattern:** The Auditor compares the Analyst's report against the **raw output from the Tools**. If the Tool output says "Fan-In: 50" but the Analyst says "No suspicious network activity," the Auditor **MUST** reject the report.
- **Context-Engineered Mode:** Intrinsic governance + Kayba's Context Playbook appended to the self-review user message under a `<Context_Playbook>` XML tag. The Analyst's initial report is identical to intrinsic — only the reviewer's guidance differs.
- **LLM-Context Mode:** Same as context_engineered, but the rules are synthesised by the LLM itself from its own training traces (via `05_generate_llm_context_rules.py`) rather than Kayba's external pipeline.

### 3. Data Integrity
- The `tool_analyze_transactions` function is the **Source of Truth**. Its calculations (Volume, Fan-In, Fan-Out, Avg Amount) are final and indisputable facts within the simulation.
- Metrics are pre-computed from the full 1.09M-row dataset and stored in `{prefix}client_metrics.json`. This is necessary because `{prefix}transactions.csv` only contains outgoing transactions for the 50 selected users — computing fan_in from it alone would return zero for nearly everyone.

## Tools (`tools.py`)

Three deterministic tools that agents call instead of reading files directly:

- **`tool_get_client_list() -> str`** — Returns the 50 client IDs. Contains no group labels or answers.
- **`tool_search_news(client_id) -> str`** — Returns entity type + all articles with full body text. No summarisation — full text is returned so agents can catch details buried in article bodies.
- **`tool_analyze_transactions(client_id) -> str`** — Returns pre-computed metrics (total_volume, tx_count, avg_amount, fan_in, fan_out) plus risk flags when thresholds are exceeded.
- **`configure_dataset(prefix) -> None`** — Switches all tool file paths to a dataset prefix (e.g., `"test_"` → reads `test_knowledge_base.json`). Called by `02_run_experiment.py` before building graphs.

### Risk Flag Thresholds

Calibrated to the benchmark data distribution. Flags are informational — agents must reason about whether a flag indicates actual risk or is explained by the knowledge base.

- `fan_in > 20` — Triggers for: FP Charity (all 5), FN Smurf (2 of 7)
- `fan_out > 80` — Triggers for: FP Payroll (all 5), FP High Roller (all 5)
- `total_volume > $200k` — Triggers for: Control Guilty (all 8), FP Payroll (4 of 5), FP High Roller (all 5)
- `avg_amount > $1,000` — Triggers for: Control Guilty (all 8), FP Structurer (all 5)
- **FN Sleepers trigger zero flags** — the entire point; only the KB reveals guilt
- **Control Innocents trigger zero flags** — clean baseline

## State Schema (`state.py`)

**Pydantic models** enforce structured JSON output from LLM agents (parsed via `with_structured_output()`):

- `ArticleExtraction` — headline, source, claims (list of factual strings)
- `NewsSummary` — articles_found + list of ArticleExtraction
- `AnalystOutput` — risk_score (0-100), risk_label, confidence (0-100), reasoning
- `ReviewOutput` — decision (APPROVE/REJECT), adjusted_risk_score (0-100), reasoning, citations (list of strings)

**`AgentState(TypedDict)`** flows through the LangGraph graph per client:

| Field | Type | Set by |
|---|---|---|
| `client_id` | str | Input |
| `forensics_output` | str | Forensics Scout (raw tool output, immutable) |
| `news_output` | str | News Scout (raw tool output, immutable) |
| `news_summary` | dict | News Scout (LLM extraction) |
| `analyst_output` | dict | Analyst / Revision |
| `review_output` | dict | Self-Review or Auditor |
| `review_decision` | str | Self-Review or Auditor (extracted for routing) |
| `revision_count` | int | Revision node (max 2) |
| `final_output` | dict | Finalise node |

## Agents (`agents.py`)

**Deterministic (no LLM):**
- `forensics_scout_node` — Calls `tool_analyze_transactions`, stores raw output. Deterministic to avoid anchoring bias on the Analyst.
- `finalise_node` — Copies approved output to `final_output`. Uses reviewer's adjusted score if APPROVE + score differs.

**LLM-powered (all use `get_llm()` → `ChatOpenAI`, default `gpt-4o-mini`; xAI/Grok supported via `grok-` prefix detection):**
- `news_scout_node` — Calls `tool_search_news`, then LLM extracts facts into `NewsSummary`. Facts-only constraint: no opinions, no risk judgments.
- `analyst_node` — Synthesises forensics + news into `AnalystOutput`. System prompt contains AML domain knowledge (threshold interpretations, "no flags ≠ clean" rule).
- `self_review_node` — Analyst reviews own work (intrinsic/context-engineered governance).
- `auditor_node` — Independent auditor reviews (hierarchical governance).
- `revision_node` — Analyst rewrites after REJECT. Instructed not to simply capitulate but use evidence.
- `make_analyst_node(extra_prompt)` — Factory returning an analyst node closure. When `extra_prompt` is non-empty (context-engineered mode), the Kayba Context Playbook is appended to the system prompt under `<Context_Playbook>` tags.
- `make_revision_node(extra_prompt)` — Same factory pattern for the revision node. Both analyst and revision nodes get the playbook because they represent the same Analyst persona at different workflow points.

**Critical design decisions:**
- Both review nodes call `_build_review_context()` which provides identical data (analyst output + raw forensics + raw news + news summary). The ONLY difference between intrinsic and hierarchical is the system prompt persona.
- `get_llm()` returns the same model for all agents (`LLM_MODEL` env var, default `gpt-4o-mini`). Models prefixed `grok-` are routed to xAI's API (`XAI_API_KEY`, `XAI_BASE_URL`). The sole experimental variable is governance structure (or prompt augmentation for context-engineered/llm_context).

## Graph (`graph.py`)

`build_graph(mode)` constructs and compiles a LangGraph `StateGraph` for one of three governance modes.

**Flow:** `dispatch → [forensics_scout ‖ news_scout] → analyst → review → [conditional] → finalise | revision → review`

- Scouts run in parallel (dispatch fans out, analyst joins when both complete)
- The review node is `self_review_node` (intrinsic, context_engineered, llm_context) or `auditor_node` (hierarchical)
- `_should_revise()` conditional edge: if REJECT and `revision_count < MAX_REVISIONS` (2), route to revision; otherwise finalise
- `_model_artefact_path(prefix)` resolves model-specific artefact files: tries `{prefix}_{model}.txt` first, falls back to `{prefix}.txt`
- For `context_engineered`: reads `external_agent_injection_{model}.txt` and passes to `make_self_review_node()`
- For `llm_context`: reads `llm_context_rules_{model}.txt` and passes to `make_self_review_node()`

```python
from graph import build_graph
app = build_graph("intrinsic")          # or "hierarchical" / "context_engineered" / "llm_context"
result = app.invoke({"client_id": "C1234", "revision_count": 0})
```

`context_engineered` raises `FileNotFoundError` if `external_agent_injection_{model}.txt` is not present.
`llm_context` raises `FileNotFoundError` if `llm_context_rules_{model}.txt` is not present.

## Experiment Runner (`02_run_experiment.py`)

Runs all clients through one or more governance modes and saves results incrementally.

```bash
python 02_run_experiment.py --dataset test --modes intrinsic hierarchical context_engineered llm_context
python 02_run_experiment.py --dataset train --modes intrinsic        # train set for trace export
python 02_run_experiment.py --model grok-4 --dataset test --modes intrinsic hierarchical context_engineered llm_context
python 02_run_experiment.py --force                                  # re-run from scratch
```

**Output structure:**
```
results/
  {dataset}/
    {model}/             # e.g., gpt-4o-mini, gpt-4o
      run_{run_id}/
        {mode}/{client_id}.json    # full AgentState (all intermediate outputs)
        summary.csv                # wide-format comparison (streamed, one row per client)
```

**Supported modes** (pass any combination to `--modes`):

| Mode | Description | Column prefix |
|---|---|---|
| `intrinsic` | Self-review baseline | `int` |
| `hierarchical` | Independent auditor | `hier` |
| `context_engineered` | Self-review + Kayba playbook | `ctx` |
| `llm_context` | Self-review + LLM-synthesised rules | `llm` |
| `hier_context_engineered` | Hierarchical auditor + Kayba playbook | `hier_ctx` |
| `hier_llm_context` | Hierarchical auditor + LLM-synthesised rules | `hier_llm` |

The last two complete a **2×3 factorial design** (architecture: intrinsic vs hierarchical × rule source: none / Kayba / LLM), deconfounding architecture from rule injection.

**summary.csv** columns are generated dynamically from whichever modes were run:
- Fixed: `client_id`, `model`
- Per mode: `{prefix}_initial_score`, `{prefix}_score`, `{prefix}_confidence`, `{prefix}_review_decision`, `{prefix}_revision_count`
- Pairwise deltas: `int_hier_delta`, `int_ctx_delta`, etc.

**Multiple runs for variance:** Use `--run-id` to separate replicates. Use `--model` to separate model conditions. Each combination gets its own directory and summary CSV.

**Resumability:** Skips clients where ALL requested modes are complete in summary.csv. A client with partial mode data (e.g. only intrinsic) is NOT skipped — it will be reprocessed for missing modes. Use `--force` to wipe and restart.

**Error isolation:** Each mode invocation is try/except. Errors save `{"client_id": "...", "error": "..."}` to JSON and write `ERROR` to the CSV row.

## Holdout Experiment (`01_build_dataset.py --holdout-group`)

Tests OOD generalisation: withholds one trap group from the train set so rule-synthesis artefacts never see it, then evaluates on the unchanged test set. Performance on the held-out group is a pure out-of-distribution test.

```bash
# 1. Build holdout train set (writes train_holdout{group}_* files, does NOT overwrite train_*)
python 01_build_dataset.py --dataset train --holdout-group D2   # any of C1,C2,C3,C4,D1,D2

# 2. Run intrinsic on holdout train set (--dataset-prefix overrides the file prefix)
python 02_run_experiment.py --dataset train --modes intrinsic --dataset-prefix train_holdoutd2_

# 3. Export traces from holdout run (ground-truth must match holdout prefix)
python 04_export_traces.py \
  --results-dir results/train/{model}/run_1/intrinsic \
  --ground-truth train_holdoutd2_ground_truth.csv \
  --output-dir training_traces_{model}_holdoutd2

# 4a. Re-run Kayba on holdout traces → external_agent_injection_{model}_holdoutd2.txt
# 4b. Re-run LLM rules → llm_context_rules_{model}_holdoutd2.txt

# 5. Run all modes on TEST set (unchanged) — artefacts auto-selected via _model_artefact_path()
python 02_run_experiment.py --dataset test \
  --modes intrinsic hierarchical context_engineered llm_context \
  --model {model} --run-id run_holdoutd2

# 6. Evaluate — annotates OOD group in per-group table, logs holdout_group param to MLflow
python 03_evaluate.py --dataset test --model {model} --run-id run_holdoutd2 --holdout-group D2
```

**Key implementation details:**
- `01_build_dataset.py`: `--holdout-group` zeros `N_*` counts for the specified group; dataset prefix becomes `train_holdout{group}_` automatically.
- `02_run_experiment.py`: `--dataset-prefix` overrides the default `{dataset}_` prefix for all file reads. Required for holdout train runs.
- `03_evaluate.py`: `--holdout-group` annotates the OOD group in per-group output with `*** OOD ***` and logs `holdout_group` to MLflow.
- Holdout artefacts use naming convention `{base}_{model}_holdout{group}.txt`; `_model_artefact_path()` does NOT auto-select these — pass them manually or swap the active artefact files.

## Trace Export & Kayba Integration (`04_export_traces.py`)

Bridges this system and Kayba's Agentic Context Engine. Runs **outside** the main experiment loop — called manually after the train run.

```bash
python 04_export_traces.py
# defaults: --results-dir results/train/gpt-4o-mini/run_1/intrinsic
#           --ground-truth train_ground_truth.csv
#           --output-dir training_traces
# For a different model:
python 04_export_traces.py --results-dir results/train/grok-4/run_1/intrinsic --output-dir training_traces_grok-4
```

Reads AgentState JSONs from the results directory and ground truth CSV, then writes one annotated `.md` file per client to the output dir. Each `.md` contains:
- Classification metadata (CORRECT/INCORRECT, agent score vs ground truth, group)
- Full forensics output, raw news articles, News Scout extractions
- Analyst reasoning and review decision
- Ground truth rationale

**Use model-specific output dirs** (`training_traces_{model}/`) to avoid mixing traces across models. The output dir is what you feed to Kayba and `05_generate_llm_context_rules.py`.

## LLM-Context Rule Generation (`05_generate_llm_context_rules.py`)

Synthesises generalizable AML reasoning rules from training traces by prompting the LLM to analyse its own past errors and successes.

```bash
# Uses LLM_MODEL env var, outputs llm_context_rules_{model}.txt
python 05_generate_llm_context_rules.py
# Explicit model and traces dir:
LLM_MODEL=grok-4 python 05_generate_llm_context_rules.py --traces-dir training_traces_grok-4
```

- Output filename defaults to `llm_context_rules_{model}.txt` (model-specific)
- xAI/Grok models routed to xAI API automatically (same `grok-` prefix detection as `agents.py`)
- **Rule quality depends on training error density**: near-zero training errors (e.g. grok-4: 2/86) produce poorly calibrated rules — the synthesis lacks failure signal

## Statistical Significance Tests (`07_significance_tests.py`)

Runs three tests against `evaluation.csv` to assess whether mode differences are statistically significant.

```bash
python 07_significance_tests.py                          # gpt-4o-mini, run_1
python 07_significance_tests.py --model gpt-5.1 --run-id 1
```

- **Cochran's Q** — omnibus test: are any of the 4 modes different in binary correct/incorrect?
- **McNemar's** — pairwise tests with Bonferroni correction
- **Bootstrap CIs** — 95% confidence intervals on F1 per mode (N=10,000, seed=42)

Reads `results/{dataset}/{model}/run_{run_id}/evaluation.csv`. Prints results to stdout; no MLflow logging.

## Revision Depth Ablation (`08_revision_depth_experiment.py` + `09_analyze_revision_depth.py`)

Tests whether performance changes as `MAX_REVISIONS` increases beyond the baseline of 2. Self-contained: defines its own graph builder, does not modify existing code.

```bash
# Run ablation (default: depths 0–10, gpt-4o-mini)
python 08_revision_depth_experiment.py
python 08_revision_depth_experiment.py --depths 0 2 5 10   # custom depths
python 08_revision_depth_experiment.py --model gpt-4o-mini --run-id 1 --force

# Analyse results and log to MLflow
python 09_analyze_revision_depth.py
python 09_analyze_revision_depth.py --model gpt-4o-mini --run-id 1 --no-mlflow
```

**Output structure:**
```
results/revision_depth/{model}/run_{run_id}/
  depth_{N}/{client_id}.json
  summary.csv
```

**Cost note:** Depths 0–10 add ~4–5× the cost of a single intrinsic run (most clients APPROVE early so actual call counts are lower than the theoretical maximum).

## Full Experiment Workflow

```bash
# 1. Generate datasets (test first, then train)
python 01_build_dataset.py --dataset test
python 01_build_dataset.py --dataset train

# 2. Run intrinsic mode on TRAIN set → traces for artefact generation
python 02_run_experiment.py --dataset train --modes intrinsic   # uses LLM_MODEL env var

# 3. Export traces (use model-specific output dir)
python 04_export_traces.py \
  --results-dir results/train/{model}/run_1/intrinsic \
  --ground-truth train_ground_truth.csv \
  --output-dir training_traces_{model}

# 4a. Generate LLM-context rules (from traces)
LLM_MODEL={model} python 05_generate_llm_context_rules.py --traces-dir training_traces_{model}
# → produces llm_context_rules_{model}.txt

# 4b. Run Kayba externally (separate project: C:/Dev/Kayba/)
#    python agentic_system_prompting.py training_traces_{model}/ --model {model} --output-dir C:/Dev/Thesis
#    → produces external_agent_injection_{model}.txt

# 5. Run all 4 modes on TEST set
python 02_run_experiment.py --dataset test \
  --modes intrinsic hierarchical context_engineered llm_context \
  --model {model}

# 6. Evaluate
python 03_evaluate.py --dataset test --model {model}
mlflow ui   # → http://localhost:5000, select runs → Compare
```

## Evaluation (`03_evaluate.py`)

Computes all metrics in Python (handles custom trap-group logic that MLflow can't infer), then logs everything to MLflow for side-by-side comparison.

```bash
python 03_evaluate.py --dataset test                              # gpt-4o-mini, run 1 (defaults)
python 03_evaluate.py --dataset test --model gpt-4o --run-id 1   # different model
python 03_evaluate.py --dataset test --run-id 2                   # replicate 2
python 03_evaluate.py --dataset test --run-name v1                # custom MLflow name prefix
```

**Three levels of metrics (per mode):**

| Level | Metrics | Purpose |
|---|---|---|
| Score Accuracy | Range accuracy (score within expected_risk_min/max), MAE from midpoint | Did the agent score correctly? |
| Classification | Precision, recall, F1, confusion matrix (threshold: score ≥ 50 = guilty) | Did the system flag launderers and clear innocents? |
| Per-Group | All above broken down by group (A, B, C1-C4, D1-D2) | Which trap types does each governance mode handle better? |

**Additional behavioural metrics:** `consensus_rate` (APPROVE rate), `avg_revisions`, `expected_llm_calls` (cost proxy: 3 base + 2×revisions).

**Reasoning quality (LLM judge):** Uses `mlflow.evaluate()` with a custom `make_genai_metric` to score each agent's reasoning text (1-5) on evidence coverage: does it cite specific metrics, reference specific article claims, and address conflicting signals? Compared against `ground_truth.rationale`.

**Output:**
- `results/{dataset}/{model}/run_{run_id}/evaluation.csv` — one row per client with all computed columns for all modes
- `results/{dataset}/{model}/run_{run_id}/evaluation_{mode}.csv` — per-mode artifact logged to MLflow
- MLflow experiment `"aml-governance"` — one run per mode, named `{model}_r{run_id}_{mode}`, with all metrics, params, and artifacts

Only modes present as columns in `summary.csv` are evaluated (dynamic — no hard-coded mode list).

## Langfuse Integration

Tracing is enabled automatically when `LANGFUSE_SECRET_KEY` is set in the environment (or `.env`). No code changes needed to toggle — the run script checks for the key at startup.

**How it works:** `02_run_experiment.py` creates a `CallbackHandler` per graph invocation and passes it via LangGraph's config propagation. Each LLM-powered node in `agents.py` accepts a `RunnableConfig` parameter and forwards it to `llm.invoke(..., config=config)`. This traces every LLM call with:
- `session_id`: `"{client_id}_{mode}"` (groups all calls for one client+mode)
- `trace_name`: `"{mode}/{client_id}"` (e.g., `"intrinsic/C1234"`)
- `metadata`: client_id and mode
- `tags`: mode and client_id (for filtering in the Langfuse UI)

**Graceful degradation:** If `LANGFUSE_SECRET_KEY` is not set, no handler is created, and the experiment runs identically without tracing.

## Environment

```bash
cp .env.example .env   # then fill in API keys
pip install -r requirements.txt
```

**Required env vars:** `OPENAI_API_KEY`
**Optional env vars:** `LLM_MODEL` (default: `gpt-4o-mini`), `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST`
**xAI/Grok env vars:** `XAI_API_KEY`, `XAI_BASE_URL` (default: `https://api.x.ai/v1`) — required when `LLM_MODEL` starts with `grok-`

## Coding Standards

- Modular, type-hinted, production-grade Python
- Always use specific **"Trap Cases"** to test reasoning failures — scenarios designed to expose when agents make incorrect judgments or miss critical signals
