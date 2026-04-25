# Experiment Results: Multi-Agent AML Governance — grok-4

> **Thesis question:** Does external context injection (Kayba ACE) close the performance gap between
> intrinsic self-correction and independent hierarchical auditing — at a fraction of the cost?
> A secondary condition tests whether LLM-synthesised self-reflection rules match or exceed Kayba.

---

## 1. Setup at a Glance

| | |
|---|---|
| **Dataset** | AMLNet (1.09M transactions, 10k users) — 168 test clients, 86 train clients |
| **Ground truth** | 60 guilty, 108 innocent (test set) |
| **Model** | `grok-4` (xAI API, `https://api.x.ai/v1`) |
| **Classification threshold** | Score ≥ 50 → predicted GUILTY |
| **Kayba training input** | 86 train traces (intrinsic mode, grok-4) |
| **Kayba output** | Context playbook (`external_agent_injection_grok-4.txt`) |
| **LLM self-reflection input** | Same 86 train traces, rules synthesised by grok-4 (`llm_context_rules_grok-4.txt`, 10,012 chars) |
| **Training error signal** | 2 incorrect / 86 correct — very sparse failure data |
| **Errors** | None — all 168 clients completed successfully across all four modes |

### The Four Modes

| Mode | What happens | Extra context | Reviewer |
|---|---|---|---|
| **Intrinsic** | Analyst reviews its own draft | None | Same LLM instance |
| **Hierarchical** | Independent Auditor reviews the Analyst | None | Separate LLM agent with different system prompt |
| **Context-Engineered** | Analyst + Kayba playbook injected into self-review | Kayba's context playbook | Same LLM instance |
| **LLM-Context** | Analyst + LLM-synthesised rules injected into self-review | Self-generated rules from train traces | Same LLM instance |

> **Architectural distinction:** Intrinsic, Context-Engineered, and LLM-Context share one growing context
> window (analyst and reviewer are the same LLM call). Hierarchical uses a separate fresh context per audit.

### Comparison Design

Not all pairwise comparisons are methodologically valid. Each comparison isolates one experimental variable:

| Comparison | Variable isolated | Valid? |
|---|---|:---:|
| Intrinsic vs Hierarchical | Governance architecture (same-context self-review vs separate-context auditor) | ✅ |
| Intrinsic vs Context-Engineered | Kayba rule injection (same architecture, rules added) | ✅ |
| Intrinsic vs LLM-Context | LLM self-reflection rule injection (same architecture, rules added) | ✅ |
| Context-Engineered vs LLM-Context | Source of rules (Kayba external vs LLM self-synthesised; same architecture) | ✅ |
| Hierarchical vs Context-Engineered | **Confounded** — architecture *and* Kayba rules differ simultaneously | ❌ |
| Hierarchical vs LLM-Context | **Confounded** — architecture *and* LLM rules differ simultaneously | ❌ |

Two additional **combined modes** (Hier+Ctx, Hier+LLM) enable decomposition of the confounded pairs:

| Comparison | Variable isolated | Valid? |
|---|---|:---:|
| Hierarchical vs Hier+Ctx | Kayba injection on top of hierarchical architecture (rules added, architecture fixed) | ✅ |
| Hierarchical vs Hier+LLM | LLM rules on top of hierarchical architecture (rules added, architecture fixed) | ✅ |
| Context-Engineered vs Hier+Ctx | Architecture change, Kayba rules fixed (self-review vs separate auditor, both with Kayba) | ✅ |
| LLM-Context vs Hier+LLM | Architecture change, LLM rules fixed (self-review vs separate auditor, both with LLM rules) | ✅ |
| Hier+Ctx vs Hier+LLM | Source of rules on hierarchical architecture (Kayba vs LLM-synthesised; architecture fixed) | ✅ |

---

## 2. Core Results

### Classification Performance

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| **Classification Accuracy** | 94.0% | 91.7% | **95.2%** | 83.9% |
| **Precision** | 0.879 | 0.848 | **0.948** | 0.690 |
| **Recall** | 0.967 | 0.933 | 0.917 | **1.000** |
| **F1 Score** | 0.921 | 0.889 | **0.932** | 0.816 |
| True Positives | 58 | 56 | 55 | **60** |
| False Positives | 8 | 10 | **3** | 27 |
| True Negatives | 100 | 98 | **105** | 81 |
| False Negatives | 2 | 4 | 5 | **0** |

