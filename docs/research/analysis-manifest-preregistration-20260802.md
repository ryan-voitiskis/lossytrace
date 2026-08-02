# Factorial benchmark v2 analysis-manifest preregistration

Date: 2026-08-02

State: private factorial-manifest generator and two-replay recipe frozen before
execution; no feature or score authorized

## Purpose

Construction checkpoints deliberately contain exact private recipe identities
but are not the scientific schema used by the frozen
[`factorial contract`](../../benchmarks/audio-integrity-v2/factorial-contract.json).
Before analysis, this gate materializes one schema-2 private manifest that
joins the already-frozen source, partition, encoder, decoder, transform,
wrapper, recipe, and retained-artifact records.

This is metadata and byte-integrity work. It may not decode audio for analysis,
compute a feature, inspect a model output, or open a transfer score.

## Frozen implementation

The exact
[`analysis-manifest plan`](../../benchmarks/audio-integrity-v2/analysis-manifest-plan.json)
binds the
[`generator`](../../scripts/compose-audio-integrity-v2-analysis-manifest.py),
factorial contract, factor levels, toolchain, source inventory, private source
allocation, private fractional assignment, complete private constructor
manifest, and path-free full-construction result.

For each of 12,885 cells the generator must:

- rehash the retained artifact and verify its byte count;
- require exact equality between the assigned cell and checkpoint cell;
- retain only a safe recipe-relative artifact path;
- preserve source and partition groups, provenance tier, source collection and
  domain, expectation, history class, codec/encoder/decoder factors,
  post-transform, wrapper, rate, channels, frames, and matched reference;
- derive a recipe digest from the frozen cell, constructor plan and generator,
  toolchain, exact source reference, and tool IDs; and
- keep every identity, artifact hash, and relative path outside Git.

The manifest must pass structural, mechanism-development-freeze, and
encoder-transfer-freeze validation. External transfer remains negative-only;
its positive-coverage profile is intentionally not invoked before a survivor
exists.

## Replay and privacy gate

Run the exact compositor twice against the same retained artifacts into two
separate private output paths. The complete private manifests and complete
path-free reports must be byte-identical. The reports may contain only input
hashes, registry counts, partition aggregates, split checks, validation
statuses, byte totals, and set digests.

Any artifact drift, registry mismatch, failed profile, external positive,
feature or score access, path leak, public verdict, or replay difference stops
the gate. Passing authorizes only a successor feature-extraction plan.
