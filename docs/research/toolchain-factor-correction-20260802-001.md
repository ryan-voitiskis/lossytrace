# Factorial benchmark v2 toolchain correction 001

Date: 2026-08-02

State: correction frozen after a capability mismatch and before any complete
expanded-setting replay; no benchmark audio, source assignment, mechanism
feature, score, or unopened label inspected

Superseded before a complete replay: recipe `002` subsequently exposed the
native-FFmpeg Vorbis mono capability boundary. Recipe `003` is documented in
[`toolchain correction 002`](toolchain-factor-correction-20260802-002.md);
this record remains the binding history for the LAME correction.

## Observed stop

Toolchain recipe `lossytrace-v2-toolchain-bindings-20260802-001` was committed
at `919e88c` before execution. Its first single-worker replay stopped during
bitstream validation of
`dev-mp3-lame-cbr96-default--stereo`:

- frozen sample rate: 44,100 Hz;
- observed FFprobe sample rate: 32,000 Hz; and
- cause: LAME 4.0 was given a 44.1 kHz WAV but no explicit output-resampling
  option, so its CBR-96 stereo preset selected 32 kHz.

The probe raised an error immediately. It emitted no aggregate, assigned no
source, and produced no retained audio. Temporary synthetic files were removed
when the failed invocation exited.

## Correction

The scientific factor remains 44.1 kHz. Recipe
`lossytrace-v2-toolchain-bindings-20260802-002` adds
`--resample 44.1` to every LAME command, including the 96/128 kbit/s CBR,
explicit-low-pass, and VBR-V2 settings in both channel treatments. Applying it
uniformly prevents sample-rate realization from depending on bitrate or
channel mode.

No other encoder, decoder, transform, wrapper, factor, or expectation changes.
The corrected path-free manifest is preserved at
[`toolchain-bindings.json` in commit `f981498`](https://github.com/ryan-voitiskis/lossytrace/blob/f981498/benchmarks/audio-integrity-v2/toolchain-bindings.json),
SHA-256
`da486f1874c802f22a67f629a60abb50989ebb0467d65ce1d1a98b07d5ea9838`.
Its validator additionally requires every LAME setting to carry the explicit
44.1 kHz option.

## Next gate

Commit this correction before restarting. Then run two complete replays of
recipe `002`; both must be byte-identical. A later mismatch requires another
dated correction rather than editing this observed record or weakening the
factor silently.
