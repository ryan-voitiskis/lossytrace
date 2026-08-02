from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate-audio-integrity-v2-public-decoder-result.py"
SPEC = importlib.util.spec_from_file_location("v2_public_decoder_result", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/public-decoder-equivalence-observed-20260802-001-aggregate.json"
)
REPORT = MODULE.load_object(REPORT_PATH)
PLAN = MODULE.load_object(
    ROOT / "benchmarks/audio-integrity-v2/public-decoder-equivalence-plan.json"
)
BINDING = MODULE.load_object(
    ROOT / "benchmarks/audio-integrity-v2/public-decoder-binary-binding.json"
)
MANIFEST = MODULE.load_object(
    ROOT / "benchmarks/audio-integrity-v2/toolchain-bindings.json"
)


class PublicDecoderResultTest(unittest.TestCase):
    def validate(self, report):
        return MODULE.validate(report, PLAN, BINDING, MANIFEST, REPORT_PATH, ROOT)

    def test_committed_result_validates(self) -> None:
        self.assertEqual([], self.validate(REPORT))

    def test_verdict_enablement_is_rejected(self) -> None:
        broken = copy.deepcopy(REPORT)
        broken["public_verdict_enabled"] = True
        self.assertIn("report public_verdict_enabled differs", self.validate(broken))

    def test_changed_projection_is_rejected(self) -> None:
        broken = copy.deepcopy(REPORT)
        broken["wrapper_paths"][0]["public_projection_sha256"] = "0" * 64
        self.assertTrue(
            any("wrapper triplet hashes differ" in error for error in self.validate(broken))
        )

    def test_inexact_analysis_pcm_is_rejected(self) -> None:
        broken = copy.deepcopy(REPORT)
        broken["wrapper_paths"][0]["analysis_decoded_pcm_exactly_matches_input"] = False
        self.assertIn("wrapper path evidence differs", self.validate(broken))


if __name__ == "__main__":
    unittest.main()
