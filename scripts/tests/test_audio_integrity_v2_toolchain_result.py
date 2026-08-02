from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate-audio-integrity-v2-toolchain-result.py"
SPEC = importlib.util.spec_from_file_location("v2_toolchain_result", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
REPORT_PATH = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "factorial-v2-toolchain-observed-20260802-001-aggregate.json"
)
REPORT = MODULE.load_object(REPORT_PATH)
MANIFEST = MODULE.load_object(
    ROOT / "benchmarks" / "audio-integrity-v2" / "toolchain-bindings.json"
)
FACTOR = MODULE.load_object(
    ROOT / "benchmarks" / "audio-integrity-v2" / "factor-levels.json"
)


class ToolchainResultTest(unittest.TestCase):
    def validate(self, report):
        return MODULE.validate(report, MANIFEST, FACTOR, REPORT_PATH, ROOT)

    def test_committed_result_validates(self) -> None:
        self.assertEqual([], self.validate(REPORT))

    def test_score_opening_is_rejected(self) -> None:
        broken = copy.deepcopy(REPORT)
        broken["scores_opened"] = True
        self.assertIn("report scores_opened differs", self.validate(broken))

    def test_missing_decoder_path_is_rejected(self) -> None:
        broken = copy.deepcopy(REPORT)
        broken["plumbing"]["decoders"].pop()
        self.assertIn("history decoder path identities differ", self.validate(broken))

    def test_wrapper_pcm_change_is_rejected(self) -> None:
        broken = copy.deepcopy(REPORT)
        broken["wrapper_golden_outputs"][0]["decoded_pcm_exactly_matches_input"] = False
        self.assertIn("wrapper golden outputs differ", self.validate(broken))

    def test_private_path_is_rejected(self) -> None:
        broken = copy.deepcopy(REPORT)
        broken["private"] = "/Users/example/private.wav"
        self.assertIn("report contains a private path", self.validate(broken))


if __name__ == "__main__":
    unittest.main()
