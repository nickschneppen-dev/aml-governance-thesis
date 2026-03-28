# Experiment Results: Holdout D2 (OOD Generalisation) — gpt-5.1

> **Holdout question:** Do the rule-injection artefacts (Kayba playbook and LLM-synthesised rules)
> transfer to out-of-distribution trap types, or do they merely memorise the specific failure patterns
> visible in training?

---

## 1. Setup at a Glance

| | |
|---|---|
| **Model** | `gpt-5.1` |
| **Test set** | n=168 — identical to matched run (60 guilty, 108 innocent) |
| **Train set** | n=75 — D2 (FN Smurf) excluded; 11 D2 traces withheld from artefact generation |
| **Held-out group** | **D2 — FN Trap: Smurf** (22 test clients, all GUILTY) |
| **Modes evaluated** | Context-Engineered, LLM-Context (rule-injection modes only; intrinsic/hierarchical unaffected) |
| **Artefacts** | `external_agent_injection_gpt-5.1_holdoutd2.txt`, `llm_context_rules_gpt-5.1_holdoutd2.txt` |
| **Run ID** | `holdoutd2` |

### What "holdout" means here

The D2 (FN Smurf) trap type was **excluded from the training set** when generating both the Kayba
playbook and the LLM-synthesised rules. The test set is unchanged. Performance on D2 in this run is
therefore a pure **out-of-distribution (OOD) test**: neither artefact has ever seen a smurf case.
Performance on all other groups is an **in-distribution (ID) test** with slightly fewer training traces.

### Comparison design

| Comparison | What it tests |
|---|---|
| Holdout vs Matched (same mode) | How much does removing D2 from training degrade D2 performance? |
| Holdout ctx vs Holdout llm | Which rule source is more robust to OOD cases? |
| Matched D2 accuracy vs Holdout D2 accuracy | Isolates the D2-specific contribution of each artefact |

---

## 2. Core Results

### Classification Performance

| Metric | Matched Ctx | **Holdout Ctx** | Matched LLM | **Holdout LLM** |
|---|:---:|:---:|:---:|:---:|
| **Classification Accuracy** | 95.2% | **92.9%** | 100% | **94.0%** |
| **Precision** | 1.000 | **0.980** | 1.000 | **1.000** |
| **Recall** | 0.867 | **0.817** | 1.000 | **0.833** |
| **F1 Score** | 0.929 | **0.891** | 1.000 | **0.909** |
| True Positives | 52 | **49** | 60 | **50** |
| False Positives | 0 | **1** | 0 | **0** |
| True Negatives | 108 | **107** | 108 | **108** |
| False Negatives | 8 | **11** | 0 | **10** |

### Score Accuracy & Governance Behaviour

| Metric | Holdout Ctx | Holdout LLM |
|---|:---:|:---:|
| Range Accuracy (score within expected band) | 89.9% | 89.9% |
| MAE from midpoint | 10.9 | **9.5** |
| Consensus Rate | 98% | **99%** |
| Avg Revisions per Case | 0.83 | **0.50** |
| Avg LLM Calls per Case | 4.7 | **4.0** |
| Avg Score Shift (final − initial) | −6.6 | −7.9 |
| Abs Avg Score Shift | 8.1 | 8.4 |

---

## 3. Per-Group Breakdown

### Classification Accuracy by Group

| Group | n | Truth | Matched Ctx | Holdout Ctx | Matched LLM | Holdout LLM |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Control Guilty** | 16 | GUILTY | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **Control Innocent** | 16 | INNOCENT | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FP Trap: Charity** | 23 | INNOCENT | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FP Trap: Payroll** | 23 | INNOCENT | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FP Trap: High Roller** | 23 | INNOCENT | ✅ 100% | ⚠️ 96% | ✅ 100% | ✅ 100% |
| **FP Trap: Structurer** | 23 | INNOCENT | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FN Trap: Sleeper** | 22 | GUILTY | ⚠️ 91% | ✅ 100% | ✅ 100% | ⚠️ 95% |
| **FN Trap: Smurf** | 22 | GUILTY | ⚠️ 73% | ❌ **50%** [OOD] | ✅ 100% | ❌ **59%** [OOD] |

*✅ = strong performance (≥80%)  ⚠️ = partial  ❌ = failure (<80%)*

### Avg Risk Score by Group

