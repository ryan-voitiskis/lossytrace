from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_breadth_repair_feasibility.py"
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/breadth-repair-provider-allocation-feasibility-plan.json"
SPEC = importlib.util.spec_from_file_location("breadth_repair_feasibility", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class BreadthRepairFeasibilityTest(unittest.TestCase):
    def test_committed_plan_and_report_validate(self) -> None:
        self.assertEqual([], MODULE.validate_plan(plan()))
        self.assertEqual([], MODULE.validate_committed_report())

    def test_report_is_deterministic(self) -> None:
        self.assertEqual(MODULE.build_report(plan()), MODULE.build_report(plan()))

    def test_public_record_and_stable_record_results_remain_distinct(self) -> None:
        results = {
            item["scenario_id"]: item["arithmetic_feasible"]
            for item in MODULE.build_report(plan())["scenario_results"]
        }
        self.assertTrue(results["public_record_three_domains_every_partition"])
        self.assertFalse(results["stable_record_three_domains_every_partition"])
        self.assertTrue(results["public_record_mastered_music_every_partition"])
        self.assertFalse(results["stable_record_mastered_music_every_partition"])
        self.assertTrue(results["public_record_final_two_mastered_music_providers"])

    def test_reference_sensitivity_depends_on_provisional_records(self) -> None:
        results = {
            item["scenario_id"]: item["arithmetic_feasible"]
            for item in MODULE.build_report(plan())["scenario_results"]
        }
        self.assertTrue(results["public_record_reference_120_recording_ceiling"])
        self.assertTrue(results["public_record_reference_120_conservative_relationship_floor"])
        self.assertFalse(results["stable_record_reference_120_recording_ceiling"])

    def test_capacity_witness_never_splits_or_promotes_a_provider(self) -> None:
        for result in MODULE.build_report(plan())["scenario_results"]:
            provider_ids = [item["provider_id"] for item in result["capacity_witness"]]
            self.assertEqual(len(provider_ids), len(set(provider_ids)))
            self.assertFalse(result["exact_member_selection_frozen"])
            self.assertFalse(result["scientifically_eligible"])

    def test_mutable_provider_cannot_be_relabelled_stable(self) -> None:
        value = plan()
        provider = next(item for item in value["new_providers"] if item["provider_id"] == "icsi_meeting")
        provider["record_status"] = "immutable_or_stable"
        self.assertIn("new provider binding differs: icsi_meeting", MODULE.validate_plan(value))

    def test_recording_ceiling_and_floor_are_bound(self) -> None:
        value = plan()
        provider = next(item for item in value["new_providers"] if item["provider_id"] == "datastorre_acoustic_examples")
        provider["available_group_capacity"] = 8
        self.assertIn("new provider binding differs: datastorre_acoustic_examples", MODULE.validate_plan(value))
        value = plan()
        scenario = next(item for item in value["scenarios"] if item["scenario_id"] == "stable_record_reference_120_recording_ceiling")
        scenario["included_new_record_statuses"].append("preservation_required_provisional")
        with self.assertRaisesRegex(ValueError, "scenario result differs"):
            MODULE.build_report(value)

    def test_stable_controlled_music_capacity_is_bound_without_mastered_promotion(self) -> None:
        value = plan()
        provider = next(item for item in value["new_providers"] if item["provider_id"] == "vienna_4x22")
        provider["available_group_capacity"] = 23
        self.assertIn("new provider binding differs: vienna_4x22", MODULE.validate_plan(value))
        value = plan()
        provider = next(item for item in value["new_providers"] if item["provider_id"] == "vienna_4x22")
        provider["capabilities"] = ["music", "mastered_music"]
        self.assertIn("new provider binding differs: vienna_4x22", MODULE.validate_plan(value))

    def test_audio_metric_score_training_and_successor_gates_remain_closed(self) -> None:
        value = plan()
        value["authorization"]["new_audio_acquisition_authorized"] = True
        value["authorization"]["perceptual_metric_execution_authorized"] = True
        value["authorization"]["no_reference_training_authorized"] = True
        value["decision_boundary"]["selected_source_successor"] = "icsi_meeting"
        errors = MODULE.validate_plan(value)
        self.assertIn("authorization boundary differs", errors)
        self.assertIn("source successor was prematurely selected", errors)

    def test_arithmetic_cannot_be_promoted_to_scientific_feasibility(self) -> None:
        value = plan()
        value["claim_boundary"]["arithmetic_feasibility_is_scientific_feasibility"] = True
        self.assertIn(
            "claim boundary must remain false: arithmetic_feasibility_is_scientific_feasibility",
            MODULE.validate_plan(value),
        )


if __name__ == "__main__":
    unittest.main()
