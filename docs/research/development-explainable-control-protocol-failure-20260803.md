# Factorial benchmark v2 explainable-control protocol stop

Date: 2026-08-03

State: retained A0-A4/R1-R2 stage stopped without score interpretation;
path-free protocol-failure evidence frozen

## Decision

Do not amend and resume the retained explainable-control adapter. The
exact-hybrid run encountered an input-duration state that the committed
adapter explicitly did not authorize as unsupported. The correct action under
the preregistration is to stop, preserve the private checkpoints, and avoid
opening either family's aggregate.

This is a protocol result, not an A0-A4 or R1/R2 measurement result. It cannot
support a candidate, repair a rejected baseline, or contribute an accuracy or
paired-direction claim. Encoder-transfer and external-transfer features and
scores remain sealed, and the public verdict remains disabled.

## What happened

The adapter was committed and pushed at
`d5e6dbcbccb22caa050d2fac62fca3498873bad1` before any control score was
computed. It selected the frozen 6,032 factorial cells, 4,090 unique PCM
sequences, and 5,895 PCM/lossless-wrapper representatives.

The exact-hybrid adapter preregistered one narrow exception: the oracle error
`no supported exact-hybrid granules` could become an explicit unsupported
result with all A0-A4 scores absent. Any other oracle error had to stop the
run. The bound oracle instead surfaced `insufficient PCM for exact-hybrid
analysis` on a three-second artifact. The runner stopped without producing a
private report or aggregate.

At termination:

- 5,735/5,895 representatives had authoritative atomic checkpoints;
- 160 had no authoritative checkpoint;
- all 160 missing representatives were exactly three seconds long;
- the missing set contained 120 negatives and 40 controlled MP3 positives;
- the missing set crossed all six source domains; and
- no partial A0-A4 score was summarized or interpreted.

This was not a random machine interruption. The fixed five-second analysis
start is structurally incompatible with these three-second cases, and the
oracle checks minimum PCM before it reaches the one error state the adapter
was permitted to map. Broadening the mapping now would be a post-score support
change expressly prohibited by the plan.

## Projection run disposition

R1/R2 independently completed all 5,895 representatives and passed exact
wrapper invariance across 1,391 multi-wrapper PCM identities. A second report
assembled entirely from checkpoints was byte-identical to the first, with
SHA-256
`05f0589a0081c566b20c53403cf18c9e3dae36bd4da37bf0c8ae34b749631a9b`.
The duplicate replay report was then removed; the authoritative private report
and checkpoints remain outside Git.

The frozen public analyzer requires both complete private reports. Creating a
projection-only analyzer after R1/R2 scores existed would change the analysis
protocol. R1/R2 score distributions, correlations, paired effects, and gates
therefore remain uninterpreted. Completion and wrapper invariance are execution
facts only.

## Path-free evidence

The committed
[`protocol-failure record`](../../research/baselines/v2/evidence/explainable-controls-observed-20260803-001-protocol-failure.json)
contains only counts, named public domains, durations, commitments, and state.
It contains no case identity, audio identity, path, raw measurement, or timing.

| Binding | SHA-256 |
| --- | --- |
| adapter plan | `f654ddcaaa7bf331536cdd9e86117fe45d836f921fef67efafedc9903a367c4a` |
| frozen runner | `1af955ccaf78a96a59bc79799f76a83e0ada60ecc1a314663cb414daa36e9a11` |
| frozen analyzer | `10f4ef983b4695d168250fc418bfd6546a24c5983866aa017ea98baa2ee55bb0` |
| exact-hybrid release oracle | `d613498f05d9f885ac3d49b04b52f33b1c1e80a20cb49e7fe61b0cebdd8d253e` |
| codec-projection release oracle | `fb285afb0e9db3d077f5826467c986dabcdeb2e1e578c09bb2c907172606c5e6` |
| exact authoritative-checkpoint identity set | `86d65db4ba754b81cbc5a3eb6b10c3870a1ae43b623f8a5eb027fd1c7af9a9ef` |
| complete private projection report, outside Git | `05f0589a0081c566b20c53403cf18c9e3dae36bd4da37bf0c8ae34b749631a9b` |
| path-free protocol-failure record | `6206ca5c61e42a238ee0530a13688fb22d491e1f47850f1aa7cd22267f6c4e80` |

## Consequence for the research gate

The retained-control stage is closed as protocol-incomplete. It does not erase
the older, complete rejection evidence for A0-A4 and R1/R2, but it also does
not add v2 paired evidence. The broader baseline atlas still has no completed
representation that meets the frozen 90% direction and 85% one-sided Wilson
lower comparison across source domains.

Do not use this failure to tune duration, start offset, support, or thresholds.
The next research decision must use only the completed, already interpreted
baseline evidence and must preserve the option to close with a rigorous
non-identifiability result instead of forcing a new detector experiment.
