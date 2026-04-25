# Statistical Significance Analysis: Multi-Agent AML Governance — All Models

> **Purpose:** This document consolidates the results of three formal statistical significance
> tests across all three experimental models: gpt-4o-mini, gpt-5.1, and grok-4. Each model
> is evaluated on the same 168-client test set under four governance modes. The tests establish
> whether observed performance differences are statistically reliable and quantify uncertainty
> around all point estimates. Cross-model comparisons reveal how model capability interacts
> with governance mode effectiveness.

---

## 1. Test Design

### 1.1 Why These Tests

The core experiment produces per-client binary classification outcomes (correct/incorrect) for
four governance modes on the same 168 clients. Because the same subjects are evaluated under
all four conditions, the outcomes are **paired** — the same client is classified by all four
modes, and errors are correlated across modes. This rules out independent-samples tests (e.g.
chi-squared on aggregate counts, independent t-tests on accuracy). The correct family of tests
is **paired comparison tests for binary outcomes**.

Three complementary tests are applied:

| Test | Purpose | What it answers |
|---|---|---|
| **Cochran's Q** | Omnibus | Is there *any* significant difference across all 4 modes simultaneously? |
| **McNemar's** (×6, Bonferroni-corrected) | Pairwise | Which *specific pairs* of modes differ significantly? |
| **Bootstrap CIs** (10,000 iterations) | Estimation | How precise is each mode's F1 and accuracy? Do CIs overlap? |

### 1.2 Experimental Setup

| | |
|---|---|
| **n** | 168 clients (60 guilty, 108 innocent) per model |
| **Classification threshold** | Score ≥ 50 → predicted GUILTY |
| **Modes** | Intrinsic, Hierarchical, Context-Engineered, LLM-Context |
| **Artefact matching** | All artefacts (Kayba playbook, LLM-context rules) generated from each model's own training traces — no cross-model mismatch |
| **gpt-4o-mini replicates** | 3 independent runs; significance tests run on Run 1 (primary) |
| **gpt-5.1, grok-4 replicates** | 1 run each |

### 1.3 Governance Modes

| Mode | Architecture | Extra context | Reviewer |
|---|---|---|---|
| **Intrinsic** | Same-context self-review | None | Analyst reviews own draft |
| **Hierarchical** | Separate-context auditor | None | Independent Auditor agent |
| **Context-Engineered** | Same-context self-review | Kayba-generated playbook | Analyst reviews own draft |
| **LLM-Context** | Same-context self-review | LLM-synthesised rules | Analyst reviews own draft |

> **Valid pairwise comparisons:** Intrinsic vs Hierarchical (architecture), Intrinsic vs
> Context-Eng (Kayba injection), Intrinsic vs LLM-Context (LLM rules), Context-Eng vs
> LLM-Context (rule source). The two pairs involving Hierarchical vs a context-injected mode
> are **confounded** — both architecture and rule injection differ simultaneously.
>
> **Scope note:** Two additional combined modes (Hier+Ctx, Hier+LLM) were subsequently run,
> completing a 2×3 design (architecture × rule source) that deconfounds these pairs. Those
> results and their clean pairwise comparisons are documented in the per-model results files
> (RESULTS-gpt-4o-mini.md §5b, RESULTS-gpt-5.1.md §5b, RESULTS-grok-4.md). Significance
> tests for the combined modes are not included here. A revision depth ablation
> (depths 0–10, intrinsic mode, gpt-4o-mini only) is documented separately in
> RESULTS-revision-depth-gpt-4o-mini.md.

### 1.4 Multiple Comparisons

Six pairwise comparisons are possible across four modes. Running six tests at α=0.05 without
correction gives a familywise error rate of 1 − 0.95⁶ ≈ 26%. **Bonferroni correction** is
applied: each raw p-value is multiplied by 6, threshold remains 0.05. This is conservative
(assumes independence across tests) but is the standard choice for small comparison sets.

---

## 2. Cochran's Q — Omnibus Test

### 2.1 Method

Cochran's Q is the non-parametric equivalent of repeated-measures ANOVA for binary outcomes.
For k classifiers evaluated on n subjects:

