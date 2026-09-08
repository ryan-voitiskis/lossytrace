# Native local-search qualification — 2026-09-08

The separately versioned v4 aligner completed the declared full-size synthetic
identity within 180 seconds in both rounds. The frozen v3 runtime failure remains
unchanged. This clears a synthetic per-case execution gate, not the codec pipeline
or perceptual research gates.

## Observed result

The [frozen protocol](../../benchmarks/perceptual-degradation-v1/alignment-native-qualification-plan-20260908.json)
was committed locally at `86011997b57659a64a7b5c8a11c248c9a26717ee` before
full-size observation. It was not externally preregistered. One execution ran
the four fixed cases twice, in fresh processes with one worker, 576,008 frames,
stereo at 48 kHz, a 180-second alignment deadline and a 210-second worker limit.
Inputs were constructed immutable arrays. No waveform files were accessed.

| Case | Round 1 seconds | Round 2 seconds | Technical outcome |
| --- | ---: | ---: | --- |
| Identity, uninstrumented | 118.043073 | 118.150284 | Completed, supported alignment |
| Identity, instrumented | 120.457561 | 118.441310 | Completed, supported alignment |
| Constant envelope | 0.955479 | 0.954081 | Unsupported: undefined envelope correlation |
| Stereo versus mono | 0.000066 | 0.000153 | Unsupported: topology/map mismatch |

All completed alignment records are byte-identical across rounds. Baseline and
instrumented identity records are also byte-identical within each round. Clock
values differ and are not required to repeat. Instrumented-minus-baseline times
are not an isolated measurement of wrapper overhead: order and host variation
were not controlled for that inference.

Every identity completed both channels with zero lag/drift, 12 active seconds and
all 24 valid local windows. Each evaluated exactly:

- 14 structural searches × 9,601 candidates, each sampling 24,000 frames;
- 10 drift searches × 121 candidates, each sampling a 48,000-frame window at stride 2;
- 135,624 native candidates total, with zero Python fallback.

The signed correlation and support machinery still distinguish valid negative
correlations, numerical invalidity and unsupported comparisons. The controls
retained their expected reasons and null common summaries. A supported alignment
is not a perceptual-quality judgment.

## What changed, and what did not

[V4](../../scripts/perceptual_degradation_alignment_v4.py) is an isolated successor,
not a patch to frozen v3. Function/class AST checks establish that only the local
search function changed; the record version tag also changes. Scientific limits,
candidate order and tie selection, invalidity precedence, sampling stride,
window geometry and final support classification remain unchanged.

The opt-in [bridge](../../scripts/perceptual_degradation_correlation_native.py)
hoists invariant reference-window work. The small [C kernel](../../scripts/perceptual_degradation_correlation_native.c)
evaluates every candidate with bounded accurate sums. Its finite partial-sum
helpers adapt [CPython 3.14.7's math.fsum implementation](https://github.com/python/cpython/blob/v3.14.7/Modules/mathmodule.c),
with the [PSF license and change notice retained](../../research/licenses/alignment-kernel-PSF-LICENSE.txt).
Compilation disables fast math and floating-point contraction. Python retains
the final square roots, division, clamping and lag selection. No FFT, approximate
pruning, reduced search radius or changed decimation is introduced.

The native path accepts exact-float lists/tuples under checked binary64,
round-to-nearest and subnormal conditions. Other inputs and internal capacity or
environment failures retain Python fallback semantics. The native library is
explicitly built and installed by the synthetic runner, never on module import
or through the public CLI.

Before full-size execution, 16 equivalence tests and 11 qualification-boundary
tests passed. Exact candidate records and full small-alignment records were
compared with zero tolerance, including random and extreme finite inputs,
subnormals, cancellation and half-even rounding, polarity, silence, invalid
values, stride boundaries, clipped windows, exact/near ties, threshold neighbors,
integer fallback, dropout, delay and unchanged inputs. These are finite tests and
algorithm checks, not a proof for every input or platform. A complete full-size
v3 identity record remains unavailable because the predecessor timed out.

## Remaining cost and research implications

Structural local search still took **82.733 and 82.715 seconds**, or **68.68% and
69.84%** of complete instrumented alignment time. Sample correlation took 35.227
and 33.252 seconds. The new local-search stage includes bridge/bookkeeping work;
it is not directly interchangeable with v3's correlation-only stage. The prior
180-second observations were censored, so no exact total speedup is claimed.

Per-case completion is not cohort throughput. If 160 cases each cost approximately
118 seconds, alignment alone would take about 5.2 hours, beyond the previous
one-hour replay cutoff. This is a conditional planning calculation, not a measured
codec/source throughput estimate. Repeating the full earlier study now would not
be justified by this result alone.

Next is a separately bounded end-to-end digital canary, with explicit new
real-audio/codec authority and exact-execution-head CI. It should test operational
cost before a full cohort replay, while preserving case accounting and support
failures. Source-group independence, human listening calibration and the eventual
full-reference/no-reference question remain separate scientific work.

## Evidence and boundaries

The [machine-readable result](../../research/toolchains/evidence/perceptual-degradation-alignment-native-synthetic-20260908-001.json)
contains all eight observations. An independent standard-library audit, without
calling the runner's aggregate function, checked saved round/result bytes,
geometry, complete native counts, stage accounting, guard reasons/nulls, frozen
bindings and the private retention layout. Four JSON reports and one hash-bound
native binary remain outside Git; no raw arrays or private paths are published.
The source, compiler executable/version/flags and binary are bound. This host's
binary links only libSystem. A complete compiler dependency closure or a
byte-reproducible rebuild across private output paths is not claimed.

Original aligners, dated evidence, thresholds and the consumed real-audio
authorization are unchanged. No real audio, codec execution, playback, capture,
metric, human collection, trait assignment, training or public verdict was
enabled. The broad research objective remains incomplete.
