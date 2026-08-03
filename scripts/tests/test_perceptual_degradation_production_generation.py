from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_production_generation.py"
SPEC = importlib.util.spec_from_file_location("production_generation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProductionGenerationTest(unittest.TestCase):
    def test_round_ratio_uses_ties_to_even(self) -> None:
        self.assertEqual(2, MODULE.round_ratio_ties_even(5, 2))
        self.assertEqual(4, MODULE.round_ratio_ties_even(7, 2))
        self.assertEqual(-2, MODULE.round_ratio_ties_even(-5, 2))
        self.assertEqual(-4, MODULE.round_ratio_ties_even(-7, 2))

    def test_hard_clip_is_exact_and_shape_preserving(self) -> None:
        samples = [-32768, -16384, -3, 3, 16384, 32767]
        output = MODULE.apply_production_control(
            "production-hard-clip-minus6dbfs-v1", 48000, 2, samples
        )
        self.assertEqual([-16384, -16384, -3, 3, 16384, 16384], output)

    def test_high_shelf_has_unity_dc_and_half_nyquist_gain(self) -> None:
        dc = [12000] * 8
        self.assertEqual(
            dc,
            MODULE.apply_production_control(
                "production-high-shelf-minus6db-nyquist-fir3-v1", 48000, 1, dc
            ),
        )
        alternating = [12000, -12000] * 4
        output = MODULE.apply_production_control(
            "production-high-shelf-minus6db-nyquist-fir3-v1",
            48000,
            1,
            alternating,
        )
        self.assertEqual([9000, -6000, 6000, -6000, 6000, -6000, 6000, -9000], output)

    def test_limiter_is_linked_and_bounded(self) -> None:
        samples = [30000, 15000, -30000, -15000]
        output = MODULE.apply_production_control(
            "production-block-limiter-minus6dbfs-5ms-v1", 48000, 2, samples
        )
        self.assertEqual([16384, 8192, -16384, -8192], output)
        self.assertLessEqual(max(abs(value) for value in output), 16384)

    def test_stereo_width_preserves_mid_and_halves_side(self) -> None:
        output = MODULE.apply_production_control(
            "production-stereo-width-half-mid-side-v1",
            44100,
            2,
            [12000, 4000, -8000, 8000],
        )
        self.assertEqual([10000, 6000, -4000, 4000], output)

    def test_stereo_width_rejects_mono(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires stereo"):
            MODULE.apply_production_control(
                "production-stereo-width-half-mid-side-v1", 48000, 1, [1, 2]
            )

    def test_synthetic_fixture_is_deterministic_and_supported(self) -> None:
        for recipe_id in sorted(MODULE.PRODUCTION_RECIPE_IDS):
            first = MODULE.synthetic_samples(recipe_id, 48000, seconds=1)
            second = MODULE.synthetic_samples(recipe_id, 48000, seconds=1)
            self.assertEqual(first, second)
            output = MODULE.apply_production_control(recipe_id, 48000, 2, first)
            changed = MODULE.changed_frame_count(first, output, 2)
            self.assertGreaterEqual(changed / 48000, 0.001)

    def test_command_expansion_rejects_unbound_tool(self) -> None:
        with self.assertRaisesRegex(ValueError, "unbound tool token"):
            MODULE.expanded_command(
                ["<TOOL:missing>", "<INPUT>", "<OUTPUT>"],
                {},
                Path("input"),
                Path("output"),
            )

    def test_resampler_filter_matches_frozen_plan(self) -> None:
        plan = json.loads(MODULE.DEFAULT_PLAN.read_text(encoding="utf-8"))
        self.assertEqual(
            MODULE.RESAMPLE_FILTER_TEMPLATE,
            plan["codec_generation_execution"]["intermediate_resampler"][
                "filter_template"
            ],
        )

    def test_command_expansion_rejects_unknown_placeholder(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown command token"):
            MODULE.expanded_command(
                ["<INPUT>", "<UNKNOWN>", "<OUTPUT>"],
                {},
                Path("input"),
                Path("output"),
            )

    def test_disk_reserve_is_enforced(self) -> None:
        with mock.patch.object(
            MODULE.shutil,
            "disk_usage",
            return_value=mock.Mock(free=15 * 1024**3 - 1),
        ):
            with self.assertRaisesRegex(ValueError, "below 15 GiB reserve"):
                MODULE.require_disk_reserve(ROOT, 15)


if __name__ == "__main__":
    unittest.main()