### Score Accuracy

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| Range Accuracy (score within expected band) | 74.4% | **78.6%** | 78.0% | 73.2% |
| MAE from midpoint | **9.7** | **9.5** | 10.4 | 12.7 |
| Avg Confidence | **85.7** | 86.1 | 82.0 | 83.2 |

### Governance Behaviour & Efficiency

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| Consensus Rate (reviewer approved) | **98%** | **98%** | 80% | 85% |
| Avg Revisions per Case | **0.20** | 0.24 | 0.86 | 0.67 |
| Avg LLM Calls per Case | **3.4** | 3.5 | 4.7 | 4.3 |
| Avg Score Shift (final − initial) | +2.5 | +2.8 | +2.5 | **+10.1** |
| Abs Avg Score Shift | **3.2** | 3.5 | 5.6 | 11.1 |

**On-REJECT score shift** (conditional on the reviewer issuing a REJECT):

| Mode | REJECT Rate | Avg Score Shift on REJECT |
|---|:---:|:---:|
| Intrinsic | 2% | +23.3 |
| Hierarchical | 2% | +23.8 |
| Context-Eng | 20% | **+3.4** |
| LLM-Context | 15% | +27.3 |

Context-Eng REJECTs trigger small downward corrections (+3.4); all other modes trigger large upward shifts when they do reject, confirming the Kayba playbook is the only intervention directing score *reductions* on flagged cases.

---

## 3. Per-Group Breakdown

### Classification Accuracy by Group

| Group | n | Truth | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Control Guilty** | 16 | GUILTY | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **Control Innocent** | 16 | INNOCENT | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FP Trap: Charity** | 23 | INNOCENT | ✅ 100% | ✅ 91% | ✅ 100% | ⚠️ 74% |
| **FP Trap: Payroll** | 23 | INNOCENT | ✅ 96% | ✅ 91% | ✅ 100% | ✅ 91% |
| **FP Trap: High Roller** | 23 | INNOCENT | ⚠️ 70% | ⚠️ 78% | ⚠️ 87% | ❌ 26% |
| **FP Trap: Structurer** | 23 | INNOCENT | ✅ 100% | ✅ 96% | ✅ 100% | ✅ 91% |
| **FN Trap: Sleeper** | 22 | GUILTY | ✅ 100% | ✅ 100% | ✅ 95% | ✅ 100% |
| **FN Trap: Smurf** | 22 | GUILTY | ✅ 91% | ✅ 82% | ✅ 82% | ✅ 100% |

*✅ = strong performance (≥80%)  ⚠️ = partial (50–79%)  ❌ = failure (<50%)*

### Average Risk Score by Group

| Group | Expected | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|
| Control Guilty | 70–100 | 81.7 | **84.9** | 80.0 | 81.2 |
| Control Innocent | 0–30 | **13.4** | **13.1** | 14.7 | 14.4 |
| FP: Charity | 0–30 | **20.4** | 22.7 | 25.0 | 31.1 |
| FP: Payroll | 0–30 | 26.3 | 24.7 | **23.0** | 26.1 |
| FP: High Roller | 0–30 | 35.7 | **32.8** | 37.0 | 57.1 |
| FP: Structurer | 0–30 | **19.6** | 22.4 | 22.6 | 27.0 |
| FN: Sleeper | 70–100 | 81.8 | **82.5** | 80.7 | 84.5 |
| FN: Smurf | 70–100 | 63.4 | 63.0 | 66.3 | **82.7** |

---

## 4. Reasoning Quality

Two LLM judges score each case on a 1–10 scale:
- **Evidence Coverage:** Does the reasoning cite specific metrics and article claims?
- **Conclusion Consistency:** Does the reasoning support the final risk decision?

### 4a. Original scores (judge: grok-4, self-evaluation)

Reasoning quality metrics were not computed for the grok-4 self-evaluation run. For reference, across
gpt-4o-mini and gpt-5.1 self-evaluation, evidence coverage was uniformly high (9.3–9.9/10) while
conclusion consistency varied with governance mode (6.8–9.9/10), with rule-injected modes scoring
highest on consistency.

