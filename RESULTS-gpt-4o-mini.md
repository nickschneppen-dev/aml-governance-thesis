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
| **Model** | `gpt-4o-mini` (identical across all four modes) |
| **Classification threshold** | Score ≥ 50 → predicted GUILTY |
| **Kayba training input** | 50 train traces (intrinsic mode, 37 correct / 13 incorrect) |
| **Kayba output** | 28 deduplicated skills, 5.4 KB context playbook |
| **LLM self-reflection input** | Same 50 train traces, rules synthesised by gpt-4o-mini itself |
| **Errors** | C3891 (fp_trap:high_roller) failed in ctx mode; C6250 (fp_trap:high_roller) failed in llm_context mode. Both modes evaluated on 49/50 clients; fp_trap:high_roller group has 4/5 clients in those modes. |

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

| Metric | Intrinsic | Hierarchical | Context-Eng (49) | LLM-Context (49) |
|---|:---:|:---:|:---:|:---:|
| **Classification Accuracy** | 56.0% | 60.0% | 57.1% | **95.9%** |
| **Precision** | 0.500 | 0.524 | 0.514 | **1.000** |
| **Recall** | 0.864 | 1.000 | 0.818 | 0.909 |
| **F1 Score** | 0.633 | 0.688 | 0.632 | **0.952** |
| True Positives | 19 | 22 | 18 | 20 |
| False Positives | 19 | 20 | 17 | **0** |
| True Negatives | 9 | 8 | 10 | **27** |
| False Negatives | 3 | 0 | 4 | 2 |

*Context-Eng and LLM-Context are evaluated on 49 clients due to one error each (both in fp_trap:high_roller).*

### Score Accuracy

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| Range Accuracy (score within expected band) | 42.0% | 52.0% | 33.0% | **84.0%** |
| MAE from midpoint | 30.4 | 30.9 | 31.2 | **11.3** |

### Governance Behaviour & Efficiency

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| Consensus Rate (reviewer approved) | 50% | 32% | 24% | 49% |
| Avg Revisions per Case | 1.46 | 1.64 | 1.71 | 1.47 |
| Avg LLM Calls per Case | 5.92 | 6.28 | 6.43 | 5.94 |
| Avg Score Shift (final − initial) | +3.6 | +10.9 | −1.6 | **−12.1** |

---

## 3. Per-Group Breakdown

### Classification Accuracy by Group

| Group | n | Truth | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Control Guilty** | 8 | GUILTY | ✅ 100% | ✅ 100% | ⚠️ 88% | ✅ 100% |
| **Control Innocent** | 8 | INNOCENT | ✅ 100% | ⚠️ 75% | ⚠️ 88% | ✅ 100% |
| **FP Trap: Charity** | 5 | INNOCENT | ⚠️ 20% | ⚠️ 20% | ⚠️ 60% | ✅ 100% |
| **FP Trap: Payroll** | 5 | INNOCENT | ❌ 0% | ⚠️ 20% | ❌ 0% | ✅ 100% |
| **FP Trap: High Roller** | 5 | INNOCENT | ❌ 0% | ❌ 0% | ❌ 0%† | ✅ 100%† |
| **FP Trap: Structurer** | 5 | INNOCENT | ❌ 0% | ❌ 0% | ❌ 0% | ✅ 100% |
| **FN Trap: Sleeper** | 7 | GUILTY | ⚠️ 71% | ✅ 100% | ⚠️ 71% | ✅ 100% |
| **FN Trap: Smurf** | 7 | GUILTY | ⚠️ 86% | ✅ 100% | ⚠️ 86% | ⚠️ 71% |

*✅ = strong performance (≥80%)  ⚠️ = partial  ❌ = failure (<50%)*
*† 4/5 clients evaluated in this group for ctx and llm_context (1 error each)*

### Average Risk Score by Group

| Group | Expected | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|
| Control Guilty | 70–100 | 81.0 | 83.1 | 75.0 | 75.0 |
| Control Innocent | 0–30 | 21.9 | 33.1 | 23.1 | 16.9 |
| FP: Charity | 0–30 | 57.0 | 55.0 | 43.0 | **12.0** |
| FP: Payroll | 0–30 | 72.8 | 70.0 | 73.4 | **31.0** |
| FP: High Roller | 0–30 | 74.0 | 91.0 | 76.3† | **31.3†** |
| FP: Structurer | 0–30 | 72.0 | 75.0 | 66.0 | **20.0** |
| FN: Sleeper | 70–100 | 60.7 | **73.6** | 52.1 | **85.0** |
| FN: Smurf | 70–100 | 68.6 | **80.7** | 62.1 | 65.7 |

