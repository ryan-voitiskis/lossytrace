# Factorial benchmark v2 exact-toolchain preregistration

Date: 2026-08-02

State: exact path-free recipe frozen before expanded-setting execution; no
benchmark audio, source-to-cell assignment, mechanism feature, score, or
unopened label inspected

Superseded before a complete replay: the first execution found that recipe
`001` allowed LAME CBR-96 stereo to choose 32 kHz despite the frozen 44.1 kHz
level. See the separately committed
[`toolchain correction`](toolchain-factor-correction-20260802-001.md). The
hashes and commands below preserve the pre-observation `001` record.

## Purpose and ordering

This checkpoint turns the frozen scientific levels into executable recipes
without learning from their expanded-setting outcomes. It is deliberately
committed before those outcomes are observed. If a recipe cannot realize its
declared level, the response is a dated factor correction—not a silent flag,
encoder, rate-control, channel, or transform substitution.

The machine-readable freeze is
[`toolchain-bindings.json`](../../benchmarks/audio-integrity-v2/toolchain-bindings.json),
SHA-256
`9b860b719ba3434268e85dbd77994de6ce60deca5f07a4a6dd7d452ddc23323c`.
It binds:

- factor freeze `lossytrace-v2-factor-levels-20260802-001` at commit
  `52470b2d0e279d002b8516a7d4f862c93133ac8b`;
- the earlier ten-encoder synthetic inventory, SHA-256
  `fb497f37ade1a6db5e3d87a0f957f6c2e72433c4091679f098ab6ce07b8b8c8d`;
- all executable and linked-component hashes from that inventory;
- 48 concrete encoder settings rather than 24 unresolved mono/stereo
  templates;
- five history-decoder commands and 132 compatible setting/decoder paths;
- one exact FFmpeg-to-headerless-s16le analysis-decoder command;
- exact algorithms or commands for every frozen PCM transform; and
- deterministic FLAC, WAV, and AIFF wrapper commands.

The implementation and validator are
[`freeze-audio-integrity-v2-toolchains.py`](../../scripts/freeze-audio-integrity-v2-toolchains.py).
The older probe harness now accepts mono as well as stereo fixtures, while its
existing stereo golden remains unchanged.

## Encoder realization

Every concrete command fixes the executable, input/output positions, rate or
quality argument, target sample rate where the frontend exposes it, and
channel treatment. LAME mono/joint-stereo modes and its explicit 16 kHz
low-pass are stated rather than inferred. Native FFmpeg Ogg commands retain
the previously necessary fixed serial offsets. libopus commands bind hard CBR
and 10 or 20 ms frames. FDK explicitly binds LC, CBR mode, and bitrate.

The replay must execute each setting twice and require a byte-identical
bitstream. FFprobe must confirm codec, AAC-LC profile, rate, and channel count.
Each compatible history decoder then runs twice and must return identical PCM
within that path. Cross-decoder PCM disagreement is recorded, not treated as a
failure: the earlier anchor probe showed it is a real factor that the design
must cross.

## Bandwidth observation boundary

Nominal defaults are not reported as measured cutoffs. Each expanded setting
receives a separate 1–23 kHz segmented-tone probe, decoded through the frozen
FFmpeg path. The report records the highest probed tone retained within 6 dB
of the median 1, 4, and 8 kHz response, together with every sampled relative
level.

This is intentionally named a *coarse decoded retained-band edge*. It is not
an exact psychoacoustic filter cutoff, a guarantee about arbitrary programme
material, or evidence of prior compression. Keeping the full curve prevents a
single convenient number from concealing non-monotone behavior.

## PCM transform realization

The exact bindings remove several otherwise material degrees of freedom:

- gain uses integer Q31 multiplication, round-to-nearest ties-to-even, and
  signed-16 saturation;
- trim, leading silence, and duration operate on exact frame counts;
- mono/stereo alternation uses exact duplication or a ties-to-even arithmetic
  mean;
- 12-bit requantization consumes a domain-separated SHA-256 counter stream,
  adds a precisely defined one-LSB-peak-to-peak triangular dither, and rounds
  to multiples of 16;
- the 16 kHz low-pass is four pinned f64 biquads with the four eighth-order
  Butterworth section-Q values stated in processing order; and
- the 32 kHz round trip binds SWResampler, 64-tap Kaiser filtering, rational
  phases, cutoff, beta, intermediate/output formats, and no dither.

Each of the ten transform levels, including identity, must produce identical
WAV and PCM hashes in two executions for all four rate/channel synthetic
inputs. That is 40 transform paths. It tests plumbing only; it does not test a
mechanism representation.

## Lossless analysis and public decoder boundary

For each synthetic rate/channel input, FFmpeg writes FLAC, WAV, and AIFF twice,
then the frozen analysis decoder emits headerless signed-s16le. All 12 wrapper
paths must be deterministic and every decoded byte must equal the input PCM.

The public LossyTrace feature-version-0 decoder is a separate equivalence
boundary. The earlier 14-group, seven-domain audit found exact feature equality
across 56 FLAC/WAV/AIFF triplets. A fresh synthetic run against a hash-bound
public binary is still required before baseline scoring. It is not folded into
this preregistration because no public binary was frozen at this checkpoint;
the result must record that as pending rather than imply completion.

## Replay and storage gate

Two complete single-worker invocations must produce byte-identical public
reports. Private executable/component paths remain outside Git. The public
report may contain only declared identities, commands, hashes, synthetic
measurements, and aggregate counts. At every phase the 15 GiB free-space
reserve remains a hard stop.

The replay is authorized to create only temporary synthetic fixtures. It may
not read an allocated source, generate a benchmark case, assign a source to a
factor cell, compute a candidate feature, open a score, or authorize a public
verdict.

## Next gate

After this preregistration is committed, run two complete replays. If they are
byte-identical and every declared level is realized, commit a separate
path-free result. Then bind and check the public decoder on wrapper-equivalent
synthetic PCM before freezing the fractional assignment.