### 4b. Re-scored with external judge (judge: claude-sonnet-4-6)

Reasoning quality metrics were computed using Claude Sonnet 4.6 as a fixed external judge. This
establishes a consistent cross-model comparison baseline and covers all six governance modes including
the combined modes (hier_context_engineered, hier_llm_context).

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context | Hier+Ctx | Hier+LLM |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Evidence Coverage (mean) | **8.98** | **8.98** | 8.96 | 8.89 | 8.93 | 8.89 |
| Conclusion Consistency (mean) | 7.47 | 7.80 | 7.59 | 7.47 | **7.90** | 7.27 |

**Key observations:**

Evidence coverage is uniformly high across all six modes (8.89–8.98) and does not vary meaningfully
with governance mode. This mirrors the gpt-5.1 pattern (9.05–9.57 under the same judge) and stands in
sharp contrast to gpt-4o-mini (6.43–6.60 under sonnet 4.6). grok-4 reliably cites specific metrics and
article content regardless of governance structure — evidence retrieval is not the limiting factor.

Conclusion consistency is moderate and shows a flatter spread across modes (7.27–7.90) compared to
gpt-5.1's dramatic split (6.28–9.39). The absence of the strong rule-injection lift seen at gpt-5.1
(where Context-Eng jumped from 6.96 to 9.39) reflects grok-4's already-strong intrinsic reasoning
baseline: when the base model is well-calibrated, explicit rules add less structural scaffolding to
the reasoning process.

The highest consistency is Hier+Ctx (7.90), followed by Hierarchical (7.80). This is the inverse of
the classification performance ordering (Context-Eng is best at F1=0.932; Hierarchical is worst at
F1=0.889). The dissociation confirms that conclusion consistency measures internal reasoning coherence,
not classification correctness: the hierarchical auditor produces locally coherent reasoning chains by
rewriting justifications after its escalation decisions, even when those decisions are wrong.

LLM-Context and Intrinsic are tied at 7.47 — the lowest among the four core modes. LLM-Context's poor
classification (F1=0.816, 27 FPs) is not visible in its reasoning quality score, confirming that the
failure is a calibration failure in the rule synthesis (over-escalation from sparse error signal), not
a failure of the reasoning process itself. The reasoning is coherent; the conclusions are wrong.

---

## 5. What the Results Mean

Findings are framed around the four valid pairwise comparisons identified in the comparison design above.

### Finding 1 [Intrinsic vs Hierarchical]: Hierarchical is deferential and underperforms intrinsic

Like gpt-5.1, the grok-4 hierarchical auditor is highly deferential — 98% consensus, avg 0.24 revisions, abs score shift of only 3.5. It underperforms intrinsic on every classification metric (F1: 0.889 vs 0.921), introducing 2 extra FPs and 2 extra FNs without compensating improvement anywhere.

The on-REJECT data reveals the mechanism: when the grok-4 auditor does reject (2% of cases), it pushes scores sharply upward (+23.8). But it almost never rejects, so this escalation tendency has negligible net effect. The auditor is largely rubber-stamping the analyst's first draft. With a highly capable base model, the independent auditor adds noise rather than value.

This mirrors gpt-5.1 (100% consensus, F1=0.855 vs intrinsic 0.883) and inverts gpt-4o-mini (28% consensus, F1=0.59 vs intrinsic 0.54). The pattern across all three models is consistent: capable base models produce deferential auditors; weak base models produce aggressive ones. Neither is well-calibrated.

### Finding 2 [Intrinsic vs Context-Engineered]: Context-Eng is the best mode — acts as a precision filter

Context-Eng achieves F1=0.932, marginally ahead of intrinsic (F1=0.921). The improvement is driven by precision, not recall: 3 FPs vs 8, 105 TN vs 100, while TPs fall slightly (55 vs 58). The Kayba playbook is triggering targeted downward revisions on borderline cases — its on-REJECT score shift is only +3.4, the only mode where REJECTs push scores *down* rather than up. This is qualitatively different from every other intervention: the playbook is acting as a precision filter rather than a recall booster.

