# Experiment Results: Multi-Agent AML Governance — gpt-4o-mini

> **Thesis question:** Does external context injection (Kayba ACE) close the performance gap between
> intrinsic self-correction and independent hierarchical auditing — at a fraction of the cost?
> A secondary condition tests whether LLM-synthesised self-reflection rules match or exceed Kayba.

---

## 1. Setup at a Glance

| | |
|---|---|
| **Dataset** | AMLNet (1.09M transactions, 10k users) — 168 test clients, 86 train clients |
| **Ground truth** | 60 guilty, 108 innocent (test set) |
| **Model** | `gpt-4o-mini` (identical across all four modes) |
| **Classification threshold** | Score ≥ 50 → predicted GUILTY |
| **Kayba training input** | 86 train traces (intrinsic mode, gpt-4o-mini) |
| **Kayba output** | 28 deduplicated skills, context playbook (`external_agent_injection_gpt-4o-mini.txt`) |
| **LLM self-reflection input** | Same 86 train traces, rules synthesised by gpt-4o-mini (`llm_context_rules_gpt-4o-mini.txt`) |
| **Errors** | None — all 168 clients completed successfully across all four modes |

### The Four Modes

| Mode | What happens | Extra context | Reviewer |
|---|---|---|---|
| **Intrinsic** | Analyst reviews its own draft | None | Same LLM instance |
| **Hierarchical** | Independent Auditor reviews the Analyst | None | Separate LLM agent with different system prompt |
| **Context-Engineered** | Analyst + Kayba playbook injected into self-review | Kayba's 28-skill playbook | Same LLM instance |
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
| **Classification Accuracy** | 47.6% | 50.0% | 48.8% | **64.3%** |
| **Precision** | 0.39 | 0.42 | 0.40 | **0.50** |
| **Recall** | 0.87 | **1.00** | 0.92 | 0.97 |
| **F1 Score** | 0.54 | 0.59 | 0.56 | **0.66** |
| True Positives | 52 | **60** | 55 | 58 |
| False Positives | 80 | 84 | 81 | **58** |
| True Negatives | 28 | 24 | 27 | **50** |
| False Negatives | 8 | **0** | 5 | 2 |

### Score Accuracy

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| Range Accuracy (score within expected band) | 30.4% | 39.9% | 32.1% | **49.4%** |
| MAE from midpoint | 34.2 | 36.3 | 34.0 | **25.2** |
| Avg Confidence | 81.5 | 81.9 | 82.4 | **83.8** |

### Governance Behaviour & Efficiency

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| Consensus Rate (reviewer approved) | 53% | 28% | 17% | 32% |
| Avg Revisions per Case | 1.41 | 1.62 | **1.80** | 1.61 |
| Avg LLM Calls per Case | 5.8 | 6.2 | **6.6** | 6.2 |
| Avg Score Shift (final − initial) | +4.6 | **+13.4** | +5.2 | +3.1 |

---

## 3. Per-Group Breakdown

### Classification Accuracy by Group

| Group | n | Truth | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Control Guilty** | 16 | GUILTY | ✅ 100% | ✅ 100% | ⚠️ 94% | ✅ 100% |
| **Control Innocent** | 16 | INNOCENT | ✅ 100% | ⚠️ 81% | ⚠️ 88% | ✅ 94% |
| **FP Trap: Charity** | 23 | INNOCENT | ⚠️ 43% | ❌ 35% | ❌ 30% | ⚠️ 48% |
| **FP Trap: Payroll** | 23 | INNOCENT | ❌ 0% | ❌ 9% | ❌ 13% | ⚠️ 52% |
| **FP Trap: High Roller** | 23 | INNOCENT | ❌ 0% | ❌ 0% | ❌ 0% | ❌ 17% |
| **FP Trap: Structurer** | 23 | INNOCENT | ❌ 9% | ❌ 4% | ❌ 13% | ❌ 35% |
| **FN Trap: Sleeper** | 22 | GUILTY | ⚠️ 77% | ✅ 100% | ✅ 91% | ✅ 100% |
| **FN Trap: Smurf** | 22 | GUILTY | ⚠️ 86% | ✅ 100% | ✅ 91% | ✅ 91% |

