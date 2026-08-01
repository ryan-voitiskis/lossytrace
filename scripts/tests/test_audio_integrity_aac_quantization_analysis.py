import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "analyze-audio-integrity-aac-quantization.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audio_integrity_aac_quantization_analysis",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def row(case_id, group, expectation, score):
    return {
        "case_id": case_id,
        "class": expectation,
        "expectation": expectation,
        "source_group": group,
        "features": {
            feature: score for feature in MODULE.FEATURES
        },
    }


class AacQuantizationAnalysisTests(unittest.TestCase):
    def test_outer_fold_is_stable_and_bounded(self):
        first = MODULE.outer_fold("source-a")
        self.assertEqual(first, MODULE.outer_fold("source-a"))
        self.assertIn(first, range(MODULE.OUTER_FOLD_COUNT))

    def test_fit_rule_uses_strict_boundary(self):
        rows = [
            row(
                f"negative-{index}",
                f"negative-group-{index}",
                "negative",
                0.1,
            )
            for index in range(
                MODULE.MINIMUM_ELIGIBLE_NEGATIVE_GROUPS
            )
        ]
        rows.extend(
            [
                row(
                    f"positive-{index}",
                    f"positive-group-{index}",
                    "controlled_positive",
                    0.2,
                )
                for index in range(5)
            ]
        )
        rule, result = MODULE.fit_rule(rows)
        self.assertEqual(result["false_positives"], 0)
        self.assertEqual(result["true_positives"], 5)
        self.assertFalse(MODULE.prediction(rows[0], rule))
        self.assertTrue(MODULE.prediction(rows[-1], rule))

    def test_confusion_counts_false_positive(self):
        rows = [
            row("negative", "negative-group", "negative", 0.1),
            row(
                "positive",
                "positive-group",
                "controlled_positive",
                0.2,
            ),
        ]
        result = MODULE.confusion(rows, [True, True])
        self.assertEqual(result["false_positives"], 1)
        self.assertEqual(result["true_positives"], 1)


if __name__ == "__main__":
    unittest.main()
