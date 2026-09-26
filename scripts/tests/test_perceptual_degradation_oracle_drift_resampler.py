import copy
import importlib.util
import math
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_oracle_drift_resampler.py"
SPEC = importlib.util.spec_from_file_location(
    "perceptual_degradation_oracle_drift_resampler", SCRIPT
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class OracleDriftResamplerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        cls.report = MODULE.load_json(MODULE.REPORT_PATH)
        cls.table = MODULE.coefficient_table(cls.plan["candidate"])

    def test_frozen_plan_validates(self):
        self.assertEqual(MODULE.validate_plan(self.plan), [])

    def test_binding_mutation_is_rejected(self):
        mutated = copy.deepcopy(self.plan)
        mutated["bindings"]["alignment_topology_freeze"]["sha256"] = "0" * 64
        self.assertIn(
            "binding alignment_topology_freeze sha256 differs",
            MODULE.validate_plan(mutated),
        )

    def test_coefficient_table_is_exactly_bound_and_dc_normalized(self):
        candidate = self.plan["candidate"]
        self.assertEqual(len(self.table), 2048)
        self.assertTrue(all(len(phase) == 128 for phase in self.table))
        self.assertTrue(all(sum(phase) == MODULE.Q30_ONE for phase in self.table))
        self.assertEqual(
            MODULE.sha256_bytes(MODULE.coefficient_table_bytes(self.table)),
            candidate["coefficient_table_sha256"],
        )

    def test_frequency_response_passes_predeclared_gates(self):
        response = self.report["frequency_response"]
        gates = self.plan["predeclared_gates"]
        self.assertLessEqual(
            response["passband_ripple_abs_db"],
            gates["maximum_passband_ripple_abs_db"],
        )
        self.assertLessEqual(
            response["stopband_maximum_db"],
            gates["maximum_stopband_magnitude_db"],
        )
        self.assertEqual(response["maximum_dc_coefficient_sum_error"], 0.0)

    def test_all_bounded_time_cases_pass_without_truth_assignment(self):
        gates = self.plan["predeclared_gates"]
        cases = self.report["time_domain_cases"]
        self.assertEqual(
            [case["correction_ppm"] for case in cases],
            [75, -60, 100, -100, 0],
        )
        for case in cases:
            self.assertEqual(case["output_frame_count"], 96000)
            self.assertFalse(case["retained_audio_accessed"])
            self.assertFalse(case["perceptual_truth_included"])
            for metric in case["channel_metrics"]:
                self.assertGreaterEqual(
                    metric["core_correlation"],
                    gates["minimum_core_correlation_each_channel"],
                )
                self.assertLessEqual(
                    abs(metric["core_gain_error_db"]),
                    gates["maximum_abs_core_gain_error_db_each_channel"],
                )
                self.assertLessEqual(
                    metric["core_maximum_absolute_error"],
                    gates["maximum_core_absolute_error_each_channel"],
                )

    def test_zero_drift_is_bit_exact_identity_without_edge_discard(self):
        identity = self.report["time_domain_cases"][-1]
        self.assertEqual(identity["correction_ppm"], 0)
        self.assertFalse(identity["correction_applied"])
        self.assertTrue(identity["identity_bypass_used"])
        self.assertTrue(identity["identity_output_bit_exact"])
        self.assertEqual(identity["mandatory_discard_frames_each_edge"], 0)
        self.assertEqual(
            identity["input_f64le_sha256"], identity["output_f64le_sha256"]
        )

    def test_applied_corrections_require_frozen_edge_discard(self):
        expected = self.plan["candidate"][
            "mandatory_discard_frames_each_edge_when_applied"
        ]
        for case in self.report["time_domain_cases"][:-1]:
            self.assertTrue(case["correction_applied"])
            self.assertFalse(case["identity_bypass_used"])
            self.assertEqual(case["mandatory_discard_frames_each_edge"], expected)

    def test_stereo_processing_has_shared_grid_and_zero_leakage(self):
        isolation = self.report["stereo_isolation"]
        self.assertEqual(isolation["input_channel_count"], 2)
        self.assertEqual(isolation["output_channel_count"], 2)
        self.assertTrue(isolation["shared_position_grid"])
        self.assertEqual(isolation["maximum_zero_channel_leakage"], 0.0)

    def test_correction_limit_and_invalid_numeric_input_fail_closed(self):
        candidate = self.plan["candidate"]
        with self.assertRaisesRegex(ValueError, "exceeds frozen ppm limit"):
            MODULE.resample_channel(
                [0.0] * 256,
                output_frames=256,
                correction_ppm=101,
                candidate=candidate,
                table=self.table,
            )
        with self.assertRaisesRegex(ValueError, "non-finite"):
            MODULE.resample_channel(
                [0.0, math.nan] + [0.0] * 254,
                output_frames=256,
                correction_ppm=75,
                candidate=candidate,
                table=self.table,
            )
        with self.assertRaisesRegex(ValueError, "channel shape differs"):
            MODULE.resample_channels(
                [[0.0] * 256, [0.0] * 255],
                output_frames=256,
                correction_ppm=75,
                candidate=candidate,
                table=self.table,
            )

    def test_golden_vector_replays_exactly_in_current_environment(self):
        self.assertEqual(
            MODULE.golden_vector(self.plan, self.table),
            self.report["golden_vector"],
        )

    def test_disk_reserve_is_fail_closed(self):
        with mock.patch.object(
            MODULE.shutil,
            "disk_usage",
            return_value=mock.Mock(free=15 * 1024**3 - 1),
        ):
            with self.assertRaisesRegex(ValueError, "below 15 GiB reserve"):
                MODULE.require_disk_reserve(ROOT, 15)

    def test_report_is_hash_bound_replayed_and_fail_closed(self):
        self.assertEqual(
            self.report["freeze_sha256"], MODULE.sha256_file(MODULE.PLAN_PATH)
        )
        self.assertEqual(
            self.report["implementation_sha256"], MODULE.sha256_file(SCRIPT)
        )
        replay = self.report["replay_observation"]
        self.assertEqual(replay["fresh_temporary_replay_count"], 2)
        self.assertTrue(replay["byte_identical"])
        self.assertEqual(len(set(replay["payload_sha256s"])), 1)
        self.assertEqual(MODULE.validate_report(self.report), [])
        mutated = copy.deepcopy(self.report)
        mutated["gate_audit"]["stopband_magnitude"] = False
        self.assertIn(
            "predeclared gates did not all pass", MODULE.validate_report(mutated)
        )

    def test_selection_closes_only_the_technical_resampler_gate(self):
        decision = self.report["decision"]
        self.assertTrue(decision["candidate_selected_as_frozen_oracle_resampler"])
        self.assertTrue(decision["bounded_drift_correction_technical_path_ready"])
        self.assertFalse(decision["retained_audio_correction_executed"])
        self.assertFalse(decision["retained_audio_correction_validated"])
        self.assertFalse(decision["human_or_perceptual_validity_present"])
        self.assertFalse(decision["full_reference_oracle_validated"])
        self.assertFalse(decision["human_collection_authorized"])
        self.assertFalse(decision["no_reference_work_eligible"])
        self.assertFalse(decision["public_verdict_enabled"])


if __name__ == "__main__":
    unittest.main()
