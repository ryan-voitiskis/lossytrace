# Full-reference evaluation synthetic replay - 2026-08-13

**State:** score-blind statistical semantics frozen; synthetic replay complete;
no scientific full-reference gate evaluated

## Outcome

LossyTrace now has a deterministic evaluator for the frozen full-reference
calibration gates. It implements severity ordering, audibility calibration,
transparent-condition safety, material-condition sensitivity, coverage,
subgroup reversal detection, and added value against both single metric
families and a simple signal-distance baseline.

The evaluator has no command for opening real scores. Its only execution path
creates fixed synthetic records, and its validator reconstructs that replay
exactly. No retained or provider audio, perceptual metric, human score, sealed
evidence, or no-reference model was accessed.

## Frozen statistical semantics

- Source groups are the atomic bootstrap unit. Related partition-group IDs are
  retained for leakage auditing but are not split or used as model features.
- The bootstrap uses 10,000 replicates, a fixed public seed, and a SHA-256
  counter/rejection sampler with no platform PRNG dependency.
- Spearman and ROC AUC use average ranks for ties. ROC AUC is the rank-based
  Mann-Whitney statistic.
- Confidence intervals use percentile source-group bootstrap quantiles:
  2.5/97.5% two-sided and 5/95% one-sided.
- At least 99% of requested replicates must produce a defined statistic. An
  undefined AUC or correlation cannot disappear through silent replicate
  filtering.
- ECE uses ten equal-width bins, left-closed/right-open except that the final
  bin includes probability 1.0.
- Eligible primary domains and reversal strata require at least eight source
  groups. Reversal is supported only when the two-sided 95% upper bound on
  Spearman correlation is below zero. Multiple-testing adjustment is omitted
  because any detected reversal is a conservative stop condition, not a
  positive efficacy claim.
- Added value uses pairwise-complete point estimates and must beat every
  single-family and simple-distance baseline by at least 0.02 Brier or 0.05
  severity correlation, exactly matching the preregistered disjunction.

Severity, audibility, safety, and sensitivity statistics use supported cases;
coverage is calculated over every eligible case so abstention cannot vanish.
Material human truth must also be audible, while transparent truth may be
neither audible nor material. Point diagnostics are reported by domain, codec,
encoder, artifact, bitrate region, and derived human-truth stratum; they do not
contribute additional selection gates.

## Boundary-rate safeguard

Ordinary percentile bootstrap gives a zero upper bound after zero observed
false alerts and a one lower bound after perfect sensitivity. Those bounds do
not express finite-sample uncertainty. The frozen evaluator therefore keeps
the source-group bootstrap interval but adds a stricter one-sided 95% Wilson
guard:

- transparent safety treats a source group as an event if any human-transparent
  condition is called materially degraded and uses the larger upper bound;
- material sensitivity treats a source group as a success only if all of its
  human-material conditions are detected and uses the smaller lower bound.

This safeguard can only make advancement harder. It does not relax the
original 5% point/10% upper transparent-safety gates or the 80% lower material
sensitivity gate.

## Synthetic replay

The replay used 80 fixed cases from 40 opaque source groups and 20 opaque
partition groups across two synthetic domains. All seven statistical gate
families deliberately pass to exercise the positive plumbing. The important
boundary observations were:

- overall severity Spearman lower one-sided 95% bound: `0.8783575139259491`;
- Brier: `0.0025000000000000027`;
- ECE: `0.050000000000000024`;
- ROC AUC lower one-sided 95% bound: `1.0`;
- transparent material-alert point rate: `0.0`;
- transparent conservative upper guard: `0.06335344864545808`;
- material-sensitivity conservative lower guard: `0.9366465513545419`; and
- overall supported coverage: `1.0`.

The synthetic input inventory SHA-256 is
`2c276e71f33984acf0bf1071af42f64a77419365e8cefd0b7c11550a6fe748bd`.
The full internal evaluation SHA-256 is
`80da8d3c62bb932198be3f887e74277603eec94129dda4b21c12dc8c0035fbbf`.
The compact committed replay SHA-256 is
`b02e4c1044c9111fc86b6fd91c7814b3c38fb836a5a6100860ff94bce4d1ff11`.

Tests separately force transparent alerts, low coverage, a negative codec
stratum relationship, zero added value, undefined AUC, malformed probabilities,
unsupported records containing values, and path-like identities. Each failure
remains visible and fails its corresponding gate.

## Claim boundary

The synthetic pass is plumbing evidence only. `scientific_gate_evaluated`,
`full_reference_gate_passed`, and `no_reference_work_eligible` all remain
false. Deterministic cross-environment metric replay is also a separate gate
and is not replaced by this evaluator.

Scientific evaluation remains blocked until separately authorized metric
outputs and valid human-calibration targets exist. The evaluator accepts only
opaque identifiers and bounded stratum codes; filenames, paths, codec metadata
as model inputs, and public verdicts remain forbidden.
