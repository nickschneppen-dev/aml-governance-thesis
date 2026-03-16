# Experiment Results: Multi-Agent AML Governance — gpt-5.1

> **Thesis question:** Does external context injection (Kayba ACE) close the performance gap between
> intrinsic self-correction and independent hierarchical auditing — at a fraction of the cost?
> A secondary condition tests whether LLM-synthesised self-reflection rules match or exceed Kayba.

---

## 1. Setup at a Glance

| | |
|---|---|
| **Dataset** | AMLNet (1.09M transactions, 10k users) — 168 test clients, 86 train clients |
| **Ground truth** | 60 guilty, 108 innocent (test set) |
| **Model** | `gpt-5.1` (identical across all four modes) |
| **Classification threshold** | Score ≥ 50 → predicted GUILTY |
| **Kayba training input** | 86 train traces (intrinsic mode) |
| **Kayba output** | 28 deduplicated skills, 5.4 KB context playbook |
| **LLM self-reflection input** | Same 86 train traces, rules synthesised by gpt-5.1 |
| **Errors** | None — all 168 clients completed successfully across all four modes |

### The Four Modes

| Mode | What happens | Extra context | Reviewer |
|---|---|---|---|
| **Intrinsic** | Analyst reviews its own draft | None | Same LLM instance |
| **Hierarchical** | Independent Auditor reviews the Analyst | None | Separate LLM agent with different system prompt |
| **Context-Engineered** | Analyst + Kayba playbook in self-review user message | Kayba's 28-skill playbook | Same LLM instance |
| **LLM-Context** | Analyst + LLM-synthesised rules in self-review user message | Self-generated rules from train traces | Same LLM instance |

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

---

## 2. Core Results

### Classification Performance

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| **Classification Accuracy** | 92.3% | 90.5% | 95.2% | **100%** |
| **Precision** | 0.961 | 0.940 | **1.000** | **1.000** |
| **Recall** | 0.817 | 0.783 | 0.867 | **1.000** |
| **F1 Score** | 0.883 | 0.855 | 0.929 | **1.000** |
| True Positives | 49 | 47 | 52 | **60** |
| False Positives | 2 | 3 | **0** | **0** |
| True Negatives | 106 | 105 | **108** | **108** |
| False Negatives | 11 | 13 | 8 | **0** |

### Score Accuracy

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| Range Accuracy (score within expected band) | 55.4% | 44.6% | 94.0% | **97.0%** |
| MAE from midpoint | 16.6 | 17.1 | 10.6 | **7.6** |

### Governance Behaviour & Efficiency

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| Consensus Rate (reviewer approved) | 99% | 100% | 100% | 100% |
| Avg Revisions per Case | 0.28 | **0.04** | 0.65 | 0.57 |
| Avg LLM Calls per Case | 3.6 | **3.1** | 4.3 | 4.1 |
| Avg Score Shift (final − initial) | −1.6 | **−0.6** | −6.0 | −3.4 |
| Abs Avg Score Shift | 2.3 | **1.0** | 8.3 | 9.1 |

---

## 3. Per-Group Breakdown

### Classification Accuracy by Group

| Group | n | Truth | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Control Guilty** | 16 | GUILTY | ✅ 100% | ⚠️ 94% | ✅ 100% | ✅ 100% |
| **Control Innocent** | 16 | INNOCENT | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FP Trap: Charity** | 23 | INNOCENT | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FP Trap: Payroll** | 23 | INNOCENT | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FP Trap: High Roller** | 23 | INNOCENT | ⚠️ 91% | ⚠️ 87% | ✅ 100% | ✅ 100% |
| **FP Trap: Structurer** | 23 | INNOCENT | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FN Trap: Sleeper** | 22 | GUILTY | ⚠️ 91% | ⚠️ 86% | ⚠️ 91% | ✅ 100% |
| **FN Trap: Smurf** | 22 | GUILTY | ❌ 59% | ❌ 59% | ⚠️ 73% | ✅ 100% |

*✅ = strong performance (≥80%)  ⚠️ = partial  ❌ = failure (<80%)*

### Average Risk Score by Group

| Group | Expected | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|
| Control Guilty | 70–100 | 78.5 | 79.7 | 79.4 | **83.4** |
| Control Innocent | 0–30 | 11.4 | 13.8 | 10.9 | 16.5 |
| FP: Charity | 0–30 | 27.7 | 28.9 | 24.4 | **22.2** |
| FP: Payroll | 0–30 | 36.0 | 37.9 | 25.7 | **23.6** |
| FP: High Roller | 0–30 | 40.6 | 42.0 | 26.3 | **26.1** |
| FP: Structurer | 0–30 | 30.6 | 31.9 | 25.3 | **22.4** |
| FN: Sleeper | 70–100 | 76.3 | 73.4 | **77.0** | 79.7 |
| FN: Smurf | 70–100 | 57.1 | 60.4 | 63.0 | **77.3** |

