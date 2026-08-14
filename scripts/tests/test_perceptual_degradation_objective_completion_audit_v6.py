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
SCRIPT = ROOT / "scripts/perceptual_degradation_objective_completion_audit_v6.py"
SPEC = importlib.util.spec_from_file_location("objective_completion_audit_v6", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObjectiveCompletionAuditV6Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))

    def test_report_is_deterministic_exact_and_still_incomplete(self) -> None:
        second = MODULE.build_report(self.plan)
        self.assertEqual(self.report, second)
        self.assertEqual(
            MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes()
        )
        self.assertFalse(self.report["summary"]["objective_complete"])
        self.assertEqual(14, self.report["summary"]["requirement_count"])
        self.assertEqual(4, self.report["summary"]["satisfied_count"])
        self.assertEqual(10, self.report["summary"]["unsatisfied_count"])

    def test_readiness_is_recorded_without_authorization_or_execution(self) -> None:
        summary = self.report["summary"]
        self.assertTrue(summary["retained_drift_validation_protocol_ready"])
        self.assertFalse(summary["retained_drift_validation_authorization_present"])
        self.assertFalse(summary["retained_drift_validation_live_runner_implemented"])
        self.assertFalse(summary["retained_drift_validation_executed"])
        self.assertFalse(summary["retained_drift_validation_complete"])
        self.assertEqual(16, summary["retained_drift_future_source_count"])
        self.assertEqual(112, summary["retained_drift_future_case_count"])
        self.assertEqual(9, summary["retained_drift_readiness_gate_pass_count"])

    def test_full_reference_requirement_remains_unsatisfied(self) -> None:
        requirement = next(
            item
            for item in self.report["requirements"]
            if item["requirement_id"]
            == "deterministic_human_calibrated_full_reference_oracle_passed"
        )
        self.assertEqual(
            "retained_drift_validation_protocol_frozen_authorization_and_execution_pending",
            requirement["state"],
        )
        self.assertFalse(requirement["satisfied"])
        self.assertIn("112 technical cases", requirement["reason"])
        self.assertIn("No retained reference was read", requirement["reason"])

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
            "retained_validation_protocol_readiness_counts_as_full_reference_oracle_pass"
        ] = True
        plan["completion_policy"][
            "retained_validation_protocol_readiness_counts_as_authorization"
        ] = True
        self.assertIn("completion policy differs", MODULE.validate_plan(plan))


if __name__ == "__main__":
    unittest.main()
