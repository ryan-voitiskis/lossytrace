# Sparse non-tonal metadata search v4 result - 2026-08-19

**Status:** bounded negative; no eligible exact member was found.

The search ran only after exact-head CI passed for the frozen v4 checkpoint.
All eight declared discovery queries executed in two batches without retry. The
first four returned no discovery records. The second batch surfaced three
distinct exact Freesound records plus one duplicate short URL. All three exact
primary pages were retrieved as text-only HTML in discovery order.

Both dobroide firecracker records were shorter than five seconds, supplied
FLAC rather than provider-original WAV, and did not document an exact capture
chain, transformation history, or quiet context before and after the event.
The qubodup record was a sub-second designed gunshot assembled from multiple
sources with fade, amplification and compression, and also lacked the required
capture and quiet-context record. All were rejected before audio access.

The search used three of the twenty allowed distinct primary records. No
candidate page was browser-rendered; no preview, waveform, media asset,
download, playback or descriptor was accessed; no response body was retained.
The result nominates no exact member, assigns no trait, changes no threshold,
allocates no manifest and enables no public verdict.

Repeating the same metadata-only route is not justified by this checkpoint. A
next source step must be materially different and separately authorized, such
as controlled source construction or recording with independent trait
adjudication. Alternatively, source-manifest feasibility can terminate as a
rigorous negative.

Artifacts:

- [frozen plan](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-metadata-search-v4-plan.json)
- [public result](../../research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v4-20260819-001.json)
- [deterministic result implementation](../../scripts/perceptual_degradation_source_trait_sparse_non_tonal_metadata_search_v4_result.py)
