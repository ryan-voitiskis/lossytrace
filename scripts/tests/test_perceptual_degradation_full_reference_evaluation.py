from __future__ import annotations

import copy
import importlib.util
import math
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts"
    / "perceptual_degradation_full_reference_evaluation.py"
)
SPEC = importlib.util.spec_from_file_location(
    "perceptual_degradation_full_reference_evaluation", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PerceptualDegradationFullReferenceEvaluationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = MODULE.synthetic_records()
        cls.evaluation = MODULE.evaluate(
            cls.records,
            primary_domains=["synthetic_music_a", "synthetic_music_b"],
        )
        cls.replay = MODULE.build_synthetic_replay(cls.evaluation)

    def evaluate_fast(self, records: list[dict]) -> dict:
        with mock.patch.object(MODULE, "BOOTSTRAP_REPLICATES", 200):
            return MODULE.evaluate(
                records,
                primary_domains=["synthetic_music_a", "synthetic_music_b"],
                bootstrap_replicates=200,
            )

    def test_tie_aware_ranks_spearman_and_auc(self) -> None:
        self.assertEqual([1.5, 1.5, 3.0, 4.0], MODULE.average_ranks([1.0, 1.0, 2.0, 3.0]))
        self.assertAlmostEqual(1.0, MODULE.spearman([1, 1, 2], [10, 10, 20]))
        self.assertAlmostEqual(
            0.875,
            MODULE.roc_auc([False, True, False, True], [0.1, 0.2, 0.2, 0.3]),
        )
        self.assertIsNone(MODULE.roc_auc([True, True], [0.1, 0.9]))

    def test_ece_uses_frozen_equal_width_boundary_policy(self) -> None:
        labels = [False, True, True]
        probabilities = [0.0, 0.1, 1.0]
        self.assertAlmostEqual(
            (0.0 + 0.9 + 0.0) / 3.0,
            MODULE.expected_calibration_error(labels, probabilities),
        )

    def test_hash_bootstrap_is_deterministic_and_keeps_groups_atomic(self) -> None:
        by_group: dict[str, list[dict]] = {}
        for record in self.records[:8]:
            by_group.setdefault(record["source_group_id"], []).append(record)
        group_ids = sorted(by_group)
        first = MODULE._resampled_records(by_group, group_ids, 7, "test-seed")
        second = MODULE._resampled_records(by_group, group_ids, 7, "test-seed")
        self.assertEqual(first, second)
        counts: dict[str, int] = {}
        for record in first:
            counts[record["source_group_id"]] = counts.get(record["source_group_id"], 0) + 1
        self.assertTrue(all(count % 2 == 0 for count in counts.values()))
        self.assertEqual(len(self.records[:8]), len(first))

    def test_evaluation_is_input_order_invariant(self) -> None:
        forward = self.evaluate_fast(copy.deepcopy(self.records))
        reverse = self.evaluate_fast(list(reversed(copy.deepcopy(self.records))))
        self.assertEqual(forward, reverse)

    def test_boundary_guard_is_conservative_when_bootstrap_is_degenerate(self) -> None:
        transparent = self.evaluation["transparent_material_rate"]
        material = self.evaluation["material_sensitivity"]
        self.assertEqual(0.0, transparent["upper_one_sided_95"])
        self.assertGreater(transparent["gate_upper_one_sided_95"], 0.0)
        self.assertLessEqual(transparent["gate_upper_one_sided_95"], 0.10)
        self.assertEqual(1.0, material["lower_one_sided_95"])
        self.assertLess(material["gate_lower_one_sided_95"], 1.0)
        self.assertGreaterEqual(material["gate_lower_one_sided_95"], 0.80)
        zero_lower, zero_upper = MODULE.wilson_bounds(0, 40)
        all_lower, all_upper = MODULE.wilson_bounds(40, 40)
        self.assertEqual(0.0, zero_lower)
        self.assertAlmostEqual(transparent["gate_upper_one_sided_95"], zero_upper)
        self.assertAlmostEqual(material["gate_lower_one_sided_95"], all_lower)
        self.assertEqual(1.0, all_upper)

    def test_all_statistical_gates_pass_only_for_synthetic_plumbing(self) -> None:
        gates = self.evaluation["gate_results"]
        self.assertTrue(gates["all_statistical_gates_pass"])
        self.assertFalse(self.replay["scientific_gate_evaluated"])
        self.assertFalse(self.replay["claim_boundary"]["full_reference_gate_passed"])
        self.assertFalse(self.replay["claim_boundary"]["no_reference_work_eligible"])
        self.assertEqual([], MODULE.validate_synthetic_replay(self.replay))
        diagnostics = self.evaluation["diagnostic_views"]
        self.assertEqual(set(MODULE.DIAGNOSTIC_AXES), set(diagnostics))
        self.assertIn("transparent_candidate", diagnostics["bitrate_region"])
        self.assertIn("transparent", diagnostics["human_truth_stratum"])
        self.assertIn("material", diagnostics["human_truth_stratum"])

    def test_one_transparent_alert_fails_conservative_safety(self) -> None:
        records = copy.deepcopy(self.records)
        transparent = next(record for record in records if record["human_transparent"])
        transparent["oracle"]["materially_degraded"] = True
        result = self.evaluate_fast(records)
        self.assertLessEqual(result["transparent_material_rate"]["point"], 0.05)
        self.assertGreater(result["transparent_material_rate"]["gate_upper_one_sided_95"], 0.10)
        self.assertFalse(result["gate_results"]["transparent_safety"])

    def test_coverage_reversal_and_added_value_fail_independently(self) -> None:
        coverage_records = copy.deepcopy(self.records)
        for record in coverage_records[:32]:
            record["oracle"] = {
                "supported": False,
                "severity": None,
                "audibility_probability": None,
                "materially_degraded": None,
            }
        coverage = self.evaluate_fast(coverage_records)
        self.assertFalse(coverage["gate_results"]["coverage"])

        reversal_records = copy.deepcopy(self.records)
        for record in reversal_records:
            if record["codec_stratum"] == "synthetic_codec_0":
                record["oracle"]["severity"] = 100.0 - record["human_severity"]
        reversal = self.evaluate_fast(reversal_records)
        self.assertIn(
            "codec_stratum:synthetic_codec_0",
            reversal["subgroup_reversal"]["reversed_strata"],
        )
        self.assertFalse(reversal["gate_results"]["no_subgroup_reversal"])

        added_value_records = copy.deepcopy(self.records)
        for record in added_value_records:
            for baseline_id in MODULE.BASELINE_IDS:
                record[baseline_id] = copy.deepcopy(record["oracle"])
        added_value = self.evaluate_fast(added_value_records)
        self.assertFalse(added_value["gate_results"]["added_value"])

    def test_invalid_bootstrap_fraction_fails_auc_gate(self) -> None:
        records = copy.deepcopy(self.records)
        for record in records:
            record["human_audible"] = False
            record["human_material"] = False
        result = self.evaluate_fast(records)
        self.assertEqual(0.0, result["audibility"]["roc_auc"]["valid_fraction"])
        self.assertFalse(result["audibility"]["roc_auc"]["validity_gate_passes"])
        self.assertFalse(result["gate_results"]["audibility_calibration"])

    def test_input_validation_rejects_metadata_leakage_and_unsupported_values(self) -> None:
        records = copy.deepcopy(self.records)
        records[0]["case_id"] = "/Users/example/private.wav"
        records[0]["primary_domain"] = "private/domain"
        records[0]["human_severity"] = math.nan
        records[1]["human_material"] = True
        records[1]["human_audible"] = False
        records[1]["partition_group_id"] = "partition-group-" + "f" * 64
        records[0]["oracle"] = {
            "supported": False,
            "severity": 1.0,
            "audibility_probability": None,
            "materially_degraded": None,
        }
        errors = MODULE.validate_records(records)
        self.assertIn("case identity differs: 0", errors)
        self.assertIn("stratum differs: 0:primary_domain", errors)
        self.assertIn("human severity differs: 0", errors)
        self.assertIn("material label lacks audibility: 1", errors)
        self.assertIn("source group crosses partition groups", errors)
        self.assertIn("unsupported prediction contains values: 0:oracle", errors)
        self.assertIn("evaluation records contain a private path", errors)

    def test_evaluator_has_no_real_score_opening_command(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn('add_parser("evaluate")', source)
        self.assertNotIn('add_parser("live")', source)
        self.assertNotIn('add_parser("open-scores")', source)

    def test_numeric_gates_match_frozen_research_plan(self) -> None:
        research_plan = MODULE.load_json(MODULE.RESEARCH_PLAN)
        self.assertEqual(
            MODULE.GATES,
            MODULE.research_plan_gate_projection(research_plan),
        )
        self.assertEqual(
            MODULE.BOOTSTRAP_REPLICATES,
            research_plan["full_reference_gates"]["bootstrap_replicates_min"],
        )

    def test_primary_domain_list_must_be_exact_and_sufficient(self) -> None:
        with mock.patch.object(MODULE, "BOOTSTRAP_REPLICATES", 200):
            with self.assertRaisesRegex(ValueError, "primary domains differ"):
                MODULE.evaluate(
                    self.records,
                    primary_domains=["synthetic_music_a"],
                    bootstrap_replicates=200,
                )
            with self.assertRaisesRegex(
                ValueError, "primary domain has insufficient source groups"
            ):
                MODULE.evaluate(
                    self.records[:14] + self.records[40:],
                    primary_domains=["synthetic_music_a", "synthetic_music_b"],
                    bootstrap_replicates=200,
                )

    def test_committed_replay_and_plan_validate(self) -> None:
        committed = MODULE.load_json(MODULE.REPLAY)
        self.assertEqual(MODULE.canonical_bytes(self.replay), MODULE.REPLAY.read_bytes())
        self.assertEqual([], MODULE.validate_synthetic_replay(committed))
        self.assertEqual([], MODULE.validate_plan(MODULE.load_json(MODULE.PLAN)))


if __name__ == "__main__":
    unittest.main()
