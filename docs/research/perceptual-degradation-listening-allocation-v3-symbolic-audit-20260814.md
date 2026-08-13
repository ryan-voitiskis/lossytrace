# Perceptual-degradation listening allocation v3 symbolic audit - 2026-08-14

**Status:** the v2 candidate-position scheduling defect is technically repaired
in a deterministic score-blind v3 successor. The successor is not selected for
an operational study, and post-assignment balance remains unresolved. No source
member, listener count, recruitment, collection, audio, score, metric,
no-reference work, or public verdict is authorized.

## Outcome

The `prefix-balanced-score-blind-v3` construction keeps trial-exposure range,
within-block trial-position range and per-candidate position range at or below
`1` for every contiguous post-eligibility allocation prefix. It therefore
passes the expanded scheduling gate at all four raw power minimums without
rounding eligible assignments to a 120-slot cycle.

The deterministic symbolic replay audited every prefix through the former
cycle-rounded boundary for each option—2,040 option-prefix cases in total:

| Subtle + MUSHRA trials | Raw eligible prefix | Largest audited prefix | v2 raw prefix | v2 cycle prefix | v3 every audited prefix |
| ---: | ---: | ---: | :---: | :---: | :---: |
| 3 + 3 | 765 | 840 | fail | fail | pass |
| 5 + 5 | 496 | 600 | fail | fail | pass |
| 8 + 6 | 345 | 360 | fail | fail | pass |
| 15 + 6 | 227 | 240 | fail | fail | pass |

Across all 2,040 audited prefixes, the largest trial-exposure, within-block
trial-position and candidate-position ranges were each `1`. At the raw
227-eligible protocol-cap prefix, subtle trials receive 28 or 29 exposures and
MUSHRA trials receive 11 or 12; every trial's block-position counts and every
candidate's position counts differ by no more than one.

The audit also passes a non-120 symbolic case with 12 trials per method, three
subtle trials per assignment, four MUSHRA trials per assignment and five MUSHRA
candidates. This guards against a repair that works only because 120 is the
trial count or because the original candidate counts are two and four.

## Construction invariant

For one listening method, let `N` be the number of trials and `L <= N` the
number assigned per eligible slot. The seeded trial order is repeated as one
infinite sequence. Eligible allocation index `p` receives global slots
`pL ... pL + L - 1`.

After any contiguous prefix of `P` eligible assignments, exactly `PL`
consecutive slots have been issued. Each of the `N` trials therefore appears
either `floor(PL/N)` or `ceil(PL/N)` times, proving trial-exposure range at most
one. Because `L <= N`, one assignment cannot contain the same trial twice.

The v3 policy additionally requires `N` to be divisible by `L`. One complete
trial-exposure cycle therefore contains `N/L` assignments. Within each cycle,
the selected block is rotated by the zero-based exposure-cycle ordinal. A trial
that starts in block position `j` consequently appears in position
`(j - k) mod L` on exposure cycle `k`; after any number of exposures, its block
position counts differ by at most one. Unsupported non-divisible trial/limit
combinations are rejected instead of silently weakening this invariant.

For each trial independently, candidate rotation advances by that trial's
zero-based exposure ordinal. After `E` exposures of a trial with `C`
candidates, every candidate occupies every position either `floor(E/C)` or
`ceil(E/C)` times. The position-count range is therefore also at most one.

The seed determines only the initial trial permutation, candidate permutation
and candidate phase. Neither participant identity, condition recipe, score nor
response affects scheduling. Participant identity contributes only to the
opaque assignment identifier and is not emitted.

## What this does not prove

The invariant assumes contiguous allocation indices are assigned after a slot
is eligible. Enrollment dropout, training failure, later technical exclusion,
missing responses and partial sessions can disturb balance in the analysed
response set. The symbolic allocator does not yet provide:

- an append-only concurrent allocation-index store;
- idempotent reservation, retry and restart recovery;
- a frozen rule for pre- versus post-assignment eligibility;
- score-blind rebalancing or weighting after missingness and exclusions; or
- monitoring thresholds that cannot inspect outcome direction.

The symbolic fixture also has only one aggregate condition trial per source.
It therefore does not prove within-assignment sequence balance across future
codec, encoder, bitrate, severity or condition-family strata, nor separation of
the same source across subtle and MUSHRA blocks. Those constraints depend on
the eventual score-blind trial manifest and need their own audit.

These are operational and statistical policy questions, not reasons to weaken
the scheduling invariant. They require a separate frozen successor if the
listening design proceeds.

## Resource implication

Because v3 passes the raw eligible prefixes, the earlier cycle-rounded 372
enrolled slots per stratum/device/partition and 1,488 across four partitions
are no longer required solely for schedule balance. The analytic lower bounds
remain 352 and 1,408 respectively under the declared 64.6% eligibility
sensitivity.

These are session slots for one aggregate condition stratum and one device
class, not unique people or a recruitment target. Total workload remains
unknown until condition strata, participant reuse, session timing, exclusions
and missingness policy are frozen. The 15 + 6 option still has 21 scored trials
and has not been shown to fit the protocol's 20-to-30-minute target.

## Decision

Trial-exposure, block-position and candidate-position scheduling are
technically repairable for the audited grid, so those narrow defects are no
longer a scientific stop. No v3 operational policy, listener count or study
design is selected. The next responsible decision remains whether the
unresolved source, condition and listening-resource scale warrants an
operational allocation-state and missingness-policy successor.

If that burden is unacceptable, explicit abstention or a rigorous negative
result remains valid completion. It must not be evaded by reusing source groups
across partitions, weakening balance or power, treating symbolic scheduling as
listening evidence, opening held-out labels, or changing the verdict-free
public CLI.
