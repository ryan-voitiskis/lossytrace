"""Evaluation accounting checks. All scores are constructed without audio."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from music_verdict_calibration import CASES, CONDITIONS, Policy, fit_policy

if importlib.util.find_spec("numpy") is not None:
    from music_verdict_evaluation import evaluate
else:
    evaluate = None


POLICY = Policy(1., -1., 1.)


def report(allocation, scores):
    return evaluate(POLICY, allocation, scores, partition="evaluation")


def correct():
    return {key: -4. if key[0] == "baseline" else 4. for key in CASES}


@unittest.skipIf(evaluate is None, "requires isolated synthetic-requirements research environment")
class EvaluationTest(unittest.TestCase):
    def test_full_design_and_one_false_alert(self):
        allocation = {f"group-{i:03}": f"chain-{i % 3}" for i in range(300)}
        scores = {group: correct() for group in allocation}
        result = report(allocation, scores)
        self.assertTrue(all(result["metric_checks"].values()))
        alerts = result["group_false_alerts"]
        self.assertAlmostEqual(alerts["upper_95_observed"], 1 - .05 ** (1 / 300))
        self.assertEqual(result["positive"]["cases"], 10800)
        self.assertEqual(result["negative"]["cases"], 1800)
        self.assertNotIn("group-000", json.dumps(result, allow_nan=False))
        for cond in CONDITIONS:
            scores["group-000"]["baseline", cond] = 4.
        result = report(allocation, scores)
        self.assertFalse(result["metric_checks"]["negative_group_upper_bound"])
        self.assertEqual(result["group_false_alerts"]["known_alerts"], 1)
        self.assertEqual(result["negative"]["outcomes"]["likely_lossy_derived"], 6)

    def test_five_of_six_with_unsupported_and_missing(self):
        scores = {group: correct() for group in ("a", "b")}
        scores["a"]["mp3-320", "identity"] = "unsupported"
        scores["b"]["mp3-320", "identity"] = 0.
        del scores["b"]["mp3-320", "gain"]
        result = report({"a": "one", "b": "one", "c": "two"}, scores)
        setting = result["group_detection_by_setting"]["mp3-320"]
        self.assertEqual(setting["groups_with_at_least_five_flags"], 1)
        self.assertEqual(setting["groups"], 3)
        self.assertEqual(result["group_false_alerts"]["unresolved_groups"], 1)
        self.assertEqual(result["positive"]["cases"], 108)
        counts = result["positive"]["outcomes"]
        self.assertEqual((counts["missing"], counts["unsupported"], counts["inconclusive"]), (37, 1, 1))
        self.assertAlmostEqual(result["positive"]["decision_coverage"], 69 / 108)
        self.assertIsNone(result["metric_checks"]["brier"])
        self.assertIsNone(result["metric_checks"]["ece"])
        self.assertFalse(result["metric_checks"]["evaluation_strata"])
        self.assertIsNone(result["strata"]["two"]["meets_stratum_limits"])
        self.assertEqual(result["calibration_at_equal_class_prior"]["scored_cases"], 82)
        self.assertEqual(result["outcomes_by_case"]["mp3-320"]["gain"]["missing"], 2)

    def test_minimum_successful_groups_for_one_setting(self):
        allocation = {str(i): str(i % 3) for i in range(300)}
        scores = {group: correct() for group in allocation}
        for i in range(223, 300):
            for condition in CONDITIONS[:2]:
                scores[str(i)]["aac-256", condition] = 0.
        below = report(allocation, scores)
        self.assertTrue(below["metric_checks"]["encoded_detection"])
        self.assertFalse(below["metric_checks"]["each_setting_lower_bound"])
        scores["223"]["aac-256", CONDITIONS[0]] = 4.
        above = report(allocation, scores)
        self.assertTrue(above["metric_checks"]["each_setting_lower_bound"])
        self.assertAlmostEqual(above["group_detection_by_setting"]["aac-256"]["lower_95"], .70197502146)

    def test_fitted_policy_matches_independent_scalar_calibration_metrics(self):
        calibration = {k: (1. if k[0] != "baseline" else -1.) * (-1. if k[1] == "gain" else 1.)
                       for k in CASES}
        policy = fit_policy({"cal": calibration}, ["cal"], partition="calibration")
        allocation = {"a": "one", "b": "one", "c": "two", "d": "two"}
        rows = {group: {key: math.sin(i + j) * (i + 1) for j, key in enumerate(CASES)}
                for i, group in enumerate(allocation)}
        metrics = evaluate(policy, allocation, rows, partition="evaluation")["calibration_at_equal_class_prior"]
        errors = []
        gaps = [[] for _ in range(10)]
        for cells in rows.values():
            for (state, _), logit in cells.items():
                encoded = int(state != "baseline")
                probability = 1. / (1. + math.exp(-math.log(5) * logit))
                weight = .5 / len(rows) / (36 if encoded else 6)
                errors.append(weight * (probability - encoded) ** 2)
                gaps[int(probability * 10)].append(weight * (probability - encoded))
        self.assertAlmostEqual(metrics["brier"], math.fsum(errors), places=14)
        self.assertAlmostEqual(metrics["ece_10"], sum(abs(math.fsum(gap)) for gap in gaps), places=14)

    def test_calibration_weights_and_abstention(self):
        # All 42 forecasts are 0.75. The balanced encoded fraction is 1/2.
        rows = dict.fromkeys(CASES, math.log(3))
        result = report({"b": "chain", "a": "chain"}, {"a": rows, "b": rows})
        calibration = result["calibration_at_equal_class_prior"]
        self.assertAlmostEqual(calibration["brier"], .3125)
        self.assertAlmostEqual(calibration["ece_10"], .25)
        self.assertEqual(calibration["bins"][7]["cases"], 84)
        self.assertAlmostEqual(calibration["bins"][7]["encoded_fraction"], .5)
        self.assertAlmostEqual(calibration["bins"][7]["balanced_mass"], 1.)
        self.assertAlmostEqual(calibration["group_bootstrap"]["ece_95_percentile"][0], .25)
        for prior, precision in result["flag_precision_by_assumed_encoded_prior"].items():
            self.assertAlmostEqual(precision, float(prior))
        no_decisions = report({"a": "chain"}, {"a": dict.fromkeys(CASES, 0.)})
        negative, positive = no_decisions["negative"], no_decisions["positive"]
        self.assertEqual(negative["decision_coverage"] + positive["decision_coverage"], 0.)
        self.assertEqual(no_decisions["calibration_at_equal_class_prior"]["bins"][5]["cases"], 42)
        self.assertIsNone(no_decisions["flag_precision_by_assumed_encoded_prior"]["0.01"])

    def test_bootstrap_takes_whole_groups_and_preserves_strata(self):
        # One stratum has one perfect and one perfectly reversed source. A second
        # stratum has two perfect sources. Cluster-resampled Brier ranges 0..0.5.
        perfect = {key: -1000. if key[0] == "baseline" else 1000. for key in CASES}
        reversed_scores = {key: -value for key, value in perfect.items()}
        allocation = dict(a="one", b="one", c="two", d="two")
        scores = dict(a=perfect, b=reversed_scores, c=perfect, d=perfect)
        calibration = report(allocation, scores)["calibration_at_equal_class_prior"]
        self.assertAlmostEqual(calibration["brier"], .25)
        self.assertEqual(calibration["bins"][9]["mean_probability"], 1.)
        interval = calibration["group_bootstrap"]["brier_95_percentile"]
        self.assertAlmostEqual(interval[0], 0.)
        self.assertAlmostEqual(interval[1], .5)
        self.assertEqual(calibration, report(dict(reversed(allocation.items())), scores)["calibration_at_equal_class_prior"])

    def test_quarantines_missing_controls_and_keeps_small_strata(self):
        allocation = {str(i): "large" for i in range(30)} | {"extra": "small"}
        scores = {group: correct() for group in allocation}
        for group in ("0", "1"):
            del scores[group]["baseline", "gain"]
        scores["2"]["baseline", "gain"] = "unsupported"
        result = report(allocation, scores)
        large = result["strata"]["large"]
        self.assertEqual(large["maximum_group_alert_rate"], 2 / 30)
        self.assertEqual(large["observed_group_alert_rate"], 0.)
        self.assertFalse(large["meets_stratum_limits"])
        self.assertIsNone(result["strata"]["small"]["meets_stratum_limits"])
        self.assertEqual(result["negative"]["outcomes"]["unsupported"], 1)

    def test_reject_unknown_ids_cases_and_bad_scores(self):
        for scores in ({"extra": {}}, {"a": {("new", "identity"): 0.}},
                       {"a": {CASES[0]: float("nan")}}, {"a": {CASES[0]: None}}):
            with self.assertRaises(ValueError):
                report({"a": "stratum"}, scores)
        with self.assertRaises(ValueError):
            evaluate(POLICY, {"a": "stratum"}, {}, partition="calibration")
