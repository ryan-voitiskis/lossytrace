from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate-perceptual-degradation-permissive-multiprovider-source-plan.py"
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/permissive-multiprovider-source-candidate-plan.json"
SPEC = importlib.util.spec_from_file_location("multiprovider_source_plan", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class PermissiveMultiproviderSourcePlanTest(unittest.TestCase):
    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate(plan()))

    def test_audio_scores_and_collection_cannot_be_authorized(self) -> None:
        value = plan()
        value["authorization"]["new_audio_acquisition_authorized"] = True
        value["authorization"]["listening_score_access_authorized"] = True
        value["authorization"]["human_collection_authorized"] = True
        errors = MODULE.validate(value)
        self.assertIn("authorization boundary differs", errors)

    def test_available_groups_cannot_be_promoted_to_qualified_or_allocated(self) -> None:
        value = plan()
        value["candidate_tiers"][0]["qualified_reference_group_count"] = 156
        value["candidate_tiers"][0]["allocated_group_count"] = 156
        errors = MODULE.validate(value)
        self.assertIn(
            "candidate tier prematurely qualifies references: exact_member_audit_candidates",
            errors,
        )
        self.assertIn(
            "candidate tier prematurely allocates groups: exact_member_audit_candidates",
            errors,
        )

    def test_source_and_provider_leakage_cannot_be_enabled(self) -> None:
        value = plan()
        value["partition_requirements"]["source_group_may_cross_partitions"] = True
        value["partition_requirements"][
            "provider_spanning_partitions_counts_as_provider_held_out_evidence"
        ] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "partition boundary must remain false: source_group_may_cross_partitions",
            errors,
        )
        self.assertIn(
            "partition boundary must remain false: provider_spanning_partitions_counts_as_provider_held_out_evidence",
            errors,
        )

    def test_pending_and_development_only_roles_cannot_be_promoted(self) -> None:
        value = plan()
        observation_path = ROOT / value["bindings"]["public_metadata_observation"]["path"]
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
        for item in observation["observations"]:
            if item["source_id"] == "musicnet_5120004":
                item["role_status"] = "qualified_reference"
        temporary = self.create_temp_observation(observation)
        try:
            value["bindings"]["public_metadata_observation"]["path"] = str(
                temporary.relative_to(ROOT)
            )
            value["bindings"]["public_metadata_observation"]["sha256"] = MODULE.sha256_file(
                temporary
            )
            errors = MODULE.validate(value)
            self.assertIn("candidate role differs: musicnet_5120004", errors)
        finally:
            temporary.unlink()

    def test_raw_capacity_cannot_be_claimed_as_partition_feasibility(self) -> None:
        value = plan()
        value["decision"]["raw_capacity_proves_four_partition_feasibility"] = True
        value["decision"]["source_manifest_frozen"] = True
        value["claim_boundary"]["one_large_provider_proves_provider_transfer"] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "decision was prematurely closed: raw_capacity_proves_four_partition_feasibility",
            errors,
        )
        self.assertIn("decision was prematurely closed: source_manifest_frozen", errors)
        self.assertIn(
            "claim boundary must remain false: one_large_provider_proves_provider_transfer",
            errors,
        )

    def create_temp_observation(self, value: dict) -> Path:
        handle, raw_path = tempfile.mkstemp(
            prefix=".tmp-multiprovider-source-observation-test-",
            suffix=".json",
            dir=ROOT / "research/toolchains/evidence",
        )
        os.close(handle)
        path = Path(raw_path)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