*✅ = strong performance (≥80%)  ⚠️ = partial (50–79%)  ❌ = failure (<50%)*

### Average Risk Score by Group

| Group | Expected | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|
| Control Guilty | 70–100 | 80.8 | **84.4** | 75.9 | 83.8 |
| Control Innocent | 0–30 | **21.2** | 29.1 | 23.8 | 20.6 |
| FP: Charity | 0–30 | 52.7 | 59.2 | 53.1 | **42.4** |
| FP: Payroll | 0–30 | 68.7 | 79.1 | 69.7 | **50.2** |
| FP: High Roller | 0–30 | 70.4 | 82.9 | 74.6 | **65.4** |
| FP: Structurer | 0–30 | 64.5 | 69.4 | 59.8 | **50.0** |
| FN: Sleeper | 70–100 | 60.9 | **77.3** | 66.4 | 83.2 |
| FN: Smurf | 70–100 | 66.4 | **77.0** | 68.0 | 75.7 |

---

## 4. Reasoning Quality

Two LLM judges score each case on a 1–10 scale:
- **Evidence Coverage:** Does the reasoning cite specific metrics and article claims?
- **Conclusion Consistency:** Does the reasoning support the final risk decision?

### 4a. Original scores (judge: gpt-4o-mini, self-evaluation)

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|
| Evidence Coverage (mean) | 9.32 | **9.54** | 9.36 | 9.42 |
| Evidence Coverage (min/max) | 6 / 10 | 6 / 10 | 8 / 10 | 6 / 10 |
| Conclusion Consistency (mean) | 6.76 | **8.23** | 7.12 | 7.87 |
| Conclusion Consistency (min/max) | 1 / 10 | 1 / 10 | 1 / 10 | 1 / 10 |

**Key observation:** Evidence coverage is uniformly high (9.32–9.54) — gpt-4o-mini reliably cites available
metrics and article content regardless of governance mode. This confirms the model engages substantively
with the evidence; the failure to classify correctly is a reasoning and weighting problem, not an evidence
retrieval problem.

Conclusion consistency is more variable and lower overall (6.76–8.23). Hierarchical scores highest (8.23),
which reflects an artefact of the audit structure: the auditor rewrites reasoning to justify its escalation
decision, producing locally coherent argument chains even when the underlying decision is wrong. Intrinsic
scores lowest (6.76), consistent with the model's tendency to issue high-confidence incorrect decisions on
the FP traps without flagging internal tension in its reasoning.

### 4b. Re-scored with external judge (judge: claude-sonnet-4-6)

To reduce self-evaluation leniency bias — a model rating its own reasoning will tend to be systematically
lenient — the reasoning quality metrics were re-run using Claude Sonnet 4.6 as a fixed external judge.
This also extends coverage to the two combined modes (hier_context_engineered, hier_llm_context) that were
not scored in the original run.

| Metric | Intrinsic | Hierarchical | Context-Eng | LLM-Context | Hier+Ctx | Hier+LLM |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Evidence Coverage (mean) | 6.45 | **6.60** | 6.46 | 6.46 | 6.43 | 6.55 |
| Conclusion Consistency (mean) | 4.62 | 5.92 | 4.79 | 5.39 | **6.35** | 6.10 |

**Key observations:**

Evidence coverage drops sharply from ~9.4 (self-judged) to ~6.5 (external judge), consistent with
self-evaluation leniency — gpt-4o-mini was awarding high scores to its own reasoning regardless of
specificity. The external judge applies a stricter standard: scores around 6–7 indicate partial evidence
citation but insufficient specificity or missing metric values.

Evidence coverage is flat across all six modes (6.43–6.60), confirming that the choice of governance
architecture does not affect how thoroughly agents retrieve and cite evidence. The failure modes are
downstream of evidence gathering.

