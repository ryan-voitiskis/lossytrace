# Codec-projection feasibility result — 2026-08-02

**Decision:** reject both preregistered codec-projection representations. Do
not run the conditional robustness stage, freeze a candidate, acquire or open
external-transfer evidence, or integrate this subsystem into the public
library or CLI. LossyTrace remains at evidence schema `1`, measurement feature
version `0`, and `public_verdict_enabled: false`.

## Question and frozen method

This study asked whether analysis-by-synthesis against a fixed MP3 encoder
could provide a source-independent, explainable measurement of prior MP3-128
compression. The literature review and preregistration fixed two summaries
before any observed score was opened:

- R1, cycle-residual retention, measures how much first-cycle residual energy
  remains aligned with the second-cycle residual;
- R2, residual directional recurrence, measures repeated residual direction
  across the two fixed projection cycles.

The oracle canonicalized input to stereo 44.1 kHz signed 16-bit PCM, ran two
fixed FFmpeg/LAME MP3-128 projection cycles, and emitted deterministic
measurements. Leave-one-source-domain-out thresholds were the next
floating-point value above the maximum supported training-negative score.
The gate required every fold to be valid, at least 75% positive-group support,
zero supported-negative alerts with a one-sided 95% Wilson upper bound no
greater than 2.5%, at least 90% overall supported recall with an 85% Wilson
lower bound, and at least 85% recall in every eligible source domain.

The observed population contained 2,261 cases: 1,734 negatives from 597 source
groups and 527 controlled MP3-128 positives, across seven source-domain
families. The 280-case future codec-only subset and release holdout remained
sealed. The evaluation is consumed development evidence, not independent
validation.

## Result

Neither representation produced a single positive alert among the 471
supported MP3-128 groups. Both also produced supported-negative alerts, so
both the recall and exact-zero false-positive gates failed.

| Representation | Negative alerts (cases/groups) | Positive support | Supported recall | Recall Wilson lower | Outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| R1 cycle-residual retention | 2 / 1 | 471/527 (89.37%) | 0/471 (0.00%) | 0.00% | rejected |
| R2 residual directional recurrence | 2 / 1 | 471/527 (89.37%) | 0/471 (0.00%) | 0.00% | rejected |

For each representation, supported-negative case alerts were 2/1,558
(0.128%; one-sided 95% Wilson upper 0.387%) and group alerts were 1/521
(0.192%; upper 0.856%). The statistical upper bounds were below 2.5%, but the
frozen rule also required exactly zero alerts. The positive recall upper bound
was only 0.571%. Every eligible positive source domain had zero recall; all
folds were otherwise valid and the positive support gate passed.

The false positives came from two variants of one consumed SQAM negative group
per representation. The R1 and R2 failures were in distinct groups. Their
scores were nevertheless strongly correlated: case-level Pearson 0.875 and
Spearman 0.932 over 2,029 paired supported cases; group-level Pearson 0.910 and
Spearman 0.870 over 992 paired groups. The two formulations therefore did not
supply independent evidence families.

Score distributions overlapped by content domain rather than separating prior
MP3 history. For example, R1 negative versus positive medians were 0.474372
versus 0.474356 for NSynth test and 0.474372 versus 0.474356 for NSynth train.
R2 medians were 0.999407 versus 0.999231 for NSynth test and 0.999343 versus
0.999317 for NSynth train. Public Tier A medians moved slightly in the desired
direction for both scores, but the domain-safe thresholds were dominated by
higher negative maxima elsewhere and no positive survived. This is a
source/content-dependence failure, not a defensible threshold-tuning
opportunity.

## Support and performance

The oracle supported 2,029/2,261 cases. Unsupported reasons were
`insufficient_activity` (156), `too_short` (46), `quiet` (25), and `clipped`
(5). It supported 1,558/1,734 negative cases (89.85%), 521/597 negative groups
(87.27%), and 471/527 positive groups (89.37%).

