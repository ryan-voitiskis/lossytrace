# Lossprint software qualification plan — 2026-09-27

Scope: private software qualification of one external baseline, following the
user's approval of the [direction review](codec-history-direction-20260927.md).
This plan precedes model inference here. It is a local prospective checkpoint,
not an externally published preregistration or a real-audio detection study.

## Immutable inputs and execution choice

- Source: `maxdjohnson/lossprint` commit
  `28b72da94e596f81a0155797c32af11c6e0bfa17` (package 1.1.0).
- Acquired source archive SHA-256:
  `51b25d176e57162b2b13ffea9e24fe9ad0e0674a52fe9f997f4a7942a905d658`.
- Cargo.lock SHA-256:
  `16f15838f36ff3b6218cf3584083e5da3457c645172012a0baf5b62397a4e8e2`.
- Model: `maxdj/lossprint` v1.0 resolved to revision
  `29bd6198fb588e7a5528fa6bb2b8762324b2f6a5`.
- ONNX SHA-256:
  `ca86c67b4035485a9c1a3b3120b4a555cb7af87b4dd28837c46b297f82c48e7d`.
- Model-card SHA-256:
  `d2a61888ff994f77f616655dbf324377a02bd7a97241acdc30de67dd9a8bd751`.

Use the already installed Rust 1.98.0 explicitly, without changing the default
LossyTrace toolchain or upstream source. This exceeds the declared 1.97 minimum
but is not the upstream rust-toolchain.toml's exact 1.97.1 environment; report
that difference. Keep dependency cache, target directory and run artifacts on
the designated external research volume. Fetch locked crates first, then build
offline. Model bytes are acquired by an explicit verified URL, not by executing
an unreviewed downloader. The reviewed build script only verifies their hash.

The source license is MIT. The bound model card declares MIT, but THIRD_PARTY.md
still describes v0.7 and another checksum. Record this documentation mismatch;
private evaluation does not assert that redistribution review is complete.
No model or third-party code is added to the LossyTrace package.

## What exactly is being qualified

Use the pinned Rust implementation, not a new reimplementation of the model
card. It decodes native-rate float32 channels, computes mid/side long/short
uncentered STFTs and runs one window at a time through tract. It takes at most
six windows in the middle 92% of longer tracks, averages probability outputs,
and pools bitrate geometrically after a minimum-of-one clamp. At 15 seconds
it uses one offset, shortened window, not six full windows or padded input.

The CLI's unchanged threshold is 0.5. Its emitted word `clean` is an upstream
classification string, not an adopted LossyTrace conclusion. `ffmpeg_aac`
represents the model's entire AAC class; it does not identify an AAC encoder.
These distinctions must survive any subsequent adapter.

## Finite software checks

Run the upstream locked library/binary tests, which exercise numeric frontend,
window policy, pooling, mappings and input errors. Its four-frame WAV/AIFF/FLAC
test asserts rejection for short duration, not successful waveform equality.
The documented bundled numeric fixtures are allowed; no natural audio is used.

Then run exactly two ordered CLI replays of these 12 generated cases:

| ID | Rate / channels / seconds | Container | Expected execution |
| --- | --- | --- | --- |
| wrapper_wav | 44100 / 1 / 3 | WAV PCM16 | Complete |
| wrapper_aiff | same exact integers | AIFF PCM16 | Complete |
| wrapper_flac | same exact integers | FLAC | Complete |
| exact_window | 48000 / 2 / 14.5 | WAV PCM16 | Complete |
| offset_window | 48000 / 2 / 15 | WAV PCM16 | Complete |
| six_windows | 48000 / 2 / 20 | WAV PCM16 | Complete |
| rate_96k | 96000 / 2 / 3 | WAV PCM16 | Complete |
| rate_192k | 192000 / 2 / 3 | WAV PCM16 | Complete |
| minimum | 8000 / 1 / 2 | WAV PCM16 | Complete |
| too_short | 44100 / 1 / 1 | WAV PCM16 | Reject |
| multichannel | 44100 / 6 / 3 | WAV PCM16 | Reject |
| low_rate | 4000 / 1 / 3 | WAV PCM16 | Reject |

Each construction resets a uint32 LCG to 1 and steps
`state = (1664525 * state + 1013904223) mod 2^32` per interleaved sample;
the signed PCM16 value is `(state >> 18) - 8192`. This is a reproducible numeric
fixture, not representative music or a perceptual reference. WAV is written
with the Python standard library. The two lossless wrappers are made using
FFmpeg 9.0.2, bound by executable hash, and decoded back to PCM16 bytes to
verify exact agreement before inference. No lossy encoder is run.

Use one worker, `--jobs 1 --threshold 0.5 -o jsonl`, one exact file per command,
60 seconds per inference, 30 seconds per wrapper conversion, and at most
30 minutes for the qualification replay invocation. Build/test budget is
separate: 30 minutes, two Cargo build jobs, 8 GiB disk allowance and the
existing 15 GiB free-space reserve. The replay runner must record timeouts,
errors and every planned slot, including not-started slots after its deadline.
Do not automatically retry a scoring slot or edit a bound binary after scoring.

Acceptance: all nine eligible cases complete in both replays with finite
0-to-1 scores and valid output fields; all three ineligible cases reject for
the expected reason in both replays; paired parsed records match exactly after
removing only the input path; the three successful lossless wrappers match;
input and binary hashes remain unchanged. Hash the plan, runner, binary and
inputs in an exclusive new run directory before scoring. Retain raw logs and
scores privately, plus a sanitized aggregate. Record the actual environment.

No classification label, codec guess, bitrate estimate or threshold crossing
on these fixtures is an acceptance criterion. Their numerical replay is
software evidence only. No cross-platform equivalence is implied.

## Exit and next decision

A failure is a qualification failure, with full accounting; do not adjust
limits or select a different model against its outputs. A pass permits
preparing a bounded detector challenge protocol, not a public detector verdict.
The actual source-grouped challenge still needs exact source identities,
provenance, codec recipes, numeric gates and execution bindings before scoring.
No retained research waveform, sealed partition, listening score, user library,
outreach, spending or release is in this qualification's scope.
