# Private construction from two published scores

## Pre-render source decisions

Construct one performance each of *Confrontation* by tapatilorenzo and *radio city* by cubee. Both authors identify these as music they made and supply compact scores using only native BeepBox synthesis. The first submission declares CC0 1.0. The second declares CC BY 4.0. Preserve title, author, source, license and construction credit with the files. Both works have notes in every bar. The earlier notation review compared two decoders, inspected all instruments and checked historical artist and work labels in available metadata. The private construction uses these retained records offline. Cross-provider lineage and full historical freshness still require reconciliation before allocation. [Author's CC0 submission](https://opengameart.org/content/four-original-midi-loops) · [Author's CC BY submission](https://opengameart.org/content/random-retro-ish-music-tracks) · [Notation and provenance checks](beepbox-arrangements-20261123.md) · [Previous renderer qualification](beepbox-render-check-20261123.md)

Selection is for this construction check only. Pick the lowest source-score SHA-256 per author among complete arrangements of at least 30 seconds, passing over explicitly named remixes and the previously documented *cyborg*/*gorio* arrangement match. The source titles, durations and hashes were known at selection. Assign both works to the same BeepBox production chain. All files derived from a work share its identity. Preserve possible links to other works by either composer.

Use one playthrough, 44.1 kHz, stereo, BeepBox 4.2.0 and xorshift32 seed 20261123. Convert the synth output directly to 16-bit integer PCM using nearest-even rounding and no dither. Record clipping. Repeat each render in a fresh process. For each piece, save a direct FLAC and a FLAC for each of the six design codec settings. Use the existing pilot constructor's encoder options and decoder handling. Check early, middle and late time alignment against the direct render, without fitting a classifier or computing a verdict. This run is a private technical check with no study split assignment.

## Verified results

| Piece | Length | Stereo frames | Intermediate encodes | Quantizer clipping |
|---|---:|---:|---:|---:|
| Confrontation | 57.6 s | 2,540,160 | 6 | 0 sample values |
| radio city | 76.8 s | 3,386,880 | 6 | 0 sample values |

The direct WAV and FLAC decoded sample-for-sample to each renderer's integer PCM. All 12 codec intermediates decoded to the expected native length without trimming. Their corresponding FLACs preserved those decoded samples exactly. FFmpeg and libsndfile agreed on every sample in the 16 WAV/FLAC files. The two complete runs reproduced all output files and the construction receipt byte for byte. [Receipt with tool versions, hashes and per-file readback](beepbox-construction-20261124.json)

For each encode, compare 8,192 left-channel samples starting at one second, the midpoint, and one second before the end. Search normalized cross-correlation over integral frame offsets from −2,048 through +2,048. All 36 peaks fell at zero frames. The lowest peak correlation was 0.9986. The sign and bounds of the lag estimator were checked against five known displacements of an independently generated signal, including gain and DC offset. The result supports same-instant crops for these two native-rate sources with these encoder and decoder builds. Other processing paths, rates and files still require their own delay handling.

Together with [Island Not Found](js13k-scores-20261124.md), there are now three privately constructed finished works, with three credited composers and two synthesis engines. They have zero formal split assignments. The 12 round trips here add no independent works. The current research preflight needs at least 540 reconciled groups across four partitions before the finished-music model comparison.

## Replay

Use a new directory on schwarz. Both runs observed here end in `beepbox-authored-20261124-001` and `-002`.

```sh
set -e
base=/Volumes/schwarz/lossytrace/validation
out="$base/beepbox-authored-replay"
PYTHONPATH=.tmp/music-verdict-v1/regression-extras-20261010-001 \
  .tmp/music-verdict-v1/python-env/bin/python -B scripts/music_verdict_beepbox_authored.py \
  "$base/beepbox-project-review-20261123-001" "$out"
cmp "$out/construction.json" research/music-verdict-v1/beepbox-construction-20261124.json
diff -qr "$out" "$base/beepbox-authored-20261124-001"
```
