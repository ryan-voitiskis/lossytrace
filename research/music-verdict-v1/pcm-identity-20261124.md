# Exact audio identity across lossless containers

The four previously constructed works supplied 27 distinct files for this check: four direct WAVs, their four lossless FLAC counterparts and 19 FLACs made by decoding known encodes. All 27 file hashes differ. Two independent decoders found **23 distinct PCM signals**. Adding the documented source-work links gives **four groups**. Exact PCM identity catches alternate wrappers. Other renders, mastering changes, edits and codec-derived copies still require source-work or session evidence. Different PCM digests cannot establish independence. [Readback by work and construction](pcm-identity-20261124.json)

Private inventory schema 3 adds `canonical_pcm_sha256` to each selected source. A historical identity reference can carry an existing commitment or null when unavailable. No historical audio is needed to read the inventory. The audit joins exact signal matches across aliases, checks for cross-partition membership and propagates the existing consumed/sealed copy restrictions. A single file digest paired with two known, different PCM commitments fails preflight. Version 1 and 2 inventories retain their earlier semantics. This change concerns split integrity and makes no estimate of detector accuracy. [Metadata checker](../../scripts/music_verdict_study.py)

The identity digest starts with the ASCII string `lossytrace:music-verdict-v1:native-s32le:v1` and one zero byte, followed by little-endian unsigned 32-bit sample rate, unsigned 16-bit channel count, and unsigned 64-bit frame count. The remaining bytes are interleaved, little-endian, full-scale signed 32-bit samples, in file channel order. Exact lossless 16-to-24-bit promotion has the same digest. A changed sample, channel layout or sample rate changes the input to the hash. The reader accepts supported native PCM subtypes and streams the complete file. Eligibility, including the minimum duration, remains a separate source check. [File reader](../../scripts/music_verdict_pcm_identity.py)

The retained 27-file readback used libsndfile and FFmpeg, verified the historical file and native sample commitments, and compared the two complete canonical streams by digest. Generated regression checks also cover depth promotion, a one-bit change in a 24-bit sample, channel swaps, rate/layout changes and the end of a partial decoding block. The inspector's file hashes and public output are unchanged.

```sh
set -e
PYTHONPATH=.tmp/music-verdict-v1/regression-extras-20261010-001 \
  .tmp/music-verdict-v1/python-env/bin/python -B scripts/music_verdict_pcm_identity_readback.py \
  /Volumes/schwarz/lossytrace/validation | cmp - research/music-verdict-v1/pcm-identity-20261124.json
```
