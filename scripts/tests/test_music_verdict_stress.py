"""Verify separation, missing-data and short-file accounting using hand-assigned logits."""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from music_verdict_calibration import Policy

available = all(importlib.util.find_spec(name) is not None for name in ("numpy", "soundfile"))
if available:
    from music_verdict_evaluation import evaluate
    from music_verdict_stress import summarize_stress


@unittest.skipUnless(available, "requires research environment")
class StressTest(unittest.TestCase):
    policy = Policy(1., -1., 1.)

    def test_expected_groups_and_short_routing(self):
        data = {"a": {"lowpass12k": 2., "quiet": -1., "sparse": 0., "short": "unsupported"},
                "b": {"short": -2.}}
        result = summarize_stress(self.policy, ["a", "b", "c"], data, partition="evaluation")
        for row in result["conditions"].values():
            self.assertEqual(sum(row["outcomes"].values()), 3)
        self.assertEqual(result["conditions"]["lowpass12k"]["observed_false_alert_rate"], 1/3)
        self.assertEqual(result["conditions"]["sparse"]["decision_coverage"], 0)
        self.assertEqual(result["short_unexpected_decisions"], 1)
        self.assertEqual(result["short_missing"], 1)

    def test_panels_cannot_mix(self):
        with self.assertRaises(ValueError):
            evaluate(self.policy, {"a": "studio"}, {"a": {"quiet": 0.}}, partition="evaluation")
        for groups, scores, partition in [
                (["a"], {"a": {("baseline", "identity"): 1}}, "evaluation"),
                (["a"], {"a": {"quiet": float("nan")}}, "evaluation"),
                (["a"], {"other": {}}, "evaluation"), (["a"], {}, "train"),
                (["a", "a"], {}, "evaluation")]:
            with self.subTest(groups=groups, scores=scores, partition=partition), self.assertRaises(ValueError):
                summarize_stress(self.policy, groups, scores, partition=partition)
