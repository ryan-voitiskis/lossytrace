from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_objective_completion_audit_v4.py"
SPEC = importlib.util.spec_from_file_location("objective_completion_audit_v4", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObjectiveCompletionAuditV4Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))

    def test_report_is_deterministic_exact_and_still_incomplete(self) -> None:
        second = MODULE.build_report(self.plan)
        self.assertEqual(self.report, second)
        self.assertEqual(MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes())
        self.assertFalse(self.report["summary"]["objective_complete"])
        self.assertEqual(14, self.report["summary"]["requirement_count"])
        self.assertEqual(4, self.report["summary"]["satisfied_count"])
        self.assertEqual(10, self.report["summary"]["unsatisfied_count"])

    def test_synthetic_integration_is_recorded_without_scientific_promotion(self) -> None:
        summary = self.report["summary"]
        self.assertTrue(summary["oracle_drift_synthetic_integration_passed"])
        self.assertTrue(
            summary["oracle_drift_resampler_integrated_on_synthetic_pcm"]
        )
        self.assertFalse(
            summary["oracle_drift_resampler_integrated_on_retained_audio"]
        )
        self.assertEqual(3, summary["oracle_drift_synthetic_case_count"])
        self.assertEqual(12, summary["oracle_drift_synthetic_gate_pass_count"])
        self.assertFalse(summary["oracle_drift_retained_validation_complete"])
        checks = self.report["evidence_checks"]
        self.assertTrue(checks["oracle_drift_held_out_apply_decision_bound"])
        self.assertTrue(checks["oracle_drift_exact_resampler_integrated_on_synthetic_pcm"])
        self.assertTrue(checks["oracle_drift_score_free_envelope_preserved"])
        self.assertFalse(checks["oracle_drift_retained_audio_access_authorized"])
        self.assertFalse(checks["oracle_drift_retained_validation_complete"])
        self.assertFalse(checks["oracle_drift_real_audio_estimation_validated"])
        self.assertFalse(
            checks["oracle_drift_synthetic_integration_is_full_reference_validation"]
        )

    def test_full_reference_oracle_requirement_remains_unsatisfied(self) -> None:
        requirement = next(
            item
            for item in self.report["requirements"]
            if item["requirement_id"]
            == "deterministic_human_calibrated_full_reference_oracle_passed"
        )
        self.assertEqual(
            "synthetic_drift_integration_passed_retained_and_scientific_validation_closed",
            requirement["state"],
        )
        self.assertFalse(requirement["satisfied"])
        self.assertIn("does not validate real drift estimation", requirement["reason"])

    def test_only_contract_and_safety_requirements_are_satisfied(self) -> None:
        satisfied = {
            item["requirement_id"]
            for item in self.report["requirements"]
            if item["satisfied"]
        }
        self.assertEqual(
            {
                "estimand_is_degradation_not_history",
                "declared_playback_chain_qualified",
                "public_cli_remains_verdict_free",
                "rigorous_negative_is_accepted_success",
            },
            satisfied,
        )
        self.assertFalse(self.report["no_reference_training_performed"])
        self.assertFalse(self.report["public_verdict_enabled"])

    def test_authority_and_promotion_policy_mutations_fail_closed(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["authorization"]["retained_audio_access_authorized"] = True
        plan["authorization"]["perceptual_metric_execution_authorized"] = True
        self.assertIn("authorization boundary differs", MODULE.validate_plan(plan))

        plan = copy.deepcopy(self.plan)
        plan["completion_policy"][
            "synthetic_drift_integration_counts_as_full_reference_oracle_pass"
        ] = True
        plan["completion_policy"][
            "technical_alignment_support_counts_as_human_calibration"
        ] = True
        self.assertIn("completion policy differs", MODULE.validate_plan(plan))


if __name__ == "__main__":
    unittest.main()
