import copy
import importlib.util
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts/perceptual_degradation_listening_condition_strata_workload.py"
)
SPEC = importlib.util.spec_from_file_location(
    "perceptual_degradation_listening_condition_strata_workload", SCRIPT
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ListeningConditionStrataWorkloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.load_json(MODULE.REPORT_PATH)

    def test_frozen_plan_validates(self):
        self.assertEqual(MODULE.validate_plan(self.plan), [])

    def test_binding_mutation_is_rejected(self):
        mutated = copy.deepcopy(self.plan)
        mutated["bindings"]["toolchain_bindings"]["sha256"] = "0" * 64
        self.assertIn(
            "binding toolchain_bindings sha256 differs",
            MODULE.validate_plan(mutated),
        )

    def test_candidate_grid_is_exactly_four_by_two_by_two(self):
        audit = self.report["candidate_codec_grid_audit"]
        self.assertEqual(audit["candidate_codec_family_count"], 4)
        self.assertEqual(audit["candidate_encoder_count"], 8)
        self.assertEqual(audit["candidate_quality_cell_count"], 16)
        self.assertEqual(audit["toolchain_expanded_setting_count"], 46)
        self.assertEqual(audit["toolchain_stereo_setting_count"], 24)
        self.assertFalse(audit["candidate_selected_for_listening"])
        self.assertFalse(audit["candidate_perceptual_truth_assigned"])
        for codec in audit["codec_rows"]:
            self.assertEqual(codec["encoder_count"], 2)
            self.assertEqual(codec["setting_count"], 4)
            for encoder in codec["encoders"]:
                self.assertEqual(encoder["setting_count"], 2)

    def test_control_inventory_has_six_families_and_twelve_recipes(self):
        audit = self.report["control_inventory_audit"]
        self.assertEqual(audit["production_family_count"], 4)
        self.assertEqual(audit["generation_family_count"], 2)
        self.assertEqual(audit["control_family_count"], 6)
        self.assertEqual(audit["control_recipe_count"], 12)
        self.assertTrue(audit["synthetic_replay_passed"])
        self.assertFalse(audit["actual_stimuli_generated"])
        self.assertFalse(audit["perceptual_truth_assigned"])

    def test_report_has_complete_sensitivity_cross_product(self):
        rows = self.report["workload_rows"]
        self.assertEqual(len(rows), 3 * 4 * 6)
        keys = {
            (row["retention_rate"], row["option_id"], row["scenario_id"])
            for row in rows
        }
        self.assertEqual(len(keys), len(rows))
        self.assertEqual(MODULE.validate_report(self.report), [])

    def test_session_capacities_separate_exact_and_optimistic_packing(self):
        expected = {
            "sources120-subtle3-mushra3": (2, 5),
            "sources120-subtle5-mushra5": (1, 3),
            "sources120-subtle8-mushra6": (1, 1),
            "sources120-subtle15-mushra6": (1, 1),
        }
        rows = [
            row
            for row in self.report["workload_rows"]
            if row["retention_rate"] == 0.90
            and row["scenario_id"] == "codec-recipe-grid"
        ]
        self.assertEqual(len(rows), 4)
        for row in rows:
            models = {model["model_id"]: model for model in row["models"]}
            exact, optimistic = expected[row["option_id"]]
            self.assertEqual(
                models["dedicated_stratum"][
                    "complete_strata_capacity_per_session"
                ],
                1,
            )
            self.assertEqual(
                models["exact_blocks_without_mushra_condition_packing"][
                    "complete_strata_capacity_per_session"
                ],
                exact,
            )
            self.assertEqual(
                models["optimistic_mushra_condition_packing"][
                    "complete_strata_capacity_per_session"
                ],
                optimistic,
            )

    def test_aggregate_scenario_cannot_duplicate_one_stratum_in_a_session(self):
        row = next(
            row
            for row in self.report["workload_rows"]
            if row["retention_rate"] == 0.90
            and row["option_id"] == "sources120-subtle3-mushra3"
            and row["scenario_id"] == "aggregate-only"
        )
        self.assertEqual(row["strata_count"], 1)
        self.assertEqual(
            {
                model["complete_strata_capacity_per_session"]
                for model in row["models"]
            },
            {1},
        )
        self.assertEqual(
            {
                model["eligible_session_slots_per_partition_device"]
                for model in row["models"]
            },
            {row["issued_eligible_prefix_per_stratum"]},
        )

    def test_enrollment_arithmetic_rounds_after_strata_multiplication(self):
        row = next(
            row
            for row in self.report["workload_rows"]
            if row["retention_rate"] == 0.90
            and row["option_id"] == "sources120-subtle3-mushra3"
            and row["scenario_id"] == "codec-recipe-grid"
        )
        self.assertEqual(
            row["session_stratum_memberships_per_partition_device"],
            row["issued_eligible_prefix_per_stratum"] * 16,
        )
        for model in row["models"]:
            expected_eligible = math.ceil(
                row["session_stratum_memberships_per_partition_device"]
                / model["complete_strata_capacity_per_session"]
            )
            expected_enrolled = math.ceil(expected_eligible / 0.646)
            self.assertEqual(
                model["eligible_session_slots_per_partition_device"],
                expected_eligible,
            )
            self.assertEqual(
                model["enrolled_session_slots_per_partition_device"],
                expected_enrolled,
            )
            four_partition_two_device = next(
                total["enrolled_session_slots"]
                for total in model["totals"]
                if total["partition_count"] == 4
                and total["device_class_count"] == 2
            )
            self.assertEqual(four_partition_two_device, expected_enrolled * 8)

    def test_ninety_percent_scale_points_are_stable_and_unselected(self):
        expected = {
            "codec-recipe-grid": (27048, 16688),
            "codec-grid-plus-control-families": (37192, 22944),
            "codec-grid-plus-control-recipes": (47332, 29204),
        }
        minimums = self.report[
            "arithmetic_minimums_across_unselected_options"
        ]
        for scenario_id, (dedicated, optimistic) in expected.items():
            values = {
                row["model_id"]: row
                for row in minimums
                if row["retention_rate"] == 0.90
                and row["scenario_id"] == scenario_id
            }
            self.assertEqual(
                values["dedicated_stratum"][
                    "enrolled_session_slots_four_partitions_one_device"
                ],
                dedicated,
            )
            self.assertEqual(
                values["optimistic_mushra_condition_packing"][
                    "enrolled_session_slots_four_partitions_one_device"
                ],
                optimistic,
            )
            self.assertTrue(
                all(
                    not value["option_selected"]
                    for value in values.values()
                )
            )
            self.assertTrue(
                all(
                    not value["session_timing_evaluated"]
                    for value in values.values()
                )
            )

    def test_committed_report_binds_current_plan_and_implementation(self):
        self.assertEqual(
            self.report["plan_sha256"], MODULE.sha256_file(MODULE.PLAN_PATH)
        )
        self.assertEqual(
            self.report["implementation_sha256"], MODULE.sha256_file(SCRIPT)
        )
        self.assertFalse(self.report["audio_accessed"])
        self.assertFalse(self.report["human_collection_performed"])
        self.assertFalse(
            self.report["decision"]["human_collection_authorized"]
        )
        self.assertFalse(
            self.report["decision"]["candidate_codec_grid_selected"]
        )
        self.assertFalse(
            self.report["decision"]["mushra_condition_packing_proven"]
        )


if __name__ == "__main__":
    unittest.main()
