# Single-file CNN runtime on the Apple M5

The full-resolution research CNN processed a generated five-minute file in **1.49 s warm median** across 48 runs. The nearest-rank p95 was **1.70 s**, the slowest fresh process returned its first score in **2.18 s**, and peak worker RSS was **692 MiB**. The median for WAV was 1.49 s and for FLAC 1.45 s. The forward pass took 90.5% of total warm elapsed time. These measurements cover whole-file SHA-256, decoding the chosen intervals, the prescribed frontend, 24 CNN forwards, and the file-level mean.

Each file contributed 24 four-second windows spread over its first 120 seconds, or 96 seconds of actual samples. Eight generated signals cover both supported sample rates, mono/stereo, and both bit depths. Each signal was written as WAV and FLAC and decoded in full for exact integer PCM comparison. The generator used enveloped tones, harmonics and seeded noise. The spectral and compression characteristics describe these fixtures only.

Each of the 16 wrappers started a new CPU worker, followed by three warm repetitions in that worker. The process used four intra-op threads, one inter-op thread, float32 CPU layers and one window at a time. Fresh-process time includes Python imports, fixed-seed model initialization and the first file score. Warm timing starts before whole-file hashing and ends after closing the file and aggregating window logits. Receipt serialization is outside warm timing. Files were read from schwarz with an already warm filesystem cache after generation and verification. All eight wrapper pairs produced identical file scores across all repeats. A separate readback recomputed all 16 input hashes and checked saved intervals, scores, peak RSS, median and p95 against the summary.

**Interpretation.** The CPU inference path fits the design's numerical latency and memory targets on these fixtures. The candidate used initialization weights and returned a diagnostic scalar. The release gate still needs a qualified fitted model, the packaged verdict/evidence path, and at least 30 complete five-minute music files. This test provides no accuracy or calibration evidence. [Frozen criteria](../../docs/research/music-verdict-successor-20260927.md) · [Exact results, versions and source hashes](synthetic-runtime-20261123.json)

The run directory on schwarz is `/Volumes/schwarz/lossytrace/validation/music-verdict-synthetic-runtime-20261123-001`. It contains the generated fixtures and the complete per-file receipts, including all half-open source-frame intervals. Reproduce on the same Mac with a new output directory.

```sh
PYTHONPATH=.tmp/music-verdict-v1/regression-extras-20261010-001 \
  .tmp/music-verdict-v1/python-env/bin/python -B scripts/music_verdict_runtime_probe.py \
  /Volumes/schwarz/lossytrace/validation/music-verdict-synthetic-runtime-replay-001
```
