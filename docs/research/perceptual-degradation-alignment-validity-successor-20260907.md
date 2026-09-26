# Explicit correlation validity in alignment — 2026-09-07

Status: a separate score-free alignment successor is implemented and exercised
on synthetic development evidence. Two complete CLI replays are byte-identical.
It corrects the invalid-value handling exposed by the
[channel audit](perceptual-degradation-channel-normalization-boundary-20260907.md)
without changing either bound original implementation, its thresholds, or any
old result. This is development repair after a known defect, not independent
preregistered validation or evidence of perceptual accuracy.

## The defect and the correction

The original cosine helper represents both invalid zero-energy correlation and
valid perfect opposite polarity with the number −1. Taking its absolute value
turns either into 1. This affects candidate selection and local windows as well
as the displayed diagnostic. Changing only the final displayed value or rejecting
every −1 would not repair the distinction.

The [successor](../../scripts/perceptual_degradation_alignment_v3.py) instead
uses a frozen typed correlation record: a defined signed value in [−1,1], or
null with an explicit reason. Its magnitude is also null when undefined.
Overlap and sampled-frame counts remain separate from validity.

- Invalid envelope and sample candidates never enter lag ranking. No valid
  candidate means no estimated lag, rather than a fabricated fallback.
- A missing alternative makes the ambiguity margin unavailable. Fractional
  interpolation requires both valid neighboring sample scores.
- A local search with no valid candidate contributes no lag to regression.
  All five drift windows and all seven structural windows remain required.
  Incomplete evidence yields null slope, residual and minimum correlation,
  together with support rejection; invalid windows are not dropped from a fit.
- Common channel estimates and minima are unavailable if a required channel
  estimate is unavailable. Per-channel rejection is never averaged away.
- A fitted zero gain has no finite dB value and no defined polarity. It is
  reported without the old −999 dB sentinel and is never inverted.

Finite vectors are internally scaled before correlation products, including
after centering for Pearson correlation, to avoid avoidable overflow and
underflow. That numerical calculation neither changes source samples nor
authorizes a normalized comparison view. Existing overlap, stride, ordering and
support thresholds are retained. A constant envelope with undefined Pearson
correlation abstains; no fallback search was selected to force support.

## Observed development behavior

All 18 previously declared family/matrix fixtures are retained as consumed
regression evidence. Their support decisions are unchanged: 15 supported and
three unsupported. Across 216 comparable diagnostic slots, 196 jointly available
values match at the reports' nine-decimal precision. The other 20 slots are
explicitly unavailable in the successor, ten for each stereo dropout. This is
not a comparison that fills missing values with zero or claims raw floating-point
identity beyond the reported precision.

Both dropouts keep the supported left-channel diagnostics and reject the silent
right channel at coarse search. Their common correlation, delay and drift are
unavailable, replacing misleading scalar summaries. Opposite-polarity fixtures
retain signed correlation −1 and defined inverted polarity. The correlated swap
and both dual-mono constructions remain supported: correcting invalidity does
not make alignment support a fidelity test.

Five additional alignment constructions all abstain. Both-zero, zero-reference,
constant-envelope and fourteen-sample inputs have no valid coarse candidate.
The otherwise-active identity construction with samples 4800–7199 set to zero
at 2 kHz has a valid global match, but only four of five drift windows and six
of seven structural windows. Both local models are correctly unavailable.
This is absence of technical alignment evidence, not a diagnosis of damage.

Five numeric report cases distinguish valid antiphase, zero test energy,
constant-envelope Pearson invalidity, and finite magnitudes of 1e−300 and
1e300. Focused tests additionally cover exact orthogonal/correlated vectors,
invalid numeric/configuration values, real alternatives in peak selection,
zero/nonrepresentable gains, topology, resource limits, unchanged inputs and
canonical replay. These are implementation checks, not natural-source coverage
or listener evidence.

## Integration and scientific boundary

The new record kind is `perceptual_degradation_alignment_v3`. The unchanged
legacy oracle rejects all 23 successor alignment records because its accepted
record kind differs. There is deliberately no conversion that coerces null
values into old numeric defaults, and no real-audio runner selects this module.
Future score-free integration must explicitly retain these validity semantics.

No corrected waveform, codec output, perceptual score, human response or trained
model is produced. No source trait is reassigned and the retained drift negative
is untouched. This work removes a concrete diagnostic defect; it does not
validate alignment after lossy coding or resolve the normalization estimand.

The next scientific requirements remain target-matched normalization, defensible
source support and controlled human calibration. The authorized clean capture
still needs its declared physical setup and execution checkpoint. The public
CLI remains verdict-free, and the full research objective is incomplete.

## Reproduction

```sh
python3 scripts/perceptual_degradation_alignment_validity_successor.py --synthetic
python3 -m unittest discover -s scripts/tests -p 'test_perceptual_degradation_alignment_validity_successor.py'
```

- [Declared development plan](../../benchmarks/perceptual-degradation-v1/alignment-validity-successor-plan.json)
- [Bound synthetic runner](../../scripts/perceptual_degradation_alignment_validity_successor.py)
- [Complete replay evidence](../../research/toolchains/evidence/perceptual-degradation-alignment-validity-successor-synthetic-20260907-001.json)
- [Focused tests](../../scripts/tests/test_perceptual_degradation_alignment_validity_successor.py)
