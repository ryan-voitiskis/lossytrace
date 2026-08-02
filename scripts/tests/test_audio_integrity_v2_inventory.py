from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate-audio-integrity-v2-inventory.py"
SPEC = importlib.util.spec_from_file_location("v2_inventory", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InventoryValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.inventory = MODULE.load_json(
            ROOT / "benchmarks" / "audio-integrity-v2" / "inventory.json"
        )

    def test_repository_inventory_is_valid(self) -> None:
        self.assertEqual([], MODULE.validate(self.inventory))
        self.assertEqual([], MODULE.validate_toolchain_probe_file(self.inventory, ROOT))
        self.assertEqual(
            [], MODULE.validate_source_identity_evidence_files(self.inventory, ROOT)
        )
        self.assertEqual(
            [],
            MODULE.validate_source_metadata_identity_evidence_files(
                self.inventory, ROOT
            ),
        )

    def test_wrapper_lineage_cannot_cross_transfer_boundary(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        transfer = next(
            row
            for row in inventory["encoder_candidates"]
            if row["encoder_id"] == "mp3_bladeenc_a2d06ec"
        )
        transfer["lineage_id"] = "lame"
        errors = MODULE.validate(inventory)
        self.assertTrue(any("development/transfer lineages overlap" in error for error in errors))

    def test_projected_counts_are_recomputed(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        inventory["projected_partition_summary"]["external_transfer"][
            "conservative_partition_groups"
        ] = 999
        errors = MODULE.validate(inventory)
        self.assertIn("external_transfer projected partition count differs", errors)

    def test_archive_byte_total_is_recomputed(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        inventory["planned_source_archive_bytes"] += 1
        self.assertIn(
            "planned_source_archive_bytes differs from source artifacts",
            MODULE.validate(inventory),
        )

    def test_provider_checksum_is_validated(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        source = next(
            row
            for row in inventory["source_candidates"]
            if row["source_id"] == "speech_commands_v0_02"
        )
        source["artifact"]["provider_checksum"] = "md5:not-a-digest"
        errors = MODULE.validate(inventory)
        self.assertTrue(any("invalid provider checksum" in error for error in errors))

    def test_multi_artifact_filenames_must_be_unique(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        source = next(
            row
            for row in inventory["source_candidates"]
            if row["source_id"] == "ravdess_audio_1_0_0"
        )
        source["artifacts"][1]["filename"] = source["artifacts"][0]["filename"]
        self.assertIn(
            "source ravdess_audio_1_0_0 has duplicate artifact filenames",
            MODULE.validate(inventory),
        )

    def test_acquired_remote_binding_requires_a_strong_etag(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        source = next(
            row
            for row in inventory["source_candidates"]
            if row["source_id"] == "lombard_grid_2018"
        )
        source["artifact"]["provider_identity"]["etag"] = 'W/"weak"'
        errors = MODULE.validate(inventory)
        self.assertTrue(any("valid acquired remote binding" in error for error in errors))

    def test_source_identity_evidence_hash_is_validated(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        source = next(
            row
            for row in inventory["source_candidates"]
            if row["source_id"] == "lombard_grid_2018"
        )
        source["source_identity_evidence"]["aggregate_sha256"] = "0" * 64
        errors = MODULE.validate_source_identity_evidence_files(inventory, ROOT)
        self.assertTrue(any("evidence hash differs" in error for error in errors))

    def test_source_identity_provider_checksum_is_bound(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        source = next(
            row
            for row in inventory["source_candidates"]
            if row["source_id"] == "sonyc_backgrounds_1_0_0"
        )
        source["artifact"]["provider_checksum"] = "md5:" + "0" * 32
        errors = MODULE.validate_source_identity_evidence_files(inventory, ROOT)
        self.assertTrue(any("provider binding differs" in error for error in errors))

    def test_multi_artifact_source_identity_provider_checksum_is_bound(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        source = next(
            row
            for row in inventory["source_candidates"]
            if row["source_id"] == "ravdess_audio_1_0_0"
        )
        self.assertEqual(
            "acquired_and_identity_verified_not_allocated", source["availability"]
        )
        source["artifacts"][0]["provider_checksum"] = "md5:" + "0" * 32
        errors = MODULE.validate_source_identity_evidence_files(inventory, ROOT)
        self.assertTrue(
            any("source identity archive binding differs" in error for error in errors)
        )

    def test_source_metadata_family_rules_hash_is_validated(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        source = next(
            row
            for row in inventory["source_candidates"]
            if row["source_id"] == "rwc_music_v2_2026"
        )
        source["artist_family_rules"]["sha256"] = "0" * 64
        errors = MODULE.validate_source_metadata_identity_evidence_files(
            inventory, ROOT
        )
        self.assertTrue(any("family rules hash differs" in error for error in errors))

    def test_source_group_rules_hash_is_validated(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        source = next(
            row
            for row in inventory["source_candidates"]
            if row["source_id"] == "satp_soundscapes_1_5"
        )
        source["source_group_rules"]["sha256"] = "0" * 64
        errors = MODULE.validate_source_identity_evidence_files(inventory, ROOT)
        self.assertTrue(any("source group rules hash differs" in error for error in errors))

    def test_frozen_state_is_rejected(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        inventory["state"] = "frozen"
        self.assertIn(
            "state must remain inventory_only_not_frozen", MODULE.validate(inventory)
        )


if __name__ == "__main__":
    unittest.main()
