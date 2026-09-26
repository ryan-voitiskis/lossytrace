# Factorial benchmark v2 preconditioning-audit preregistration

Date: 2026-08-02

State: exact synthetic-audit plan and implementation frozen before replay;
benchmark source audio remains unread and no benchmark case, feature, score, or
unopened label is authorized

## Why this gate exists

The codec, history-decoder, PCM-transform, lossless-wrapper, and analysis-
decoder paths already have byte-identical synthetic toolchain evidence. The
passing construction-feasibility audit establishes that all 793 selected
source headers can satisfy their assigned factors. Neither result exercises
the complete source-preconditioning path that precedes both members of every
matched pair.

That path crosses three native PCM representations present in the selected
corpus—signed 16-bit, signed 24-bit, and binary32 float—and combines an
identity-hashed native-frame crop, channel treatment, optional resampling, and
final no-dither quantization. A mismatch there could create source-format or
channel artefacts shared unevenly across cells. This gate isolates that risk
without reading any benchmark waveform.

## Frozen implementation

[`preconditioning-audit-plan.json`](../../benchmarks/audio-integrity-v2/preconditioning-audit-plan.json)
binds the exact audit and reusable preconditioning modules, factor and
toolchain evidence, passing construction-feasibility result, and private tool
inventory by SHA-256.

FFmpeg `8.1.2_1` decodes the one selected lossless stream to binary64 PCM,
crops exact native sample indices, applies channel treatment, and, only when
needed, uses the already-audited 64-tap exact-rational Kaiser SWResampler with
no dither. A streaming Python boundary converts each finite binary64 sample by
its exact integer ratio to `sample * 32768`, rounds to nearest with ties to
even, saturates to signed 16-bit, and writes deterministic little-endian PCM.
No f64 audio file is materialized.

The long-source offset uses the frozen first-eight-byte SHA-256 ranking and a
modulus of `available_native_frame_starts + 1`, so the final legal start is not
excluded. Short provider windows are retained without padding or rejection.

## Synthetic coverage and stops

Six declared synthetic cases cover `pcm_s16le`, `pcm_s24le`, and `pcm_f32le`;
mono and stereo native streams; mono, stereo, identity, duplicate, and mean
channel paths; 44.1 and 48 kHz native and target rates; native-rate and
resampled paths; a bounded provider window; and a provider window longer than
12 seconds requiring the identity-hashed crop.

Every case runs twice within each complete replay. The audit stops on a header
mismatch, nonfinite sample, command failure, output disagreement, path leak,
binding change, reserve breach, or attempted benchmark-source access. Two
complete path-free reports must also be byte-identical.

Passing this audit will authorize only a successor construction recipe. It
will not itself authorize benchmark generation, feature computation, score
opening, or an external positive.
