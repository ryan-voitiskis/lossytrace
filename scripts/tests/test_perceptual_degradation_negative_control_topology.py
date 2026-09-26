import copy
import importlib.util
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_negative_control_topology.py"
SPEC = importlib.util.spec_from_file_location(
    "perceptual_degradation_negative_control_topology", SCRIPT
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class NegativeControlTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.load_json(MODULE.REPORT_PATH)

    def test_frozen_plan_validates(self):
        self.assertEqual(MODULE.validate_plan(self.plan), [])

    def test_binding_mutation_is_rejected(self):
        mutated = copy.deepcopy(self.plan)
        mutated["bindings"]["research_plan"]["sha256"] = "0" * 64
        self.assertIn(
            "binding research_plan sha256 differs",
            MODULE.validate_plan(mutated),
        )

    def test_twenty_required_classes_are_partitioned_exactly_once(self):
        audit = self.report["required_inventory_audit"]
        self.assertEqual(audit["required_class_count"], 20)
        self.assertEqual(
            audit["axis_class_counts"],
            {
                "transparent_truth_axis": 1,
                "source_trait_axis": 7,
                "alignment_nuisance_axis": 7,
                "human_truth_production_axis": 5,
            },
        )
        self.assertTrue(audit["all_required_classes_accounted_once"])
        self.assertFalse(audit["source_traits_are_condition_strata"])
        self.assertFalse(audit["scientific_coverage_complete"])

    def test_source_traits_keep_missing_and_confounded_candidates_visible(self):
        audit = self.report["source_trait_axis_audit"]
        self.assertEqual(audit["class_count"], 7)
        self.assertEqual(audit["candidate_record_present_class_count"], 5)
        self.assertEqual(audit["unique_candidate_record_count"], 4)
        self.assertEqual(
            audit["missing_explicit_candidate_classes"], ["quiet", "clipped"]
        )
        self.assertTrue(audit["joint_sparse_tonal_candidate"])
        self.assertFalse(audit["source_trait_scientific_coverage_complete"])
        by_class = {row["class_id"]: row for row in audit["rows"]}
        self.assertEqual(
            by_class["sparse"]["candidate_ids"],
            by_class["tonal"]["candidate_ids"],
        )
        self.assertTrue(
            all(not row["exact_members_frozen"] for row in audit["rows"])
        )

    def test_production_axis_does_not_promote_partial_recipe_inventory(self):
        audit = self.report["human_truth_production_axis_audit"]
        self.assertEqual(audit["class_count"], 5)
        self.assertEqual(audit["candidate_record_present_class_count"], 5)
        self.assertEqual(
            audit["synthetic_perceptual_recipe_replayed_class_count"], 3
        )
        self.assertEqual(audit["human_truth_class_count"], 0)
        by_class = {row["class_id"]: row for row in audit["rows"]}
        self.assertFalse(by_class["dither"]["isolated_condition_ready"])
        self.assertFalse(
            by_class["sample_rate_conversion"]["isolated_condition_ready"]
        )
        self.assertTrue(
            all(not row["condition_selected"] for row in audit["rows"])
        )

    def test_alignment_axis_exposes_incomplete_correction_plumbing(self):
        audit = self.report["alignment_nuisance_axis_audit"]
        self.assertEqual(audit["class_count"], 7)
        self.assertEqual(audit["technical_representation_present_count"], 7)
        self.assertEqual(
            audit["known_incomplete_correction_or_fixture_classes"],
            [
                "bounded_clock_drift",
                "leading_trailing_silence",
                "resampling",
            ],
        )
        self.assertFalse(audit["alignment_nuisance_role_complete"])
        self.assertTrue(
            all(
                not row["listening_condition_role_frozen"]
                for row in audit["rows"]
            )
        )

    def test_non_substitution_rules_preserve_natural_and_production_roles(self):
        rules = "\n".join(self.report["non_substitution_rules"])
        self.assertIn(
            "generated low-pass transform does not satisfy", rules
        )
        self.assertIn(
            "production hard-clipping recipe does not satisfy", rules
        )
        self.assertIn(
            "Dither combined with a 12-bit requantization does not establish",
            rules,
        )
        self.assertIn(
            "deterministic resampler used for alignment or metric views",
            rules,
        )
        self.assertFalse(
            self.report["additional_condition_inventory_audit"][
                "production_clipping_substitutes_for_clipped_reference"
            ]
        )

    def test_predecessor_arithmetic_is_reproduced_exactly(self):
        reproduction = self.report["workload_arithmetic_reproduction"]
        self.assertEqual(reproduction["scenario_count"], 2)
        self.assertEqual(reproduction["minimum_row_count"], 18)
        self.assertTrue(reproduction["all_minimums_reproduced_exactly"])

    def test_corrected_workload_cross_product_and_rounding(self):
        rows = self.report["condition_breadth_workload_rows"]
        self.assertEqual(len(rows), 3 * 4 * 6)
        self.assertEqual(
            len(self.report["arithmetic_minimums_across_unselected_options"]),
            3 * 6 * 3,
        )
        row = next(
            value
            for value in rows
            if value["retention_rate"] == 0.90
            and value["option_id"] == "sources120-subtle3-mushra3"
            and value["scenario_id"]
            == "codec-plus-required-and-extra-families"
        )
        self.assertEqual(row["strata_count"], 24)
        self.assertEqual(
            row["session_stratum_memberships_per_partition_device"],
            row["issued_eligible_prefix_per_stratum"] * 24,
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

    def test_ninety_percent_corrected_scale_points_are_stable(self):
        expected = {
            "codec-plus-required-production-families": (35500, 21904),
            "codec-plus-required-and-extra-families": (40572, 25028),
            "codec-plus-required-and-extra-recipes": (50716, 31284),
            "required-families-plus-alignment-human-truth": (47332, 29204),
            "extra-families-plus-alignment-human-truth": (52404, 32332),
            "extra-recipes-plus-alignment-human-truth": (62548, 38584),
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
                all(not value["option_selected"] for value in values.values())
            )

    def test_report_binds_current_plan_and_implementation_fail_closed(self):
        self.assertEqual(
            self.report["plan_sha256"], MODULE.sha256_file(MODULE.PLAN_PATH)
        )
        self.assertEqual(
            self.report["implementation_sha256"], MODULE.sha256_file(SCRIPT)
        )
        self.assertEqual(MODULE.validate_report(self.report), [])
        self.assertFalse(self.report["audio_accessed"])
        self.assertFalse(self.report["human_collection_performed"])
        decision = self.report["decision"]
        self.assertEqual(
            decision[
                "candidate_or_technical_representation_present_class_count"
            ],
            18,
        )
        self.assertFalse(decision["negative_class_scientific_coverage_complete"])
        self.assertFalse(decision["condition_breadth_selected"])
        self.assertFalse(decision["human_collection_authorized"])
        self.assertFalse(decision["no_reference_work_eligible"])


if __name__ == "__main__":
    unittest.main()
