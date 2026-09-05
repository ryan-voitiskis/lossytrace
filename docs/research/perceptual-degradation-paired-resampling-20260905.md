# Crossed resampling and missing-rating bounds — 2026-09-05

Status: synthetic development comparison complete; no replacement method is
qualified for human calibration. Resampling improves several variance-stress
cases but still undercovers, especially when rare source effects are absent
from the sampled panel. Missing-rating bounds address a different uncertainty
and can be wide enough to prevent a useful decision.

## Design and methods

The [plan](../../benchmarks/perceptual-degradation-v1/paired-resampling-audit-plan.json)
was declared before execution. It specifies 12 mechanisms, 128 independently
seeded panels per mechanism, 24 synthetic listeners and 12 synthetic sources.
It is a development comparison, not independently preregistered confirmation.
The earlier cases and findings remain consumed development evidence; fresh
seeds alone do not make this an independent validation of a method designed
after reading those findings.

Every generated paired difference passes through the unchanged event reducer
and role resolver. Completed differences retain their sign. Unsubmitted single
grades do not become paired outcomes. Each method receives only the completed
paired values and the full planned assignment grid, including missing cells.
Synthetic hidden outcomes are used only to evaluate performance, never as
estimator inputs. All generated grades are bounded without clipping.

The target is the population mean paired difference before missingness. Most
cases put that mean at the old -1 material boundary. Two clear controls put it
at -2 or 0, with complete data and with independent 10% missingness. These are
diagnostic coordinates, not justified human materiality margins or labels.
Variation stresses include doubled deviations, source-dependent residual
variance and a zero-mean source mixture with effects -0.2 and +1.8, occurring
with probabilities 0.9 and 0.1.

The three methods are:

1. The unchanged fixed-variance crossed Gaussian solver on complete pairs.
2. A basic pigeonhole-bootstrap interval for the complete-case mean, resampling
   all planned listener indices and source indices independently with replacement.
3. A bounded-missingness extension: each unobserved pair is allowed to take any
   value in [-4, +4]. The method bootstraps the resulting lower and upper endpoint
   statistics, without manufacturing a point estimate from their midpoint.