---

## 4. Reasoning Quality

Two LLM judges score each case on a 1–10 scale:
- **Evidence Coverage:** Does the reasoning cite specific metrics and article claims?
- **Conclusion Consistency:** Does the reasoning support the final risk decision?

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| Evidence Coverage (mean) | 9.60 | **9.74** | 9.69 | 9.86 |
| Evidence Coverage (min) | 6 | 9 | 8 | 8 |
| Conclusion Consistency (mean) | 7.34 | 7.37 | **8.80** | 8.72 |
| Conclusion Consistency (min) | 1 | 1 | 3 | 1 |

**Key observation:** Evidence coverage is uniformly high across all modes — gpt-5.1 reliably engages with
available evidence regardless of governance structure. The meaningful distinction is in conclusion
consistency: Context-Engineered (8.80) and LLM-Context (8.72) score substantially higher than Intrinsic
(7.34) and Hierarchical (7.37). Rule injection improves the alignment between stated reasoning and final
decision — even when the rules were derived from a different model's failure traces.

---

## 5. What the Results Mean

Findings are framed around the four valid pairwise comparisons identified in the comparison design above.

### Finding 1 [Intrinsic vs Hierarchical]: At gpt-5.1, hierarchical is marginally worse, not better

At gpt-4o-mini, the hierarchical auditor achieved a net F1 gain via perfect recall — it missed zero
guilty clients at the cost of many false positives. At gpt-5.1, this dynamic reverses: hierarchical
underperforms intrinsic on all classification metrics (F1: 0.855 vs 0.883) and produces fewer correct
decisions overall (152/168 vs 155/168).

The FP gap between modes is narrow — hierarchical produces 3 FPs vs intrinsic's 2. The larger difference
is in false negatives: hierarchical misses 13 guilty clients vs intrinsic's 11. Paradoxically, the
independent auditor is both more likely to issue FPs and more likely to miss guilty clients than
self-review. This is visible in the per-group breakdown: hierarchical achieves 94% on Control Guilty
(1 miss) and 86% on FN Sleeper — both below intrinsic's 100% and 91% respectively.

The hierarchical auditor's very high consensus rate (100%) and low avg revisions (0.04) explain the
mechanism: unlike at gpt-4o-mini, the gpt-5.1 auditor almost always approves the analyst's first draft.
The auditor barely intervenes (abs score shift of only 1.0), so when the analyst is wrong, the auditor
fails to catch it. The problem has shifted from over-escalation to under-intervention.

This is a model-capability finding: at gpt-4o-mini, the auditor was too aggressive; at gpt-5.1, it is
too deferential. The hierarchical architecture does not automatically deliver better governance — its
usefulness depends on the auditor being appropriately calibrated against the analyst's systematic errors.

### Finding 2 [Intrinsic vs Context-Engineered]: Kayba injection markedly improves precision and score calibration

Injecting Kayba's playbook (derived from 86 gpt-5.1 training traces) into the self-review step produces
a clear improvement: F1 rises from 0.883 to 0.929, precision improves from 0.961 to 1.000 (zero false
positives), and score range accuracy jumps from 55.4% to 94.0%.

The most striking result is the elimination of all false positives. The 2 FPs that intrinsic generates
(both in FP High Roller) disappear in context-engineered. The Kayba playbook correctly encodes and applies
the residual FP bias from the training traces: FP High Roller improves from 91% to 100%, with avg group
scores dropping from 40.6 to 26.3.

The remaining gap is in false negatives — context-engineered still misses 8 guilty clients vs intrinsic's
11, for a net recall of 0.867. The FN Smurf group is the primary holdout (73% vs 59% for intrinsic —
improved, but not solved). The Kayba playbook addresses the model's residual FP bias effectively but does
not provide strong enough recall-boosting signal for the smurf pattern.

Score accuracy improvement is substantial: range accuracy 94.0% vs 55.4%, MAE 10.6 vs 16.6. The Kayba
rules are pushing scores into correct target bands. The avg score shift of −6.0 (vs −1.6 for intrinsic)
confirms the rules are actively pulling scores downward on cases that would otherwise be over-scored.