Conclusion consistency shows more meaningful variation under the external judge (4.62–6.35). The
hierarchical combined modes (Hier+Ctx: 6.35, Hier+LLM: 6.10) score highest, suggesting that when both
an independent auditor and explicit rules are present, the final written reasoning is more internally
coherent. Pure intrinsic self-review scores lowest (4.62), reinforcing the anchoring finding: agents
reach a conclusion early and construct reasoning around it rather than deriving the conclusion from the
evidence.

---

## 5. What the Results Mean

Findings are framed around the four valid pairwise comparisons identified in the comparison design above.

### Finding 1 [Intrinsic vs Hierarchical]: Hierarchical achieves perfect recall but at severe FP cost

Hierarchical achieves F1=0.59 vs intrinsic F1=0.54 — a marginal improvement driven entirely by perfect
recall (0 FNs vs 8). But this comes at an extreme cost: 84 false positives vs intrinsic's 80. The
hierarchical auditor flags every guilty client but cannot distinguish innocents: 84 of 108 innocent clients
are incorrectly escalated.

The mechanism is clear from the per-group data: the hierarchical auditor scores FP groups almost as high
as truly guilty clients (payroll avg 79.1, high roller avg 82.9, structurer avg 69.4). When confronted
with legitimate businesses whose transaction patterns resemble money laundering, the auditor amplifies the
Analyst's initial over-escalation (+13.4 avg score shift) rather than correcting it. The 0% consensus
rate on payroll and near-zero rates on other FP traps confirm the auditor is nearly always REJECTing the
analyst's initial assessment and demanding escalation.

The FN trap performance offers a counterpoint: hierarchical achieves 100% on both Sleeper and Smurf (vs
77% and 86% for intrinsic). The independent auditor's aggressive escalation stance is exactly right for
hidden guilty clients but catastrophically wrong for false positive traps. The two failure modes are
structurally incompatible with a single escalation-biased auditor.

### Finding 2 [Intrinsic vs Context-Engineered]: Kayba injection has negligible net effect at gpt-4o-mini

Context-engineered barely improves on intrinsic (F1: 0.56 vs 0.54, 5 FNs vs 8, but 81 FPs vs 80). The
Kayba playbook, derived from 86 gpt-4o-mini training traces, does encode the right corrective direction —
payroll accuracy improves from 0% to 13%, structurer from 9% to 13%, and FN Sleeper from 77% to 91%.
But these marginal gains are swamped by a new problem: the context-engineered mode has the lowest
consensus rate (17%) and highest avg revisions (1.80), meaning the injected rules are triggering constant
REJECTs without producing correct assessments.

The likely mechanism: the Kayba rules are being applied indiscriminately to all cases rather than
selectively where they are relevant. The self-review prompt with rules increases the reviewer's critical
sensitivity, causing it to reject even correct assessments. At gpt-4o-mini, the model lacks the reasoning
precision to execute on Kayba's generalised principles selectively — it applies them as blanket rules.

This is a capability-interaction finding: Kayba's 28-skill playbook requires a model with sufficient
reasoning ability to apply each skill conditionally. At gpt-4o-mini, the rules become a blunt instrument.

### Finding 3 [Intrinsic vs LLM-Context]: LLM self-synthesis produces the largest improvement

LLM-Context achieves F1=0.66 — the best result among all four modes — compared to intrinsic's F1=0.54.
The improvement is driven by substantial FP reduction: 58 FPs vs 80 for intrinsic, and TN rises from 28
to 50. MAE improves from 34.2 to 25.2.

The per-group data reveals what the self-synthesised rules are doing: payroll accuracy improves from 0%
to 52% (avg score drops from 68.7 to 50.2), structurer from 9% to 35% (avg score 64.5→50.0), and charity
from 43% to 48%. These are the groups where gpt-4o-mini was most systematically wrong, and the rules —
synthesised from examples of those specific errors — directly target them.

However, LLM-Context still fails on high roller (17% accuracy, avg score 65.4), and FP performance
remains far from solved. The rules reduce but do not eliminate the systematic over-escalation bias. The
training traces capture the model's failure modes at n=86, but the 23-client-per-group FP traps in the
test set expose patterns the rules do not fully generalise across.

