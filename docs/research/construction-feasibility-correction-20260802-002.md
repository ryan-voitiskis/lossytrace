# Factorial benchmark v2 construction-feasibility correction 002

Date: 2026-08-02

State: lossless-codec scope corrected after the first selected header; no
waveform sample, generated benchmark audio, feature, score, or unopened label
was inspected

Recipe `002` verified the bound source artifacts and then stopped on a selected
source whose FFprobe codec name is `pcm_f32le`. The audit had enumerated only
integer PCM names. Floating-point PCM is uncompressed PCM and is already
inside the benchmark's frozen PCM-source and deterministic s16
preconditioning scope; rejecting it would silently narrow that scope based on
an implementation whitelist omission.

Recipe `lossytrace-v2-construction-feasibility-20260802-003` therefore accepts
FFprobe codec name `flac` or any name beginning with `pcm_`, and continues to
reject every compressed lossy codec name. This changes no selected identity,
partition, assignment, duration minimum, provider window, transform, or score
boundary.

The corrected plan SHA-256 is
`661213a64da4bee2016ad46f27d8e0c02a012f4b9bce8c035516c3f0e40f5dc7`.
The corrected generator SHA-256 is
`2ed51649a7bccda1fcfbe51eebb27c86dc9aad52017b3befaaae25dfb3588cc9`.
It binds upstream checkpoint
`124f42bd9d92195be9ea7df7fa512425034f015a`.

Commit this correction before either complete replay. The same two-replay
byte-identity gate remains mandatory.
