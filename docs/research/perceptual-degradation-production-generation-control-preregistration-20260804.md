# Production and generation control preregistration - 2026-08-04

**Status:** score-blind recipes frozen before implementation or audio access;
synthetic replay and all actual stimulus generation remain unauthorized

## Purpose

This preregistration fills the recipe-definition gap found by the
source/condition qualification. It does not claim that any recipe is audible,
materially degrading, transparent, representative of a codec, or suitable for
the final listening manifest. Those are later evidence questions.

The machine plan freezes four deterministic signed-16 PCM controls:

- hard clipping at `-6 dBFS`;
- a symmetric three-tap high-frequency shelf with unity DC and `-6.02 dB`
  Nyquist gain;
- a linked, five-millisecond block-lookahead limiter at `-6 dBFS`; and
- stereo-width reduction to half the original side signal while preserving
  the mid signal.

The limiter is explicitly a deterministic study control, not an emulation of
a named commercial mastering product. Every production recipe needs at least
`0.1%` changed-frame support on a future selected excerpt; insufficient
support produces `unsupported`, not an unchanged condition presented as a
control.

## Codec generations

Eight two-generation stereo paths are frozen against the already hash-bound
toolchain:

- same-setting repetition for MP3/LAME V2, AAC/FFmpeg 128 kbit/s,
  Opus/libopus 128 kbit/s, and Vorbis/libvorbis q6; and
- a balanced cross-codec cycle covering MP3 to AAC, AAC to Opus, Opus to
  Vorbis, and Vorbis to MP3.

Each intermediate encode is decoded through the bound analysis decoder and
checkpointed as signed-16 PCM before the next generation. Intermediate sample
rate transitions use the next encoder setting's exact bound command. Every
bitstream and PCM stage must be hash-recorded, while disposable bitstreams are
removed only after successful binding.

Codec name, encoder, nominal bitrate, generation count, and recipe order remain
controlled-condition metadata. They cannot become the impairment or
transparency target.

## Next gate

The next authorized step is implementation plus exactly 12 synthetic-only
cases: one for each production or generation recipe. The implementation hash
must be frozen before two fresh replays, and the two path-free reports must be
byte-identical. Retained and provider audio, perceptual metrics, listening
scores, recruitment, and human collection remain prohibited.