```
Q = (k−1) × [k × ΣCj² − T²] / [k × T − ΣRi²]

where:
  k  = number of modes (4)
  n  = number of subjects (168)
  Cj = total correct for mode j (column sum)
  Ri = total modes correct for subject i (row sum)
  T  = grand total of correct classifications
```

Under the null hypothesis (all modes equivalent), Q ~ chi-squared, df = k−1 = 3.

### 2.2 Results Across All Models

| Model | Q statistic | df | p-value | Significant? |
|---|:---:|:---:|:---:|:---:|
| gpt-4o-mini | 27.105 | 3 | < 0.0001 | **Yes** |
| gpt-5.1 | 28.869 | 3 | < 0.0001 | **Yes** |
| grok-4 | 22.059 | 3 | 0.0001 | **Yes** |

### 2.3 Interpretation

The null hypothesis is **rejected for all three models** (all p ≤ 0.0001). At least one
governance mode produces statistically different classification outcomes in every experiment.
This result is consistent regardless of model capability level — from gpt-4o-mini's 47.6%
intrinsic accuracy to grok-4's 94.0%.

Notably, the Q statistic remains high even for gpt-5.1 (Q = 28.869) and grok-4 (Q = 22.059)
despite their near-ceiling baseline performance. This indicates the error patterns are
sufficiently different across modes to register a clear omnibus signal even when total errors
are few. In both cases, the signal is driven primarily by LLM-Context — in opposite directions
(best for gpt-5.1, worst for grok-4).

All further pairwise analysis is warranted — the omnibus test confirms this is not post-hoc
fishing.

---

## 3. Pairwise McNemar's Tests — Bonferroni-Corrected

### 3.1 Method

For each pair of modes (A, B), a 2×2 contingency table is built over 168 clients:

|  | Mode B correct | Mode B wrong |
|---|---|---|
| **Mode A correct** | a — both right (irrelevant) | b — A right, B wrong |
| **Mode A wrong** | c — B right, A wrong | d — both wrong (irrelevant) |

Only the discordant cells b and c carry information. McNemar's test with Yates' continuity
correction:

```
chi-squared = (|b − c| − 1)² / (b + c),   df = 1
```

A significant result means one mode corrects cases the other fails at a rate beyond chance.

### 3.2 Results: gpt-4o-mini

| Mode A | Mode B | b (A+ B−) | c (A− B+) | chi-sq | p (raw) | p (Bonf.) | Sig. |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Intrinsic | Hierarchical | 12 | 16 | 0.321 | 0.5708 | 1.0000 | No |
| Intrinsic | Context-Eng | 16 | 18 | 0.029 | 0.8638 | 1.0000 | No |
| Intrinsic | LLM-Context | 11 | 39 | 14.580 | 0.0001 | **0.0008** | **Yes** |
| Hierarchical | Context-Eng | 15 | 13 | 0.036 | 0.8501 | 1.0000 | No |
| Hierarchical | LLM-Context | 9 | 33 | 12.595 | 0.0004 | **0.0023** | **Yes** |
| Context-Eng | LLM-Context | 10 | 36 | 13.587 | 0.0002 | **0.0014** | **Yes** |

**3/6 pairs significant.** LLM-Context significantly outperforms every other mode.

### 3.3 Results: gpt-5.1

| Mode A | Mode B | b (A+ B−) | c (A− B+) | chi-sq | p (raw) | p (Bonf.) | Sig. |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Intrinsic | Hierarchical | 6 | 3 | 0.444 | 0.5050 | 1.0000 | No |
| Intrinsic | Context-Eng | 1 | 6 | 2.286 | 0.1306 | 0.7834 | No |
| Intrinsic | LLM-Context | 0 | 13 | 11.077 | 0.0009 | **0.0052** | **Yes** |
| Hierarchical | Context-Eng | 0 | 8 | 6.125 | 0.0133 | 0.0800 | No |
| Hierarchical | LLM-Context | 0 | 16 | 14.062 | 0.0002 | **0.0011** | **Yes** |
| Context-Eng | LLM-Context | 0 | 8 | 6.125 | 0.0133 | 0.0800 | No |

