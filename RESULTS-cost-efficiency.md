# Cost Efficiency Analysis: Multi-Agent AML Governance

> **What this file answers:** How much does each governance mode actually cost — in real API tokens — and
> how efficiently does each model × mode combination convert dollars into correct AML classifications?

---

## 1. Setup

### Methodology

Token counts are **real**, not estimated. Every LLM call made during the experiment was traced through
Langfuse, which recorded `inputUsage` and `outputUsage` directly from the API response for each
GENERATION node. The 6.3 GB Langfuse observations export was streamed with `ijson` to extract all
65,262 GENERATION records (61,080 with real token usage), then each trace was matched to its
`(model, mode, client_id)` result via fingerprint matching against the local result JSONs.

**Coverage:** 3,015 of 3,024 expected test-set traces matched (99.7%).
**API model strings confirmed from Langfuse:** `gpt-4o-mini-2024-07-18`, `gpt-5.1-2025-11-13`,
`grok-4-0709`.

### Pricing Constants

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Source |
|---|---:|---:|---|
| `gpt-4o-mini-2024-07-18` | $0.150 | $0.600 | OpenAI published |
| `gpt-5.1-2025-11-13` | $1.25 | $10.00 | Confirmed |
| `grok-4-0709` | $2.00 | $6.00 | Confirmed |

### Dataset

168 test clients (60 guilty, 108 innocent) × 3 models × 6 governance modes = 3,024 traces.

---

## 2. Raw Data: Token Counts

### 2a. Mean Tokens per Case (Input / Output / Total)

| Mode | gpt-4o-mini | gpt-5.1 | grok-4 |
|---|:---:|:---:|:---:|
| **Intrinsic** | 10,528 / 1,404 / **11,932** | 6,763 / 3,128 / **9,891** | 6,522 / 2,344 / **8,866** |
| **Hierarchical** | 8,105 / 1,543 / **9,648** | 3,893 / 2,580 / **6,473** | 6,328 / 2,749 / **9,077** |
| **Context-Eng** | 28,908 / 1,636 / **30,545** | 35,908 / 4,847 / **40,755** | 30,357 / 4,002 / **34,359** |
| **LLM-Context** | 22,038 / 1,466 / **23,504** | 24,636 / 4,672 / **29,307** | 16,992 / 3,646 / **20,638** |
| **Hier+Ctx** | 16,080 / 1,811 / **17,891** | 18,775 / 4,627 / **23,402** | 13,385 / 3,645 / **17,031** |
| **Hier+LLM** | 10,513 / 1,641 / **12,155** | 10,722 / 3,629 / **14,351** | 11,242 / 3,954 / **15,196** |

### 2b. Mean Tokens: No-Revision Cases vs Revised Cases

"No-revision" = reviewer approved on the first pass; "revised" = at least one rejection and rewrite.

| Mode | Model | No-rev cases | No-rev tokens | Revised cases | Revised tokens | Multiplier |
|---|---|:---:|:---:|:---:|:---:|:---:|
| Intrinsic | gpt-4o-mini | 20 (12%) | 3,543 | 148 (88%) | 13,066 | 3.7× |
| Intrinsic | gpt-5.1 | 124 (74%) | 6,185 | 44 (26%) | 20,333 | 3.3× |
| Intrinsic | grok-4 | 142 (84%) | 7,124 | 27 (16%) | 18,032 | 2.5× |
| Hierarchical | gpt-4o-mini | 25 (15%) | 3,406 | 141 (85%) | 10,755 | 3.2× |
| Hierarchical | gpt-5.1 | 162 (96%) | 6,024 | 6 (4%) | 18,592 | 3.1× |
| Hierarchical | grok-4 | 138 (82%) | 7,177 | 30 (18%) | 17,817 | 2.5× |
| Context-Eng | gpt-4o-mini | 6 (4%) | 5,245 | 158 (96%) | 31,505 | 6.0× |
| Context-Eng | gpt-5.1 | 58 (35%) | 14,435 | 109 (65%) | 54,761 | 3.8× |
| Context-Eng | grok-4 | 95 (57%) | 11,725 | 73 (43%) | 63,815 | 5.4× |
| LLM-Context | gpt-4o-mini | 16 (10%) | 4,984 | 150 (90%) | 25,479 | 5.1× |
| LLM-Context | gpt-5.1 | 73 (43%) | 11,006 | 95 (57%) | 43,370 | 3.9× |
| LLM-Context | grok-4 | 102 (60%) | 9,171 | 67 (40%) | 38,094 | 4.2× |
| Hier+Ctx | gpt-5.1 | 91 (54%) | 14,586 | 77 (46%) | 33,820 | 2.3× |
| Hier+Ctx | grok-4 | 120 (71%) | 11,572 | 48 (29%) | 30,679 | 2.7× |
| Hier+LLM | gpt-4o-mini | 14 (8%) | 3,998 | 154 (92%) | 12,896 | 3.2× |
| Hier+LLM | gpt-5.1 | 135 (81%) | 11,099 | 32 (19%) | 28,070 | 2.5× |
| Hier+LLM | grok-4 | 102 (61%) | 9,148 | 65 (39%) | 24,687 | 2.7× |

