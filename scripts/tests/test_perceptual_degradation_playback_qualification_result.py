from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate-perceptual-degradation-playback-qualification-result.py"
SPEC = importlib.util.spec_from_file_location("playback_qualification_result", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def result() -> dict:
    return MODULE.load_json(MODULE.RESULT)


class PlaybackQualificationResultTest(unittest.TestCase):
    def test_committed_result_validates(self) -> None:
        self.assertEqual([], MODULE.validate(result()))

    def test_exact_rate_and_channel_observations_are_required(self) -> None:
        value = result()
        value["execution"]["audio_context_sample_rate_hz"] = 96_000
        value["responsible_human_observations"]["left_button_audible_from_left_only"] = False
        errors = MODULE.validate(value)
        self.assertIn("execution evidence differs: audio_context_sample_rate_hz", errors)
        self.assertIn(
            "responsible-human observation differs: left_button_audible_from_left_only",
            errors,
        )

    def test_no_discomfort_and_no_rating_are_distinct(self) -> None:
        value = result()
        value["responsible_human_observations"]["no_discomfort_observed"] = False
        value["responsible_human_observations"]["degradation_rating_provided"] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "responsible-human observation differs: no_discomfort_observed", errors
        )
        self.assertIn("a degradation rating was improperly recorded", errors)

    def test_retained_references_and_perceptual_truth_remain_closed(self) -> None:
        value = result()
        value["access_boundary"]["retained_reference_played"] = True
        value["access_boundary"]["listener_response_collected"] = True
        value["claim_boundary"]["qualification_is_perceptual_validation"] = True
        errors = MODULE.validate(value)
        self.assertIn("access boundary must remain false: retained_reference_played", errors)
        self.assertIn("access boundary must remain false: listener_response_collected", errors)
        self.assertIn(
            "claim boundary must remain false: qualification_is_perceptual_validation",
            errors,
        )

    def test_private_paths_are_rejected(self) -> None:
        value = copy.deepcopy(result())
        value["fixture_disposition"]["private_path"] = "/Users/example/private"
        self.assertIn(
            "qualification result must not contain a private absolute path",
            MODULE.validate(value),
        )


if __name__ == "__main__":
    unittest.main()
