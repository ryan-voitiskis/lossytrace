# Cost of a single-file measurement score on the Apple M5

The research comparator takes a WAV or FLAC through the Rust inspector, passes the 12 feature-v0 measurements and their missingness indicators to a fitted logistic model, and returns one raw score. The model receives no path, file hash, format, duration or reference track. The inspector reads and hashes the entire file and measures up to its first 120 seconds. Timing used the same eight five-minute generated signals, each in WAV and FLAC, as the earlier CNN benchmark. Regeneration reproduced the previously recorded file hashes, sizes and decoded PCM commitments for all 16 inputs. [Comparator measurements](comparator-runtime-20261124.json) · [CNN benchmark](synthetic-runtime-20261123.md)

| File-to-score timing | Measurement comparator | Research CNN |
|---|---:|---:|
| Warm median, 48 calls | 0.220 s | 1.488 s |
| Warm nearest-rank p95 | 0.305 s | 1.695 s |
| Slowest fresh worker to first result, 16 starts | 0.375 s | 2.184 s |

The comparator's WAV and FLAC warm medians were 0.220 s and 0.222 s. Starting the Rust process, hashing, decoding, measuring and parsing its JSON took a median 0.220 s. Checking and applying the fitted transform and logistic model took a median 0.12 ms. The Python worker reached 33.8 MiB RSS and the Rust child reached 86.0 MiB. Their sum, 119.8 MiB, is a conservative upper bound on simultaneous RSS. The CNN used a single worker with 692 MiB peak RSS.

Both measurements used the same M5 and warm filesystem cache on schwarz. The comparator inspects a continuous 120 seconds. The CNN samples 24 four-second windows over that span. Workers ran sequentially in separate benchmark sessions. Each comparator call starts a new inspector subprocess. Warm calls reuse the loaded Python checkpoint. Cold timing includes Python startup, parameter loading, the first inspector invocation, the score calculation and receipt emission.

## Parameter and replay checks

The timing model was fitted on the 42 control and codec variants of one generated 30-second signal. Only one of the 12 numeric measurements had any observations in this particular training fixture. This limits what its scores mean. Every timed call still ran the ordinary feature extractor, checked the full input schema and applied the full-width transform. The CNN timing used initialization weights. Detector accuracy and the release runtime gate on finished music remain open.

The comparator now persists its feature order, fitted imputation values, training observation mask, standardization, coefficients, intercept and solver termination in a digest-bound JSON checkpoint. Fresh-process loading reproduced all training logits exactly. Four repeats on each timed file gave identical reports and logits, and all eight WAV/FLAC pairs gave identical measurements and logits. A separate scalar readback of the retained outputs verified the 64 scores, the fitted logistic gradient, per-file hashes, analysis intervals and timing summaries. Corrupt or incompatible checkpoints fail before inference. [Comparator code](../../scripts/music_verdict_comparator.py) · [Checkpoint tests](../../scripts/tests/test_music_verdict_comparator.py)

## Reproduce

The retained output on schwarz is `lossytrace/validation/comparator-runtime-20261124-001`. It holds the generated WAV and FLAC files, synthetic training measurements, fitted checkpoint, per-file inspector reports and timing records. Use a new directory for each replay. Timings depend on machine load and cache. File hashes, fitted parameters and scores can be compared independently of timing.

```sh
cargo build --offline --release --locked
PYTHONPATH=.tmp/music-verdict-v1/regression-extras-20261010-001 \
  .tmp/music-verdict-v1/python-env/bin/python -B scripts/music_verdict_comparator_runtime.py \
  /Volumes/schwarz/lossytrace/validation/comparator-runtime-replay
```
