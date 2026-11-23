import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from music_verdict_calibration import CASES, CONDITIONS, Policy, fit_policy


def matrix(scale=1.):
    # Five out of six conditions per class have the correct sign.
    return {(s,c): scale * (-1 if s == "baseline" else 1) * (-1 if c == "gain" else 1)
            for s,c in CASES}


class CalibrationTest(unittest.TestCase):
    def test_known_bce_optimum_and_inclusive_raw_thresholds(self):
        policy = fit_policy({"a":matrix()}, ["a"], partition="calibration")
        self.assertAlmostEqual(policy.temperature, 1/math.log(5))
        self.assertEqual(policy.score(1)[0], "inconclusive")
        self.assertEqual(policy.score(-1)[0], "inconclusive")
        self.assertAlmostEqual(policy.score(1)[1], 5/6)
        self.assertEqual(policy.score(math.nextafter(1., math.inf))[0], "likely_lossy_derived")
        self.assertEqual(policy.score(math.nextafter(-1., -math.inf))[0], "no_evidence_detected")

    def test_equal_class_weights_despite_six_to_one_counts(self):
        data = {(s,c): 1. if s != "baseline" or c == CONDITIONS[0] else -1. for s,c in CASES}
        policy = fit_policy({"a":data}, ["a"], partition="calibration")
        # Only one sixth of the negatives have the wrong sign: 1/12 total mass.
        self.assertAlmostEqual(policy.temperature, 1/math.log(11))

    def test_replay_and_scale_equivariance(self):
        original = fit_policy({"a":matrix(),"b":matrix(2)}, ["b","a"], partition="calibration")
        self.assertEqual(original, fit_policy({"b":matrix(2),"a":matrix()}, ["a","b"], partition="calibration"))
        scaled = fit_policy({"b":matrix(2e100),"a":matrix(1e100)}, ["a","b"], partition="calibration")
        self.assertAlmostEqual(scaled.temperature/1e100, original.temperature)
        self.assertAlmostEqual(scaled.score(2e100)[1], original.score(2)[1])

    def test_missing_group_case_nonfinite_and_partition(self):
        for groups, ids, partition in [
            ({"a": matrix()}, ["a","b"], "calibration"),
            ({"a": matrix()}, ["a","a"], "calibration"),
            ({"a": matrix()}, ["a"], "evaluation"),
            ({"a": dict(list(matrix().items())[1:])}, ["a"], "calibration"),
            ({"a": {**matrix(), CASES[0]: float("nan")}}, ["a"], "calibration"),
        ]:
            with self.assertRaises(ValueError):
                fit_policy(groups, ids, partition=partition)

    def test_fail_on_nonidentifiable_or_boundary_only_minima(self):
        for data in [matrix(0), matrix(-1),
                     {(s,c): -1 if s=="baseline" else 1 for s,c in CASES}]:
            with self.assertRaises(ValueError):
                fit_policy({"a": data}, ["a"], partition="calibration")

    def test_reject_overflowed_threshold_and_saturated_probability_does_not_move_it(self):
        data = matrix()
        data["baseline","gain"] = sys.float_info.max
        with self.assertRaisesRegex(ValueError, "unrepresentable calibration threshold"):
            fit_policy({"a":data}, ["a"], partition="calibration")
        policy = Policy(1, -900, 900)
        self.assertEqual(policy.score(899), ("inconclusive",1.))
        self.assertEqual(policy.score(900), ("likely_lossy_derived",1.))
