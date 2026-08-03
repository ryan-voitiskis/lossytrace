# Factorial benchmark v2 CRNN baseline result

Date: 2026-08-03

State: naive and random-high-frequency-mask Koops-style CRNN development
baselines complete; path-free aggregate frozen; encoder and external transfer
remain sealed

## Decision

Neither CRNN condition supplies usable evidence of prior lossy history on the
factorial v2 mechanism-development population. The naive model labels 95.48%
of negative cases positive and alerts on 518/527 negative source groups. The
masked model labels every case positive at the frozen 0.5 boundary and alerts
on all 527 negative source groups.

The matched-reference result fails the preregistered discovery comparison by a
large margin. Naive source-group direction is 372/527 = 70.59%, with a
one-sided 95% Wilson lower bound of 67.22%. The masked condition is 312/527 =
59.20%, with a lower bound of 55.64%. The comparison levels are 90% direction
and an 85% lower bound. Neither baseline can be promoted by this stage in any
case.

This is a useful negative result: random high-frequency masking does not turn
the paper-aligned spectrogram classifier into a stable codec-history
measurement under complete source-domain folds and hard genuine-PCM
negatives. Do not tune either threshold, architecture, mask, sampling policy,
or loss on these observed scores. The next authorized stage is the separately
committed v2 adapter for the retained A0-A4 and R1/R2 explainable controls.

## Fixed boundary and population

The run follows the frozen
[`development-baseline plan`](../../benchmarks/audio-integrity-v2/development-baseline-plan.json)
and its
[`preregistration`](development-baseline-preregistration-20260802.md):

- six leave-one-source-domain-out folds with grouped inner validation;
- one canonical case per exact decoded PCM for training;
- deterministic one-thread CPU execution with seed 20260802;
- the fixed 0.5 classification boundary;
- no class resampling, class weighting, paired loss, threshold search, or
  post-score protocol change;
- 9,653 factorial cases, 7,701 unique decoded PCM sequences, 9,513 retained
  wrapper representatives, and 527 source groups; and
- exact score and window-count invariance across every represented lossless
  wrapper of identical PCM.

This is paper-aligned rather than an exact reproduction. Koops, Micchi, and
Quinton publish the high-level model and masking intervention, but not code,
weights, convolution channel counts, spectrogram hop defaults, optimizer, or
training schedule. LossyTrace's evaluation is also deliberately stricter:
complete source-domain outer folds, grouped inner validation, exact-PCM
collapse, and the retained hard-negative matrix.

## Classification failure atlas

All rates describe this selected development population. They are not
real-library prevalence estimates or calibrated history probabilities.

| Analysis unit and condition | TP | FN | TN | FP | Recall | Negative FPR | Balanced accuracy | AUC | Log loss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| factorial case, naive | 4,903 | 85 | 211 | 4,454 | 98.30% | 95.48% | 51.41% | 52.26% | 0.7249 |
| unique PCM, naive | 4,879 | 85 | 109 | 2,628 | 98.29% | 96.02% | 51.14% | 50.75% | 0.6488 |
| factorial case, masked | 4,988 | 0 | 0 | 4,665 | 100.00% | 100.00% | 50.00% | 48.03% | 0.7400 |
| unique PCM, masked | 4,964 | 0 | 0 | 2,737 | 100.00% | 100.00% | 50.00% | 46.31% | 0.6548 |

At source-group level, naive detects at least one positive for 526/527 groups
but also alerts on 518/527 negative groups. Masked detects at least one
positive and alerts on at least one negative for all 527 groups. High recall
therefore reflects a near-universal positive decision, not safe history
separation.

The fixed-boundary failure is not merely a calibration inconvenience. The
unique-PCM AUC is 50.75% naive and 46.31% masked, so a threshold search on this
population would not repair a stable ranking signal and would violate the
frozen protocol regardless.

## Matched-reference effects

The primary paired calculation removes exact duplicate PCM pairs and takes one
median positive-minus-reference direction per source group.

| Condition | Positive groups | Direction rate | One-sided 95% Wilson lower | Median group delta | P05 to P95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| naive | 372/527 | 70.59% | 67.22% | 0.0000945 | -0.0009921 to 0.0135457 |
| masked | 312/527 | 59.20% | 55.64% | 0.0000112 | -0.0003684 to 0.0006334 |

Direction is source-domain dependent rather than stable:

| Outer source domain | Naive direction | Naive lower | Masked direction | Masked lower |
| --- | ---: | ---: | ---: | ---: |
| DEMAND/MAESTRO consumed transfer | 91.67% | 80.89% | 58.33% | 44.70% |
| MUSDB18-HQ consumed transfer | 86.67% | 81.45% | 47.33% | 40.73% |
| NSynth test sparse | 64.15% | 52.87% | 58.49% | 47.21% |
| NSynth train sparse | 51.50% | 45.71% | 64.50% | 58.77% |
| private full-mix training | 92.50% | 82.65% | 80.00% | 67.85% |
| public Tier A controlled | 72.92% | 61.36% | 58.33% | 46.49% |

No condition reaches the overall 90% / 85% comparison, and neither is
directionally stable across domains. The masked-minus-naive unique-PCM score
has median 0.01194, P05 -0.05513, and P95 0.07896. That shift does not create
history separation; at the fixed boundary it moves the masked system to an
all-positive decision.

## Execution and integrity

The naive run was interrupted by a machine restart after four folds. Each fold
had already been written atomically with a checkpoint and fold binding. The
unchanged runner revalidated all 9,513 artifact representatives, resumed the
four completed folds, and trained only the final two. All six naive and six
masked folds subsequently passed:

- exact checkpoint SHA-256 binding;
- exact outer unique-PCM and wrapper-representative counts;
- exact outer case-ID population;
- fold-file identity with the complete private report;
- exact case-to-artifact score and window-count mapping; and
- exact wrapper invariance across 1,398 multi-wrapper PCM groups.

The path-free analyzer was replayed to a fresh temporary output and produced a
byte-identical result. No private identity, path, audio hash, checkpoint, or
model weight enters Git.

## Evidence bindings

| Artifact | SHA-256 |
| --- | --- |
| naive private report, retained outside Git | `cd9f76ca170027af49defa336dcc5d7128dc0910c67f36b6208148608d03410d` |
| masked private report, retained outside Git | `d7a7d7c0d2180de623926da6d93200279cc477f44668616befc67576d46cb472` |
| path-free public aggregate | `f42d4f1844524ef25f998810394a62361cd31efb42b0b38893ff42c706fde84c` |
| frozen CRNN runner | `4fdc8f9305251211985f8427fd6ab8ab243dff153a41dfd7006465e125ad0c46` |
| frozen CRNN analyzer | `389684f9fbcf270182ce8a9ad76708487a4efcfe2461299e8bca1238e7f05868` |
| frozen development-baseline plan | `9d483ec87365aa4253fa5997458f2fab604b27f029ce42ca20d917f79caa51b0` |

The public aggregate is
[`crnn-observed-20260802-001-aggregate.json`](../../research/baselines/v2/evidence/crnn-observed-20260802-001-aggregate.json).
It explicitly keeps independent validation false, encoder and external
transfer unopened, softmax uncalibrated, baseline promotion disabled, and the
public verdict disabled.
