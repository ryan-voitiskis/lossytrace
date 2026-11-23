# Reproducible PCM from a generated BeepBox score

The pinned BeepBox 4.2.0 renderer produced identical stereo PCM in fresh Node processes on this Mac at both 44.1 and 48 kHz. The generated 32-second score exercises each of the eight instrument types found in the two composers' projects. Every four-second instrument section contained signal. A second complete run reproduced all eight WAV and FLAC files and the JSON receipt byte for byte. [Run receipt](beepbox-render-check-20261123.json) · [Source-project review](beepbox-arrangements-20261123.md)

The score has two intro bars, twelve loop bars played once and two outro bars. A newly initialized xorshift32 generator supplies every call to the pinned synthesizer's random function, including noise-table construction. Changing only the seed left all five pitched sections identical and changed the noise, spectrum and drumset sections at both rates. At 44.1 kHz the white-noise section changed in 132,304 of 176,400 frames. The seed belongs in the construction record for each source render. The first fixture draft accidentally gave the FM instrument silent operators. The zero-energy check caught that before any verified results were written. The retained fixture sets the FM operator levels explicitly.

The runner checks the npm package digest before loading its bundled synthesizer. It renders offline with no audio device, uses the existing integer PCM converter with nearest-even rounding and no dither, and checks for clipping. FFmpeg decoded each WAV and FLAC back to the expected integer bytes at both 16 and 24 bits. A second decoder, libsndfile, verified every sample, sample rate, channel count, bit depth and frame count. These results establish repeatability for the recorded software versions, arm64 host and generated score. Reproducibility across different software or actual authored projects remains unmeasured. [Fixture generator](../../scripts/music_verdict_beepbox_fixture.mjs) · [PCM verification](../../scripts/music_verdict_beepbox_render_check.py)

A separate metadata screen compared the 27 published arrangement names and both credited handles against the 328 pinned RWC rows and 48 metadata layers of the 24 selected private-library tracks. It found zero exact normalized artist or work-name matches in either inventory, using the earlier group audit's name normalization and slash-separated title matching. Aliases, translations and other historical collections remain unresolved. These two credits still contribute at most two candidate groups. This test generated one new score and used no third-party music or model predictions. [Historical inventory bindings and matching rules](source-group-and-transfer-audit-20261123.md)

## Replay

The verified runs on schwarz end in `beepbox-render-check-20261123-002` and `-003`. Compare the output directory from a fresh run to either one. The package and file hashes, seed, decoded PCM commitments, versions and results are in the receipt.

```sh
base=/Volumes/schwarz/lossytrace/validation
PYTHONPATH=.tmp/music-verdict-v1/regression-extras-20261010-001 \
  .tmp/music-verdict-v1/python-env/bin/python -B scripts/music_verdict_beepbox_render_check.py \
  "$base/beepbox-project-review-20261123-001/beepbox-4.2.0.tgz" \
  "$base/beepbox-render-replay-001"
diff -qr "$base/beepbox-render-check-20261123-002" "$base/beepbox-render-replay-001"
```
