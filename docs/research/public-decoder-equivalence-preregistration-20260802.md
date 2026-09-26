# Factorial benchmark v2 public-decoder equivalence preregistration

Date: 2026-08-02

State: source, build, and comparison recipe frozen before building or running
the public decoder; no benchmark audio, source assignment, mechanism feature,
score, or unopened label inspected

## Purpose

The exact-toolchain result accepts FFmpeg as the research analysis decoder and
shows byte-exact PCM across FLAC, WAV, and AIFF. The public LossyTrace CLI uses
Symphonia and downmixes to `f32` before measuring. Before baseline scoring, a
fresh check must show that container choice does not change the public
feature-version-0 evidence for identical PCM.

The machine-readable plan is
[`public-decoder-equivalence-plan.json`](../../benchmarks/audio-integrity-v2/public-decoder-equivalence-plan.json).
Its SHA-256 is
`581c76772d93019fba4d12f01dd04f95fdd5f8d51163bcd3dc45519f36f4f30b`.
It binds the public Rust source tree at commit
`397e288f79ff381711e915f9bea325c1f176e67f`, Cargo inputs, Rust/Cargo 1.94.0,
single-job locked release build, exact synthetic inputs, wrapper set, public
report projection, and stop conditions.

## Ordered gate

The work is split deliberately:

1. commit this plan and probe implementation;
2. build the public binary in a fresh target directory on a volume that does
   not spend the local 15 GiB benchmark reserve;
3. commit a path-free binding for the binary hash and linked libraries without
   running wrapper equivalence; and
4. run two complete wrapper-equivalence replays and require byte-identical
   path-free reports.

## Exact comparison

Four three-second integer PCM fixtures cross 44.1/48 kHz and mono/stereo. Each
is wrapped as FLAC, WAV, and AIFF, giving 12 paths. For every wrapper:

- the frozen FFmpeg analysis decoder must again emit signed-s16le bytes exactly
  equal to the input PCM;
- the hash-bound public CLI runs twice and must emit identical JSON; and
- the comparison removes only the input-container hash, codec debug label, and
  extension, then requires every remaining field to match exactly across the
  three wrappers.

The exact projection retains analyzed sample count and duration, truncation,
sample rate, channel count, declared bit depth, verdict state, and the complete
compression-trace object. This tests the actual public behavior rather than
claiming sample-level identity from an API that does not expose decoded PCM.

Passing is container/decoder plumbing evidence only. It says nothing about
whether any compression-history measurement is accurate.
