# Perceptual-degradation negative/control topology - 2026-08-14

**Status:** deterministic score-blind topology and workload sensitivity
complete. All twenty frozen negative classes are accounted for exactly once,
but scientific coverage is incomplete. No source, condition, metric, listening
design, recruitment, collection, response access, no-reference work, or public
verdict is selected or authorized.

## Why the topology matters

The prior condition-strata workload counted a 16-recipe codec grid plus the
four synthetically replayed production controls and two codec-generation
families. That was a valid breadth sensitivity, but it was not a complete
representation of the research contract's negative policy: it omitted the
separate dither and sample-rate-conversion classes, and it did not distinguish
source traits from interventions or alignment nuisances.

Blindly adding all twenty negative classes to the listening-strata count would
also be wrong. Naturally quiet or sparse material is a source context that must
be preserved within grouped evidence. It is not interchangeable with a new
processing condition. Gain, delay, polarity, drift and edge silence may be
alignment nuisances, audible interventions, or both, depending on the frozen
role. The topology therefore separates four axes before doing any arithmetic.

## Required-class topology

| Axis | Classes | Current boundary |
| --- | ---: | --- |
| Transparent truth | 1 | Sixteen codec recipes are candidates; human transparency truth is absent |
| Source traits | 7 | Five classes have metadata candidates; exact members and trait qualification are absent |
| Alignment nuisances | 7 | All have some technical representation; role and several correction fixtures remain incomplete |
| Human-truth production controls | 5 | All have candidate recipes; three have perceptual synthetic replay and none has human truth |

The source-trait classes are natural bandwidth limitation, quiet, sparse,
tonal, synthetic, noisy and clipped. The metadata inventory nominates FSDD,
TinySOL, Slakh and SONYC for five of those classes. Quiet and naturally clipped
references have no explicit candidate record. TinySOL jointly carries sparse
and tonal labels, so it cannot by itself identify independent sparse and tonal
effects. No exact member, trait, relationship or partition assignment is
frozen.

The alignment-nuisance classes are gain, polarity, integer delay, fractional
delay, resampling, bounded clock drift and leading/trailing silence. Existing
synthetic code represents all seven, but the evidence is not a complete oracle
correction audit:

- resampling has a deterministic transform and metric audio-view replay, not
  an aligned-pair correction replay;
- bounded drift has a limit and an over-limit abstention fixture, not a
  successful bounded-drift correction replay; and
- silence has a leading-only transform and edge-trim limits, not paired leading
  and trailing fixtures.

The production classes are equalization, limiting, stereo width, dither and
sample-rate conversion. Equalization, limiting and stereo width have
deterministic synthetic recipe replays. The current dither candidate combines
TPDF dither with 12-bit requantization, so it cannot identify an isolated
dither contrast. The sample-rate-conversion candidate is a technical transform,
not a perceptual recipe replay. None has listening truth.

## Non-substitution rules

The audit enforces ten score-blind rules. The most consequential are:

- a generated low-pass condition does not satisfy naturally bandwidth-limited
  source coverage;
- the production hard-clipping recipe does not satisfy naturally clipped
  reference coverage;
- generated fixtures do not satisfy synthetic-source coverage;
- one jointly sparse and tonal source does not identify separate trait effects;
- 12-bit requantization with dither does not establish isolated dither behavior;
- an alignment resampler does not establish the human effect of sample-rate
  conversion; and
- a codec recipe can count as a transparent lossy control only after frozen
  human analysis assigns that state.

A condition carrying several labels counts once in session arithmetic, but its
outcomes do not identify label-specific effects without independent contrasts.
Source traits require exact grouped representation in every partition that
supports a corresponding transfer or subgroup claim; pooled provider capacity
cannot substitute.

## Corrected condition breadth

The corrected family sensitivity starts with sixteen codec recipes and one
representative from each of the five required human-truth production classes.
The existing production-clipping control and the repeated/cross-codec controls
remain additional non-substituting conditions because they exercise separate
failure modes.

At 90% retention, four partitions and one declared device class, the arithmetic
minima across four unselected workload options are:

| Candidate breadth | Strata | Dedicated session slots | Optimistic MUSHRA packing |
| --- | ---: | ---: | ---: |
| Codec + required production families | 21 | 35,500 | 21,904 |
| Above + clipping and generation families | 24 | 40,572 | 25,028 |
| Above with all generation recipes | 30 | 50,716 | 31,284 |
| Required families + 7 alignment human-truth conditions | 28 | 47,332 | 29,204 |
| Extra families + 7 alignment human-truth conditions | 31 | 52,404 | 32,332 |
| Extra recipes + 7 alignment human-truth conditions | 37 | 62,548 | 38,584 |

The 24- and 30-strata rows correct the earlier 22- and 28-strata composition by
restoring dither and sample-rate conversion. The 28-, 31- and 37-strata rows do
not assert that every alignment nuisance needs a separate listening condition;
they expose the cost if that role is selected. Conversely, omitting those seven
from session arithmetic is not evidence that normalization is perceptually
free.

All values are enrolled session slots, not unique people. The optimistic model
still lacks allocator, player, session-timing, fatigue, covariance, reuse and
retained-balance evidence. Source-trait requirements are not multiplied into
these rows because their exact grouped prevalence and partition allocation are
unfrozen.

## Decision boundary

The result closes an accounting ambiguity, not a scientific gate. Eighteen of
twenty classes have a candidate record or technical representation, but no
class is promoted to completed scientific coverage. Before exact condition
selection could support a pilot, the score-blind preparation still needs:

- explicit quiet and naturally clipped source-trait candidates;
- exact source members, trait qualification, relationships and partitions;
- an isolated dither condition and perceptual sample-rate-conversion recipe;
- bounded-drift correction and paired leading/trailing-silence fixtures;
- an explicit decision on which alignment nuisances require human truth; and
- human truth for transparency, audibility, severity and production controls.

If the corrected resource scale or these non-substitution requirements are
unacceptable, rejection remains a rigorous successful result. This audit does
not authorize recruitment or collection, and the public CLI remains
verdict-free.

## Bound artifacts

- [`negative/control topology plan`](../../benchmarks/perceptual-degradation-v1/negative-control-topology-plan.json)
- [`deterministic implementation`](../../scripts/perceptual_degradation_negative_control_topology.py)
- [`score-blind evidence`][evidence]

[evidence]: ../../research/toolchains/evidence/perceptual-degradation-negative-control-topology-20260814-001.json
