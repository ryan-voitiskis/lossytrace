# Sparse non-tonal metadata search v3 result - 2026-08-19

**Status:** one exact metadata candidate is nominated; no candidate audio was
accessed.

All eight declared discovery queries ran. The first four-query transport batch
was retried once because its result was not surfaced to the caller; the retry
used the same strings and did not expand the discovery scope. Eleven distinct
exact Freesound records were attempted, five were inspected as text-only
primary HTML, and six timed out without yielding primary evidence. Nineteen
primary-record request attempts remained within the frozen cap of twenty. No
response body was retained.

The first fully eligible primary record was Freesound sound 476736, a
26.745-second CC0 stereo 48 kHz 24-bit WAV described as one thunder clap with
light-rain recording context, recorded through a Zoom H6 XY capsule with no
processing. The search stopped immediately after that exact record. The other
successfully inspected records failed duration, transformation, format,
licence, or single-transient requirements; timeout rows carry no inferred
metadata from discovery snippets.

This is metadata eligibility only. It does not confirm time occupancy,
spectral concentration, a source trait, perceptual truth, manifest allocation
or a public verdict. A separate one-member checkpoint must be committed and
green on exact-head CI before the exact provider original may be acquired.

Artifacts:

- [frozen search plan](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-metadata-search-v3-plan.json)
- [public search result](../../research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v3-20260819-001.json)
- [deterministic result implementation](../../scripts/perceptual_degradation_source_trait_sparse_non_tonal_metadata_search_v3_result.py)
