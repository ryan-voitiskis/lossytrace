import importlib.util
import json
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/analyze-audio-integrity-codec-projection.py"
CONFIG_PATH = ROOT / "research/codec-projection/oracle-v1/config.json"
SPEC = importlib.util.spec_from_file_location("codec_projection_analysis", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def row(case_id, domain, group, expectation, r1, r2, class_name=None):
    supported = r1 is not None and r2 is not None
    return {
        "case_id": case_id,
        "source_domain": domain,
        "source_group": group,
        "expectation": expectation,
        "class": class_name
        or ("mp3_128" if expectation == "controlled_positive" else "pcm"),
        "measurement": {
            "support": {"supported": supported},
            "scores": (
                {
                    "r1_cycle_residual_retention": r1,
                    "r2_residual_directional_recurrence": r2,
                }
                if supported
                else None
            ),
        },
    }


class CodecProjectionAnalysisTests(unittest.TestCase):
    def test_threshold_uses_only_other_domain_negatives(self):
        rows = [
            row("a-neg", "a", "a-neg", "negative", 0.1, 0.3),
            row("a-pos", "a", "a-pos", "controlled_positive", 0.8, 0.9),
            row("b-neg", "b", "b-neg", "negative", 0.2, 0.4),
            row("b-pos", "b", "b-pos", "controlled_positive", 0.9, 0.95),
        ]
        evaluation, _ = MODULE.evaluate_representation(
            rows, "r1_cycle_residual_retention", CONFIG
        )
        folds = {fold["held_out_source_domain"]: fold for fold in evaluation["folds"]}
        self.assertEqual(folds["a"]["training_maximum_negative_score"], 0.2)
        self.assertEqual(folds["b"]["training_maximum_negative_score"], 0.1)
        self.assertEqual(
            folds["a"]["threshold_inclusive"], math.nextafter(0.2, math.inf)
        )
        self.assertEqual(
            evaluation["pooled_out_of_fold"]["negative_groups"]["predicted_count"],
            1,
        )

    def test_negative_group_uses_any_case_and_positive_group_uses_median(self):
        rows = [
            row("n1", "a", "negative-group", "negative", 0.1, 0.1),
            row("n2", "a", "negative-group", "negative", 0.8, 0.8),
            row("p1", "a", "positive-group", "controlled_positive", 0.4, 0.4),
            row("p2", "a", "positive-group", "controlled_positive", 0.9, 0.9),
            row("p3", "a", "positive-group", "controlled_positive", 0.6, 0.6),
        ]
        negatives, positives = MODULE.group_outcomes(
            rows, "r1_cycle_residual_retention", 0.65, CONFIG["selection"]
        )
        self.assertTrue(negatives["negative-group"]["predicted"])
        self.assertEqual(negatives["negative-group"]["score"], 0.8)
        self.assertFalse(positives["positive-group"]["predicted"])
        self.assertEqual(positives["positive-group"]["score"], 0.6)

    def test_representation_evaluation_is_order_independent(self):
        rows = [
            row("a-neg", "a", "a-neg", "negative", 0.1, 0.2),
            row("a-pos", "a", "a-pos", "controlled_positive", 0.8, 0.7),
            row("b-neg", "b", "b-neg", "negative", 0.2, 0.1),
            row("b-pos", "b", "b-pos", "controlled_positive", 0.9, 0.8),
        ]
        first, _ = MODULE.evaluate_representation(
            rows, "r1_cycle_residual_retention", CONFIG
        )
        second, _ = MODULE.evaluate_representation(
            list(reversed(rows)), "r1_cycle_residual_retention", CONFIG
        )
        self.assertEqual(first, second)

    def test_path_redaction_rejects_identity_and_absolute_path(self):
        MODULE.assert_path_free({"inputs": {"sha256": "a" * 64}})
        with self.assertRaisesRegex(ValueError, "private key"):
            MODULE.assert_path_free({"case_id": "private-case"})
        with self.assertRaisesRegex(ValueError, "absolute path"):
            MODULE.assert_path_free({"note": "/private/audio.flac"})

    def test_zero_alert_wilson_gate_needs_enough_supported_groups(self):
        _, small = MODULE.wilson_bounds(0, 100, CONFIG["evaluation"]["one_sided_95_z"])
        _, large = MODULE.wilson_bounds(0, 150, CONFIG["evaluation"]["one_sided_95_z"])
        self.assertGreater(
            small,
            CONFIG["evaluation"]["maximum_negative_one_sided_95_wilson_upper"],
        )
        self.assertLess(
            large,
            CONFIG["evaluation"]["maximum_negative_one_sided_95_wilson_upper"],
        )


if __name__ == "__main__":
    unittest.main()
