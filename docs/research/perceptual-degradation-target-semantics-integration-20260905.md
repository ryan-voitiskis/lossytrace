# Perceptual target semantics integration — 2026-09-05

Status: a separate synthetic integration successor is implemented and replayed
twice with byte-identical results. It preserves all predecessor artifacts and
numeric thresholds. It does not select replacement scientific gates or accept
observed responses, audio, perceptual metric results or sealed evidence.

The restart review identified a disagreement between the contract's
correct-response probability and the full-reference evaluator's Boolean
audibility target. This successor establishes the exact scope of the existing
outputs and supplies a typed adapter for the existing synthetic listening
pipeline. It is not a replacement full-reference evaluator or a calibrated
oracle.

## Verified behavior

| Quantity | Meaning | Successor handling |
| --- | --- | --- |
| Correct-response probability | Chance of a correct forced-choice response | Preserves the fitted estimate and interval; chance remains 0.5 |
| Current fitted probability scope | Inverse-logit of the analysis-group intercept, with listener and source effects zero | Explicitly identified as conditional, not population-marginal |
| Audible-condition label | Frozen decision based on the probability interval, point estimate and evidence support | True for audible, false for chance-equivalent, null for indeterminate |
| Audible-condition probability | Probability attached to a separately defined condition class | Null; the existing fit does not estimate it |
| Per-source target | Evidence tied to an exact reference/condition pair | Ineligible; aggregate treatment results cannot be broadcast to individual sources |

The current logistic implementation returns `logistic(parameters[0])`. Averaging
over a population of random effects generally produces a different quantity
because inverse-logit is nonlinear. This successor preserves the computed
value and identifies the unresolved population-averaging requirement; it does
not invent a marginal estimate.

Two independently invoked complete replays ran the bound synthetic listening
fixture plus a declared intermediate-response fixture. In the intermediate
fixture, only the audible-nonmaterial analysis group's forced-choice sequence
changes to thirteen correct responses in each twenty. The existing fit returns
indeterminate audibility, which the adapter preserves as a null class label.
Source and listener grouping, severity observations, exclusion behavior and
the frozen human decision thresholds are unchanged.

Scalar witnesses also reproduce the mismatch using the actual legacy scoring
functions. At correct-response truth 0.5, forecasting 0.5 yields response Brier
0.25. Feeding the same forecast to the legacy audible-class score against a
false label yields 0.25, whereas a correct class-probability forecast of zero
yields class Brier zero. Legacy class ECE becomes 0.5 in that example. These
are algebraic/synthetic results, not perceptual scores or observed listening
data. The legacy Brier ceiling of 0.15 is therefore not transferable to response
prediction without a new statistical justification.

The old record validator also accepts all-false audible/transparent/material
labels. That does not mean such records necessarily represent indeterminate
truth; it establishes that the Boolean envelope cannot distinguish an explicit
unknown state by itself. The new adapter refuses to convert unknown or absent
audibility into a negative.

## What remains unresolved

Before any scientific calibration, a successor must freeze the prediction unit,
population averaging, source/condition linkage, treatment of human uncertainty,
and matching evaluation criteria. Response Brier has irreducible Bernoulli
variation; a condition-class score answers a different question. Existing AUC,
ECE and Brier thresholds cannot silently move between these targets.

There is also an unresolved rating-target issue in the
[subtle listening protocol](perceptual-degradation-listening-protocol-20260803.md).
It asks the listener to grade the selected candidate after forced choice. The
[synthetic player](../../research/listening-player/player.js) records one grade
and the selected position, while the analysis fits SDG over all subtle
responses. Under that wording, an incorrect choice grades the hidden reference,
not the encoded condition. The live response mapping is not implemented, so
this is a protocol/interface gap rather than an observed bias. A successor must
bind each rating to its actual stimulus role and choose either separate
candidate ratings or an explicitly different selected-candidate estimand.

The adapter retains the old audibility decision rule solely to preserve
semantics in synthetic integration. It does not prove that absent material
severity evidence establishes nonmateriality, validate the fixed variance
assumptions, qualify any source, or narrow the original research objective.
The source-manifest, listening, metric-execution, full-reference, grouped
transfer and no-reference requirements all remain outstanding.

## Reproduction

```sh
python3 -m unittest discover -s scripts/tests -p 'test_perceptual_degradation_perceptual_target_semantics.py'
python3 scripts/perceptual_degradation_perceptual_target_semantics.py --synthetic
```

The command has no observed-data input option and writes its report to standard
output. Its adapter verifies the bound synthetic analysis provenance, accepts
only the declared development groups, checks support counts and probability
intervals, and reconciles reported states against the unchanged listening rule.
The tests compare a fresh replay with the stored evidence and reject semantic,
authority, provenance and grouping violations.

Artifacts:

- [Plan](../../benchmarks/perceptual-degradation-v1/perceptual-target-semantics-plan.json)
- [Implementation](../../scripts/perceptual_degradation_perceptual_target_semantics.py)
- [Tests](../../scripts/tests/test_perceptual_degradation_perceptual_target_semantics.py)
- [Synthetic evidence](../../research/toolchains/evidence/perceptual-degradation-target-semantics-synthetic-20260905-001.json)
- [Restart review](perceptual-degradation-strategic-review-20260905.md)