*† 4/5 clients evaluated*

---

## 4. What the Results Mean

Findings are framed around the four valid pairwise comparisons identified in the comparison design above.
Cross-comparisons involving Hierarchical vs Context-Engineered or Hierarchical vs LLM-Context are not
drawn, as both the architecture and the injected content differ in those pairs.

### Finding 1 [Intrinsic vs Hierarchical]: Hierarchical raises recall at a large precision cost

Comparing the two no-rules conditions isolates the architectural variable: same-context self-review
(intrinsic) vs separate-context independent auditor (hierarchical).

Hierarchical achieves perfect recall (1.000 vs 0.864) — it misses zero guilty clients, including all
seven FN Sleepers (100%) and all seven FN Smurfs (100%). This represents the intended auditor behaviour:
the independent reviewer refuses to let the analyst's conservative assessment stand. However, the cost is
severe: 20 false positives vs 19 for intrinsic, for a net F1 of 0.688 vs 0.633. The improvement in recall
(eliminating all FNs) is not enough to offset the systematic over-escalation: the auditor drives the
average score upward by +10.9 points across all cases.

The over-escalation pattern is visible in the per-group scores: the hierarchical auditor pushes FP Payroll
to 70.0, FP High Roller to 91.0, and FP Structurer to 75.0 — all deep into guilty territory for clients
that are innocent. This is consistent with an auditor that interprets quantitative red flags as dispositive
rather than rebuttable, and is not constrained by the cumulative article-based context that the analyst
originally built up.

Consensus rate (32%) and efficiency (6.28 LLM calls per case) confirm the pattern: the auditor rejects
frequently, forces extensive revision cycles, and still ends at high risk scores because the analyst
ultimately does not have grounds to override the auditor's demand for escalation.

### Finding 2 [Intrinsic vs Context-Engineered]: Kayba injection provides marginal benefit on FP Charity but does not close larger gaps

Injecting Kayba's externally-derived playbook into the self-review step produces a mixed outcome at
gpt-4o-mini. F1 falls very slightly (0.632 vs 0.633) — within noise — with one fewer TP (18 vs 19) and
two fewer FPs (17 vs 19). The benefit is concentrated in FP Charity (60% vs 20%): the Kayba rules
successfully transfer some recognition that NGO-style fan-in patterns can have legitimate explanations.

However, FP Payroll (0%), FP High Roller (0%), and FP Structurer (0%) remain total failures in both
modes. The Kayba playbook does not generalise its charity-case learning to the other FP trap subtypes.
FN Sleeper accuracy is unchanged (71% in both). Context-Engineered also produces a lower consensus rate
than intrinsic (24% vs 50%) and the highest revision count (1.71 avg), indicating that the Kayba rules
are triggering additional review cycles without resolving them productively.

The average score shift is slightly negative (−1.6 vs +3.6 for intrinsic), confirming the rules do
induce some downward pressure — but not enough to push FP Payroll, High Roller, or Structurer below the
50-point classification threshold. At gpt-4o-mini capability, the Kayba playbook is too thin (5.4KB, 28
skills) to overcome the model's strong initial over-scoring on quantitative red flags.

### Finding 3 [Intrinsic vs LLM-Context]: Self-synthesised rules produce a transformative improvement

The same-architecture, same-injection-point comparison but replacing Kayba's rules with LLM-synthesised
rules produces results qualitatively different from any other mode: F1=0.952, accuracy 95.9%, and
precision 1.000 with zero false positives across 49 evaluated clients.

Every FP trap subtype is solved: charity (100%), payroll (100%), high roller (100%, 4/4 evaluated),
structurer (100%). The average score for FP Payroll falls from 72.8 to 31.0; FP High Roller from 74.0 to
31.3; FP Structurer from 72.0 to 20.0. The self-synthesised rules encode a consistent principle that
quantitative red flags alone are insufficient when a legitimate business explanation appears in the
knowledge base — and this principle transfers across all FP subtypes.