[Owen (2007)](https://arxiv.org/abs/0712.1111) motivates separate row/column
resampling and examines its variance behavior. Its analysis is conditional on
observation patterns and is not an exact small-sample confidence-interval or
selective-missingness guarantee. The bounded-endpoint extension evaluated here
is not a theorem supplied by that paper.

For N planned cells, m missing cells and observed sum S in grade units, the
finite-panel mean lies in `[(S - 4m)/N, (S + 4m)/N]`. This follows directly from
the response support. The distinction between such identification information
and additional assumptions is consistent with
[Manski (2005)](https://doi.org/10.1016/j.ijar.2004.10.006).
Those bounds contain the mean of the realized panel, not automatically the
population mean. Sampling uncertainty is evaluated separately.

Each primary interval uses 1,024 bootstrap draws and type-7 quantiles at 1/80
and 79/80. Basic limits reflect the opposite bootstrap quantile around the
observed statistic. Quantile interpolation and interval arithmetic use exact
rationals, including equality at the material boundary. Candidate intervals
are intersected with the known [-4, +4] population support. The reference
pointwise coverage is 97.5%, not established coverage or a familywise guarantee.

No empty bootstrap draw is discarded or redrawn. Any empty draw invalidates
the complete-case ratio interval for that panel. The bounded method still has
set-valued information when a resample contains no completed outcomes. Existing
24-listener, 12-source and 96-complete-response count gates govern diagnostic
severity decisions; passing those counts does not validate a method.

## Complete-data result: adaptation helps but is insufficient

The two new intervals coincide when no paired outcome is missing.

| Boundary mechanism | Legacy intervals covering the population mean | Crossed intervals covering the population mean | Mean crossed interval width |
| --- | ---: | ---: | ---: |
| Matched variation | 128/128 | 126/128 | 0.4851 |
| All three SDs doubled | 90/128 | 119/128 | 0.9689 |
| Source SD doubled | 95/128 | 121/128 | 0.7989 |
| Source-dependent residual variance | 123/128 | 124/128 | 0.5490 |
| Rare source-effect mixture | 106/128 | 105/128 | 0.7290 |

The legacy width stays at 0.4696 in these balanced panels. The new method reacts
to observed variation, but its 119/128 coverage under doubled deviations is
92.97%, with an outer-simulation Wilson 95% interval of 87.18–96.26%. This does
not establish the nominal 97.5% coverage.

The rare-source case is more decisive: coverage is 82.03%, with Wilson interval
74.48–87.72%. Thirty-three panels happened to contain no +1.8 source effect.
Only 10 of those 33 crossed intervals covered the population mean; all 23
crossed misses occurred in this subgroup. Every panel nevertheless passed the
count gates. Resampling cannot invent a component absent from the sampled
sources. This is a synthetic sampling limitation, not an observed frequency of
rare audio artifacts or a theorem against every uncertainty estimator.

## Missingness result: bounds prevent one error at a cost

| Boundary mechanism | Legacy coverage | Complete-case crossed coverage | Bounded crossed coverage | Mean bounded interval width |
| --- | ---: | ---: | ---: | ---: |
| Independent 25% missingness | 125/128 | 122/128 | 128/128 | 2.8732 |
| Differences at or below the population mean missing | 0/128 | 0/128 | 128/128 | 5.8967 |
| Negative-source-effect groups missing | 79/128 | 3/84 returned | 128/128 | 6.3286 |

Under outcome-dependent missingness, 87 panels pass the count gates. Both
complete-case methods produce nonmaterial support in all 87 even though the
true mean is at the diagnostic boundary. The bounded method makes no such
claim: all 128 decisions remain indeterminate. Its 128/128 coverage is not
proof of universal validity; the interval is very wide, and the same method
already fails the complete-data rare-source challenge.

For missing source groups, 752 empty primary bootstrap draws invalidate 44
complete-case intervals. The other 84 return intervals; only three cover the
target. All 128 panels fail source-count support, so coverage among supported
results has denominator zero. The 44 invalid panels remain in all-planned-panel
accounting. The bounded method retains all draws and all assigned source groups.

Finite-panel bounds contain the realized full-panel mean in every generated
panel, as required by their arithmetic. That observation must not be promoted
into a population-confidence claim. In particular, missing-rating bounds do
not fix unobserved source-population components when every assigned rating is
already complete.

## Usefulness and bootstrap precision

All methods make the correct diagnostic material/nonmaterial decision in
128/128 panels for each clear complete-data control. This does not establish
interval calibration: a decision far from a threshold can remain correct even
when an interval misses the true mean.

With independent 10% missingness, the bounded method supports the correct
material decision in 61/128 panels and abstains in 67; it supports the correct
nonmaterial decision in 126/128 and abstains in two. No opposite-direction
decision occurs in those controls. Mean widths are 1.4493 and 1.4587. The method
is not universally abstaining, but its substantial loss of decisiveness is
part of the result, not a success to hide behind zero wrong claims.

The first eight panels of every mechanism also use 2,048 draws, preserving
the original 1,024-draw prefix. No diagnostic decision or interval-return state
changes in those 96 checked panels. The largest endpoint movement is 0.2664
grade units and the largest absolute width change is 0.3625, both for bounded
intervals with missing source groups. Only three of
the eight corresponding complete-case intervals return at both draw counts.
This limited precision check is not independent validation or a proof that
bootstrap quantiles are sufficiently precise for a human study.

## Consequence and reproduction

Neither the legacy method nor this crossed-basic replacement is selected for
human calibration. The next uncertainty successor needs to confront finite
source-sampling error and rare components, not merely adapt an interval's
width. It should compare coverage, useful decisions and abstention jointly;
an eventual sampling/support design must specify the population it can defend.
Missingness prevention, sensitivity assumptions and honest bounds remain
separate from uncertainty caused by unsampled source types.

Two full executions produced byte-identical
[aggregate evidence](../../research/toolchains/evidence/perceptual-degradation-paired-resampling-synthetic-20260905-001.json).
The [implementation](../../scripts/perceptual_degradation_paired_resampling.py)
hash-binds the plan and predecessor engine/evidence, which in turn bind all
earlier analysis sources. The [tests](../../scripts/tests/test_perceptual_degradation_paired_resampling.py)
include literal resampling enumeration, independent rational quantiles, missing
outcome non-leakage, sharp finite-panel bounds, boundary equality, empty-draw
accounting, scoped smoke runs and full golden replay.
The pre-commit review added the plan's omitted width-drift diagnostic and a
translation-versus-width regression test. Two full replays of that reporting
correction were byte-identical; all primary results and existing diagnostics
were unchanged from the initial draft.

```sh
python3 scripts/perceptual_degradation_paired_resampling.py --synthetic
python3 -m unittest discover -s scripts/tests -p 'test_perceptual_degradation_paired_resampling.py'
```

No human data, research audio, actual codec conditions, metric scores or sealed
evidence were accessed. No human margin, audibility model, full-reference oracle,
no-reference training eligibility, final scientific disposition or public
verdict is established. The authorized capture still awaits its physical setup
declaration. All original objective requirements and execution gates remain.
