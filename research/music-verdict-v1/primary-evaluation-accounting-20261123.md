# Single-file verdict evaluation accounting

The [frozen study](../../docs/research/music-verdict-successor-20260927.md) counts an independent recording group once, despite its 42 processing variants. The [research evaluator](../../scripts/music_verdict_evaluation.py) now computes the primary decision and calibration metrics for either model using its own fixed policy. It takes a preallocated group-to-stratum map and one score per expected file. Caller verification of the allocation and model artifact is still required.

At the design minimum of 300 groups, zero groups with a false alert gives a one-sided 95% upper bound of 0.9936%. One alerted group raises it to 1.5715%, even if only one of its six controls triggered. For each individual codec setting, at least 224 groups must flag five or six variants. The one-sided lower bound is 69.8490% for 223 groups and 70.1975% for 224. These are arithmetic consequences of the design.

## Accounting choices

- Every allocated group contributes six controls and 36 encoded cases. Missing files, missing whole groups, unsupported outputs and explicit inconclusive decisions stay in their class denominators. The report preserves each category, decision coverage and the full state-by-processing confusion counts.
- An explicit unsupported control produced no flag. A missing control has an unknown outcome. The report gives the observed alert count and the upper bound if every unresolved group had an alert. Only the latter can establish the false-alert limit with incomplete negative outputs.
- Full-case Brier score and ten-bin expected calibration error require a probability for every allocated case, including inconclusive decisions. Each group has equal weight and each class has half the weight within its group. Reported calibration uncertainty uses 1,000 fixed-seed percentile bootstrap draws of whole groups within production strata. An interval is unavailable when a stratum has only one group. This uncertainty is conditional on the sampled strata and fixed policy.
- Estimated precision among flagged files is reported at assumed encoded prevalences of 1%, 10% and 50% when outputs are complete. It assumes the class-conditional flag rates transfer. Zero flags leave precision undefined. These scenarios do not estimate the prevalence in a user's library.
- Stratum results include class-specific counts and coverage. A small stratum is shown even if its performance limit cannot be evaluated. The metric report has no release switch. Runtime, provenance, held-out provider, file preservation, replay and independent saved-output verification require separate evidence.

## Offline verification

Eight tests exercise synthetic score matrices. They include the 300-group false-alert and per-codec boundaries, five-of-six counting with missing and unsupported cases, equal class weights despite a 6:1 case ratio, whole-group bootstrap behavior, a missing-stratum-output check, and a fit-to-evaluation replay against separately calculated scalar Brier and calibration error. The verdict-research suite passed 94 tests in the isolated NumPy/Torch environment.

```sh
.tmp/music-verdict-v1/python-env/bin/python -B -m unittest discover \
  -s scripts/tests -p 'test_music_verdict*.py'
```

This work used constructed numbers throughout. The [offline pilot result](../music-library-pilot-v1/single-file-interpretation-20261123.md) and the [source qualification checkpoint](victor-session-and-calibration-checkpoint-20261123.md) remain the relevant evidence about detector performance and source availability.
