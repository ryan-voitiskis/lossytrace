# Sparse non-tonal exact-member confirmation v2 - 2026-08-19

**Status:** the exact candidate completed two frozen private descriptor replays
and returned a class mismatch.

Only the provider-original Freesound sound 703342 WAV was acquired through the
official authenticated download route. Its container matched the precommitted
boundary: stereo 192 kHz 32-bit IEEE-float PCM, 11.802182292 seconds. No
playback occurred, one worker was used, the 15 GiB free-space reserve was
preserved and no decoded or derived PCM was retained.

The two private replay reports are byte-identical. The candidate did not match
the already-frozen sparse non-tonal descriptor on all channels, so the public
terminal outcome is `class_mismatch`. The candidate was not replaced and no
descriptor threshold changed after observation.

An independent audit recomputed the descriptor predicates from the private
report, checked attribution and private replay identity, and verified that the
public projection contains the exact terminal result without channel
measurements, audio hashes or private paths. Those technical checks do not
assign a source trait, establish perceptual truth, allocate a source manifest
or enable a public verdict.

The negative is frozen. A successor requires a new, separately frozen
metadata-only search and another exact-member confirmation checkpoint before
any further candidate audio is accessed.

Artifacts:

- [frozen confirmation plan](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-exact-member-confirmation-v2-plan.json)
- [public confirmation result](../../research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v2-20260819-001.json)
- [independent audit](../../research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v2-audit-20260819-001.json)
- [confirmation runner](../../scripts/perceptual_degradation_source_trait_sparse_non_tonal_exact_member_confirmation_v2.py)
- [independent validator](../../scripts/validate_perceptual_degradation_source_trait_sparse_non_tonal_exact_member_confirmation_v2.py)
