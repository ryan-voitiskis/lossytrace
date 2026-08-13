# Perceptual-degradation listening missingness stress - 2026-08-14

**Status:** deterministic score-blind synthetic stress complete. V3 issued
schedule balance does not imply balance in the retained response set. No
empirical missingness mechanism, correction, exclusion rule, operational study,
recruitment, collection, audio, response, score, or public verdict is selected
or authorized.

## Outcome

The v3 allocator remains correct for what it claims: every complete contiguous
issued prefix has trial-exposure, within-block trial-position and candidate-
position ranges no greater than one. Retaining the first `floor(90%)` eligible
assignments also preserves those bounds because it is another contiguous
prefix.

Arbitrary post-assignment loss is different. Across four listener-count options,
256 whole-session MCAR masks and 256 trial-level MCAR masks were replayed per
option. None of the 2,048 replicate schedules retained the strict range-at-most-
one invariant:

| Option | Session-MCAR strict passes | Trial-MCAR strict passes | Session-MCAR support passes | Trial-MCAR support passes |
| --- | ---: | ---: | ---: | ---: |
| 3 + 3, 765 eligible | 0 / 256 | 0 / 256 | 256 / 256 | 256 / 256 |
| 5 + 5, 496 eligible | 0 / 256 | 0 / 256 | 256 / 256 | 256 / 256 |
| 8 + 6, 345 eligible | 0 / 256 | 0 / 256 | 256 / 256 | 256 / 256 |
| 15 + 6, 227 eligible | 0 / 256 | 0 / 256 | 200 / 256 | 40 / 256 |

“Support pass” here means only that every symbolic source retained at least the
feasibility plan's eight judgments in both methods. It is not a power result or
a sufficient scientific gate. In the 15 + 6 trial-MCAR stress, the median
number of MUSHRA source groups below eight judgments was two and the maximum
was seven. Whole-session MCAR was less damaging at that option, but still left
as many as 12 MUSHRA source groups below eight judgments in one replay.

MCAR imbalance does not by itself demonstrate bias: a correctly specified
hierarchical analysis can use unequal counts. The replay shows that the issued-
schedule invariant cannot be cited as evidence that analysed observations are
balanced, and that support and uncertainty must be recomputed from the actual
retained design before any truth assignment.

## Structured stress

Two score-blind structural masks expose risks hidden by the scalar 90% usable-
trial assumption:

- Dropping exposure ordinals congruent to zero modulo ten retains roughly
  82-90% depending on the small per-source exposure count, yet produces
  candidate-position ranges up to three. A technical failure synchronized with
  replay or presentation phase can therefore preserve aggregate retention while
  confounding candidate identity with position.
- Removing all trials for 12 seeded symbolic source groups retains approximately
  90% of trials but leaves only 108 of 120 source groups and gives 12 groups
  zero judgments in both methods. The overall percentage does not preserve the
  planned source design or domain/provider coverage.

The 108-source stress is not automatically underpowered; it requires the power
and breadth calculations to be rerun against the retained grouped design. The
point is that an average usable-rate scalar cannot supply that proof.

## Frozen interpretation

The following distinctions now apply:

1. **Issued schedule:** v3 has a deterministic prefix-balance proof.
2. **Retained design:** missingness and exclusions can change exposure,
   position, source and condition support; all must be recomputed score-blind.
3. **Outcome validity:** unequal counts may be modelled, but unsupported groups,
   structural missingness or unidentifiable contrasts must abstain rather than
   inherit the issued-schedule claim.
4. **Power:** the existing 90% planning sensitivity is not evidence that the
   realized mechanism is MCAR and is not a substitute for retained-design power
   analysis.

No missing-response imputation, inverse-probability weighting, replacement
assignment, exclusion threshold or adaptive recruitment rule is selected.
Selecting one from outcome direction would invalidate the score-blind boundary.

## Decision

Post-assignment missingness remains an operational and statistical gate. Before
collection could be considered, a separately frozen successor would need to
bind:

- when eligibility is established relative to allocation-index reservation;
- append-only, idempotent and restart-safe assignment state;
- outcome-blind definitions of incomplete sessions and exclusions;
- retained-design support diagnostics by source, condition and position;
- the prespecified analysis or abstention response to lost support; and
- power recalculation rules for structured rather than scalar missingness.

This audit does not imply that collection should proceed. The 352-enrolled-slot
per-stratum/device/partition analytic lower bound still carries an unverified
missingness mechanism, unresolved session timing and an unknown multiplier for
condition strata. If the scale or assumptions are unacceptable, a rigorous
negative result or explicit abstention remains valid completion.
