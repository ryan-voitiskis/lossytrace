# Perceptual-degradation listening analysis synthetic replay - 2026-08-13

**Status:** score-blind response and analysis plumbing frozen and replayed with
synthetic records only; human collection, observed-response analysis, retained
ODAQ reference reading, and perceptual conclusions remain unauthorized.

## Outcome

The missing layer between listening allocation and the full-reference oracle
now has an executable contract. The replay validates de-identified session and
response envelopes, applies only prespecified outcome-blind exclusions, fits
crossed listener/source random-intercept models, applies the frozen audibility
and material-severity rules, and builds a development-only monotonic bridge
between SDG and hidden-reference-normalized MUSHRA loss.

The committed synthetic fixture produces the three intended supported states:

- a chance-equivalent group is `transparent`;
- an audible group below the material boundary is `audible_nonmaterial`; and
- an audible bridge group beyond both material boundaries is
  `materially_degraded`.

These are fixture assertions, not observations about audio or people. The
report therefore keeps `scientific_gate_evaluated`, collection eligibility,
and oracle-truth eligibility false.

## Frozen analysis

Audibility uses a Bernoulli-logit model with crossed listener and source random
intercepts. SDG and MUSHRA loss use Gaussian crossed-random-intercept models.
Variance components remain those declared by the score-blind power model; they
are not re-estimated from synthetic or later condition outcomes. The solver is
deterministic penalized IRLS/least squares with conjugate-gradient normal
equations. Intervals are multiplicity-adjusted Wald intervals for the fixed
intercept from the penalized Hessian. The implementation fails closed on
non-convergence.

The multiplicity-adjusted one-sided threshold remains `2.2414027276`.
Audibility requires a lower probability bound above `0.5` and a point estimate
of at least `0.75`. Chance equivalence requires the fitted interval to lie
strictly within `[0.45, 0.55]`. Material subtle evidence requires the SDG upper
bound below `-1`; material MUSHRA evidence requires the hidden-reference loss
lower bound above `10`. A bridge condition must pass both severity rules;
disagreement is `indeterminate`.

The development-only bridge first maps SDG by
`severity = clip(-25 * SDG, 0, 100)`, then fits a bounded isotonic MUSHRA-loss
mapping. It preserves `SDG = -1`, `MUSHRA loss = 10`, and unified severity
`25` as the same material boundary. Transfer and validation outcomes cannot
refit the mapping.

## Negative controls exercised

The tests demonstrate that:

- observed-human-response or collection-authorized envelopes are rejected;
- duplicate response or idempotency keys are rejected;
- malformed scales and participant/session mismatches are rejected;
- source/partition and condition/analysis-group leakage are rejected;
- underpowered groups abstain;
- hidden-reference or anchor quality failures are excluded from the primary
  result but retained in a declared sensitivity analysis; and
- conflicting SDG and MUSHRA material conclusions become `indeterminate`.

The command line exposes only `--synthetic-output`. It has no real-response
input option and refuses to replace an existing report.

## Playback qualification boundary

The previously reported 48 kHz delivery, correct left/right routing, fixed
comfortable level, quiet fixed loudspeaker position, effects-off state, and no
discomfort qualify only the private playback plumbing. They do not establish
audibility, transparency, material degradation, formal BS.1116/MUSHRA
compliance, or listener-training eligibility.

## Remaining gates

This checkpoint does not repair the unresolved equivalence-power limitation,
freeze an operational listener count, authorize recruitment or collection, or
open any score. Before observed responses could be analysed, a fresh
score-blind amendment still needs to bind the final stimulus allocation,
quality thresholds, participant count, repetitions, compensation, retention,
responsible-human approval, and exact analysis hashes.

The retained ODAQ clean references were not read or projected. Their separate
successor authorization remains required before that path can execute.
