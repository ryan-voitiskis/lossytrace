# Descriptor frame origin and window support — 2026-09-05

Status: declared synthetic mechanism audit executed twice with byte-identical
results. Frame origin and frame inventory alone change the frozen spectral
classification of an unchanged periodic record. The audit isolates a mechanism
behind the predecessor's coherent-kernel result; it does not select a new
descriptor or establish natural-source or perceptual truth.

## What this adds

The [rate/context audit](perceptual-degradation-descriptor-rate-context-20260905.md)
changed several factors together. This successor holds sample rate, source
samples, duration of each analysis frame, FFT band and thresholds fixed. It
separately varies the frame origin, number of frames and diagnostic aggregation.
No real audio is accessed or played, and no capture specification changes.

At 48 kHz, three exact integer periods of 1,024 samples are repeated eight
times: the prior coherent harmonic construction, an impulse train, and an
exact quarter-rate tone. The coherent period is reused consumed development
evidence, not fresh validation. Its integer formula is checked against the
predecessor's generated period. The two controls separate the residual-background
mechanism from removal of a pure impulse and ordinary tonal concentration.

Every origin from 0 through 1,023 is tested with 11 and 12 frames, at the original
512-sample hop. All frames fit inside the same fixed record; all are cyclic
rotations of one period with exactly the same unwindowed energy. There is no
new padding, changed recording rate, altered amplitude or added noise.

The 11-frame inventory has six frames in one phase and five in the phase half
a period later. The 12-frame inventory has six of each. These are overlapping
analysis views, not independent observations, listeners, sources or trials.

## The mechanism at one origin

The coherent integer period has the exact form:

```text
x[0] = 511 * 8192
x[n] = -8192 for other even n
x[n] = 0 for odd n
```

Its unwindowed DFT has equal positive real coefficients at every bin except
DC and Nyquist, which are zero. This follows from the finite Fourier sum and
is checked at every bin. It is a mathematical spectrum, not a human non-tonal
label: a periodic harmonic construction is not an eligible natural transient.

At frame origin zero, the Hann window's zero removes the large boundary sample.
The remaining even-sample background, multiplied by Hann, has its included
spectral power concentrated at bins 1 and 511. Half a period later, the large
sample lies at the window maximum and the included spectrum is broadly spread.
The original admission step nevertheless accepts both because it measures
energy **before** windowing, when their energies are identical.

With 11 frames, the six weak-spectrum frames contribute only 0.029395914% of
the total analyzed-band energy but determine both equally weighted medians.
The five other frames contribute 99.970604086% of that energy.

| Frame origin | Frames | Frozen flatness | Frozen top-eight share | Spectral class |
| --- | --- | --- | --- | --- |
| 0 | 11 | 0.000000001 | 1.000000000 | Tonal |
| 128 | 11 | 0.986670558 | 0.035764611 | Non-tonal |
| 512 | 11 | 0.999462027 | 0.015682431 | Non-tonal |
| 0 | 12 | 0.499731014 | 0.507841215 | Indeterminate |

Origins 0 and 512 use the same hop-grid phase but reverse the 6:5 inventory
imbalance. Adding the twelfth frame balances the phases, and the two medians
become averages of their separate middle values. This is a precise explanation
of the technical classification change, not a claim about listener judgment.
It also does not prove that this mechanism caused any natural candidate failure.

## Exhaustive results, including diagnostic failures

Three methods are compared on all 6,144 family/origin/inventory cases:

- The unchanged raw-power admission and equal-frame medians.
- A diagnostic additional admission check at 0.001 of maximum post-Hann
  **analyzed-band** energy, retaining the same medians and class cutoffs.
- A diagnostic sum of the originally admitted positive-energy bin powers,
  followed by the same flatness and concentration formulas on that pooled
  spectrum. It still requires three contributing frames.

Reusing 0.001 isolates the admission location; it is not independent
justification of that cutoff. Pooling changes aggregation and effective energy
weighting, not only admission. Neither diagnostic is an approved replacement.

For the coherent construction, the full counts across 1,024 origins are:

