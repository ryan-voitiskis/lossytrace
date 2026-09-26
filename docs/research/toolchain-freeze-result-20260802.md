# Factorial benchmark v2 exact-toolchain result

Date: 2026-08-02

Decision: accept recipe `lossytrace-v2-toolchain-bindings-20260802-004` for
benchmark construction after the remaining public-decoder equivalence check;
retain the narrower stereo-only Vorbis encoder-transfer boundary

Scientific state: synthetic plumbing evidence only; no allocated source read,
benchmark case generated, source assigned to a cell, mechanism feature or
score computed, candidate selected, unopened label inspected, or public
verdict enabled

## Reproducibility binding

The committed path-free aggregate is
[`factorial-v2-toolchain-observed-20260802-001-aggregate.json`](../../research/toolchains/evidence/factorial-v2-toolchain-observed-20260802-001-aggregate.json),
SHA-256
`29ddfe00bb419aedcbdee8de530785f5981de279f2bd190f4a337ebbe8c3cc23`.
Two fresh, complete, single-worker recipe-`004` invocations produced that same
hash and compared byte-for-byte equal.

The accepted bindings are:

- corrected factor freeze SHA-256
  `4065553ef4fbe505ea0d79b149570bc1483396dbcc1de52597890e61f59481bd`;
- exact toolchain manifest SHA-256
  `d2af2f0b78b184189806d724c294d7606f37d2763839e17c9289f7957da52070`;
- canonical manifest JSON SHA-256
  `2d6b90c7f0122beb220a98d0f89f66502e513cbafcf373045dc89e1da64d46be`;
- expanded probe implementation SHA-256
  `21fa31de0b0783f05d55dcd8e78b8d0c39c12c358d88dc641cf88ad0f64ee78e`;
  and
- base probe implementation SHA-256
  `ea6ae02980421c720a86093c8169d5de91c2f9d08a1ad4541f57adaa0df0403e`.

The result validator is
[`validate-audio-integrity-v2-toolchain-result.py`](../../scripts/validate-audio-integrity-v2-toolchain-result.py).
It verifies the factor and manifest bindings, every setting and compatible
decoder identity, exact public commands, observed stream realization,
bandwidth frequency grid, transform/wrapper Cartesian sets, deterministic
flags, summary counts, path redaction, and verdict-free state.

## Executable matrix result

All 46 corrected encoder settings produced byte-identical bitstreams across
their two within-replay executions. FFprobe confirmed every declared codec,
AAC-LC profile, sample rate, and channel count:

| Codec | Mono settings | Stereo settings | Total |
| --- | ---: | ---: | ---: |
| MP3 | 7 | 7 | 14 |
| AAC-LC | 6 | 6 | 12 |
| Opus | 6 | 6 | 12 |
| Vorbis | 3 | 5 | 8 |
| **Total** | **22** | **24** | **46** |

The missing two Vorbis mono rows are the frozen FFmpeg-native transfer
exclusion, not probe attrition. LAME CBR-96 remained at the explicit 44.1 kHz
rate after correction. No setting required another substitution.

The five history decoder implementations produced 126 compatible paths. Every
path returned byte-identical WAV containers and PCM across two executions.
Exact PCM differed across decoder implementations for all 46 bitstreams; 20
settings also differed in frame count. The frame-count set comprised all 12
AAC settings, both Shine settings, and all six libvorbis settings.

This is not codec-history evidence. It confirms that decoder identity,
alignment, priming/padding, sample quantization, and usable overlap must remain
explicit factors. A model cannot pool these paths as interchangeable copies of
one target.

## Coarse bandwidth observations

Every setting has a complete segmented-tone curve. Retained-band edges ranged
from 14 to 21 kHz. The intentionally explicit filters behaved distinctly:

- LAME CBR-128 with `--lowpass 16`: 15.5 kHz in mono and stereo;
- FFmpeg AAC-LC CBR-128 with `-cutoff 16000`: 16.5 kHz in mono and stereo.

Defaults were often channel- and implementation-dependent. Examples include
LAME CBR-96 at 20 kHz mono versus 15 kHz stereo, FDK AAC CBR-96 at 16.5 kHz
mono versus 14 kHz stereo, libopus at 20 kHz, and FFmpeg-native Opus at 15.5
kHz. This validates the decision to record a measured curve rather than infer
bandwidth from codec, bitrate, or a nominal default.

These values remain coarse decoded retention edges on synthetic tones. They
are neither exact psychoacoustic cutoff estimates nor provenance signals.

## Transform and wrapper result

Four deterministic rate/channel inputs crossed nine ordinary transform levels
for 36 paths. Identity, integer Q31 gain, trim, leading silence, duration,
eighth-order low-pass, 32 kHz resampling round trip, SHA-256 TPDF
requantization, and alternate channel topology were identical across two
executions.

The lossless-wrapper transform was tested separately. FFmpeg wrote FLAC, WAV,
and AIFF twice for all four inputs, producing 12 deterministic encode/decode
paths. The frozen analysis decoder returned headerless signed-s16le bytes
exactly equal to each input for every wrapper.

## Corrections retained as evidence

Three stop-and-correct events occurred before acceptance:

1. LAME CBR-96 stereo selected 32 kHz until its output rate was explicit.
2. FFmpeg native Vorbis could not realize mono; the factor and claim were
   narrowed rather than bridged with mislabeled dual-mono.
3. Wrapper rewriting was double-counted in the ordinary-transform expected
   total; recipe `004` separated 36 ordinary paths from 12 wrapper paths.

Each correction was committed before the next execution. None used a
mechanism score, source waveform, or unopened label.

## Remaining gate

The exact FFmpeg analysis decoder is accepted for lossless-wrapper PCM.
Fresh equivalence with the hash-bound public LossyTrace/Symphonia decoder is
still pending, as explicitly recorded in the aggregate. It must pass on
synthetic FLAC/WAV/AIFF triplets before baseline scoring.

After that check, freeze the fractional source-to-cell assignment as a
separate record. Do not generate benchmark audio or open a partition before
both records are committed.
