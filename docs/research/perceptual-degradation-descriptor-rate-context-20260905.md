# Sparse/tonal descriptor: rate and context audit — 2026-09-05

Status: declared synthetic audit executed twice with byte-identical results.
The frozen descriptor is not invariant to sample rate or recorded context in
these constructions. This is a technical validity finding about the source
qualification machinery, not an observed perceptual failure or a replacement
source classification. No actual audio was read or recorded.

## Why this changes the next action

The [restart review](perceptual-degradation-strategic-review-20260905.md)
identified sample-rate and context sensitivity as untested assumptions. The
source manifest remains unresolved, so an actual population-sampling design
cannot be established by inventing additional grouping IDs. Before another
statistical amendment, this audit checks an earlier prerequisite: whether the
source descriptor can support the interpretation expected of the authorized
clean capture.

The [frozen capture specification](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-clean-capture-acquisition-spec.json)
permits both 48 and 96 kHz and 15–30 seconds of context. The exact-member runner
feeds native-rate channel samples to `classify`; it does not supply sample rate
to the spectral function. The unchanged descriptor uses a 1,024-sample FFT,
512-sample hop, nearly the whole non-DC/non-Nyquist spectrum, and ten blocks
spanning the entire recording.

Consequently, the FFT window is 21.333… ms at 48 kHz but 10.666… ms at 96 kHz;
bin spacing changes from 46.875 to 93.75 Hz, and the highest included bin from
23,953.125 to 47,906.25 Hz. These are different physical analysis views, not
merely different storage rates. This audit measures their consequences without
changing the descriptor.

## Declared constructions and identity checks

Four fixed periodic functions use a 46.875-Hz fundamental: equal-amplitude
harmonics 1–511 with zero phases, the same harmonics with fixed hash-derived
phases, hash-derived harmonics 1–255, and a single 1,500-Hz tone. No phase seed,
frequency set or amplitude was selected after observing descriptor output.

Each function is evaluated on a common 192-kHz grid, rounded to integer samples
once, then sampled at 48, 96 and 192 kHz for six periods (0.128 seconds).
Every lower-rate sample equals the corresponding higher-rate sample exactly
at shared time instants. The periodic functions' highest harmonic is below
24 kHz; the unpadded rate comparison does not invoke a media resampler or move
their physical frequencies. Quantization and sampling are explicit parts of
the construction, not a claim about recorder or resampler quality.

All twelve kernels are analyzed. The short kernels are not eligible natural
members, listening stimuli or an exception to minimum-duration rules. The
192-kHz cases are development diagnostics, not an additional capture option.

The coherent kernel is also placed at seven seconds in 15 seconds of zeros,
at the two capture-permitted rates. This meets only the duration/quiet geometry
being tested. A synthesized periodic multisine is not a single natural transient
and cannot be submitted as the clean capture.

## Rate counterexamples

The padded coherent construction changes its complete contrast result:

| Native rate | Active time blocks | Median flatness | Top-eight-bin share | Frozen result |
| --- | --- | --- | --- | --- |
| 48 kHz | 1/10 | 0.986670558 | 0.035764611 | Sparse/non-tonal contrast passes |
| 96 kHz | 1/10 | 0.000039540 | 0.032338455 | Abstains |

Both spectral measurements are supported, with 13 and 14 active frames
respectively. The change is not a missing-data fallback or an occupancy change.
The signal is unchanged at shared sample instants, and no real recording,
encoder or perceptual metric is involved.

The unpadded full-band hash-phase construction supplies a separate spectral
witness: flatness falls from 0.717675633 at 48 kHz to 0.000031235 at 96 kHz
and 0.000000171 at 192 kHz. Its non-tonal flag changes from true to false.
It is non-sparse at every rate and therefore abstains from the admitted complete
contrast classes at every rate; a changed spectral flag must not be reported
as a changed complete contrast in this example.

The remaining results are retained, including those that do not show the
hypothesized transition. The lower-band hash-phase construction abstains at all
three rates. The single tone remains tonal/non-sparse at all rates. The
unpadded coherent construction is also classified tonal/non-sparse at all
rates, despite its many equal-amplitude harmonics. That is not edited into a
more convenient non-tonal control or described as a perceptual misclassification.