The trade-off: FN Smurf falls to 71% (vs 86% intrinsic) with two misses (C6018 score=35, C5350 score=40).
The aggressive downward reviewer that clears FP traps also over-corrects for two confirmed smurfs whose
transaction profiles have surface-level legitimacy. This is a precision-recall boundary condition: the
rules that resolve all FPs are the same rules that occasionally over-clear a subtle FN.

Average score shift of −12.1 (vs +3.6 intrinsic) quantifies the corrective force. Consensus rate (49%)
and avg revisions (1.47) are nearly identical to intrinsic, suggesting the rules lead to decisive
first-pass rejections rather than repeated inconclusive cycles.

### Finding 4 [Context-Engineered vs LLM-Context]: LLM self-synthesis dramatically outperforms Kayba extraction at gpt-4o-mini

With architecture held constant, the source of rules is the isolated variable. At gpt-4o-mini, the
difference is not narrow — it is decisive: F1=0.952 vs 0.632, accuracy 95.9% vs 57.1%, and 0 FPs vs 17.
Kayba's playbook provides marginal improvement over intrinsic; LLM-Context transforms performance.

Three factors likely explain the gap:

**Rule density and specificity.** The LLM-synthesised rules (~17KB) are roughly three times larger
than Kayba's skillbook (~5.4KB, 28 deduplicated skills). More rules, each targeting a specific
observed failure pattern, gives the self-reviewer a broader corrective vocabulary.

**Error-focused synthesis vs skill abstraction.** The synthesis prompt in
`05_generate_llm_context_rules.py` explicitly structures the input around INCORRECT cases and
CORRECT TRAP cases, asking the LLM to identify what went wrong and what worked. Kayba's ACE
pipeline extracts generalised "skills" — reusable reasoning principles — which may be less
directly targeted at the specific calibration failures the reviewer needs to correct. For
gpt-4o-mini, which systematically over-flags quantitative red flags, targeted corrective rules
matter more than generalised best practices.

**Training trace model alignment.** Both artefacts were derived from gpt-4o-mini training traces.
In this run, unlike the gpt-5.1 run, there is no model mismatch: the LLM rules were synthesised
by gpt-4o-mini itself from gpt-4o-mini traces, and the test agent is also gpt-4o-mini. The
Kayba pipeline likewise encoded gpt-4o-mini failure patterns. The absence of a mismatch confound
makes this comparison cleaner than the gpt-5.1 version — and the gap is even larger, suggesting
that rule density and synthesis strategy are the dominant factors rather than model alignment.

### Finding 5 [Cross-cutting]: LLM-Context solves all FP traps; intrinsic and ctx share a systematic quantitative bias

At gpt-4o-mini, the persistent failure across intrinsic, hierarchical, and context-engineered is
systematic over-scoring on quantitative red flags. All four FP trap subtypes sit at 0–20% accuracy
for intrinsic/ctx/hier. The model anchors heavily on fan-in, fan-out, and volume thresholds and does
not consistently allow legitimate knowledge-base explanations to overcome them.

LLM-Context is the only mode that breaks this pattern — and it does so completely. This suggests the
failure is not in the analytical capacity of gpt-4o-mini per se, but in the absence of an explicit
corrective prior. When the self-reviewer is equipped with rules synthesised directly from past
over-flagging errors, the model can and does apply them.

FN Sleeper accuracy (71% for intrinsic and ctx) reflects a secondary limitation: the model sometimes
fails to read past a benign cover profile and extract buried adverse signals from article body text. The
hierarchical auditor resolves this (100%) by not carrying the analyst's anchored framing into the review
step, but at the cost of 20 FPs elsewhere. LLM-Context also achieves 100% FN Sleeper accuracy — the
corrective rules do not trade off against FN detection except for a modest smurf effect.

---

## 5. Thesis Implications

Hypotheses are evaluated only against the valid pairwise comparisons. Hierarchical is not
compared to Context-Engineered or LLM-Context because both the architecture and the injected
knowledge differ in those pairs — no clean causal claim can be made.

