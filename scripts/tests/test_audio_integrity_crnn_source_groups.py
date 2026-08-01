import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "analyze-audio-integrity-crnn-source-groups.py"
)
SPEC = importlib.util.spec_from_file_location("crnn_source_groups", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def row(case_id, group, expectation, prediction, score):
    return {
        "case_id": case_id,
        "source_group": group,
        "domain": "domain-a",
        "expectation": expectation,
        "predicted_positive": prediction,
        "score": score,
    }


class CrnnSourceGroupAnalysisTests(unittest.TestCase):
    def test_analysis_distinguishes_group_shortcut_from_positive_only_alert(self):
        report = {
            "heldout_opened": False,
            "public_verdict_enabled": False,
            "disposition": "failed_development_source_domain_gate",
            "case_predictions": [
                row("a-neg", "a", "negative", True, 0.7),
                row("a-pos", "a", "controlled_positive", True, 0.8),
                row("b-neg", "b", "negative", False, 0.2),
                row("b-pos", "b", "controlled_positive", True, 0.9),
                row("c-neg", "c", "negative", False, 0.1),
                row("c-pos", "c", "controlled_positive", False, 0.3),
            ],
        }
        result = MODULE.analyze(report)
        self.assertEqual(
            result["summary"],
            {
                "any_alert_source_group_count": 2,
                "negative_alert_source_group_count": 1,
                "all_cases_alert_source_group_count": 1,
                "positive_only_alert_source_group_count": 1,
            },
        )
        self.assertEqual(result["disposition"], "failed_source_group_specificity_check")

    def test_duplicate_case_predictions_fail_closed(self):
        report = {
            "heldout_opened": False,
            "public_verdict_enabled": False,
            "disposition": "failed_development_source_domain_gate",
            "case_predictions": [
                row("duplicate", "a", "negative", False, 0.1),
                row("duplicate", "a", "controlled_positive", True, 0.9),
            ],
        }
        with self.assertRaisesRegex(SystemExit, "duplicate case prediction"):
            MODULE.analyze(report)

    def test_nested_transfer_report_with_no_pcm_alerts_passes(self):
        report = {
            "heldout_opened": False,
            "public_verdict_enabled": False,
            "disposition": (
                "development_transfer_gate_passed_requires_independent_review"
            ),
            "transfer": {
                "case_predictions": [
                    row("a-neg", "a", "negative", False, 0.2),
                    row("a-pos", "a", "controlled_positive", True, 0.8),
                    row("b-neg", "b", "negative", False, 0.1),
                    row("b-pos", "b", "controlled_positive", False, 0.3),
                ]
            },
        }
        result = MODULE.analyze(report)
        self.assertEqual(
            result["input_prediction_set"],
            "transfer.case_predictions",
        )
        self.assertEqual(
            result["disposition"],
            "passed_source_group_specificity_check",
        )

    def test_unrecognized_disposition_fails_closed(self):
        report = {
            "heldout_opened": False,
            "public_verdict_enabled": False,
            "disposition": "production_ready",
            "case_predictions": [
                row("a-neg", "a", "negative", False, 0.2),
            ],
        }
        with self.assertRaisesRegex(SystemExit, "allowed development disposition"):
            MODULE.analyze(report)


if __name__ == "__main__":
    unittest.main()
