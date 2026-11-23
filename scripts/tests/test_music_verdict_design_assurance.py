"""Verify the rank calculation against the locked calibrator and grouped evaluation policy."""
import importlib.util
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from music_verdict_calibration import CASES, fit_policy
from music_verdict_design_assurance import alert_allowance, pass_fraction, verify_combinations

if importlib.util.find_spec("numpy") is not None:
    from music_verdict_evaluation import evaluate
else:
    evaluate = None


class AssuranceTest(unittest.TestCase):
    def test_exact_small_allocations_and_study_boundary(self):
        self.assertEqual(verify_combinations(), 3418)
        self.assertEqual(alert_allowance(298), -1)
        self.assertEqual(alert_allowance(300), 0)
        self.assertEqual(alert_allowance(500), 1)
        self.assertEqual(pass_fraction(100, 300, 0), 1/4)

    @unittest.skipIf(evaluate is None, "requires research numpy environment")
    def test_group_max_and_tied_score_follow_the_actual_calibrated_cutoff(self):
        # Raw scores are constructed numbers. Small positive logits on negative
        # cases ensure the temperature fit has a finite interior minimum.
        def cells(top):
            return {(state, cond): (6.0 if state != "baseline" else top if cond == "gain" else -4.0)
                    for state, cond in CASES}
        calibration = {f"cal-{i}": cells(i/256) for i in range(100)}
        policy = fit_policy(calibration, list(calibration), partition="calibration")
        maximum = 99/256
        self.assertEqual(policy.high_logit, math.nextafter(maximum, math.inf))
        strata = {f"eval-{i}": str(i % 3) for i in range(300)}
        scores = {key: cells(maximum) for key in strata}
        def inspect():
            return evaluate(policy, strata, scores, partition="evaluation")
        tied = inspect()
        self.assertEqual(tied["group_false_alerts"]["known_alerts"], 0)
        self.assertTrue(tied["metric_checks"]["negative_group_upper_bound"])
        scores["eval-0"] = cells(policy.high_logit)
        crossed = inspect()
        self.assertEqual(crossed["group_false_alerts"]["known_alerts"], 1)
        self.assertFalse(crossed["metric_checks"]["negative_group_upper_bound"])
        self.assertTrue(crossed["metric_checks"]["each_setting_lower_bound"])


if __name__ == "__main__":
    unittest.main()
