# Sparse non-tonal exact-member confirmation v3 - 2026-08-19

**Status:** the exact candidate completed two frozen private descriptor replays
and abstained.

Only the provider-original Freesound sound 476736 WAV was acquired through the
official authenticated download route. Its container matched the precommitted
boundary: stereo 48 kHz signed 24-bit integer PCM, 26.745645833 seconds. No
playback occurred, one worker was used, the 15 GiB free-space reserve was
preserved and no decoded or derived PCM was retained.

The two private replay reports are byte-identical. The candidate did not
produce a supported sparse non-tonal decision on all channels under the
already-frozen descriptor, so the public terminal outcome is `abstained`. The
candidate was not replaced and no descriptor threshold changed after
observation.

An independent audit recomputed the descriptor predicates from the private
report, checked attribution and private replay identity, and verified that the
public projection contains the exact terminal result without channel
measurements, audio hashes or private paths. Those technical checks do not
assign a source trait, establish perceptual truth, allocate a source manifest
or enable a public verdict.

The negative is frozen. Three exact sparse non-tonal candidates have now failed
the unchanged descriptor: the first and third abstained, while the second
returned a class mismatch. A successor requires a separately frozen
metadata-only search and another exact-member confirmation checkpoint before
any further candidate audio is accessed.

Artifacts:

- [frozen confirmation plan](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-exact-member-confirmation-v3-plan.json)
- [public confirmation result](../../research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v3-20260819-001.json)
- [independent audit](../../research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v3-audit-20260819-001.json)
- [confirmation runner](../../scripts/perceptual_degradation_source_trait_sparse_non_tonal_exact_member_confirmation_v3.py)
- [independent validator](../../scripts/validate_perceptual_degradation_source_trait_sparse_non_tonal_exact_member_confirmation_v3.py)
