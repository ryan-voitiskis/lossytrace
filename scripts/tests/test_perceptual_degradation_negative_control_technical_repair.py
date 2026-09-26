import copy
import importlib.util
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts/perceptual_degradation_negative_control_technical_repair.py"
)
SPEC = importlib.util.spec_from_file_location(
    "perceptual_degradation_negative_control_technical_repair", SCRIPT
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class NegativeControlTechnicalRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.load_json(MODULE.REPORT_PATH)

    def test_frozen_plan_validates(self):
        self.assertEqual(MODULE.validate_plan(self.plan), [])

    def test_binding_mutation_is_rejected(self):
        mutated = copy.deepcopy(self.plan)
        mutated["bindings"]["alignment_fixture_freeze"]["sha256"] = "0" * 64
        self.assertIn(
            "binding alignment_fixture_freeze sha256 differs",
            MODULE.validate_plan(mutated),
        )

    def test_isolated_dither_is_deterministic_bounded_and_shape_preserving(self):
        samples = [-30000, -1, 0, 1, 30000] * 100
        candidate = self.plan["isolated_dither_candidate"]
        first, first_histogram = MODULE.apply_isolated_dither(
            samples,
            seed_prefix=candidate["seed_prefix"],
            recipe_id=candidate["recipe_id"],
        )
        second, second_histogram = MODULE.apply_isolated_dither(
            samples,
            seed_prefix=candidate["seed_prefix"],
            recipe_id=candidate["recipe_id"],
        )
        self.assertEqual(first, second)
        self.assertEqual(first_histogram, second_histogram)
        self.assertEqual(len(first), len(samples))
        self.assertEqual(set(first_histogram), {-1, 0, 1})
        self.assertTrue(all(value > 0 for value in first_histogram.values()))
        self.assertTrue(
            all(abs(output - source) <= 1 for source, output in zip(samples, first))
        )

    def test_dither_replay_is_not_requantization_or_perceptual_truth(self):
        case = self.report["isolated_dither_case"]
        self.assertEqual(case["noise_minimum_lsb"], -1)
        self.assertEqual(case["noise_maximum_lsb"], 1)
        self.assertFalse(case["bit_depth_change"])
        self.assertTrue(case["frame_shape_preserved"])
        self.assertGreater(case["changed_sample_count"], 0)
        self.assertFalse(case["perceptual_truth_included"])

    def test_sample_rate_conversion_binds_new_tool_and_preserves_geometry(self):
        case = self.report["sample_rate_conversion_case"]
        candidate = self.plan["sample_rate_conversion_candidate"]
        self.assertEqual(case["tool_binary_sha256"], candidate["tool"]["binary_sha256"])
        self.assertEqual(case["source_sample_rate_hz"], 48000)
        self.assertEqual(case["intermediate_sample_rate_hz"], 32000)
        self.assertEqual(case["output_sample_rate_hz"], 48000)
        self.assertEqual(case["input_frame_count"], 96000)
        self.assertEqual(case["intermediate_frame_count"], 64000)
        self.assertEqual(case["output_frame_count"], 96000)
        self.assertTrue(case["input_output_differ"])
        self.assertTrue(case["output_geometry_preserved"])
        self.assertFalse(case["dither_applied"])
        self.assertFalse(case["normalization_applied"])
        self.assertFalse(case["historical_ffmpeg_binding_reused"])
        self.assertFalse(case["perceptual_truth_included"])

    def test_ffmpeg_successor_rejects_binary_hash_drift(self):
        candidate = copy.deepcopy(self.plan["sample_rate_conversion_candidate"])
        candidate["tool"]["binary_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "binary hash differs"):
            MODULE.verify_bound_ffmpeg(candidate)

    def test_bounded_drift_selection_uses_disjoint_held_out_windows(self):
        rows = self.report["bounded_clock_drift_cases"]
        self.assertEqual([row["actual_drift_ppm"] for row in rows], [75, -60, 0])
        for row in rows:
            self.assertEqual(
                row["selected_correction_ppm"], row["actual_drift_ppm"]
            )
            self.assertFalse(row["selection_used_held_out_windows"])
            self.assertFalse(row["fixture_interpolator_is_frozen_oracle_resampler"])
            self.assertFalse(row["production_resampler_executed"])
            self.assertFalse(row["perceptual_truth_included"])
            if row["actual_drift_ppm"]:
                self.assertTrue(row["apply_correction"])
                self.assertGreaterEqual(
                    row["held_out_mean_correlation_after"], 0.99
                )
                self.assertGreaterEqual(
                    row["held_out_mean_correlation_improvement"], 0.05
                )
            else:
                self.assertFalse(row["apply_correction"])
                self.assertEqual(
                    row["held_out_mean_correlation_improvement"], 0.0
                )

    def test_drift_replay_is_deterministic(self):
        candidate = self.plan["bounded_clock_drift_candidate"]
        first = MODULE.replay_drift_case(candidate, 75)
        second = MODULE.replay_drift_case(candidate, 75)
        self.assertEqual(first, second)
        self.assertEqual(first["selected_correction_ppm"], 75)
        self.assertTrue(first["apply_correction"])

    def test_paired_edge_silence_exercises_support_and_abstention(self):
        rows = {
            row["case_id"]: row
            for row in self.report["paired_edge_silence_cases"]
        }
        supported = rows["supported-paired-edges"]
        self.assertEqual(supported["alignment_status"], "supported")
        self.assertEqual(supported["alignment_reason_codes"], [])
        self.assertEqual(supported["reported_total_edge_trim_seconds"], 1.0)
        over = rows["over-limit-paired-edges"]
        self.assertEqual(over["alignment_status"], "unsupported")
        self.assertIn("excessive_trim", over["alignment_reason_codes"])
        self.assertEqual(over["reported_total_edge_trim_seconds"], 2.4)
        for row in rows.values():
            self.assertTrue(row["leading_edge_exact_zero"])
            self.assertTrue(row["trailing_edge_exact_zero"])
            self.assertEqual(
                row["reported_total_edge_trim_seconds"],
                row["expected_total_edge_silence_seconds"],
            )
            self.assertFalse(row["perceptual_truth_included"])

    def test_disk_reserve_is_fail_closed(self):
        with mock.patch.object(
            MODULE.shutil,
            "disk_usage",
            return_value=mock.Mock(free=15 * 1024**3 - 1),
        ):
            with self.assertRaisesRegex(ValueError, "below 15 GiB reserve"):
                MODULE.require_disk_reserve(ROOT, 15)

    def test_committed_report_is_hash_bound_and_byte_identical(self):
        self.assertEqual(
            self.report["plan_sha256"], MODULE.sha256_file(MODULE.PLAN_PATH)
        )
        self.assertEqual(
            self.report["implementation_sha256"], MODULE.sha256_file(SCRIPT)
        )
        replay = self.report["replay_observation"]
        self.assertEqual(replay["fresh_temporary_replay_count"], 2)
        self.assertTrue(replay["byte_identical"])
        self.assertEqual(len(set(replay["payload_sha256s"])), 1)
        self.assertFalse(replay["paths_included"])
        self.assertFalse(replay["timing_included"])
        self.assertEqual(MODULE.validate_report(self.report), [])

    def test_report_keeps_scientific_and_collection_gates_closed(self):
        summary = self.report["summary"]
        self.assertFalse(summary["actual_audio_accessed"])
        self.assertFalse(summary["perceptual_metric_executed"])
        self.assertFalse(summary["perceptual_truth_included"])
        self.assertFalse(summary["listener_response_collected"])
        self.assertFalse(summary["condition_selected"])
        decision = self.report["decision"]
        self.assertFalse(decision["production_oracle_resampler_selected"])
        self.assertFalse(decision["retained_audio_correction_validated"])
        self.assertFalse(decision["perceptual_condition_selected"])
        self.assertFalse(decision["human_truth_present"])
        self.assertFalse(decision["negative_class_scientific_coverage_complete"])
        self.assertFalse(decision["human_collection_authorized"])
        self.assertFalse(decision["no_reference_work_eligible"])
        self.assertFalse(decision["public_verdict_enabled"])


if __name__ == "__main__":
    unittest.main()
