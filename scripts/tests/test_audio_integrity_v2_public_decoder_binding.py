from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = (
    ROOT
    / "benchmarks"
    / "audio-integrity-v2"
    / "public-decoder-equivalence-plan.json"
)
BINDING_PATH = (
    ROOT
    / "benchmarks"
    / "audio-integrity-v2"
    / "public-decoder-binary-binding.json"
)
PROBE_PATH = ROOT / "scripts" / "probe-audio-integrity-v2-public-decoder.py"
BASE_PATH = ROOT / "scripts" / "probe-audio-integrity-v2-toolchains.py"


def load(path: Path):
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PublicDecoderBindingTest(unittest.TestCase):
    def test_binding_is_path_free_and_matches_frozen_inputs(self) -> None:
        binding = load(BINDING_PATH)
        self.assertEqual(
            "public_decoder_binary_frozen_before_equivalence_probe",
            binding["state"],
        )
        self.assertEqual(sha256(PLAN_PATH), binding["plan_binding"]["sha256"])
        self.assertEqual(sha256(PROBE_PATH), binding["probe_script_sha256"])
        self.assertEqual(sha256(BASE_PATH), binding["base_probe_script_sha256"])
        self.assertEqual(64, len(binding["binary"]["sha256"]))
        self.assertEqual(3_242_160, binding["binary"]["byte_count"])
        self.assertFalse(binding["benchmark_audio_generated"])
        self.assertFalse(binding["scores_opened"])
        self.assertFalse(binding["selection_authorized"])
        self.assertFalse(binding["public_verdict_enabled"])
        self.assertFalse(binding["equivalence_probe_executed"])
        serialized = json.dumps(binding, sort_keys=True)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("/Volumes/", serialized)


if __name__ == "__main__":
    unittest.main()
