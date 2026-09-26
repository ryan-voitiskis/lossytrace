# Factorial benchmark v2 construction-preflight preregistration

Date: 2026-08-02

State: exact metadata-only preflight frozen before private replay; benchmark
waveforms, codec outputs, features, scores, and unopened labels remain unread

## Purpose

The assignment, header feasibility, toolchain, wrapper decoder, and source-
preconditioning boundaries now have independently frozen, byte-identical
evidence. The remaining pre-construction questions are whether every private
cell still has complete executable lineage and whether the intended external
volume can retain the whole 12,885-cell benchmark without violating the 15 GiB
reserve.

[`construction-preflight-plan.json`](../../benchmarks/audio-integrity-v2/construction-preflight-plan.json)
binds the exact source allocation, candidate index, recipe-`004` assignment,
private and public feasibility evidence, synthetic preconditioning result,
factor and toolchain evidence, decoder result, tool-path inventory, and
preflight generator by SHA-256.

## Lineage checks

The preflight requires 793 source groups, 6,356 controlled positives, 6,529
negative/reference cells, and a still-uninstantiated 100-group external
positive reserve. Every positive must resolve to its exact matched H0 on source
group, channel treatment, target sample rate, transform, and wrapper. Every
generated H0/H1 must also resolve to its untransformed identity PCM recipe
source. No recipe may point across an evidence partition or outside the frozen
factor and toolchain levels.

These checks consume identities and header counts only. They do not decode a
source, invoke an encoder, or calculate a signal statistic.

## Storage upper bound

The retained-size calculation is intentionally conservative. For each cell it
ceil-rescales the already-bound excerpt frame count, adds 128 frames to a
preconditioning resample, adds 4,096 frames to every positive for codec and
history-decoder padding, applies the transform's duration/channel upper bound,
and adds wrapper overhead. FLAC is budgeted at 110% of raw s16 PCM plus 1 MiB;
WAV and AIFF receive 1 MiB above raw PCM. Roundtrip resampling receives two
128-frame tails.

The selected output volume passes only if it can retain that sum plus 2 GiB of
one-worker workspace and the 15 GiB reserve. Exact ambient free bytes are not
reported, because they would make otherwise identical replay evidence drift.

## Checkpoint contract

The successor constructor must use recipe-addressed artifacts, same-filesystem
temporary files and atomic renames, and a private sidecar written only after
the final wrapper and canonical analysis-decoded PCM have been validated. A
resume may skip a cell only after rechecking every plan/recipe binding, byte
count, and hash. Codec bitstreams and unwrapped PCM remain one-cell temporaries.
The final private manifest stays outside Git; public evidence excludes cell,
source, member, artifact, and machine-path identities.

Two complete path-free preflight reports must be byte-identical. Passing this
gate authorizes implementation and freezing of the constructor, not benchmark
audio generation by the preflight itself.
