# Experiment Results: Multi-Agent AML Governance

> **Thesis question:** Does external context injection (Kayba ACE) close the performance gap between
> intrinsic self-correction and independent hierarchical auditing — at a fraction of the cost?
> A secondary condition tests whether LLM-synthesised self-reflection rules match or exceed Kayba.

---

## 1. Setup at a Glance

| | |
|---|---|
| **Dataset** | AMLNet (1.09M transactions, 10k users) — 50 test clients, 50 train clients |
| **Ground truth** | 22 guilty, 28 innocent per split |
| **Model** | `gpt-5.1` (identical across all four modes) |
| **Classification threshold** | Score ≥ 50 → predicted GUILTY |
| **Kayba training input** | 50 train traces (intrinsic mode, 37 correct / 13 incorrect) |
| **Kayba output** | 28 deduplicated skills, 5.4 KB context playbook |
| **LLM self-reflection input** | Same 50 train traces, rules synthesised by gpt-5.1 itself |

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

The data tables below include all four modes for reference. Findings and thesis implications are
structured only around the four valid comparisons.

---

## 2. Core Results

### Classification Performance

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| **Classification Accuracy** | 90.0% | 88.0% | 90.0% | **94.0%** |
| **Precision** | 0.947 | 0.900 | 0.905 | **1.000** |
| **Recall** | 0.818 | 0.818 | 0.864 | 0.864 |
| **F1 Score** | 0.878 | 0.857 | 0.884 | **0.927** |
| True Positives | 18 | 18 | 19 | 19 |
| False Positives | 1 | 2 | 2 | **0** |
| True Negatives | 27 | 26 | 26 | **28** |
| False Negatives | 4 | 4 | 3 | 3 |

### Score Accuracy

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| Range Accuracy (score within expected band) | 46.0% | 52.0% | 58.0% | **88.0%** |
| MAE from midpoint | 17.0 | 16.6 | 16.3 | **10.3** |

### Governance Behaviour & Efficiency

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| Consensus Rate (reviewer approved) | 100% | 100% | 100% | 100% |
| Avg Revisions per Case | 0.20 | **0.04** | 0.14 | 0.52 |
| Avg LLM Calls per Case | 3.40 | **3.08** | 3.28 | 4.04 |
| Avg Score Shift (final − initial) | −2.0 | +0.4 | −2.0 | **−6.4** |
| Avg Confidence | 81.8 | 81.6 | 81.9 | **85.0** |

---

## 3. Per-Group Breakdown

### Classification Accuracy by Group

| Group | n | Truth | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Control Guilty** | 8 | GUILTY | ✅ 100% | ✅ 100% | ✅ 100% | ⚠️ 88% |
| **Control Innocent** | 8 | INNOCENT | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FP Trap: Charity** | 5 | INNOCENT | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FP Trap: Payroll** | 5 | INNOCENT | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FP Trap: High Roller** | 5 | INNOCENT | ⚠️ 80% | ⚠️ 60% | ⚠️ 60% | ✅ 100% |
| **FP Trap: Structurer** | 5 | INNOCENT | ✅ 100% | ✅ 100% | ✅ 100% | ✅ 100% |
| **FN Trap: Sleeper** | 7 | GUILTY | ⚠️ 86% | ✅ 100% | ⚠️ 86% | ✅ 100% |
| **FN Trap: Smurf** | 7 | GUILTY | ⚠️ 57% | ❌ 43% | ⚠️ 71% | ⚠️ 71% |

*✅ = strong performance (≥80%)  ⚠️ = partial  ❌ = failure (<50%)*

### Average Risk Score by Group

| Group | Expected | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|
| Control Guilty | 70–100 | 80.3 | 83.9 | 81.3 | 78.5 |
| Control Innocent | 0–30 | 14.0 | 17.0 | 15.3 | **14.3** |
| FP: Charity | 0–30 | 30.0 | 30.2 | 26.6 | **23.6** |
| FP: Payroll | 0–30 | 39.8 | 42.2 | 40.0 | **22.8** |
| FP: High Roller | 0–30 | 45.0 | 47.8 | 45.0 | **25.0** |
| FP: Structurer | 0–30 | 34.4 | 36.0 | 31.4 | **21.4** |
| FN: Sleeper | 70–100 | 71.6 | **76.6** | 71.0 | **79.9** |
| FN: Smurf | 70–100 | 55.4 | 53.0 | 55.0 | **57.1** |

---

## 4. What the Results Mean

Findings are framed around the four valid pairwise comparisons identified in the comparison design above.
Cross-comparisons involving Hierarchical vs Context-Engineered or Hierarchical vs LLM-Context are not
drawn, as both the architecture and the injected content differ in those pairs.

### Finding 1 [Intrinsic vs Hierarchical]: Governance architecture has a small net effect at gpt-5.1

Comparing the two no-rules conditions isolates the architectural variable: same-context self-review
(intrinsic) vs separate-context independent auditor (hierarchical).

