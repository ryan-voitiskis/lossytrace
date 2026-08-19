# Sparse non-tonal metadata search v3 plan - 2026-08-19

**Status:** frozen before query execution; no new candidate metadata or audio
has been accessed under this checkpoint.

This successor preserves both failed exact sparse candidates and the unchanged
sparse/tonal descriptor. It excludes all fifteen exact Freesound members
consumed by the earlier metadata checkpoints, including the first abstention and
the second class mismatch.

The search is limited to eight declared discovery queries and twenty exact
Freesound primary records. Discovery snippets are not evidence. Only bounded
`text/html` or `application/json` primary-record responses may be read; candidate
pages may not be browser-rendered and audio, preview players, waveform assets,
downloads and descriptor execution remain closed.

An eligible record must be a distinct five-to-sixty-second provider-original
lossless WAV with CC0 1.0 or CC BY 4.0 rights, an explicit all-channel capture
chain, and an explicit no-processing or trim-only history. Metadata must support
one broadband natural transient with surrounding recording context. This
narrower metadata proxy does not alter the frozen descriptor and cannot confirm
occupancy, spectrum, source-trait truth or perceptual truth.

The search stops at the first fully eligible exact member. A nomination remains
metadata only and requires a new committed, exact-head-green one-member
confirmation checkpoint before the original audio may be acquired.

Artifacts:

- [frozen search plan](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-metadata-search-v3-plan.json)
- [plan validator](../../scripts/perceptual_degradation_source_trait_sparse_non_tonal_metadata_search_v3.py)