### Finding 4 [Context-Engineered vs LLM-Context]: LLM self-synthesis clearly outperforms Kayba at this capability level

LLM-Context F1 (0.66) substantially exceeds Context-Engineered F1 (0.56). The gap is visible across
every FP group: payroll 52% vs 13%, structurer 35% vs 13%, charity 48% vs 30%. LLM-Context produces 23
fewer false positives (58 vs 81).

Both artefacts were derived from the same 86 gpt-4o-mini training traces. The difference reflects rule
format and density: the LLM-synthesised rules are structured around specific error patterns — the exact
reasoning failures gpt-4o-mini made during training. Kayba's 28-skill playbook extracts generalised
principles ("prioritise qualitative context over quantitative flags") that are directionally correct but
require the model to apply them flexibly. At gpt-4o-mini's capability level, the case-specific corrective
language in the LLM rules is more actionable than Kayba's abstract principles.

The consensus rate comparison reinforces this: LLM-Context has 32% consensus (vs context-engineered's
17%), meaning the LLM-synthesised rules produce fewer spurious REJECTs while still producing correct
escalation decisions.

### Finding 5 [Cross-cutting]: FP traps are the defining failure mode at gpt-4o-mini

The dominant pattern across all four modes is systematic false positive failure on FP trap groups. All
92 FP-trap clients collectively generate between 58 and 84 false positives depending on mode. The three
worst groups — payroll, high roller, structurer — account for 69 of 108 innocent clients and are near-
total failures in intrinsic, hierarchical, and context-engineered modes.

The failure pattern is consistent: gpt-4o-mini anchors on quantitative red flags (high fan-out, high
volume, high avg amount) and fails to apply KB article context to rebut those flags. Intrinsic avg score
of 68.7 for payroll clients — legitimate businesses with known innocent explanations — reflects a model
that reads the qualifying evidence and then ignores it in its final score.

This is a qualitative reasoning failure, not an evidence retrieval failure: evidence coverage scores are
9.32 (the model reads the articles) but conclusion consistency is 6.76 (the conclusion does not follow
from the evidence cited). The gap between these two scores is diagnostic of anchoring bias.

### Finding 6 [Reasoning quality]: High evidence coverage with low conclusion consistency confirms anchoring

Evidence coverage (9.32–9.54 across modes) is high: gpt-4o-mini cites specific transaction metrics and
KB article content in its reasoning. Conclusion consistency (6.76–8.23) is substantially lower: the
final score often contradicts the agent's own cited evidence.

This gap is diagnostic. The model retrieves mitigating information but fails to apply it to update its
initial quantitative assessment — it writes reasoning that acknowledges the legitimate business explanation
and then issues a high risk score anyway. LLM-Context's improvement in conclusion consistency (7.87 vs
6.76 for intrinsic) confirms the self-synthesised rules are partially correcting this pattern.

Hierarchical's elevated conclusion consistency (8.23) is an artefact: the auditor rewrites reasoning to
justify its escalation decision, producing locally coherent chains built around the wrong conclusion.

---

## 5b. Combined Governance Modes: Hierarchical + Context Injection

Two additional modes stack context injection onto the hierarchical architecture — the auditor receives either the Kayba playbook (Hier+Ctx) or the LLM-synthesised rules (Hier+LLM) in its prompt. This creates a 2×3 design (architecture × rule source) and enables the previously-confounded comparisons listed above.

### Classification Performance

