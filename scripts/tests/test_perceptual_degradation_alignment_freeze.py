from __future__ import annotations

import importlib.util
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "perceptual_degradation_alignment.py"
FREEZE_PATH = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "alignment-fixture-freeze.json"
)
SPEC = importlib.util.spec_from_file_location("perceptual_degradation_alignment", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FREEZE = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PerceptualDegradationAlignmentFreezeTest(unittest.TestCase):
    def test_freeze_is_score_free_and_hash_bound(self) -> None:
        self.assertEqual(
            "score_free_alignment_limits_frozen_before_retained_audio",
            FREEZE["state"],
        )
        for key in (
            "features_computed",
            "perceptual_metric_executed",
            "retained_audio_accessed",
            "scores_opened",
            "sealed_labels_opened",
            "public_verdict_enabled",
        ):
            self.assertFalse(FREEZE[key])
        for binding in [FREEZE["research_plan"], *FREEZE["bindings"].values()]:
            path = ROOT / binding["path"]
            self.assertEqual(binding["sha256"], sha256_file(path))

    def test_frozen_limits_match_implementation(self) -> None:
        expected = {
            "envelope_rate_hz": MODULE.ENVELOPE_RATE_HZ,
            "maximum_correlation_samples": MODULE.MAX_CORRELATION_SAMPLES,
            "minimum_alignment_correlation": MODULE.MIN_ALIGNMENT_CORRELATION,
            "minimum_ambiguity_margin": MODULE.MIN_AMBIGUITY_MARGIN,
            "maximum_gain_abs_db": MODULE.MAX_GAIN_ABS_DB,
            "maximum_clock_drift_ppm": MODULE.MAX_CLOCK_DRIFT_PPM,
            "maximum_nonlinear_drift_residual_samples": MODULE.MAX_NONLINEAR_DRIFT_RESIDUAL_SAMPLES,
            "maximum_edge_trim_seconds": MODULE.MAX_EDGE_TRIM_SECONDS,
            "maximum_edge_trim_fraction": MODULE.MAX_EDGE_TRIM_FRACTION,
            "maximum_delay_seconds_default": 2.0,
            "minimum_active_seconds_default": 4.0,
        }
        self.assertEqual(expected, FREEZE["limits"])
        self.assertEqual(FREEZE["freeze_id"], MODULE.LIMITS_ID)


if __name__ == "__main__":
    unittest.main()
