# Factorial benchmark v2 source-allocation result

Date: 2026-08-02

State: source identities frozen privately; no benchmark audio, factor level,
mechanism score, or unopened label inspected

## Outcome

The preregistered identity-only allocation completed and replayed exactly. It
enumerated 37,463 eligible identity candidates and selected one member for
each of 793 retained source groups:

| Evidence partition | Selected groups | Source domains |
| --- | ---: | ---: |
| Mechanism development | 527 | 6 |
| Encoder transfer | 102 | 6 |
| External transfer | 164 | 7 |

The difference between the earlier inventory's seven development domain labels
and this allocation's six is intentional. The same 48 public Tier A source
groups occurred once as full originals and again as matched controlled
excerpts. The frozen allocation uses the controlled PCM excerpt as the single
base for each group rather than double-counting that lineage.

All transfer floors remain intact. This is an allocation result, not evidence
that any group is independent beyond its documented partition boundary and not
evidence that codec history is identifiable.

## Constraint results

- VCTK retained exactly 28 female and 28 male provider speaker IDs before one
  utterance was chosen per speaker.
- RAVDESS selected 15 acted-speech and 9 acted-song members across its 24 actor
  groups; its repeated-PCM pair remained excluded.
- RWC's deterministic augmenting-path matching covered all 85 artist families
  with 85 distinct normalized work titles.
- Every retained group has exactly one selected member.
- No existing v1 SQAM or release holdout identity was included.
- No waveform content, duration, mechanism measurement, or unopened label
  participated in ranking.

The selected RWC collection counts were 17 classical, 28 genre, 6 jazz, 33
popular, and 1 royalty-free family. These are content-domain factors inside
one RWC provider stratum, not 85 independent recording or production chains.

## Reproducibility and privacy

Two full low-priority executions independently rehashed the bound provider
artifacts, rebuilt the identity index, and applied the frozen rules. Their
canonical non-timing outputs were byte-identical:

| Private artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Candidate index | 32,797,130 | `07a00a0f56570c0778e384c6a816a69be13fffe42596c1aad80d5a6a99357a07` |
| Exact source allocation | 789,972 | `e4b7d2ab42253e00ce0e0b95c8049193f9b6178ecbb6212811fde96d58c088d4` |

The frozen public rules hash is
`f7bda6b5b133e83e558e4812bbe5a48f8dddd6659368f11ad4784420efb1590b`.
The path-free public aggregate is
[`source-allocation-observed-20260802.json`](../../research/sources/evidence/source-allocation-observed-20260802.json),
SHA-256
`92558487864280bb1e7d37fe5474b1be3df49ed3a0b549cb382a8f17d06e20a7`.

The candidate index and allocation remain outside Git under the private v2
benchmark root. They contain no absolute machine paths. The public aggregate
recursively excludes exact case, group, member, relative-path, source-group,
and audio-hash fields.

## Executed boundary and implementation corrections

The rules and implementation were committed before the first attempt. Two
pre-output plumbing stops occurred and are preserved in Git history:

1. the VCTK archive hash was read from a singular rather than plural evidence
   key; and
2. SATP's provider `/` missing-coordinate sentinel was rejected by the
   absolute-path privacy guard.

Both fixes were made and tested without changing any ranking prefix, identity,
eligibility rule, grouping rule, expected count, or matching procedure. The
first stop occurred before the VCTK archive was enumerated. The second reached
identity enumeration but stopped before selection and emitted no artifact;
missing SATP coordinates are now represented as JSON `null` while their
preregistered singleton grouping keys are unchanged.

## Interpretation and next gate

The source allocation is now frozen. It establishes exactly which PCM masters
may feed later construction, but it does not freeze codec settings, transforms,
encoder or decoder binaries, or which fractional-factorial cells each group
receives.

The next checkpoint is therefore a factor-level freeze. It must define the
bounded reference excerpt rule, codec settings, PCM hard-negative transforms,
analysis decoders, support factors, and partition-specific coverage without
generating audio. Exact toolchain bindings and the fractional assignment then
remain separate commits. No mechanism representation or score is authorized
until all three gates are complete.
