from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "construct-audio-integrity-v2-benchmark.py"
PLAN_PATH = ROOT / "benchmarks" / "audio-integrity-v2" / "construction-plan.json"
TOOLCHAIN_PATH = (
    ROOT / "benchmarks" / "audio-integrity-v2" / "toolchain-bindings.json"
)
SPEC = importlib.util.spec_from_file_location("v2_constructor", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PLAN = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
TOOLCHAIN = json.loads(TOOLCHAIN_PATH.read_text(encoding="utf-8"))


class AudioIntegrityV2ConstructorTest(unittest.TestCase):
    def test_plan_authorizes_frozen_full_build_and_binds_evidence(self) -> None:
        self.assertEqual("full", PLAN["authorized_scope"])
        self.assertTrue(PLAN["benchmark_source_audio_read"])
        self.assertTrue(PLAN["benchmark_audio_generated"])
        self.assertTrue(PLAN["smoke_selection"]["authorized"])
        self.assertEqual(202, PLAN["smoke_selection"]["expected_cell_count"])
        self.assertFalse(PLAN["features_computed"])
        self.assertFalse(PLAN["scores_opened"])
        self.assertFalse(PLAN["public_verdict_enabled"])
        self.assertEqual(
            MODULE.sha256_file(SCRIPT), PLAN["bindings"]["generator_sha256"]
        )
        self.assertEqual(
            "5f8e48fa58366c5259eb4e854a869cf145841f20ff7238427bd9038d91ae5615",
            PLAN["bindings"]["smoke_result_sha256"],
        )
        self.assertEqual(
            "5a53608613789e7411e54e877acdbf33a2fb434645255c5fb3114163764e2bad",
            PLAN["bindings"]["private_smoke_manifest_sha256"],
        )

    def test_synthetic_cases_cover_every_encoder_transform_wrapper_and_decoder(self) -> None:
        settings = {
            row["expanded_setting_id"]: row
            for row in TOOLCHAIN["expanded_encoder_settings"]
        }
        decoders = {
            row["history_decoder_id"]: row
            for row in TOOLCHAIN["history_decoder_bindings"]
        }
        cases = PLAN["synthetic_cases"]
        observed_encoders = set()
        observed_decoders = set()
        for case in cases:
            setting_id = case["expanded_setting_id"]
            if setting_id is None:
                continue
            setting = settings[setting_id]
            decoder = decoders[case["history_decoder_id"]]
            observed_encoders.add(setting["encoder_id"])
            observed_decoders.add(case["history_decoder_id"])
            self.assertEqual(case["sample_rate_hz"], setting["expected_sample_rate_hz"])
            self.assertEqual(case["channel_count"], setting["expected_channel_count"])
            self.assertIn(setting["codec_family"], decoder["codec_families"])
        self.assertEqual(
            set(PLAN["synthetic_coverage"]["all_encoder_implementations"]),
            observed_encoders,
        )
        self.assertEqual(
            set(PLAN["synthetic_coverage"]["all_history_decoders"]),
            observed_decoders,
        )
        self.assertEqual(
            {row["transform_id"] for row in TOOLCHAIN["pcm_transform_bindings"]},
            {row["transform_id"] for row in cases},
        )
        self.assertEqual(
            {row["wrapper_id"] for row in TOOLCHAIN["wrapper_bindings"]},
            {row["wrapper_id"] for row in cases},
        )

    def test_recipe_address_is_deterministic_and_wrapper_specific(self) -> None:
        cell = {"assignment_id": "ab" + "1" * 62, "wrapper_id": "aiff16"}
        self.assertEqual(
            "cases/ab/ab" + "1" * 62 + ".aiff",
            MODULE.artifact_relative_path(cell),
        )
        self.assertEqual(
            "checkpoints/ab/ab" + "1" * 62 + ".json",
            MODULE.checkpoint_relative_path(cell),
        )

    def test_smoke_selection_is_deterministic_and_deduplicated(self) -> None:
        cells = [
            {
                "assignment_id": identity,
                "group_id": identity,
                "expectation": "negative",
                "evidence_partition": "external_transfer",
                "transform_id": "identity",
                "wrapper_id": "flac16",
                "channel_treatment_id": "mono",
                "target_sample_rate_hz": 44100,
            }
            for identity in ("b", "a")
        ]
        feasibility = {
            identity: {"codec_name": "pcm_s16le"} for identity in ("a", "b")
        }
        selected = MODULE.smoke_cells(cells, feasibility)
        self.assertEqual(["a"], [row["assignment_id"] for row in selected])

    def test_public_constructor_evidence_rejects_private_identity_and_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "private key"):
            MODULE.assert_public_path_free({"cell": {}})
        with self.assertRaisesRegex(ValueError, "private path"):
            MODULE.assert_public_path_free({"note": "/private/output"})


if __name__ == "__main__":
    unittest.main()
