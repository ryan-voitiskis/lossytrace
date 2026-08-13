# Perceptual-degradation listening feasibility frontier - 2026-08-13

**Status:** score-blind analytic feasibility frontier complete; no operational
study design, listener count, source manifest, recruitment, collection, audio
access, metric execution, or public verdict is authorized.

## Outcome

The accepted 16-reference, one-provider ODAQ path remains useful for
development-only delivery, player, analysis, and attribution plumbing. It
cannot establish human-transparent lossy truth under the frozen equivalence
model.

At chance truth `p = 0.5`, the source random-effect floor for 16 independent
source groups limits asymptotic equivalence power to `0.0353439413`. This is
the best-case limit after listener and binomial uncertainty tend to zero.
Adding listeners, repeat judgments, or sessions cannot reach the required
`0.80` power without increasing independent source coverage.

The first source count whose asymptotic power exceeds `0.80` is 39 independent
source groups per truth-bearing partition:

| Independent source groups | Asymptotic maximum equivalence power |
| ---: | ---: |
| 16 | 0.0353439413 |
| 24 | 0.4231652586 |
| 38 | 0.7998483254 |
| 39 | 0.8155467383 |
| 48 | 0.9141250236 |
| 120 | 0.9999413764 |

The 39-source boundary is mathematical, not operational. With 39 sources and
all 15 subtle trials assigned to one transparent aggregate, the stress model
still requires 6,093 eligible listeners, or 9,432 enrolled listener slots
after the declared attrition assumptions. The design is close to the source
variance limit, so extra listeners buy very little information.

A more source-diverse reference sensitivity with 120 source groups and five
transparent trials per eligible listener requires 496 eligible listeners or
768 enrolled listener slots for one aggregate stratum and one device class.
It is not a selected design. It only makes the scale visible.

## Model and unchanged thresholds

The frontier carries forward the score-blind known-variance planning model:

- familywise alpha `0.05` across four primary decision families;
- one-sided normal threshold `2.2414027276`;
- audibility equivalence interval `[0.45, 0.55]`;
- target equivalence power `0.80`;
- listener logit standard deviation `0.45`; and
- source logit standard deviation `0.35`.

For symmetric equivalence at chance, 80% power requires a planning standard
error below `0.0141926337`. Sixteen sources alone contribute `0.021875`, which
already exceeds that ceiling. The analysis does not relax the interval,
discard the source effect, pool source groups across partitions, or use a raw
binomial mean as ground truth.

This remains a planning approximation, not the final hierarchical analysis.
Its purpose is to reject impossible designs before outcomes are available.

## Attrition and missingness sensitivity

The finite-listener frontier applies these score-blind stress assumptions:

- 15% enrollment dropout;
- 20% training failure;
- 5% technical or quality exclusion; and
- 90% usable trial retention after missingness.

The resulting eligible-listener retention is `0.646`. These values are not
empirical rates, participant exclusion thresholds, or authorization to alter
the response set. A later score-blind pilot amendment must replace or justify
them before any main count can be frozen.

## Partition and device implications

Source groups cannot cross development, calibration, transfer, or final
validation boundaries. Consequently, the asymptotic minimum is:

- 39 unique source groups for one development-only partition;
- 117 across three independent partitions; and
- 156 across four independent partitions.

A 120-source reference sensitivity would require 360 or 480 unique source
groups across three or four partitions respectively. Derivatives of one source
do not count as new groups.

Device classes are treated as separate prespecified estimands and reports. The
qualified Adam T7V / RME ADI-2 Pro FS path supports only that declared playback
class; it does not prove headphone performance or pooled cross-device
generality. At the 120-source/five-trial reference sensitivity, two device
classes double the lower-bound workload from 768 to 1,536 enrolled listener
slots per aggregate stratum.

## Severity and bridge sensitivity

The direct material decision remains conservative: a bridge condition must
pass both the SDG and MUSHRA-loss gates. Joint power is reported using the
Fréchet lower bound, avoiding an unsupported independence assumption.

Unified severity mapping uncertainty is added in quadrature to the larger of
the locally mapped SDG and MUSHRA standard errors. In the 120-source/five-trial
reference sensitivity, mapped-severity power falls from approximately `1.0`
with no mapping error to `0.5708250533` with a five-point mapping standard
error. This does not change the direct material rule; it shows that a bridge
pilot and uncertainty model remain necessary before unified severity can be
treated as precise.

## Decision

The narrow ODAQ path is retained for development plumbing exactly as accepted,
but it cannot assign transparent truth or support independent transfer. No
listener count or operational study is frozen.

The next score-blind source-design requirement is a broader, multi-provider,
permissively licensed manifest with at least 39 independent source groups in
every truth-bearing partition, followed by balanced incomplete-block and
resource feasibility analysis. If that scale is unacceptable or unavailable,
the scientifically valid outcome is explicit abstention: LossyTrace must not
claim transparent-lossy calibration, human-calibrated oracle validation, or
no-reference eligibility.

No retained ODAQ reference was read or projected for this calculation. No
processed condition, score, metric, response, private path, or sealed evidence
was accessed.