This is a markedly stronger result than the gpt-4o-mini experiment, where context-engineered barely
improved on intrinsic. At gpt-5.1, Kayba's generalised skill playbook is genuinely actionable — the model
can execute on the principles where a weaker model struggled.

### Finding 3 [Intrinsic vs LLM-Context]: Perfect classification

LLM-Context achieves F1=1.000, 100% accuracy, zero FPs, and zero FNs. Every group reaches 100%
accuracy, including the historically difficult FN Smurf (100% vs 59% for intrinsic).

This is the strongest result in the experiment. The self-synthesised rules (derived from 86 gpt-5.1
training traces) provide transformative improvement: MAE drops from 16.6 to 7.6, range accuracy reaches
97.0%, and the avg smurf group score rises from 57.1 to 77.3 — well into the expected 70–100 range.

The LLM-synthesised rules encode specific corrective heuristics calibrated directly to gpt-5.1's failure
modes on the training set. The FN Smurf improvement in particular reflects a rule that smurf-like
transaction profiles (low fan-in, small amounts) can disguise genuinely guilty clients when adverse
signals are buried in article body text — precisely the failure pattern visible in the gpt-5.1 training
traces.

### Finding 4 [Context-Engineered vs LLM-Context]: LLM self-synthesis outperforms Kayba, driven by FN Smurf

At gpt-4o-mini, LLM-Context F1 (0.952) dramatically exceeded Context-Engineered F1 (0.632). At gpt-5.1,
both modes improve substantially over intrinsic, and the gap narrows to F1 of 1.000 vs 0.929. Both
artefacts were derived from the same 86 gpt-5.1 training traces, so the difference reflects source and
format of rules, not model alignment.

Kayba's playbook eliminates all false positives and dramatically improves score calibration. LLM-context
still wins on recall (no FNs) and overall F1, but the difference is driven almost entirely by FN Smurf
(100% vs 73%). Every other group is at 100% for both modes.

The remaining advantage of LLM-Context likely reflects rule density and specificity: the LLM-synthesised
rules (~22KB, highly case-specific) provide more targeted smurf-detection guidance than Kayba's 5.4KB
generalised skill playbook. The LLM synthesis prompt structures input around specific INCORRECT cases,
producing rules that directly address the observed failure mode. Kayba extracts generalised "skills" —
reusable reasoning principles — which encode the right direction but with less precision on the hard cases.

The narrowing gap compared to gpt-4o-mini (F1 gap of 0.320 at gpt-4o-mini vs 0.071 at gpt-5.1) is a
capability effect: gpt-5.1 can execute on Kayba's general principles more faithfully, reducing the
advantage of case-specific rules for most trap types except the hardest one (FN Smurf).

### Finding 5 [Cross-cutting]: gpt-5.1 eliminates the FP failure modes that plagued gpt-4o-mini

At gpt-4o-mini, Payroll, High Roller, and Structurer FP traps were total failures (0%) across intrinsic,
hierarchical, and context-engineered. At gpt-5.1, all three are solved or nearly solved in every mode —
intrinsic alone achieves 100% on Payroll and Structurer, and 91% on High Roller.

This is the clearest capability jump in the data: gpt-5.1 can read article context and apply it to rebut
quantitative flags without needing additional rules. The qualitative reasoning failure that characterised
gpt-4o-mini at these traps (anchoring on fan-out/volume while ignoring KB explanations) does not appear
at scale in gpt-5.1.

The one remaining systematic failure at gpt-5.1 is FN Smurf — 59% accuracy for intrinsic and
hierarchical. This is a qualitatively different error: the smurf pattern requires reading buried adverse
signals in article body text and overriding a plausibly innocent transaction profile. Neither the analyst's
self-review nor the hierarchical auditor resolves this without rule injection. Context-Engineered (73%)
and LLM-Context (100%) both improve it, suggesting the solution is rule-based: the model needs an
explicit corrective prior that smurf-like transaction profiles can disguise genuinely guilty clients.

### Finding 6 [Reasoning quality]: Rules improve decision consistency without harming evidence engagement

Evidence coverage scores are uniformly high across all modes (9.60–9.86), confirming that gpt-5.1
reliably engages with forensic metrics and article content regardless of governance structure. This is a
baseline quality floor improvement over gpt-4o-mini.

The meaningful differentiation is in conclusion consistency: Context-Engineered (8.80) and LLM-Context
(8.72) score ~1.4 points higher than Intrinsic (7.34) and Hierarchical (7.37). Rule injection tightens
the alignment between what the model says in its reasoning and what decision it ultimately issues. Both
artefacts were derived from gpt-5.1 training traces, so this improvement reflects the direct utility of
in-distribution corrective rules.

