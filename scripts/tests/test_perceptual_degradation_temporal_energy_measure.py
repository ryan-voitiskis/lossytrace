from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
import unittest
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_temporal_energy_measure.py"
EVIDENCE = ROOT / "research/toolchains/evidence/perceptual-degradation-temporal-energy-measure-synthetic-20260907-001.json"
SPEC = importlib.util.spec_from_file_location("temporal_energy_measure", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class TemporalEnergyMeasureTest(unittest.TestCase):
    def test_plan_and_predecessor_bytes_are_bound(self):
        self.assertEqual("temporal-energy-measure-20260907-001", M.load_plan()["plan_id"])
        with mock.patch.object(M, "sha", return_value="0" * 64), self.assertRaisesRegex(ValueError, "plan bytes"):
            M.load_plan()
        actual = M.sha
        with mock.patch.object(M, "sha", side_effect=lambda path: actual(path) if path == M.PLAN else "0" * 64), self.assertRaisesRegex(ValueError, "predecessor"):
            M.load_plan()

    def test_disk_reserve_exact_boundary(self):
        for free in (0, 15 * 1024**3 - 1):
            with mock.patch.object(M.shutil, "disk_usage", return_value=SimpleNamespace(free=free)), self.assertRaisesRegex(ValueError, "reserve"):
                M.profile_runs(M.profiles()[0], 48000)
        with mock.patch.object(M.shutil, "disk_usage", return_value=SimpleNamespace(free=15 * 1024**3)):
            M.reserve()

    def test_sample_rates_are_strict_positive_integers(self):
        for rate in (0, -1, True, 2.0, None, "48000"):
            with self.assertRaises(ValueError):
                M.measure_runs([(1, 1)], rate)
            with self.assertRaises(ValueError):
                M.measure_samples([1], rate)

    def test_samples_are_strict_signed_24_bit_integers(self):
        for value in (True, 1.0, None, "1", 2**23, -(2**23) - 1):
            with self.assertRaises(ValueError):
                M.measure_runs([(1, value)], 1)
            with self.assertRaises(ValueError):
                M.measure_samples([value], 1)
        for value in (-(2**23), 2**23 - 1):
            self.assertTrue(M.measure_samples([value], 1)["supported"])

    def test_invalid_run_shapes_lengths_and_lazy_inputs_are_rejected(self):
        for runs in (None, "1", iter([(1, 1)]), [(1,)], [(1, 1, 1)], ["11"], [(0, 1)], [(-1, 1)], [(True, 1)], [(1.0, 1)]):
            with self.assertRaises(ValueError):
                M.measure_runs(runs, 1)
        for samples in (None, "1", iter([1])):
            with self.assertRaises(ValueError):
                M.measure_samples(samples, 1)

    def test_empty_and_silence_are_unsupported_not_zero_spans(self):
        for samples, duration in (([], "0/1"), ([0] * 20, "10/1")):
            result = M.measure_samples(samples, 2)
            self.assertFalse(result["supported"])
            self.assertEqual(duration, result["recording_duration_seconds"])
            self.assertEqual("0/1", result["squared_integer_amplitude_exposure_seconds"])
            self.assertEqual("0/1", result["literal_nonzero_cell_duration_seconds"])
            self.assertTrue(all(value is None for value in result["quantile_times_seconds"].values()))
            for key in ("central_90_energy_span_seconds", "central_50_energy_span_seconds", "squared_sample_energy_centroid_seconds", "first_nonzero_cell_start_seconds", "last_nonzero_cell_end_seconds", "recording_relative_central_90_fraction"):
                self.assertIsNone(result[key])

    def test_closed_form_constant_pulse_in_seconds(self):
        result = M.measure_runs([(10, 0), (4, 7), (6, 0)], 2)
        self.assertEqual({"q05": "51/10", "q25": "11/2", "q50": "6/1", "q75": "13/2", "q95": "69/10"}, result["quantile_times_seconds"])
        self.assertEqual("9/5", result["central_90_energy_span_seconds"])
        self.assertEqual("1/1", result["central_50_energy_span_seconds"])
        self.assertEqual("6/1", result["squared_sample_energy_centroid_seconds"])
        self.assertEqual("98/1", result["squared_integer_amplitude_exposure_seconds"])
        self.assertEqual("2/1", result["literal_nonzero_cell_duration_seconds"])
        self.assertEqual("9/50", result["recording_relative_central_90_fraction"])

    def test_nonuniform_sample_cell_quantiles_and_centroid_are_exact(self):
        result = M.measure_samples([1, 2], 2)
        self.assertEqual({"q05": "1/8", "q25": "17/32", "q50": "11/16", "q75": "27/32", "q95": "31/32"}, result["quantile_times_seconds"])
        self.assertEqual("27/32", result["central_90_energy_span_seconds"])
        self.assertEqual("5/16", result["central_50_energy_span_seconds"])
        self.assertEqual("13/20", result["squared_sample_energy_centroid_seconds"])
        self.assertEqual("5/2", result["squared_integer_amplitude_exposure_seconds"])

    def test_plateau_quantile_uses_earliest_boundary(self):
        samples = [2, 0, 0, 2]
        result = M.measure_samples(samples, 1)
        self.assertEqual("1/1", result["quantile_times_seconds"]["q50"])
        self.assertEqual("2/1", result["squared_sample_energy_centroid_seconds"])
        self.assertEqual("19/5", result["central_90_energy_span_seconds"])
        self.assertEqual(result, M.dense_reference(samples, 1))

    def test_run_splitting_and_sample_adapter_preserve_every_field(self):
        runs = [(3, 0), (4, -7), (2, 2), (3, 0)]
        samples = [value for count, value in runs for _ in range(count)]
        original = copy.deepcopy(runs)
        expected = M.measure_runs(runs, 10)
        self.assertEqual(expected, M.measure_runs([(1, value) for value in samples], 10))
        self.assertEqual(expected, M.measure_samples(tuple(samples), 10))
        self.assertEqual(expected, M.dense_reference(samples, 10))
        self.assertEqual(original, runs)

    def test_signed_gain_changes_exposure_not_timing(self):
        samples = [0, 2, -1, 4, 0]
        base, scaled = [M.measure_samples([gain * value for value in samples], 5) for gain in (1, -2)]
        self.assertEqual(M.physical_view(base, include_exposure=False), M.physical_view(scaled, include_exposure=False))
        self.assertEqual(4 * Fraction(base["squared_integer_amplitude_exposure_seconds"]), Fraction(scaled["squared_integer_amplitude_exposure_seconds"]))

    def test_leading_zero_translation_shifts_times_not_spans(self):
        base = M.measure_samples([2, -1, 4], 5)
        shifted = M.measure_samples([0] * 10 + [2, -1, 4], 5)
        for key in M.QUANTILES:
            self.assertEqual(Fraction(base["quantile_times_seconds"][key]) + 2, Fraction(shifted["quantile_times_seconds"][key]))
        for key in ("squared_sample_energy_centroid_seconds", "first_nonzero_cell_start_seconds", "last_nonzero_cell_end_seconds"):
            self.assertEqual(Fraction(base[key]) + 2, Fraction(shifted[key]))
        for key in ("central_90_energy_span_seconds", "central_50_energy_span_seconds", "squared_integer_amplitude_exposure_seconds", "literal_nonzero_cell_duration_seconds"):
            self.assertEqual(base[key], shifted[key])

    def test_trailing_zeros_preserve_energy_times_but_change_context(self):
        base, padded = [M.measure_samples([2, -1, 4] + [0] * count, 5) for count in (0, 3)]
        changed = {key for key in base if base[key] != padded[key]}
        self.assertEqual({"recording_duration_seconds", "sample_count", "recording_relative_central_90_fraction"}, changed)
        self.assertEqual(Fraction(base["recording_relative_central_90_fraction"]) / 2, Fraction(padded["recording_relative_central_90_fraction"]))

    def test_exact_sample_cell_refinement_preserves_physical_measure(self):
        samples = [0, 2, -1, 4, 0]
        base = M.measure_samples(samples, 5)
        doubled = M.measure_samples([value for value in samples for _ in range(2)], 10)
        self.assertEqual(M.physical_view(base), M.physical_view(doubled))
        self.assertEqual(2 * base["sample_count"], doubled["sample_count"])

    def test_dense_numerical_core_does_not_call_run_or_sample_adapters(self):
        with mock.patch.object(M, "measure_runs", side_effect=AssertionError("run integration used")), mock.patch.object(M, "measure_samples", side_effect=AssertionError("adapter used")):
            result = M.dense_reference([1, 2], 2)
        self.assertEqual("13/20", result["squared_sample_energy_centroid_seconds"])
        self.assertEqual("11/16", result["quantile_times_seconds"]["q50"])

    def test_frozen_profile_inventory_gain_and_cell_boundaries(self):
        profiles = M.profiles()
        self.assertEqual(9, len(profiles))
        self.assertEqual(9, len({row["profile_id"] for row in profiles}))
        for gain in (0, 2, True, 1.0, None):
            with self.assertRaises(ValueError):
                M.profile_runs(profiles[0], 48000, gain)
        changed = copy.deepcopy(profiles[0])
        changed["duration"] = 31
        with self.assertRaises(ValueError):
            M.profile_runs(changed, 48000)
        with self.assertRaisesRegex(ValueError, "sample-cell boundaries"):
            M.profile_runs(profiles[0], 1)


class TemporalEnergyMeasureReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = M.build_report()
        cls.profiles = {row["synthetic_profile_id"]: row for row in cls.report["physical_profiles"]}

    def test_complete_report_replays_exactly(self):
        self.assertEqual(EVIDENCE.read_bytes(), M.canonical(self.report))
        self.assertEqual(36, self.report["native_rate_and_signed_gain_summaries_evaluated"])
        self.assertEqual(36, self.report["independent_dense_checks_passed"])
        self.assertTrue(self.report["technical_measure_definition_selected"])

    def test_all_profiles_rates_and_signed_gain_checks_are_retained(self):
        self.assertEqual(9, len(self.profiles))
        for profile in self.profiles.values():
            self.assertEqual([48000, 96000], [row["sample_rate_hz"] for row in profile["native_rate_views"]])
            self.assertEqual(4, profile["independent_dense_checks_passed"])
            self.assertTrue(profile["exact_density_refinement_identity"])
            for check in profile["signed_gain_checks"]:
                self.assertEqual(-2, check["gain"])
                self.assertTrue(check["temporal_and_context_fields_identical"])
                self.assertTrue(check["squared_amplitude_exposure_multiplied_by_four"])

    def test_consumed_context_witnesses_remain_distinct_from_time_span(self):
        identifiers = ["single-15-5.950", "single-15-6.000", "single-30-5.950", "single-30-6.000"]
        self.assertEqual([3, 2, 2, 1], [self.profiles[key]["consumed_legacy_analytic_occupancy"]["active_block_count"] for key in identifiers])
        self.assertEqual(["36/25"] * 4, [self.profiles[key]["native_rate_views"][0]["summary"]["central_90_energy_span_seconds"] for key in identifiers])
        for key in ("50_ms_translation_quantiles_shift_exactly", "exact_zero_append_preserves_temporal_measures", "zero_append_context_ratio_halves"):
            self.assertTrue(self.report["comparisons"][key])

    def test_separated_equal_support_has_different_energy_spread(self):
        comparison = self.report["comparisons"]["contiguous_vs_separated"]
        self.assertEqual({"contiguous": "8/5", "separated": "8/5"}, comparison["literal_nonzero_cell_duration_seconds"])
        self.assertEqual({"contiguous": "36/25", "separated": "316/25"}, comparison["central_90_energy_span_seconds"])
        result = self.profiles["separated-equal-intervals"]["native_rate_views"][0]["summary"]
        self.assertEqual("34/5", result["quantile_times_seconds"]["q50"])
        self.assertEqual("62/5", result["squared_sample_energy_centroid_seconds"])

    def test_positive_background_is_not_silently_discarded(self):
        expected = [(10, "720603/500000", "360639/250000"), (100, "7803/5000", "72729/5000")]
        for row, (amplitude, before, after) in zip(self.report["comparisons"]["positive_background_append"], expected, strict=True):
            self.assertEqual(amplitude, row["background_amplitude"])
            self.assertEqual(before, row["before_span_seconds"])
            self.assertEqual(after, row["after_span_seconds"])
            self.assertFalse(row["exact_zero_padding_invariance_applies"])
        result = self.profiles["background-100-30"]["native_rate_views"][0]["summary"]
        self.assertEqual("1029/50", result["quantile_times_seconds"]["q95"])
        self.assertEqual("30/1", result["literal_nonzero_cell_duration_seconds"])

    def test_claims_and_actual_execution_stay_closed(self):
        self.assertTrue(all(value is False for value in self.report["claim_boundary"].values()))
        for key in ("actual_audio_accessed", "generated_audio_retained", "perceptual_or_statistical_fit_executed"):
            self.assertIs(False, self.report[key])
        for marker in (b"/Users/", b".wav", b".flac", b"participant-", b"pcm_sha", b"encoded_sha"):
            self.assertNotIn(marker, M.canonical(self.report))

    def test_cli_cannot_open_inputs_or_tune_the_definition(self):
        for args in ([], ["--synthetic", "--input", "unopened.wav"], ["--synthetic", "--quantile", "0.1"]):
            execution = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True)
            self.assertNotEqual(0, execution.returncode)


if __name__ == "__main__":
    unittest.main()
