# Perceptual-degradation sparse non-tonal exact-member confirmation v2 - 2026-08-19

**Status:** frozen before Freesound sound 703342 is downloaded or measured.

This checkpoint binds the bounded metadata result, the previous Freesound
abstention, and the already-frozen sparse/tonal descriptor implementation and
thresholds. Only sound 703342 may be acquired, using the official authenticated
Freesound original-download control. The page may not be played.

The expected original is an 11.802-second, 192 kHz, stereo, 32-bit IEEE-float
WAV. The runner rejects integer PCM, non-finite float samples, unexpected
geometry, out-of-bound duration, malformed RIFF data and files above the frozen
25 MiB limit. Direct IEEE-float and WAVE_FORMAT_EXTENSIBLE parsing, the frozen
sparse non-tonal fixture, replay plumbing and public redaction all have focused
synthetic tests.

The live run uses one worker, verifies the 15 GiB reserve, uses fresh temporary
directories, performs two byte-identical private replays, and retains no
decoded or derived PCM. The retained private reports contain the source hashes,
container and channel measurements; the public projection contains only the
terminal checkpoint outcome and excludes those details, private paths, audio
and provider scores.

Abstention or class mismatch is a valid negative. Neither permits replacement
inside this checkpoint or a threshold change. Codec generation, perceptual
metrics, playback, listening, sealed evidence, trait assignment, manifest
allocation, no-reference training and public verdicts remain closed.

Artifacts:

- [frozen confirmation plan](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-exact-member-confirmation-v2-plan.json)
- [one-worker confirmation runner](../../scripts/perceptual_degradation_source_trait_sparse_non_tonal_exact_member_confirmation_v2.py)
