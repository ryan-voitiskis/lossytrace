from __future__ import annotations

import importlib
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts")) if str(ROOT / "scripts") not in sys.path else None
V3 = importlib.import_module("perceptual_degradation_alignment_v3")
RUNNER = importlib.import_module("perceptual_degradation_alignment_validity_successor")


class CorrelationValidityTest(unittest.TestCase):
    def test_valid_negative_one_is_not_an_invalid_sentinel(self):
        values = [1.0, -1.0] * 16
        result = V3.correlate(values, [-value for value in values], 0)
        self.assertAlmostEqual(-1.0, result.value)
        self.assertAlmostEqual(1.0, result.magnitude)
        self.assertIsNone(result.reason)

    def test_zero_energy_has_no_signed_or_absolute_value(self):
        for a, b in (([1.0] * 32, [0.0] * 32), ([0.0] * 32, [1.0] * 32), ([0.0] * 32, [0.0] * 32)):
            result = V3.correlate(a, b, 0)
            self.assertIsNone(result.value)
            self.assertIsNone(result.magnitude)
            self.assertEqual("zero_energy", result.reason)

    def test_constant_pearson_is_undefined_but_constant_cosine_is_defined(self):
        self.assertEqual("zero_centered_energy", V3.correlate([2.0] * 32, [3.0] * 32, 0, centered=True).reason)
        self.assertAlmostEqual(1.0, V3.correlate([2.0] * 32, [3.0] * 32, 0).value)

    def test_insufficient_overlap_is_not_a_competing_lag(self):
        values = [1.0, -1.0] * 16
        results = {0: V3.correlate(values, values, 0), 30: V3.correlate(values, values, 30)}
        self.assertEqual({0}, set(V3.valid_scores(results, magnitude=True)))
        self.assertEqual("insufficient_overlap", results[30].reason)
        self.assertEqual((0, None, None), V3._peak(V3.valid_scores(results, magnitude=True)))

    def test_empty_search_has_no_lag(self):
        self.assertEqual((None, None, None), V3._peak({}))
        self.assertEqual({}, V3.valid_scores({0: V3.Correlation(None, "zero_energy", 32, 32)}, magnitude=True))

    def test_peak_requires_a_real_alternative_and_neighbors(self):
        self.assertEqual((0, 0.0, None), V3._peak({-1: 0.5, 0: 1.0, 1: 0.5}))
        self.assertEqual((0, 0.0, 0.75), V3._peak({-2: 0.25, -1: 0.5, 0: 1.0, 1: 0.5}))

    def test_signed_coarse_order_is_distinct_from_magnitude_order(self):
        results = {0: V3.Correlation(-1.0, None, 32, 32), 1: V3.Correlation(0.5, None, 32, 32)}
        self.assertEqual(-1.0, V3.valid_scores(results, magnitude=False)[0])
        self.assertEqual(1.0, V3.valid_scores(results, magnitude=True)[0])

    def test_nonfinite_and_non_numeric_inputs_are_invalid(self):
        for value in (math.nan, math.inf, -math.inf, True, "1", 10**400):
            self.assertEqual("invalid_numeric_input", V3.correlate([value] * 32, [1.0] * 32, 0).reason)

    def test_extreme_finite_values_do_not_underflow_or_overflow(self):
        for scale in (1e-300, 1e300):
            values = [scale, -scale] * 16
            self.assertAlmostEqual(1.0, V3.correlate(values, values, 0).value)
            self.assertAlmostEqual(-1.0, V3.correlate(values, [-value for value in values], 0, centered=True).value)

    def test_closed_form_orthogonal_and_correlated_vectors(self):
        a, b = [1.0, 0.0] * 16, [0.0, 1.0] * 16
        self.assertEqual(0.0, V3.correlate(a, b, 0).value)
        c = [3 * x + y for x, y in zip(a, b, strict=True)]
        self.assertAlmostEqual(3 / math.sqrt(10), V3.correlate(a, c, 0).value)

    def test_invalid_correlation_cannot_contain_a_valid_number(self):
        for args in ((1.0, "zero_energy", 32, 32), (None, None, 32, 32), (math.nan, None, 32, 32), (1.1, None, 32, 32), (0.5, None, 1, 2), (True, None, 32, 32), (None, True, 32, 32), (0.0, None, 0, 0), (0.5, None, True, True)):
            with self.assertRaises(ValueError):
                V3.Correlation(*args)

    def test_local_silence_never_returns_global_lag_as_evidence(self):
        result = V3.local_lag([0.0] * 200, [0.0] * 200, 0, 100, 40, 5)
        self.assertIsNone(result["lag_samples"])
        self.assertIsNone(result["correlation"].magnitude)
        self.assertEqual(0, result["candidates"]["valid"])

    def test_missing_local_windows_do_not_fit_a_drift(self):
        for structural in (False, True):
            result = V3.window_audit([0.0] * 1200, [0.0] * 1200, 200, 0, structural=structural)
            self.assertEqual("incomplete_valid_windows", result["reason"])
            for key in ("clock_drift_ppm", "residual_samples", "minimum_correlation"):
                self.assertIsNone(result[key])

    def test_short_span_does_not_claim_perfect_drift_correlation(self):
        result = V3.window_audit([1.0] * 100, [1.0] * 100, 200, 0, structural=False)
        self.assertEqual("insufficient_window_span", result["reason"])
        self.assertIsNone(result["minimum_correlation"])

    def test_zero_fit_has_no_db_or_polarity(self):
        for a, b in (([1.0, 0.0] * 16, [0.0, 1.0] * 16), ([1.0] * 32, [0.0] * 32)):
            result = V3.gain_diagnostics(a, b)
            self.assertEqual(0.0, result["linear_gain"])
            self.assertIsNone(result["observed_gain_db"])
            self.assertIsNone(result["polarity"])
            self.assertEqual("zero_fitted_gain", result["reason"])

    def test_zero_reference_cannot_define_gain(self):
        self.assertEqual("zero_reference_energy", V3.gain_diagnostics([0.0] * 32, [1.0] * 32)["reason"])

    def test_valid_gain_retains_sign_and_scale(self):
        result = V3.gain_diagnostics([1.0, -1.0] * 16, [-0.5, 0.5] * 16)
        self.assertAlmostEqual(-0.5, result["linear_gain"])
        self.assertAlmostEqual(-6.020599913, result["observed_gain_db"])
        self.assertEqual("inverted", result["polarity"])

    def test_nonrepresentable_linear_gain_is_not_an_infinite_or_zero_sentinel(self):
        for a, b, expected_db in ((1e-300, 1e300, 12000.0), (1e300, 1e-300, -12000.0)):
            result = V3.gain_diagnostics([a] * 32, [b] * 32)
            self.assertIsNone(result["linear_gain"])
            self.assertEqual(expected_db, result["observed_gain_db"])
            self.assertEqual("linear_gain_not_representable", result["reason"])

    def test_incomplete_aggregate_is_null(self):
        self.assertIsNone(V3._complete([1.0, None], min))
        self.assertIsNone(V3._complete([], min))
        self.assertEqual(0.0, V3._complete([0.0, 1.0], min))


class AlignmentValiditySuccessorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = RUNNER.build_report()

    def test_all_declared_cases_retained(self):
        self.assertEqual(18, self.report["known_regression_case_count"])
        self.assertEqual(5, len(self.report["additional_alignment_cases"]))
        self.assertEqual(5, len(self.report["numeric_cases"]))

    def test_known_status_outcomes_are_preserved(self):
        self.assertEqual(15, self.report["known_regression_supported"])
        self.assertEqual(0, self.report["known_regression_status_changes"])

    def test_jointly_defined_diagnostics_match_prior_precision(self):
        for item in self.report["cases"]:
            comparison = item["defined_diagnostic_comparison"]
            self.assertLessEqual(float(comparison["maximum_absolute_difference_from_rounded_prior"]), 1e-8)
            self.assertEqual(12, comparison["jointly_defined_fields"] + comparison["unavailable_successor_fields"])

    def test_both_stereo_dropouts_have_null_common_summaries(self):
        cases = [item for item in self.report["cases"] if item["matrix_id"] == "right_channel_zero"]
        self.assertEqual(2, len(cases))
        for item in cases:
            result = item["successor"]
            self.assertEqual("unsupported", result["status"])
            self.assertEqual("1.000000000", item["old_minimum_correlation"])
            self.assertIsNone(result["summary"]["minimum_correlation"])
            self.assertIsNone(result["summary"]["clock_drift_ppm"])
            self.assertEqual("supported", result["channels"][0]["status"])
            self.assertIsNone(result["channels"][1]["correlation"])
            self.assertIn("no_valid_coarse_correlation", result["channels"][1]["reasons"])

    def test_valid_relative_polarity_still_has_signed_negative_correlation(self):
        for item in self.report["cases"]:
            if item["matrix_id"] == "right_polarity_inversion":
                right = item["successor"]["channels"][1]
                self.assertEqual("-1.000000000", right["correlation"]["value"])
                self.assertEqual("inverted", right["gain"]["polarity"])

    def test_silent_local_window_abstains_without_fabricated_drift(self):
        item = next(item for item in self.report["additional_alignment_cases"] if item["construction"] == "central_silent_window")
        result = item["successor"]
        self.assertIn("drift_windows_unavailable", result["reasons"])
        self.assertIn("structural_windows_unavailable", result["reasons"])
        self.assertIsNone(result["summary"]["clock_drift_ppm"])
        channel = result["channels"][0]
        self.assertEqual(4, channel["drift"]["valid_window_count"])
        self.assertEqual(6, channel["structural"]["valid_window_count"])

    def test_zero_constant_and_short_arrays_do_not_get_a_lag(self):
        for item in self.report["additional_alignment_cases"]:
            if item["construction"] != "central_silent_window":
                self.assertEqual("unsupported", item["successor"]["status"])
                self.assertIsNone(item["successor"]["summary"]["integer_delay_samples"])

    def test_no_oracle_integration_or_sample_correction(self):
        self.assertTrue(self.report["legacy_oracle_rejects_all_successor_records"])
        for item in self.report["cases"] + self.report["additional_alignment_cases"]:
            self.assertTrue(item["inputs_unchanged"])
            self.assertEqual("alignment record kind differs", item["successor"]["legacy_oracle_rejection"])
            for flag in ("public_verdict_enabled", "perceptual_claim", "sample_correction_applied"):
                self.assertFalse(item["successor"][flag])

    def test_bindings_and_authority_stay_closed(self):
        self.assertTrue(self.report["predecessor_files_unchanged"])
        self.assertTrue(all(value is False for value in self.report["claim_boundary"].values()))
        RUNNER.load_plan()

    def test_binding_mutation_fails_closed(self):
        with patch.object(RUNNER, "PLAN_SHA", "0" * 64), self.assertRaisesRegex(ValueError, "plan bytes"):
            RUNNER.load_plan()

    def test_reserve_fails_before_generation(self):
        with patch.object(RUNNER.fixtures.shutil, "disk_usage") as usage:
            usage.return_value.free = 15 * 1024**3 - 1
            with self.assertRaisesRegex(ValueError, "reserve"):
                RUNNER.build_report()

    def test_canonical_report_contains_no_nonfinite_numbers(self):
        encoded = RUNNER.fixtures.canonical(self.report)
        self.assertEqual(self.report, json.loads(encoded))
        self.assertNotIn(b"NaN", encoded)
        self.assertNotIn(b"Infinity", encoded)

    def test_committed_report_matches_complete_replay(self):
        path = ROOT / "research/toolchains/evidence/perceptual-degradation-alignment-validity-successor-synthetic-20260907-001.json"
        self.assertEqual(path.read_bytes(), RUNNER.fixtures.canonical(self.report))

    def test_cli_accepts_no_audio_input_route(self):
        result = subprocess.run([sys.executable, str(Path(RUNNER.__file__)), "--input", "undeclared.wav"], capture_output=True, text=True, check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", result.stdout)

    def test_configuration_is_strict(self):
        arguments = dict(reference_channels=[[1.0] * 32], test_channels=[[1.0] * 32], reference_channel_map=["M"], test_channel_map=["M"], sample_rate_hz=2000, recipe_identity="config")
        for key, value in (("sample_rate_hz", True), ("sample_rate_hz", 0), ("sample_rate_hz", 1.5), ("minimum_active_seconds", math.nan), ("maximum_delay_seconds", math.inf), ("maximum_delay_seconds", False), ("recipe_identity", "")):
            with self.assertRaises(ValueError):
                V3.align_channels(**{**arguments, key: value})

    def test_invalid_topology_has_no_common_estimates(self):
        result = V3.align_channels(reference_channels=[[1.0] * 32, [1.0] * 32], test_channels=[[1.0] * 32], reference_channel_map=["L", "R"], test_channel_map=["M"], sample_rate_hz=2000, recipe_identity="topology")
        self.assertIn("channel_topology_mismatch", result["support"]["reasons"])
        self.assertEqual([], result["alignment"]["channels"])
        self.assertTrue(all(value is None for value in result["alignment"]["summary"].values()))

    def test_invalid_numeric_channel_has_no_measurements(self):
        result = V3.align_channels(reference_channels=[[math.nan] * 32], test_channels=[[1.0] * 32], reference_channel_map=["M"], test_channel_map=["M"], sample_rate_hz=2000, recipe_identity="invalid")
        self.assertEqual(["invalid_numeric_input"], result["support"]["reasons"])
        self.assertIsNone(result["alignment"]["summary"]["minimum_correlation"])


if __name__ == "__main__":
    unittest.main()
