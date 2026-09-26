from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate_perceptual_degradation_stable_music_provider_screen.py"
OBSERVATION = ROOT / "research/toolchains/evidence/perceptual-degradation-stable-music-provider-public-record-observation-20260814-001.json"
SPEC = importlib.util.spec_from_file_location("stable_music_provider_screen", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def observation() -> dict:
    return json.loads(OBSERVATION.read_text(encoding="utf-8"))


class StableMusicProviderScreenTest(unittest.TestCase):
    def test_committed_observation_validates(self) -> None:
        self.assertEqual([], MODULE.validate_committed_observation())

    def test_controlled_candidates_cannot_be_promoted_to_mastered_music(self) -> None:
        value = observation()
        candidate = value["stable_controlled_music_candidates"][0]
        candidate["capabilities"].append("mastered_music")
        candidate["music_role"] = "mastered_music"
        errors = MODULE.validate_observation(value)
        self.assertIn("candidate capability differs: vienna_4x22", errors)
        self.assertIn("candidate mastered-music boundary differs: vienna_4x22", errors)

    def test_extra_rights_restrictions_cannot_be_ignored(self) -> None:
        value = observation()
        item = next(row for row in value["screened_not_added"] if row["source_id"] == "kraisler_21082251_v1")
        item["public_description_additional_restrictions"] = []
        self.assertIn("KRAISLER rights-conflict disposition differs", MODULE.validate_observation(value))

    def test_paper_licence_cannot_replace_audio_dataset_licence(self) -> None:
        value = observation()
        item = next(row for row in value["screened_not_added"] if row["source_id"] == "moisesdb")
        item["audio_dataset_licence"] = "CC BY 4.0"
        self.assertIn("MoisesDB licence-scope disposition differs", MODULE.validate_observation(value))

    def test_audio_metric_score_and_training_boundaries_remain_closed(self) -> None:
        value = observation()
        value["access_boundary"]["audio_member_accessed"] = True
        value["access_boundary"]["perceptual_metric_executed"] = True
        value["access_boundary"]["no_reference_training_performed"] = True
        errors = MODULE.validate_observation(value)
        self.assertIn("access boundary differs: audio_member_accessed", errors)
        self.assertIn("access boundary differs: perceptual_metric_executed", errors)
        self.assertIn("access boundary differs: no_reference_training_performed", errors)

    def test_access_boundary_keys_cannot_be_removed(self) -> None:
        value = observation()
        del value["access_boundary"]["audio_member_accessed"]
        self.assertIn("access boundary differs: audio_member_accessed", MODULE.validate_observation(value))

    def test_successors_and_scientific_gates_remain_closed(self) -> None:
        value = observation()
        value["decision"]["source_successor_selected"] = True
        value["decision"]["no_reference_work_eligible"] = True
        errors = MODULE.validate_observation(value)
        self.assertIn("decision differs: source_successor_selected", errors)
        self.assertIn("decision differs: no_reference_work_eligible", errors)

    def test_bounded_negative_cannot_become_full_objective_result(self) -> None:
        value = observation()
        value["claim_boundary"]["bounded_search_is_exhaustive_global_search"] = True
        value["claim_boundary"]["screen_is_full_objective_negative_result"] = True
        errors = MODULE.validate_observation(value)
        self.assertIn("claim boundary must remain false: bounded_search_is_exhaustive_global_search", errors)
        self.assertIn("claim boundary must remain false: screen_is_full_objective_negative_result", errors)


if __name__ == "__main__":
    unittest.main()
