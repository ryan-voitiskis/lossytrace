from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate_perceptual_degradation_stable_mastered_music_provider_screen.py"
OBSERVATION = ROOT / "research/toolchains/evidence/perceptual-degradation-stable-mastered-music-provider-public-record-observation-20260814-001.json"
SPEC = importlib.util.spec_from_file_location("stable_mastered_music_provider_screen", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def observation() -> dict:
    return json.loads(OBSERVATION.read_text(encoding="utf-8"))


class StableMasteredMusicProviderScreenTest(unittest.TestCase):
    def test_committed_observation_validates(self) -> None:
        self.assertEqual([], MODULE.validate_committed_observation())

    def test_candidate_capacity_and_capability_are_bound(self) -> None:
        value = observation()
        item = value["stable_mastered_music_candidates"][0]
        item["candidate_group_capacity"] = 17
        item["capabilities"] = ["music"]
        errors = MODULE.validate_observation(value)
        self.assertIn("candidate binding differs: solar_flux_zenodo", errors)
        self.assertIn("candidate capability differs: solar_flux_zenodo", errors)

    def test_language_and_render_variants_cannot_inflate_capacity(self) -> None:
        value = observation()
        item = next(row for row in value["stable_mastered_music_candidates"] if row["provider_id"] == "remnant_tamil_worship")
        item["candidate_group_capacity"] = 115
        self.assertIn("candidate binding differs: remnant_tamil_worship", MODULE.validate_observation(value))

    def test_historical_record_discrepancy_cannot_be_erased(self) -> None:
        value = observation()
        item = next(row for row in value["stable_mastered_music_candidates"] if row["provider_id"] == "lotte_lehmann_farewell_recital")
        item["public_description_wav_count"] = 19
        self.assertIn("Lehmann record discrepancy boundary differs", MODULE.validate_observation(value))

    def test_under_capacity_catalog_cannot_be_promoted(self) -> None:
        value = observation()
        item = next(row for row in value["screened_not_added"] if row["source_id"] == "daniel_william_lawrence_five_albums")
        item["candidate_group_capacity_ceiling"] = 8
        self.assertIn("Daniel Lawrence capacity boundary differs", MODULE.validate_observation(value))

    def test_audio_metric_score_and_training_boundaries_remain_closed(self) -> None:
        value = observation()
        value["access_boundary"]["audio_member_accessed"] = True
        value["access_boundary"]["waveform_or_container_inspected"] = True
        value["access_boundary"]["perceptual_metric_executed"] = True
        value["access_boundary"]["no_reference_training_performed"] = True
        errors = MODULE.validate_observation(value)
        self.assertIn("access boundary differs: audio_member_accessed", errors)
        self.assertIn("access boundary differs: waveform_or_container_inspected", errors)
        self.assertIn("access boundary differs: perceptual_metric_executed", errors)
        self.assertIn("access boundary differs: no_reference_training_performed", errors)

    def test_arithmetic_cannot_select_successor_or_prove_science(self) -> None:
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
