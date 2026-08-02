# Factorial benchmark v2 fractional-assignment result 002

Date: 2026-08-02

State: recipe `002` replayed byte-identically but was superseded before audio
generation because generated-cell identity sources were not explicit; see
[`correction 002`](fractional-assignment-correction-20260802-002.md)

## Bound inputs

Corrected recipe `002` was executed only after correction commit `c2db91f`
had been pushed. Both complete runs used:

- rules SHA-256
  `bd0c611f66efb20c7e1da5537150ddf678a42b61f924b3640180aad30b236bd2`;
- generator SHA-256
  `5759206092b37b7ec7310ff7b7062089297b9e4bffdfad6bfd3e56705f13bbed`;
- private source-allocation SHA-256
  `e4b7d2ab42253e00ce0e0b95c8049193f9b6178ecbb6212811fde96d58c088d4`;
  and
- the previously frozen factor, toolchain, and public-decoder evidence bound
  by the rules.

The assignment read only group identity, partition, source collection, source
domain, and provenance tier. Complete mappings remain outside Git.

## Replay result

Both private assignments have SHA-256
`7d901ee66537ff684a7c5624c530a9e18e559c9b17cd4e4dc85498065ba4aa27`.
Both path-free run aggregates have SHA-256
`9f4c0adce163038d62503e5466694e30f5c26ae078c2a331206db4217556f61a`.
The attested public aggregate is
[`fractional-assignment-observed-20260802-002.json`](../../research/sources/evidence/fractional-assignment-observed-20260802-002.json),
with SHA-256
`64a030b9d84361e382db376b8630da9ddf2555f2c244d7f625ba09bc621c4142`.

The corrected assignment contains 793 source groups and 12,058 cells:

- 6,356 controlled positives;
- 5,702 matched references or hard negatives;
- zero unmatched positives;
- exact matching of every positive on group, partition, channel treatment,
  target sample rate, PCM transform, and wrapper;
- all 527 development and 102 encoder-transfer groups at one anchor per codec;
- exact nonanchor quotas of 120 groups per development template and 60 per
  encoder-transfer template;
- nine nonidentity transforms at 40 development, 20 encoder-transfer, and 20
  external groups each;
- an exact 10/10 external hard-negative split over 44.1 and 48 kHz for every
  nonidentity transform; and
- a 100-group external MP3 reserve fixed at 44.1 kHz while codec setting,
  encoder, decoder, feature, and score remain unset.

All template-domain, channel, decoder, transform, wrapper, and sample-rate
coverage checks passed. The corrected 955-cell increase over rejected recipe
`001` is the expected separation of references that previously collapsed
across 44.1 and 48 kHz.

## Interpretation and authorization boundary

The assignment is deterministic, source-aware, waveform-blind, and free of
the recipe-`001` sample-rate aliasing. A subsequent construction-lineage audit
found that transformed H0 and H1 cells did not explicitly name their shared
untransformed identity source. This result is retained as rejected evidence
and must not enter a benchmark denominator.

No assigned audio had been generated and no score had been opened. Construction
remains paused until recipe `003` passes two fresh byte-identical replays.
Mechanism scoring, representation selection, encoder-transfer opening, and
external positive materialization remain unauthorized.
