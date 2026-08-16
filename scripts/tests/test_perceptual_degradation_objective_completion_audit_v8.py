from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SCRIPT = ROOT / "scripts/perceptual_degradation_objective_completion_audit_v8.py"
SPEC = importlib.util.spec_from_file_location("objective_completion_audit_v8", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObjectiveCompletionAuditV8Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))

    def test_report_is_deterministic_exact_and_still_incomplete(self) -> None:
        self.assertEqual(self.report, MODULE.build_report(self.plan))
        self.assertEqual(
            MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes()
        )
        self.assertTrue(self.report["audio_accessed"])
        self.assertFalse(self.report["summary"]["objective_complete"])
        self.assertEqual(4, self.report["summary"]["satisfied_count"])
        self.assertEqual(10, self.report["summary"]["unsatisfied_count"])

    def test_reproducible_technical_negative_is_reconciled(self) -> None:
        summary = self.report["summary"]
        self.assertTrue(summary["retained_drift_validation_authorization_present"])
        self.assertTrue(summary["retained_drift_validation_live_runner_implemented"])
        self.assertTrue(summary["retained_drift_validation_executed"])
        self.assertTrue(summary["retained_drift_protocol_execution_complete"])
        self.assertTrue(summary["retained_drift_validation_reproducible_technical_negative"])
        self.assertEqual(2, summary["retained_drift_validation_replay_count"])
        self.assertEqual(16, summary["retained_drift_validation_reference_count"])
        self.assertEqual(112, summary["retained_drift_validation_case_count_per_replay"])
        self.assertEqual(16, summary["retained_drift_validation_gate_pass_count"])
        self.assertEqual(17, summary["retained_drift_validation_gate_count"])
        self.assertFalse(summary["retained_drift_validation_all_gates_pass"])
        self.assertFalse(summary["retained_drift_validation_is_perceptual_evidence"])

    def test_full_reference_requirement_remains_unsatisfied(self) -> None:
        requirement = next(
            item
            for item in self.report["requirements"]
            if item["requirement_id"]
            == "deterministic_human_calibrated_full_reference_oracle_passed"
        )
        self.assertEqual(
            "retained_clean_reference_controlled_drift_execution_complete_reproducible_technical_negative",
            requirement["state"],
        )
        self.assertFalse(requirement["satisfied"])
        self.assertIn("16 of 17 gates passed", requirement["reason"])
        self.assertIn("not human calibration", requirement["reason"])

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
        self.assertFalse(self.report["metrics_executed"])
        self.assertFalse(self.report["no_reference_training_performed"])
        self.assertFalse(self.report["public_verdict_enabled"])

    def test_result_cannot_be_promoted_by_plan_mutation(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["completion_policy"][
            "retained_drift_failed_gate_counts_as_scientific_completion"
        ] = True
        changed["claim_boundary"]["retained_drift_all_predeclared_gates_pass"] = True
        self.assertIn("completion policy differs", MODULE.validate_plan(changed))
        self.assertIn("claim boundary must remain false", MODULE.validate_plan(changed))


if __name__ == "__main__":
    unittest.main()
