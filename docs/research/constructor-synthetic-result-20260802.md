# Factorial benchmark v2 constructor synthetic result

Date: 2026-08-02

State: 13 synthetic constructor cases are byte-identical within and across two
complete replays; no benchmark source waveform, benchmark case, feature,
score, or unopened label was read

## Replay result

The committed construction plan has SHA-256
`6f44e0f267332dea750d4a4f0239eca6ddc356a9e2f84a5a078b445c77202430`.
Both complete path-free run reports have SHA-256
`2f5b2d9ef6898edb2d5a47f26b1e403fcaac2d24742ef7a06f377daf12dff2e2`.
The attested result is
[`constructor-synthetic-observed-20260802-001.json`](../../research/sources/evidence/constructor-synthetic-observed-20260802-001.json),
with SHA-256
`0ff79ee2a54c416bb486320c295eabdff96bfffcb391edc60c7a28ae718b8590`.

Every case rendered twice inside each replay. The two complete reports are also
byte-identical. The 13 cases cover:

- negative and controlled-positive render paths;
- MP3 LAME, Shine, and BladeEnc;
- FFmpeg, Apple AudioToolbox, and FDK AAC;
- libopus and FFmpeg-native Opus;
- libvorbis and FFmpeg-native Vorbis;
- FFmpeg, Apple AudioToolbox, mpg123, opusdec, and oggdec history decoders;
- all ten PCM-transform levels; and
- FLAC, WAV, and AIFF final wrappers.

For every case, final wrapper PCM matched the exact transformed signed-s16
input under the frozen canonical analysis decoder. Final artifact, temporary
codec bitstream, source PCM, history PCM, transformed PCM, and canonical final
PCM hashes were deterministic. These are construction-plumbing facts, not
detector measurements.

## Disposition

The exact constructor has passed its synthetic gate. A separately committed
plan correction may now authorize only the deterministic 202-cell benchmark
smoke set: 108 controlled positives and 94 negatives selected without scores
across settings, decoder/codec paths, transforms, wrappers, partitions, source
formats, channels, and target rates.

The smoke must run into two separate recipe roots and produce byte-identical
private manifests and path-free reports. Full construction, feature
computation, scoring, partition opening, and external-positive generation
remain unauthorized.