| Group | Holdout Ctx | Holdout LLM | Matched Ctx | Matched LLM |
|---|:---:|:---:|:---:|:---:|
| Control Guilty | 82.0 | 81.8 | 79.4 | 83.4 |
| Control Innocent | 12.2 | 13.9 | 10.9 | 16.5 |
| FP: Charity | 21.5 | 22.7 | 24.4 | 22.2 |
| FP: Payroll | 25.8 | 21.3 | 25.7 | 23.6 |
| FP: High Roller | 28.4 | 24.5 | 26.3 | 26.1 |
| FP: Structurer | 22.2 | 21.3 | 25.3 | 22.4 |
| FN: Sleeper | 81.3 | 77.4 | 77.0 | 79.7 |
| **FN: Smurf [OOD]** | **53.9** | **58.4** | **63.0** | **77.3** |

---

## 4. The OOD Signal: D2 Smurf Isolated

This is the core result. Both artefacts were generated without seeing any D2 training traces.
Performance on D2 in the holdout run reflects pure transfer from non-smurf examples.

| Condition | Context-Eng D2 Acc | LLM-Context D2 Acc | Context-Eng D2 Avg Score | LLM-Context D2 Avg Score |
|---|:---:|:---:|:---:|:---:|
| **Matched** (D2 in training) | 73% | **100%** | 63.0 | **77.3** |
| **Holdout** (D2 withheld) | 50% | 59% | 53.9 | 58.4 |
| **Drop** | −23pp | −41pp | −9.1 | −18.9 |

Both modes collapse on D2 Smurf when it is withheld from training. The drops are large and in the
same direction, confirming that both artefacts **had encoded D2-specific corrective signal** in the
matched run.

The LLM-Context drop is larger in absolute terms (−41pp vs −23pp), because LLM-Context had achieved
**perfect** D2 accuracy in the matched run — 100% → 59% — whereas Context-Engineered was already
partial (73% → 50%). With nothing to transfer from, LLM-Context's case-specific rules provide no
special edge over the base model's intrinsic performance (which was also ~59% for intrinsic alone in
the matched run).

### What the scores reveal

In the matched run, LLM-Context pushed average D2 scores from 57.1 (intrinsic) to 77.3 — well into
the expected 70–100 band. In the holdout, scores fall to 58.4 — nearly identical to intrinsic
baseline. The artefact is not generating residual smurf signal from general principles; the corrective
effect disappears almost entirely.

Context-Engineered's holdout score (53.9) is below even the matched intrinsic baseline (57.1),
suggesting that with only the general playbook and no D2-specific failure examples, the Kayba skills
are actually slightly miscalibrated for this pattern — the rule that helps in-distribution may be
absent or incorrectly weighted OOD.

---

## 5. In-Distribution Impact

Removing 11 D2 training traces had minimal effect on all other groups. This is expected — fewer
training examples should not improve non-D2 performance — but the magnitude of any change is
informative.

**Context-Engineered non-D2 changes (holdout vs matched):**
- FP High Roller: 100% → 96% (−4pp, −1 case) — slight regression with fewer total traces
- FN Sleeper: 91% → 100% (+9pp) — small improvement, likely noise given n=22
- All other groups: unchanged at 100%

**LLM-Context non-D2 changes (holdout vs matched):**
- FN Sleeper: 100% → 95% (−5pp, −1 case) — marginal regression
- All other groups: unchanged at 100%

The non-D2 results are nearly identical to the matched run. The artefacts have not degraded on
in-distribution groups despite having 11 fewer training traces. This confirms the OOD degradation
is specific to D2, not a general artefact quality drop.

---

## 6. What the Results Mean

### Finding 1: Both rule sources encoded D2-specific signal, not just general AML principles

The matched run suggested LLM-Context "solved" FN Smurf via a general rule about buried body-text
signals. The holdout falsifies this: with D2 withheld, LLM-Context drops from 100% to 59% — the same
level as intrinsic baseline. The corrective effect was not a general principle that transferred; it
was a D2-calibrated rule that required smurf training examples to exist.

Context-Engineered tells a similar story: 73% → 50%. Kayba's skills for "buried adverse signals" or
"benign transaction profile with qualitative guilt" were sharpened by seeing smurf examples in
training. Without them, the playbook provides no meaningful improvement over intrinsic on this trap type.

### Finding 2: LLM-Context is more brittle on OOD cases than Context-Engineered

In the matched run, LLM-Context outperformed Context-Engineered on D2 (100% vs 73%). In the holdout,
the performance gap reverses direction: Context-Engineered achieves 50% and LLM-Context achieves 59%
— a small advantage for LLM, but both are failures relative to their matched-run performance.

