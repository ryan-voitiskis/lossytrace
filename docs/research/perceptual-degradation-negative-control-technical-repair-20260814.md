# Perceptual-degradation negative-control technical repair - 2026-08-14

**Status:** four score-blind synthetic technical candidates replayed twice and
byte-identically. This closes named plumbing gaps for condition construction
and alignment decision testing. It does not select a source, listening
condition, oracle resampler, metric, study design or perceptual truth, and it
does not authorize recruitment or collection.

## Why a successor was required

The negative/control topology audit identified four specific technical gaps:

- the existing dither transform combined TPDF dither with 12-bit
  requantization, so it could not isolate dither;
- the existing resampler was used as a technical transform or metric view, not
  replayed as a standalone sample-rate-conversion candidate;
- the alignment code estimated clock drift but did not implement the contract's
  held-out-improvement decision for applying a correction; and
- leading and trailing silence had no paired support/abstention fixtures.

The historical toolchain also bound FFmpeg 8.1.2_1, but that binary is no
longer installed on this host. The locally available executable is FFmpeg 9.0
with SHA-256
`d1dffe4871ee17878b18e3f305f650265c5b06cbab8007df5bc4dccca71a672f`.
The successor therefore binds the exact new binary and full version-output
hash rather than silently claiming the historical binding.

## Isolated dither candidate

`production-isolated-s16-tpdf-1lsb-v1` deterministically derives two
independent SHA-256 counter bits per sample and adds their difference. The
resulting integer noise is in `{-1, 0, 1}` with the expected triangular shape.
It changes neither frame geometry nor nominal signed-16 bit depth.

Across 192,000 samples, 95,943 changed. The noise histogram was:

| Noise | Samples |
| ---: | ---: |
| -1 LSB | 48,081 |
| 0 LSB | 96,057 |
| +1 LSB | 47,862 |

This is an isolated deterministic dither-noise candidate. It is not a complete
high-precision-to-signed-16 quantization workflow and has no human truth.

## Sample-rate-conversion candidate

`production-src-roundtrip-48k-32k-48k-swr9-v1` converts a two-second signed-16
stereo synthetic fixture from 48 kHz to 32 kHz and back to 48 kHz. Both stages
use the exact bound FFmpeg 9.0 binary and frozen SWR settings: 64-tap filter,
exact-rational mode, Kaiser beta 9, cutoff 0.95, no interpolation, no dither and
no normalization.

The replay produced exactly 96,000 input frames, 64,000 intermediate frames
and 96,000 output frames. Input and output PCM differ, as required for a
non-identity condition, while channel count and final frame geometry are
preserved. Two fresh temporary replays produced identical hashes.

The FFmpeg 9.0 binding is a technical condition-construction successor only.
It is not selected as the oracle's production resampler and does not establish
sample-rate conversion audibility or materiality.

## Bounded clock-drift decision fixture

The successor uses a 12-second deterministic binary64 fixture, a grid from
`-100` to `+100` ppm in 5 ppm increments, and ten one-second windows. Five
alternating windows select a candidate correction; the other five decide
whether held-out alignment improved enough to apply it. Held-out windows never
participate in selection.

| Actual drift | Selected correction | Held-out before | Held-out after | Decision |
| ---: | ---: | ---: | ---: | --- |
| +75 ppm | +75 ppm | 0.8352 | 0.9970 | apply |
| -60 ppm | -60 ppm | 0.8892 | 0.9974 | apply |
| 0 ppm | 0 ppm | 1.0000 | 1.0000 | do not apply |

Correction requires a selection margin of at least `0.0001`, held-out
correlation of at least `0.99`, and held-out improvement of at least `0.05`.
The fixture's linear interpolator is deliberately marked as not being the
frozen oracle resampler. It proves the score-blind decision procedure on these
synthetic cases, not production correction, retained-audio support or
perceptual validity.

## Paired leading/trailing-silence fixtures

Both fixtures contain exact-zero leading and trailing edges around twelve
active seconds:

| Leading | Trailing | Total edge trim | Result |
| ---: | ---: | ---: | --- |
| 0.4 s | 0.6 s | 1.0 s | supported |
| 1.2 s | 1.2 s | 2.4 s | `excessive_trim` abstention |

The supported case recovers the 800-sample leading offset. The over-limit case
recovers the 2,400-sample offset and keeps the frozen `excessive_trim` reason
visible. This is structural support evidence, not proof that edge silence is
inaudible.

## Replay and boundary

The four-candidate payload was built twice in fresh temporary directories. The
canonical payload SHA-256 was identical in both runs:
`a23b329047dec2bb39115254c82128edf455ef57e85abb81447e0e6584babb8b`.
No generated audio was retained, and the evidence contains no paths or timing.

The following remain open:

- exact source-trait members and independent quiet/clipped candidates;
- selection of any production or alignment condition for listening;
- a separately bound production oracle drift resampler and retained-audio
  correction validation;
- human transparency, audibility, severity and production-control truth;
- source/domain/codec/encoder grouped transfer; and
- every no-reference eligibility gate.

The public CLI remains verdict-free. A rigorous rejection based on the
remaining scientific or resource boundary remains a successful result.

## Bound artifacts

- [`technical-repair plan`](../../benchmarks/perceptual-degradation-v1/negative-control-technical-repair-plan.json)
- [`deterministic implementation`](../../scripts/perceptual_degradation_negative_control_technical_repair.py)
- [`synthetic evidence`][evidence]

[evidence]: ../../research/toolchains/evidence/perceptual-degradation-negative-control-technical-repair-20260814-001.json
