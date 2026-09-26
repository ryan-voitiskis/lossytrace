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
SCRIPT = ROOT / "scripts/perceptual_degradation_objective_completion_audit_v11.py"
SPEC = importlib.util.spec_from_file_location("objective_completion_audit_v11", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObjectiveCompletionAuditV11Test(unittest.TestCase):
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

    def test_exact_member_confirmation_is_reconciled_without_trait_truth(self) -> None:
        summary = self.report["summary"]
        self.assertTrue(summary["source_trait_exact_member_confirmation_complete"])
        self.assertEqual(2, summary["source_trait_exact_provider_original_count_acquired"])
        self.assertEqual(2, summary["source_trait_private_replay_count"])
        self.assertTrue(summary["source_trait_private_replays_byte_identical"])
        self.assertTrue(summary["source_trait_audio_accessed_for_confirmation"])
        self.assertTrue(summary["source_trait_descriptor_computed"])
        self.assertTrue(summary["quiet_absolute_pcm_level_measured"])
        self.assertTrue(summary["quiet_nonzero_activity_support_observed"])
        self.assertTrue(
            summary["clipped_plateau_or_saturation_support_event_observed"]
        )
        self.assertFalse(summary["quiet_trait_truth_established"])
        self.assertFalse(summary["naturally_clipped_trait_truth_established"])

    def test_source_and_difficult_negative_requirements_remain_unsatisfied(self) -> None:
        requirements = {
            row["requirement_id"]: row for row in self.report["requirements"]
        }
        source = requirements["truth_bearing_source_manifest_feasible_and_frozen"]
        difficult = requirements[
            "difficult_natural_and_production_negatives_preserved_in_evaluation"
        ]
        self.assertFalse(source["satisfied"])
        self.assertIn("No quiet classification threshold", source["reason"])
        self.assertIn("sparse and tonal remain non-independent", source["reason"])
        self.assertFalse(difficult["satisfied"])
        self.assertIn("neither was assigned as trait truth", difficult["reason"])
        self.assertIn("no natural or production negative", difficult["reason"])

    def test_retained_drift_result_is_unchanged(self) -> None:
        predecessor = MODULE.load_json(
            MODULE._bound(self.plan, "predecessor_audit_report")
        )
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

    def test_policy_mutation_cannot_promote_descriptor_to_truth(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["completion_policy"]["descriptor_observation_counts_as_trait_truth"] = True
        changed["claim_boundary"]["descriptor_observation_is_perceptual_truth"] = True
        errors = MODULE.validate_plan(changed)
        self.assertIn("completion policy differs", errors)
        self.assertIn("claim boundary must remain false", errors)


if __name__ == "__main__":
    unittest.main()
