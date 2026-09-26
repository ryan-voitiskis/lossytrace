import copy
import importlib.util
import json
import math
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts/perceptual_degradation_listening_retained_design_robustness.py"
)
SPEC = importlib.util.spec_from_file_location(
    "perceptual_degradation_listening_retained_design_robustness", SCRIPT
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RetainedDesignRobustnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.feasibility = MODULE.load_json(
            MODULE._bound(cls.plan, "feasibility_plan")
        )
        cls.resource = MODULE.load_json(
            MODULE._bound(cls.plan, "resource_frontier_plan")
        )
        cls.manifest = MODULE.RESOURCE.make_symbolic_manifest(cls.resource)
        cls.seed = cls.resource["symbolic_fixture"]["allocation_seed"]

    def test_frozen_plan_validates(self):
        self.assertEqual(MODULE.validate_plan(self.plan), [])

    def test_binding_mutation_is_rejected(self):
        mutated = copy.deepcopy(self.plan)
        mutated["bindings"]["feasibility_plan"]["sha256"] = "0" * 64
        self.assertIn(
            "binding feasibility_plan sha256 differs",
            MODULE.validate_plan(mutated),
        )

    def test_kish_effective_count_tracks_imbalance(self):
        self.assertEqual(MODULE.kish_effective_count([]), 0.0)
        self.assertEqual(MODULE.kish_effective_count([2, 2, 2]), 3.0)
        self.assertAlmostEqual(MODULE.kish_effective_count([1, 2]), 1.8)

    def test_candidate_position_graph_connectivity(self):
        candidates = ["a", "b"]
        self.assertEqual(
            MODULE._connected_components(
                candidates,
                2,
                {("a", 1), ("a", 2), ("b", 1), ("b", 2)},
            ),
            1,
        )
        self.assertEqual(
            MODULE._connected_components(
                candidates, 2, {("a", 1), ("b", 2)}
            ),
            2,
        )

    def test_small_mcar_replay_is_deterministic_and_score_blind(self):
        local_plan = copy.deepcopy(self.plan)
        local_plan["stress_contract"]["replicate_count"] = 4
        rows = MODULE.MISSINGNESS._make_schedule(
            self.manifest, self.seed, 24, 3, 3
        )
        first = MODULE._mcar_aggregate(
            local_plan,
            self.feasibility,
            self.manifest,
            rows,
            self.seed,
            "hash_mcar_trial",
            0.90,
        )
        second = MODULE._mcar_aggregate(
            local_plan,
            self.feasibility,
            self.manifest,
            rows,
            self.seed,
            "hash_mcar_trial",
            0.90,
        )
        self.assertEqual(first, second)
        self.assertFalse(first["aggregate"]["outcomes_included"])
        self.assertEqual(first["aggregate"]["replicate_count"], 4)

    def test_reduced_full_report_build_is_deterministic(self):
        local_plan = copy.deepcopy(self.plan)
        local_plan["stress_contract"]["replicate_count"] = 2
        local_plan["stress_contract"]["retention_rates"] = [0.90]
        local_plan["stress_contract"]["issued_reserve_multipliers"] = [1.0]
        local_plan["stress_contract"]["source_correlated_loss_counts"] = [6]
        local_plan["frontier_options"] = [local_plan["frontier_options"][0]]
        with mock.patch.object(MODULE, "validate_plan", return_value=[]):
            first = MODULE.build_report(local_plan)
            second = MODULE.build_report(local_plan)
        self.assertEqual(first, second)
        self.assertFalse(first["outcome_values_generated"])
        self.assertFalse(first["outcome_values_read"])
        self.assertFalse(first["decision"]["reserve_option_selected"])
        self.assertEqual(MODULE.validate_report(first), [])

    def test_committed_report_binds_current_plan_and_implementation(self):
        report = MODULE.load_json(MODULE.REPORT_PATH)
        self.assertEqual(report["plan_sha256"], MODULE.sha256_file(MODULE.PLAN_PATH))
        self.assertEqual(
            report["implementation_sha256"], MODULE.sha256_file(SCRIPT)
        )
        self.assertEqual(MODULE.validate_report(report), [])

    def test_frontier_exposes_compact_workload_support_cost(self):
        report = MODULE.load_json(MODULE.REPORT_PATH)
        minimums = report[
            "minimum_reserve_multiplier_by_option_kind_and_retention"
        ]
        compact = minimums["sources120-subtle15-mushra6"]
        self.assertEqual(
            compact["hash_mcar_trial"]["retention_0.85"], 1.4
        )
        self.assertEqual(
            compact["hash_mcar_session"]["retention_0.90"], 1.2
        )
        self.assertTrue(
            report["decision"][
                "all_mcar_sensitivity_cells_have_bounded_reserve_option"
            ]
        )
        self.assertFalse(
            report["decision"][
                "all_source_correlated_cells_preserve_fixed_manifest_support"
            ]
        )
        self.assertTrue(
            report["decision"][
                "any_source_correlated_cell_preserves_retained_aggregate_power"
            ]
        )

    def test_enrollment_projection_uses_frozen_eligibility_rate(self):
        report = MODULE.load_json(MODULE.REPORT_PATH)
        compact = next(
            option
            for option in report["option_results"]
            if option["option_id"] == "sources120-subtle15-mushra6"
        )
        reserve = next(
            row
            for row in compact["reserve_rows"]
            if row["issued_reserve_multiplier"] == 1.4
        )
        expected = math.ceil(
            reserve["issued_eligible_prefix"]
            / self.feasibility["score_blind_stress_assumptions"][
                "eligible_listener_retention_rate"
            ]
        )
        self.assertEqual(
            reserve[
                "planning_enrolled_slots_per_stratum_device_partition"
            ],
            expected,
        )
        self.assertEqual(
            reserve["planning_enrolled_slots_across_four_partitions"],
            4 * expected,
        )


if __name__ == "__main__":
    unittest.main()