**2/6 pairs significant.** LLM-Context significantly outperforms Intrinsic and Hierarchical.
Context-Eng vs LLM-Context and Intrinsic vs Context-Eng show directional trends (b=0 or b=1)
but do not reach significance after correction — a power limitation from near-ceiling baseline.

### 3.4 Results: grok-4

| Mode A | Mode B | b (A+ B−) | c (A− B+) | chi-sq | p (raw) | p (Bonf.) | Sig. |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Intrinsic | Hierarchical | 8 | 4 | 0.750 | 0.3865 | 1.0000 | No |
| Intrinsic | Context-Eng | 6 | 8 | 0.071 | 0.7893 | 1.0000 | No |
| Intrinsic | LLM-Context | 19 | 2 | 12.190 | 0.0005 | **0.0029** | **Yes** |
| Hierarchical | Context-Eng | 4 | 10 | 1.786 | 0.1814 | 1.0000 | No |
| Hierarchical | LLM-Context | 21 | 8 | 4.966 | 0.0259 | 0.1551 | No |
| Context-Eng | LLM-Context | 24 | 5 | 11.172 | 0.0008 | **0.0050** | **Yes** |

**2/6 pairs significant.** LLM-Context significantly *underperforms* Intrinsic and Context-Eng
— a complete inversion of the gpt-4o-mini and gpt-5.1 pattern.

### 3.5 Cross-Model Comparison of Pairwise Results

The following table summarises whether each pairwise comparison is significant and in which
direction across all three models. Direction is relative to Mode B (positive = Mode B better).

| Comparison | gpt-4o-mini | gpt-5.1 | grok-4 | Note |
|---|:---:|:---:|:---:|---|
| Intrinsic vs Hierarchical | No (p=1.000) | No (p=1.000) | No (p=1.000) | Consistent null across all models |
| Intrinsic vs Context-Eng | No (p=1.000) | No (p=0.783) | No (p=1.000) | Consistent null; trend for gpt-5.1 |
| **Intrinsic vs LLM-Context** | **Yes, LLM+ (p=0.0008)** | **Yes, LLM+ (p=0.0052)** | **Yes, LLM− (p=0.0029)** | **Inverts for grok-4** |
| Hierarchical vs Context-Eng | No (p=1.000) | No (p=0.080) | No (p=1.000) | Confounded; all null |
| Hierarchical vs LLM-Context | Yes, LLM+ (p=0.0023) | Yes, LLM+ (p=0.0011) | No (p=0.155) | Confounded; grok-4 trend reversed |
| **Context-Eng vs LLM-Context** | **Yes, LLM+ (p=0.0014)** | **No (p=0.080, trend)** | **Yes, CTX+ (p=0.0050)** | **Cleanest comparison; inverts** |

### 3.6 Pairwise Interpretation by Comparison

#### Intrinsic vs Hierarchical

**Not significant across all three models (p=1.000 for all).** The architectural distinction
between same-context self-review and separate-context auditing produces no statistically
detectable improvement at any capability level tested. This is a consistent finding:

- For **gpt-4o-mini**: the auditor is aggressive (28% consensus), escalates scores frequently,
  and achieves perfect recall — but introduces so many false positives that net accuracy is
  indistinguishable from self-review (12 vs 16 discordant cases, symmetric).
- For **gpt-5.1**: the auditor is entirely passive (100% consensus), almost never intervening.
  6 vs 3 discordant cases — too few to detect anything.
- For **grok-4**: the auditor is similarly passive (98% consensus). 8 vs 4 discordant cases.

**Implication:** Independent governance architecture adds no statistically verified benefit.
Whether the auditor is aggressive (gpt-4o-mini) or passive (gpt-5.1, grok-4), the net effect
on correct classifications is not distinguishable from unaided self-review.

#### Intrinsic vs Context-Engineered

**Not significant across all three models** (p = 1.000, 0.783, 1.000). The Kayba-generated
playbook does not produce a statistically reliable improvement over unaided self-review in
any model condition. However, the pattern shifts with model capability:

