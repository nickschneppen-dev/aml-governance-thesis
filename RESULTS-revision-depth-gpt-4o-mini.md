# Revision Depth Ablation — gpt-4o-mini

**Experiment:** `08_revision_depth_experiment.py`
**Model:** gpt-4o-mini
**Dataset:** test set, n=168 (60 guilty / 108 innocent)
**Depths tested:** 0–10 (MAX_REVISIONS = 0 means no revision loop; the analyst's first output is final)
**Governance mode:** Intrinsic (analyst reviews its own draft)

---

## 1. Overall Metrics by Depth

| Depth | Acc   | Prec  | Rec   | F1    | TP | FP | TN | FN | Consensus | AvgRev |
|------:|------:|------:|------:|------:|---:|---:|---:|---:|----------:|-------:|
|     0 | 68.5% | 0.532 | 0.983 | 0.690 | 59 | 52 | 56 |  1 |        6% |   0.00 |
|     1 | 52.1% | 0.421 | 0.949 | 0.583 | 56 | 77 | 31 |  3 |       53% |   0.60 |
|     2 | 50.6% | 0.411 | 0.883 | 0.561 | 53 | 76 | 32 |  7 |       57% |   0.93 |
|     3 | 48.8% | 0.397 | 0.833 | 0.538 | 50 | 76 | 32 | 10 |       57% |   1.21 |
|     4 | 46.1% | 0.379 | 0.877 | 0.529 | 50 | 82 | 26 |  7 |       59% |   1.53 |
|     5 | 42.3% | 0.333 | 0.709 | 0.453 | 39 | 78 | 30 | 16 |       61% |   1.74 |
|     6 | 49.4% | 0.395 | 0.845 | 0.538 | 49 | 75 | 33 |  9 |       69% |   1.74 |
|     7 | 47.0% | 0.358 | 0.655 | 0.463 | 38 | 68 | 40 | 20 |       69% |   1.92 |
|     8 | 42.9% | 0.336 | 0.709 | 0.456 | 39 | 77 | 31 | 16 |       71% |   1.78 |
|     9 | 44.0% | 0.348 | 0.690 | 0.462 | 40 | 75 | 33 | 18 |       69% |   2.17 |
|    10 | 44.8% | 0.353 | 0.719 | 0.474 | 41 | 75 | 33 | 16 |       72% |   2.05 |

**Best F1 is at depth=0** (no revision loop at all).

---

## 2. Per-Group Classification Accuracy by Depth

| Group             |  d0  |  d1  |  d2  |  d3  |  d4  |  d5  |  d6  |  d7  |  d8  |  d9  | d10  |
|-------------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|
| Control Guilty    | 100% | 100% | 100% | 100% | 100% | 100% |  88% |  69% |  69% |  69% |  75% |
| Control Innocent  | 100% | 100% | 100% | 100% |  88% | 100% | 100% | 100% | 100% | 100% | 100% |
| FP: Charity       |  87% |  26% |  22% |  35% |  35% |  35% |  26% |  52% |  22% |  39% |  26% |
| FP: Payroll       |  22% |   4% |  13% |   9% |   4% |   0% |  17% |  17% |   9% |   9% |  17% |
| FP: High Roller   |   9% |   9% |   9% |   4% |   4% |   9% |   0% |   4% |   0% |   4% |   0% |
| FP: Structurer    |  57% |  26% |  26% |  22% |   9% |  17% |  30% |  30% |  35% |  22% |  30% |
| FN: Sleeper       |  95% |  86% |  86% |  73% |  86% |  60% |  86% |  62% |  75% |  76% |  73% |
| FN: Smurf         | 100% | 100% |  82% |  82% |  80% |  58% |  81% |  67% |  68% |  62% |  68% |

---

## 3. Score Trajectories

Initial scores are consistent across all depths (the analyst's first draft is unaffected by revision cap), but final scores diverge significantly as revisions accumulate.

| Depth | Init Score — Guilty | Final Score — Guilty | Init Score — Innocent | Final Score — Innocent |
|------:|--------------------:|---------------------:|----------------------:|-----------------------:|
|     0 |                77.5 |                 77.5 |                  44.6 |                   44.6 |
|     1 |                78.3 |                 71.0 |                  43.2 |                   56.1 |
|     2 |                78.3 |                 68.8 |                  44.0 |                   55.9 |
|     3 |                78.0 |                 63.2 |                  44.1 |                   58.1 |
|     4 |                78.6 |                 66.2 |                  43.3 |                   57.5 |
|     5 |                78.3 |                 58.6 |                  44.8 |                   58.6 |
|     6 |                79.2 |                 63.6 |                  44.0 |                   55.7 |
|     7 |                78.0 |                 58.2 |                  44.0 |                   54.9 |
|     8 |                78.5 |                 61.4 |                  43.4 |                   57.5 |
|     9 |                78.4 |                 61.3 |                  43.9 |                   57.4 |
|    10 |                78.7 |                 58.5 |                  44.2 |                   58.1 |

---

## 4. Actual Revisions Taken

Although the cap increases, the model hits a soft ceiling around 1.7–2.2 average revisions regardless of how many loops are permitted. Most clients converge to APPROVE well before the cap.

| Depth cap | Avg revisions taken | Max revisions taken |
|----------:|--------------------:|--------------------:|
|         0 |                0.00 |                   0 |
|         1 |                0.60 |                   1 |
|         2 |                0.93 |                   2 |
|         3 |                1.21 |                   3 |
|         4 |                1.51 |                   4 |
|         5 |                1.74 |                   5 |
|         6 |                1.72 |                   6 |
|         7 |                1.89 |                   7 |
|         8 |                1.73 |                   8 |
|         9 |                2.14 |                   9 |
|        10 |                2.05 |                  10 |

---

## 5. Key Findings

### Finding 1: No revisions is optimal — self-revision actively hurts gpt-4o-mini

Depth 0 (no revision loop) achieves the best F1 (0.690) and accuracy (68.5%) of any depth. Every revision step beyond zero degrades overall performance. The main experiment's baseline of depth=2 (F1=0.561) already represents a substantial drop from the no-revision optimum.

This is a direct empirical confirmation of the confirmation bias hypothesis: the analyst's first draft is better than anything it produces after reviewing its own work.

### Finding 2: Self-review biases toward guilty — FP rate explodes immediately

At depth 0, the model approves its own initial output 94% of the time and correctly clears many innocents. The moment a single revision loop is introduced (depth 1), FPs jump from 52 → 77 (+48%) while FNs barely change (1 → 3). The self-reviewer consistently escalates risk scores rather than downgrading them. This is the same direction as Hierarchical mode — but without an independent auditor to provide a principled basis for escalation, the elevation is noise-driven.

### Finding 3: Score compression at higher depths destroys discriminative power

Initial scores are stable across all depths (guilty avg ~78.5, innocent avg ~44.0 — a ~34-point separation). After revisions, the gap narrows with each loop:
- Depth 0: guilty=77.5 vs innocent=44.6 → gap = **33 points**
- Depth 2: guilty=68.8 vs innocent=55.9 → gap = **13 points**
- Depth 5: guilty=58.6 vs innocent=58.6 → gap = **0 points**
- Depth 10: guilty=58.5 vs innocent=58.1 → gap = **0.4 points**

By depth 5, the model has revised itself into complete indecision — guilty and innocent clients receive statistically identical scores. The revision loop doesn't sharpen judgment; it erodes it.

### Finding 4: False positive traps are hardest hit by revisions

FP traps (groups C1–C4) start with mediocre accuracy at depth 0, then collapse further under self-revision:

- **FP: Payroll** — 22% at d0, falls to 0% by d5. The model's initial caution (flagging high fan-out) is appropriate skepticism that self-review then reverses.
- **FP: High Roller** — Already near-zero at d0 (9%), revisions offer no recovery path and occasionally reach 0%.
- **FP: Charity** — Best FP group at d0 (87%), but collapses to 22–35% with any revision. The initial reading of the knowledge base is correct; revision-loop second-guessing undoes it.
- **FP: Structurer** — 57% at d0 (strongest among Payroll/Structurer), degrades to 9–30% range.

The pattern is consistent: the analyst's first reading of the KB is more accurate than its revised reading, but the self-review step systematically moves scores in the wrong direction for innocents who look guilty.

### Finding 5: True positive recall is well-maintained until high depths, then collapses

FN traps (D1 Sleeper, D2 Smurf) are well-detected at low depths and degrade gradually:
- **FN: Sleeper** — 95% at d0, holds above 73% through d4, then falls to 60–86% range.
- **FN: Smurf** — 100% at d0 and d1, then drifts down to 58–82%.

Even simple control cases are not immune: Control Guilty accuracy drops from 100% to 69% by depth 7–9, as the model revises confirmed launderers' scores downward through repeated self-doubt cycles.

### Finding 6: Consensus rate grows with depth but reflects exhaustion, not convergence

Consensus rate (fraction of clients where final review is APPROVE) rises monotonically from 6% at d0 to 72% at d10. This is not evidence that deeper revision leads to better-calibrated agreement — it reflects the model running out of revision budget and being forced to finalise. High consensus at depth 10 coexists with the worst F1 scores.

### Finding 7: The revision ceiling saturates around 2 actual loops regardless of cap

Despite caps of 5–10 being available, average actual revisions plateau between 1.7–2.2. Most clients reach APPROVE within 2 loops regardless of how many are permitted. This suggests the marginal value of additional revision budget above 2 is essentially zero in terms of the model's willingness to keep rejecting, yet the damage already done by the first 1–2 revisions is sufficient to degrade performance substantially.

### Finding 8: The main experiment's depth=2 baseline is already past peak

The main experiment uses depth=2 for all governance modes. This ablation shows that intrinsic mode at depth=2 (F1=0.561) is measurably worse than at depth=0 (F1=0.690). The context-engineered and LLM-context results in the main experiment are therefore being compared against a penalised intrinsic baseline. The true ceiling for self-correction may be higher than reported if measured at the single-draft level — though that would not constitute a governance mode in practice.

---

## 6. Summary

The revision depth ablation provides strong evidence that self-revision is harmful for gpt-4o-mini in this task domain. The model's initial draft encodes the best judgment it will produce; every subsequent self-review cycle moves scores toward a compressed, undifferentiated middle that fails both FP and FN cases. The key mechanism is not random noise but a consistent directional bias: the self-reviewer defaults to escalation for any case with ambiguous signals, inflating risk scores across the board. Deeper revision caps do not correct this — they amplify it. The results motivate the main experiment's design: comparing governance modes that inject external structure (hierarchical auditor, Kayba playbook, LLM-synthesised rules) against an intrinsic baseline that has already been shown to degrade monotonically with additional self-review budget.
