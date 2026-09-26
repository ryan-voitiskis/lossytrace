# Paired uncertainty: variance and missingness sensitivity — 2026-09-05

Status: bounded synthetic diagnostic executed; the fixed-variance interval is
not established as a human-calibration method. This result preserves the old
solver, plans, power calculations and evidence. It neither selects a replacement
estimator nor changes a human materiality margin.

## What was tested

The [audit plan](../../benchmarks/perceptual-degradation-v1/paired-uncertainty-audit-plan.json)
declares eight mechanisms, one population target and 128 independent seeded
panels per mechanism. Each panel has 24 synthetic listeners and 12 synthetic
source groups, with one paired trial per listener/source combination.

The target is the expected signed condition-minus-hidden-reference grade
difference before missingness. It is -1 in every mechanism, a diagnostic
coordinate at the old material boundary, not a newly justified human margin.
Listener, source and residual effects are independent, zero-mean discrete
variables. Their matched standard deviations are 0.25, 0.30 and 0.50 grade
units. Four further complete-data cases double one or all of those deviations.

Integer differences are represented by two legitimate 1.0–5.0 candidate grades,
without clipping. The unchanged paired event reducer and role resolver recover
the signed difference. Incomplete trials retain a locked choice and one grade,
but no paired target. Assignment templates are local to each simulated panel;
replicates are not pooled as extra sources or listeners. The forced-choice
position is a fixed nuisance, not a model of human detectability.

The old crossed Gaussian solver fits only complete pairs. Its variance
components remain at their original values in every case. The new
nonmateriality adapter checks the resulting severity evidence; no audibility
classifier or combined perceptual truth is evaluated.

This is a development diagnostic whose mechanism was declared before execution,
not an independently preregistered confirmatory study. The design separates its
target, generating mechanisms, method and performance measures, following the
simulation-study reporting approach of
[Morris, White and Crowther (2019)](https://discovery.ucl.ac.uk/id/eprint/10066118/).
That guidance supplies no evidence for the chosen human variance assumptions.

## Complete-data result: fixed width does not ensure coverage

For the balanced complete design the fitted intercept equals the grand mean.
Its actual sampling variance is
`listener_variance / 24 + source_variance / 12 + residual_variance / 288`.
The audit checks the actual solver against this independent mean/variance
calculation within 1e-8. It then enumerates the finite discrete distribution of
the sample mean by convolution. This gives coverage without a normal
approximation or Monte Carlo error, up to floating-point arithmetic.

Here, coverage means the probability that the interval contains the known
synthetic population mean. The old interval is approximately -1 ± 0.234783
when centered at that mean. Its width does not react to the simulated increase
in actual variance.

| Generating variation | Enumerated coverage of the unchanged interval |
| --- | ---: |
| Matched variance | 97.624% |
| Listener SD doubled | 91.363% |
| Source SD doubled | 79.765% |
| Residual SD doubled | 95.720% |
| All three SDs doubled | 73.595% |

The frozen multiplier `2.2414027276` corresponds to approximately 97.5% central
coverage under a normal model, not an ordinary 95% central interval. It derives
from a one-sided tail allocation. The audit does not establish familywise
coverage across multiple methods, conditions or directional claims.

The matched discrete result is close to that normal reference. It does not
validate the variance values for real ratings or establish general coverage.
The variance-stress results show a concrete failure mode for treating the
unchanged interval as calibrated when its fixed components are wrong.

## Missingness result: enough responses can still give the wrong target

The remaining mechanisms retain matched generating variance but change which
paired responses are completed. The target stays at the pre-missingness
population mean; it is not silently changed to the completer mean.

| Missingness mechanism | Returned intervals covering the target | Wilson 95% interval for simulated coverage | Estimated bias in grade units |
| --- | ---: | ---: | ---: |
| Independent one-quarter missing | 125 / 128 | 93.34–99.20% | +0.0179 |
| Differences at or below -1 missing | 0 / 128 | 0–2.91% | +0.5516 |
| Negative source-effect groups missing | 81 / 128 | 54.66–71.13% | +0.3001 |

These are finite simulation estimates, not human error rates. Bias Monte Carlo
standard errors are approximately 0.00984, 0.00319 and 0.00579 respectively.
The full report includes rate numerators, denominators, Monte Carlo standard
errors and Wilson intervals. A plug-in Monte Carlo SE of zero at 0/128 does
not prove that population coverage is exactly zero.

The outcome-dependent mechanism deliberately removes the more negative
differences. It is a sensitivity challenge, not an observed participant dropout
pattern. Ninety-seven panels still pass the old count-based support rules, yet
all 97 produce nonmaterial severity support for a population exactly at the
diagnostic boundary. The other 31 abstain on support. This is not repaired by
simply retaining a minimum number of responses.

In contrast, the source-dependent mechanism leaves too few source groups in
all 128 panels. The support gate therefore keeps every severity decision
indeterminate. The raw 81/128 interval coverage must not be reported as coverage
among supported results: that latter denominator is zero.

All 1,024 fitted panels returned numerical intervals. Convergence alone did not
protect coverage. Dedicated tests also exercise entirely missing panels and
known numerical failures, preserving all planned replicates in the accounting
without fabricating an interval or rerolling a seed. Conditional rates are
reported separately from the fraction of all replicates that return and cover.

## Consequence for the research program

The current fixed-variance, complete-case preparation path must not supply
human-calibrated truth without a separately justified variance and missingness
model. Count gates and correct decision logic are necessary safeguards but do
not establish valid uncertainty. Estimating variance may address width errors;
it does not by itself recover information lost through selective missingness.

The next statistical successor should evaluate explicit variance-estimation and
uncertainty methods, alongside a declared missingness strategy and sensitivity
analysis. It must preserve the intended listener/source population and avoid
turning completer-only results into population or per-source labels. The paired
materiality margin, audibility boundary behavior, multiplicity and real-study
delivery remain separate unresolved decisions. This audit selects none of them.

No research audio, metric score, observed listener response, sealed label or
real source identity was accessed. No oracle, no-reference training, final
research disposition or public verdict is enabled. The authorized clean capture
still requires the physical equipment/setup declaration before execution.

## Reproduction

Two independent full CLI runs produced byte-identical aggregate
[evidence](../../research/toolchains/evidence/perceptual-degradation-paired-uncertainty-synthetic-20260905-001.json).
The [implementation](../../scripts/perceptual_degradation_paired_uncertainty.py)
binds the exact plan bytes and predecessor sources. Its CLI has no input path,
replication-tuning or observed-data option. Reduced in-memory unit smoke tests
are explicitly labelled as reduced, not as the full audit.

```sh
python3 scripts/perceptual_degradation_paired_uncertainty.py --synthetic
python3 -m unittest discover -s scripts/tests -p 'test_perceptual_degradation_paired_uncertainty.py'
```

The [tests](../../scripts/tests/test_perceptual_degradation_paired_uncertainty.py)
include independent brute-force probability enumeration, generating moments,
all signed grade ticks in both candidate positions, missingness rules, numerical
solver comparisons, failure denominators, scope/plan tampering and golden replay.