---

## 3. Raw Data: Cost per Case

### 3a. Mean Cost per Case (USD)

| Mode | gpt-4o-mini | gpt-5.1 | grok-4 |
|---|:---:|:---:|:---:|
| **Intrinsic** | $0.0024 | $0.0397 | $0.0271 |
| **Hierarchical** | $0.0021 | $0.0307 | $0.0292 |
| **Context-Eng** | $0.0053 | $0.0934 | $0.0847 |
| **LLM-Context** | $0.0042 | $0.0775 | $0.0559 |
| **Hier+Ctx** | $0.0035 | $0.0697 | $0.0486 |
| **Hier+LLM** | $0.0026 | $0.0497 | $0.0462 |

### 3b. Total Cost to Classify All 168 Test Clients (USD)

| Mode | gpt-4o-mini | gpt-5.1 | grok-4 |
|---|:---:|:---:|:---:|
| **Intrinsic** | $0.41 | $6.67 | $4.55 |
| **Hierarchical** | $0.36 | $5.15 | $4.90 |
| **Context-Eng** | $0.89 | $15.68 | $14.23 |
| **LLM-Context** | $0.70 | $13.02 | $9.38 |
| **Hier+Ctx** | $0.59 | $11.72 | $8.17 |
| **Hier+LLM** | $0.43 | $8.35 | $7.76 |

### 3c. Relative Cost vs gpt-4o-mini Intrinsic (Cheapest Baseline)

gpt-4o-mini intrinsic ($0.0024/case) = 1×.

| Mode | gpt-5.1 relative | grok-4 relative |
|---|:---:|:---:|
| Intrinsic | 17× | 11× |
| Hierarchical | 13× | 12× |
| Context-Eng | 39× | 35× |
| LLM-Context | 32× | 23× |
| Hier+Ctx | 29× | 20× |
| Hier+LLM | 21× | 19× |

---

## 4. Raw Data: Classification Performance Alongside Cost

### 4a. F1, Accuracy, and Cost per Case — Full Grid

| Model | Mode | n | TP | FP | TN | FN | F1 | Accuracy | Cost/case |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| gpt-4o-mini | Intrinsic | 168 | 51 | 80 | 28 | 9 | 0.534 | 47.0% | $0.0024 |
| gpt-4o-mini | Hierarchical | 166 | 57 | 84 | 24 | 1 | 0.573 | 48.8% | $0.0021 |
| gpt-4o-mini | Context-Eng | 164 | 52 | 78 | 28 | 6 | 0.553 | 48.8% | $0.0053 |
| gpt-4o-mini | LLM-Context | 166 | 56 | 57 | 51 | 2 | 0.655 | 64.5% | $0.0042 |
| gpt-4o-mini | Hier+Ctx | 168 | 59 | 102 | 6 | 1 | 0.534 | 38.7% | $0.0035 |
| gpt-4o-mini | Hier+LLM | 168 | 59 | 95 | 13 | 1 | 0.551 | 42.9% | $0.0026 |
| gpt-5.1 | Intrinsic | 168 | 49 | 2 | 106 | 11 | 0.883 | 92.3% | $0.0397 |
| gpt-5.1 | Hierarchical | 168 | 47 | 3 | 105 | 13 | 0.855 | 90.5% | $0.0307 |
| gpt-5.1 | Context-Eng | 167 | 52 | 0 | 107 | 8 | 0.929 | 95.2% | $0.0934 |
| gpt-5.1 | LLM-Context | 168 | 60 | 0 | 108 | 0 | **1.000** | **100.0%** | $0.0775 |
| gpt-5.1 | Hier+Ctx | 168 | 50 | 0 | 108 | 10 | 0.909 | 94.0% | $0.0697 |
| gpt-5.1 | Hier+LLM | 167 | 57 | 1 | 107 | 2 | 0.974 | 97.6% | $0.0497 |
| grok-4 | Intrinsic | 169 | 59 | 8 | 100 | 2 | 0.922 | 94.1% | $0.0271 |
| grok-4 | Hierarchical | 168 | 56 | 10 | 98 | 4 | 0.889 | 91.7% | $0.0292 |
| grok-4 | Context-Eng | 168 | 55 | 3 | 105 | 5 | 0.932 | 95.2% | $0.0847 |
| grok-4 | LLM-Context | 169 | 61 | 27 | 81 | 0 | 0.819 | 83.9% | $0.0559 |
| grok-4 | Hier+Ctx | 168 | 54 | 3 | 105 | 6 | 0.923 | 94.6% | $0.0486 |
| grok-4 | Hier+LLM | 167 | 60 | 23 | 84 | 0 | 0.839 | 86.2% | $0.0462 |

