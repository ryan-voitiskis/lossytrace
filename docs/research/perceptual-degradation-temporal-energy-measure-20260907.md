# Temporal energy spread and recording context — 2026-09-07

Status: a continuous technical measurement is selected and implemented for
synthetic development. Two complete captured CLI replays are byte-identical.
No sparse classifier, perceived-duration model or source assignment is selected.
The definition was written before the first synthetic execution; this checkpoint
publishes the plan and development observations together, not independent
preregistered validation.

## The decision

Separate three quantities previously at risk of being conflated: temporal energy
spread in seconds, literal nonzero support, and recording-relative occupancy.
The [rate/context audit](perceptual-degradation-descriptor-rate-context-20260905.md)
showed why recording-relative blocks cannot serve as context-invariant event
duration. The [window-support audit](perceptual-degradation-descriptor-window-support-20260905.md)
separately demonstrated that spectral support and aggregation need an explicit
definition. This checkpoint implements only the temporal part; it does not
resolve spectral bandwidth, windowing or time-local structure.

The primary literature distinguishes temporal extent, signal representation and
descriptor concept. Peeters et al. use an envelope-threshold effective-duration
descriptor, not the raw-energy quantiles defined here; their flatness descriptor
also depends on the chosen spectral representation. The paper's formula pages
were visually checked, and no empirical duration threshold or tonal cutoff is
adopted from them. [Peeters et al., 2011, pp. 2903–2908](https://brungio.github.io/GP_2011_JASA.pdf)
The historical MPEG-7 overview likewise distinguishes temporal and spectral
descriptors and their summaries; this work makes no MPEG-7 conformance claim.
[MPEG N7708, 2005](https://mpeg.chiariglione.org/standards/mpeg-7/audio.html)

## Exact definition and units

For each integer sample x[n] at rate fs, place constant squared-amplitude density
x[n]^2 on the sample cell [n/fs, (n+1)/fs). Its integral is sum(x[n]^2)/fs.
The units are integer-amplitude-squared seconds, not joules, calibrated sound
pressure, loudness or perceptual impairment. DC, carrier structure and all
background are included. There is no filtering, denoising, envelope extraction
or estimated noise-floor subtraction.

For positive total mass, t(q) is the earliest time at which integrated density
reaches fraction q of the total. Interpolation within cells is exact rational
arithmetic. On a flat cumulative plateau, use its left boundary. Report t(0.05),
t(0.25), t(0.50), t(0.75), t(0.95), plus:

- Central-90 span: t(0.95) − t(0.05), in seconds.
- Central-50 span: t(0.75) − t(0.25), in seconds.
- Raw squared-sample energy centroid, using exact sample-cell midpoints.
- First/last nonzero-cell boundaries and summed nonzero-cell duration.
- Recording duration and central-90 span divided by recording duration.

The plan's distinction between span and context-relative ratio means the span
is not divided by recording duration. It does not mean independence from which
positive-energy content the recording includes, as the background cases show.

The percent positions define summaries, not sparse/not-sparse margins. Literal
nonzero support is not detected salient activity. Empty and all-zero input
return unsupported with null quantiles, spans, centroid and support endpoints;
observed duration, zero exposure and zero nonzero-cell duration are preserved.
Silence does not become a zero-span sparse example.

Exact run-length integration and an integer-sample adapter produce the same
measure. This is a sample-cell convention, not a reconstruction of the unknown
continuous acoustic waveform. Duplicating each cell while doubling the sample
rate preserves this mathematical density; that identity does not validate a
real analog sampling or media-resampling chain.

## Declared development observations

Nine physical profiles are evaluated at 48 and 96 kHz and signed gains 1 and −2:
36 summaries. These are integer runs, not acquired or saved audio. Four profiles
reuse the consumed 1.6-second constant-interval context witnesses. The remaining
profiles separate equal-energy intervals or explicitly add positive constant
background; they are not natural captures or perceptual noise simulations.

| Construction | Record length | Literal nonzero duration | Central-90 energy span |
| --- | --- | --- | --- |
| One 1.6-second interval, zero background | 15 s | 1.6 s | 1.44 s |
| Same interval, 50 ms later | 15 s | 1.6 s | 1.44 s |
| Same interval, 15 seconds of zeros appended | 30 s | 1.6 s | 1.44 s |
| Two 0.8-second intervals starting at 6 and 18 seconds | 30 s | 1.6 s | 12.64 s |
| Interval amplitude 1,000, background amplitude 10 | 15 s | 15 s | 1.441206 s |
| Same, with 15 seconds of background appended | 30 s | 30 s | 1.442556 s |
| Interval amplitude 1,000, background amplitude 100 | 15 s | 15 s | 1.5606 s |
| Same, with 15 seconds of background appended | 30 s | 30 s | 14.5458 s |

All declared gain and exact density-refinement identities pass. Gain −2 leaves
timing and context fields unchanged while multiplying exposure by four. The
50-ms translation shifts every energy quantile by exactly 50 ms. Exact zero
append leaves the temporal measures unchanged but halves the context ratio
from 0.096 to 0.048. The bound predecessor's analytic occupancy replay retains
its original 3/2/2/1 active-block counts across the four context witnesses;
these are not fresh PCM descriptor runs or new source classifications.

Separating equal-energy intervals preserves 1.6 seconds of nonzero support but
widens the central-90 span from 1.44 to 12.64 seconds. Both have median-energy
time 6.8 seconds when the contiguous interval starts at 6 seconds. For the
separated pair this is the beginning of the intervening cumulative plateau,
not the gap midpoint. Its energy centroid is 12.4 seconds rather than 6.8.
An energy-quantile span can include silence and is neither total active duration
nor a shortest interval containing a given energy fraction.

Positive background deliberately breaks the zero-append identity. At background
amplitude 100, extending the recording moves t(0.95) from 7.5873 to 20.58 seconds.
The central-90 span then covers much of the background despite unchanged event
timing. No background is subtracted to hide this result. The levels describe
exact arithmetic constructions, not measured environmental noise, cleanliness
or audibility. A future noise-aware definition would need its own justified
measurement and validation contract.

## Numerical verification and limits

At 20 and 40 cells per second, all nine profiles and both signed gains are
expanded into small arrays. A separate numerical core directly enumerates
squared weights, cumulative masses and weighted cell midpoints. All 36 dense
checks agree exactly with run integration, the sample adapter and the high-rate
physical-time/exposure fields. These low-rate views are numerical density
analogs, not acoustic test stimuli.

The dense core does not call the run integrator or adapter, but it shares the
result-assembly/serialization function. Independent closed-form unit expectations
therefore also check nonuniform-cell quantiles, spans, centroid, exposure and
plateau ties. This is arithmetic corroboration, not an independent scientific
validation dataset or evidence that these summaries predict perception.

Twenty-three focused tests cover these identities, strict input types and
24-bit limits, silence/null handling, plan bindings, the 15-GiB reserve,
unchanged inputs, complete replay and the closed synthetic-only CLI. Two full
captured CLI outputs are byte-identical. The initial successful CLI's displayed
output was truncated; the identity claim refers to the next two complete
captures, not a comparison against unavailable initial bytes.

## Research consequence and next gate

This selects a reproducible technical quantity with explicit units and limits.
It does not justify using raw energy
spread as perceived duration, sparse-source truth, event detection or a clean
reference criterion. Background sensitivity, carrier/DC dependence and spectral
time-locality remain explicit design questions. Fresh natural evidence and
source provenance are still necessary before any trait assignment.

The frozen sparse/tonal descriptor and clean-capture specification are unchanged.
Capture authority remains valid, but the actual microphone/recorder, channel,
gain and safe physical setup still need declaration and a committed execution
checkpoint. No audio was accessed, generated, retained or played here. No metric,
human-response collection, full-reference oracle, no-reference training, outreach,
spending or public-verdict gate is opened. The overall objective remains active
and incomplete; no final research disposition is justified by this checkpoint.

```sh
python3 scripts/perceptual_degradation_temporal_energy_measure.py --synthetic
python3 -m unittest discover -s scripts/tests -p 'test_perceptual_degradation_temporal_energy_measure.py'
```

- [Declared definition and plan](../../benchmarks/perceptual-degradation-v1/temporal-energy-measure-plan.json)
- [Implementation](../../scripts/perceptual_degradation_temporal_energy_measure.py)
- [Focused tests](../../scripts/tests/test_perceptual_degradation_temporal_energy_measure.py)
- [Complete synthetic evidence](../../research/toolchains/evidence/perceptual-degradation-temporal-energy-measure-synthetic-20260907-001.json)