| Metric | Hierarchical | Hier+Ctx | Hier+LLM | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|
| **Accuracy** | 50.0% | 38.7% | 42.9% | 48.8% | **64.3%** |
| **F1** | 0.59 | 0.534 | 0.551 | 0.56 | **0.66** |
| True Positives | **60** | 59 | 59 | 55 | 58 |
| False Positives | 84 | **102** | 95 | 81 | **58** |
| True Negatives | 24 | **6** | 13 | 27 | **50** |
| False Negatives | **0** | 1 | 1 | 5 | 2 |
| MAE | 36.3 | **41.4** | 36.8 | 34.0 | **25.2** |
| In-Range % | 39.9% | 33.3% | 39.9% | 32.1% | **49.4%** |
| Consensus Rate | 28% | **0%** | 14% | 17% | 32% |
| Avg Revisions | 1.62 | **2.00** | 1.80 | **1.80** | 1.61 |
| Avg Score Shift | +13.4 | **+23.8** | +20.6 | +5.2 | +3.1 |

### Per-Group Classification Accuracy

| Group | n | Hierarchical | Hier+Ctx | Hier+LLM | Context-Eng | LLM-Context |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Control Guilty** | 16 | ✅ 100% | ✅ 100% | ✅ 100% | ⚠️ 94% | ✅ 100% |
| **Control Innocent** | 16 | ⚠️ 81% | ❌ 31% | ⚠️ 62% | ⚠️ 88% | ✅ 94% |
| **FP Trap: Charity** | 23 | ❌ 35% | ❌ 0% | ❌ 4% | ❌ 30% | ⚠️ 48% |
| **FP Trap: Payroll** | 23 | ❌ 9% | ❌ 0% | ❌ 0% | ❌ 13% | ⚠️ 52% |
| **FP Trap: High Roller** | 23 | ❌ 0% | ❌ 0% | ❌ 0% | ❌ 0% | ❌ 17% |
| **FP Trap: Structurer** | 23 | ❌ 4% | ❌ 4% | ❌ 9% | ❌ 13% | ❌ 35% |
| **FN Trap: Sleeper** | 22 | ✅ 100% | ✅ 95% | ✅ 100% | ✅ 91% | ✅ 100% |
| **FN Trap: Smurf** | 22 | ✅ 100% | ✅ 100% | ✅ 95% | ✅ 91% | ✅ 91% |

### What the Combined Modes Reveal

**Hier+Ctx is the worst configuration in the entire experiment.** 102 false positives, 0% consensus rate (every single case is rejected), and an average score shift of +23.8. The Kayba playbook, designed to increase critical scrutiny of risk escalations, hands the already over-aggressive gpt-4o-mini auditor additional ammunition to escalate. The two biases compound: the hierarchical auditor's baseline over-escalation tendency (+13.4 shift) is amplified by the playbook triggering even more aggressive intervention. Only 6 of 108 innocent clients are correctly cleared.

**Hier+LLM is partially moderated but still inferior.** The LLM-synthesised rules provide more targeted guidance than Kayba's general principles, which slightly attenuates the compounding effect: 95 FPs (vs 102), 14% consensus (vs 0%), and 13 correctly-cleared innocents (vs 6). The LLM rules, built from specific failure examples, are less likely to be applied as blanket escalation triggers. But the fundamental problem remains: the hierarchical auditor's escalation bias absorbs any downward corrective signal the rules provide.

**Decomposing the confounded comparisons:**
- *Hierarchical vs Hier+Ctx* (Kayba injection on hierarchical): −0.056 F1. Adding Kayba rules to the auditor actively hurts — it converts a marginally adequate auditor into a total false-positive machine.
- *Hierarchical vs Hier+LLM* (LLM rules on hierarchical): −0.039 F1. Same direction, smaller damage.
- *Context-Eng vs Hier+Ctx* (architecture change, Kayba fixed): −0.026 F1. Self-review with Kayba is marginally better than a separate auditor with Kayba.
- *LLM-Context vs Hier+LLM* (architecture change, LLM rules fixed): −0.109 F1. Self-review with LLM rules substantially outperforms a separate auditor with LLM rules. This is the largest architecture effect in the experiment — but it runs in the direction of favouring self-review.

The combined-mode results confirm that at gpt-4o-mini's capability level, governance interventions do not stack constructively. Each additional layer of escalation bias (hierarchical auditor, Kayba rules) compounds rather than balances the previous one. The intrinsic+LLM-Context combination, which works within a single context window and provides specific corrective rules, is the only configuration that materially improves the baseline.

