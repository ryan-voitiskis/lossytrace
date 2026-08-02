# Factorial benchmark v2 construction preregistration

Date: 2026-08-02

State: exact constructor and synthetic-only recipe frozen before replay;
benchmark waveform decoding, benchmark case generation, features, scores, and
unopened labels remain unauthorized

## Bound engine

[`construction-plan.json`](../../benchmarks/audio-integrity-v2/construction-plan.json)
binds the constructor, source-preconditioning module, toolchain and feasibility
helpers, metadata preflight, factors, all public gate evidence, private tool
inventory, and the future private source/assignment inputs by SHA-256.

The same constructor engine is used for three authority stages:

1. synthetic glue replays only;
2. two separate deterministic 202-cell benchmark smoke roots; and
3. the full 12,885-cell build.

Only stage 1 is currently authorized. Each successor stage requires a
committed plan correction that binds the preceding path-free evidence. The
full stage additionally requires byte-identical private smoke manifests.

## Exact rendering order

Each distinct source-group, channel-treatment, and target-rate base uses the
already-replayed preconditioning module and is temporarily sealed as FLAC only
after canonical PCM equality passes.

For H0, the constructor decodes that base to signed-s16 WAV, applies exactly
the assigned PCM transform, writes the assigned FLAC/WAV/AIFF wrapper, and
streams the frozen canonical analysis decode to a PCM hash. For H1, it first
runs the exact expanded encoder setting and assigned history decoder, then
applies the same post-codec transform and wrapper checks. Thus a robustness
pair is always `H0(transform)` versus `H1(codec then transform)` from one
preconditioned source. A lossless-wrapper rewrite changes no sample.

The source WAV is removed after positive encoding; codec bitstreams are hashed
and removed after history decode; and superseded PCM is removed before wrapper
generation. Canonical analysis PCM is piped rather than materialized, keeping
at most two derived uncompressed case files live. Temporary extracted archive
members are source inputs, not retained derived cases.

## Synthetic constructor replay

Thirteen four-second fixtures cover negative and controlled-positive glue,
all ten encoder implementations, all five history decoders, all ten transform
levels, all three wrappers, mono and stereo, and 44.1/48 kHz. Every case is
rendered twice inside each complete replay. The audit compares final artifact,
codec bitstream, source PCM, history PCM, transformed PCM, and canonical final
PCM hashes. Two complete path-free reports must also match byte-for-byte.

This evidence complements, rather than duplicates, the earlier all-setting
toolchain and native-format preconditioning replays: it tests the constructor's
actual recipe ordering, temporary-file lifecycle, wrapper validation, and
analysis-decode plumbing.

## Smoke selection and checkpointing

The future 202-cell smoke set is selected without scores by the lowest frozen
cell digest independently across every expanded setting; compatible decoder
and codec; positive transform and codec; partition/transform/wrapper/
expectation combination; and native-format/channel/target-rate combination.
Deduplication leaves 108 positives and 94 negatives. Its identity remains
private until smoke authorization.

Final artifacts and checkpoints are recipe-addressed. Audio is fsynced and
atomically renamed only after wrapper and PCM validation; the private sidecar
is then atomically committed. Resume requires artifact rehashing and a fresh
canonical analysis decode before a cell may be skipped. Exact orphaned derived
artifacts without sidecars are reconstructed. Public evidence contains only
counts, byte totals, and aggregate digests.

## Stops

Any binding change, render disagreement, PCM mismatch, unbound factor,
authority expansion, private-path leak, reserve breach, feature or score read,
external-positive construction, or public verdict stops the stage. Passing
synthetic evidence authorizes only a separately committed smoke correction.
