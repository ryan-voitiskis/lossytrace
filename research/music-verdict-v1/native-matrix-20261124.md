# Native mono construction and frame alignment

Four generated mono sources exercised all combinations of 44.1/48 kHz and 16/24-bit PCM. Each ran slightly over 30 seconds. Each produced six controls and 36 encoded FLACs. A fifth matrix applied −6 dB to the 48 kHz, 24-bit source before encoding and then repeated the same six postprocessing conditions. It retained the original group and received a distinct PCM identity for matching crops. This yielded **210 verified FLACs from four signals**. The work used no finished-music scores, model fitting or listening. [Run receipt](native-matrix-20261124.json) · [Frozen construction requirements](../../docs/research/music-verdict-successor-20260927.md)

The private constructor accepts a bound source WAV or FLAC, verifies its native format and writes a common PCM input for every encoder. Its manifest records input and output hashes, actual bitrate from packet bytes and durations, decoder and resampler tail removals, and the processing applied on both sides of the encode. Preprocessing the common input is available on training sources only. Allocation, historical freshness, rights and execution freeze remain caller responsibilities. [Constructor](../../scripts/music_verdict_construction.py)

## A frame-count failure at ordinary track lengths

The previous resampling recipe required FFmpeg's two sample-rate conversions to produce exactly the starting frame count. Whole-second inputs passed. For the pinned FFmpeg build, we exercised all 147 source-length residues at 44.1 kHz and all 160 at 48 kHz by adding zero through 146 or 159 frames to a one-second input.

| Starting rate | Exact length | One extra frame | Two extra frames |
|---|---:|---:|---:|
| 44.1 kHz | 14 | 133 | 0 |
| 48 kHz | 14 | 134 | 12 |

For the new recipe the output interval is the original half-open native frame range. Only the resampling condition can discard up to two surplus frames at the end. A short result, a larger excess or a length change in any other processing condition fails construction. Existing pilot callers retain their original strict length check. Both classes traverse the same postprocessing code.

## Independent checks

- FFmpeg and libsndfile agreed sample-for-sample on all 210 mono FLACs. Every encoded intermediate retained one channel and the native sample rate. All files decoded to their original frame count. The TPDF condition produced 16-bit PCM at either source depth.
- Early, middle and late comparisons across six codec identities and seven resampling paths per matrix gave **195 zero-frame correlation lags**. The frontend's side channel was exactly zero in every mono quartet inspected. Sample-domain arithmetic independently reproduced both the pre-encode gain and the post-encode gain for every codec state.
- MP3 packet means rounded to the three selected rates. AAC-LC requested at 256 kb/s averaged **203.19–236.73 kb/s** across the five matrices. The 48 kHz, 24-bit signal averaged 219.41 kb/s directly and 236.73 kb/s after pre-encode gain. These measurements describe the generated packet payloads and counts, including packets at the stream boundaries. The requested encoder setting and the measured mean are recorded separately.
- Two full mono constructions reproduced all intermediate files, FLACs and per-source manifests byte for byte. Replaying the earlier two stereo signals through the new constructor reproduced all 84 historical FLAC hashes and all 12 intermediate hashes. The earlier receipts and their original code bindings are preserved at their recorded revisions.

The study still requires independently grouped finished music and the execution freeze. These checks qualify the construction mechanics on the tested inputs.

## Replay

Retained mono runs on schwarz end in `native-mono-matrix-20261124-001` and `-002`. The second run adds the full resampling-alignment and rate-residue readback. Stereo comparisons are in `native-stereo-replay-20261124-001`. Use a new output directory.

```sh
set -e
base=/Volumes/schwarz/lossytrace/validation
out="$base/native-mono-replay"
PYTHONPATH=.tmp/music-verdict-v1/regression-extras-20261010-001 \
  .tmp/music-verdict-v1/python-env/bin/python -B scripts/music_verdict_native_matrix.py "$out"
cmp "$out/summary.json" research/music-verdict-v1/native-matrix-20261124.json
diff -qr "$out" "$base/native-mono-matrix-20261124-002"
```
