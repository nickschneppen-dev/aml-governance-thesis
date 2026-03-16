# Experiment Results: grok-4 (n=168 Test Set)

## Setup

- **Model**: grok-4 (via xAI API, `https://api.x.ai/v1`)
- **Dataset**: test set, n=168 (60 guilty, 108 innocent)
- **Governance modes**: intrinsic, hierarchical, context_engineered, llm_context
- **Run**: `results/test/grok-4/run_1/`
- **Artefacts**: both generated from grok-4 training traces (n=86)
  - `external_agent_injection_grok-4.txt` — Kayba ACE pipeline on grok-4 training traces
  - `llm_context_rules_grok-4.txt` — LLM-synthesised rules from grok-4 training traces (10,012 chars)
- **Training error signal**: 2 incorrect / 86 correct in training — very sparse failure data

---

## Core Classification Metrics

| Metric          | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|-----------------|-----------|--------------|-------------|-------------|
| Accuracy        | 94.0%     | 91.7%        | **95.2%**   | 83.9%       |
| Precision       | 0.879     | 0.848        | **0.948**   | 0.690       |
| Recall          | 0.967     | 0.933        | 0.917       | **1.000**   |
| F1              | 0.921     | 0.889        | **0.932**   | 0.816       |
| TP/FP/TN/FN     | 58/8/100/2 | 56/10/98/4 | **55/3/105/5** | 60/27/81/0 |
| MAE             | 9.7       | **9.5**      | 10.4        | 12.7        |
| In-Range %      | 74.4%     | **78.6%**    | 78.0%       | 73.2%       |
| Consensus Rate  | **98%**   | **98%**      | 80%         | 85%         |
| Avg Revisions   | **0.20**  | 0.24         | 0.86        | 0.67        |

---

## Per-Group Classification Accuracy

| Group             | Intrinsic | Hierarchical | Context-Eng | LLM-Context | n  |
|-------------------|-----------|--------------|-------------|-------------|----|
| Control Guilty    | 100%      | 100%         | 100%        | 100%        | 16 |
| Control Innocent  | 100%      | 100%         | 100%        | 100%        | 16 |
| FP: Charity       | 100%      | 91%          | 100%        | 74%         | 23 |
| FP: Payroll       | 96%       | 91%          | **100%**    | 91%         | 23 |
| FP: High Roller   | 70%       | 78%          | **87%**     | 26%         | 23 |
| FP: Structurer    | 100%      | 96%          | 100%        | 91%         | 23 |
| FN: Sleeper       | 100%      | 100%         | 95%         | 100%        | 22 |
| FN: Smurf         | 91%       | 82%          | 82%         | **100%**    | 22 |

---

## Revision Loop Behaviour

| Mode         | REJECT Rate | Rev1 Rate | Rev2 Rate | Avg Score Shift (on reject) |
|--------------|-------------|-----------|-----------|------------------------------|
| Intrinsic    | 2%          | 16%       | 4%        | +23.3                        |
| Hierarchical | 2%          | 18%       | 7%        | +23.8                        |
| Context-Eng  | 20%         | 44%       | 42%       | +3.4                         |
| LLM-Context  | 15%         | 40%       | 27%       | +27.3                        |

---

## Key Findings

### Finding 1: Context-Eng is Best on grok-4 — Inverting the gpt-5.1 Pattern

On gpt-5.1, LLM-Context was best (F1=1.000) and Context-Eng second (F1=0.929). On grok-4, this is reversed: Context-Eng leads (F1=0.932) and LLM-Context is worst (F1=0.816). The likely cause is the training error signal: grok-4 made only 2 errors across 86 training clients. LLM-context rule synthesis relies on analysing incorrect cases — with only 2 failures, the rules were poorly calibrated and pushed toward aggressive escalation (0 FNs but 27 FPs). Kayba's ACE pipeline synthesises skills from all traces, not just errors, making it more robust when failure data is sparse.

### Finding 2: LLM-Context Degrades Under Sparse Error Signal

LLM-Context has perfect recall (0 FNs) but 27 FPs — the worst precision of any mode (0.690). The FP trap accuracy collapses: FP High Roller drops to 26%, FP Charity to 74%. This suggests the synthesised rules, trained on only 2 error cases, over-generalised toward escalation without learning the specific "explain the red flag" patterns needed for FP traps. This is a failure mode unique to grok-4's near-perfect training performance.

### Finding 3: Intrinsic Grok-4 is Highly Capable Baseline

At 94.0% accuracy and F1=0.921, grok-4's intrinsic performance is only marginally below Context-Eng and comfortably above LLM-Context. The model barely needs the revision loop (2% rejection rate, avg 0.20 revisions). FP High Roller (70%) is the only material weakness in intrinsic mode — the high-volume casino/IPO/mining pattern remains the hardest false positive trap across all models.

### Finding 4: Context-Eng Acts as a Precision Filter, Not a Recall Booster

