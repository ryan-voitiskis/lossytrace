from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "preflight-audio-integrity-v2-construction.py"
PLAN_PATH = (
    ROOT / "benchmarks" / "audio-integrity-v2" / "construction-preflight-plan.json"
)
SPEC = importlib.util.spec_from_file_location("v2_construction_preflight", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PLAN = json.loads(PLAN_PATH.read_text(encoding="utf-8"))


class AudioIntegrityV2ConstructionPreflightTest(unittest.TestCase):
    def test_plan_is_preconstruction_and_binds_exact_generator(self) -> None:
        self.assertEqual(
            "construction_preflight_frozen_before_private_replay", PLAN["state"]
        )
        self.assertFalse(PLAN["benchmark_source_audio_read"])
        self.assertFalse(PLAN["benchmark_audio_generated"])
        self.assertFalse(PLAN["construction_authorized"])
        self.assertEqual(
            MODULE.sha256_file(SCRIPT), PLAN["bindings"]["generator_sha256"]
        )

    def test_resample_bound_rounds_up_and_adds_tail(self) -> None:
        self.assertEqual(
            44229,
            MODULE.preconditioned_frame_upper(48001, 48000, 44100),
        )
        self.assertEqual(
            48001,
            MODULE.preconditioned_frame_upper(48001, 48000, 48000),
        )

    def test_transform_shape_bounds_cover_duration_and_channel_changes(self) -> None:
        self.assertEqual(
            (3 * 48000, 2),
            MODULE.transformed_shape_upper(
                frame_count=12 * 48000,
                channel_count=2,
                sample_rate_hz=48000,
                transform_id="duration-prefix-3s",
            ),
        )
        self.assertEqual(
            (12 * 48000, 1),
            MODULE.transformed_shape_upper(
                frame_count=12 * 48000,
                channel_count=2,
                sample_rate_hz=48000,
                transform_id="alternate-channel-topology",
            ),
        )

    def test_flac_bound_exceeds_raw_pcm_and_container_allowance(self) -> None:
        raw_bytes = 48000 * 2 * 2
        observed = MODULE.artifact_byte_upper(
            frame_count=48000, channel_count=2, wrapper_id="flac16"
        )
        self.assertGreaterEqual(
            observed,
            raw_bytes + MODULE.PER_ARTIFACT_CONTAINER_ALLOWANCE_BYTES,
        )

    def test_public_preflight_rejects_private_identity_and_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "private key"):
            MODULE.assert_public_path_free({"assignment_id": "private"})
        with self.assertRaisesRegex(ValueError, "private path"):
            MODULE.assert_public_path_free({"note": "/private/output"})


if __name__ == "__main__":
    unittest.main()
