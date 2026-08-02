# Cannam fixed-rule failure atlas result - 2026-08-02

**Decision:** reject the exact published-weight Cannam baseline for a safe
scoped prior-lossy assessment. Preserve its failures as required challenge
families in the successor factorial benchmark. Do not tune its thresholds,
derive a support filter from its errors, or use it as a public verdict.

## Question and frozen method

This study measured the exact
[`cannam/vamp-lossy-encoding-detector`](https://github.com/cannam/vamp-lossy-encoding-detector)
revision `7a70bd8d15e68b0b1942a9d3deac6ad4d8293b8b` on all 5,280
already-consumed LossyTrace development cases. The published rule was frozen
before scoring:

- a plugin window was positive when `cf >= 0.5`;
- a file was positive when at least 25% of its windows were positive;
- the complete retained input was supplied without new preprocessing; and
- the model, weights, plugin host, and thresholds were not changed.

P1 is the general multi-codec population: 3,546 controlled positives and 1,734
genuine-PCM or PCM-transform negatives from 597 source groups and eight source
domains. P2 is the task-matched MP3-128 view: the same 1,734 negatives and 527
controlled MP3-128 positives. Both are consumed development evidence. The 280
future codec-only cases and release-held-out labels remained sealed.

## Result

The detector had very high sensitivity and very low specificity. On P1 it
detected 3,526/3,546 controlled positives, but falsely alerted on 1,171/1,734
negative cases and on 545/597 negative source groups. This fails the
predeclared safety gate irrespective of recall.

| Population and metric | Result | Two-sided 95% Wilson interval |
| --- | ---: | ---: |
| P1 recall | 3,526/3,546 = 99.44% | 99.13%-99.63% |
| P1 specificity | 563/1,734 = 32.47% | 30.31%-34.71% |
| P1 false-positive rate | 1,171/1,734 = 67.53% | 65.29%-69.69% |
| P1 selected-population precision | 3,526/4,697 = 75.07% | 73.81%-76.29% |
| P1 selected-population accuracy | 4,089/5,280 = 77.44% | 76.30%-78.55% |
| P1 balanced accuracy | 65.95% | not a binomial rate |
| P1 negative-group alert rate | 545/597 = 91.29% | 88.76%-93.30% |
| P2 MP3-128 recall | 527/527 = 100.00% | 99.28%-100.00% |
| P2 specificity | 563/1,734 = 32.47% | 30.31%-34.71% |
| P2 selected-population accuracy | 1,090/2,261 = 48.21% | 46.15%-50.27% |
| P2 selected-population precision | 527/1,698 = 31.04% | 28.88%-33.28% |

Accuracy and precision are properties of these selected populations, not
estimates for a music library. P2 is especially instructive: perfect MP3-128
recall coexisted with only 31.0% precision because the same signal was common
in genuine PCM. A headline sensitivity result therefore does not establish
usable prior-history inference.

## Failure atlas

The dominant failure is a bandwidth/content shortcut. Every case in each of
these genuine-PCM classes alerted:

- 253/253 resampled 48 kHz NSynth cases;
- 150/150 sharp-low-pass 16 kHz MUSDB cases;
- 150/150 32-to-44.1 kHz resampled MUSDB cases;
- 40/40 low-pass-only retained full-mix cases;
- 36/36 independent 32-to-44.1 kHz PCM resamples; and
- 36/36 independent 19 kHz low-pass PCM cases.

Sparse and domain-shifted sources also failed. The false-alert rate was
198/253 (78.26%) for 16 kHz NSynth montages and 15/20 (75.00%) for
provider-confirmed VocalSet PCM. Even untouched or benignly transformed
full-mix PCM was unsafe: 13/40 untouched lossless cases, 15/40 gain-only cases,
12/40 trim-only cases, and 10/40 dither-only cases alerted.

The effect varied sharply by source domain. Negative-case specificity ranged
from 10.00% on NSynth train and 14.15% on NSynth test to 73.96% on the public
Tier A controlled set. Every negative source group alerted in each of the two
NSynth domains, MUSDB, the DEMAND/MAESTRO transfer set, and the private
full-mix set. This is not stable source-independent evidence.

Controlled positives were nearly saturated, but not uniformly so. The only
positive class with misses was AAC-LC 256: 20/40 cases were detected. Every
named source domain nevertheless had at least one detected controlled-positive
variant per represented source group, illustrating why an `any variant`
group statistic cannot repair poor case-level specificity.

## Duration and score interpretation

Before P1, the historical-pilot audit found that the earlier 112-case report
used full tracks while the retained overlap used 30-second excerpts. All 104
shared inputs had different window counts, and one gain-only negative crossed
the fixed 25% file boundary. The invalid comparison was stopped and retained;
a same-input replay then reproduced byte-for-byte. This establishes that the
file rule is excerpt/duration-sensitive, not that the model or host drifted.

P1 had 10-613 windows per case, with median 30 and p95 41. Negative-case
false-positive rates were 76.12% for 10-29 windows, 66.30% for 30-59 windows,
41.67% for 60-119 windows, and 28.57% for the seven cases with at least 120
windows. These bands are confounded by source composition and are descriptive,
but they rule out treating the aggregation threshold as duration-invariant.

The positive-window fraction is not a probability. Its P1 median was 1.0 for
controlled positives but 0.69375 for negatives, with both distributions
reaching 1.0. Selected-population calibration diagnostics (Brier 0.1732, ECE
0.1826) do not establish calibration or transport to any other population.

## What this teaches the successor benchmark

The result supports five design requirements rather than a detector repair:

1. Pair every codec-derived case with the same source under genuine PCM
   low-pass, resampling, gain, trim, dither, and wrapper controls.
2. Group splits by source before any fitting; random case splits would leak
   the content signatures that dominate this result.
3. Hold out encoder implementations and source collections, not merely files
   from familiar collections.
4. Treat excerpt duration and aggregation as explicit factors.
5. Require source-group-safe false-positive gates before sensitivity can be
   considered.

The next research step is therefore the frozen encoder/source inventory and
paired factorial construction. Cannam's errors may check benchmark coverage,
but may not define exclusions, support, thresholds, or a new candidate.

## Reproducibility and evidence commitments

The 5,280 atomic partials regenerated a byte-identical schema-2 raw report,
and the analyzer regenerated the committed path-free aggregate byte-for-byte.
The aggregate contains counts, public class/domain labels, summary statistics,
and input commitments; it contains no case identities, source-group
identifiers, audio hashes, or machine paths.

| Artifact | SHA-256 |
| --- | --- |
| observed manifest | `e19b5b408fedf348fa9b6499d5cdd1b6b734d84b19b895d5b0a528f0c4423b7a` |
| retained audio inventory | `6959dfc49b4e5790606c6528ec31d7e6fc14525d78fc491ae0c0304908bf2deb` |
| raw report and replay | `5d8c07e307285f4a00a5f8ae482391ebdab5b75afb176d5211d1ca0c3d00a905` |
| path-free aggregate and replay | `52350a3c06310efeabe20c9fe513cc964267e67c4617ea41592ffa944fada9ff` |
| analyzer | `035f4a527f6e7ae2ef38a2a2de56548948bb6f7977f78f79645d3bae50f8114c` |
| frozen preregistration | `a32d836e89cd9954147ef5dc155b49de25b468effb8ccf4e95dcb2216c665ee1` |
| detector plugin | `9e989b81061fcc5b6186f7a0ed2534400f6b8de1e1ee711a1f76aee1c547c9e6` |
| Vamp host | `a9c197e1d10a4d03748ad2b9a3712013cf9ac8c46dd797dbba44f7f809904a64` |
| Vamp SDK revision | `44c2487763eb248a933e9eff9169cfadee375009` |

Private case rows, paths, audio hashes, audio, logs, and partials remain outside
Git. No threshold was retuned, no support rule or candidate was selected, no
future score was opened, and no public LossyTrace behavior changed.
