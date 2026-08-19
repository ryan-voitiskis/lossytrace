# Sparse non-tonal clean-capture acquisition specification - 2026-08-19

**Status:** specification frozen; no outreach, spending, collection or audio
access is authorized.

The bounded public metadata route ended without an eligible sparse non-tonal
member after three exact descriptor failures. This document specifies the
materially different clean-capture route required before anyone is contacted or
any recording is commissioned.

One delivery contains exactly one original recorder WAV of one safe broadband
physical impulse: a balloon pop or wooden-clapper impact. Firearms, explosives,
pyrotechnics and hazardous events are excluded. The recording is 15-30 seconds
at 48 or 96 kHz, signed 24-bit integer PCM, with at least five seconds of quiet
context before and after the only salient event and at least 3 dB peak
headroom. Mono is preferred; stereo requires a complete independent chain log
for every channel.

The private delivery record must include exact member and source-group identity,
rights-holder identity, CC0 1.0 or CC BY 4.0 declaration and attribution, file
size and SHA-256, and a complete capture log: UTC time, event material and
actuation, location, microphone and channel mapping, position/orientation/
distance, recorder or interface and firmware, per-channel gain, container, and
confirmation that filters, limiters, AGC, safety tracks and processing were
disabled.

Only the original memory-card or recorder file is acceptable. Trimming,
resampling, sample-format conversion, fades, normalization, dynamics, limiting,
filtering, denoising, reverb, pitch change and sound design are all prohibited.

Acceptance remains metadata-first and fail-closed. No preview or download may
occur until every required field passes in the frozen review order. Any accepted
delivery still needs its own committed exact-member checkpoint and successful
exact-head CI before audio access. Acceptance is not descriptor evidence,
source-trait truth, perceptual truth, manifest allocation or a public verdict.

Artifacts:

- [machine-readable specification](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-clean-capture-acquisition-spec.json)
- [fail-closed validator](../../scripts/perceptual_degradation_source_trait_sparse_non_tonal_clean_capture_acquisition_spec.py)
