# Independent-group audit — 2026-09-05

Status: synthetic development audit complete. The frozen boundary-rate
implementation can overstate evidence when related sources share outcomes.
Its record validator accepts the relationship metadata, but the bootstrap and
Wilson guard count source groups rather than the independent partition groups
in this declared stress model. No real error rate, replacement inference method
or full-reference pass is established.

## Why this matters for the original objective

The oracle must transfer to unfamiliar sources, domains, codecs and encoders.
Its uncertainty cannot gain independent collection evidence merely because
more related recordings receive distinct source IDs. Split isolation and
sampling independence are different requirements. A source-level interval is
not inherently wrong for every population, but its population and dependence
assumptions need justification before a generalization claim.

The [frozen evaluator](../../scripts/perceptual_degradation_full_reference_evaluation.py)
checks that a source does not cross partition groups. Its `bootstrap_summary`
and `_source_group_guard` group by `source_group_id`; partition counts are
diagnostics rather than inference inputs. The
[contract](perceptual-degradation-contract-20260803.md) keeps related sessions,
performers, releases, collections and production chains in partition groups.
Neither an opaque ID nor placement in a different split establishes statistical
independence.

[Cameron and Miller (2015)](https://cameron.econ.ucdavis.edu/research/Cameron_Miller_JHR_2015_February.pdf)
explain why ignoring within-cluster correlation can understate uncertainty and
why few clusters remain difficult even with cluster-aware methods. That is
methodological background, not a guarantee for this application or permission
to select a replacement model.

## Prospective design and exact arithmetic

The [new plan](../../benchmarks/perceptual-degradation-v1/independent-group-audit-plan.json)
was declared before the audit ran. This is a targeted development
falsification following consumed uncertainty findings, not independent method
validation or a new human-study preregistration.

There are C independent, identically distributed Bernoulli(theta) partition
outcomes. Each partition contains K distinct synthetic sources that share its
outcome perfectly. All conditions are supported and observed. This is a
dependence stress case, not measured audio dependence or permission to split
one real recording into artificial source groups.

The grid uses C in {1, 4, 20, 40}, K in {1, 2, 4, 40}, and theta in
{0.05, 0.10, 0.11, 0.20, 0.79, 0.80, 0.90, 0.95}: 128 combinations. For each,
every possible number k of event-bearing partitions is enumerated with exact
binomial probability. Total mass is exactly one; there is no Monte Carlo error
in these grid probabilities. The same event model is interpreted separately as
a false material alert on a transparent condition or a correct material alert
on a material condition; these are not mixed in one population.

Three boundary guards are compared: unchanged source-count Wilson, the same
Wilson formula using C, and exact binomial-tail inversion using C. Upper and
lower bounds each have a nominal one-sided 95% reference; they are not together
a two-sided 95% interval. Exact-tail comparison follows the binomial inversion
described by [NIST](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm),
with one-sided tail probability 0.05. Equality is handled explicitly. Exact
probabilities are stored as reduced `numerator/denominator` strings, avoiding
loss of large integer precision. Boundary endpoint brackets use 64 rational
bisections; rounded displays never decide a pass.

Under this equal-size, perfectly shared-outcome model, the partition event
probability also equals the equal-source event probability. The actual variance
of the source mean is `theta*(1-theta)/C`, whereas the independent-source
working variance is `theta*(1-theta)/(C*K)`. The variance ratio is K; adding
related sources has not supplied K times as many independent draws.

## The actual boundary-rate code ignores regrouping

The existing 80-case synthetic fixture was regrouped into 40, 20 or one
partition, keeping its 40 source groups and every other record field unchanged.
Every variant passed the existing record validator. Each transparent/material
subset was passed through the unchanged `_rate_summary`, with 10,000 bootstrap
draws. Only these two rate components were executed, not `evaluate()` or any
real metric or scientific gate.

| Source groups | Partition groups | False-alert upper bound, zero alerts | Sensitivity lower bound, all correct | Both numeric rate components pass |
| ---: | ---: | ---: | ---: | --- |
| 40 | 40 | 0.063353 | 0.936647 | Yes |
| 40 | 20 | 0.063353 | 0.936647 | Yes |
| 40 | 1 | 0.063353 | 0.936647 | Yes |

All 10,000 draws return for each component and variant. The point values,
bootstrap bounds, source guards and combined limits are identical apart from
the diagnostic partition count. At these constant outcomes the bootstrap
bounds are exactly zero or one, so the Wilson guard determines the combined
rate limit.

For comparison, the exact-binomial zero-alert upper bound based on genuinely
independent partitions is 0.072158 for 40, 0.139108 for 20, and 0.95 for one.
Those bounds require the declared Bernoulli sampling assumptions; partition
IDs alone do not make them applicable to future audio evidence.

## Exact failure probabilities under the declared model

With C=20, K=2 and true false-alert probability theta=0.11, zero observed alerts
occur with probability `0.89^20`, approximately 0.0972299658. In that event the legacy combined
safety component passes with upper bound 0.063353, despite the population rate
exceeding the allowed 0.10. Thus this event alone gives a 9.72% lower bound on
false combined safety-component claims. It is not a probability that all
full-reference gates pass.

With one independent partition and 40 sources, theta=0.20 gives an 80% chance
of zero observed alerts and the same false safety-component pass. Separately,
if true sensitivity is 0.79, all observations are correct with probability 79%;
the same source-count machinery then claims a lower bound of 0.936647. These
large effects are consequences of the deliberately strong dependence model,
not measured frequencies in a music library.

| Method | Largest upper-bound noncoverage probability in the grid | Largest lower-bound noncoverage probability in the grid |
| --- | ---: | ---: |
| Source-count Wilson | 0.900000 | 0.900000 |
| Partition-count Wilson | 0.210000 | 0.200000 |
| Partition exact binomial | 0.048028 | 0.048028 |

Noncoverage means the upper bound falls below theta, or the lower bound exceeds
theta, respectively. The guard-only pass probabilities in the evidence are
distinct from the combined bootstrap rule. Separate extreme-event probabilities
give the lower bounds on combined-component false claims above. No whole-oracle
pass probability is computed. At a threshold boundary, a population claim need
not be false, but a bound can still fail to cover its target.

Switching the Wilson denominator to partition count does not restore exact
small-sample coverage. Exact binomial inversion does control the two separate
tail errors in this model and grid, but it is not a general replacement for
uncertain human labels, continuous severity, unequal groups, shared listeners,
crossed dependencies or non-random source selection.

## The successor needs a population contract, not just a new key

Two unequal-size examples make the target issue explicit. A one-source
partition and a nine-source partition have equal-partition mean 0.5 whether
their outcomes are (1, 0) or (0, 1). Their equal-source means are 0.1 and 0.9.
Changing aggregation or weights can change the estimand, not merely its
standard error. Related recordings can still provide useful within-group
information; that is different from new independent collection evidence.

Before a new inferential gate is eligible for human calibration or oracle
transfer, it must declare the target population, sampling frame, independent
unit, cluster-size weighting and relevant nested or crossed dependencies. It
must distinguish source-conditional listener targets from population-average
claims, carry insufficient independent-group support into abstention, and
assess few-group behavior prospectively. The inference unit may need to be
coarser than a source or involve multiple dimensions; it is not automatically
identical to the leakage-control partition field.

No existing plan, gate threshold or dated result was changed. No new minimum
group count or replacement method was selected. The earlier synthetic
statistics replay remains an implementation replay, not evidence of valid
grouped generalization. Capture, source-trait adjudication, listening, metric,
oracle, training and public-verdict gates remain closed at their prerequisites.

## Reproduction and verification

Two full corrected executions produced byte-identical
[aggregate evidence](../../research/toolchains/evidence/perceptual-degradation-independent-groups-synthetic-20260905-001.json).
The [implementation](../../scripts/perceptual_degradation_independent_groups.py)
hash-binds the plan, predecessor evaluator and prior uncertainty report, and
validates the evaluator's transitive bindings. The
[tests](../../scripts/tests/test_perceptual_degradation_independent_groups.py)
check literal Bernoulli enumeration, exact tail equality, complementary
coverage, source-count invariance, actual guard equivalence, outward endpoint
brackets, unchanged observations under regrouping and full golden replay.

An initial test caught cache-key aliasing between Boolean and integer inputs;
typed caches now preserve strict validation, including warmed-cache tests.
The public evidence uses compact exact rational strings. Its probabilities and
existing diagnostics were checked unchanged against the verbose draft before
publication. Neither correction changes the generating model or inference rules.

```sh
python3 scripts/perceptual_degradation_independent_groups.py --synthetic
python3 -m unittest discover -s scripts/tests -p 'test_perceptual_degradation_independent_groups.py'
```
