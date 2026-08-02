# Factorial benchmark v2 fractional-assignment result

Date: 2026-08-02

State: two private identity-only assignment replays are byte-identical; the
path-free aggregate is frozen; no audio, waveform statistic, feature, score,
or unopened label was inspected

## Bound inputs

The assignment was executed only after preregistration commit `b33e828` had
been pushed. Both runs used:

- rules SHA-256
  `aec91fc4e31a080000769d8ea385a08d308014a939a3c1d4f69140fb11ca576f`;
- generator SHA-256
  `80088fb1e2c503d16c3ea26c0a152f5a737e5ee808bb4a9ba5205539097ac1ca`;
- private source-allocation SHA-256
  `e4b7d2ab42253e00ce0e0b95c8049193f9b6178ecbb6212811fde96d58c088d4`;
  and
- the previously frozen factor, toolchain, and public-decoder evidence bound
  by the rules.

Only group identity, partition, source collection, source domain, and
provenance tier were available to the assignment. The complete mappings stay
outside Git.

## Replay result

Both complete private assignments have SHA-256
`ab57fe19daa6b3f6497df8592ee0173e1159d7606a00ad4ac7f18c9f5c0d5328`.
Both path-free run aggregates have SHA-256
`ed614760424b438921a6673cc89beaa2a6c9bc309bc5dc71d073b4f0b538fb0f`.
The attested public aggregate is
[`fractional-assignment-observed-20260802.json`](../../research/sources/evidence/fractional-assignment-observed-20260802.json),
with SHA-256
`ee98c77aba75cad588deec8c64c85830591c3ed76773c5d04a6c6b9b96be577e`.

The frozen assignment contains 793 source groups and 11,103 cells:

- 6,356 controlled-positive cells, each with an exact matched PCM reference;
- 4,747 negative reference or hard-negative cells;
- zero unmatched positives;
- all 527 development and 102 encoder-transfer groups at one anchor per codec;
- exact nonanchor quotas of 120 groups per development template and 60 per
  encoder-transfer template;
- nine nonidentity transforms at 40 development, 20 encoder-transfer, and 20
  external groups each;
- all compatible history decoders above their frozen group and template
  minima; and
- an identity-only 100-group external reserve with encoder, codec, decoder,
  and score still unset.

All development templates span six source domains. All encoder-transfer
templates also span six domains. Applicable mono/stereo templates are exactly
balanced at 60/60 in development and 30/30 in transfer; FFmpeg-native Vorbis
transfer remains explicitly stereo-only.

## Interpretation and authorization boundary

The replay gate passed. This establishes a deterministic, source-aware but
waveform-blind allocation and removes assignment drift as a later explanation
for a result. It is not evidence that any codec-history representation works.

The next authorized operation is resumable one-worker construction of the
assigned PCM cases while preserving the 15 GiB free-space reserve. Mechanism
scoring, representation selection, encoder-transfer opening, and external
positive materialization remain unauthorized until their later freezes.