At 48 kHz, placing that coherent kernel into the declared padded recording also
changes its spectral class from tonal to non-tonal. This comparison jointly
changes frame origin, boundaries, eligible frames and context; it does not
isolate a single cause. The implementation selects active frames by unwindowed
power before applying the Hann window, which motivates a separate frame-origin
and windowed-support audit. No such follow-up was added to the declared grid
after seeing these results.

The native-rate comparison likewise changes bandwidth, window duration,
frequency resolution and frame inventory together. It proves non-invariance
of the deployed descriptor, not a causal decomposition of those factors or the
correctness of a particular replacement.

## Context counterexamples

The occupancy-only construction is a fixed 1.6-second interval of constant
nonzero samples in zeros. It is deliberately not a natural acoustic transient
or a spectral classification test. Its nonzero samples and duration never
change. All tested placements have at least five seconds of quiet on each side.

| Total duration | Event onset | Active blocks at both 48 and 96 kHz | Sparse flag |
| --- | --- | --- | --- |
| 15 s | 5.950 s | 3 | False |
| 15 s | 6.000 s | 2 | True |
| 30 s | 5.950 s | 2 | True |
| 30 s | 6.000 s | 1 | True |

Thus either translating the event by 50 ms or adding 15 seconds of trailing
quiet changes the original sparse flag. Exact interval-overlap calculations
reproduce all eight measurements. For the first construction, the three
nonzero blocks have relative powers 1/30, 1 and 1/30: each is well above the
unchanged 1/1000 activity threshold.

Whole-recording occupancy is intentionally context-relative. This is not a
programming error in that definition. It establishes that the label cannot
also be assumed to be an intrinsic property of the event, independent of the
permitted recording duration and placement. The source-trait interpretation
needs to say which of those quantities it means.

## Research disposition of this checkpoint

The three original ideal fixtures did not establish rate/context invariance.
This audit supplies explicit counterexamples; it does not show that any
particular retained candidate was wrongly classified, that natural captures
must fail, or that perceptual estimation itself is impossible.

Before using this machinery as a rate-independent source-trait adjudicator,
a separately justified successor should define the physical spectral band,
analysis duration and frame support, and distinguish event sparsity from
whole-recording occupancy. Its new validation must use fresh evidence. A fixed
rate alone would not resolve the demonstrated context dependence, and another
capture chosen simply because it passes the same rule would not validate the
construct.

The original descriptor, thresholds, acquisition specification and all consumed
candidate outcomes remain unchanged. The user's one-capture authority is not
revoked or expanded: the physical setup declaration and exact execution
checkpoint are still required. Any capture under the old specification retains
its original narrow technical claim; no amendment or retrospective relabeling
is implied by this report.

Human calibration, source allocation, population inference, perceptual metric
execution, oracle validation and no-reference training remain gated. No source
trait, replacement descriptor, scientific threshold or public verdict was
selected. The overall research objective remains incomplete.

## Reproduction

```sh
python3 scripts/perceptual_degradation_descriptor_rate_context.py --synthetic
python3 -m unittest discover -s scripts/tests -p 'test_perceptual_degradation_descriptor_rate_context.py'
```

Two complete final replays are byte-identical. The initial execution has the
same numerical and classification results; a report flag was clarified from
`statistical_or_perceptual_metrics_executed` to
`statistical_fits_or_perceptual_metrics_executed` before publication, with no
experimental change. Tests cover shared-grid identity, physical units, a direct
DFT cross-check, exact occupancy, invalid inputs, disk reserve, the complete
report and closed execution boundaries. Generated sample arrays remain in
memory only and are never saved or played.

A separate numerical cross-check used NumPy 2.3.5 under Python 3.12.14 with
the same declared signal generator but an independent FFT and descriptor
calculation. All 14 spectral cases, 315 active frames, occupancy counts and
classification flags agree. The largest difference from the published rounded
values is 4.626e-10, within their nine-decimal rounding. It also checks the full
padded signals' shared-grid identity. This is an arithmetic check, not independent
scientific validation; NumPy is not added to the audit or test dependencies.

- [Declared plan](../../benchmarks/perceptual-degradation-v1/descriptor-rate-context-audit-plan.json)
- [Implementation](../../scripts/perceptual_degradation_descriptor_rate_context.py)
- [Tests](../../scripts/tests/test_perceptual_degradation_descriptor_rate_context.py)
- [Full synthetic evidence](../../research/toolchains/evidence/perceptual-degradation-descriptor-rate-context-synthetic-20260905-001.json)
