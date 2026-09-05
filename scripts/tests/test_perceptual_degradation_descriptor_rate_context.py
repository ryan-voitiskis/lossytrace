from __future__ import annotations

import cmath
import copy
import importlib.util
import json
import math
import subprocess
import sys
import unittest
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_descriptor_rate_context.py"
EVIDENCE = ROOT / "research/toolchains/evidence/perceptual-degradation-descriptor-rate-context-synthetic-20260905-001.json"
SPEC = importlib.util.spec_from_file_location("descriptor_rate_context", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class DescriptorRateContextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = M.load_engine()
        cls.tone = M.master_period("single_tone")

    def test_plan_and_predecessor_bytes_are_bound(self):
        with mock.patch.object(M, "sha", return_value="0" * 64), self.assertRaisesRegex(ValueError, "plan bytes"):
            M.load_plan()
        actual = M.sha
        with mock.patch.object(M, "sha", side_effect=lambda path: actual(path) if path == M.PLAN else "0" * 64), self.assertRaisesRegex(ValueError, "predecessor"):
            M.load_plan()

    def test_disk_reserve_is_enforced_including_exact_boundary(self):
        for free in (0, 15 * 1024**3 - 1):
            with mock.patch.object(M.shutil, "disk_usage", return_value=SimpleNamespace(free=free)), self.assertRaisesRegex(ValueError, "reserve"):
                M.reserve()
        with mock.patch.object(M.shutil, "disk_usage", return_value=SimpleNamespace(free=15 * 1024**3)):
            M.reserve()

    def test_tone_is_the_same_1500_hz_function_at_shared_sample_times(self):
        kernels = {rate: M.kernel(self.tone, rate) for rate in M.RATES}
        self.assertEqual(3, len(M.shared_grid_checks(kernels)))
        for rate, samples in kernels.items():
            self.assertEqual(rate * 128 // 1000, len(samples))
            for n in (0, 1, 31, 128, 1023):
                self.assertEqual(round(8192 * math.cos(2 * math.pi * 1500 * n / rate)), samples[n])

    def test_coherent_construction_has_declared_peak_and_integer_range(self):
        period = M.master_period("coherent_full_band")
        self.assertEqual(511 * 8192, period[0])
        self.assertEqual(-8192, period[2048])
        self.assertTrue(all(type(value) is int and -(2**23) <= value < 2**23 for value in period))

    def test_corrupted_shared_grid_fails(self):
        kernels = {rate: M.kernel(self.tone, rate) for rate in M.RATES}
        kernels[48000][1] += 1
        with self.assertRaisesRegex(ValueError, "identity"):
            M.shared_grid_checks(kernels)

    def test_unknown_families_rates_and_periods_fail(self):
        for family in (None, True, [], "replacement"):
            with self.assertRaises(ValueError):
                M.master_period(family)
        for rate in (True, 48000.0, 44100, None):
            with self.assertRaises(ValueError):
                M.kernel(self.tone, rate)
            with self.assertRaises(ValueError):
                M.rate_geometry(rate)
        for period in ([], [True] * 4096, [2**23] * 4096, tuple(self.tone)):
            with self.assertRaises(ValueError):
                M.kernel(period, 48000)

    def test_fft_physical_units_change_with_native_rate(self):
        for rate in M.RATES:
            geometry = M.rate_geometry(rate)
            self.assertEqual(Fraction(1024, rate), Fraction(geometry["fft_window_seconds"]))
            self.assertEqual(Fraction(rate, 1024), Fraction(geometry["bin_spacing_hz"]))
            self.assertEqual(Fraction(511 * rate, 1024), Fraction(geometry["highest_included_bin_hz"]))
        self.assertIs(False, M.rate_geometry(192000)["capture_permitted_rate"])

    def test_bound_fft_matches_direct_dft_for_complex_values(self):
        values = [complex(index - 3, index % 3 - 1) for index in range(8)]
        expected = [sum(value * cmath.exp(-2j * math.pi * k * n / len(values)) for n, value in enumerate(values)) for k in range(len(values))]
        for actual, reference in zip(self.engine._fft(values), expected, strict=True):
            self.assertAlmostEqual(actual.real, reference.real, places=9)
            self.assertAlmostEqual(actual.imag, reference.imag, places=9)

    def test_tonal_control_retains_its_frozen_class_at_every_rate(self):
        for rate in M.RATES:
            descriptor = self.engine.classify(M.kernel(self.tone, rate))
            self.assertIs(True, descriptor["tonal_non_sparse_contrast"])
            self.assertIs(False, descriptor["spectral_concentration"]["non_tonal"])

    def test_context_counts_match_literal_time_interval_overlap(self):
        expected = {(15, "5.950"): (3, [Fraction(1, 30), Fraction(1), Fraction(1, 30)]),
                    (15, "6.000"): (2, [Fraction(1), Fraction(1, 15)]),
                    (30, "5.950"): (2, [Fraction(1, 31), Fraction(1)]),
                    (30, "6.000"): (1, [Fraction(1)])}
        for rate in (48000, 96000):
            for (duration, onset), (count, nonzero_powers) in expected.items():
                analytic = M.analytic_occupancy(rate, duration, onset)
                self.assertEqual(count, analytic["active_block_count"])
                self.assertEqual(nonzero_powers, [Fraction(value) for value in analytic["relative_block_powers"] if Fraction(value)])
                self.assertEqual(count <= 2, analytic["sparse"])

    def test_contexts_keep_duration_of_nonzero_event_and_quiet_requirements(self):
        for rate in (48000, 96000):
            for duration in (15, 30):
                for onset in ("5.950", "6.000"):
                    count, start, end = M.context_parameters(rate, duration, onset)
                    self.assertEqual(Fraction(8, 5), Fraction(end - start, rate))
                    self.assertGreaterEqual(start, 5 * rate)
                    self.assertGreaterEqual(count - end, 5 * rate)

    def test_undeclared_context_variants_are_rejected(self):
        for args in ((44100, 15, "5.950"), (48000.0, 15, "5.950"), (48000, 15.0, "5.950"), (48000, 16, "5.950"), (48000, 15, "5.951"), (48000, 15, None)):
            with self.assertRaises(ValueError):
                M.context_parameters(*args)

    def test_kernel_construction_does_not_mutate_the_common_period(self):
        before = copy.deepcopy(self.tone)
        for rate in M.RATES:
            M.kernel(self.tone, rate)
        self.assertEqual(before, self.tone)


class DescriptorRateContextReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = M.build_report()

    def test_full_replay_matches_all_declared_evidence(self):
        self.assertEqual(EVIDENCE.read_bytes(), M.canonical(self.report))
        constructions = self.report["rate_audit"]["kernel_constructions"]
        self.assertEqual(4, len(constructions))
        self.assertEqual(12, sum(len(item["native_rate_results"]) for item in constructions))
        self.assertTrue(all(check["all_shared_samples_identical"] for item in constructions for check in item["shared_grid_checks"]))
        self.assertEqual(8, len(self.report["context_audit"]["occupancy_only_constructions"]))

    def test_frozen_observed_rate_counterexample_is_retained(self):
        padded = self.report["rate_audit"]["padded_coherent_kernel"]
        first, second = padded["native_rate_results"]
        self.assertIs(True, first["descriptor"]["sparse_non_tonal_contrast"])
        self.assertIs(True, second["descriptor"]["abstain"])
        self.assertTrue(padded["changes_from_48000_hz"][0]["contrast_class_changed"])
        for row in padded["native_rate_results"]:
            self.assertIs(False, row["eligible_natural_capture"])

    def test_counterexamples_do_not_silently_replace_coherent_kernel_results(self):
        coherent = self.report["rate_audit"]["kernel_constructions"][0]
        self.assertEqual("coherent_full_band", coherent["synthetic_construction"])
        self.assertTrue(all(row["descriptor"]["spectral_concentration"]["tonal"] for row in coherent["native_rate_results"]))

    def test_context_counterexamples_and_exact_checks_are_retained(self):
        context = self.report["context_audit"]
        self.assertTrue(all(row["exact_overlap_check_passed"] for row in context["occupancy_only_constructions"]))
        self.assertEqual(4, len(context["comparisons"]))
        self.assertTrue(all(row["sparse_flag_changed"] and row["event_samples_unchanged"] for row in context["comparisons"]))

    def test_no_source_truth_reclassification_or_execution_gate_opens(self):
        self.assertTrue(all(value is False for value in self.report["claim_boundary"].values()))
        for key in ("generated_audio_retained", "actual_audio_accessed", "statistical_fits_or_perceptual_metrics_executed"):
            self.assertIs(False, self.report[key])
        for marker in (b"/Users/", b".wav", b".flac", b"participant-", b"pcm_sha", b"encoded_sha"):
            self.assertNotIn(marker, M.canonical(self.report))

    def test_cli_has_no_actual_input_or_tuning_options(self):
        for args in ([], ["--synthetic", "--input", "unopened.wav"], ["--synthetic", "--rate", "48000"]):
            result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True)
            self.assertNotEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
