# Paired subtle ratings: score-blind software successor — 2026-09-05

Status: protocol and synthetic response-processing successor only. No live
player, listening session, recruitment, storage or observed-data adapter is
authorized. The existing protocol, player, response schema, analysis plan and
evidence remain unchanged. This successor does not qualify those predecessors
for collecting data and does not inherit their power or calibration results.

## Correction and primary source

The old protocol asks for one grade on the candidate selected as more different.
The old player records that selection and one grade. The analysis accepts a
condition-linked `sdg` restricted to -4 through 0. An incorrect selection would
therefore grade the hidden reference under the written instructions. No live
response mapping exists, so this is a preparation defect, not observed bias.

[ITU-R BS.1116-3](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1116-3-201502-I%21%21PDF-E.pdf),
section 4, calls for two candidate ratings against the known reference.
Sections 10.2–10.3 distinguish absolute grades from paired differences for
statistical analysis. Attachment 1 defines the sign as object minus hidden
reference and discusses both positive and negative observations. These
provisions support recording both grades and retaining the signed contrast;
they do not authorize LossyTrace's other statistical or collection choices.

## Successor trial and response target

1. Present a known reference and concealed candidates A and B. One is the hidden
   reference and the other the test condition. Keep recipes and roles outside
   the participant-facing assignment and response.
2. Require a forced choice before grading and lock it. Do not reveal correctness.
3. Grade **both** A and B independently against the known reference on a 1–5
   impairment scale: 5 imperceptible, 4 perceptible but not annoying, 3 slightly
   annoying, 2 annoying, 1 very annoying. Record tenths as integer ticks 10–50.
   Each grade requires explicit entry; there are no default responses.
4. Permit grade revisions before submission, but not a changed forced choice.
   Submit the pair atomically only when both grades exist. No post-submission
   edits or duplicate events are accepted by the deterministic reducer.
5. Resolve candidate roles only on the analysis side using the bound assignment.
   The browser never supplies correctness, an SDG, source identity or a role.
6. Compute `paired_sdg = (condition_grade_ticks - hidden_reference_grade_ticks)
   / 10`. Its admissible range is **-4 through +4**, not -4 through 0. Preserve
   both raw grades, forced-choice accuracy and the signed difference.

Incorrect forced choices remain in the paired analysis. Neither the selected
candidate nor the lower grade determines which rating belongs to the condition.
Positive differences, equal ratings and choices inconsistent with the grades
are retained, not clamped, reinterpreted as improvement, or excluded by outcome.
Both candidates may receive 5; the separate forced-choice question already
requires a guess. This departs from the example instructions in Attachment 3
that expect exactly one top grade. The hybrid procedure is not claimed to
comply formally with BS.1116. Pre-rating choice may influence subsequent grades;
its effect and the additional response burden remain design-validation issues.

The signed difference is an observation, not a severity verdict. A common grade
offset cancels in the contrast. Restricting analysis to correct choices or
clamping positive differences can turn symmetric errors into apparent damage.
There is no automatic migration from legacy one-grade records: the unobserved
second grade cannot be reconstructed from the choice or assumed to be 5.

## Executable boundary and synthetic evidence

The [plan](../../benchmarks/perceptual-degradation-v1/paired-rating-protocol-plan.json)
binds the predecessors and this document. The
[implementation](../../scripts/perceptual_degradation_paired_rating.py) provides
an event reducer and assignment-bound role resolver. It handles only generated
synthetic trials; the command line has no response-file input. IDs and grouping
originate in the generated assignment, not the response. Strict fields reject
role/identity injections, cross-assignment responses and invalid grades.

An unfinished event stream is explicitly incomplete, preserves any entered
values, and has no complete-pair analysis eligibility. It is never imputed.
Whether a future missing-rating trial can contribute to audibility alone must
be prospectively specified; this successor does not discard or admit it to a
live analysis. This reducer is not a delivery check, consent system, persistent
transaction service, browser UI, timing qualification or anti-tampering proof.

Five balanced 24-listener by 12-source numerical fixtures exercise equal top
grades, symmetric response errors, correctness-correlated ratings, a common
rating offset and positive differences. All 288 trials in each fixture pass
through the same reducer and role resolver. Candidate positions are balanced
within each listener and source. The old Gaussian numerical solver is reused
on signed differences solely to test that the target reaches a crossed-effects
fit without clipping. Its fixed variance components are not endorsed for the
paired target, and no old decision rule, bridge mapping or material threshold
is applied. The report contains aggregates only and must replay byte-for-byte.

## Remaining prerequisites

A real integration requires a separately bound paired-rating UI and concealed
stimulus delivery, session/privacy/idempotency validation, outcome-blind
missingness rules, a paired-target variance/power assessment, population and
source/condition estimands, and uncertainty-aware scientific decision rules.
The original material boundary is not changed or automatically transferred.
The MUSHRA block is not modified. Qualification of the historical playback
chain does not validate this new procedure. The source manifest, metric/legal
boundary, human calibration and grouped transfer gates still apply before
oracle or no-reference conclusions. No source, audio, metric or human data was
opened by this work.

Reproduction:

```sh
python3 -m unittest discover -s scripts/tests -p 'test_perceptual_degradation_paired_rating.py'
python3 scripts/perceptual_degradation_paired_rating.py --synthetic
```