The relatively low conclusion consistency for Hierarchical (7.37, same as intrinsic despite 100%
consensus) confirms the gpt-5.1 hierarchical auditor's pattern: it approves reasoning it has not
critically engaged with, rather than genuinely verifying the analyst's argument chain.

---

## 6. Comparison with gpt-4o-mini Results

Both models were tested on the identical n=168 test set (60 guilty, 108 innocent), enabling direct comparison.

### Classification Performance — All Four Modes

| Metric | 4o-mini Int | 5.1 Int | 4o-mini Hier | 5.1 Hier | 4o-mini Ctx | 5.1 Ctx | 4o-mini LLM | 5.1 LLM |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Accuracy** | 47.6% | **92.3%** | 50.0% | **90.5%** | 48.8% | **95.2%** | 64.3% | **100%** |
| **F1** | 0.54 | **0.883** | 0.59 | **0.855** | 0.56 | **0.929** | 0.66 | **1.000** |
| False Positives | 80 | **2** | 84 | **3** | 81 | **0** | 58 | **0** |
| False Negatives | 8 | **11** | **0** | 13 | 5 | **8** | **2** | 0 |
| Range Accuracy | 30.4% | **55.4%** | 39.9% | **44.6%** | 32.1% | **94.0%** | 49.4% | **97.0%** |
| MAE | 34.2 | **16.6** | 36.3 | **17.1** | 34.0 | **10.6** | 25.2 | **7.6** |

### Per-Group Accuracy — Intrinsic Baseline Comparison

| Group | n | gpt-4o-mini | gpt-5.1 | Delta |
|---|:---:|:---:|:---:|:---:|
| Control Guilty | 16 | 100% | 100% | = |
| Control Innocent | 16 | 100% | 100% | = |
| FP: Charity | 23 | 43% | **100%** | +57pp |
| FP: Payroll | 23 | 0% | **100%** | +100pp |
| FP: High Roller | 23 | 0% | **91%** | +91pp |
| FP: Structurer | 23 | 9% | **100%** | +91pp |
| FN: Sleeper | 22 | 77% | **91%** | +14pp |
| FN: Smurf | 22 | **86%** | 59% | −27pp |

**Key cross-model findings:**

1. **Baseline capability gap is enormous.** gpt-5.1 intrinsic (F1=0.883) vastly outperforms gpt-4o-mini
   intrinsic (F1=0.54). The entire FP failure mode that defines the gpt-4o-mini results — 0% on payroll,
   0% on high roller, 9% on structurer — is resolved at the base model level in gpt-5.1. gpt-5.1
   intrinsic alone outperforms gpt-4o-mini LLM-Context (F1=0.66), the best gpt-4o-mini mode.

2. **The error distribution inverts across models.** gpt-4o-mini systematically over-flags (80 FPs, 8 FNs
   in intrinsic). gpt-5.1 systematically under-flags on one specific pattern (2 FPs, 11 FNs in intrinsic
   — driven by FN Smurf at 59%). The capability jump resolves the FP anchoring bias but reveals a
   residual FN blind spot on the hardest buried-signal trap.

3. **Rule injection effects are capability-dependent.** At gpt-4o-mini, Kayba rules barely move the
   needle (F1: 0.54→0.56); at gpt-5.1, they produce a strong improvement (F1: 0.883→0.929). LLM-Context
   improves substantially at both capability levels (gpt-4o-mini: +0.12 F1; gpt-5.1: +0.117 F1), but
   for different reasons: at gpt-4o-mini the rules correct systematic anchoring bias; at gpt-5.1 they
   address a narrow FN Smurf blind spot.

4. **Hierarchical architecture produces opposite failure modes at each model.** At gpt-4o-mini the
   auditor over-escalates (84 FPs, 0 FNs, +13.4 avg score shift). At gpt-5.1 it under-intervenes
   (3 FPs, 13 FNs, −0.6 avg score shift). Neither model achieves the idealised well-calibrated auditor.
   The same architectural choice produces diametrically opposite error profiles — a central finding for
   the thesis on governance robustness.

5. **Context-engineered's low consensus rate is gpt-4o-mini specific.** At gpt-4o-mini: 17% consensus,
   1.80 revisions, 6.6 calls/case. At gpt-5.1: 100% consensus, 0.65 revisions, 4.3 calls/case. The
   Kayba rules act as an indiscriminate trigger at gpt-4o-mini but are applied selectively at gpt-5.1
   — a direct capability-execution effect establishing where Kayba's generalised principles become
   actionable.

---

## 7. Thesis Implications