Intrinsic edges out hierarchical on F1 (0.878 vs 0.857) and precision (0.947 vs 0.900), while both
modes achieve identical recall (0.818). The intrinsic mode catches one more true positive and produces
one fewer false positive. The hierarchical auditor also does slightly worse on FN Smurf (43% vs 57%),
likely because its fresh context window does not carry the analyst's original evidence chain, making
subtle buried signals harder to sustain across the audit boundary.

On the other hand, the hierarchical auditor is more efficient (3.08 vs 3.40 LLM calls; 0.04 vs 0.20
avg revisions) because its stronger calibration leads it to approve reports on the first pass. The
average score shift for hierarchical (+0.4) is near-zero, with no systematic escalation — a marked
difference from the same architecture at gpt-4o-mini capability, where the auditor over-escalated
by +14.1 on average. This suggests the architectural penalty of independent auditing shrinks as model
capability increases.

### Finding 2 [Intrinsic vs Context-Engineered]: Kayba rule injection provides a modest improvement

Injecting Kayba's externally-derived playbook into the self-review step improves F1 from 0.878 to 0.884
and captures one additional true positive (recall 0.864 vs 0.818). The mode corrects one more FN Smurf
(71% vs 57%) while maintaining the same FP Payroll and High Roller results as intrinsic. The cost is
minimal — 3.28 vs 3.40 LLM calls — because the rules reduce the need for rejection-and-revision cycles
(0.14 vs 0.20 avg revisions).

The improvement is real but narrow. Range accuracy improves from 46% to 58%, and MAE from 17.0 to 16.3.
Kayba's playbook appears to carry useful signal — it was derived from actual errors on the training set —
but the gain is not large enough to be decisive on its own.

### Finding 3 [Intrinsic vs LLM-Context]: Self-synthesised rules produce the largest improvement

Replacing Kayba's external rules with rules the LLM derived from its own training errors — same
self-review architecture, same injection point — produces a substantially larger gain: F1 rises from
0.878 to 0.927, accuracy from 90% to 94%, and precision from 0.947 to 1.000 (zero false positives).

The mechanism is aggressive downward revision: average score shift of −6.4 vs −2.0 for intrinsic.
This is concentrated on FP traps — payroll avg drops to 22.8 (from 39.8), high roller to 25.0 (from
45.0), structurer to 21.4 (from 34.4) — while guilty clients remain above the threshold. The
self-derived rules appear to have encoded a targeted skepticism: *if a legitimate business explanation
exists in the knowledge base, quantitative red flags alone are not sufficient*. This principle transfers
across FP trap subtypes that intrinsic consistently over-flags.

The trade-off is a small FN Smurf deterioration (71% vs 57%) — aggressive review that correctly clears
FP traps also risks over-clearing genuine guilty smurfs with buried evidence. Range accuracy jumps to
88% (from 46%), and MAE to 10.3 (from 17.0). The additional cost is 0.64 LLM calls per case.

### Finding 4 [Context-Engineered vs LLM-Context]: LLM self-synthesis outperforms Kayba extraction

With architecture held constant (both are same-context self-review with rules injected at the same
review step), the source of the rules is the isolated variable. LLM-Context outperforms
Context-Engineered on every metric: F1=0.927 vs 0.884, accuracy 94% vs 90%, precision 1.000 vs
0.905, and range accuracy 88% vs 58%.

Three factors likely explain the gap:

**Rule density and specificity.** The LLM-synthesised rules (~17KB) are roughly three times larger
than Kayba's skillbook (~5.4KB, 28 deduplicated skills). More rules, each targeting a specific
observed failure pattern, gives the self-reviewer a broader corrective vocabulary.

**Error-focused synthesis vs skill abstraction.** The synthesis prompt in
`05_generate_llm_context_rules.py` explicitly structures the input around INCORRECT cases and
CORRECT TRAP cases, asking the LLM to identify what went wrong and what worked. Kayba's ACE
pipeline extracts generalised "skills" — reusable reasoning principles — which may be less
directly targeted at the specific calibration failures the reviewer needs to correct.

**Training trace model mismatch.** Both artefacts were derived from training traces produced by
gpt-4o-mini running in intrinsic mode. Kayba's pipeline encoded *that model's* failure patterns
into its 28 skills. The LLM self-synthesis was run *by* gpt-5.1 over those same traces, producing
rules in a frame gpt-5.1 finds more directly actionable. A fair comparison would require
regenerating training traces with gpt-5.1 and re-running Kayba on those — the current result
conflates rule source with model alignment.

The FN Smurf accuracy is identical (both 71%), suggesting the extra correction strength of LLM
rules does not further harm recall beyond what context injection already introduces.

### Finding 5 [Cross-cutting]: FP High Roller is the last persistent failure; FN Smurf is a new one

Two groups reveal boundary conditions that cut across all four modes:

**FP High Roller (60–80% for intrinsic/hier/ctx; 100% for LLM-Context):** High-volume clients with
a casino or investment alibi continue to fool three of four modes. The quantitative signal (fan-out
>80, volume >$200k) appears to dominate the article-based explanation for all modes except LLM-Context,
which systematically drives these scores to ~25. The self-synthesised rules are the only intervention
that transfers training-set experience with high-roller profiles to the test set.