| Comparison | Hypothesis | Result |
|---|---|---|
| Intrinsic vs Hierarchical | Governance architecture affects accuracy | **Partially supported** — hierarchical achieves higher F1 (0.688 vs 0.633) via perfect recall, but at the cost of 20 FPs and +10.9 avg score escalation |
| Intrinsic vs Hierarchical | Independent auditing prevents confirmation bias | **Partially supported** — the auditor overcorrects rather than anchoring, but this produces excessive false positives rather than better calibration |
| Intrinsic vs Context-Engineered | Kayba rule injection improves on intrinsic | **Weakly supported** — FP Charity improves (60% vs 20%), overall F1 unchanged; other FP traps unresolved |
| Intrinsic vs LLM-Context | LLM self-reflection rules improve on intrinsic | **Strongly supported** — F1=0.952 vs 0.633; zero FPs; all FP trap subtypes solved |
| Context-Eng vs LLM-Context | LLM self-synthesis outperforms Kayba extraction | **Strongly supported** — F1=0.952 vs 0.632; the gap is not incremental but transformative at this capability level |

### Suggested framing for thesis write-up

The results are best structured around the two independent experimental axes:

**Axis 1 — Governance architecture:** Intrinsic vs Hierarchical isolates whether a separate-context
independent auditor outperforms same-context self-review. At gpt-4o-mini, the hierarchical auditor
achieves perfect recall (zero FNs) by refusing to approve borderline cases, but this comes at the
cost of systematic over-escalation: +10.9 avg score shift and 20 false positives. The architecture
improves one failure mode (FN recall) while creating another (FP inflation). Contrast with gpt-5.1,
where the same architecture gap largely disappears — suggesting the hierarchical auditor's tendency
to over-escalate is a model-capability effect that diminishes as the base model becomes better
calibrated.

**Axis 2 — Knowledge injection:** Intrinsic vs Context-Engineered vs LLM-Context tests whether
adding rules to the self-review step helps, and whether the source of those rules matters. At
gpt-4o-mini, Kayba's playbook provides marginal and selective improvement (FP Charity only). LLM
self-synthesised rules provide a transformative improvement — the only intervention that overcomes
the model's systematic quantitative anchoring. The finding that LLM-synthesised rules dramatically
outperform Kayba's extracted skills (F1=0.952 vs 0.632) points to rule density and error-focused
synthesis as the critical factors: the model needs explicit, case-specific corrective priors, not
generalised reasoning principles. Unlike the gpt-5.1 run, there is no model mismatch confound in
this comparison — both artefacts are derived from and applied to the same gpt-4o-mini traces.

---

## 7. Hierarchical Auditor Failure Analysis

> **For subsequent experiments:** Run `python 06_analyse_auditor.py` after each full experiment and
> paste the output below. This section documents which of the two competing hypotheses best explains
> hierarchical over-escalation for that model/dataset combination.

**Hypotheses under test:**
- **H-A (Context-window isolation):** The auditor lacks the analyst's evidence chain and defaults to
  salient quantitative signals when re-evaluating from raw data. Signature: citations dominated by
  metric names (fan_in, fan_out, volume), little or no engagement with KB article content.
- **H-B (Prompt under-constraining):** The auditor's system prompt does not adequately instruct it to
  consider legitimate explanations for flags. Signature: citations acknowledge KB content but still
  treat quantitative flags as dispositive.

*This section is a template. The analysis below was run retrospectively on the n=50 gpt-4o-mini results
with 06_analyse_auditor.py as a methodology proof-of-concept. Future RESULTS files should include this
section populated from the corresponding experiment.*

### Summary (n=50, gpt-4o-mini, retrospective)

| Metric | Value |
|---|---|
| FP errors in hierarchical mode | 20 / 28 innocent clients |
| Avg score escalation (intrinsic → hierarchical) for FP errors | +13.2 points |
| Auditor citations classified QUANT | 27 / 42 (64%) |
| Auditor citations classified QUAL | 6 / 42 (14%) |

### Reasoning Stance Breakdown

| Stance | n | % | Interpretation |
|---|:---:|:---:|---|
| QUANT_DOMINANT | 11 | 55% | Auditor cites only raw flags; no KB engagement |
| MIXED | 7 | 35% | Sees KB context but treats quantitative flags as dispositive |
| QUAL_ENGAGED | 1 | 5% | Genuinely wrestles with qualitative evidence before escalating |
| DISMISSAL | 1 | 5% | Acknowledges KB explanation, rejects it as unverified |

### Per-Subtype Breakdown

