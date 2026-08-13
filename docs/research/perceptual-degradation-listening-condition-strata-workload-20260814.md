# Perceptual-degradation listening condition-strata workload - 2026-08-14

**Status:** deterministic score-blind workload sensitivity complete. A
comparable 16-recipe codec grid and the existing control inventories can be
counted, but they are not selected listening conditions and carry no
perceptual truth. No source, condition, option, partition, device policy,
listener count, recruitment, collection, audio generation, metric execution,
or public verdict is selected or authorized.

## Question and evidence boundary

The retained-design robustness frontier reports resources for one aggregate
condition stratum. This audit asks how that resource changes when the scientific
claim must preserve codec, encoder, within-family quality, or control-specific
strata. It uses only frozen technical metadata and the existing score-blind
reserve results. It does not open audio, generate stimuli, run a perceptual
metric, read outcomes, or assign any recipe a transparent or material label.

The bound audio-integrity toolchain contains 46 settings: 24 stereo settings,
four codec families, and ten encoder identities. A metadata-only comparison
grid can represent four codec families, two encoders per family, and two
matched within-family quality levels per encoder:

| Codec | Development encoder | Transfer encoder | Levels |
| --- | --- | --- | --- |
| MP3 | LAME 4.0 | BladeEnc a2d06ec | 96k, 128k |
| AAC-LC | FFmpeg native 8.1.2 | FDK-AAC 2.0.3 | 96k, 128k |
| Opus | libopus 1.6.1 | FFmpeg native 8.1.2 | 64k, 96k |
| Vorbis | libvorbis 1.3.7 | FFmpeg native 8.1.2 | q2, q4 |

These 16 recipes are an arithmetic candidate grid only. Historical availability
does not establish that the conditions are scientifically sufficient, suitable
for listening, transparent, audible, or materially impaired. The existing
synthetic control inventory contributes six families or twelve recipes: four
production controls and two generation-control families represented by eight
generation recipes. It does not complete the required artifact isolates,
difficult natural negatives, or production negatives.

## Multiplication model

For each retained-design workload option and 85%, 90%, or 95% retention
sensitivity, the audit takes the larger bounded session-loss or trial-loss
reserve. It then multiplies the issued eligible prefix by the scenario's stratum
count before dividing by any session-packing capacity and before enrollment
rounding. The frozen 0.646 eligible-listener retention factor is applied last.
Independent partition and declared-device sensitivities are multiplied only
after that rounding.

Six condition-breadth scenarios are reported:

| Scenario | Strata | Supported scope |
| --- | ---: | --- |
| Aggregate only | 1 | Pooled estimand only |
| Codec family | 4 | One estimand per candidate codec family |
| Codec by encoder | 8 | Two encoder estimands per codec family |
| Codec recipe grid | 16 | Codec by encoder by matched quality |
| Grid plus control families | 22 | 16 codec recipes plus 6 control families |
| Grid plus control recipes | 28 | 16 codec recipes plus all 12 control recipes |

Three packing models keep evidentially different assumptions separate:

1. **Dedicated stratum:** one complete stratum per session. This is the direct
   multiplication of the existing per-stratum result.
2. **Exact complete blocks without MUSHRA condition packing:** a session may
   carry multiple complete subtle and MUSHRA blocks only when both frozen trial
   caps allow it. The 3 + 3 option fits two strata; the other options fit one.
3. **Optimistic MUSHRA condition packing:** several conditions share each
   MUSHRA source trial, subject to the frozen eight-additional-condition cap.
   The 3 + 3 and 5 + 5 options arithmetically fit five and three complete strata;
   the 8 + 6 and 15 + 6 options fit one.

The third model is not allocator, player, timing, fatigue, covariance, or
retained-balance evidence. It is retained solely to show how much a separately
validated multi-condition design could change the envelope.

## Resource sensitivity

The following values are arithmetic minima across four unselected workload
options at 90% retention, four independent partitions, and one declared device
class. They count enrolled **session slots**, not unique people.

| Condition breadth | Dedicated strata | Optimistic MUSHRA packing |
| --- | ---: | ---: |
| 16 codec recipes | 27,048 | 16,688 |
| 16 recipes + 6 control families | 37,192 | 22,944 |
| 16 recipes + 12 control recipes | 47,332 | 29,204 |

The exact-block model equals the dedicated result for these arithmetic minima,
because its minimum uses the compact 15 + 6 option, which cannot fit more than
one complete stratum. The optimistic minima use the 3 + 3 option. Neither option
is selected. Adding a second independent device class doubles the relevant
four-partition session-slot total; it does not prove generalization to other
devices.

Across the 16-recipe grid, the optimistic four-partition figure ranges from
18,192 at 85% retention to 15,160 at 95%. The corresponding dedicated range is
31,508 to 24,768. These are planning sensitivities under the frozen analytic
missingness model, not empirical recruitment forecasts.

## What remains selection-dependent

The arithmetic proves only that condition breadth is a first-order scientific
resource multiplier and that the currently modelled envelopes are large. It
does not determine:

- which codec, encoder, quality, control, artifact-isolate, or hard-negative
  conditions are scientifically necessary;
- whether a source can safely expose multiple conditions without learning,
  fatigue, carryover, or covariance invalidating the retained-design result;
- whether the candidate trials fit the 20-30 minute session target;
- how session slots may be reused across people, days, devices, or partitions;
- whether exact frozen sources preserve provider, domain, and production
  breadth within every condition stratum; or
- whether any feasible breadth can support the contract's transparent-safety,
  severity, artifact-profile, uncertainty, and abstention claims.

A responsible successor would require an explicit condition-selection decision
and a separately frozen, score-blind pilot for the multi-condition allocator,
player, session timing, covariance, retained support, and reuse policy. If the
resource scale or assumptions are unacceptable, that is a rigorous negative
result. This audit does not authorize recruitment or collection.

## Bound artifacts

- [`workload sensitivity plan`](../../benchmarks/perceptual-degradation-v1/listening-condition-strata-workload-plan.json)
- [`deterministic implementation`](../../scripts/perceptual_degradation_listening_condition_strata_workload.py)
- [`score-blind evidence`][evidence]

[evidence]: ../../research/toolchains/evidence/perceptual-degradation-listening-condition-strata-workload-20260814-001.json