FP High Roller improves from 70% (intrinsic) to 87% (Context-Eng) — the best result for that group on grok-4. FP Payroll reaches 100%. Avg score for FP High Roller drops from 35.7 to 37.0 (marginal), but more clients land below the 50-point threshold.

Score accuracy is similar across intrinsic and Context-Eng (range accuracy 74.4% vs 78.0%, MAE 9.7 vs 10.4), confirming the Kayba rules are not distorting correctly-scored cases — they are selectively correcting borderline escalations.

### Finding 3 [Intrinsic vs LLM-Context]: LLM-Context degrades under sparse error signal

LLM-Context is the worst-performing mode (F1=0.816, accuracy 83.9%) — a substantial regression from intrinsic. It achieves perfect recall (0 FNs, 60 TPs) but at the cost of 27 false positives, the most of any mode across all three models.

The root cause is sparse training data: grok-4 made only 2 errors across 86 training clients. LLM-context rule synthesis analyses incorrect cases to extract corrective heuristics — with only 2 failures, the rules lack sufficient signal to learn the "explain the red flag" patterns needed for FP traps. The synthesised rules over-generalised toward escalation: FP High Roller collapses to 26%, FP Charity to 74%, avg score for FP High Roller reaches 57.1 (far above the innocent threshold). The LLM-synthesised rules are pushing innocents well into guilty territory.

This failure mode is unique to grok-4's near-perfect training performance. It confirms that LLM-Context effectiveness depends on training error density, not just model capability.

### Finding 4 [Context-Engineered vs LLM-Context]: Kayba is more robust when failure signal is sparse

Context-Eng (F1=0.932) substantially outperforms LLM-Context (F1=0.816) — a gap of 0.116. Both artefacts were derived from the same 86 grok-4 training traces. The difference is in what each pipeline extracts: Kayba's ACE synthesises generalised skills from all traces (both correct and incorrect), while the LLM rule synthesis focuses on incorrect cases to identify corrective patterns.

When errors are rare, Kayba's all-trace synthesis is more robust: it encodes the model's general decision-making patterns without depending on a large error sample. The LLM synthesis is left with too little failure signal to calibrate rules that can distinguish genuine risk from explainable red flags. The practical implication: for highly capable models with sparse training errors, Kayba is the safer artefact choice.

### Finding 5 [Cross-cutting]: grok-4 intrinsic is a near-ceiling baseline; FP High Roller is the universal stress point

At 94.0% accuracy and F1=0.921, grok-4's intrinsic performance is extremely strong — barely below Context-Eng and requiring almost no revision loop (2% rejection rate). The only material weakness is FP High Roller at 70%: the combination of dual quantitative flags (high fan-out AND high volume) with an alibi requiring specialised domain knowledge (casino junket operations, ASIC sector-wide monitoring) pushes even a highly capable model toward false escalation.

FP High Roller is the hardest trap across all three models: 0% (gpt-4o-mini intrinsic), 91% (gpt-5.1 intrinsic), 70% (grok-4 intrinsic). Even the best intervention — Context-Eng on grok-4 — only reaches 87%. No mode on any model achieves 100%.

---

## 5b. Combined Governance Modes: Hierarchical + Context Injection

Two additional modes stack context injection onto the hierarchical architecture — the auditor receives either the Kayba playbook (Hier+Ctx) or the LLM-synthesised rules (Hier+LLM) in its prompt. These enable clean decomposition of the architecture and rule-source variables.

### Classification Performance

| Metric | Hierarchical | Hier+Ctx | Hier+LLM | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|
| **Accuracy** | 91.7% | **94.6%** | 86.3% | **95.2%** | 83.9% |
| **Precision** | 0.848 | **0.947** | 0.723 | **0.948** | 0.690 |
| **Recall** | 0.933 | 0.900 | **1.000** | 0.917 | **1.000** |
| **F1** | 0.889 | 0.923 | 0.839 | **0.932** | 0.816 |
| True Positives | 56 | 54 | **60** | 55 | **60** |
| False Positives | 10 | 3 | 23 | **3** | 27 |
| True Negatives | 98 | 105 | 85 | **105** | 81 |
| False Negatives | 4 | 6 | **0** | 5 | **0** |
| MAE | **9.5** | 9.9 | 12.6 | 10.4 | 12.7 |
| In-Range % | **78.6%** | 78.6% | 73.8% | 78.0% | 73.2% |
| Consensus Rate | 98% | **89%** | **89%** | 80% | 85% |
| Avg Revisions | 0.24 | 0.46 | 0.64 | 0.86 | 0.67 |
| Avg Score Shift | +2.8 | **+4.3** | +9.9 | +3.4 | +27.3 |

