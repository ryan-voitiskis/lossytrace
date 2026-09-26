# Factorial benchmark v2 construction correction 002

Date: 2026-08-02

State: constructor authority expanded from the frozen 202-cell smoke selection
to the complete 12,885-cell assignment before full construction; features,
scores, external positives, partition opening, and public verdicts remain
unauthorized

## Trigger

The two complete smoke roots have byte-identical sorted private manifests with
SHA-256
`5a53608613789e7411e54e877acdbf33a2fb434645255c5fb3114163764e2bad`.
Their path-free public attestation has SHA-256
`5f8e48fa58366c5259eb4e854a869cf145841f20ff7238427bd9038d91ae5615`.
All 202 cells passed fresh artifact hashing, wrapper validation, and canonical
analysis-PCM validation in both roots.

## Narrow authority change

The constructor, preconditioning module, factor levels, assignment, toolchain,
and every upstream evidence binding remain byte-for-byte unchanged. This
correction changes only the construction plan from `scope=smoke` to
`scope=full` and binds both the public smoke result and the shared private
smoke-manifest hash.

The authorized full scope is exactly the previously frozen 12,885 cells: 6,356
controlled positives and 6,529 matched negatives across 793 source groups. It
does not authorize a new source, setting, decoder, transform, wrapper, cell, or
external-positive lineage.

## Full-build contract

The full build must use one worker and the unchanged recipe-addressed,
checkpointed constructor on the external volume. Each retained artifact must
be atomically committed only after exact wrapper and canonical analysis-PCM
validation. Resume must rehash the artifact and freshly decode canonical PCM
before skipping a checkpoint.

The run stops on any binding mismatch, out-of-assignment cell, artifact or PCM
disagreement, invalid checkpoint, private-path leak, reserve breach, feature or
score read, external-positive construction, transfer-partition opening, or
public verdict. Only a path-free aggregate attestation may enter Git.

Passing this gate will establish a reproducible constructed corpus. It will not
establish detector accuracy or authorize analysis. Feature extraction and each
later evidence opening require their own frozen plans.
