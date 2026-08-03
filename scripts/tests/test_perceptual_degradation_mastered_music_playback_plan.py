from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts/validate-perceptual-degradation-mastered-music-playback-plan.py"
)
PLAN = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/mastered-music-playback-qualification-plan.json"
)
SPEC = importlib.util.spec_from_file_location("mastered_music_playback", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class MasteredMusicPlaybackPlanTest(unittest.TestCase):
    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate(plan()))

    def test_audio_and_human_collection_cannot_be_authorized(self) -> None:
        value = plan()
        value["access_boundary"]["retained_audio_access_authorized"] = True
        value["access_boundary"]["listener_response_collection_authorized"] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "access boundary must remain false: retained_audio_access_authorized", errors
        )
        self.assertIn(
            "access boundary must remain false: listener_response_collection_authorized",
            errors,
        )

    def test_lossy_music_portals_cannot_become_clean_references(self) -> None:
        value = plan()
        fma = next(
            item for item in value["deferred_or_excluded_sources"] if item["source_id"] == "fma"
        )
        fma["disposition"] = "lossless_reference"
        value["claim_boundary"]["lossy_distributed_audio_used_as_lossless_reference"] = True
        errors = MODULE.validate(value)
        self.assertIn("FMA reference boundary differs", errors)
        self.assertIn(
            "claim boundary differs: lossy_distributed_audio_used_as_lossless_reference",
            errors,
        )

    def test_audibility_confirmation_cannot_qualify_playback(self) -> None:
        value = plan()
        playback = value["local_playback_observation"]
        playback["operator_synthetic_audibility_confirmation_reused_as_qualification"] = True
        playback["physical_playback_qualified"] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "playback boundary differs: operator_synthetic_audibility_confirmation_reused_as_qualification",
            errors,
        )
        self.assertIn("playback boundary differs: physical_playback_qualified", errors)

    def test_permissive_fallback_cannot_claim_independent_transfer(self) -> None:
        value = plan()
        fallback = value["permissive_source_fallback"]
        fallback["provider_stratum_count"] = 16
        fallback["independent_provider_transfer_supported"] = True
        fallback["final_validation_supported"] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "permissive fallback count differs: provider_stratum_count", errors
        )
        self.assertIn(
            "permissive fallback boundary differs: independent_provider_transfer_supported",
            errors,
        )
        self.assertIn(
            "permissive fallback boundary differs: final_validation_supported", errors
        )

    def test_source_manifest_cannot_become_freezable_before_human_gates(self) -> None:
        value = plan()
        value["decision"]["licences_frozen"] = True
        value["decision"]["source_and_condition_manifest_freezable"] = True
        errors = MODULE.validate(value)
        self.assertIn("premature qualification completion: licences_frozen", errors)
        self.assertIn(
            "premature qualification completion: source_and_condition_manifest_freezable",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
