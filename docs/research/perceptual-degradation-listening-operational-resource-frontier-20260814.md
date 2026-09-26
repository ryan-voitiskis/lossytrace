# Perceptual-degradation listening operational resource frontier - 2026-08-14

**Status:** deterministic score-blind allocator replay complete; the analytic
minimums and trial-exposure-cycle sensitivities are not operationally balanced.
No source member, listener count, allocation policy, study design, recruitment,
collection, audio, metric, score, no-reference work, or public verdict is
authorized.

## Outcome

The 120-source design is arithmetically power-feasible, but the existing v2
allocator does not produce a candidate-position-balanced finite prefix at any
of the four modelled workload options. The raw power minimums also have unequal
trial exposure. Rounding eligible assignments to complete 120-slot cycles
equalizes trial exposure, but candidate-position imbalance repeats across
cycles and still fails the frozen balance audit.

The resource frontier for one aggregate condition stratum, one device class
and one truth-bearing partition is:

| Subtle + MUSHRA trials per eligible slot | Raw eligible | Raw enrolled | Raw enrolled, four partitions | Cycle-rounded eligible | Cycle-rounded enrolled | Cycle-rounded enrolled, four partitions |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 + 3 | 765 | 1,185 | 4,740 | 840 | 1,301 | 5,204 |
| 5 + 5 | 496 | 768 | 3,072 | 600 | 929 | 3,716 |
| 8 + 6 | 345 | 535 | 2,140 | 360 | 558 | 2,232 |
| 15 + 6 | 227 | 352 | 1,408 | 240 | 372 | 1,488 |

The raw 352 and four-partition 1,408 figures remain the enrollment-minimizing
analytic lower bounds at the protocol caps. The 372 and 1,488 figures are only
trial-exposure-cycle sensitivities. They are not balanced designs or frozen
recruitment targets.

## Allocator finding

The replay constructed an in-memory symbolic v2 manifest with 120 source-group
identities, 840 non-audio stimulus records and 240 trials. It called the actual
v2 allocator with consecutive allocation indices and opened no audio or
responses.

The audit requires trial-exposure range `0` and maximum candidate-position
range no greater than `1`. At the raw minimum eligible prefixes, the maximum
observed ranges were:

| Subtle trials | Subtle exposure range | MUSHRA exposure range | Subtle position range | MUSHRA position range |
| ---: | ---: | ---: | ---: | ---: |
| 3 | 3 | 3 | 7 | 7 |
| 5 | 5 | 5 | 5 | 5 |
| 8 | 8 | 6 | 1 | 3 |
| 15 | 13 | 6 | 3 | 2 |

At complete 120-slot trial-exposure cycles, both exposure ranges become `0`.
The maximum position ranges remain `7`, `5`, `3`, and `2` respectively. The
current candidate phase repeats when the allocation index advances by 120;
because 120 is divisible by both candidate counts, the within-cycle position
preference repeats rather than cancelling in later cycles.

This is scheduling evidence, not response evidence. It does not show a measured
perceptual bias. It shows that a candidate-position effect would be confounded
with candidate identity under the current schedule and therefore must not be
ignored.

## Interpretation and scale

Each count is an enrollment or eligible **session slot**, not necessarily a
unique person. Listener reuse across development, calibration, transfer and
final validation is not frozen. The table also covers only one aggregate
condition stratum and one device class. Total workload must be multiplied by
the eventual number of separately estimated codec, encoder, bitrate and other
condition strata, and by any additional device classes.

The 64.6% eligible-listener retention and 90% usable-trial rate are declared
planning sensitivities, not empirical rates. Cycle rounding is conditional on
assigning the allocation index after eligibility is established; that policy
is not selected. Later missingness and exclusions can disturb exposure and
position balance even after a balanced schedule is issued.

The 15 + 6 option assigns 21 scored trials per eligible slot. The protocol's
20-to-30-minute target has not been timed at this workload, so the
enrollment-minimizing option is not presumed operationally feasible.

## Decision

No option is selected. A score-blind allocator successor is required before an
operational listening design can be frozen. It must balance candidate position
across arbitrary prespecified prefixes or define a justified cycle and stopping
policy, then separately handle eligibility, exclusions and missingness without
looking at outcome scores.

The listening-resource scale also remains a substantive feasibility question.
If the eventual source, condition and recruitment burden is unacceptable, the
scientifically valid outcome remains abstention or a rigorous negative result;
the objective must not be rescued by weakening source independence, balance,
power, held-out validation, or the verdict-free public boundary.

No additional physical playback test is needed from the responsible human at
this checkpoint. The declared RME ADI-2 Pro FS and Adam Audio T7V playback
qualification remains passed for plumbing only.