### 4b. Cost per Correctly Identified Launderer (Cost / TP)

| Mode | gpt-4o-mini | gpt-5.1 | grok-4 |
|---|:---:|:---:|:---:|
| **Intrinsic** | $0.0080 | $0.1362 | $0.0772 |
| **Hierarchical** | $0.0062 | $0.1096 | $0.0875 |
| **Context-Eng** | $0.0168 | $0.3016 | $0.2588 |
| **LLM-Context** | $0.0124 | $0.2170 | $0.1538 |
| **Hier+Ctx** | $0.0100 | $0.2343 | $0.1513 |
| **Hier+LLM** | $0.0073 | $0.1465 | $0.1294 |

### 4c. Cost per Correct Decision (Cost / (TP + TN))

| Mode | gpt-4o-mini | gpt-5.1 | grok-4 |
|---|:---:|:---:|:---:|
| **Intrinsic** | $0.0051 | $0.0431 | $0.0286 |
| **Hierarchical** | $0.0044 | $0.0339 | $0.0318 |
| **Context-Eng** | $0.0109 | $0.0986 | $0.0890 |
| **LLM-Context** | $0.0065 | $0.0775 | $0.0661 |
| **Hier+Ctx** | $0.0090 | $0.0741 | $0.0514 |
| **Hier+LLM** | $0.0060 | $0.0509 | $0.0539 |

### 4d. F1 per Dollar × 1000 (Higher = More Cost-Efficient)

| Mode | gpt-4o-mini | gpt-5.1 | grok-4 |
|---|:---:|:---:|:---:|
| **Intrinsic** | 0.222 | 0.022 | **0.034** |
| **Hierarchical** | **0.273** | **0.028** | 0.030 |
| **Context-Eng** | 0.104 | 0.010 | 0.011 |
| **LLM-Context** | 0.156 | 0.013 | 0.015 |
| **Hier+Ctx** | 0.153 | 0.013 | 0.019 |
| **Hier+LLM** | 0.212 | 0.020 | 0.018 |

---

## 5. Raw Data: Revision Overhead

Percentage of each mode's total tokens that come from revision passes rather than the first-pass
analyst + initial review:

| Mode | gpt-4o-mini | gpt-5.1 | grok-4 |
|---|:---:|:---:|:---:|
| **Intrinsic** | 70.3% | 37.5% | 19.7% |
| **Hierarchical** | 64.7% | 6.9% | 20.9% |
| **Context-Eng** | 82.8% | 64.6% | 65.9% |
| **LLM-Context** | 78.8% | 62.4% | 55.6% |
| **Hier+Ctx** | — | 37.7% | 32.1% |
| **Hier+LLM** | 67.1% | 22.7% | 39.8% |

> Note: gpt-4o-mini Hier+Ctx shows no-revision cases as 0 (all 168 traces got at least one revision),
> so overhead is undefined (full column is revision cost). This reflects gpt-4o-mini's extremely
> aggressive combined-mode rejection behaviour.

---

## 6. Interpretation: Token Composition

### 6a. Output tokens reveal model verbosity — and explain the gpt-4o-mini vs capable-model cost gap

The input token difference across models is moderate (for the same mode, gpt-4o-mini and gpt-5.1
receive similar prompts). The **output token gap is the larger structural difference**:

| Model | Intrinsic output | Context-Eng output | Ratio |
|---|:---:|:---:|:---:|
| gpt-4o-mini | 1,404 | 1,636 | 1.2× |
| gpt-5.1 | 3,128 | 4,847 | 1.5× |
| grok-4 | 2,344 | 4,002 | 1.7× |

gpt-5.1 and grok-4 write reasoning that is 2–3× longer than gpt-4o-mini's. When both the analyst
and reviewer produce verbose outputs, revision passes compound this: each revision regenerates the
full analyst + reviewer reasoning at full length. With gpt-5.1 Context-Eng, revised cases average
54,761 tokens — nearly four times the no-revision baseline of 14,435. Longer, better reasoning is
not free.

### 6b. The Kayba playbook injection cost (Context-Eng premium)

The input token excess for Context-Eng vs Intrinsic isolates the playbook injection cost:

| Model | Intrinsic input | Context-Eng input | Playbook overhead | Overhead cost/case |
|---|:---:|:---:|:---:|:---:|
| gpt-4o-mini | 10,528 | 28,908 | +18,380 tokens | +$0.0028 |
| gpt-5.1 | 6,763 | 35,908 | +29,145 tokens | +$0.0364 |
| grok-4 | 6,522 | 30,357 | +23,835 tokens | +$0.0477 |

The Kayba playbook costs roughly $0.04–$0.05 per case to inject for capable models — even before
any revision overhead. This is the floor cost for Context-Eng regardless of classification outcome.
For gpt-5.1, that $0.04/case injection buys a meaningful performance gain (F1: 0.883 → 0.929);
for grok-4, it buys marginally less (F1: 0.922 → 0.932), making the return-on-injection
substantially lower.

### 6c. Hierarchical architecture as a context-window cost reduction

The hierarchical auditor receives a fresh context window — it does not carry the analyst's full
accumulated reasoning chain. This makes it naturally cheaper to run per call. The difference is
visible in no-revision input tokens:

| No-revision input | gpt-4o-mini | gpt-5.1 | grok-4 |
|---|:---:|:---:|:---:|
| Intrinsic | 3,543 | 6,185 | 7,124 |
| Hierarchical | 3,406 | 6,024 | 7,177 |

At this level they are nearly identical (both receive the same structured summary). The cost
advantage of Hierarchical emerges primarily from its lower rejection rate — not from a fundamental
per-call token reduction. Since capable-model auditors almost never reject (gpt-5.1: 4% rejection,
grok-4: 18% rejection), they avoid most revision overhead, making Hierarchical a cheaper capable-
model path despite each call being structurally similar in cost to Intrinsic.

### 6d. Hier+Ctx vs Context-Eng: the fresh-context playbook advantage

Injecting the Kayba playbook into a fresh hierarchical context window costs far less than injecting
it into an accumulated self-review context:

| Playbook overhead | gpt-4o-mini | gpt-5.1 | grok-4 |
|---|:---:|:---:|:---:|
| Context-Eng (accumulated) | +18,380 tokens | +29,145 tokens | +23,835 tokens |
| Hier+Ctx (fresh) | +7,975 tokens | +14,882 tokens | +6,208 tokens |
| Reduction via fresh context | 57% fewer | 49% fewer | 74% fewer |

When the playbook is injected into a hierarchical auditor's fresh context, it does not sit on top
of the analyst's entire reasoning history — only the structured summary. This makes Hier+Ctx
substantially cheaper than Context-Eng despite offering equivalent rule injection:

| | gpt-5.1 cost | gpt-5.1 F1 | grok-4 cost | grok-4 F1 |
|---|:---:|:---:|:---:|:---:|
| Context-Eng | $0.0934 | 0.929 | $0.0847 | 0.932 |
| **Hier+Ctx** | **$0.0697** | 0.909 | **$0.0486** | 0.923 |
| Saving | 25% cheaper | −0.020 F1 | 43% cheaper | −0.009 F1 |

For grok-4, paying 43% less for a loss of less than 1 F1 point (0.932 → 0.923) makes Hier+Ctx
the stronger cost-performance choice. For gpt-5.1, the 25% saving comes at a 2-point F1 loss,
which may or may not be acceptable depending on whether you require zero false positives.

### 6e. LLM-Context is cheaper than Context-Eng because the rules are shorter