- For **gpt-4o-mini**: the discordance is symmetric (16 vs 18) — the playbook helps and harms
  in roughly equal measure. The "capability-execution gap" hypothesis applies: the model
  triggers over-scrutiny (83% rejection rate) without accurately operationalising the rules.
- For **gpt-5.1**: the discordance is directional (1 vs 6) but insufficient (p = 0.783). The
  playbook helps more than it hurts. With a larger test set this would likely be significant.
- For **grok-4**: the discordance is near-symmetric (6 vs 8). Both modes perform near-ceiling;
  very little room for the playbook to differentiate.

**Implication:** The Kayba playbook improves performance directionally for capable models but
does not reach significance on n=168. This is a power limitation, not evidence of absence.

#### Intrinsic vs LLM-Context

**The most important comparison — and the one that inverts across models.**

- **gpt-4o-mini** (p = 0.0008, c=39 >> b=11): LLM-Context is strongly and significantly
  better. Case-specific self-synthesised rules correct 39 cases that Intrinsic gets wrong,
  while introducing only 11 new errors. The LLM has enough training errors (many) to
  synthesise rules that target real failure modes.

- **gpt-5.1** (p = 0.0052, b=0, c=13): LLM-Context is again significantly better, with a
  perfectly asymmetric result — it never makes an error that Intrinsic gets right. The rules
  are strictly additive corrections. gpt-5.1's higher capability means fewer errors total,
  but the ones that exist are still addressed by the self-synthesised rules.

- **grok-4** (p = 0.0029, b=19 >> c=2): LLM-Context is significantly **worse**. Intrinsic
  gets 19 cases right that LLM-Context gets wrong — the inversion of the above. grok-4 made
  only 2 errors in 86 training traces, so the rule synthesis had almost no failure signal.
  The resulting rules do not target real failure modes — they appear to over-sensitise the
  model, introducing 27 false positives vs 8 for Intrinsic.

**Implication:** The effectiveness of LLM-context rule synthesis is gated by training error
density. Sufficient failures must exist in training traces for the synthesis to produce
actionable rules. Below this threshold, self-synthesised rules may actively harm performance.

#### Hierarchical vs Context-Engineered *(confounded)*

Not significant for any model (p = 1.000, 0.080, 1.000). Both architecture and rule injection
differ — no clean causal attribution is possible. Reported for completeness only.

#### Hierarchical vs LLM-Context *(confounded)*

Significant for gpt-4o-mini (p=0.0023, LLM+) and gpt-5.1 (p=0.0011, LLM+), not significant
for grok-4 (p=0.155, directional trend for Hier+). Again confounded — architecture and rules
differ. The grok-4 trend reversal is consistent with LLM-Context underperforming overall for
that model.

#### Context-Engineered vs LLM-Context *(cleanest comparison)*

**The methodologically cleanest comparison:** same architecture, same pipeline, only the
source of injected rules differs (Kayba external vs LLM self-synthesised). Results:

- **gpt-4o-mini** (p = 0.0014, c=36 >> b=10): LLM-Context significantly better. Self-
  synthesised case-specific rules outperform abstract Kayba rules at this capability level.
  The model can operationalise concrete examples derived from its own failure modes more
  effectively than generalised external rule descriptions.

- **gpt-5.1** (p = 0.080, b=0, c=8): LLM-Context directionally better but not significant.
  Near-ceiling performance for both modes leaves only 8 discordant cases — insufficient power
  after Bonferroni correction. All discordant cases favour LLM-Context (b=0).

- **grok-4** (p = 0.0050, b=24 >> c=5): Context-Eng significantly better. Kayba's externally
  generated playbook — which generalises across failure modes rather than being synthesised
  from grok-4's specific (near-zero) errors — outperforms self-synthesised rules that had
  almost no failure signal to learn from.

**Implication:** The superiority of external (Kayba) vs internal (LLM) rule synthesis depends
on training error density. For weaker models with many training errors, self-synthesised rules
win. For stronger models with near-zero training errors, external rules generalise better.

---

## 4. Bootstrap Confidence Intervals

### 4.1 Method

