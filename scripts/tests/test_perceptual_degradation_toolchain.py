from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE = importlib.import_module("perceptual_degradation_toolchain")


class PerceptualDegradationToolchainTest(unittest.TestCase):
    def test_templates_are_score_free_and_stream_float64(self) -> None:
        self.assertIn("pcm_f64le", MODULE.DECODE_TEMPLATE)
        self.assertIn("f64le", MODULE.DECODE_TEMPLATE)
        self.assertIn(MODULE.RESAMPLE_FILTER, MODULE.RESAMPLE_TEMPLATE)
        encoded = " ".join(MODULE.DECODE_TEMPLATE + MODULE.RESAMPLE_TEMPLATE).lower()
        self.assertNotIn("visqol", encoded)
        self.assertNotIn("peaq", encoded)
        self.assertNotIn("verdict", encoded)

    def test_resampler_is_exact_rational_and_dither_free(self) -> None:
        self.assertIn("exact_rational=1", MODULE.RESAMPLE_FILTER)
        self.assertIn("linear_interp=0", MODULE.RESAMPLE_FILTER)
        self.assertIn("dither_method=none", MODULE.RESAMPLE_FILTER)
        self.assertIn("osf=dbl", MODULE.RESAMPLE_FILTER)

    def test_tool_hashes_reuse_frozen_v2_bindings(self) -> None:
        self.assertEqual(
            "d2af2f0b78b184189806d724c294d7606f37d2763839e17c9289f7957da52070",
            MODULE.sha256_file(
                ROOT / "benchmarks" / "audio-integrity-v2" / "toolchain-bindings.json"
            ),
        )
        self.assertEqual(64, len(MODULE.FFMPEG_SHA256))
        self.assertEqual(64, len(MODULE.FFPROBE_SHA256))


if __name__ == "__main__":
    unittest.main()
