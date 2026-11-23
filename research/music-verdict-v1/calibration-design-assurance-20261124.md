# What the minimum allocation implies for the false-alert gate

Under a fixed scoring model and exchangeable, distinct negative group maxima, the frozen 100-group calibration and 300-group evaluation design has a **25% chance of passing the negative false-alert gate**. This calculation uses no audio, observed scores or assumptions about positive-class detection. It diagnoses the sampling behavior of the existing rule. Provider holdout and real production differences can violate exchangeability, so the percentage is a design scenario and cannot predict this detector's finished-music accuracy. [Frozen design](../../docs/research/music-verdict-successor-20260927.md) · [Exact calculation](calibration-design-assurance-20261124.json)

Each group contributes six negative cases. Reduce each group to its largest raw score. The high cutoff is the next representable value above the largest calibration negative. A group therefore alerts exactly when its maximum strictly exceeds the largest calibration maximum. Repeated windows or related encodes add no independent ranks.

With 300 evaluation groups, zero alerts gives a one-sided 95% upper bound of 0.994%. One alert gives 1.571% and fails the 1% ceiling. Zero evaluation alerts means the single largest maximum among all 400 groups belongs to calibration. Under the stated rank model its probability is 100/400. The expected number of alerted evaluation groups is 300/101, or 2.97. These calculations assume completed negative scores and address only this gate. Ties at the maximum can make zero alerts more likely, and a detector can also meet the false-alert criterion by abstaining on everything. The separate detection and coverage gates rule out that latter behavior.

| Calibration groups | Evaluation groups | P(zero evaluation group alerts) under the rank model |
|---:|---:|---:|
| 100 | 300 | 25.0% |
| 300 | 300 | 50.0% |
| 600 | 300 | 66.7% |
| 1,200 | 300 | 80.0% |

Extra calibration groups can raise the upper cutoff and reduce detection. These are scenarios, with no amendment to the allocation or decision rule. At 300 evaluation groups, each of the six codec settings separately needs **224 successful groups** for its exact lower bound to reach 70%. A group succeeds when at least five of its six processed copies flag.

Two other questions have different denominators. Under independent, identically distributed continuous maxima, the true group alert risk after the 100-group calibration is at most 1% in about 63.4% of calibration draws; its 95th percentile is 2.95%. For a *fixed*, already calibrated model with true alert risk exactly 1% on independent evaluation groups, the chance of seeing zero alerts in 300 groups is 4.90%. The 25% rank calculation averages over different calibration draws and their different resulting risks. None of these figures estimates a user's individual file history.

## Verification

For an allowance of k alerted evaluation groups, failure requires that the k+1 largest combined ranks all lie in evaluation. The script computes the resulting fraction with exact integers. Exhaustive enumeration of 3,418 small label allocations reproduced the frequencies and the expected number of alerts. Integer binomial tails independently reproduced the study's confidence-limit boundaries. A regression passes tied maxima and a one-floating-point-step exceedance through the actual calibration and evaluation code, with six controls per group and 300 evaluation groups. It recovers zero and one alert, respectively. No finished-music output was opened. [Calculation](../../scripts/music_verdict_design_assurance.py) · [Policy regression](../../scripts/tests/test_music_verdict_design_assurance.py)

```sh
set -eo pipefail
python3 -B scripts/music_verdict_design_assurance.py | cmp - research/music-verdict-v1/calibration-design-assurance-20261124.json
PYTHONPATH=.tmp/music-verdict-v1/regression-extras-20261010-001 \
  .tmp/music-verdict-v1/python-env/bin/python -B -m unittest discover -s scripts/tests -p 'test_music_verdict_design_assurance.py'
```
