# Sparse non-tonal metadata search v4 plan - 2026-08-19

**Status:** frozen before query execution.

This metadata-only checkpoint follows three exact sparse non-tonal descriptor
negatives. It preserves the original finger-snap abstention, the gunshot class
mismatch and the thunder abstention, and excludes all twenty-six exact
Freesound records consumed by the preceding plans and searches.

The descriptor class and every threshold remain unchanged. The new metadata
proxy is narrower: a candidate must be a ten-to-sixty-second provider-original
lossless WAV of one recorded broadband physical impulse, with primary-record
support for at least three seconds of quiet context before and after the event.
The record must also establish permissive rights, every channel's exact capture
chain, natural recorded-waveform intent and an explicit transformation history
limited to none or a declared trim. Normalization, fades, denoising, dynamics,
reverb, pitch change and rendered or synthesized sound design are disallowed.

The search is bounded to eight declared discovery queries and at most twenty
distinct primary Freesound records. Discovery snippets are not evidence. Only
primary HTML or JSON text may be retrieved, with one worker, fresh temporary
storage, no retained response bodies and at least 15 GiB free disk.

Audio downloads, previews, audio elements, waveform or spectrogram assets,
candidate-page browser rendering, playback and descriptor execution remain
closed. A metadata-qualified member would require a separate committed
exact-member checkpoint before audio access. Nomination would not assign a
trait, allocate a manifest, establish perceptual truth or enable a public
verdict. A bounded negative is valid.

Artifacts:

- [frozen plan](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-metadata-search-v4-plan.json)
- [fail-closed validator](../../scripts/perceptual_degradation_source_trait_sparse_non_tonal_metadata_search_v4.py)
