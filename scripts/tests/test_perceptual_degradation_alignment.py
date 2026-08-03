from __future__ import annotations

import importlib.util
import json
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "perceptual_degradation_alignment.py"
SCHEMA = ROOT / "benchmarks" / "perceptual-degradation-v1" / "alignment-result.schema.json"
SPEC = importlib.util.spec_from_file_location("perceptual_degradation_alignment", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture(sample_rate: int = 2000, seconds: int = 6) -> list[float]:
    values = []
    for index in range(sample_rate * seconds):
        time = index / sample_rate
        envelope = 0.2 + 0.8 * ((index // 137) % 7) / 6
        values.append(
            envelope
            * (
                0.55 * math.sin(2 * math.pi * 113 * time)
                + 0.31 * math.sin(2 * math.pi * 271 * time + 0.2)
                + 0.14 * math.sin(2 * math.pi * 419 * time + index * index * 1e-7)
            )
        )
    return values


class PerceptualDegradationAlignmentTest(unittest.TestCase):
    def test_schema_is_score_free_and_verdict_free(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(1, schema["properties"]["schema_version"]["const"])
        self.assertFalse(schema["properties"]["public_verdict_enabled"]["const"])
        encoded = json.dumps(schema).lower()
        self.assertNotIn("mos_lqo", encoded)
        self.assertNotIn("materially_degraded", encoded)

    def test_identity_alignment_is_supported_and_deterministic(self) -> None:
        reference = fixture()
        first = MODULE.align_mono(
            reference=reference,
            test=reference,
            sample_rate_hz=2000,
            recipe_identity="identity",
        )
        second = MODULE.align_mono(
            reference=reference,
            test=reference,
            sample_rate_hz=2000,
            recipe_identity="identity",
        )
        self.assertEqual(first, second)
        self.assertEqual("supported", first["status"])
        self.assertEqual(0, first["alignment"]["integer_delay_samples"])
        self.assertAlmostEqual(1.0, first["alignment"]["correlation"], places=12)

    def test_delay_gain_and_polarity_are_reported(self) -> None:
        reference = fixture()
        delay = 73
        test = [0.0] * delay + [-0.5 * value for value in reference]
        result = MODULE.align_mono(
            reference=reference,
            test=test,
            sample_rate_hz=2000,
            recipe_identity="delay-gain-polarity",
        )
        self.assertEqual("supported", result["status"])
        self.assertEqual(delay, result["alignment"]["integer_delay_samples"])
        self.assertEqual("inverted", result["alignment"]["polarity"])
        self.assertAlmostEqual(-6.020599913, result["alignment"]["observed_gain_db"], places=6)

    def test_excessive_delay_abstains_instead_of_fabricating_support(self) -> None:
        reference = fixture()
        test = [0.0] * 2100 + reference
        result = MODULE.align_mono(
            reference=reference,
            test=test,
            sample_rate_hz=2000,
            recipe_identity="excessive-trim",
            maximum_delay_seconds=1.5,
        )
        self.assertEqual("unsupported", result["status"])
        self.assertIn("excessive_trim", result["support"]["reasons"])

    def test_fractional_delay_is_bounded_and_repeatable(self) -> None:
        reference = fixture()
        expected = 0.25
        test = []
        for index in range(len(reference) + 1):
            position = index - expected
            if position < 0 or position >= len(reference) - 1:
                test.append(0.0)
                continue
            lower = int(position)
            fraction = position - lower
            test.append(
                reference[lower] * (1.0 - fraction)
                + reference[lower + 1] * fraction
            )
        result = MODULE.align_mono(
            reference=reference,
            test=test,
            sample_rate_hz=2000,
            recipe_identity="fractional-delay",
        )
        self.assertEqual("supported", result["status"])
        self.assertEqual(0, result["alignment"]["integer_delay_samples"])
        self.assertAlmostEqual(
            expected, result["alignment"]["fractional_delay_samples"], delta=0.05
        )

    def test_periodic_alignment_and_excessive_gain_abstain(self) -> None:
        periodic = [
            math.sin(2 * math.pi * 100 * index / 2000) for index in range(12000)
        ]
        periodic_result = MODULE.align_mono(
            reference=periodic,
            test=periodic,
            sample_rate_hz=2000,
            recipe_identity="periodic",
        )
        self.assertEqual("unsupported", periodic_result["status"])
        self.assertIn(
            "ambiguous_alignment_peak", periodic_result["support"]["reasons"]
        )

        reference = fixture()
        gain_result = MODULE.align_mono(
            reference=reference,
            test=[0.1 * value for value in reference],
            sample_rate_hz=2000,
            recipe_identity="gain-over-limit",
        )
        self.assertEqual("unsupported", gain_result["status"])
        self.assertIn("gain_exceeds_limit", gain_result["support"]["reasons"])

    def test_clock_drift_over_limit_abstains(self) -> None:
        reference = fixture()
        ratio = 1.0 + 200.0 / 1_000_000.0
        test = []
        for index in range(math.floor(len(reference) * ratio)):
            position = index / ratio
            if position >= len(reference) - 1:
                break
            lower = int(position)
            fraction = position - lower
            test.append(
                reference[lower] * (1.0 - fraction)
                + reference[lower + 1] * fraction
            )
        result = MODULE.align_mono(
            reference=reference,
            test=test,
            sample_rate_hz=2000,
            recipe_identity="drift-over-limit",
        )
        self.assertEqual("unsupported", result["status"])
        self.assertIn(
            "clock_drift_exceeds_limit", result["support"]["reasons"]
        )

    def test_silence_and_nonfinite_input_abstain(self) -> None:
        silence = [0.0] * 12000
        silent_result = MODULE.align_mono(
            reference=silence,
            test=silence,
            sample_rate_hz=2000,
            recipe_identity="silence",
        )
        self.assertEqual("unsupported", silent_result["status"])
        self.assertIn("insufficient_active_audio", silent_result["support"]["reasons"])

        invalid_result = MODULE.align_mono(
            reference=[0.0, math.nan],
            test=[0.0, 0.0],
            sample_rate_hz=2000,
            recipe_identity="nan",
        )
        self.assertEqual(["invalid_numeric_input"], invalid_result["support"]["reasons"])


if __name__ == "__main__":
    unittest.main()