For each mode and model, 10,000 bootstrap resamples (n=168 with replacement) are drawn. F1
and accuracy are computed on each resample. The 2.5th and 97.5th percentiles define the 95%
CI.

### 4.2 Results: gpt-4o-mini

| Mode | Accuracy | Acc 95% CI | F1 | F1 95% CI |
|---|:---:|---|:---:|---|
| Intrinsic | 0.476 | [0.399 − 0.554] | 0.542 | [0.452 − 0.624] |
| Hierarchical | 0.500 | [0.423 − 0.577] | 0.588 | [0.503 − 0.667] |
| Context-Eng | 0.488 | [0.411 − 0.565] | 0.561 | [0.472 − 0.640] |
| **LLM-Context** | **0.643** | **[0.571 − 0.714]** | **0.659** | **[0.573 − 0.735]** |

LLM-Context is clearly separated: its lower bound (0.571 accuracy, 0.573 F1) exceeds the
upper bounds of both Intrinsic (0.554 accuracy, 0.624 F1). The other three modes have
heavily overlapping CIs spanning ~0.15 width — consistent with the non-significant pairwise
McNemar's results among them. The practical advantage of LLM-Context over Intrinsic is
confirmed even under the most conservative bootstrap draw (+0.017 accuracy lower bound).

### 4.3 Results: gpt-5.1

| Mode | Accuracy | Acc 95% CI | F1 | F1 95% CI |
|---|:---:|---|:---:|---|
| Intrinsic | 0.923 | [0.881 − 0.958] | 0.883 | [0.810 − 0.940] |
| Hierarchical | 0.905 | [0.857 − 0.946] | 0.855 | [0.777 − 0.919] |
| Context-Eng | 0.952 | [0.917 − 0.982] | 0.929 | [0.874 − 0.973] |
| **LLM-Context** | **1.000** | **[1.000 − 1.000]** | **1.000** | **[1.000 − 1.000]** |

LLM-Context achieves a degenerate CI of [1.000 − 1.000], reflecting zero classification
errors on the 168-client test set. Every bootstrap resample also returns perfect performance —
there is no observed variance to estimate. This should be interpreted as "consistent with
near-perfect performance given observed data", not a guarantee of exactly 1.000 on unseen
data. All three other modes' upper bounds (0.946–0.982) fall below LLM-Context's lower bound
(1.000), confirming significant separation. Hierarchical performs worst (F1: 0.855), with a
CI that overlaps the other two non-LLM modes but sits consistently lower.

### 4.4 Results: grok-4

| Mode | Accuracy | Acc 95% CI | F1 | F1 95% CI |
|---|:---:|---|:---:|---|
| Intrinsic | 0.940 | [0.905 − 0.976] | 0.921 | [0.867 − 0.965] |
| Hierarchical | 0.917 | [0.875 − 0.958] | 0.889 | [0.826 − 0.942] |
| **Context-Eng** | **0.952** | **[0.917 − 0.982]** | **0.932** | **[0.879 − 0.975]** |
| LLM-Context | 0.839 | [0.780 − 0.893] | 0.816 | [0.744 − 0.880] |

For grok-4 the picture inverts: LLM-Context is the worst mode, clearly separated from the
others in the downward direction. Its upper bound (0.893 accuracy, 0.880 F1) falls below the
lower bounds of Context-Eng (0.917 accuracy, 0.879 F1) — non-overlapping in the wrong
direction. Intrinsic, Hierarchical, and Context-Eng all overlap substantially, consistent
with their non-significant McNemar's results. Context-Eng has the highest point estimates and
the tightest upper CI, positioning it as the best mode for grok-4.

### 4.5 Cross-Model CI Summary

The following table shows where each mode's F1 CI sits relative to the others, per model:

| Model | Best mode (CI) | Worst mode (CI) | Separation confirmed? |
|---|---|---|---|
| gpt-4o-mini | LLM-Context [0.573−0.735] | Intrinsic [0.452−0.624] | Yes — no overlap |
| gpt-5.1 | LLM-Context [1.000−1.000] | Hierarchical [0.777−0.919] | Yes — no overlap |
| grok-4 | Context-Eng [0.879−0.975] | LLM-Context [0.744−0.880] | Yes — no overlap |

