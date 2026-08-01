import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "analyze-audio-integrity-exact-hybrid-ablation.py"
)
SPEC = importlib.util.spec_from_file_location("exact_hybrid_evaluation", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def row(case_id, domain, group, expectation, score, edge=True):
    return {
        "case_id": case_id,
        "source_domain": domain,
        "source_group": group,
        "expectation": expectation,
        "class": "mp3_128" if expectation == "controlled_positive" else "pcm",
        "provenance_tier": "tier_a_confirmed",
        "baseline_edge": {
            "spectral_edge_drop_db": 4.0 if edge else 2.0,
            "spectral_edge_persistence": 0.01,
        },
        "probe": {"aggregate": {"score": score}},
    }


class ExactHybridEvaluationTest(unittest.TestCase):
    def test_replay_must_bind_the_same_ablation_report(self):
        replay = {
            "schema_version": 1,
            "feature_version": 0,
            "public_verdict_enabled": False,
            "inputs": {"ablation_report_sha256": "expected"},
            "replay": {"passed": True, "mismatch_case_count": 0},
        }
        MODULE.validate_replay(replay, "expected")
        with self.assertRaisesRegex(ValueError, "did not pass"):
            MODULE.validate_replay(replay, "different")

    def test_public_parent_and_transcode_components_are_one_domain_family(self):
        self.assertEqual(
            MODULE.source_domain_family(
                {"case_id": "a", "source_domain": "public_tier_a_originals"}
            ),
            "public_tier_a",
        )
        self.assertEqual(
            MODULE.source_domain_family(
                {"case_id": "b", "source_domain": "public_tier_a_controlled"}
            ),
            "public_tier_a",
        )

    def test_leave_domain_thresholds_do_not_use_held_domain(self):
        rows = [
            row("a-neg", "a", "a-neg", "negative", 0.1),
            row("a-pos", "a", "a-pos", "controlled_positive", 0.8),
            row("b-neg", "b", "b-neg", "negative", 0.2),
            row("b-pos", "b", "b-pos", "controlled_positive", 0.9),
        ]
        result = MODULE.evaluate_row(rows, "score")
        folds = {fold["held_out_source_domain"]: fold for fold in result["folds"]}
        self.assertEqual(folds["a"]["training_maximum_negative_score"], 0.2)
        self.assertEqual(folds["b"]["training_maximum_negative_score"], 0.1)
        self.assertEqual(
            result["pooled_out_of_fold"]["negative_groups"][
                "predicted_source_group_count"
            ],
            1,
        )

    def test_edge_is_a_predictor_not_a_support_exclusion(self):
        groups = MODULE.group_outcomes(
            [row("negative", "a", "g", "negative", 0.9, edge=False)],
            "score",
            0.5,
            "negative",
        )
        self.assertTrue(groups["g"]["supported"])
        self.assertFalse(groups["g"]["predicted"])

    def test_wilson_zero_alert_upper_requires_sufficient_groups(self):
        _, upper_small = MODULE.wilson_bounds(0, 10)
        _, upper_large = MODULE.wilson_bounds(0, 150)
        self.assertGreater(upper_small, MODULE.MAX_NEGATIVE_ALERT_UPPER)
        self.assertLess(upper_large, MODULE.MAX_NEGATIVE_ALERT_UPPER)


if __name__ == "__main__":
    unittest.main()
