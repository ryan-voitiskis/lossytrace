from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_listening_feasibility.py"
PLAN = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/listening-feasibility-frontier-plan.json"
)
EVIDENCE = (
    ROOT
    / "research/toolchains/evidence/perceptual-degradation-listening-feasibility-frontier-20260813-001.json"
)
SPEC = importlib.util.spec_from_file_location("listening_feasibility", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ListeningFeasibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = json.loads(PLAN.read_text(encoding="utf-8"))
        cls.report = MODULE.build_report(cls.plan)

    def test_plan_is_score_blind_and_all_bound_files_match(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))
        authorization = self.plan["authorization"]
        self.assertTrue(authorization["score_blind_analytic_planning_only"])
        for key, value in authorization.items():
            if key != "score_blind_analytic_planning_only":
                self.assertFalse(value, key)

    def test_odaq_16_source_path_cannot_reach_equivalence_target(self) -> None:
        odqa = self.report["odaq_narrow_path"]
        self.assertEqual(16, odqa["independent_source_groups"])
        self.assertAlmostEqual(0.0353439413, odqa["asymptotic_maximum_equivalence_power"])
        self.assertFalse(odqa["target_attainable_under_frozen_model"])
        self.assertFalse(odqa["transparent_truth_supported"])
        for row in self.report["frontier_rows"]:
            if row["source_groups"] == 16:
                self.assertIsNone(row["minimum_eligible_listeners"])
                self.assertFalse(row["target_power_attainable_with_finite_listeners"])

    def test_asymptotic_source_floor_is_exactly_39_groups(self) -> None:
        frontier = self.report["source_frontier"]
        self.assertEqual(
            39,
            frontier[
                "minimum_source_groups_per_independent_partition_for_asymptotic_80_percent_equivalence_power"
            ],
        )
        self.assertLess(frontier["source_groups_38_asymptotic_power"], 0.8)
        self.assertGreater(frontier["source_groups_39_asymptotic_power"], 0.8)

    def test_finite_frontier_rewards_sources_and_trials_without_relaxing_target(self) -> None:
        def row(source_groups: int, trials: int) -> dict:
            return next(
                item
                for item in self.report["frontier_rows"]
                if item["source_groups"] == source_groups
                and item["transparent_trials_per_eligible_listener"] == trials
            )

        self.assertGreater(
            row(64, 5)["minimum_eligible_listeners"],
            row(120, 5)["minimum_eligible_listeners"],
        )
        self.assertGreater(
            row(120, 5)["minimum_eligible_listeners"],
            row(120, 15)["minimum_eligible_listeners"],
        )
        for item in (row(64, 5), row(120, 5), row(120, 15)):
            self.assertGreaterEqual(item["equivalence_power"], 0.8)

    def test_analytic_power_agrees_with_original_monte_carlo_stress_design(self) -> None:
        value = copy.deepcopy(self.plan)
        value["score_blind_stress_assumptions"][
            "usable_trial_rate_after_missingness"
        ] = 1.0
        standard_error = MODULE.audibility_standard_error(
            value,
            probability=0.5,
            eligible_listeners=240,
            source_groups=120,
            trials_per_listener=15,
        )
        analytic = MODULE.equivalence_power(
            value, estimate_truth=0.5, standard_error=standard_error
        )
        original = json.loads(
            (
                ROOT
                / "research/toolchains/evidence/perceptual-degradation-listening-power-simulation-20260803-001.json"
            ).read_text(encoding="utf-8")
        )["decision"]["maximum_stress_equivalence_power"]
        self.assertAlmostEqual(original, analytic, delta=0.015)

    def test_attrition_and_missingness_increase_required_enrollment(self) -> None:
        stressed = MODULE.frontier_row(
            self.plan, source_groups=120, trials_per_listener=5
        )
        ideal = copy.deepcopy(self.plan)
        ideal["score_blind_stress_assumptions"][
            "eligible_listener_retention_rate"
        ] = 1.0
        ideal["score_blind_stress_assumptions"][
            "usable_trial_rate_after_missingness"
        ] = 1.0
        ideal_row = MODULE.frontier_row(
            ideal, source_groups=120, trials_per_listener=5
        )
        self.assertGreater(
            stressed["minimum_eligible_listeners"],
            ideal_row["minimum_eligible_listeners"],
        )
        self.assertGreater(
            stressed["minimum_enrolled_listener_slots"],
            stressed["minimum_eligible_listeners"],
        )

    def test_mushra_trial_count_never_exceeds_protocol_cap(self) -> None:
        for row in self.report["frontier_rows"]:
            self.assertLessEqual(
                row["mushra_trials_per_eligible_listener_assumed"], 6
            )
        fifteen = next(
            item
            for item in self.report["frontier_rows"]
            if item["source_groups"] == 120
            and item["transparent_trials_per_eligible_listener"] == 15
        )
        self.assertEqual(6, fifteen["mushra_trials_per_eligible_listener_assumed"])

    def test_bridge_mapping_uncertainty_is_visible_and_reduces_power(self) -> None:
        row = self.report["reference_workload_sensitivity"]["row"]
        powers = [
            item["power"]
            for item in row[
                "mapped_severity_power_by_mapping_standard_error"
            ]
        ]
        self.assertEqual(powers, sorted(powers, reverse=True))
        self.assertGreater(powers[0], powers[-1])
        self.assertIn("bridge_direct_joint_power_lower_bound", row)

    def test_device_classes_are_separate_and_double_listener_slots(self) -> None:
        device = self.report["reference_workload_sensitivity"][
            "device_class_workload"
        ]
        self.assertEqual([1, 2], [item["device_class_count"] for item in device])
        self.assertFalse(device[0]["pooled_generalization"])
        self.assertEqual(
            2
            * device[0][
                "minimum_enrolled_listener_slots_at_reference_120_source_5_trial_design"
            ],
            device[1][
                "minimum_enrolled_listener_slots_at_reference_120_source_5_trial_design"
            ],
        )

    def test_grouped_partitions_do_not_reuse_source_groups(self) -> None:
        partitions = self.report["source_frontier"]["partition_requirements"]
        self.assertEqual(
            [(1, 39), (3, 117), (4, 156)],
            [
                (
                    item["partition_count"],
                    item["asymptotic_minimum_unique_source_groups"],
                )
                for item in partitions
            ],
        )

    def test_report_remains_non_authorizing_and_no_reference_ineligible(self) -> None:
        self.assertEqual([], MODULE.validate_report(self.report))
        decision = self.report["decision"]
        self.assertFalse(decision["listener_count_frozen"])
        self.assertFalse(decision["source_manifest_frozen"])
        self.assertFalse(decision["operational_design_frozen"])
        self.assertFalse(decision["main_collection_authorized"])
        self.assertFalse(decision["no_reference_work_eligible"])
        self.assertFalse(self.report["public_verdict_enabled"])

    def test_report_is_byte_deterministic_and_matches_committed_evidence(self) -> None:
        first = MODULE._json_bytes(MODULE.build_report(copy.deepcopy(self.plan)))
        second = MODULE._json_bytes(MODULE.build_report(copy.deepcopy(self.plan)))
        self.assertEqual(first, second)
        self.assertEqual(first, EVIDENCE.read_bytes())
        self.assertEqual(
            hashlib.sha256(PLAN.read_bytes()).hexdigest(),
            self.report["analysis_plan_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
            self.report["implementation_sha256"],
        )

    def test_bound_hash_drift_fails_closed(self) -> None:
        value = copy.deepcopy(self.plan)
        value["bindings"]["research_contract"]["sha256"] = "0" * 64
        self.assertIn(
            "bound file hash differs: research_contract",
            MODULE.validate_plan(value),
        )

    def test_cli_has_only_bound_planning_input_and_refuses_overwrite(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn('add_argument("--responses"', source)
        self.assertNotIn('add_argument("--audio"', source)
        self.assertNotIn('add_argument("--manifest"', source)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "frontier.json"
            first = subprocess.run(
                ["python3", str(SCRIPT), "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, first.returncode, first.stderr)
            second = subprocess.run(
                ["python3", str(SCRIPT), "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(0, second.returncode)
            self.assertIn("refusing to replace output", second.stderr)


if __name__ == "__main__":
    unittest.main()
