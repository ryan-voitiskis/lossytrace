# Sparse non-tonal clean-capture metadata intake gate - 2026-08-19

**Status:** implemented and synthetically validated; live delivery acceptance
remains closed.

The frozen clean-capture specification now has a deterministic metadata-first
intake implementation. It validates eight ordered gate groups before any future
audio access:

1. rights and attribution;
2. exact member and source-group identity;
3. original-WAV lineage;
4. complete per-channel capture chain;
5. empty transformation history;
6. frozen container, duration and headroom bounds;
7. quiet margins and the single-event declaration; and
8. the safe non-hazardous event declaration.

The committed synthetic fixture passes all eight gates. Tamper tests reject
disallowed processing, short duration, insufficient headroom, insufficient
quiet context, an unsafe event, disallowed rights, missing channel metadata,
absolute paths, malformed nested objects, opened authority and changed binding
hashes. Running the command without `--synthetic` fails closed because live
delivery acceptance has not been authorized.

The public synthetic result exposes only aggregate gate status. It contains no
rights-holder identity, location, channel details, filename or declared audio
hash, and the implementation never attempts to open an audio file. A synthetic
pass is not a live delivery, audio-integrity verification, descriptor evidence,
source-trait truth, perceptual truth or manifest allocation.

A future live delivery must remain private and outside Git. It requires a new
committed authorization checkpoint before its metadata is read. Even a passing
live metadata record would still require a separate exact-member checkpoint and
successful exact-head CI before any preview, download or audio access.

Artifacts:

- [frozen intake plan](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-clean-capture-intake-plan.json)
- [intake implementation](../../scripts/perceptual_degradation_source_trait_sparse_non_tonal_clean_capture_intake.py)
- [synthetic fixture](../../scripts/tests/fixtures/clean_capture_intake_valid_synthetic.json)
- [aggregate synthetic result](../../research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-clean-capture-intake-synthetic-20260819-001.json)