The single-worker observed run took 4,222,390 ms in total, about 70.4 minutes.
Median oracle time was 2,077 ms per case and p95 was 2,197 ms. Maximum observed
peak resident memory was 46,628,864 bytes (44.5 MiB). These measurements are
research-harness timings and do not authorize a public performance claim.

## Reproducibility and run disposition

The final run was bound to repository commit
`b0fbf48c47fe71af889c4fa059771aba8478a60d`. Its 2,261 atomic partials
regenerated a byte-identical non-timing raw report, and the analyzer regenerated
a byte-identical path-free aggregate. Timing is separate because it contains
non-deterministic timestamps and observations.

An earlier run identifier is retained privately as engineering audit evidence
but excluded from the result. It first stopped before case 1 because the
harness incorrectly required a Git commit identifier to be a SHA-256, then
stopped after 126 completed partials because an early unsupported case was
validated as if it must contain a zero-valued block count. Both general
validation defects were fixed and tested before the clean, separately bound
final run. No partial or report from the earlier run was mixed into the final
evidence.

The only preregistration clarification made after synthetic smoke testing and
before observed scoring documented FFmpeg input options for raw signed 16-bit
PCM. No observed or archived score was opened before that clarification.

## Evidence commitments

Private manifests, case rows, paths, timings, audio, and partials remain
outside Git. The committed aggregate is path-free and contains no case
identities.

| Artifact | SHA-256 |
| --- | --- |
| retained audio inventory | `52cabf360429abe7941c4e0a68d89561dcbb7745d2bf87f4f5992b68c23f445f` |
| observed manifest | `e19b5b408fedf348fa9b6499d5cdd1b6b734d84b19b895d5b0a528f0c4423b7a` |
| baseline raw report | `4c9ddedc847801a8db3a4bdda318faa7a15e478ee4698bd17a2c3d47287aacc9` |
| codec-projection raw report and replay | `952dfd0405d0f1458d7a1ed26a67d725674346ca015cdcedbf8b2e5b5d887ecb` |
| timing report | `a81604ff047029891f3ea0ed356344b4ed0c3281600e71d7f20fafde79281842` |
| path-free aggregate and replay | `5e01c145745e094c476a6de17a35ba05ffdba7adca82a8d76148db09e03dcb5c` |
| oracle release binary | `fb285afb0e9db3d077f5826467c986dabcdeb2e1e578c09bb2c907172606c5e6` |
| FFmpeg binary | `1332dc2de372bade9a8a63da0d6cdfab9de97fcefbae707bcc0b0506e1203327` |
| LAME CLI | `11095c200ebbef2b43adc795aee0ae1adcfc91a1467b70f524582327bc3f685a` |
| linked libmp3lame | `463453796b54698b8016af58ab86066ffbafe5229c10c500e4fe6b92d7a63934` |
| oracle config | `2f122d7eeed263c0700f78675b1382923c09f8f333903b970afe7cfb18670603` |
| runner | `b749397528462970312af71ed9396164b44ab86d2ae9621c592a72268202432d` |
| analyzer | `325f2f4b9b9789ac7eaeba72357367535b4f05b1fe3ac558a19ceacec430e631` |
| preregistration | `d6b66a9e6e892c59db64edfb909fd29a1968cedb7100a8a30e5941f0eb7419c1` |

## Recommended disposition

Stop tuning cycle-residual thresholds and combinations. Retain the isolated
oracle, deterministic runner, grouped analyzer, and path-free aggregate as
reusable negative-result infrastructure. Do not describe R1 or R2 as a
detector, probability, authenticity measure, codec identifier, or provenance
verdict.

The conditional robustness stage was not run because no representation passed
the observed gate; therefore this study makes no robustness claim. No
candidate was frozen, no new external-transfer set was acquired or opened,
and neither sealed holdout was opened. A future attempt should begin only with
a materially different explainable signal and a fresh preregistration, not a
post-hoc variation of these scores.
