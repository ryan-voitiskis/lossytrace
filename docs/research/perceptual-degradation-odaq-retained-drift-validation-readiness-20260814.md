# ODAQ retained-reference drift-validation readiness - 2026-08-14

**Status:** the score-blind real-content technical-validation protocol and its
narrow successor-authorization schema are frozen. All nine metadata-only
readiness gates pass. No retained reference was read or projected, no live
runner was implemented, and no synthetic drift, metric, playback, response,
model training or public verdict was produced.

## Frozen validation population

The protocol binds the exact acquired ODAQ clean-reference inventory:

- 16 stereo sources at 48 kHz;
- 54,633,154 retained source bytes under aggregate inventory SHA-256
  `d7f244da55b510b639300d55271b1ebd5fb9f7454b258bec30588bf18eefde2f`;
- seven float32 WAVs and nine extensible 24-bit integer WAVs;
- at least 360,701 frames per reference; and
- all 16 attribution notices ready, with no unresolved source.

The existing synthetic-only canonical projection covers both source geometries
without gain, normalization, dither, resampling or channel transformation. The
protocol uses only the first 288,000 frames, so its six-second analysis segment
fits every acquired reference. This is a metadata conclusion, not a retained
audio observation.

## Predeclared technical replay

If separately authorized, the future run contains 112 cases: seven controlled
drifts for each of 16 clean references. Candidate selection uses five fixed
training windows; five disjoint windows decide whether correction is worth
applying. A reference-energy mask is fixed independently of the candidate, and
each channel needs at least three eligible windows in both partitions or the
case abstains with `insufficient_signal_support`.

For supported nonzero cases, each drift requires at least 12 supported sources,
an estimate within 5 ppm, and at least 95% correct estimates overall. Every
applied case must satisfy the frozen held-out rule, reach at least 0.999
post-correction core correlation per channel, and improve each channel by at
least 0.01. Non-applied output must be bit-exact, zero drift may never be
falsely applied, every abstention needs a predeclared reason, and the score-free
oracle must remain execution-blocked.

Two fresh executions must yield byte-identical public reports. Derived PCM is
temporary and in-memory only. Public evidence excludes private paths,
per-reference hashes and audio.

## Authorization boundary

The schema permits only a future responsible-human record that authorizes the
exact clean inventory, in-memory canonical projection, frozen controlled-drift
cases and technical estimator/correction path. It keeps ODAQ processed
conditions and scores, actual codec generation, perceptual metrics, playback,
ratings, listener collection, sealed evidence, no-reference training, final
validation and public verdicts false.

The plan cannot self-authorize. A live retained-audio runner must not be
implemented until the exact successor authorization is committed and passes
exact-head CI.

The readiness report binds plan SHA-256
`c91f27e5a448bfe387b913f5240cb0d6f86f3a0e5e79cfaecf7f74d94497e48b`
and implementation SHA-256
`a061e91fb6747770aa1ede1a73124fb5892b729082f2c8e20660c2666bf72c8b`.
The committed report SHA-256 is
`0dd7af1f64eaeda41287fba319ec13423443f7bedc7c33917fd7bba1483f2da2`.

Machine-readable artifacts:

- [`execution plan`](../../benchmarks/perceptual-degradation-v1/odaq-retained-drift-validation-execution-plan.json)
- [`authorization schema`](../../benchmarks/perceptual-degradation-v1/odaq-retained-drift-validation-authorization.schema.json)
- [`readiness report`](../../research/toolchains/evidence/perceptual-degradation-odaq-retained-drift-validation-readiness-20260814-001.json)
- [`pure validator`](../../scripts/perceptual_degradation_odaq_retained_drift_validation_readiness.py)
- [`mutation tests`](../../scripts/tests/test_perceptual_degradation_odaq_retained_drift_validation_readiness.py)
