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
SCRIPT = ROOT / "scripts/perceptual_degradation_objective_completion_audit_v7.py"
SPEC = importlib.util.spec_from_file_location("objective_completion_audit_v7", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObjectiveCompletionAuditV7Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))

    def test_report_is_deterministic_exact_and_still_incomplete(self) -> None:
        self.assertEqual(self.report, MODULE.build_report(self.plan))
        self.assertEqual(MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes())
        self.assertTrue(self.report["audio_accessed"])
        self.assertFalse(self.report["summary"]["objective_complete"])
        self.assertEqual(4, self.report["summary"]["satisfied_count"])
        self.assertEqual(10, self.report["summary"]["unsatisfied_count"])

    def test_private_delivery_completion_is_reconciled(self) -> None:
        summary = self.report["summary"]
        self.assertTrue(summary["odaq_clean_reference_delivery_authorization_present"])
        self.assertTrue(summary["odaq_clean_reference_delivery_runner_implemented"])
        self.assertTrue(summary["odaq_clean_reference_delivery_executed"])
        self.assertEqual(16, summary["odaq_clean_reference_delivery_source_count"])
        self.assertEqual(2, summary["odaq_clean_reference_delivery_replay_count"])
        self.assertTrue(summary["odaq_clean_reference_delivery_replays_byte_identical"])
        self.assertTrue(summary["odaq_clean_reference_delivery_attribution_attached"])
        self.assertFalse(summary["odaq_clean_reference_delivery_is_perceptual_evidence"])

    def test_full_reference_requirement_remains_unsatisfied(self) -> None:
        requirement = next(
            item
            for item in self.report["requirements"]
            if item["requirement_id"]
            == "deterministic_human_calibrated_full_reference_oracle_passed"
        )
        self.assertEqual(
            "retained_clean_reference_delivery_complete_drift_validation_authorization_and_execution_pending",
            requirement["state"],
        )
        self.assertFalse(requirement["satisfied"])
        self.assertIn("delivery plumbing only", requirement["reason"])
        self.assertIn("separately committed responsible-human authorization", requirement["next_gate"])

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

    def test_delivery_cannot_be_promoted_by_plan_mutation(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["completion_policy"][
            "private_delivery_completion_counts_as_full_reference_oracle_pass"
        ] = True
        changed["authorization"]["retained_drift_correction_authorized"] = True
        self.assertIn("completion policy differs", MODULE.validate_plan(changed))
        self.assertIn("authorization boundary differs", MODULE.validate_plan(changed))


if __name__ == "__main__":
    unittest.main()
