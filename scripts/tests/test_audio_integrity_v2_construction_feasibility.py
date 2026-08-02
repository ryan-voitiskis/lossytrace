from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "scripts" / "audit-audio-integrity-v2-construction-feasibility.py"
)
SPEC = importlib.util.spec_from_file_location("v2_construction_feasibility", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PLAN = json.loads(
    (
        ROOT
        / "benchmarks"
        / "audio-integrity-v2"
        / "construction-feasibility-plan.json"
    ).read_text(encoding="utf-8")
)


class ConstructionFeasibilityTest(unittest.TestCase):
    def test_plan_is_pre_audit_and_binds_generator(self) -> None:
        self.assertEqual(
            "construction_feasibility_frozen_before_header_audit", PLAN["state"]
        )
        self.assertFalse(PLAN["audio_generated"])
        self.assertFalse(PLAN["headers_inspected"])
        self.assertFalse(PLAN["scores_opened"])
        self.assertEqual(
            MODULE.sha256_file(SCRIPT),
            PLAN["bindings"]["audit_generator_sha256"],
        )

    def test_provider_decimal_window_stays_inside_declared_bounds(self) -> None:
        header = {
            "native_sample_rate_hz": 44100,
            "native_frame_count": 44100 * 10,
        }
        row = {
            "factors": {
                "audio_start_seconds": "0.00001",
                "audio_end_seconds": "9.99999",
            }
        }
        start, end = MODULE.provider_window(row, header)
        self.assertEqual(1, start)
        self.assertEqual(440999, end)

    def test_excerpt_is_capped_at_exactly_twelve_native_seconds(self) -> None:
        header = {
            "native_sample_rate_hz": 48000,
            "native_frame_count": 48000 * 30,
        }
        self.assertEqual(48000 * 12, MODULE.excerpt_frame_count({}, header))

    def test_duration_support_boundaries_are_exact(self) -> None:
        rate = 8000
        self.assertEqual("lt1", MODULE.duration_stratum(rate - 1, rate))
        self.assertEqual("ge1_lt3", MODULE.duration_stratum(rate, rate))
        self.assertEqual("ge3_lt6", MODULE.duration_stratum(rate * 3, rate))
        self.assertEqual("ge6_le12", MODULE.duration_stratum(rate * 6, rate))

    def test_transform_minima_do_not_round_duration(self) -> None:
        rate = 44100
        self.assertFalse(
            MODULE.transform_supported("trim-head-250ms", rate // 2 - 1, rate)
        )
        self.assertTrue(
            MODULE.transform_supported("trim-head-250ms", rate // 2, rate)
        )
        self.assertFalse(
            MODULE.transform_supported("duration-prefix-3s", rate * 3 - 1, rate)
        )
        self.assertTrue(
            MODULE.transform_supported("duration-prefix-3s", rate * 3, rate)
        )

    def test_public_aggregate_rejects_private_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "private key"):
            MODULE.assert_public_path_free({"group_id": "private"})
        with self.assertRaisesRegex(ValueError, "private path"):
            MODULE.assert_public_path_free({"note": "/private/source.wav"})


if __name__ == "__main__":
    unittest.main()