The LLM-synthesised rules are shorter documents than the Kayba playbook, producing lower injection
overhead:

| Input token overhead vs Intrinsic | gpt-4o-mini | gpt-5.1 | grok-4 |
|---|:---:|:---:|:---:|
| Context-Eng (Kayba playbook) | +18,380 | +29,145 | +23,835 |
| LLM-Context (LLM rules) | +11,510 | +17,873 | +10,470 |
| LLM rules are shorter by | 37% | 39% | 56% |

This makes LLM-Context meaningfully cheaper per case than Context-Eng. The practical consequence
is that gpt-5.1 LLM-Context (the best-performing mode, F1=1.000) is also $0.0159/case cheaper
than gpt-5.1 Context-Eng (F1=0.929). You pay less and get better performance — the LLM-
synthesised rules are both shorter and more effective at gpt-5.1's capability level.

---

## 7. Interpretation: Revision Overhead

### 7a. gpt-4o-mini's revision loop is a cost sinkhole

For gpt-4o-mini, the majority of tokens — between 65% and 83% depending on mode — come from
revision passes rather than the first analyst + review cycle. This is not a sign of an effective
governance mechanism; it is a sign of a broken one.

The mechanism: gpt-4o-mini's reviewer (in all self-review modes) frequently issues REJECT
decisions on FP trap cases, triggering revision passes. But the revisions rarely produce correct
outcomes — accuracy across modes is 38–65%, meaning most of the revision spending produces
**still-wrong answers**. The 82.8% revision overhead for Context-Eng is the worst case: the Kayba
rules act as a near-indiscriminate rejection trigger (96% of cases get revised), and almost none of
those revisions fix the underlying classification error.

Concretely: of the $0.0053 gpt-4o-mini Context-Eng spends per case, approximately $0.0044 (83%)
is consumed by revision cycles that correct fewer than 5% of cases. The effective spend per correct
outcome improvement is extremely poor.

Contrast with **gpt-5.1 Hierarchical**: 96% of cases need no revision (6.9% revision overhead).
The auditor reviews once and almost always approves. Total cost: $0.0307/case. This is one of the
cheapest capable-model paths, though the auditor's passivity means it misses 13 FNs.

### 7b. Revision multiplier: cost of a revised case vs a first-pass approval

When a case is revised, the cost multiplies dramatically because each additional call receives the
full accumulated context — prior reasoning, reviewer critique, and draft revision — appended to the
prompt. The multiplier grows with the length of that accumulation:

| Model + Mode | First-pass cost | Revised case cost | Multiplier |
|---|:---:|:---:|:---:|
| gpt-4o-mini Intrinsic | $0.0008 | $0.0026 | 3.3× |
| gpt-4o-mini Context-Eng | $0.0011 | $0.0055 | 5.1× |
| gpt-5.1 Intrinsic | $0.0291 | $0.0697 | 2.4× |
| gpt-5.1 Context-Eng | $0.0415 | $0.1210 | 2.9× |
| grok-4 Intrinsic | $0.0222 | $0.0528 | 2.4× |
| grok-4 Context-Eng | $0.0331 | $0.1520 | 4.6× |

grok-4 Context-Eng is the extreme case: a revised client costs **$0.1520** — 4.6× the $0.0331
base case cost, and nearly 7× the grok-4 Intrinsic first-pass cost. The Kayba playbook sits in the
growing context window across every revision cycle, compounding its token overhead with each pass.

### 7c. The revision depth ablation confirms this: fewer revisions is better and cheaper

The separate revision depth ablation (`RESULTS-revision-depth-gpt-4o-mini.md`) found that
**depth 0 (no revision loop) produces higher F1 than depth 2** for gpt-4o-mini intrinsic
(F1=0.690 vs F1=0.561). This aligns precisely with the token data: first-pass cases use only
3,543 tokens and cost $0.0008, while the average intrinsic case uses 11,932 tokens ($0.0024)
due to revision overhead. The revision loop is not only ineffective at gpt-4o-mini — it is the
primary cost driver, and removing it would simultaneously reduce cost by 67% and improve accuracy.

---

## 8. Interpretation: Cross-Model Cost Efficiency

### 8a. gpt-4o-mini's paradox: cheapest per case, worst return on spend

gpt-4o-mini is 11–39× cheaper per case than capable models. But its accuracy is so low that most
of the spend goes to producing wrong answers:

| Model + Mode | Cost for 168 clients | Correct decisions | Cost per correct decision |
|---|:---:|:---:|:---:|
| gpt-4o-mini Hierarchical | $0.36 | 81 | $0.0044 |
| gpt-4o-mini LLM-Context | $0.70 | 107 | $0.0065 |
| grok-4 Intrinsic | $4.55 | 159 | $0.0286 |
| gpt-5.1 Hierarchical | $5.15 | 152 | $0.0339 |
| gpt-5.1 Intrinsic | $6.67 | 155 | $0.0431 |
| gpt-5.1 Hier+LLM | $8.35 | 164 | **$0.0509** |
| gpt-5.1 LLM-Context | $13.02 | 168 | $0.0775 |
| grok-4 Context-Eng | $14.23 | 160 | $0.0890 |

gpt-4o-mini Hierarchical costs $0.0044 per correct decision, appearing extremely efficient. But
this obscures that 87 of those decisions are wrong — it correctly classifies 81/168 clients, barely
better than chance. grok-4 Intrinsic costs $0.0286 per correct decision and gets 159/168 right.
The apparent cost efficiency of gpt-4o-mini dissolves once the error rate is factored in.

### 8b. The cost-performance frontier

Plotting F1 against cost per case reveals which combinations sit on the Pareto frontier (no other
point is both cheaper and better):

| Model + Mode | Cost/case | F1 | On frontier? | Notes |
|---|:---:|:---:|:---:|---|
| gpt-4o-mini LLM-Context | $0.0042 | 0.655 | ✅ | Best F1 in this price range |
| grok-4 Intrinsic | $0.0271 | 0.922 | ✅ | **Cheapest capable-model option** |
| grok-4 Hier+Ctx | $0.0486 | 0.923 | ✅ | Marginally higher F1 at 79% cost premium over grok-4 Intrinsic |
| gpt-5.1 Hier+LLM | $0.0497 | 0.974 | ✅ | Best F1 under $0.08/case |
| gpt-5.1 Hier+Ctx | $0.0697 | 0.909 | ❌ | Dominated by gpt-5.1 Hier+LLM |
| gpt-5.1 LLM-Context | $0.0775 | 1.000 | ✅ | Perfect F1 — efficiency ceiling |
| gpt-5.1 Hierarchical | $0.0307 | 0.855 | ❌ | Dominated by grok-4 Intrinsic (cheaper, higher F1) |
| gpt-5.1 Intrinsic | $0.0397 | 0.883 | ❌ | Dominated by grok-4 Intrinsic (cheaper, higher F1) |
| grok-4 Context-Eng | $0.0847 | 0.932 | ❌ | Dominated by gpt-5.1 Hier+LLM |

The key dominance relationships:
- **grok-4 Intrinsic ($0.0271, F1=0.922)** is the cheapest capable-model entry point on the
  frontier. With output tokens repriced at $6/1M (vs the previous estimate of $15/1M), grok-4's
  low revision rate (16% of cases revised) keeps its mean cost below all gpt-5.1 modes. Critically,
  it dominates both gpt-5.1 Hierarchical and gpt-5.1 Intrinsic — it is cheaper than both and has
  higher F1 than both.
- **gpt-5.1 Hier+LLM ($0.0497, F1=0.974)** is the standout: near-perfect classification at
  moderate cost. LLM-synthesised rules on a fresh hierarchical context produce 57 TPs with only
  1 FP and 2 FNs — and the short LLM rules keep the injection overhead low.
- **gpt-5.1 LLM-Context ($0.0775, F1=1.000)** is the efficiency ceiling: perfect classification,
  but at 56% more than Hier+LLM. The additional 3 TPs recovered (57→60) and the 1 FP eliminated
  costs $4.67 extra for the full 168-client set.
- **grok-4 Hier+Ctx ($0.0486, F1=0.923)** is technically on the frontier but practically
  unattractive: it costs 79% more than grok-4 Intrinsic for a 0.001 F1 gain. Its only use case
  is if you want Kayba-style rule injection on grok-4 and care about the slight edge over bare
  intrinsic performance.
- **All gpt-5.1 modes except Hier+LLM and LLM-Context fall off the frontier**: the revised
  grok-4 pricing makes grok-4 Intrinsic cheaper and better than gpt-5.1 Hierarchical and
  gpt-5.1 Intrinsic outright.