---

## 6. Comparison with gpt-5.1 Results

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
   intrinsic alone outperforms gpt-4o-mini LLM-Context (the best gpt-4o-mini mode, F1=0.66) on F1.

2. **The error distribution inverts across models.** gpt-4o-mini systematically over-flags (80 FPs, 8 FNs
   in intrinsic). gpt-5.1 systematically under-flags on one specific pattern (2 FPs, 11 FNs in intrinsic
   — driven by FN Smurf at 59%). The capability jump resolves the FP anchoring bias but reveals a
   residual FN blind spot on the hardest buried-signal trap.

3. **Rule injection effects are capability-dependent.** At gpt-4o-mini, Kayba rules barely move the
   needle (F1: 0.54→0.56); at gpt-5.1, they produce a strong improvement (F1: 0.883→0.929). LLM-Context
   improves substantially at both capability levels (gpt-4o-mini: +0.12 F1; gpt-5.1: +0.117 F1), but
   for different reasons: at gpt-4o-mini, the rules correct systematic anchoring bias; at gpt-5.1, they
   address a narrow FN Smurf blind spot.

4. **Hierarchical architecture produces opposite failure modes at each model.** At gpt-4o-mini the
   auditor over-escalates (84 FPs, 0 FNs, +13.4 avg score shift). At gpt-5.1 it under-intervenes
   (3 FPs, 13 FNs, −0.6 avg score shift). Neither model achieves the idealised well-calibrated auditor.

5. **Context-engineered's low consensus rate is gpt-4o-mini specific.** At gpt-4o-mini: 17% consensus,
   1.80 revisions, 6.6 calls/case. At gpt-5.1: 100% consensus, 0.65 revisions, 4.3 calls/case. The
   Kayba rules act as an indiscriminate trigger at gpt-4o-mini but are applied selectively at gpt-5.1
   — a direct model-capability effect on rule execution.

---

## 7. Thesis Implications

| Comparison | Hypothesis | Result |
|---|---|---|
| Intrinsic vs Hierarchical | Governance architecture affects accuracy | **Marginally supported** — hierarchical F1 0.59 vs 0.54; but improvement is from perfect recall at severe FP cost, not genuine quality improvement |
| Intrinsic vs Hierarchical | Independent auditing prevents confirmation bias | **Not supported** — auditor escalates aggressively on FP traps, amplifying rather than correcting the analyst's FP bias |
| Intrinsic vs Context-Engineered | Kayba rule injection improves on intrinsic | **Not supported at this capability level** — F1 0.56 vs 0.54; rules trigger excessive REJECTs without producing correct outcomes; execution capability insufficient |
| Intrinsic vs LLM-Context | LLM self-reflection rules improve on intrinsic | **Supported** — F1 0.66 vs 0.54; 22 fewer FPs; targeted rules directly address the observed anchoring failure mode |
| Context-Eng vs LLM-Context | LLM self-synthesis outperforms Kayba extraction | **Strongly supported** — F1 0.66 vs 0.56; 23 fewer FPs; Kayba's generalised principles require higher execution capability than case-specific rules |

### Suggested framing for thesis write-up

The gpt-4o-mini results establish the **baseline condition** for the governance comparison:

**Contribution 1 — The FP anchoring failure mode:**
gpt-4o-mini's dominant failure is systematic false positive generation on FP trap groups. The model reads
legitimate KB evidence but fails to apply it to rebut its own quantitative risk flags — confirmed by the
evidence coverage / conclusion consistency gap (9.32 vs 6.76). This anchoring failure provides the ground
truth against which rule injection's effectiveness is evaluated.

**Contribution 2 — The capability-execution boundary for Kayba:**
Kayba's generalised skill playbook requires a model capable of applying principles conditionally. At
gpt-4o-mini, the playbook acts as an undifferentiated trigger (17% consensus, 1.80 revisions) without
producing correct outcomes. The rules are not wrong — they encode the right direction — but the model
cannot execute on them selectively. This establishes a capability-execution threshold that gpt-5.1 crosses.

