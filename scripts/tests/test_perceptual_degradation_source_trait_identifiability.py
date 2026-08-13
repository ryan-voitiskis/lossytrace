import copy
import importlib.util
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_source_trait_identifiability.py"
SPEC = importlib.util.spec_from_file_location(
    "perceptual_degradation_source_trait_identifiability", SCRIPT
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SourceTraitIdentifiabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.load_json(MODULE.REPORT_PATH)

    def test_frozen_plan_validates(self):
        self.assertEqual(MODULE.validate_plan(self.plan), [])

    def test_binding_mutation_is_rejected(self):
        mutated = copy.deepcopy(self.plan)
        mutated["bindings"]["negative_control_topology_plan"]["sha256"] = "0" * 64
        self.assertIn(
            "binding negative_control_topology_plan sha256 differs",
            MODULE.validate_plan(mutated),
        )

    def test_plan_freezes_all_seven_source_traits_without_assignment(self):
        policy = self.plan["qualification_policy"]
        self.assertEqual(policy["required_trait_ids"], MODULE.EXPECTED_TRAITS)
        self.assertFalse(policy["pcm_descriptor_is_provenance"])
        self.assertFalse(policy["generated_transform_can_substitute_for_natural_trait"])
        self.assertFalse(
            policy["shared_candidate_can_establish_independent_trait_contrasts"]
        )
        self.assertTrue(policy["exact_member_assignment_requires_separate_authorization"])

    def test_every_trait_requires_common_and_trait_specific_evidence(self):
        rows = self.report["proof_obligation_audit"]
        self.assertEqual([row["trait_id"] for row in rows], MODULE.EXPECTED_TRAITS)
        for row in rows:
            self.assertEqual(row["common_proof_obligation_count"], 6)
            self.assertTrue(row["proof_obligations_frozen"])
            self.assertFalse(row["proof_obligations_satisfied_by_current_replay"])
            self.assertTrue(row["provenance_evidence"])

    def test_non_identifiability_witnesses_are_pcm_identical(self):
        rows = self.report["non_identifiability_witnesses"]
        self.assertEqual(
            {row["witness_id"] for row in rows}, MODULE.EXPECTED_WITNESSES
        )
        for row in rows:
            self.assertEqual(row["latent_history_count"], 2)
            self.assertTrue(row["pcm_byte_identical"])
            self.assertEqual(row["first_pcm_sha256"], row["second_pcm_sha256"])
            self.assertFalse(row["source_member_included"])
            self.assertFalse(row["trait_truth_included"])

    def test_witness_fixture_replay_is_deterministic(self):
        for row in self.plan["non_identifiability_witnesses"]:
            first = MODULE.replay_non_identifiability_witness(row)
            second = MODULE.replay_non_identifiability_witness(row)
            self.assertEqual(first, second)
            self.assertTrue(first["pcm_byte_identical"])

    def test_sparse_tonal_overlap_does_not_replace_independent_contrasts(self):
        rows = {
            row["fixture_id"]: row
            for row in self.report["overlap_and_contrast_cases"]
        }
        overlap = rows["sparse-tonal-overlap"]
        sparse = rows["sparse-nontonal-contrast"]
        tonal = rows["tonal-nonsparse-contrast"]
        self.assertEqual(overlap["active_block_count"], 2)
        self.assertGreaterEqual(overlap["tone_projection_share"], 0.99)
        self.assertEqual(sparse["active_block_count"], 2)
        self.assertLessEqual(sparse["tone_projection_share"], 0.05)
        self.assertEqual(tonal["active_block_count"], 10)
        self.assertGreaterEqual(tonal["tone_projection_share"], 0.99)
        for row in rows.values():
            self.assertFalse(row["source_member_included"])
            self.assertFalse(row["trait_truth_included"])

    def test_candidate_audit_preserves_missing_quiet_and_clipped(self):
        rows = {row["trait_id"]: row for row in self.report["candidate_record_audit"]}
        self.assertEqual(rows["quiet"]["candidate_ids"], [])
        self.assertEqual(rows["clipped"]["candidate_ids"], [])
        self.assertEqual(rows["sparse"]["candidate_ids"], ["tinysol_6_0"])
        self.assertEqual(rows["tonal"]["candidate_ids"], ["tinysol_6_0"])
        for row in rows.values():
            self.assertTrue(row["candidate_record_matches_bound_topology"])
            self.assertFalse(row["exact_members_frozen"])
            self.assertFalse(row["trait_assigned"])

    def test_disk_reserve_is_fail_closed(self):
        with mock.patch.object(
            MODULE.shutil,
            "disk_usage",
            return_value=mock.Mock(free=15 * 1024**3 - 1),
        ):
            with self.assertRaisesRegex(ValueError, "below 15 GiB reserve"):
                MODULE.require_disk_reserve(ROOT, 15)

    def test_committed_report_is_hash_bound_and_replayed_twice(self):
        self.assertEqual(self.report["plan_sha256"], MODULE.sha256_file(MODULE.PLAN_PATH))
        self.assertEqual(self.report["implementation_sha256"], MODULE.sha256_file(SCRIPT))
        replay = self.report["replay_observation"]
        self.assertEqual(replay["fresh_temporary_replay_count"], 2)
        self.assertTrue(replay["byte_identical"])
        self.assertEqual(len(set(replay["payload_sha256s"])), 1)
        self.assertFalse(replay["paths_included"])
        self.assertFalse(replay["timing_included"])
        self.assertEqual(MODULE.validate_report(self.report), [])

    def test_report_keeps_access_truth_and_collection_closed(self):
        summary = self.report["summary"]
        self.assertFalse(summary["actual_audio_accessed"])
        self.assertFalse(summary["source_member_selected"])
        self.assertFalse(summary["trait_truth_included"])
        self.assertFalse(summary["perceptual_metric_executed"])
        self.assertFalse(summary["listener_response_collected"])
        decision = self.report["decision"]
        self.assertTrue(decision["source_trait_proof_contract_ready"])
        self.assertTrue(decision["pcm_only_trait_assignment_rejected"])
        self.assertFalse(decision["exact_source_trait_members_frozen"])
        self.assertFalse(decision["source_trait_scientific_coverage_complete"])
        self.assertFalse(decision["human_collection_authorized"])
        self.assertFalse(decision["no_reference_work_eligible"])
        self.assertFalse(decision["public_verdict_enabled"])


if __name__ == "__main__":
    unittest.main()