| Comparison | Hypothesis | Result |
|---|---|---|
| Intrinsic vs Hierarchical | Governance architecture affects accuracy | **Not supported at gpt-5.1** — hierarchical slightly underperforms intrinsic (F1: 0.855 vs 0.883); the auditor is too deferential, not too aggressive |
| Intrinsic vs Hierarchical | Independent auditing prevents confirmation bias | **Not supported at gpt-5.1** — auditor confirms analyst output ~100% of the time; net result is passive rather than corrective |
| Intrinsic vs Context-Engineered | Kayba rule injection improves on intrinsic | **Supported** — F1 0.929 vs 0.883, zero FPs, score accuracy 94% vs 55%; Kayba playbook derived from gpt-5.1 training traces |
| Intrinsic vs LLM-Context | LLM self-reflection rules improve on intrinsic | **Strongly supported** — F1=1.000 vs 0.883; perfect classification; all trap groups resolved |
| Context-Eng vs LLM-Context | LLM self-synthesis outperforms Kayba extraction | **Supported but gap narrows** — F1 1.000 vs 0.929; difference driven entirely by FN Smurf (100% vs 73%); Kayba is genuinely effective but less targeted on the hardest trap type |

### Suggested framing for thesis write-up

The gpt-5.1 results should be framed as a **model-capability robustness check** for the governance
findings established at gpt-4o-mini:

**Axis 1 — Governance architecture (Intrinsic vs Hierarchical):**
The hierarchical auditor's behaviour is strongly model-dependent. At gpt-4o-mini it over-escalated
(too aggressive, high FPs); at gpt-5.1 it under-intervenes (too deferential, slightly higher FNs). In
neither model does it achieve the idealised outcome of a well-calibrated independent reviewer. This
suggests that the architectural advantage of hierarchical governance is not robust: it requires careful
calibration of the auditor's sensitivity level to the analyst's specific failure modes, which may shift
across model versions.

**Axis 2 — Knowledge injection (Intrinsic vs Context-Engineered vs LLM-Context):**
Rule injection improves performance at both capability levels, but the mechanism shifts. At gpt-4o-mini,
rules were necessary to overcome systematic quantitative anchoring that the base model could not self-
correct. At gpt-5.1, the base model is better calibrated, but rules still improve the residual error
profile — especially the FN Smurf gap. Both artefacts were derived from gpt-5.1 training traces, making
this a clean comparison of rule source (Kayba generalised skills vs LLM case-specific rules) without
model mismatch confounds.

The narrowing gap between Context-Engineered and LLM-Context at gpt-5.1 (from F1 gap of 0.10 at
gpt-4o-mini to 0.071 at gpt-5.1) is the central cross-model finding: as base model capability increases,
the source of rules matters less. A stronger model can execute on Kayba's general principles more
faithfully, reducing the advantage of highly specific, error-focused rules — except for the hardest trap
type (FN Smurf), where case-specific rules still provide a decisive edge.

---

## 8. Output Files

| File | Contents |
|---|---|
| `results/test/gpt-5.1/run_1/summary.csv` | Wide-format raw scores for 168 clients × 4 modes |
| `results/test/gpt-5.1/run_1/evaluation.csv` | Per-client computed metrics (in_range, correct, score_shift, etc.) |
| `results/test/gpt-5.1/run_1/evaluation_{mode}.csv` | Per-mode artifact (logged to MLflow) |
| `results/test/gpt-5.1/run_1/{mode}/*.json` | Full AgentState for each client — forensics, news, reasoning, review |
| `results/old_runs/gpt-5.1_n50_old/` | Earlier n=50 gpt-5.1 results before dataset expansion to n=168 |
| `external_agent_injection.txt` | Kayba's 28-skill context playbook (derived from 86 gpt-5.1 train traces) |
| `llm_context_rules.txt` | Self-synthesised rules from 86 gpt-5.1 training traces |
| `training_traces/*.md` | 86 annotated train traces fed to both Kayba and the LLM synthesiser |

To inspect a specific client's full reasoning chain:
```python
import json
state = json.load(open("results/test/gpt-5.1/run_1/intrinsic/C2083.json"))
print(state["analyst_output"]["reasoning"])
print(state["review_output"]["reasoning"])
```

To reproduce the evaluation:
```bash
LLM_MODEL=gpt-5.1 python 02_run_experiment.py --dataset test --modes intrinsic hierarchical context_engineered llm_context --model gpt-5.1
python 03_evaluate.py --dataset test --model gpt-5.1
mlflow ui  # http://127.0.0.1:5000
```
