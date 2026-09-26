# Sparse non-tonal exact-member confirmation v3 plan - 2026-08-19

**Status:** frozen before provider-original acquisition; the candidate audio is
unopened.

This checkpoint binds only Freesound sound 476736 and its expected
provider-original container: stereo 48 kHz signed 24-bit integer PCM WAV,
26.700–26.800 seconds and at most 10 MiB. The parser supports direct and
extensible 24-bit integer PCM and rejects other formats, channel geometry,
duration or encoded size.

After this plan passes exact-head CI, the exact original may be obtained only
through the official authenticated download route. The already-frozen
sparse/tonal descriptor will run twice with one worker in fresh temporary
directories. All supported channels must independently pass the sparse
non-tonal class. The two private reports must be byte-identical, attribution
must be attached, and decoded or derived PCM must not be retained.

The public projection contains only the exact member, terminal outcome and
bounded execution/claim metadata. Channel measurements, encoded and PCM hashes,
private paths, provider scores and processed conditions remain private.
Abstention or class mismatch is a frozen negative: no candidate substitution,
threshold change, trait assignment or manifest allocation is permitted inside
this checkpoint.

Artifacts:

- [frozen confirmation plan](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-exact-member-confirmation-v3-plan.json)
- [confirmation runner](../../scripts/perceptual_degradation_source_trait_sparse_non_tonal_exact_member_confirmation_v3.py)
- [focused tests](../../scripts/tests/test_perceptual_degradation_source_trait_sparse_non_tonal_exact_member_confirmation_v3.py)
