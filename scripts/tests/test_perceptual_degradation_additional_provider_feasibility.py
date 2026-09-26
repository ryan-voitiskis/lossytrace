from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_additional_provider_feasibility.py"
PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "additional-permissive-provider-allocation-feasibility-plan.json"
)
SPEC = importlib.util.spec_from_file_location("additional_provider_feasibility", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class AdditionalProviderFeasibilityTest(unittest.TestCase):
    def test_committed_plan_and_report_validate(self) -> None:
        self.assertEqual([], MODULE.validate_plan(plan()))
        self.assertEqual([], MODULE.validate_committed_report())

    def test_report_is_deterministic(self) -> None:
        self.assertEqual(MODULE.build_report(plan()), MODULE.build_report(plan()))

    def test_frozen_scenario_results_hold(self) -> None:
        results = {
            result["scenario_id"]: result["arithmetic_feasible"]
            for result in MODULE.build_report(plan())["scenario_results"]
        }
        self.assertTrue(results["expanded_count_only_39_each_partition"])
        self.assertTrue(results["expanded_two_providers_39_each_partition"])
        self.assertTrue(results["expanded_final_three_domain_minimum"])
        self.assertTrue(results["expanded_music_minimum_every_partition"])
        self.assertFalse(results["expanded_three_domains_every_partition"])
        self.assertFalse(results["expanded_mastered_music_minimum_every_partition"])
        self.assertFalse(results["expanded_final_two_mastered_music_providers"])
        self.assertFalse(results["expanded_reference_sensitivity_120_each_partition"])

    def test_capacity_witness_never_splits_a_provider(self) -> None:
        for result in MODULE.build_report(plan())["scenario_results"]:
            provider_ids = [item["provider_id"] for item in result["capacity_witness"]]
            self.assertEqual(len(provider_ids), len(set(provider_ids)))
            self.assertFalse(result["exact_member_selection_frozen"])
            self.assertFalse(result["scientifically_eligible"])

    def test_synthetic_cannot_be_relabelled_as_music(self) -> None:
        value = plan()
        provider = next(
            item for item in value["providers"] if item["provider_id"] == "slakh"
        )
        provider["capabilities"] = ["music"]
        self.assertIn(
            "provider capabilities differ: slakh", MODULE.validate_plan(value)
        )

    def test_controlled_music_cannot_be_relabelled_as_mastered(self) -> None:
        value = plan()
        provider = next(
            item
            for item in value["providers"]
            if item["provider_id"] == "choralebricks"
        )
        provider["capabilities"] = ["music", "mastered_music"]
        self.assertIn(
            "provider capabilities differ: choralebricks",
            MODULE.validate_plan(value),
        )

    def test_observed_new_provider_capacity_is_bound(self) -> None:
        value = plan()
        provider = next(
            item for item in value["providers"] if item["provider_id"] == "urmp"
        )
        provider["available_group_capacity"] = 44
        self.assertIn(
            "additional provider binding differs: urmp", MODULE.validate_plan(value)
        )

    def test_audio_score_metric_and_training_gates_remain_closed(self) -> None:
        value = plan()
        value["authorization"]["new_audio_acquisition_authorized"] = True
        value["authorization"][
            "target_perceptual_degradation_listening_score_access_authorized"
        ] = True
        value["authorization"]["perceptual_metric_execution_authorized"] = True
        value["authorization"]["no_reference_training_authorized"] = True
        self.assertIn("authorization boundary differs", MODULE.validate_plan(value))

    def test_successor_cannot_be_silently_selected(self) -> None:
        value = plan()
        value["decision_boundary"]["selected_source_successor"] = "albumdb"
        value["decision_boundary"]["selected_metric_successor"] = "visqol"
        errors = MODULE.validate_plan(value)
        self.assertIn("source successor was prematurely selected", errors)
        self.assertIn("metric successor was prematurely selected", errors)

    def test_candidate_screen_cannot_become_scientific_feasibility(self) -> None:
        value = plan()
        value["claim_boundary"][
            "arithmetic_feasibility_is_scientific_feasibility"
        ] = True
        self.assertIn(
            "claim boundary must remain false: arithmetic_feasibility_is_scientific_feasibility",
            MODULE.validate_plan(value),
        )


if __name__ == "__main__":
    unittest.main()
