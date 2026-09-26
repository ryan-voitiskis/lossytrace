from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_provider_allocation_feasibility.py"
PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "permissive-provider-allocation-feasibility-plan.json"
)
SPEC = importlib.util.spec_from_file_location("provider_allocation_feasibility", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


class ProviderAllocationFeasibilityTest(unittest.TestCase):
    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate_plan(plan()))

    def test_report_is_deterministic_and_matches_frozen_scenarios(self) -> None:
        first = MODULE.build_report(plan())
        second = MODULE.build_report(plan())
        self.assertEqual(first, second)
        results = {
            result["scenario_id"]: result
            for result in first["scenario_results"]
        }
        self.assertTrue(results["audit_count_only"]["arithmetic_feasible"])
        self.assertFalse(
            results["audit_two_providers_each_partition"]["arithmetic_feasible"]
        )
        self.assertFalse(
            results["audit_final_three_domain_minimum"]["arithmetic_feasible"]
        )
        self.assertFalse(
            results["add_musicnet_final_three_domain_minimum"][
                "arithmetic_feasible"
            ]
        )
        self.assertTrue(
            results["add_all_pending_final_three_domain_minimum"][
                "arithmetic_feasible"
            ]
        )
        self.assertFalse(
            results["all_pending_three_domains_each_partition"][
                "arithmetic_feasible"
            ]
        )

    def test_capacity_witness_never_splits_a_provider(self) -> None:
        report = MODULE.build_report(plan())
        for result in report["scenario_results"]:
            providers = [item["provider_id"] for item in result["capacity_witness"]]
            self.assertEqual(len(providers), len(set(providers)))
            self.assertFalse(result["exact_member_selection_frozen"])
            self.assertFalse(result["scientifically_eligible"])

    def test_synthetic_cannot_be_relabelled_as_music(self) -> None:
        value = plan()
        for provider in value["providers"]:
            if provider["provider_id"] == "slakh":
                provider["domain"] = "music"
        self.assertIn("provider domain differs: slakh", MODULE.validate_plan(value))

    def test_pending_provider_cannot_be_promoted_by_sensitivity(self) -> None:
        value = plan()
        value["solver_policy"]["pending_provider_can_be_scientifically_eligible"] = True
        value["scenarios"][4]["scientifically_eligible"] = True
        errors = MODULE.validate_plan(value)
        self.assertIn("solver policy differs", errors)
        self.assertIn(
            "scenario was prematurely made eligible: add_all_pending_final_three_domain_minimum",
            errors,
        )

    def test_member_audio_score_and_collection_authority_remain_closed(self) -> None:
        value = plan()
        value["authorization"]["exact_member_selection_authorized"] = True
        value["authorization"]["new_audio_acquisition_authorized"] = True
        value["authorization"]["listening_score_access_authorized"] = True
        value["authorization"]["human_collection_authorized"] = True
        self.assertIn("authorization boundary differs", MODULE.validate_plan(value))

    def test_source_floor_and_domain_minimum_remain_bound(self) -> None:
        value = plan()
        value["scenarios"][0]["minimum_groups_each_partition"] = 38
        value["scenarios"][2]["domain_minimums_by_partition"]["final_validation"][
            "music"
        ] = 7
        errors = MODULE.validate_plan(value)
        self.assertIn("scenario source floor differs: audit_count_only", errors)
        self.assertIn(
            "scenario domain minimum differs: audit_final_three_domain_minimum",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
