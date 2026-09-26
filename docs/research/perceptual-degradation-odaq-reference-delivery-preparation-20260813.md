# ODAQ clean-reference delivery preparation - 2026-08-13

## Decision

The acquired 16-reference population cannot be sent unchanged through the
existing private browser-delivery contract. Seven files are IEEE-float WAV,
which that contract rejects, while nine use WAVE_FORMAT_EXTENSIBLE rather than
the contract's canonical integer-PCM format tag.

A synthetic-only projection is now frozen. It has no live-corpus CLI command:

- 24-bit extensible PCM is repackaged as canonical 24-bit PCM WAV with its
  sample payload unchanged;
- 32-bit float PCM is mapped to signed 32-bit integer PCM using nearest,
  ties-to-even rounding;
- non-finite samples, values below -1, and values at or above +1 stop before an
  output can be accepted; and
- sample rate, channel count, frame count, gain, normalization, dither and
  resampling remain unchanged or absent.

The float mapping loses only values finer than the signed-32 quantization grid;
it does not add random dither or apply signal-dependent gain. That is a
delivery representation rule, not evidence of perceptual equivalence.

## Synthetic evidence

Generated boundary fixtures exercised float rounding, negative full scale,
sub-LSB values, the largest float below +1, non-finite and out-of-range stops,
24-bit payload preservation, and fail-closed rate/channel/mask handling. Two
fresh projections were byte-identical at SHA-256
`27b6e8e4a72aa94ee89f42e6621762b565415f70a9e367c380efbf3659a1676e`.
Temporary WAVs were removed with their temporary directory.

No retained ODAQ file was read by this preparation. No study stimulus was
created, no processed condition or score was opened, and no listener response
was collected.

## Future private execution gate

A successor authorization must bind the exact 16-reference private inventory,
one-worker atomic output, the 15 GiB reserve, per-source and per-output hashes
and geometry, attribution record IDs, and two byte-identical fresh private
replays. Any unexpected geometry or float-domain violation stops before output
commit. Audio, paths and per-member hashes remain outside Git.

The delivery session must run at exactly 48 kHz. The RME interface was last
observed at 96 kHz, so sample-rate match is not yet qualified. Left/right
channels, quiet conditions, fixed listening position, effects-off state, and
the comfortable conservative fixed level also remain session observations for
the responsible human. Synthetic playback and the earlier “funky sounds” check
are not listening evidence.
