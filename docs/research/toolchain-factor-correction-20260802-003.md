# Factorial benchmark v2 toolchain correction 003

Date: 2026-08-02

State: replay-accounting correction frozen after one complete synthetic recipe
`003` invocation and before its second replay; no benchmark audio, source
assignment, mechanism feature, score, or unopened label inspected

## Observed stop

The first complete invocation of recipe
`lossytrace-v2-toolchain-bindings-20260802-003` produced a private path-free
aggregate with SHA-256
`b58bcb48ea6d435bc6e062d1e9418620ec96cb511b4ca13eb47a860e275dc53e`.
All 46 encoder settings, 126 decoder paths, 36 executed ordinary transform
paths, and 12 wrapper paths completed. Before starting replay 2, aggregate
review found that the recipe declared 40 expected ordinary transform paths.

The four-path difference is bookkeeping: the tenth frozen transform,
lossless-wrapper rewriting, is tested more completely in the separate
FLAC/WAV/AIFF section. Four rate/channel inputs times the other nine transform
levels equals 36 ordinary paths. The wrapper section separately contains 12
encode/decode paths. Counting wrapper rewriting in both places would be a
double count.

## Correction

Recipe `lossytrace-v2-toolchain-bindings-20260802-004` changes the expected
ordinary transform count from 40 to 36 and adds runtime assertions for:

- four transform inputs;
- 36 ordinary transform paths; and
- 12 lossless-wrapper paths.

No codec command, decoder command, transform implementation, wrapper command,
bandwidth probe, factor level, or claim boundary changes. The recipe-`003`
aggregate is not accepted as one of the required two replays because its
contract was internally inconsistent.

The corrected path-free manifest is
[`toolchain-bindings.json`](../../benchmarks/audio-integrity-v2/toolchain-bindings.json),
SHA-256
`d2af2f0b78b184189806d724c294d7606f37d2763839e17c9289f7957da52070`.

## Next gate

Run two fresh complete invocations of recipe `004`. Both reports must be
byte-identical before the toolchain result can be frozen.
