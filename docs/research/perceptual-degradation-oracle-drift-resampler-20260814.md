# Perceptual-degradation oracle drift resampler - 2026-08-14

**Status:** a deterministic bounded-clock-drift correction resampler passed all
nine predeclared synthetic gates and is selected as the frozen oracle
resampler. This closes the score-blind technical resampling choice. It does not
authorize or validate retained-audio correction, perceptual metrics, human
truth or collection.

## Why this successor was required

The earlier negative-control repair froze the train/held-out decision for
applying a bounded drift correction. Its linear interpolator was explicitly a
fixture helper, not the production oracle resampler. The research contract
requires every applied correction to use a frozen resampler and to record its
filter and phase behavior.

An initial pre-freeze 64-tap design screen showed only about 20 dB rejection
from 0.99 Nyquist, which was too weak for this role. No retained audio or
outcome informed that screen. The frozen successor uses 128 taps and passes a
predeclared 55 dB stopband gate.

## Frozen algorithm

`oracle-bounded-drift-kaiser-sinc128-q30-v1` is a planar-binary64,
Kaiser-windowed sinc interpolator with:

- 128 taps at offsets `-63..64`;
- 2,048 nearest phases with explicit half-up selection and carry;
- 0.95-Nyquist cutoff and Kaiser beta 9;
- signed-Q30 coefficients whose sum is exactly one at every phase;
- coefficient-table SHA-256
  `dbe4442199b56cd56880f1f45c09889721519dd7a165a4de76117b5e219dab82`;
- independent channels on one shared position grid;
- zero extension plus mandatory discard of 64 output frames at each edge when
  correction is applied; and
- a bit-exact identity bypass when drift is zero.

The mapping is `source_position = output_frame * (1 + ppm / 1,000,000)` and
is limited to the existing `+-100 ppm` alignment boundary. There is no
normalization, dither, channel mixing or perceptual computation.

## Predeclared gate result

All nine gates passed:

| Gate | Frozen limit | Observed worst case |
| --- | ---: | ---: |
| Core correlation per channel | at least 0.999999 | 0.9999999906 |
| Absolute core gain error | at most 0.001 dB | 0.000030982 dB |
| Core sample error | at most 0.002 | 0.000163054 |
| Passband ripple through 0.9 Nyquist | at most 0.001 dB | 0.000267399 dB |
| Magnitude from 0.99 Nyquist | at most -55 dB | -60.1104 dB |
| DC coefficient-sum error | 0 | 0 |
| Zero-channel leakage | 0 | 0 |
| Zero-drift output | bit-exact | bit-exact |
| Coefficient table | bound hash | matched |

The frequency response covered 128 phases, 181 passband frequencies and three
stopband frequencies. Every one of the 2,048 coefficient phases was included
in the table hash and exact-sum check.

## Independent time-domain replay

The drifted observations were sampled directly from an analytic two-channel
source-time function. The candidate resampler did not generate its own test
inputs, avoiding the earlier fixture's linear-interpolation inverse path.

| Correction | Observed frames | Output frames | Edge discard | Result |
| ---: | ---: | ---: | ---: | --- |
| +75 ppm | 96,007 | 96,000 | 64 + 64 | all gates passed |
| -60 ppm | 95,994 | 96,000 | 64 + 64 | all gates passed |
| +100 ppm | 96,009 | 96,000 | 64 + 64 | all gates passed |
| -100 ppm | 95,990 | 96,000 | 64 + 64 | all gates passed |
| 0 ppm | 96,000 | 96,000 | none | bit-exact bypass |

The boundary cases show the algorithm remains supported at the frozen limit;
the implementation rejects corrections beyond it and non-finite or malformed
channel inputs. A stereo-isolation fixture produced exactly zero leakage into
an all-zero channel.

## Determinism and boundary

Two complete fresh temporary replays were byte-identical at payload SHA-256
`a57b1844f42f695d6d82f3a4a0b1aad87a43fb4d8f57fb2ee33edcf97a9955c3`.
The report also freezes a compact, integer-derived dyadic golden-vector
input/output pair so another execution environment can detect coefficient or
numeric drift without replaying the full workload. No generated audio was
retained, and the evidence contains no path or timing.

This result selects only the technical resampler. The held-out apply decision
must still be integrated with this exact implementation, then exercised on
retained development pairs under separate authority. Until that happens,
retained-audio correction remains unexecuted and unvalidated. No human or
perceptual validity follows from the synthetic gates, and the full-reference
oracle, no-reference estimator and public verdict remain closed.

Bound artifacts:

- [`resampler freeze`](../../benchmarks/perceptual-degradation-v1/oracle-drift-resampler-freeze.json)
- [`deterministic implementation`](../../scripts/perceptual_degradation_oracle_drift_resampler.py)
- [`synthetic evidence`][evidence]

[evidence]: ../../research/toolchains/evidence/perceptual-degradation-oracle-drift-resampler-20260814-001.json