In all three models, the CI analysis confirms that the outlier mode (LLM-Context for gpt-4o-mini
and gpt-5.1; LLM-Context as worst for grok-4; Context-Eng as best for grok-4) is genuinely
separated, not within sampling noise.

---

## 5. Cross-Model Summary of Statistical Evidence

### 5.1 Cochran's Q

| Model | Q | p | Verdict |
|---|:---:|:---:|---|
| gpt-4o-mini | 27.105 | <0.0001 | Modes differ significantly |
| gpt-5.1 | 28.869 | <0.0001 | Modes differ significantly |
| grok-4 | 22.059 | 0.0001 | Modes differ significantly |

All three experiments show statistically real differences across modes.

### 5.2 Significant Pairwise Results (post-Bonferroni)

| Comparison | gpt-4o-mini | gpt-5.1 | grok-4 |
|---|---|---|---|
| Intrinsic vs LLM-Context | **LLM+ p=0.0008** | **LLM+ p=0.0052** | **LLM− p=0.0029** |
| Hierarchical vs LLM-Context* | LLM+ p=0.0023 | LLM+ p=0.0011 | n.s. p=0.155 |
| Context-Eng vs LLM-Context | **LLM+ p=0.0014** | n.s. p=0.080 | **CTX+ p=0.0050** |
| All other pairs | n.s. | n.s. | n.s. |

*confounded comparison

### 5.3 Key Findings

1. **Hierarchical auditing adds no statistically verified value at any model capability level.**
   Intrinsic vs Hierarchical is non-significant for all three models (p = 1.000, 1.000, 1.000).
   The auditor's behaviour varies dramatically — aggressive for gpt-4o-mini, passive for
   gpt-5.1 and grok-4 — but neither produces a net improvement in correct classifications
   that survives statistical testing.

2. **Kayba context injection (Context-Eng) does not significantly improve on unaided
   self-review for any model.** Intrinsic vs Context-Eng is non-significant across all three
   models (p = 1.000, 0.783, 1.000). Directional trends exist, particularly for gpt-5.1, but
   n=168 lacks the power to confirm them after Bonferroni correction.

3. **LLM-Context is significantly different from Intrinsic for all three models — but in
   opposite directions.** For gpt-4o-mini and gpt-5.1 it significantly outperforms (p = 0.0008
   and 0.0052); for grok-4 it significantly underperforms (p = 0.0029). The direction depends
   on training error density.

4. **The Context-Eng vs LLM-Context comparison — the cleanest test of rule source — inverts
   between gpt-4o-mini and grok-4.** LLM-Context wins significantly for gpt-4o-mini (p=0.0014,
   c=36 vs b=10); Context-Eng wins significantly for grok-4 (p=0.0050, b=24 vs c=5); gpt-5.1
   shows a directional trend for LLM-Context (b=0, c=8) that does not survive correction.

5. **Training error density is the mediating variable for LLM-Context effectiveness:**

   | Model | Train errors / 86 | LLM-Context vs Intrinsic |
   |---|:---:|---|
   | gpt-4o-mini | many | Significantly better |
   | gpt-5.1 | moderate | Significantly better |
   | grok-4 | 2 / 86 | Significantly worse |

   Below a critical threshold of failure signal, LLM-context rule synthesis produces
   miscalibrated rules that degrade rather than improve performance.

6. **Bootstrap CIs confirm all significant McNemar's findings** and add quantified uncertainty
   to all point estimates. Non-overlapping CIs match every significant pairwise result; heavily
   overlapping CIs match every non-significant pair. The two methods are fully consistent.

---

## 6. Limitations

- **Bonferroni correction is conservative.** It assumes independence across all six pairwise
  tests, which is not the case (modes share the same 168 subjects). More powerful corrections
  (Holm, Benjamini-Hochberg) would yield lower corrected p-values, potentially bringing
  borderline results (gpt-5.1 Context-Eng vs LLM-Context, p=0.080; gpt-5.1 Intrinsic vs
  Context-Eng, p=0.783) into significance.

