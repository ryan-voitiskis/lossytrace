# Factorial benchmark v2 fractional-assignment result 004

Date: 2026-08-02

State: two feasibility-filtered private assignments and path-free aggregates
are byte-identical; assignment is frozen for a new construction-feasibility
audit; no waveform sample, benchmark audio, feature, score, or unopened label
was read

## Replay result

The committed rules have SHA-256
`3697c08f348d79f8ee87f951126f2b037d88394b2e3b47f514a1e30f456f5eae`.
Both complete private assignments have SHA-256
`46039d6fc22a6764daf81684d109e43a9f96b97af7d85e99258b1efe0449c5bb`.
Both path-free run aggregates have SHA-256
`5a494208933c5fefe13c950aa31a1de06a5f48ddbb4f9cfa6b58f2d537f8e2b0`.
The attested public result is
[`fractional-assignment-observed-20260802-004.json`](../../research/sources/evidence/fractional-assignment-observed-20260802-004.json),
with SHA-256
`05fa5c09c90a2fd8404c8afa08f7515032c1f3633cc7bfcc17e58526f984a25d`.

The assignment contains 793 source groups and 12,885 cells: 6,356 controlled
positives and 6,529 matched or standalone PCM references. Every positive has
an exact matched negative on source group, channel treatment, target sample
rate, transform, and wrapper, and every generated cell names its identity PCM
recipe source. The 100-group external MP3-positive reserve still has no codec
setting, encoder, decoder, feature, score, or opened label.

## Feasibility correction audit

The predicate excludes the following group-transform pairs before ranking:

| Partition | Source domain | Transform | Excluded groups |
| --- | --- | --- | ---: |
| encoder transfer | home-recorded bandwidth-limited digit speech | 3 s duration prefix | 6 |
| encoder transfer | home-recorded bandwidth-limited digit speech | 250 ms head trim | 6 |
| encoder transfer | studio speech | 3 s duration prefix | 36 |
| external transfer | laboratory Lombard speech | 3 s duration prefix | 50 |

These are eligibility counts for all selected source groups, not detector
outcomes or post-score exclusions. Development has no exclusion. Every exact
per-transform quota remains satisfied after selection within the eligible
set.

Relative to recipe `003`, the source groups, all 4,196 identity positives, all
793 base-reference assignments, all 100 external reservations, and every
transform without a duration minimum are byte-for-byte unchanged. Ten
duration-prefix group slots and three trim group slots are replaced. The total
cell count rises by one only because the new matched recipes have a different
identity-reference deduplication pattern; positive counts and quotas do not
change.

## Disposition

Recipe `004` is the only assignment authorized as input to a successor
header-only construction-feasibility audit. Audio construction remains stopped
until that separately frozen audit passes twice. Features, scores, and external
positive encoder selection remain unauthorized.
