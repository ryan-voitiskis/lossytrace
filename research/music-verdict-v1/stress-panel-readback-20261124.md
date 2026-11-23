# Native stress controls and input format regression

Two offline runs each constructed 32 FLACs from eight generated signals. They cover all combinations of mono/stereo, 44.1/48 kHz and 16/24-bit PCM. Every file, PCM hash and construction manifest matched across runs. The 12 kHz cutoff measured −3.01 dB at both rates. The quiet and sparse outputs matched independent sample-domain calculations, including the partial fade at the file boundary. Each 20-second output matched the corresponding input prefix sample for sample. The CNN interval selector rejected all eight short inputs. These checks exercise construction and duration handling. They do not measure real-file false alerts or certify a public unsupported-input path. [Frozen recipes](stress-panel-plan-20261124.md) · [Readback](stress-panel-readback-20261124.json)

The first run exposed a valid 48 kHz, 16-bit mono RIFF/WAV whose periodic test signal caused FFmpeg to guess MPEG transport stream and fail. The private constructor now reads the format from the verified input header, passes that demuxer to FFmpeg, and explicitly uses WAV for the common encoder input. The same failing file then produced six encoded streams and all 42 primary FLACs with verified PCM readback. The partly completed first run is retained. The public measurement-only CLI also read all eight source WAVs and 32 FLACs, reporting the expected input hash, native format and analyzed frame count for every file. Its ability to measure a short file is independent of the research verdict duration rule.

The two full stress runs on schwarz end in `native-stress-panel-20261124-002` and `-003`. The primary regression run is `native-stress-primary-regression-20261124-001`. The recipe was committed at `edc2e0b` before construction. Replay from this checkout into a new directory.

```sh
set -e
out=/Volumes/schwarz/lossytrace/validation/native-stress-replay
PYTHONPATH=.tmp/music-verdict-v1/regression-extras-20261010-001 \
  .tmp/music-verdict-v1/python-env/bin/python -B scripts/music_verdict_stress_smoke.py "$out"
cmp "$out/summary.json" research/music-verdict-v1/stress-panel-readback-20261124.json
diff -qr "$out" /Volumes/schwarz/lossytrace/validation/native-stress-panel-20261124-002
```
