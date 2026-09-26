# Perceptual-degradation retained-design robustness - 2026-08-14

**Status:** deterministic score-blind sensitivity complete. Bounded issued
reserve can recover the frozen planning gates under every modelled MCAR cell,
but it cannot recover missing truth-bearing source groups. No retention
mechanism, reserve, listener count, exclusion rule, operational design,
recruitment, collection, audio, response, score, or public verdict is selected
or authorized.

## Question and method

The prior missingness audit proved that v3's issued-schedule balance does not
survive arbitrary post-assignment loss. This frontier asks a narrower next
question: if the frozen 120-source symbolic design issued additional eligible
session slots, how much reserve would be needed for at least 244 of 256
deterministic replays to retain all three planning gates?

The gates are:

1. audibility-equivalence, audible-alternative and direct material-severity
   planning power remain at least 0.80 under the frozen variance model;
2. every one of the 120 planned source groups retains at least eight judgments
   in both methods; and
3. every symbolic trial's candidate-position bipartite graph remains connected,
   so an additive candidate-versus-position contrast is not rank-confounded.

The replay covers four workload options, five issued-reserve multipliers,
three retention rates, whole-session and independent-trial hash masks, and 256
replicates: 30,720 retained designs. Sixty additional deterministic designs
drop 6, 12, or 24 complete source groups. No response value is generated or
read.

Planning standard errors use the frozen random-effect variances, the realized
synthetic response count, and Kish effective listener and source counts. This
is an analytic sensitivity consistent with the earlier planning model. It is
not a fitted hierarchical-power simulation, an empirical missingness estimate,
or listening evidence.

## Minimum reserve sensitivity

The table reports the smallest issued-reserve multiplier that meets the joint
244/256 gate. Session and trial entries are separate because whole-session loss
changes listener support while trial loss can erode individual-source support.

| Workload | 85% session / trial | 90% session / trial | 95% session / trial |
| --- | ---: | ---: | ---: |
| 3 subtle + 3 MUSHRA | 1.2 / 1.1 | 1.1 / 1.1 | 1.0 / 1.0 |
| 5 subtle + 5 MUSHRA | 1.2 / 1.1 | 1.1 / 1.1 | 1.0 / 1.0 |
| 8 subtle + 6 MUSHRA | 1.2 / 1.1 | 1.1 / 1.1 | 1.0 / 1.0 |
| 15 subtle + 6 MUSHRA | 1.3 / 1.4 | 1.2 / 1.2 | 1.1 / 1.1 |

At the existing 90% planning sensitivity, none of the raw minimum prefixes
reaches the 244/256 joint gate. The first three options require a 10% issued
reserve. The compact 15 + 6 option requires 20% because the six-trial MUSHRA
cap leaves less per-source support despite its lower listener-slot count.

At the harsher 85% sensitivity, satisfying both session and trial masks would
produce the following planning workload. Counts are per aggregate condition
stratum, device class and partition; the four-partition column is not a count
of unknown condition strata.

| Workload | Joint reserve | Eligible slots | Enrolled slots | Four partitions |
| --- | ---: | ---: | ---: | ---: |
| 3 + 3 | 1.2 | 918 | 1,422 | 5,688 |
| 5 + 5 | 1.2 | 596 | 923 | 3,692 |
| 8 + 6 | 1.2 | 414 | 641 | 2,564 |
| 15 + 6 | 1.4 | 318 | 493 | 1,972 |

The smaller listener count for 15 + 6 is not a recommendation. Session timing,
fatigue, the number of condition strata, recruitment feasibility, and the
actual missingness mechanism remain unknown. Candidate-position connectivity
was not the limiting gate at the minimum passing reserves; equivalence power
and, for 15 + 6, fixed-source support were limiting. This does not restore the
strict range-at-most-one balance invariant in the retained observations.

## Structured source loss

Reserve behaves differently when loss removes complete sources. At each raw
minimum, dropping six sources leaves 114 and retains aggregate planning power
with audibility-equivalence power of approximately 0.803-0.808. Dropping 12
leaves 108 and reduces that power to approximately 0.775-0.777; dropping 24
leaves 96 and reduces it to approximately 0.697-0.714.

A 40% reserve can raise the retained-aggregate equivalence calculation above
0.80 even after all 24 source groups are removed. That does **not** repair the
planned design:

- the removed sources still have zero judgments;
- their candidate-position graphs are absent;
- provider, domain and partition breadth cannot be evaluated without frozen
  exact-member assignments; and
- additional observations on the remaining sources do not replace independent
  truth-bearing groups.

Therefore every structured-source-loss cell fails fixed-manifest support and
position-adjusted planned contrasts, even when its retained aggregate power
passes. A realized study would need to recompute exact-member breadth and power
and abstain from affected claims rather than inherit an aggregate 120-source
planning result.

## Decision boundary

This frontier shows that the modelled MCAR resource envelope is finite, not
that it is acceptable or empirical. A responsible next decision may compare
the reserve costs with a separately frozen pilot and operational policy. Such
a successor would still need:

- empirical, score-blind pilot estimates rather than assumed retention rates;
- exact source membership and provider/domain/partition breadth gates;
- append-only, idempotent allocation-index reservation and restart recovery;
- outcome-blind completeness and exclusion rules;
- prespecified retained-design diagnostics and abstention; and
- explicit authority before recruitment or collection.

No reserve option, workload, missingness correction, adaptive replacement, or
collection path follows from this result. A decision that the resource scale or
remaining assumptions are unacceptable remains a rigorous negative result.

## Bound artifacts

- [`frozen plan`](../../benchmarks/perceptual-degradation-v1/listening-retained-design-robustness-plan.json)
- [`deterministic implementation`](../../scripts/perceptual_degradation_listening_retained_design_robustness.py)
- [`score-blind evidence`][evidence]

[evidence]: ../../research/toolchains/evidence/perceptual-degradation-listening-retained-design-robustness-20260814-001.json
