# Paired uncertainty serialization correction — 2026-09-05

The [original uncertainty audit](perceptual-degradation-paired-uncertainty-20260905.md)
passed locally, but [CI at commit 924e660](https://github.com/ryan-voitiskis/lossytrace/actions/runs/33950011227)
failed its exact golden-report comparison. The reported mismatch was a Wilson
interval boundary serialized as `0.0` locally and `0` on the Linux runner.
The original report remains immutable and is hash-bound by its successor.

The cause was integer clamp constants in `max(0, center-radius)` and
`min(1, center+radius)`. Tiny floating-point cancellation differences can choose
either the integer clamp or a floating-point result. Rounding numerical values
does not resolve the resulting JSON type spelling difference.

The correction uses floating-point clamp constants. It changes no generating
mechanism, seed, paired response, estimator, interval multiplier, materiality
boundary, missingness rule, count gate or scientific conclusion. Historical
implementation bytes remain available at the original commit. The experiment
plan and all predecessor analysis implementations are unchanged.

Two full corrected CLI executions produced byte-identical
[successor evidence](../../research/toolchains/evidence/perceptual-degradation-paired-uncertainty-synthetic-20260905-002.json).
The successor names its serialization revision and binds the original report's
exact hash. Tests require numerical equality of every scenario with the
original report and strict byte equality with the successor golden report.
Boundary-type tests cover zero/all successes at every denominator from 1 to 129.
Tampering with the archived original is rejected.

This is a reproducibility repair, not new human evidence or a replacement
statistical method. The fixed-variance and selective-missingness limitations
remain unchanged. No audio, listener collection, metric execution, training,
capture or public verdict is enabled. Local replay and exact-head CI status
remain distinct; the failed original CI run is not relabelled as successful.