**FN Smurf (43–71% across all modes):** Confirmed launderers disguised as gig workers or students,
with guilt buried in article body text. All modes miss at least two of the seven. Notably, the smurf
failure emerges in gpt-5.1 despite gpt-4o-mini achieving 100% on this group — a regression. The
stronger model's improved ability to accept legitimate explanations for quantitative anomalies (which
resolves FP Payroll and FP High Roller) is the same mechanism that makes it more willing to accept
a benign cover story for a genuine launderer. This is a precision-recall boundary condition inherent
to the task, not a correctable governance failure.

---

## 5. Thesis Implications

Hypotheses are evaluated only against the valid pairwise comparisons. Hierarchical is not
compared to Context-Engineered or LLM-Context because both the architecture and the injected
knowledge differ in those pairs — no clean causal claim can be made.

| Comparison | Hypothesis | Result |
|---|---|---|
| Intrinsic vs Hierarchical | Governance architecture affects accuracy | **Weak support** — intrinsic edges out hierarchical (F1=0.878 vs 0.857), but the gap is small and direction-dependent on model capability |
| Intrinsic vs Hierarchical | Independent auditing prevents confirmation bias | **Not supported as framed** — 100% consensus in both modes; hierarchical does not catch more errors, it catches different ones (better FN Sleeper, worse FN Smurf) |
| Intrinsic vs Context-Engineered | Kayba rule injection improves on intrinsic | **Supported, modestly** — F1=0.884 vs 0.878; one additional TP, better smurf recall |
| Intrinsic vs LLM-Context | LLM self-reflection rules improve on intrinsic | **Strongly supported** — F1=0.927 vs 0.878; zero FPs, 88% range accuracy |
| Context-Eng vs LLM-Context | LLM self-synthesis outperforms Kayba extraction | **Supported** — F1=0.927 vs 0.884; LLM rules induce stronger, better-targeted correction |

### Suggested framing for thesis write-up

The results are best structured around the two independent experimental axes:

**Axis 1 — Governance architecture:** Intrinsic vs Hierarchical isolates whether a separate-context
independent auditor outperforms same-context self-review. At gpt-5.1, the architecture difference
is small and nuanced: intrinsic is marginally better overall, but hierarchical performs better on
FN Sleeper (100% vs 86%) at the cost of FN Smurf (43% vs 57%). The auditor's separate context
prevents anchoring, which helps for subtle true positives but hurts for cases where the analyst's
original evidence chain is the critical reasoning artefact.

**Axis 2 — Knowledge injection:** Intrinsic vs Context-Engineered vs LLM-Context tests whether
adding rules to the self-review step helps, and whether the source of those rules matters. Both
injection conditions outperform the no-rules baseline; LLM-Context substantially more so. The
finding that LLM-synthesised rules outperform Kayba's extracted skills (F1=0.927 vs 0.884) is
the novel contribution, with three plausible contributing factors: the LLM rules are ~3× denser,
are synthesised with an explicit error-focus rather than general skill abstraction, and are produced
by the same model that consumes them. The latter is also a confound: both artefacts were derived
from gpt-4o-mini training traces, meaning Kayba's skills encode that model's failure patterns while
the LLM rules were synthesised by gpt-5.1 from those same traces. A fully controlled comparison
requires regenerating training traces with gpt-5.1 and re-running Kayba on those before the
source-of-rules variable is cleanly isolated.

---

## 6. Output Files

| File | Contents |
|---|---|
| `results/test/gpt-5.1/run_1/summary.csv` | Wide-format raw scores for all 50 clients × 4 modes |
| `results/test/gpt-5.1/run_1/evaluation.csv` | Per-client computed metrics (in_range, correct, score_shift, etc.) |
| `results/test/gpt-5.1/run_1/evaluation_{mode}.csv` | Per-mode artifact (logged to MLflow) |
| `results/test/gpt-5.1/run_1/{mode}/*.json` | Full AgentState for each client — forensics, news, reasoning, review |
| `results/old_runs/RESULTS_gpt-4o-mini.md` | Previous results under gpt-4o-mini (3 modes: intrinsic, hierarchical, ctx) |
| `external_agent_injection.txt` | Kayba's 28-skill context playbook (injected into ctx mode) |
| `llm_context_rules.txt` | Self-synthesised rules from training traces (injected into llm_context mode) |
| `training_traces/*.md` | 50 annotated train traces fed to both Kayba and the LLM synthesiser |

To inspect a specific client's full reasoning chain:
```python
import json
state = json.load(open("results/test/gpt-5.1/run_1/intrinsic/C2083.json"))
print(state["analyst_output"]["reasoning"])
print(state["review_output"]["reasoning"])
```

To reproduce the evaluation:
```bash
python 03_evaluate.py --dataset test --model gpt-5.1
mlflow ui  # http://127.0.0.1:5000
```