### 8c. The cross-model capability jump vs the cost jump

A common framing: is paying more for a capable model "worth it"? The token data makes this concrete:

- gpt-4o-mini Intrinsic: $0.0024/case, F1=0.534 → $0.41 total, 79 correct decisions
- gpt-5.1 Intrinsic: $0.0397/case, F1=0.883 → $6.67 total, 155 correct decisions
- **grok-4 Intrinsic: $0.0271/case, F1=0.922 → $4.55 total, 159 correct decisions**

At the **same total budget** ($6.67), you can run gpt-5.1 Intrinsic on all 168 clients OR
gpt-4o-mini Intrinsic on 2,779 clients. But grok-4 Intrinsic runs all 168 clients for only $4.55
with even higher F1. The F1 gain (+0.349 over gpt-4o-mini) from switching to gpt-5.1 costs
$0.0373/case additional; grok-4 buys +0.388 F1 for only $0.0247/case additional.

The trade-off for gpt-4o-mini LLM-Context (best gpt-4o-mini mode, F1=0.655) vs grok-4 Intrinsic
(cheapest capable mode, F1=0.922): paying $0.0271 vs $0.0042 — 6.5× more — buys +0.267 F1 and
52 more correct decisions. For an AML system where each missed launderer carries regulatory and
financial risk, this gap is almost certainly worth closing.

---

## 9. Interpretation: Practical Deployment Implications

### 9a. The Kayba playbook injection cost at capable-model pricing

Context-Eng adds $0.0364/case in gpt-5.1 input costs just for the playbook injection — before
any revision overhead. Over 168 clients, that is $6.12 of the $15.68 total Context-Eng spend
that goes purely to carrying the playbook text. At scale (e.g., 10,000 monthly case reviews),
Context-Eng would cost approximately $934 per month vs $397 for Intrinsic — a $537/month
premium, of which $364 is attributable to the playbook injection alone.

Whether that premium is justified depends on the capability level. At gpt-5.1, Context-Eng buys
F1: 0.883 → 0.929 (2 FPs eliminated, 3 more TPs recovered). At grok-4, it buys F1: 0.922 → 0.932
(5 fewer FPs, 4 fewer TPs). The injection is buying increasingly small gains as base model
capability increases.

**The efficient alternative**: Hier+Ctx injects the same playbook into a fresh hierarchical
auditor context, achieving nearly identical F1 at 25% (gpt-5.1) or 43% (grok-4) lower cost.
For any deployment that wants Kayba-style rule injection, Hier+Ctx is strictly preferable to
Context-Eng on cost grounds at gpt-5.1 and grok-4 capability levels.

### 9b. gpt-5.1 Hier+LLM is the operational sweet spot

Based on the combined cost-performance picture:

| Property | gpt-5.1 Hier+LLM |
|---|---|
| F1 | 0.974 |
| False positives | 1 |
| False negatives | 2 |
| Cost per case | $0.0497 |
| Cost for 168 clients | $8.35 |
| Revision overhead | 22.7% |
| Average calls per case | ~3.6 |

It achieves near-perfect classification (missing only 2 launderers and flagging 1 innocent),
costs well under the LLM-Context ceiling, and carries only 22.7% revision overhead (vs 62–83%
for the self-review modes with rules). The LLM-synthesised rules are short enough that the
injection cost is moderate, and the fresh hierarchical context prevents playbook accumulation
across revision cycles.

If the target is instead **minimising cost while retaining capable-model accuracy**, grok-4
Intrinsic ($0.0271, F1=0.922) is the better choice — 46% cheaper than gpt-5.1 Hier+LLM with
only a 0.052 F1 gap. The right choice depends on tolerance for the 2 missed launderers and
1 false positive that gpt-5.1 Hier+LLM also carries.

If the requirement is **zero false negatives** (never miss a launderer), the only options are
gpt-5.1 LLM-Context or grok-4 LLM-Context (both hit 0 FNs) — at $9–13 for 168 clients.
gpt-5.1 Hier+LLM misses 2 clients at roughly half to two-thirds the cost.

### 9c. gpt-4o-mini is unsuitable for production AML classification at any governance setting

The combination of low accuracy (38–65% depending on mode) and paradoxically high revision
overhead (65–83% of tokens going to ineffective revision passes) means that gpt-4o-mini fails
on both performance and cost-efficiency once accuracy is properly weighted. The apparent
"cheapness" ($0.36–$0.89 for 168 clients) is illusory: you are paying to produce mostly wrong
answers at high volume.

