from __future__ import annotations

import importlib
import json
import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE = importlib.import_module("perceptual_degradation_alignment_v2")
SCHEMA = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "alignment-result-v2.schema.json"
)


def fixture(sample_rate: int = 2000, seconds: int = 6, phase: float = 0.0) -> list[float]:
    return [
        (0.2 + 0.8 * ((index // 137) % 7) / 6)
        * (
            0.55 * math.sin(2 * math.pi * 113 * index / sample_rate + phase)
            + 0.31 * math.sin(2 * math.pi * 271 * index / sample_rate + 0.2)
            + 0.14
            * math.sin(
                2 * math.pi * 419 * index / sample_rate + index * index * 1e-7
            )
        )
        for index in range(sample_rate * seconds)
    ]


class PerceptualDegradationAlignmentV2Test(unittest.TestCase):
    def test_schema_remains_score_and_verdict_free(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertFalse(schema["properties"]["public_verdict_enabled"]["const"])
        encoded = json.dumps(schema).lower()
        self.assertNotIn("mos_lqo", encoded)
        self.assertNotIn("materially_degraded", encoded)

    def test_stereo_identity_and_per_channel_gain_polarity_are_supported(self) -> None:
        left = fixture()
        right = fixture(phase=0.37)
        test_left = [0.5 * value for value in left]
        test_right = [-0.3 * value for value in right]
        first = MODULE.align_channels(
            reference_channels=[left, right],
            test_channels=[test_left, test_right],
            reference_channel_map=["L", "R"],
            test_channel_map=["L", "R"],
            sample_rate_hz=2000,
            recipe_identity="stereo-gain-polarity",
        )
        second = MODULE.align_channels(
            reference_channels=[left, right],
            test_channels=[test_left, test_right],
            reference_channel_map=["L", "R"],
            test_channel_map=["L", "R"],
            sample_rate_hz=2000,
            recipe_identity="stereo-gain-polarity",
        )
        self.assertEqual(first, second)
        self.assertEqual("supported", first["status"])
        channels = first["alignment"]["channels"]
        self.assertEqual(["preserved", "inverted"], [item["polarity"] for item in channels])
        self.assertAlmostEqual(-6.020599913, channels[0]["observed_gain_db"], places=6)
        self.assertAlmostEqual(-10.457574906, channels[1]["observed_gain_db"], places=6)

    def test_channel_count_map_and_swap_are_unsupported(self) -> None:
        left = fixture()
        right = fixture(phase=0.37)
        count = MODULE.align_channels(
            reference_channels=[left, right],
            test_channels=[left],
            reference_channel_map=["L", "R"],
            test_channel_map=["M"],
            sample_rate_hz=2000,
            recipe_identity="topology-mismatch",
        )
        self.assertIn("channel_topology_mismatch", count["support"]["reasons"])
        mapped = MODULE.align_channels(
            reference_channels=[left, right],
            test_channels=[right, left],
            reference_channel_map=["L", "R"],
            test_channel_map=["R", "L"],
            sample_rate_hz=2000,
            recipe_identity="map-swap",
        )
        self.assertIn("channel_map_mismatch", mapped["support"]["reasons"])

    def test_channel_delay_disagreement_is_unsupported(self) -> None:
        left = fixture()
        right = fixture(phase=0.37)
        result = MODULE.align_channels(
            reference_channels=[left, right],
            test_channels=[
                [0.0] * 20 + left[:-20],
                [0.0] * 27 + right[:-27],
            ],
            reference_channel_map=["L", "R"],
            test_channel_map=["L", "R"],
            sample_rate_hz=2000,
            recipe_identity="channel-delay-disagreement",
        )
        self.assertEqual("unsupported", result["status"])
        self.assertIn(
            "channel_alignment_disagreement", result["support"]["reasons"]
        )

    def test_midstream_splice_is_structurally_unsupported(self) -> None:
        reference = fixture()
        test = reference[:5000] + reference[5100:]
        result = MODULE.align_channels(
            reference_channels=[reference],
            test_channels=[test],
            reference_channel_map=["M"],
            test_channel_map=["M"],
            sample_rate_hz=2000,
            recipe_identity="midstream-splice",
        )
        self.assertEqual("unsupported", result["status"])
        self.assertIn("structural_edit_suspected", result["support"]["reasons"])


if __name__ == "__main__":
    unittest.main()
