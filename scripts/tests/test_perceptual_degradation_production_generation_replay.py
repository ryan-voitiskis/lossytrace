from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts/validate-perceptual-degradation-production-generation-replay.py"
)
EVIDENCE = (
    ROOT
    / "research/toolchains/evidence/perceptual-degradation-production-generation-synthetic-replay-20260804-001.json"
)
SPEC = importlib.util.spec_from_file_location("production_generation_replay", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def evidence() -> dict:
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


class ProductionGenerationReplayTest(unittest.TestCase):
    def test_committed_replay_evidence_validates(self) -> None:
        self.assertEqual([], MODULE.validate(evidence()))

    def test_replay_reports_must_be_two_and_identical(self) -> None:
        value = evidence()
        value["replay_observation"]["report_sha256s"][1] = "0" * 64
        self.assertIn("replay report hashes differ", MODULE.validate(value))

    def test_actual_audio_and_outcome_access_remain_false(self) -> None:
        value = evidence()
        value["summary"]["actual_audio_accessed"] = True
        value["summary"]["perceptual_truth_included"] = True
        errors = MODULE.validate(value)
        self.assertIn("outcome boundary differs: actual_audio_accessed", errors)
        self.assertIn("outcome boundary differs: perceptual_truth_included", errors)

    def test_all_production_controls_must_pass_support(self) -> None:
        value = evidence()
        value["production_cases"][0]["support_passed"] = False
        value["production_cases"][0]["changed_frame_fraction"] = 0.0
        errors = MODULE.validate(value)
        recipe_id = value["production_cases"][0]["recipe_id"]
        self.assertIn(f"production support failed: {recipe_id}", errors)
        self.assertIn(f"production support fraction differs: {recipe_id}", errors)

    def test_only_frozen_cross_rate_paths_resample(self) -> None:
        value = evidence()
        case = next(
            item
            for item in value["generation_cases"]
            if item["recipe_id"] == "generation-repeat-mp3-lame-v2-v1"
        )
        case["intermediate_resampling_applied"] = True
        self.assertIn(
            "generation replay transition differs: generation-repeat-mp3-lame-v2-v1",
            MODULE.validate(value),
        )

    def test_verified_tool_hashes_must_match_bound_toolchain(self) -> None:
        value = evidence()
        value["verified_tools"]["ffmpeg_8_1_2_1"] = "0" * 64
        self.assertIn("verified tool bindings differ", MODULE.validate(value))


if __name__ == "__main__":
    unittest.main()
