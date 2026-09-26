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
SCRIPT = ROOT / "scripts/perceptual_degradation_objective_completion_audit_v12.py"
SPEC = importlib.util.spec_from_file_location("objective_completion_audit_v12", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObjectiveCompletionAuditV12Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_plan_and_committed_report_replay_exactly(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))
        self.assertEqual(self.report, MODULE.build_report(self.plan))
        self.assertEqual(
            MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes()
        )

    def test_objective_remains_four_of_fourteen(self) -> None:
        summary = self.report["summary"]
        self.assertFalse(summary["objective_complete"])
        self.assertEqual(4, summary["satisfied_count"])
        self.assertEqual(10, summary["unsatisfied_count"])
        self.assertFalse(summary["source_trait_manifest_frozen"])

    def test_readiness_is_reconciled_without_trait_promotion(self) -> None:
        summary = self.report["summary"]
        self.assertTrue(summary["source_trait_adjudication_relationship_audit_complete"])
        self.assertTrue(summary["quiet_post_hoc_threshold_route_rejected"])
        self.assertFalse(summary["quiet_trait_truth_established"])
        self.assertTrue(summary["clipped_descriptor_and_provenance_assignment_ready"])
        self.assertFalse(summary["naturally_clipped_trait_truth_established"])
        self.assertFalse(summary["independent_sparse_and_tonal_contrasts_established"])

    def test_source_requirement_records_exact_remaining_boundary(self) -> None:
        requirements = {
            row["requirement_id"]: row for row in self.report["requirements"]
        }
        source = requirements["truth_bearing_source_manifest_feasible_and_frozen"]
        self.assertFalse(source["satisfied"])
        self.assertIn("prevents a post-hoc quiet cutoff", source["reason"])
        self.assertIn("only one conservative partition group", source["reason"])
        self.assertIn("No source trait was assigned", source["reason"])

    def test_retained_drift_result_is_unchanged(self) -> None:
        predecessor = MODULE.load_json(MODULE._bound(self.plan, "predecessor_audit_report"))
        for section in ("summary", "evidence_checks"):
            keys = {
                key
                for key in predecessor[section]
                if key.startswith("retained_drift") or key.startswith("oracle_drift")
            }
            self.assertTrue(keys)
            self.assertEqual(
                {key: predecessor[section][key] for key in keys},
                {key: self.report[section][key] for key in keys},
            )

    def test_policy_mutation_cannot_promote_readiness(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["completion_policy"][
            "clipped_descriptor_and_provenance_readiness_counts_as_trait_assignment"
        ] = True
        changed["claim_boundary"]["clipped_readiness_is_trait_assignment"] = True
        errors = MODULE.validate_plan(changed)
        self.assertIn(
            "completion policy differs: clipped_descriptor_and_provenance_readiness_counts_as_trait_assignment",
            errors,
        )
        self.assertIn("claim boundary must remain false", errors)


if __name__ == "__main__":
    unittest.main()
