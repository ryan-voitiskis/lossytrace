from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "perceptual_degradation_listening_power.py"
REPORT_PATH = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-listening-power-simulation-20260803-001.json"
)
SPEC = importlib.util.spec_from_file_location("listening_power", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ListeningPowerTest(unittest.TestCase):
    def test_committed_report_matches_full_replay(self) -> None:
        committed = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(committed, MODULE.build_report())
        self.assertFalse(
            committed["decision"]["candidate_equivalence_target_met"]
        )
        self.assertTrue(committed["decision"]["stress_equivalence_target_met"])

    def test_report_is_deterministic_and_score_blind(self) -> None:
        first = MODULE.build_report(500)
        second = MODULE.build_report(500)
        self.assertEqual(first, second)
        self.assertFalse(first["observed_audio_scores_or_listener_responses_used"])
        self.assertFalse(first["decision"]["main_collection_authorized"])
        self.assertFalse(first["decision"]["listener_count_frozen"])

    def test_more_information_reduces_planning_standard_error(self) -> None:
        small = MODULE.simulate_design(MODULE.DESIGNS[0], replicates=200)
        large = MODULE.simulate_design(MODULE.DESIGNS[-1], replicates=200)
        self.assertGreater(
            small["audibility"][0]["planning_standard_error"],
            large["audibility"][0]["planning_standard_error"],
        )
        self.assertGreater(
            small["sdg_severity"][0]["planning_standard_error"],
            large["sdg_severity"][0]["planning_standard_error"],
        )

    def test_truth_at_decision_boundary_does_not_claim_high_power(self) -> None:
        result = MODULE.simulate_design(MODULE.DESIGNS[-1], replicates=2000)
        audible_boundary = next(
            row for row in result["audibility"] if row["truth_probability"] == 0.75
        )
        sdg_boundary = next(
            row for row in result["sdg_severity"] if row["truth_mean_sdg"] == -1.0
        )
        self.assertLess(audible_boundary["audible_gate_power"], 0.6)
        self.assertLess(sdg_boundary["material_severity_power"], 0.1)

    def test_invalid_replicate_count_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "replicates must be positive"):
            MODULE.simulate_design(MODULE.DESIGNS[0], replicates=0)


if __name__ == "__main__":
    unittest.main()