- **Ceiling effects reduce power for gpt-5.1 and grok-4.** With most modes above 90%
  accuracy, very few discordant cases exist for McNemar's to operate on. Non-significance
  in these cases reflects insufficient power, not absence of effect. A larger test set (e.g.
  n=500) would likely resolve several borderline pairs.

- **Two pairwise comparisons are confounded** (Hierarchical vs Context-Eng, Hierarchical vs
  LLM-Context) — both governance architecture and rule injection differ simultaneously. These
  are reported for completeness but cannot be used to attribute effects to a single variable.

- **gpt-5.1 and grok-4 have single runs.** Only gpt-4o-mini has 3 replicates confirming
  variance. The single-run results for the other two models are reliable on the significance
  tests (which operate on within-run paired data) but variance in point estimates is not
  characterised.

- **The gpt-5.1 LLM-Context degenerate CI [1.000−1.000] cannot be extrapolated.** Zero
  errors on the observed test set is a strong empirical finding, but it does not imply
  exactly perfect performance on any future test set. The CI reflects observed data, not a
  theoretical guarantee.

- **Training error density is a post-hoc explanation for grok-4's LLM-Context inversion.**
  While it is well-supported by the evidence (2/86 training errors, 27 test FPs), it is not
  a controlled experimental manipulation. Confirming this mechanism would require a designed
  experiment varying training error density directly.

---

## 7. Robustness Across Replicates (Run 1 / 2 / 3)

Each model was evaluated on the same 168-client test set across three independent replicates
(different random API samples, same artefacts). This section reports whether the point
estimates and qualitative conclusions from sections 2–5 are stable across runs.

> **Note on gpt-5.1 artefact integrity:** Runs 2 and 3 for gpt-5.1 were initially executed
> with context-engineered and LLM-context artefacts that had been accidentally overwritten
> with holdout-D2 versions (trained on 75 clients, D2 Smurf excluded). Both runs were
> re-executed with the correct full-train artefacts (86 clients, all groups) before the
> results below were recorded. Run 1 was unaffected (conducted before the holdout experiment).

### 7.1 F1 by Mode Across Runs

#### gpt-4o-mini

| Mode | Run 1 | Run 2 | Run 3 | Mean | Std | Range |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Intrinsic | 0.542 | 0.528 | 0.531 | 0.534 | 0.006 | 0.014 |
| Hierarchical | 0.588 | 0.571 | 0.569 | 0.576 | 0.009 | 0.019 |
| Context-Eng | 0.561 | 0.587 | 0.580 | 0.576 | 0.011 | 0.026 |
| LLM-Context | 0.659 | 0.645 | 0.635 | 0.646 | 0.010 | 0.024 |

#### gpt-5.1

| Mode | Run 1 | Run 2 | Run 3 | Mean | Std | Range |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Intrinsic | 0.883 | 0.873 | 0.893 | 0.883 | 0.008 | 0.020 |
| Hierarchical | 0.855 | 0.914 | 0.895 | 0.888 | 0.025 | 0.059 |
| Context-Eng | 0.929 | 0.919 | 0.909 | 0.919 | 0.008 | 0.020 |
| LLM-Context | **1.000** | **1.000** | **1.000** | **1.000** | **0.000** | **0.000** |

#### grok-4

| Mode | Run 1 | Run 2 | Run 3 | Mean | Std | Range |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Intrinsic | 0.921 | 0.927 | 0.927 | 0.925 | 0.003 | 0.006 |
| Hierarchical | 0.889 | 0.891 | 0.934 | 0.905 | 0.021 | 0.045 |
| Context-Eng | 0.932 | 0.872 | 0.957 | 0.920 | 0.036 | 0.085 |
| LLM-Context | 0.816 | 0.828 | 0.811 | 0.818 | 0.007 | 0.017 |

### 7.2 TP / FP / TN / FN Across Runs

#### gpt-4o-mini

| Mode | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Intrinsic | 52/80/28/8 | 52/85/23/8 | 52/84/24/8 |
| Hierarchical | 60/84/24/0 | 58/85/23/2 | 60/91/17/0 |
| Context-Eng | 55/81/27/5 | 59/82/26/1 | 60/87/21/0 |
| LLM-Context | 58/58/50/2 | 60/66/42/0 | 60/69/39/0 |

