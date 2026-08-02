import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate-audio-integrity-factorial-manifest.py"
CONTRACT_PATH = ROOT / "benchmarks/audio-integrity-v2/factorial-contract.json"
EXAMPLE_PATH = ROOT / "benchmarks/audio-integrity-v2/manifest.example.json"
SPEC = importlib.util.spec_from_file_location("factorial_manifest", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FactorialManifestTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.manifest = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    def validate(self, manifest=None, profile="structural"):
        return MODULE.validate(
            self.contract,
            self.manifest if manifest is None else manifest,
            profile=profile,
            contract_sha256="a" * 64,
            manifest_sha256="b" * 64,
        )

    def test_example_is_structurally_valid_and_report_is_path_free(self):
        errors, report = self.validate()
        self.assertEqual(errors, [])
        self.assertTrue(report["valid"])
        self.assertEqual(report["inventory"]["case_count"], 6)
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn("fixture-development-reference", serialized)
        MODULE.assert_path_free(report)

    def test_reference_must_share_source_and_partition(self):
        manifest = copy.deepcopy(self.manifest)
        case = next(
            value
            for value in manifest["cases"]
            if value["case_id"] == "fixture-development-mp3"
        )
        case["reference_case_id"] = "fixture-transfer-reference"
        errors, _ = self.validate(manifest)
        self.assertTrue(
            any("differs from reference on source_group" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("differs from reference on evidence_partition" in error for error in errors),
            errors,
        )

    def test_transformed_positive_uses_separate_base_and_matched_reference(self):
        manifest = copy.deepcopy(self.manifest)
        base = next(
            value
            for value in manifest["cases"]
            if value["case_id"] == "fixture-development-mp3"
        )
        transformed = copy.deepcopy(base)
        transformed.update(
            {
                "case_id": "fixture-development-mp3-resampled",
                "relative_path": "generated/development-mp3-resampled.flac",
                "audio_sha256": "f" * 64,
                "post_transform_ids": ["resample-32k-44k1"],
                "reference_case_id": "fixture-development-resample",
                "recipe_id": "recipe-development-mp3-resampled",
            }
        )
        manifest["cases"].append(transformed)
        manifest["recipes"].append(
            {
                "recipe_id": "recipe-development-mp3-resampled",
                "output_case_id": transformed["case_id"],
                "source_case_id": "fixture-development-reference",
                "command_sha256": "f" * 64,
                "tool_ids": ["fixture-tool"],
            }
        )
        errors, _ = self.validate(manifest)
        self.assertEqual([], errors)

    def test_encoder_transfer_must_use_unseen_lineage(self):
        manifest = copy.deepcopy(self.manifest)
        encoder = next(
            value
            for value in manifest["encoders"]
            if value["encoder_id"] == "fixture-mp3-transfer"
        )
        encoder["lineage_id"] = "fixture-mp3-lineage-a"
        errors, report = self.validate(manifest)
        self.assertIn(
            "encoder_transfer reuses an encoder lineage from mechanism_development",
            errors,
        )
        self.assertFalse(report["split_checks"]["encoder_transfer_lineage_disjoint"])

    def test_source_lineage_cannot_be_renamed_across_partitions(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["source_collections"][1]["source_lineage_id"] = (
            manifest["source_collections"][0]["source_lineage_id"]
        )
        errors, report = self.validate(manifest)
        self.assertTrue(
            any("source_lineage" in error and "crosses" in error for error in errors),
            errors,
        )
        self.assertFalse(report["split_checks"]["source_lineage_single_partition"])

    def test_eligible_case_must_currently_decode_as_pcm(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["cases"][0]["current_codec"] = "mp3"
        errors, _ = self.validate(manifest)
        self.assertTrue(any("ineligible current codec" in error for error in errors))

    def test_freeze_profile_enforces_sample_and_factor_coverage(self):
        errors, _ = self.validate(profile="mechanism_development_freeze")
        self.assertTrue(
            any("requires 150 source_groups" in error for error in errors), errors
        )
        self.assertTrue(
            any("positive groups for opus" in error for error in errors), errors
        )
        self.assertTrue(
            any("encoder lineages for aac_lc" in error for error in errors), errors
        )

    def test_aggregate_rejects_private_identity_keys(self):
        with self.assertRaisesRegex(ValueError, "forbidden private key"):
            MODULE.assert_path_free({"case_id": "private"})
        with self.assertRaisesRegex(ValueError, "absolute path"):
            MODULE.assert_path_free({"note": "/private/audio.flac"})


if __name__ == "__main__":
    unittest.main()
