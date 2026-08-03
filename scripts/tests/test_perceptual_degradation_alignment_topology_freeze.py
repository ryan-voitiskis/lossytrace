from __future__ import annotations

import hashlib
import importlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE = importlib.import_module("perceptual_degradation_alignment_v2")
FREEZE_PATH = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "alignment-topology-freeze.json"
)
FREEZE = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PerceptualDegradationAlignmentTopologyFreezeTest(unittest.TestCase):
    def test_freeze_is_score_free_and_hash_bound(self) -> None:
        for key in (
            "features_computed",
            "perceptual_metric_executed",
            "retained_audio_accessed",
            "scores_opened",
            "sealed_labels_opened",
            "public_verdict_enabled",
        ):
            self.assertFalse(FREEZE[key])
        for binding in [FREEZE["upstream_mono_freeze"], *FREEZE["bindings"].values()]:
            path = ROOT / binding["path"]
            self.assertEqual(binding["sha256"], sha256_file(path))

    def test_limits_match_implementation(self) -> None:
        self.assertEqual(FREEZE["freeze_id"], MODULE.LIMITS_ID)
        self.assertEqual(
            {tuple(value) for value in FREEZE["limits"]["supported_channel_maps"]},
            MODULE.SUPPORTED_CHANNEL_MAPS,
        )
        self.assertEqual(
            FREEZE["limits"]["maximum_channel_lag_disagreement_samples"],
            MODULE.MAX_CHANNEL_LAG_DISAGREEMENT_SAMPLES,
        )
        self.assertEqual(
            FREEZE["limits"]["maximum_structural_residual_samples"],
            MODULE.MAX_STRUCTURAL_RESIDUAL_SAMPLES,
        )


if __name__ == "__main__":
    unittest.main()
