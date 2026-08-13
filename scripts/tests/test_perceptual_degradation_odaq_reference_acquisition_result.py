from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate-perceptual-degradation-odaq-reference-acquisition-result.py"
SPEC = importlib.util.spec_from_file_location("odaq_reference_acquisition_result", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def result() -> dict:
    return MODULE.load_json(MODULE.RESULT)


class OdaqReferenceAcquisitionResultTest(unittest.TestCase):
    def test_committed_result_validates(self) -> None:
        self.assertEqual([], MODULE.validate(result()))

    def test_exact_inventory_is_required(self) -> None:
        value = result()
        value["retained_inventory"]["reference_count"] = 15
        value["retained_inventory"]["retained_audio_bytes"] -= 1
        self.assertIn("retained inventory evidence differs", MODULE.validate(value))

    def test_processed_scores_stimuli_and_collection_remain_closed(self) -> None:
        value = result()
        value["access_boundary"]["processed_condition_opened"] = True
        value["access_boundary"]["listening_score_opened"] = True
        value["access_boundary"]["stimulus_generated"] = True
        value["access_boundary"]["listener_response_collected"] = True
        errors = MODULE.validate(value)
        self.assertIn("access boundary must remain false: processed_condition_opened", errors)
        self.assertIn("access boundary must remain false: listening_score_opened", errors)
        self.assertIn("access boundary must remain false: stimulus_generated", errors)
        self.assertIn("access boundary must remain false: listener_response_collected", errors)

    def test_range_observation_cannot_be_claimed_as_all_attempts(self) -> None:
        value = result()
        value["successful_resume_range_access"]["scope"] = "all_attempts"
        self.assertIn("successful-resume Range evidence differs", MODULE.validate(value))

    def test_private_paths_are_rejected(self) -> None:
        value = copy.deepcopy(result())
        value["private_root"] = "/Users/example/Application Support/private"
        self.assertIn("result must not contain a private absolute path", MODULE.validate(value))


if __name__ == "__main__":
    unittest.main()
