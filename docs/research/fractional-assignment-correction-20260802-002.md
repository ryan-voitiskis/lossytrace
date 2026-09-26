# Factorial benchmark v2 fractional-assignment correction 002

Date: 2026-08-02

State: corrected recipe frozen before replay; no benchmark audio, waveform
statistic, feature, score, or unopened label was inspected

## Trigger

Construction-lineage review found that recipe `002` recorded every positive's
matched H0 but did not record the untransformed identity PCM from which both
the H0 transform and H1 history recipe must be reproduced.

The distinction matters for robustness cells:

- identity source: `X`;
- matched transformed negative: `T(X)`; and
- transformed positive: `T(D(E(X)))`.

`T(X)` is the evaluation match for `T(D(E(X)))`, but `X` is the recipe source
for both generated branches. Inferring `X` later from group, channel, sample
rate, transform, and wrapper would leave construction lineage outside the
frozen assignment. Recipe `002` is therefore deterministic and
sample-rate-correct, but incomplete as a construction recipe.

The public factorial-manifest validator also conflated these two roles: it
required a positive's matched reference to be an identity `pcm_reference` and
required the recipe source to be that same case. The validator now permits a
positive to match an eligible `pcm_hard_negative` while independently
requiring every generated recipe to start from an identity `pcm_reference`.
Matched H0/H1 output factors must still agree.

## Corrected recipe

Recipe `lossytrace-v2-fractional-assignment-20260802-003` records
`source_reference_assignment_id` on every generated cell. Every nonidentity
negative points to an identity PCM source. Every positive records both that
same identity source and its exact matched negative. Container-rewrite cells
use FLAC as the source wrapper; other transforms retain the assigned wrapper.

The corrected rules SHA-256 is
`372049ed3567443f171d60a7c93a1e547a7eb4e732ac9dfaebf9a33a78229f37`.
They bind generator SHA-256
`07242c92df17207ccad8e2f7cdf57f01fd4819b9a0d56e7ca2e2c0341a76782e`
and upstream checkpoint
`cb4059366d104ad9836cbf55d55235ce88e411ce`.

## Replay gate

Commit this correction before execution. Then rerun the complete private
assignment twice and require byte-identical private outputs and path-free run
aggregates. The validator must prove that every generated cell has an explicit
identity source and that every positive and matched negative share it. Only a
fresh recipe-`003` result may authorize construction.