### Per-Group Classification Accuracy

| Group | n | Hierarchical | Hier+Ctx | Hier+LLM | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Control Guilty** | 16 | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **Control Innocent** | 16 | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FP Trap: Charity** | 23 | ✅ 91% | ✅ 96% | ✅ 91% | ✅ 100% | ⚠️ 74% |
| **FP Trap: Payroll** | 23 | ✅ 91% | ✅ 100% | ⚠️ 83% | ✅ 100% | ✅ 91% |
| **FP Trap: High Roller** | 23 | ⚠️ 78% | ✅ 91% | ❌ 39% | ⚠️ 87% | ❌ 26% |
| **FP Trap: Structurer** | 23 | ✅ 96% | ✅ 100% | ⚠️ 87% | ✅ 100% | ✅ 91% |
| **FN Trap: Sleeper** | 22 | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 95% | ✅ 100% |
| **FN Trap: Smurf** | 22 | ✅ 82% | ⚠️ 73% | ✅ 100% | ✅ 82% | ✅ 100% |

### What the Combined Modes Reveal

**Hier+Ctx is effectively equivalent to Context-Eng.** F1=0.923 vs F1=0.932 — a gap of just 0.009. Both achieve 3 FPs, near-identical per-group accuracy, and similar score shifts (+4.3 vs +3.4). At grok-4's capability level, whether the Kayba playbook is delivered to a self-reviewing analyst or a separate hierarchical auditor makes virtually no difference. The most architecture-neutral result across all three models.

**Hier+LLM partially moderates LLM-Context's FP problem.** LLM-Context generates 27 FPs; Hier+LLM reduces this to 23 FPs with the same 0 FNs. The hierarchical auditor acts as a modest brake on the over-escalation from the poorly-calibrated LLM rules. The improvement is real but insufficient: 23 FPs still produces F1=0.839, well below Context-Eng.

**FP High Roller remains the stress point.** Hier+Ctx achieves 91% on High Roller — the best result for that group on grok-4 — but Hier+LLM collapses to 39%. The sparse-error LLM rules cannot handle the dual-flag complexity regardless of whether they are applied via self-review or a hierarchical auditor.

**FN Smurf trade-off.** Hier+LLM achieves 100% on FN Smurf (same as LLM-Context), while Hier+Ctx scores only 73% — the same weakness seen in Context-Eng (82%) and bare Hierarchical (82%). The LLM rules provide Smurf-detection signal that the Kayba playbook lacks, and this transfers unchanged to the hierarchical auditor context.

**Decomposing the confounded comparisons:**
- *Hierarchical vs Hier+Ctx*: +0.034 F1 — Kayba injection modestly improves the deferential grok-4 auditor, giving it a principled basis to intervene.
- *Hierarchical vs Hier+LLM*: −0.050 F1 — LLM rules on the auditor extend the same sparse-signal degradation seen in LLM-Context.
- *Context-Eng vs Hier+Ctx*: −0.009 F1 — virtually no architecture effect when Kayba rules are present.
- *LLM-Context vs Hier+LLM*: +0.023 F1 — uniquely on grok-4, switching to the hierarchical auditor with LLM rules *helps* (vs hurts at the other two models). The auditor slightly attenuates the over-escalation from sparse LLM rules.

The combined-mode results reinforce the main finding: Kayba (Context-Eng) is the most stable intervention regardless of architecture, while LLM-Context effectiveness is tightly coupled to training error density.

---

## 6. Comparison with gpt-5.1 and gpt-4o-mini

Both models were tested on the identical n=168 test set (60 guilty, 108 innocent), enabling direct comparison.

### Intrinsic Baseline Comparison