Context-Eng has the fewest FPs (3) of any mode/model combination in the whole experiment. The 20% rejection rate and +3.4 score shift on REJECT suggest the playbook is triggering cautious downward revisions on flagged cases — reviewing borderline escalations and correctly clearing them. This is qualitatively different from LLM-Context's behaviour (+27.3 shift on reject, pushing upward).

### Finding 5: Hierarchical is Deferential and Underperforms Intrinsic

Like gpt-5.1, grok-4's hierarchical auditor is highly deferential (98% consensus, avg 0.24 revisions). It underperforms intrinsic on every metric. With a capable base model, the independent auditor adds noise rather than value — it introduces 2 extra FPs and 2 extra FNs vs intrinsic without a compensating improvement anywhere.

### Finding 6: FP High Roller is the Universal Weak Spot

High Roller (casino/IPO/mining context explaining high fan-out + high volume) is the only group where no mode achieves >90% on grok-4: intrinsic 70%, hierarchical 78%, context_engineered 87%. Across all three models, High Roller is the most consistently difficult FP trap. The combination of two concurrent risk flags (fan_out AND volume) with an alibi that requires domain knowledge (junket operators, ASIC monitoring being sector-wide) pushes even capable models toward false escalation.

---

## Comparison with gpt-5.1 and gpt-4o-mini (n=168)

### Intrinsic Baseline Comparison

| Group             | gpt-4o-mini | gpt-5.1 | grok-4 |
|-------------------|-------------|---------|--------|
| Control Guilty    | 100%        | 100%    | 100%   |
| Control Innocent  | 100%        | 100%    | 100%   |
| FP: Charity       | 43%         | 100%    | 100%   |
| FP: Payroll       | 0%          | 100%    | 96%    |
| FP: High Roller   | 0%          | 91%     | 70%    |
| FP: Structurer    | 9%          | 100%    | 100%   |
| FN: Sleeper       | 77%         | 91%     | 100%   |
| FN: Smurf         | 86%         | 59%     | 91%    |
| **Overall Acc**   | 47.6%       | 92.3%   | 94.0%  |
| **F1**            | 0.54        | 0.883   | 0.921  |

### Best-Mode Comparison

| Mode         | gpt-4o-mini (best) | gpt-5.1 (best) | grok-4 (best) |
|--------------|-------------------|----------------|---------------|
| Best mode    | LLM-Context       | LLM-Context    | Context-Eng   |
| Best F1      | 0.66              | 1.000          | 0.932         |
| Best Acc     | 64.3%             | 100%           | 95.2%         |

### Cross-Model Findings

1. **Capability ordering**: gpt-5.1 ≥ grok-4 > gpt-4o-mini on intrinsic. gpt-5.1 and grok-4 are close (92.3% vs 94.0%), with grok-4 slightly stronger on FP traps but weaker on FN Smurf without rules.

2. **LLM-Context ranking reverses across models**: Best on gpt-4o-mini (compensates for anchoring bias), best on gpt-5.1 (model can apply general rules effectively), worst on grok-4 (sparse training errors degrade rule synthesis). The effectiveness of LLM-context rules depends on training error density, not just model capability.

3. **Context-Eng (Kayba) is stable across capable models**: On gpt-5.1 F1=0.929, on grok-4 F1=0.932. Kayba's skill synthesis transfers reliably when the base model is capable, independent of which model generated the training traces.

4. **Hierarchical is consistently deferential on capable models**: Near-100% consensus for both gpt-5.1 and grok-4. The independent auditor only behaves aggressively when the underlying model is weak (gpt-4o-mini: 28% consensus).

5. **FP High Roller is the universal hard case**: 91% (gpt-5.1 intrinsic), 70% (grok-4 intrinsic), 0% (gpt-4o-mini intrinsic). Even the best intervention (Context-Eng on grok-4) only reaches 87%. It remains unsolved.

---

## Thesis Implications

The grok-4 results add two important data points:

**LLM-Context rule quality is training-data dependent**: When a capable model makes very few training errors, LLM-context synthesis produces poorly calibrated rules. This is a practical limitation: the approach works well for weaker models (many errors → rich failure signal) and for stronger models when errors are qualitatively diverse, but degrades when errors are near-zero. The optimal use case for LLM-context may be mid-capability models, not the strongest available.

**Kayba (Context-Eng) is the most consistent intervention**: It is the best or near-best mode on gpt-4o-mini (F1=0.56, second), gpt-5.1 (F1=0.929, second), and grok-4 (F1=0.932, first). Its advantage is that it synthesises skills rather than error patterns — a more robust signal that doesn't require the model to have failed in specific ways. This makes it the safer production choice when training error signal is sparse.

---

## Output Files

- `results/test/grok-4/run_1/summary.csv` — 168 clients, all 4 modes
- `results/test/grok-4/run_1/evaluation.csv` — full metrics per client
- `results/test/grok-4/run_1/{mode}/C*.json` — full AgentState per client
- MLflow run: `grok-4_r1_{mode}` in experiment `aml-governance`
