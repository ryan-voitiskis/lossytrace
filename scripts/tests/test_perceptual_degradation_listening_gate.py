from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate-perceptual-degradation-listening-gate.py"
GATE_PATH = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "listening-preparation-gate.json"
)
SPEC = importlib.util.spec_from_file_location("listening_gate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
GATE = json.loads(GATE_PATH.read_text(encoding="utf-8"))


class ListeningGateTest(unittest.TestCase):
    def test_current_gate_is_valid_and_collection_is_unauthorized(self) -> None:
        self.assertEqual([], MODULE.validate(GATE))
        self.assertFalse(GATE["human_collection_authorized"])
        self.assertFalse(GATE["recruitment_authorized"])
        self.assertFalse(GATE["response_storage_authorized"])

    def test_gate_rejects_real_listener_authorization(self) -> None:
        changed = copy.deepcopy(GATE)
        changed["human_collection_authorized"] = True
        changed["recruitment_authorized"] = True
        self.assertIn(
            "human_collection_authorized must remain false",
            MODULE.validate(changed),
        )
        self.assertIn(
            "recruitment_authorized must remain false", MODULE.validate(changed)
        )

    def test_gate_rejects_premature_prerequisite_completion(self) -> None:
        changed = copy.deepcopy(GATE)
        changed["completed"]["power_report_frozen"] = True
        self.assertIn(
            "completed.power_report_frozen must be false", MODULE.validate(changed)
        )

    def test_gate_rejects_response_identity_or_small_cell_publication(self) -> None:
        changed = copy.deepcopy(GATE)
        changed["privacy"]["participant_identity_in_response_data"] = True
        changed["privacy"]["public_small_cell_results_authorized"] = True
        errors = MODULE.validate(changed)
        self.assertIn(
            "privacy.participant_identity_in_response_data must remain false",
            errors,
        )
        self.assertIn(
            "privacy.public_small_cell_results_authorized must remain false", errors
        )


if __name__ == "__main__":
    unittest.main()