| Method | Frames | Tonal | Non-tonal | Indeterminate | Unsupported |
| --- | --- | --- | --- | --- | --- |
| Original medians | 11 | 47 | 899 | 78 | 0 |
| Original medians | 12 | 0 | 830 | 194 | 0 |
| Post-window band admission | 11 | 0 | 1,004 | 20 | 0 |
| Post-window band admission | 12 | 0 | 1,024 | 0 | 0 |
| Pooled spectra | 11 | 0 | 1,024 | 0 | 0 |
| Pooled spectra | 12 | 0 | 1,024 | 0 | 0 |

Changing 11 to 12 frames changes the original class at 172 origins and the
post-window-admission class at 20 origins. At origin zero, post-window admission
keeps only the five strong frames and changes the result to non-tonal while
retaining over 99.97% of band energy. But its full sweep still leaves
indeterminate results at origins 53–62 and 962–971 with 11 frames. The audit
does not discard those cases or raise the admission threshold until they pass.

The impulse train is non-tonal at every origin under all three methods and both
inventories. When a pure impulse falls at the window zero, that frame has zero
band energy and the original implementation already excludes it. The exact
tone remains tonal in every case. The coherent result therefore involves
positive residual spectral energy, not a general inability to discard zero
spectra or an across-the-board tone/control failure.

All origin classes are retained through complete run-length encodings, together
with feature extrema, support counts, energy fractions and detailed coherent
ledgers. No random origin sampling or selected successful subset is involved.

## Consequence for the research program

The descriptor cannot be treated as a frame-origin-independent summary of
spectral structure. Raw activity does not guarantee that a frame's normalized
post-window spectrum represents a meaningful share of the analyzed energy.
Equal-frame medians, energy-conditioned medians and pooled spectra also measure
different quantities; freezing their thresholds does not make them interchangeable.

The next descriptor design must state whether it targets an energy-weighted
excerpt spectrum, time-local structure, or the distribution of normalized
frame properties. Frame support and aggregation must match that choice.
Pooling resolves the class variation in this narrow periodic grid, but combining
energy over time discards temporal organization; this result cannot validate
pooling for natural transients or rare local structure. Physical bandwidth and
event-versus-recording occupancy remain separately unresolved.

The necessary successor is a justified measurement definition with fresh
validation, not promotion of whichever diagnostic passes these consumed
examples. All original descriptor outcomes and thresholds remain unchanged.
The authorized capture still needs its physical setup and execution checkpoint;
this audit neither performs nor expands it. Source assignment, human calibration,
metric execution, oracle validation, no-reference training and public verdicts
remain closed. The full research objective is incomplete.

## Reproduction and independent arithmetic checks

```sh
python3 scripts/perceptual_degradation_descriptor_window_support.py --synthetic
python3 -m unittest discover -s scripts/tests -p 'test_perceptual_degradation_descriptor_window_support.py'
```

Two full CLI outputs are byte-identical. Twenty focused tests pass under local
Python 3.14 and 3.12. The exhaustive computation reuses each unique rotated
frame spectrum with exact multiplicities; 48 direct comparisons against the
unchanged descriptor agree in counts, flags and nine-decimal features.

A separate NumPy 2.3.5 / Python 3.12.14 calculation independently constructs all
three integer signals, checks their closed-form DFTs, and verifies all 18,432
origin-specific class decisions without calling the original FFT or reducer.
It also verifies every published support/feature range and detailed ledger,
including ledger support counts; this is not a claim that unpublished per-origin
numeric summaries were compared. The
largest difference from rounded nine-decimal extrema is 4.899e-10; the largest
ledger-ratio absolute difference is 1.677e-14. This is numerical corroboration,
not independent scientific validation. NumPy is not a new project dependency.

- [Declared plan](../../benchmarks/perceptual-degradation-v1/descriptor-window-support-audit-plan.json)
- [Implementation](../../scripts/perceptual_degradation_descriptor_window_support.py)
- [Tests](../../scripts/tests/test_perceptual_degradation_descriptor_window_support.py)
- [Complete synthetic evidence](../../research/toolchains/evidence/perceptual-degradation-descriptor-window-support-synthetic-20260905-001.json)
