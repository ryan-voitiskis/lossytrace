from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_objective_completion_audit.py"
PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "objective-completion-audit-plan.json"
)
SPEC = importlib.util.spec_from_file_location("objective_completion_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class ObjectiveCompletionAuditTest(unittest.TestCase):
    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate_plan(plan()))

    def test_report_is_deterministic_and_incomplete(self) -> None:
        first = MODULE.build_report(plan())
        second = MODULE.build_report(plan())
        self.assertEqual(first, second)
        self.assertFalse(first["summary"]["objective_complete"])
        self.assertIsNone(first["summary"]["final_recommendation"])
        self.assertEqual(14, first["summary"]["requirement_count"])
        self.assertEqual(4, first["summary"]["satisfied_count"])
        self.assertEqual(10, first["summary"]["unsatisfied_count"])

    def test_only_current_contract_and_safety_boundaries_are_satisfied(self) -> None:
        report = MODULE.build_report(plan())
        satisfied = {
            item["requirement_id"]
            for item in report["requirements"]
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

    def test_synthetic_plumbing_cannot_be_promoted_to_scientific_completion(self) -> None:
        report = MODULE.build_report(plan())
        requirements = {
            item["requirement_id"]: item for item in report["requirements"]
        }
        self.assertEqual(
            "synthetic_plumbing_only",
            requirements[
                "deterministic_human_calibrated_full_reference_oracle_passed"
            ]["state"],
        )
        self.assertFalse(
            requirements[
                "deterministic_human_calibrated_full_reference_oracle_passed"
            ]["satisfied"]
        )
        self.assertFalse(report["evidence_checks"]["scientific_gate_evaluated"])

    def test_no_reference_work_remains_ineligible(self) -> None:
        report = MODULE.build_report(plan())
        requirements = {
            item["requirement_id"]: item for item in report["requirements"]
        }
        no_reference = requirements[
            "no_reference_estimator_trained_and_independently_validated"
        ]
        self.assertEqual("not_started_by_design", no_reference["state"])
        self.assertFalse(no_reference["satisfied"])
        self.assertFalse(report["no_reference_training_performed"])

    def test_score_audio_member_and_training_authority_cannot_be_opened(self) -> None:
        value = plan()
        value["authorization"]["new_audio_acquisition_authorized"] = True
        value["authorization"]["listening_score_access_authorized"] = True
        value["authorization"]["perceptual_metric_execution_authorized"] = True
        value["authorization"]["no_reference_training_authorized"] = True
        self.assertIn("authorization boundary differs", MODULE.validate_plan(value))

    def test_final_recommendation_cannot_be_invented_by_audit(self) -> None:
        value = plan()
        value["completion_policy"][
            "current_recommendation"
        ] = "continue_no_reference_research"
        self.assertIn("completion policy differs", MODULE.validate_plan(value))

    def test_green_tests_and_synthetic_replay_cannot_count_as_evidence(self) -> None:
        value = plan()
        value["completion_policy"][
            "preparation_or_synthetic_replay_counts_as_scientific_completion"
        ] = True
        value["completion_policy"]["green_tests_count_as_perceptual_evidence"] = True
        self.assertIn("completion policy differs", MODULE.validate_plan(value))


if __name__ == "__main__":
    unittest.main()