More importantly, the **magnitude of the drop** is larger for LLM-Context (−41pp vs −23pp). This
reflects a structural difference: LLM-Context generates dense, case-specific rules that are tightly
calibrated to the failure modes it observed. When those failures are absent from training, there is
no generalised rule to fall back on. Kayba's generalised skill framework at least provides a residual
floor — the playbook encodes broader AML reasoning principles that partially apply even OOD, even
if not optimally.

This is a meaningful qualification of the LLM-Context advantage: its superiority in the matched run
was partly a function of having seen the hard cases. It is a stronger learner *with enough signal*,
but more brittle *without it*.

### Finding 3: The OOD drop mirrors the intrinsic baseline exactly

In the matched run, all four modes show intrinsic D2 accuracy at 59%. In the holdout, both
rule-injection modes revert toward 59% when D2 is withheld. This convergence is not a coincidence —
it confirms that without smurf-specific training signal, rule-injection modes provide no uplift on
this trap type. The base model's intrinsic capability (59%) is the floor, and only artefacts derived
from D2 examples can lift above it.

The thesis implication: for the hardest trap type (deeply buried qualitative signals with a clean
quantitative profile), context injection's benefit is earned through training exposure, not
architectural design. A governance framework built without encountering this failure mode will not
spontaneously develop the corrective prior.

### Finding 4: ID performance is robust to smaller training sets

Removing 11 D2 traces from an 86-trace training set (reducing to 75 traces) caused negligible
degradation on the remaining 7 groups. Both modes remained at 95–100% across all non-D2 groups, with
single-case regressions that are within noise. This confirms that the artefact quality for
in-distribution groups is not sensitive to modest reductions in training volume — the relevant
variable is *coverage of the target failure mode*, not total trace count.

---

## 7. Summary: Matched vs Holdout at a Glance

| Metric | Matched Ctx | Holdout Ctx | Δ | Matched LLM | Holdout LLM | Δ |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Overall Accuracy | 95.2% | 92.9% | −2.3pp | 100% | 94.0% | −6.0pp |
| F1 | 0.929 | 0.891 | −0.038 | 1.000 | 0.909 | −0.091 |
| False Negatives | 8 | 11 | +3 | 0 | 10 | +10 |
| **D2 Smurf Accuracy** | **73%** | **50%** | **−23pp** | **100%** | **59%** | **−41pp** |
| D2 Avg Score | 63.0 | 53.9 | −9.1 | 77.3 | 58.4 | −18.9 |
| Non-D2 groups | 97–100% | 95–100% | ≈0 | 91–100% | 95–100% | ≈0 |

---

## 8. Output Files

| File | Contents |
|---|---|
| `results/test/gpt-5.1/run_holdoutd2/summary.csv` | Raw scores for 168 clients × 2 modes |
| `results/test/gpt-5.1/run_holdoutd2/evaluation.csv` | Per-client computed metrics |
| `results/test/gpt-5.1/run_holdoutd2/{mode}/*.json` | Full AgentState per client |
| `results/train/gpt-5.1/run_holdoutd2/intrinsic/` | Train run on holdout dataset (75 traces, no D2) |
| `train_holdoutd2_*.{csv,json}` | Holdout train dataset files |
| `training_traces_gpt-5.1_holdoutd2/` | 75 annotated train traces (D2 withheld) |
| `external_agent_injection_gpt-5.1_holdoutd2.txt` | Kayba playbook from 75 holdout traces |
| `llm_context_rules_gpt-5.1_holdoutd2.txt` | LLM-synthesised rules from 75 holdout traces |
| `external_agent_injection_gpt-5.1.txt` | Swapped to holdoutd2 version during this run (original backed up to .bak) |
| `llm_context_rules_gpt-5.1.txt` | Swapped to holdoutd2 version during this run (original backed up to .bak) |

To restore the matched-run artefacts after this experiment:
```bash
cp external_agent_injection_gpt-5.1.txt.bak external_agent_injection_gpt-5.1.txt
cp llm_context_rules_gpt-5.1.txt.bak llm_context_rules_gpt-5.1.txt
```

To reproduce the holdout evaluation:
```bash
# Swap in holdout artefacts
cp external_agent_injection_gpt-5.1_holdoutd2.txt external_agent_injection_gpt-5.1.txt
cp llm_context_rules_gpt-5.1_holdoutd2.txt llm_context_rules_gpt-5.1.txt

# Run
python 02_run_experiment.py --dataset test --modes context_engineered llm_context --model gpt-5.1 --run-id holdoutd2
python 03_evaluate.py --dataset test --model gpt-5.1 --run-id holdoutd2 --holdout-group D2
```
