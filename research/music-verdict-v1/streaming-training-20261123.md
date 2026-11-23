# Streaming matched audio during CNN training

With 40 model-selection groups, 42 cases per group and 24 windows per case, the 44.1 kHz frontend would produce 157.5 GiB of float32 features. The corresponding 48 kHz figure is 171.8 GiB. Either exceeds the M5's 24 GiB of unified memory. The training reader now loads four aligned PCM windows at a time. Model selection reads one file's intervals in sequence and releases each feature tensor after use. It checks the bound SHA-256 and native header on the same open file before decoding. Re-reading and hashing files on successive passes trades disk traffic for memory. [Reader](../../scripts/music_verdict_pcm_inputs.py) · [Training loop](../../scripts/music_verdict_training.py)

Two locally generated 30-second stereo signals exercised the research CNN. One provided 48 kHz, 24-bit training material and the other provided 44.1 kHz, 16-bit selection material. Each had a baseline and six codec settings, crossed with six processing conditions. One epoch used 36 matched quartets, took three optimizer steps and scored 294 selection windows from 42 files. Input checking, training and selection took **50.37 seconds**. Peak process RSS was **4.43 GiB** across construction and fitting. These measurements cover this two-signal run. Full-corpus throughput and finished-music accuracy remain unmeasured. [Run receipt](streaming-training-20261123.json)

A separate readback checked the hashes and native headers of all 84 FLAC cases, decoded the 12 encoded intermediates, verified both baseline wraps and checked all 14 gain controls within half a PCM step. Regression tests cover WAV/FLAC window equality and exact agreement in weight updates and epoch histories between streaming and in-memory inputs on a smaller test network. The generated full-size CNN weights were discarded. The earlier single-file pilot remains the empirical performance result. [Reader tests](../../scripts/tests/test_music_verdict_pcm_inputs.py) · [Single-file pilot](../music-library-pilot-v1/single-file-interpretation-20261123.md)

The retained sources, encodes, FLACs and construction manifests are in `/Volumes/schwarz/lossytrace/validation/music-verdict-streaming-smoke-20261123-001`. To replay with the study environment and mounted drive, supply a fresh output directory.

```sh
PYTHONPATH=.tmp/music-verdict-v1/regression-extras-20261010-001 \
  .tmp/music-verdict-v1/python-env/bin/python -B scripts/music_verdict_streaming_smoke.py \
  /Volumes/schwarz/lossytrace/validation/music-verdict-streaming-replay-001
```
