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
SCRIPT = ROOT / "scripts/perceptual_degradation_objective_completion_audit_v9.py"
SPEC = importlib.util.spec_from_file_location("objective_completion_audit_v9", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObjectiveCompletionAuditV9Test(unittest.TestCase):
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
        self.assertFalse(self.report["summary"]["objective_complete"])
        self.assertEqual(4, self.report["summary"]["satisfied_count"])
        self.assertEqual(10, self.report["summary"]["unsatisfied_count"])

    def test_source_trait_metadata_result_is_reconciled(self) -> None:
        summary = self.report["summary"]
        self.assertTrue(summary["source_trait_exact_member_metadata_audit_complete"])
        self.assertEqual(7, summary["source_trait_required_count"])
        self.assertEqual(6, summary["source_trait_candidate_record_count"])
        self.assertTrue(summary["quiet_metadata_only_route_rejected"])
        self.assertFalse(summary["quiet_exact_candidate_identified"])
        self.assertTrue(
            summary["naturally_clipped_exact_metadata_candidate_identified"]
        )
        self.assertTrue(summary["naturally_clipped_candidate_identified"])
        self.assertFalse(summary["naturally_clipped_trait_truth_established"])
        self.assertFalse(summary["source_trait_audio_accessed_by_metadata_audit"])
        self.assertFalse(summary["source_trait_audio_descriptor_computed"])
        self.assertFalse(summary["source_trait_manifest_frozen"])

    def test_source_manifest_requirement_remains_unsatisfied(self) -> None:
        requirement = next(
            item
            for item in self.report["requirements"]
            if item["requirement_id"]
            == "truth_bearing_source_manifest_feasible_and_frozen"
        )
        self.assertFalse(requirement["satisfied"])
        self.assertIn("Six of seven trait classes", requirement["reason"])
        self.assertIn("SONYC", requirement["reason"])

    def test_difficult_negative_requirement_remains_unsatisfied(self) -> None:
        requirement = next(
            item
            for item in self.report["requirements"]
            if item["requirement_id"]
            == "difficult_natural_and_production_negatives_preserved_in_evaluation"
        )
        self.assertFalse(requirement["satisfied"])
        self.assertIn("no audio descriptor", requirement["reason"])
        self.assertIn("Quiet remains", requirement["reason"])

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

    def test_candidate_cannot_be_promoted_by_plan_mutation(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["completion_policy"][
            "exact_metadata_candidate_counts_as_trait_truth"
        ] = True
        changed["claim_boundary"]["clipped_metadata_candidate_is_trait_truth"] = True
        self.assertIn("completion policy differs", MODULE.validate_plan(changed))
        self.assertIn("claim boundary must remain false", MODULE.validate_plan(changed))


if __name__ == "__main__":
    unittest.main()
