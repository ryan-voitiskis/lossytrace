# Production and generation synthetic replay - 2026-08-04

**Status:** two fresh score-blind synthetic replays passed byte-for-byte;
actual audio, perceptual metrics, and listener evidence remained unopened

## Result

The implementation and synthetic-only execution plan were committed at
`9b6d2ba613e89b418030b0fedf0f6a73f7137fb7` before observation. The exact-head
CI run passed before execution. Two invocations then used separate fresh
temporary directories and produced reports with the same SHA-256:
`099b5ac6eff9a705dfa4575a55ea827d56808890b92932f4379e187854178137`.

All 12 frozen cases completed. Each of the four production controls changed
more than the preregistered `0.1%` frame-support minimum. Each of the eight
codec cases completed two stages across MP3, AAC-LC, Opus, and Vorbis. Only the
AAC-to-Opus and Opus-to-Vorbis paths invoked the exact frozen intermediate
resampler, matching their 44.1/48 kHz transitions.

## Evidence boundary

The generated PCM and encoded bitstreams were ephemeral and removed after
hashing. The full reports were moved to recoverable Trash after their hashes
and path-free aggregates were checked; they are not retained in the research
corpus. The retained evidence contains case counts, support counts, intended
transition flags, tool and implementation bindings, and the identical report
hash. It contains no source path, runtime timing, audio, score, listener
response, perceptual truth, severity label, transparency label, or codec
ranking.

This closes only deterministic synthetic recipe replay. It makes the four
production and eight multi-generation recipes eligible for future score-blind
manifest construction; it does not make any condition material, audible, or
transparent. Actual stimulus generation remains unauthorized until source
licence/attribution, mastered-music breadth, excerpt, and playback gates close.
