from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts"
    / "perceptual_degradation_source_trait_adjudication_relationship.py"
)
SPEC = importlib.util.spec_from_file_location(
    "source_trait_adjudication_relationship", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceTraitAdjudicationRelationshipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.build_report(cls.plan)

    def test_plan_and_committed_report_replay_exactly(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))
        self.assertEqual(
            MODULE.canonical_json_bytes(self.report), MODULE.REPORT_PATH.read_bytes()
        )
        self.assertEqual([], MODULE.validate_report(self.report, self.plan))

    def test_quiet_post_hoc_threshold_is_rejected(self) -> None:
        changed = copy.deepcopy(self.plan)
        changed["policy"][
            "current_quiet_observation_may_be_relabelled_by_new_numeric_cutoff"
        ] = True
        changed["policy"]["later_threshold_may_be_retrofit_to_observed_descriptor"] = True
        errors = MODULE.validate_plan(changed)
        self.assertIn(
            "current quiet observation must not be relabelled post hoc", errors
        )
        self.assertIn(
            "policy differs: later_threshold_may_be_retrofit_to_observed_descriptor",
            errors,
        )

    def test_clipped_readiness_does_not_assign_trait(self) -> None:
        clipped = self.report["adjudication"]["clipped"]
        self.assertTrue(clipped["technical_support_predicate_frozen_before_observation"])
        self.assertTrue(clipped["technical_support_event_observed"])
        self.assertFalse(clipped["partition_support_frozen"])
        self.assertFalse(clipped["trait_assigned"])
        self.assertTrue(
            self.report["decision"][
                "clipped_evidence_ready_for_separately_authorized_assignment_gate"
            ]
        )

    def test_tinysol_capacity_does_not_establish_independent_contrasts(self) -> None:
        relationships = self.report["relationship_audit"]
        self.assertEqual(2273, relationships["tinysol_eligible_exact_member_candidate_count"])
        self.assertEqual(1, relationships["tinysol_conservative_partition_group_count"])
        self.assertFalse(
            relationships["tinysol_provider_or_partition_independence_established"]
        )
        self.assertFalse(
            relationships["independent_sparse_and_tonal_contrasts_established"]
        )

    def test_no_new_access_assignment_allocation_or_verdict(self) -> None:
        access = self.report["access_boundary"]
        self.assertTrue(access["bound_committed_metadata_read"])
        self.assertTrue(
            all(
                value is False
                for key, value in access.items()
                if key != "bound_committed_metadata_read"
            )
        )
        self.assertFalse(self.report["summary"]["source_trait_manifest_frozen"])
        self.assertFalse(self.report["summary"]["objective_completion_count_changed"])

    def test_claim_promotion_and_private_material_are_rejected(self) -> None:
        changed = copy.deepcopy(self.report)
        changed["claim_boundary"]["clipped_readiness_is_trait_assignment"] = True
        changed["private_path"] = "/Users/example/provider-originals/source.wav"
        errors = MODULE.validate_report(changed, self.plan)
        self.assertIn("report differs from deterministic replay", errors)
        self.assertTrue(
            any(error.startswith("public report exposes forbidden material") for error in errors)
        )


if __name__ == "__main__":
    unittest.main()