**Contribution 3 — LLM-Context as the effective governance mechanism at lower capability:**
LLM-synthesised rules, structured around specific failure examples, are sufficiently concrete for
gpt-4o-mini to act on. They reduce FPs by 22 and improve F1 by 0.12, confirming that governance
effectiveness depends not only on rule quality but on whether the governed model can execute on the
form of rules provided.

---

## 7b. Run-to-Run Variance (Robustness Check)

Three independent runs (same model, same dataset, different LLM samples) quantify how stable the results are under sampling noise.

| Mode | Run 1 | Run 2 | Run 3 | Mean F1 | Std |
|---|:---:|:---:|:---:|:---:|:---:|
| **Intrinsic** | 0.542 | 0.523 | 0.537 | 0.534 | ±0.008 |
| **Hierarchical** | 0.588 | 0.566 | 0.581 | 0.578 | ±0.009 |
| **Context-Eng** | 0.561 | 0.578 | 0.592 | 0.577 | ±0.012 |
| **LLM-Context** | 0.659 | 0.635 | 0.646 | 0.647 | ±0.010 |

F1 standard deviation is ≤0.012 across all modes — roughly 1–2 percentage points. The **rank ordering is fully stable** across all three runs: LLM-Context > Hierarchical ≈ Context-Eng > Intrinsic. Run 1's LLM-Context result (F1=0.659) is the high-water mark; the mean across runs (0.647) remains the best mode by a clear margin. The main findings are not artefacts of a single lucky sample.

The FP count for LLM-Context ranges 58–69 across runs (mean 65.3), reflecting the mode's sensitivity to which specific borderline cases the LLM assigns near-threshold scores. This range does not affect the qualitative conclusion — LLM-Context consistently produces substantially fewer FPs than the other three modes (which average 83–87 FPs).

## 7c. Revision Depth Ablation

A separate ablation tests how MAX_REVISIONS (the cap on self-review loops) affects intrinsic-mode performance across depths 0–10. The key result: **depth 0 (no revision loop) is optimal** — F1=0.690 at depth 0 vs F1=0.561 at depth 2 (the main experiment baseline). Every additional revision loop degrades performance through score compression and escalation bias, confirming that the main experiment's intrinsic baseline is already penalised. Full results and methodology: **`RESULTS-revision-depth-gpt-4o-mini.md`**.

---

## 8. Output Files

| File | Contents |
|---|---|
| `results/test/gpt-4o-mini/run_1/summary.csv` | Wide-format raw scores for 168 clients × 4 modes |
| `results/test/gpt-4o-mini/run_1/evaluation.csv` | Per-client computed metrics (in_range, correct, score_shift, etc.) |
| `results/test/gpt-4o-mini/run_1/evaluation_{mode}.csv` | Per-mode artifact (logged to MLflow) |
| `results/test/gpt-4o-mini/run_1/{mode}/*.json` | Full AgentState for each client — forensics, news, reasoning, review |
| `external_agent_injection_gpt-4o-mini.txt` | Kayba's 28-skill context playbook (derived from 86 gpt-4o-mini train traces) |
| `llm_context_rules_gpt-4o-mini.txt` | Self-synthesised rules from 86 gpt-4o-mini training traces (3,743 chars) |
| `training_traces/*.md` | 86 annotated train traces fed to both Kayba and the LLM synthesiser |

To inspect a specific client's full reasoning chain:
```python
import json
state = json.load(open("results/test/gpt-4o-mini/run_1/intrinsic/C1941.json"))
print(state["analyst_output"]["reasoning"])
print(state["review_output"]["reasoning"])
```

To reproduce the evaluation:
```bash
LLM_MODEL=gpt-4o-mini python 02_run_experiment.py --dataset test --modes intrinsic hierarchical context_engineered llm_context --model gpt-4o-mini
python 03_evaluate.py --dataset test --model gpt-4o-mini
mlflow ui  # http://127.0.0.1:5000
```
