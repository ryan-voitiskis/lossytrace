from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate_perceptual_degradation_stable_speech_provider_screen.py"
OBSERVATION = ROOT / "research/toolchains/evidence/perceptual-degradation-stable-speech-provider-public-record-observation-20260814-001.json"
SPEC = importlib.util.spec_from_file_location("stable_speech_provider_screen", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def observation() -> dict:
    return json.loads(OBSERVATION.read_text(encoding="utf-8"))


class StableSpeechProviderScreenTest(unittest.TestCase):
    def test_committed_observation_validates(self) -> None:
        self.assertEqual([], MODULE.validate_committed_observation())

    def test_candidate_capacity_and_revision_are_bound(self) -> None:
        value = observation()
        candidate = value["stable_speech_candidates"][0]
        candidate["candidate_group_capacity"] = 189
        candidate["repository_commit"] = "7990b7d"
        self.assertIn("VibraVox candidate binding differs", MODULE.validate_observation(value))

    def test_only_clean_headset_speech_is_eligible(self) -> None:
        value = observation()
        candidate = value["stable_speech_candidates"][0]
        candidate["eligible_public_subset"] = "speech_noisy"
        candidate["eligible_public_audio_field"] = "audio.throat_microphone"
        errors = MODULE.validate_observation(value)
        self.assertIn("VibraVox eligible field boundary differs", errors)

    def test_body_conduction_and_noisy_subsets_remain_excluded(self) -> None:
        value = observation()
        value["screen_policy"]["body_conduction_channel_eligible_as_clean_reference"] = True
        value["stable_speech_candidates"][0]["excluded_public_subsets"] = ["speechless_clean"]
        errors = MODULE.validate_observation(value)
        self.assertIn("screen policy differs", errors)
        self.assertIn("VibraVox excluded subset boundary differs", errors)

    def test_data_object_audio_metric_score_and_training_boundaries_remain_closed(self) -> None:
        value = observation()
        value["access_boundary"]["repository_data_object_opened"] = True
        value["access_boundary"]["audio_member_accessed"] = True
        value["access_boundary"]["perceptual_metric_executed"] = True
        value["access_boundary"]["no_reference_training_performed"] = True
        errors = MODULE.validate_observation(value)
        self.assertIn("access boundary differs: repository_data_object_opened", errors)
        self.assertIn("access boundary differs: audio_member_accessed", errors)
        self.assertIn("access boundary differs: perceptual_metric_executed", errors)
        self.assertIn("access boundary differs: no_reference_training_performed", errors)

    def test_successors_and_scientific_gates_remain_closed(self) -> None:
        value = observation()
        value["decision"]["source_successor_selected"] = True
        value["decision"]["no_reference_work_eligible"] = True
        value["claim_boundary"]["candidate_capacity_is_scientific_feasibility"] = True
        errors = MODULE.validate_observation(value)
        self.assertIn("decision differs: source_successor_selected", errors)
        self.assertIn("decision differs: no_reference_work_eligible", errors)
        self.assertIn("claim boundary must remain false: candidate_capacity_is_scientific_feasibility", errors)


if __name__ == "__main__":
    unittest.main()
