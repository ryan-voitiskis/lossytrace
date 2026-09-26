# Lossprint qualification result — 2026-09-27

**Outcome: the pinned external baseline passed this bounded software
qualification. No detector-accuracy claim follows.** It is now practical to
prepare a controlled challenge without training another detector or recruiting
listeners.

The [prospective plan](lossprint-qualification-plan-20260927.md) was written
before model inference; its runner was hashed and tested before the two CLI
replays. This was local, uncommitted prospective work, not prior external
publication. [Machine-readable aggregate](../../research/baselines/lossprint/evidence/software-qualification-20260927-001.json).

## Results

| Check | Result |
| --- | --- |
| Upstream Rust library, binary and public-API tests | 28 passed |
| LossyTrace qualification-runner tests | 12 passed before replay |
| Eligible CLI calls | 18/18 completed with valid output |
| Deliberately ineligible calls | 6/6 rejected for the declared reason |
| Planned slots retained | 24/24; zero timeouts or not-started slots |
| Repeated records | Exact match after removing only the input path |
| WAV/AIFF/FLAC wrappers | Exact decoded PCM and identical parsed outputs |
| Original generated inputs, model, source bindings, tools and plan | Unchanged |

An additional post-execution test verifies that the saved aggregate still binds
the exact executed plan and runner; all 13 current runner tests pass.

The 24 slots are 12 fixture cases repeated twice, not 24 independent source
groups. There are nine eligible cases and three input-rejection cases per
replay. Fixtures exercise native-rate branches, mono/stereo, exact/offset/six
window policies and the minimum duration. They are reproducible LCG integers,
not music and not a perceptual-quality reference. No lossy codec was run.

Eligible CLI calls took 0.023–1.076 seconds including process startup. Their
combined time was 4.189 seconds, not the whole qualification wall time and not
a prediction of real-corpus throughput. The source build took approximately
8 minutes. No inference attempt was retried or its threshold changed.

## Exact implementation and environment

The source is [Lossprint commit 28b72da](https://github.com/maxdjohnson/lossprint/tree/28b72da94e596f81a0155797c32af11c6e0bfa17),
package 1.1.0. The ONNX model is v1.0 at
[Hugging Face revision 29bd619](https://huggingface.co/maxdj/lossprint/tree/29bd6198fb588e7a5528fa6bb2b8762324b2f6a5).
Acquired model bytes matched the source build script's checksum. The plan and
aggregate bind source, lockfile, model, runner and executable identities.

Execution used macOS 27.0 arm64, Rust 1.98.0 and Python 3.14.7. The already
installed Rust toolchain was selected explicitly; the upstream exact toolchain
file requests 1.97.1. This run is not a replication on that exact toolchain.
LossyTrace's own default Rust toolchain and dependencies were not changed.
FFmpeg 9.0.2 made and verified only the two lossless wrappers.

Locked dependency metadata contains 145 packages including the root, all
external dependencies from the registry, with declared licenses present.
This inventory includes target-conditional packages and is not a claim that
all 145 were linked. Fetch used an isolated cache; compilation and tests then
ran offline. The source has MIT terms and the pinned model card declares MIT.
The upstream THIRD_PARTY.md still describes v0.7 and a different model hash.
That stale notice is recorded, not silently repaired or treated as completed
redistribution clearance. No upstream code or model is added to LossyTrace.

Source, dependency cache, build outputs, generated numeric fixtures and private
logs remain on the designated external research volume. The upstream Python
CLI integration script was inspected but not run: it downloads natural MUSDB
audio. The bundled tiny decoder fixtures are documented numeric samples, and
the upstream public-API inference test generates numeric noise.

## What the actual API means

- The native Rust frontend uses a maximum of six selected windows on longer
  tracks. It does not inspect every sample for local codec-history events.
- The seven model outputs identify codec families, not arbitrary encoder
  implementations. The `ffmpeg_aac` output represents all AAC. Apple/FDK AAC
  enum names exist in the library but have no model columns and return zero.
- The CLI reports family and bitrate only above its unchanged 0.5 threshold;
  bitrate is rounded to 0.1 kb/s. Window bitrate pooling is geometric.
- The upstream `clean` string is not an adopted LossyTrace provenance claim.
  A score named probability is not automatically calibrated for our population.

These implementation facts reconcile the execution path; they do not verify
the publisher's reported accuracy or establish equivalence with the training
frontend. Same-host repeatability is not cross-platform equivalence.

## Next step

The [first challenge design](lossprint-first-challenge-design-20260927.md)
fixes a small deterministic selection from consumed development groups and
keeps all their cases, including difficult negatives. Metadata selection,
private artifact binding, runner tests and execution-head CI still precede
real-audio scoring. No sealed partition or retained waveform was opened here.
Family and bitrate correctness will be reported separately from binary
detection. No public integration, calibrated confidence, listening result,
release or broader research completion is claimed.
