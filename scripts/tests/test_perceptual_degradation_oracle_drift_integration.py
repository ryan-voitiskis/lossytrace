from __future__ import annotations

import copy
import importlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE = importlib.import_module("perceptual_degradation_oracle_drift_integration")


class OracleDriftIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))

    def test_report_is_deterministic_and_exactly_committed(self) -> None:
        second = MODULE.build_report(self.plan)
        self.assertEqual(MODULE.canonical_bytes(self.report), MODULE.canonical_bytes(second))
        self.assertEqual([], MODULE.validate_report(self.report))
        self.assertEqual(MODULE.canonical_bytes(self.report), MODULE.REPORT_PATH.read_bytes())

    def test_bound_held_out_decisions_drive_exact_resampler_application(self) -> None:
        cases = self.report["cases"]
        self.assertEqual([75, -60, 0], [case["actual_drift_ppm"] for case in cases])
        self.assertEqual([75, -60, 0], [case["selected_correction_ppm"] for case in cases])
        self.assertEqual([True, True, False], [case["apply_correction"] for case in cases])
        self.assertTrue(all(not case["selection_used_held_out_windows"] for case in cases))
        self.assertEqual(
            self.plan["integration"]["coefficient_table_sha256"],
            self.report["coefficient_table_sha256"],
        )

    def test_applied_cases_improve_and_support_post_correction_alignment(self) -> None:
        for case in self.report["cases"][:2]:
            self.assertEqual(64, case["mandatory_discard_frames_each_edge"])
            for metric in case["channel_core_metrics"]:
                self.assertGreaterEqual(metric["correlation_after"], 0.999)
                self.assertGreaterEqual(metric["correlation_improvement"], 0.1)
            self.assertEqual("supported", case["post_correction_alignment"]["status"])
            self.assertEqual([], case["post_correction_alignment"]["reasons"])
            self.assertLessEqual(
                abs(case["post_correction_alignment"]["clock_drift_ppm"]), 1.0
            )

    def test_zero_drift_uses_bit_exact_identity_bypass(self) -> None:
        identity = self.report["cases"][2]
        self.assertFalse(identity["apply_correction"])
        self.assertEqual(0, identity["mandatory_discard_frames_each_edge"])
        self.assertTrue(identity["identity_output_bit_exact"])
        self.assertEqual(identity["input_f64le_sha256"], identity["output_f64le_sha256"])
        self.assertTrue(
            all(
                metric["correlation_after"] == 1.0
                and metric["correlation_improvement"] == 0.0
                for metric in identity["channel_core_metrics"]
            )
        )

    def test_score_free_oracle_and_access_boundaries_remain_closed(self) -> None:
        for case in self.report["cases"]:
            envelope = case["score_free_oracle"]
            self.assertEqual("execution_blocked", envelope["result_state"])
            self.assertEqual(["not_authorized", "not_authorized"], envelope["metric_execution_states"])
            self.assertIsNone(envelope["impairment_severity"])
            self.assertIsNone(envelope["audibility_probability"])
            self.assertFalse(case["retained_audio_accessed"])
            self.assertFalse(case["perceptual_metric_executed"])
            self.assertFalse(case["perceptual_truth_included"])
            self.assertFalse(case["human_response_accessed"])
            self.assertFalse(case["public_verdict_enabled"])
        self.assertFalse(self.report["decision"]["full_reference_oracle_validated"])
        self.assertFalse(self.report["decision"]["no_reference_work_eligible"])

    def test_authority_and_integration_drift_fail_closed(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["authorization"]["retained_audio_access_authorized"] = True
        plan["authorization"]["perceptual_metric_execution_authorized"] = True
        errors = MODULE.validate_plan(plan)
        self.assertIn("authorization boundary differs", errors)

        plan = copy.deepcopy(self.plan)
        plan["integration"]["mandatory_discard_frames_each_edge_when_applied"] = 0
        plan["integration"]["metric_execution"] = True
        self.assertIn("integration contract differs", MODULE.validate_plan(plan))

    def test_report_promotions_fail_closed(self) -> None:
        report = copy.deepcopy(self.report)
        report["cases"][0]["perceptual_metric_executed"] = True
        report["summary"]["human_response_accessed"] = True
        report["decision"]["retained_audio_correction_validated"] = True
        report["decision"]["no_reference_work_eligible"] = True
        errors = MODULE.validate_report(report)
        self.assertIn("case boundary differs: 75:perceptual_metric_executed", errors)
        self.assertIn("summary boundary differs: human_response_accessed", errors)
        self.assertIn(
            "decision must be false: retained_audio_correction_validated", errors
        )
        self.assertIn("decision must be false: no_reference_work_eligible", errors)

    def test_report_is_path_free_and_contains_no_audio_payload(self) -> None:
        encoded = json.dumps(self.report, sort_keys=True)
        self.assertNotIn("/Users/", encoded)
        self.assertNotIn("Application Support", encoded)
        self.assertNotIn(".wav", encoded.lower())
        self.assertNotIn("corrected_channels", encoded)
        self.assertFalse(self.report["resources"]["generated_audio_retained"])


if __name__ == "__main__":
    unittest.main()