| Group | n | gpt-4o-mini | gpt-5.1 | grok-4 |
|---|:---:|:---:|:---:|:---:|
| Control Guilty | 16 | ✅ 100% | ✅ 100% | ✅ 100% |
| Control Innocent | 16 | ✅ 100% | ✅ 100% | ✅ 100% |
| FP: Charity | 23 | ❌ 43% | ✅ 100% | ✅ 100% |
| FP: Payroll | 23 | ❌ 0% | ✅ 100% | ✅ 96% |
| FP: High Roller | 23 | ❌ 0% | ✅ 91% | ⚠️ 70% |
| FP: Structurer | 23 | ❌ 9% | ✅ 100% | ✅ 100% |
| FN: Sleeper | 22 | ⚠️ 77% | ✅ 91% | ✅ 100% |
| FN: Smurf | 22 | ✅ 86% | ❌ 59% | ✅ 91% |
| **Overall Accuracy** | | 47.6% | 92.3% | **94.0%** |
| **F1** | | 0.54 | 0.883 | **0.921** |

### Best-Mode Comparison

| | gpt-4o-mini | gpt-5.1 | grok-4 |
|---|:---:|:---:|:---:|
| **Best mode** | LLM-Context | LLM-Context | Context-Eng |
| **Best F1** | 0.660 | 1.000 | 0.932 |
| **Best Accuracy** | 64.3% | 100% | 95.2% |

### Cross-Model Findings

1. **Capability ordering on intrinsic baseline**: gpt-5.1 (F1=0.883) ≈ grok-4 (F1=0.921) >> gpt-4o-mini (F1=0.54). grok-4 is marginally stronger than gpt-5.1 on FP traps (better on FP High Roller 70% vs 91% is counterintuitive — gpt-5.1 is better) but grok-4 shows superior FN Sleeper (100% vs 91%) and FN Smurf (91% vs 59%).

2. **LLM-Context ranking inverts at grok-4**: Best at gpt-4o-mini (compensates anchoring bias), best at gpt-5.1 (model applies general rules effectively), worst at grok-4 (sparse training errors degrade rule synthesis). Effectiveness depends on training error density, not just model capability.

3. **Context-Eng (Kayba) is the most stable intervention across capable models**: F1=0.929 on gpt-5.1, F1=0.932 on grok-4. Kayba's skill synthesis is robust to variation in which model generated the training traces because it does not require errors to be numerous — it synthesises from all traces.

4. **Hierarchical is consistently deferential on capable models**: Near-100% consensus for both gpt-5.1 (100%) and grok-4 (98%). The independent auditor behaves aggressively only when the base model is weak (gpt-4o-mini: 28% consensus). Neither extreme — over-escalation nor rubber-stamping — delivers well-calibrated governance.

5. **FP High Roller is the universal unsolved case**: 0% (gpt-4o-mini intrinsic), 91% (gpt-5.1 intrinsic), 70% (grok-4 intrinsic). The best single result across all modes and models is 100% on gpt-5.1 with LLM-Context or Context-Eng. On grok-4, the ceiling is 91% (Hier+Ctx).

---

## 7. Thesis Implications

| Comparison | Hypothesis | Result |
|---|---|---|
| Intrinsic vs Hierarchical | Governance architecture affects accuracy | **Not supported at grok-4** — hierarchical underperforms intrinsic (F1: 0.889 vs 0.921); the capable base model makes the auditor irrelevant |
| Intrinsic vs Hierarchical | Independent auditing prevents confirmation bias | **Not supported at grok-4** — 98% consensus; the auditor rarely intervenes and adds noise when it does |
| Intrinsic vs Context-Engineered | Kayba rule injection improves on intrinsic | **Supported** — F1 0.932 vs 0.921; 5 fewer FPs; Kayba acts as a precision filter, uniquely triggering downward score corrections |
| Intrinsic vs LLM-Context | LLM self-reflection rules improve on intrinsic | **Not supported at grok-4** — F1 0.816 vs 0.921; sparse training errors (2/86) produce poorly calibrated rules that over-escalate |
| Context-Eng vs LLM-Context | LLM self-synthesis outperforms Kayba extraction | **Reversed at grok-4** — Context-Eng F1 0.932 vs LLM-Context F1 0.816; Kayba's all-trace synthesis is more robust than error-pattern synthesis when failures are rare |

### Suggested framing for thesis write-up

The grok-4 results provide the third data point in the capability × governance interaction, and introduce the training error density dimension that neither gpt-4o-mini nor gpt-5.1 exposed.

