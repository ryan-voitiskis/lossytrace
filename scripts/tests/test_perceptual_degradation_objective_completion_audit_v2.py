from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_objective_completion_audit_v2.py"
PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "objective-completion-audit-plan-20260814-002.json"
)
SPEC = importlib.util.spec_from_file_location("objective_completion_audit_v2", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class ObjectiveCompletionAuditV2Test(unittest.TestCase):
    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate_plan(plan()))

    def test_report_is_deterministic_and_still_incomplete(self) -> None:
        first = MODULE.build_report(plan())
        second = MODULE.build_report(plan())
        self.assertEqual(first, second)
        self.assertFalse(first["summary"]["objective_complete"])
        self.assertEqual(14, first["summary"]["requirement_count"])
        self.assertEqual(4, first["summary"]["satisfied_count"])
        self.assertEqual(10, first["summary"]["unsatisfied_count"])

    def test_source_arithmetic_is_not_promoted_to_manifest_completion(self) -> None:
        report = MODULE.build_report(plan())
        source = next(
            item
            for item in report["requirements"]
            if item["requirement_id"]
            == "truth_bearing_source_manifest_feasible_and_frozen"
        )
        self.assertTrue(report["summary"]["source_arithmetic_feasible"])
        self.assertEqual("arithmetic_feasible_exact_manifest_unfrozen", source["state"])
        self.assertFalse(source["satisfied"])
        self.assertEqual(0, report["evidence_checks"]["qualified_reference_group_count"])
        self.assertEqual(0, report["evidence_checks"]["allocated_group_count"])

    def test_preregisterable_metric_is_not_promoted_to_selected_or_executed(self) -> None:
        report = MODULE.build_report(plan())
        metric = next(
            item
            for item in report["requirements"]
            if item["requirement_id"]
            == "perceptual_metric_execution_and_legal_gate_passed"
        )
        self.assertTrue(report["summary"]["metric_successor_preregisterable"])
        self.assertFalse(report["summary"]["metric_successor_selected"])
        self.assertFalse(report["evidence_checks"]["new_successor_metric_gate_exists"])
        self.assertEqual(
            "successor_preregisterable_unselected_execution_closed",
            metric["state"],
        )
        self.assertFalse(metric["satisfied"])
        self.assertFalse(report["metrics_executed"])

    def test_only_contract_and_safety_boundaries_are_satisfied(self) -> None:
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

    def test_authority_and_promotion_policies_fail_closed(self) -> None:
        value = plan()
        value["authorization"]["exact_member_metadata_audit_authorized"] = True
        value["authorization"]["perceptual_metric_execution_authorized"] = True
        value["authorization"]["no_reference_training_authorized"] = True
        self.assertIn("authorization boundary differs", MODULE.validate_plan(value))

        value = plan()
        value["completion_policy"][
            "arithmetic_feasibility_counts_as_manifest_qualification"
        ] = True
        value["completion_policy"][
            "preregisterable_metric_successor_counts_as_selection"
        ] = True
        self.assertIn("completion policy differs", MODULE.validate_plan(value))

    def test_no_reference_work_and_public_verdict_remain_closed(self) -> None:
        report = MODULE.build_report(plan())
        self.assertFalse(report["no_reference_training_performed"])
        self.assertFalse(report["public_verdict_enabled"])
        self.assertFalse(report["evidence_checks"]["scientific_gate_evaluated"])


if __name__ == "__main__":
    unittest.main()