| Group | n (FP errors) | Dominant stance | Interpretation |
|---|:---:|---|---|
| FP Payroll | 7/7 | QUANT_DOMINANT (5), MIXED (2) | Auditor treats fan_out=100+ as standalone finding; payroll explanation never engages |
| FP High Roller | 2/5 | QUANT_DOMINANT (2) | Volume/fan_out flags treated as dispositive |
| FP Charity | 4/5 | QUANT_DOMINANT (2), MIXED (2) | Fan-in threshold acknowledged but NGO context dismissed |
| FP Structurer | 5/5 | MIXED (3), QUANT_DOMINANT (1), QUAL_ENGAGED (1) | Most varied; one case genuinely reads article |

### Hypothesis Assessment

**H-A is the primary explanation (60% of cases):** The majority of auditor rejections show no
substantive engagement with KB article content. The auditor re-evaluates from raw quantitative data
in a fresh context window, finds a flag, and escalates — the analyst's carefully constructed
evidence chain is invisible to it.

**H-B is a secondary factor (40% of cases):** In the MIXED cases, the auditor does read the KB
context but still concludes that quantitative flags are dispositive. This subset implicates the
auditor prompt: it instructs the auditor to check "all claims from the news articles" but does not
explicitly instruct it to treat flags as rebuttable when a plausible legitimate explanation exists.

**Both hypotheses have different design implications.** H-A is architectural: the separate context
window is a structural information loss that cannot be fixed by prompt engineering alone. H-B is
addressable through prompt revision. The data suggest a combined intervention would be required to
materially reduce hierarchical FP rate: (1) pass the analyst's full evidence chain into the auditor
context, and (2) add an explicit "flags are rebuttable" instruction to the auditor prompt.

### Representative Verbatim Quotations

**QUANT_DOMINANT — C4562 (FP Charity):**
> "The Analyst's report fails to directly address the RAW quantitative data that indicates a HIGH
> FAN-IN risk flag with 25 unique senders, which is clearly stated to be above the threshold of 20.
> The Analyst mentions the fan-in but does not provide a robust explanation regarding the implications
> of this specific raw data finding."
> Citation: *"Raw data shows Fan-In=25 which triggers a HIGH risk flag, exceeding the threshold of
> 20, but Analyst's report insufficiently justifies the medium risk score of 65."*

**DISMISSAL — C9986 (FP Control Innocent):**
> "The Analyst's report did not adequately address the absence of a clear connection between the
> client's financial activities and the legitimate business activities suggested in the news articles.
> While the Analyst noted complexity in the transactions, they failed to acknowledge the critical
> lack of evidence linking the transactions to the project management profession."

**MIXED — C1941 (FP Structurer):**
> "The Analyst fails to fully address all relevant risk flags... While the average transaction amount
> is correctly noted as exceeding the $1,000 threshold... the Analyst did not adequately account for
> the claims made in the news articles."
> Citation: *"Raw data shows Avg Amount = $1,160.42 prompting a risk flag, but Analyst does not
> adequately explain the implications of high patient throughput and audit scrutiny as detailed in
> Article 2."*

---

## 6. Output Files

| File | Contents |
|---|---|
| `results/test/gpt-4o-mini/run_1/summary.csv` | Wide-format raw scores for 50 clients × 4 modes (49 for ctx/llm due to errors) |
| `results/test/gpt-4o-mini/run_1/evaluation.csv` | Per-client computed metrics (in_range, correct, score_shift, etc.) |
| `results/test/gpt-4o-mini/run_1/evaluation_{mode}.csv` | Per-mode artifact (logged to MLflow) |
| `results/test/gpt-4o-mini/run_1/{mode}/*.json` | Full AgentState for each client — forensics, news, reasoning, review |
| `results/old_runs/RESULTS_gpt-4o-mini.md` | Earlier 3-mode results (intrinsic, hierarchical, ctx only) before llm_context was added |
| `external_agent_injection.txt` | Kayba's 28-skill context playbook (injected into ctx mode) |
| `llm_context_rules.txt` | Self-synthesised rules from gpt-4o-mini training traces (injected into llm_context mode) |
| `training_traces/*.md` | 50 annotated train traces fed to both Kayba and the LLM synthesiser |

To inspect a specific client's full reasoning chain:
```python
import json
state = json.load(open("results/test/gpt-4o-mini/run_1/intrinsic/C2083.json"))
print(state["analyst_output"]["reasoning"])
print(state["review_output"]["reasoning"])
```

To reproduce the evaluation:
```bash
python 03_evaluate.py --dataset test --model gpt-4o-mini
mlflow ui  # http://127.0.0.1:5000
```
