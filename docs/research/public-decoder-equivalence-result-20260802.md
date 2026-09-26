# Factorial benchmark v2 public-decoder equivalence result

Date: 2026-08-02

Decision: accept the hash-bound LossyTrace/Symphonia public decoder as
lossless-wrapper invariant for the frozen synthetic gate; exact-toolchain
binding is complete

Scientific state: decoder/container plumbing evidence only; no benchmark
audio, allocated source, source assignment, mechanism score, candidate,
unopened label, or public verdict

## Reproducibility

The committed path-free result is
[`public-decoder-equivalence-observed-20260802-001-aggregate.json`](../../research/toolchains/evidence/public-decoder-equivalence-observed-20260802-001-aggregate.json),
SHA-256
`e18ebce9101a59321fe7fcf509222b78d2218476653a091396e596de72520683`.
Two complete invocations produced that same hash and compared byte-for-byte
equal.

The replay binds:

- plan SHA-256
  `581c76772d93019fba4d12f01dd04f95fdd5f8d51163bcd3dc45519f36f4f30b`;
- public binary SHA-256
  `af8bd1389f55325a01ad7ebd48d2ad050a3f8028dccd6ee69262548028d54cb4`;
- exact-toolchain recipe `lossytrace-v2-toolchain-bindings-20260802-004`; and
- the previously accepted FFmpeg toolchain result.

The result validator is
[`validate-audio-integrity-v2-public-decoder-result.py`](../../scripts/validate-audio-integrity-v2-public-decoder-result.py).

## Result

All 12 wrapper paths passed:

- 44.1 kHz mono: FLAC, WAV, AIFF;
- 44.1 kHz stereo: FLAC, WAV, AIFF;
- 48 kHz mono: FLAC, WAV, AIFF; and
- 48 kHz stereo: FLAC, WAV, AIFF.

For every wrapper, the FFmpeg analysis decoder returned signed-s16le bytes
exactly equal to the synthetic input PCM. The public CLI emitted identical JSON
across its two runs. Within each rate/channel triplet, its complete projected
evidence was exactly equal across FLAC, WAV, and AIFF after excluding only the
container byte hash, codec debug name, and extension.

The compared projection retained the schema and verdict state, analyzed sample
count and duration, truncation, sample rate, channel count, declared bit depth,
and complete compression-trace object. This directly establishes public
container invariance at the observable feature boundary. It does not claim
that Symphonia and FFmpeg produce byte-identical internal samples, because the
public API does not expose those samples.

## Decision boundary

This closes the exact-toolchain gate for construction. It does not validate a
codec-history detector, estimate accuracy, or authorize score opening. The
next permissible step is to freeze the fractional source-to-cell assignment
using only already-frozen identities and categorical factors. Benchmark audio
may be generated only after that separate assignment record is committed.
