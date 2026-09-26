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
MODULE = importlib.import_module(
    "perceptual_degradation_oracle_drift_estimator_integration"
)


class OracleDriftEstimatorIntegrationTest(unittest.TestCase):
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

    def test_training_selection_and_apply_decisions_match_frozen_inventory(self) -> None:
        cases = self.report["cases"]
        estimator = self.plan["estimator"]
        self.assertEqual(
            estimator["actual_drift_ppm_cases"],
            [case["actual_drift_ppm"] for case in cases],
        )
        self.assertEqual(
            estimator["expected_selected_correction_ppm"],
            [case["decision"]["selected_correction_ppm"] for case in cases],
        )
        self.assertEqual(
            estimator["expected_apply_correction"],
            [case["decision"]["apply_correction"] for case in cases],
        )
        self.assertTrue(
            all(
                case["decision"]["selection_used_held_out_windows"] is False
                for case in cases
            )
        )

    def test_held_out_rule_applies_only_material_improvements(self) -> None:
        threshold = self.plan["estimator"][
            "minimum_held_out_correlation_improvement_to_apply"
        ]
        for case in self.report["cases"]:
            improvement = case["decision"][
                "held_out_mean_correlation_improvement_proxy"
            ]
            if case["decision"]["apply_correction"]:
                self.assertGreaterEqual(improvement, threshold)
            elif case["actual_drift_ppm"] != 0:
                self.assertLess(improvement, threshold)

    def test_applied_cases_use_exact_resampler_and_improve_every_channel(self) -> None:
        applied = [
            case for case in self.report["cases"]
            if case["decision"]["apply_correction"]
        ]
        self.assertEqual([75, -60, 100, -100], [case["actual_drift_ppm"] for case in applied])
        for case in applied:
            self.assertTrue(case["resampler_invoked"])
            self.assertTrue(case["resampler_correction_applied"])
            self.assertFalse(case["output_bit_exact_to_observed"])
            self.assertEqual(64, case["mandatory_discard_frames_each_edge"])
            for metric in case["channel_core_metrics"]:
                self.assertGreaterEqual(metric["correlation_after"], 0.999)
                self.assertGreaterEqual(metric["correlation_improvement"], 0.1)

    def test_low_nonzero_drifts_are_bit_exact_passthrough(self) -> None:
        cases = {case["actual_drift_ppm"]: case for case in self.report["cases"]}
        for drift in (20, -20):
            case = cases[drift]
            self.assertFalse(case["decision"]["apply_correction"])
            self.assertFalse(case["resampler_invoked"])
            self.assertFalse(case["resampler_correction_applied"])
            self.assertTrue(case["output_bit_exact_to_observed"])
            self.assertEqual(case["input_f64le_sha256"], case["output_f64le_sha256"])

    def test_zero_drift_uses_exact_identity_bypass(self) -> None:
        identity = self.report["cases"][2]
        self.assertEqual(0, identity["actual_drift_ppm"])
        self.assertTrue(identity["resampler_invoked"])
        self.assertFalse(identity["resampler_correction_applied"])
        self.assertTrue(identity["output_bit_exact_to_observed"])
        self.assertEqual(identity["input_f64le_sha256"], identity["output_f64le_sha256"])

    def test_post_decision_alignment_and_score_free_boundaries_hold(self) -> None:
        for case in self.report["cases"]:
            self.assertEqual("supported", case["post_decision_alignment"]["status"])
            self.assertEqual([], case["post_decision_alignment"]["reasons"])
            envelope = case["score_free_oracle"]
            self.assertEqual("execution_blocked", envelope["result_state"])
            self.assertEqual(
                ["not_authorized", "not_authorized"],
                envelope["metric_execution_states"],
            )
            self.assertIsNone(envelope["impairment_severity"])
            self.assertIsNone(envelope["audibility_probability"])
        self.assertFalse(self.report["decision"]["full_reference_oracle_validated"])
        self.assertFalse(self.report["decision"]["no_reference_work_eligible"])

    def test_authority_and_estimator_mutations_fail_closed(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["authorization"]["retained_audio_access_authorized"] = True
        plan["authorization"]["perceptual_metric_execution_authorized"] = True
        self.assertIn("authorization boundary differs", MODULE.validate_plan(plan))

        plan = copy.deepcopy(self.plan)
        plan["estimator"]["selection_uses_held_out_windows"] = True
        self.assertIn("estimator contract differs", MODULE.validate_plan(plan))

        plan = copy.deepcopy(self.plan)
        plan["correction"]["nonzero_no_apply_policy"] = "resample_anyway"
        self.assertIn("correction contract differs", MODULE.validate_plan(plan))

    def test_report_promotions_fail_closed(self) -> None:
        report = copy.deepcopy(self.report)
        report["cases"][0]["perceptual_metric_executed"] = True
        report["summary"]["human_response_accessed"] = True
        report["decision"]["retained_audio_correction_validated"] = True
        report["decision"]["no_reference_work_eligible"] = True
        errors = MODULE.validate_report(report)
        self.assertIn("case boundary differs: 75:perceptual_metric_executed", errors)
        self.assertIn("summary boundary differs: human_response_accessed", errors)
        self.assertIn("decision must be false: retained_audio_correction_validated", errors)
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
