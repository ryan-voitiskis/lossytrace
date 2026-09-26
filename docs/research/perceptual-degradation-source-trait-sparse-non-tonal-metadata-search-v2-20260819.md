# Perceptual-degradation sparse non-tonal metadata search v2 result - 2026-08-19

**Status:** bounded metadata-only search complete; one exact member nominated;
candidate audio unopened.

The frozen search executed its first four discovery queries. Nine exact
Freesound records were then retrieved sequentially as text-only HTML in
discovery order. No candidate page was rendered in a browser and no audio,
preview, waveform, spectrogram or referenced media asset was requested.

The first eight exact records were rejected for at least one frozen reason:
normalization or other processing, a disallowed licence, multiple or continuous
events, an absent all-channel capture chain, or an absent explicit
transformation history.

Record 9, Freesound sound 703342, met every metadata prerequisite:

- CC0 1.0;
- a provider WAV described as 192 kHz, 32-bit-float stereo and 11.802 seconds;
- one natural 9 mm pistol round, explicitly not assembled sound design;
- dual Shure SM58 microphones in stereo into a Zoom F3; and
- an explicit no-processing statement.

The search stopped at that record, leaving the remaining four queries
unexecuted. This is a metadata nomination only. It is not descriptor evidence,
source-trait truth, perceptual truth, relationship evidence or manifest
allocation.

Artifacts:

- [frozen search plan](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-metadata-search-v2-plan.json)
- [path-free search result](../../research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v2-20260819-001.json)
- [deterministic result implementation](../../scripts/perceptual_degradation_source_trait_sparse_non_tonal_metadata_search_v2_result.py)
