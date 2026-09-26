# Perceptual-degradation source-trait identifiability - 2026-08-14

**Status:** seven source-trait proof obligations frozen and seven synthetic
fixtures replayed twice and byte-identically. This prevents PCM descriptors
from being promoted to source provenance or perceptual truth. It does not read
or select an exact source member, qualify a trait, generate a listening
stimulus or authorize collection.

## Why this gate was needed

The negative/control topology requires seven source-trait classes: natural
bandwidth limitation, quiet, sparse, tonal, synthetic, noisy and clipped.
Five have candidate records, but quiet and naturally clipped references have
none. TinySOL is the only current record for both sparse and tonal material,
so it does not provide independent contrasts. The technical-repair replay
closed transform and alignment plumbing gaps but deliberately did not solve
source identity.

The distinction matters because several relevant PCM descriptors are not
causal histories. A low high-frequency share can arise from a capture chain,
source physics, a generated low-pass or codec processing. Low level can be an
original property or a later gain operation. Flat-topped samples can represent
unwanted clipping or an intentional waveform. Synthetic origin is not a
waveform shape.

## Constructive non-identifiability witnesses

Four fixtures assign two different latent histories to the exact same
signed-16 PCM bytes. These are logical counterexamples by construction, not
claims about retained sources:

| Witness | Competing histories | PCM relation |
| --- | --- | --- |
| Bandlimited multitone | capture-chain bandwidth limit / generated low-pass | byte-identical |
| Quiet tone | preserved quiet source / later attenuation | byte-identical |
| Deterministic noise | documented synthesis / captured noise rendered to the same PCM | byte-identical |
| Flat-top waveform | source/capture clipping / intentional generation | byte-identical |

All four paired SHA-256 values matched. Therefore no function of decoded PCM
alone can distinguish the paired histories. PCM measurement can support a
descriptor, but provenance must come from an independently bound source,
capture or processing record.

This does not say the traits are useless. It says the study must not define a
natural negative with the same shortcut the estimator is supposed to resist.

## Sparse and tonal overlap

Three four-second fixtures used ten equal blocks and a 500 Hz projection:

| Fixture | Active blocks | 500 Hz projection share |
| --- | ---: | ---: |
| Sparse tonal overlap | 2/10 | 0.999999999 |
| Sparse non-tonal contrast | 2/10 | 0.000021551 |
| Tonal non-sparse contrast | 10/10 | 0.999999999 |

The overlap fixture demonstrates that one candidate may legitimately carry
both labels. The two contrast fixtures demonstrate the structure needed to
identify label-specific effects. They do not assign trait truth to any real
source.

## Frozen qualification boundary

Every source-trait member must have exact member identity, derivative-group
identity, clean-reference eligibility, original coding and processing
provenance, licence/attribution evidence, and partition support. Each trait
also has a specific descriptor and provenance obligation. In particular:

- natural bandwidth must not be represented by a generated low-pass or codec
  cutoff;
- quiet source level must be separate from the gain control;
- sparse and tonal claims require at least one independent contrast each;
- synthetic origin requires a generation or synthesis record;
- noisy material requires capture or scene-noise provenance rather than merely
  low-level or generated noise; and
- naturally clipped material requires a source or capture-chain record and
  exclusion of intentional flat-top waveforms; generated hard clipping remains
  a separate production control.

The bound topology still has five candidate records and no explicit quiet or
naturally clipped candidate. No exact member or trait is frozen, and current
scientific source-trait coverage remains incomplete.

## Replay and authority

Two fresh temporary payloads were byte-identical at SHA-256
`ebd9d9ca7b17092b5b8dea619ae75c4a587bbbfd688dd3f26096815947c282ca`.
No generated audio was retained; paths and timing are excluded. The replay
accessed no actual or retained audio, selected no member, opened no score or
sealed evidence, executed no perceptual metric and collected no response.

The next scientific gate is a separately authorized exact-member metadata and
provenance audit. It must preserve missing quiet/clipped candidates and the
sparse/tonal confound rather than filling them from waveform thresholds. Human
truth, source selection, stimulus generation, collection, no-reference work
and the public CLI remain closed.

Bound artifacts:

- [`source-trait identifiability plan`](../../benchmarks/perceptual-degradation-v1/source-trait-identifiability-plan.json)
- [`deterministic implementation`](../../scripts/perceptual_degradation_source_trait_identifiability.py)
- [`synthetic evidence`][evidence]

[evidence]: ../../research/toolchains/evidence/perceptual-degradation-source-trait-identifiability-20260814-001.json