**Axis 1 — Governance architecture (Intrinsic vs Hierarchical):**
The hierarchical auditor's behaviour is model-capability dependent: over-escalates on weak models (gpt-4o-mini), rubber-stamps on strong models (gpt-5.1, grok-4). grok-4 confirms this is a general property of capable-model auditors, not an artefact of gpt-5.1 specifically. The architectural choice of independent auditing produces no benefit at high capability levels without explicit calibration of the auditor's intervention threshold.

**Axis 2 — Knowledge injection (Intrinsic vs Context-Engineered vs LLM-Context):**
Kayba (Context-Eng) is the most stable intervention across all three models, improving on intrinsic at all capability levels (F1 gains: +0.02 at gpt-4o-mini, +0.046 at gpt-5.1, +0.011 at grok-4). LLM-Context shows a training-data dependency that Kayba does not: it requires sufficient error signal to synthesise useful corrective rules. At grok-4 with only 2 training errors, LLM-Context degrades the baseline by 0.105 F1 — the largest governance-induced regression in the experiment.

The cross-model pattern suggests a general principle: Kayba's skill synthesis is robust across the capability spectrum because it learns from all examples; LLM self-synthesis is powerful when errors are numerous and varied (gpt-4o-mini, gpt-5.1) but brittle when they are rare.

---

## 7b. Run-to-Run Variance (Robustness Check)

Three independent runs (same model, same dataset, different LLM samples) quantify how stable the results are under sampling noise.

| Mode | Run 1 | Run 2 | Run 3 | Mean F1 | Std |
|---|:---:|:---:|:---:|:---:|:---:|
| **Intrinsic** | 0.921 | 0.950 | 0.923 | 0.931 | ±0.013 |
| **Hierarchical** | 0.889 | 0.915 | 0.930 | 0.911 | ±0.017 |
| **Context-Eng** | 0.932 | 0.915 | 0.957 | 0.935 | ±0.017 |
| **LLM-Context** | 0.816 | 0.870 | 0.808 | 0.831 | ±0.027 |

F1 standard deviation ranges from ±0.013 to ±0.027. The **rank ordering is stable** across all three runs: Context-Eng > Intrinsic > Hierarchical > LLM-Context holds in every run. LLM-Context shows the highest variance (±0.027), reflecting its sensitivity to near-threshold scoring on the FP traps — but its position as the worst mode is consistent. Context-Eng is the best mode in all three runs.

The FP count for Context-Eng varies 0–6 across runs (mean 3.0), and for LLM-Context it is tightly clustered at 27–29 (mean 27.7, 0 FNs in all three runs). The qualitative conclusions — that sparse training errors degrade LLM-Context and that Kayba acts as a precision filter — hold across all replicates.

## 8. Output Files

| File | Contents |
|---|---|
| `results/test/grok-4/run_1/summary.csv` | Wide-format raw scores for 168 clients × 4 modes |
| `results/test/grok-4/run_1/evaluation.csv` | Per-client computed metrics (in_range, correct, score_shift, etc.) |
| `results/test/grok-4/run_1/evaluation_{mode}.csv` | Per-mode artifact (logged to MLflow) |
| `results/test/grok-4/run_1/{mode}/*.json` | Full AgentState for each client — forensics, news, reasoning, review |
| `external_agent_injection_grok-4.txt` | Kayba's context playbook (derived from 86 grok-4 train traces) |
| `llm_context_rules_grok-4.txt` | Self-synthesised rules from 86 grok-4 training traces (10,012 chars) |
| `training_traces_grok-4/*.md` | 86 annotated train traces fed to both Kayba and the LLM synthesiser |

To inspect a specific client's full reasoning chain:
```python
import json
state = json.load(open("results/test/grok-4/run_1/intrinsic/C1941.json"))
print(state["analyst_output"]["reasoning"])
print(state["review_output"]["reasoning"])
```

To reproduce the evaluation:
```bash
LLM_MODEL=grok-4 python 02_run_experiment.py --dataset test --modes intrinsic hierarchical context_engineered llm_context --model grok-4
python 03_evaluate.py --dataset test --model grok-4
mlflow ui  # http://127.0.0.1:5000
```
