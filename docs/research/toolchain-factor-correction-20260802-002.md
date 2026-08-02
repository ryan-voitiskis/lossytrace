# Factorial benchmark v2 toolchain correction 002

Date: 2026-08-02

State: corrected exact recipe frozen after factor correction commit
`cb2f75434c8918089ac8f861c087758c5d2260bd` and before execution; no complete
replay, benchmark audio, source assignment, mechanism feature, score, or
unopened label inspected

Superseded after its first complete replay: recipe `003` double-counted
lossless-wrapper rewriting in its expected ordinary-transform total. The
commands and algorithms were unchanged in
[`toolchain correction 003`](toolchain-factor-correction-20260802-003.md).

## Binding

This record supersedes toolchain recipe `002` after the independently committed
[`Vorbis factor correction`](factor-level-correction-20260802-001.md). Recipe
`lossytrace-v2-toolchain-bindings-20260802-003` binds:

- factor freeze `lossytrace-v2-factor-levels-20260802-002`, SHA-256
  `4065553ef4fbe505ea0d79b149570bc1483396dbcc1de52597890e61f59481bd`;
- the factor correction commit
  `cb2f75434c8918089ac8f861c087758c5d2260bd`;
- all 32 development settings;
- 14 encoder-transfer settings, with only the two FFmpeg-native Vorbis stereo
  settings present;
- 126 compatible history-decoder paths; and
- the unchanged transform, wrapper, analysis-decoder, bandwidth-observation,
  binary, component, and storage bindings from recipe `002`.

The current path-free manifest is
[`toolchain-bindings.json`](../../benchmarks/audio-integrity-v2/toolchain-bindings.json),
SHA-256
`f804c0528a0f93cad6d5fb7a0001f384e16767627b91885f4457c4792b295b7e`.
Its validator requires exactly two FFmpeg-native Vorbis rows, both stereo, so a
future generator cannot accidentally restore an unrealizable or mislabeled
mono row.

## Scientific boundary

The correction removes an impossible interaction; it does not turn missing
coverage into positive evidence. Encoder-transfer results for Vorbis must be
reported as stereo-only. Mono/stereo transfer comparisons remain available
for MP3, AAC-LC, and Opus, and development Vorbis still covers both channels.

No command was selected using a codec-history score. The only observations
used were declared tool capabilities and deterministic plumbing failures.

## Next gate

Run recipe `003` twice with one low-priority worker. Both complete path-free
reports must be byte-identical. Any further setting, decoder, transform, or
wrapper mismatch stops for another committed correction.