The revision depth ablation result adds additional evidence: the gpt-4o-mini governance loop
is actively harmful (depth 0 F1=0.690 vs depth 2 F1=0.561). Deploying gpt-4o-mini with a
revision loop is worse than not having one — and costs more.

### 9d. Context-Eng on grok-4 is the most expensive failure mode

grok-4 Context-Eng: $0.0847/case, F1=0.932. 73 of 168 cases (43%) get at least one revision,
and revised cases cost $0.1520 each. The Kayba playbook accumulates in the growing revision
context, amplifying the per-revision cost. grok-4's intrinsic performance is already 0.922 —
the 0.010 F1 gain from Context-Eng costs $0.0847 vs $0.0271, a 3.1× cost increase for a
fractional gain. This is the worst cost-per-F1-point trade in the experiment.

---

## 10. Pricing Sensitivity

All absolute cost figures depend on the pricing constants in `10_cost_analysis.py`. The pricing
used in this document is confirmed ($1.25/$10.00 for gpt-5.1; $2.00/$6.00 for grok-4).

### Impact of pricing on key conclusions

| Conclusion | Sensitivity |
|---|---|
| gpt-4o-mini is cheapest per case | **Robust** — would need gpt-5.1 or grok-4 to be 15× cheaper than current to change |
| gpt-5.1 LLM-Context is on the Pareto frontier | **Robust** — driven by F1=1.000 regardless of absolute pricing |
| gpt-5.1 Hier+LLM ($0.0497) is cheaper than Context-Eng ($0.0934) | **Robust** — relative ordering holds across 2× pricing variation |
| grok-4 Intrinsic is on the Pareto frontier | **Sensitive to grok-4 output pricing** — at $6/1M grok-4 output, grok-4 Intrinsic dominates gpt-5.1 Intrinsic; at $15/1M (previous estimate) it did not |
| Context-Eng revision cases are more expensive than LLM-Context revision cases | **Robust** — driven by playbook token counts (measurable), not pricing |

To re-run with corrected pricing:
```bash
# Edit PRICING dict at top of script, then:
python 10_cost_analysis.py --skip-stream
```

---

## 11. Summary

| Finding | Key number |
|---|---|
| Cheapest mode overall | gpt-4o-mini Hierarchical: $0.0021/case |
| Cheapest capable-model mode | grok-4 Intrinsic: $0.0271/case |
| Best F1 at any cost | gpt-5.1 LLM-Context: F1=1.000 at $0.0775/case |
| Best cost-performance balance | gpt-5.1 Hier+LLM: F1=0.974 at $0.0497/case |
| Cheapest alternative with high accuracy | grok-4 Intrinsic: F1=0.922 at $0.0271/case |
| Worst cost-performance trade | grok-4 Context-Eng: F1=0.932 at $0.0847/case (3.1× cost for 0.010 F1 gain over intrinsic) |
| Token overhead from Kayba playbook | +18–29K input tokens per case; $0.04–$0.05/case for capable models |
| Max revision multiplier | grok-4 Context-Eng: revised cases cost 4.6× base |
| gpt-4o-mini revision overhead | 65–83% of total tokens from revision passes |
| gpt-5.1 hierarchical revision overhead | 6.9% — almost never revises |
| Real vs estimated cost proxy | Estimated LLM-call proxy (`3 + 2×revisions`) undercounts Context-Eng cost by 3–5× because it misses the playbook injection tokens |

---

## 12. Output Files

| File | Contents |
|---|---|
| `10_cost_analysis.py` | Analysis script; streaming + matching + pricing |
| `.token_index_cache.pkl` | Cached token index from 6.3 GB stream (speeds up re-runs) |
| `results/cost_analysis.csv` | Per-trace matched data: model, mode, client_id, tokens, cost, correct |
| `1774563890090-lf-observations-export-*.json` | Source: 6.3 GB Langfuse observations (65K GENERATION records) |
| `1774563119788-lf-traces-export-*.csv` | Source: 14,206 Langfuse traces |

To re-run with updated pricing (uses cache — instant):
```bash
python 10_cost_analysis.py --skip-stream
```

To re-run from scratch (re-streams 6.3 GB file — ~5–10 minutes):
```bash
python 10_cost_analysis.py --save-cache
```
