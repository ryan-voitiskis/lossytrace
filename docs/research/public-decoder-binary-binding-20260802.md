# Factorial benchmark v2 public-decoder binary binding

Date: 2026-08-02

State: public binary frozen after the preregistered build and before wrapper
equivalence; no benchmark audio, source assignment, mechanism feature, score,
or unopened label inspected

## Binding

The path-free binding is
[`public-decoder-binary-binding.json`](../../benchmarks/audio-integrity-v2/public-decoder-binary-binding.json),
SHA-256
`da2b4844498b529f2379585036fad0a13da4b7dab9fa4aee076acc8772ac412d`.

The preregistered locked, single-job release build produced:

- version: `lossytrace 0.1.0-alpha.1`;
- binary SHA-256:
  `af8bd1389f55325a01ad7ebd48d2ad050a3f8028dccd6ee69262548028d54cb4`;
- byte count: 3,242,160; and
- dynamic dependency: the bound macOS `libSystem` only.

The binding also repeats the exact Rust source tree, Cargo inputs, Rust/Cargo
versions, build command/environment, plan hash, public-decoder probe hash, and
base synthetic-generator hash. The private target directory is deliberately
absent.

The build ran on an attached volume. macOS nevertheless reported the local
data volume below the frozen reserve afterward, so execution paused. Clearing
only Homebrew's re-downloadable download cache restored the reserve before any
probe. No source, corpus, tool binary, or evidence artifact was removed.

## Next gate

The binary binding is immutable for this check. Run two complete synthetic
equivalence replays against this exact binary and the already-bound FFmpeg.
Both public path-free reports must be byte-identical before fractional
assignment begins.