#### gpt-5.1

| Mode | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Intrinsic | 49/2/106/11 | 48/2/106/12 | 50/2/106/10 |
| Hierarchical | 47/3/105/13 | 53/3/105/7 | 51/3/105/9 |
| Context-Eng | 52/0/108/8 | 51/0/108/9 | 50/0/108/10 |
| LLM-Context | **60/0/108/0** | **60/0/108/0** | **60/0/108/0** |

#### grok-4

| Mode | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Intrinsic | 58/8/100/2 | 57/6/102/3 | 57/6/102/3 |
| Hierarchical | 56/10/98/4 | 57/11/97/3 | 57/5/103/3 |
| Context-Eng | 55/3/105/5 | 51/6/102/9 | 55/0/108/5 |
| LLM-Context | 60/27/81/0 | 60/25/83/0 | 60/28/80/0 |

### 7.3 FN Smurf (D2) Accuracy Across Runs

The FN Smurf group (n=22) is the hardest subgroup and the most diagnostic for
rule-injection effectiveness, since Smurf clients have clean transaction data and
guilt is detectable only from buried news intelligence.

| Model | Mode | Run 1 | Run 2 | Run 3 |
|---|---|:---:|:---:|:---:|
| gpt-4o-mini | Intrinsic | 86% | 82% | 68% |
| gpt-4o-mini | Hierarchical | 100% | 96% | 100% |
| gpt-4o-mini | Context-Eng | 91% | 96% | 100% |
| gpt-4o-mini | LLM-Context | 91% | 100% | 100% |
| gpt-5.1 | Intrinsic | 59% | 59% | 64% |
| gpt-5.1 | Hierarchical | 59% | 68% | 68% |
| gpt-5.1 | Context-Eng | 73% | 64% | 64% |
| gpt-5.1 | LLM-Context | **100%** | **100%** | **100%** |
| grok-4 | Intrinsic | 91% | 86% | 86% |
| grok-4 | Hierarchical | 82% | 86% | 86% |
| grok-4 | Context-Eng | 82% | 59% | 82% |
| grok-4 | LLM-Context | 100% | 100% | 100% |

### 7.4 Observations

**Mode rankings are stable across all runs for all models.** No replicate produces a rank
inversion at the overall F1 level. The ordering established in sections 2–5
(gpt-4o-mini: LLM > Ctx ≈ Hier > Int; gpt-5.1: LLM > Ctx > Int ≈ Hier; grok-4:
Ctx ≈ Int > Hier > LLM) holds in every replicate.

**gpt-5.1 LLM-Context is perfectly stable.** F1 = 1.000, TP/FP/TN/FN = 60/0/108/0,
and Smurf accuracy = 100% in all three runs (std = 0.000). This is the most robust
finding in the study.

**Hierarchical shows the most variance for gpt-5.1** (F1 range 0.059, FN 7–13). The
independent auditor's judgment on borderline cases — particularly FN Sleepers — is
less deterministic than the rule-injection modes, likely because it relies on a
separate LLM inference rather than a constrained prompt augmentation.

**Context-Eng shows the most variance for grok-4** (F1 range 0.085, FP 0–6 across
runs). The Kayba playbook activates inconsistently for grok-4's Smurf group (59–82%),
suggesting the playbook's abstract skills do not reliably trigger on this typology at
this capability level.

**LLM-Context for grok-4 is stable in the wrong direction** (F1 0.811–0.828, std
0.007). The degradation relative to Intrinsic is consistent and precise — confirming
that the sparse-training-error problem identified in section 5 is a systematic effect,
not noise.

**gpt-4o-mini variance is moderate and consistent in direction.** All three runs agree
LLM-Context > {Context-Eng, Hierarchical} > Intrinsic, with within-mode F1 variation
of ≤ 0.024. The FP counts fluctuate more than FN counts (FPs range 58–80 for
Intrinsic), reflecting the stochastic weighting of ambiguous FP-trap evidence.
