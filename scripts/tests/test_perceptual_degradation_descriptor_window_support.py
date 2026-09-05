from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_descriptor_window_support.py"
EVIDENCE = ROOT / "research/toolchains/evidence/perceptual-degradation-descriptor-window-support-synthetic-20260905-001.json"
SPEC = importlib.util.spec_from_file_location("descriptor_window_support", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def expand(encoded):
    labels = []
    for run in encoded:
        if run["start_origin_inclusive"] != len(labels):
            raise AssertionError("origin gap or overlap")
        labels.extend([run["class"]] * (run["end_origin_exclusive"] - run["start_origin_inclusive"]))
    return labels


class DescriptorWindowSupportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = M.load_predecessor().load_engine()

    def test_plan_and_predecessor_bytes_are_bound(self):
        with mock.patch.object(M, "sha", return_value="0" * 64), self.assertRaisesRegex(ValueError, "plan bytes"):
            M.load_plan()
        actual = M.sha
        with mock.patch.object(M, "sha", side_effect=lambda path: actual(path) if path == M.PLAN else "0" * 64), self.assertRaisesRegex(ValueError, "predecessor"):
            M.load_plan()

    def test_disk_reserve_exact_boundary(self):
        for free in (0, 15 * 1024**3 - 1):
            with mock.patch.object(M.shutil, "disk_usage", return_value=SimpleNamespace(free=free)), self.assertRaisesRegex(ValueError, "reserve"):
                M.period(M.FAMILIES[0])
        with mock.patch.object(M.shutil, "disk_usage", return_value=SimpleNamespace(free=15 * 1024**3)):
            M.reserve()

    def test_declared_exact_integer_periods(self):
        coherent, impulse, tone = [M.period(family) for family in M.FAMILIES]
        self.assertEqual(511 * 8192, coherent[0])
        self.assertEqual(511, coherent.count(-8192))
        self.assertEqual(512, coherent.count(0))
        self.assertEqual(1, sum(v != 0 for v in impulse))
        self.assertEqual([1048576, 0, -1048576, 0] * 256, tone)
        for values in (coherent, impulse, tone):
            self.assertEqual(1024, len(values))
            self.assertTrue(all(type(v) is int and -(2**23) <= v < 2**23 for v in values))

    def test_unknown_family_is_rejected(self):
        for family in (None, True, [], "new"):
            with self.assertRaises(ValueError):
                M.period(family)
        with self.assertRaises(ValueError):
            M.expected_dft("new")

    def test_rotations_preserve_samples_and_exact_energy(self):
        values = M.period(M.FAMILIES[0])
        original = copy.deepcopy(values)
        expected_energy = sum(v * v for v in values)
        for origin in range(1024):
            rotated = M.rotate(values, origin)
            self.assertEqual((values * 2)[origin:origin + 1024], rotated)
            self.assertEqual(expected_energy, sum(v * v for v in rotated))
        self.assertEqual(original, values)

    def test_invalid_periods_origins_and_inventories_are_rejected(self):
        values = M.period(M.FAMILIES[0])
        for origin in (-1, 1024, True, 1.0, None):
            with self.assertRaises(ValueError):
                M.rotate(values, origin)
            with self.assertRaises(ValueError):
                M.inventory(origin, 11)
        for invalid in ([], [True] * 1024, [2**23] * 1024, tuple(values)):
            with self.assertRaises(ValueError):
                M.rotate(invalid, 0)
        for count in (10, 13, 11.0, True, None):
            with self.assertRaises(ValueError):
                M.inventory(0, count)

    def test_all_frame_inventories_fit_the_same_fixed_record(self):
        values = M.period(M.FAMILIES[0])
        record = values * 8
        for origin in range(1024):
            for count in (11, 12):
                expanded = [index for index, n in M.inventory(origin, count) for _ in range(n)]
                expected = [(origin + j * 512) % 1024 for j in range(count)]
                self.assertEqual(sorted(expected), sorted(expanded))
                self.assertLessEqual(origin + 1024 + (count - 1) * 512, len(record))
        self.assertEqual(((0, 6), (512, 5)), M.inventory(0, 11))
        self.assertEqual(((512, 6), (0, 6)), M.inventory(512, 12))

    def test_closed_form_dfts_are_checked_for_all_bins(self):
        for family in M.FAMILIES:
            self.assertTrue(M.analytic_check(self.engine, family, M.period(family))["passed"])
        with self.assertRaisesRegex(ValueError, "DFT"):
            M.analytic_check(self.engine, M.FAMILIES[0], [0] * 1024)

    def test_zero_band_energy_is_not_spectral_support(self):
        self.assertIsNone(M.spectral_values([0.0] * 511))
        self.assertEqual((1.0, 8 / 511), M.spectral_values([1.0] * 511))

    def test_support_and_class_boundaries_keep_indeterminate_separate(self):
        self.assertEqual("unsupported", M.result(1.0, 0.02, 2, 1.0)["class"])
        self.assertEqual("tonal", M.result(0.1, 0.6, 3, 1.0)["class"])
        self.assertEqual("non_tonal", M.result(0.5, 0.2, 3, 1.0)["class"])
        self.assertEqual("indeterminate", M.result(0.49, 0.2, 3, 1.0)["class"])
        self.assertIsNone(M.result(None, None, 0, 0.0)["spectral_flatness"])

    def test_empty_spectral_frames_stay_unsupported_in_every_method(self):
        zero = {"raw_power": 1.0, "band_energy": 0.0, "powers": [0.0] * 511, "spectral": None}
        results = M.summarize(self.engine, [zero] * 1024, 0, 11)
        self.assertTrue(all(row["class"] == "unsupported" for row in results.values()))
        self.assertTrue(all(row["contributing_frame_count"] == 0 for row in results.values()))

    def test_legacy_crosscheck_rejects_changed_support_or_features(self):
        observed = M.result(1.0, 0.02, 5, 1.0)
        expected = {"supported": True, "active_frame_count": 5,
                    "median_spectral_flatness": "1.000000000", "median_top_8_bin_power_share": "0.020000000",
                    "tonal": False, "non_tonal": True}
        M.compare_legacy(expected, observed)
        for key, value in (("contributing_frame_count", 4), ("spectral_flatness", "0.999999999")):
            changed = copy.deepcopy(observed)
            changed[key] = value
            with self.assertRaisesRegex(ValueError, "cross-check"):
                M.compare_legacy(expected, changed)

    def test_run_encoding_covers_each_origin_once(self):
        labels = ["tonal"] * 17 + ["indeterminate"] * 10 + ["non_tonal"] * 997
        self.assertEqual(labels, expand(M.runs(labels)))
        for invalid in (labels[:-1], labels + ["tonal"], ["unknown"] * 1024):
            with self.assertRaises(ValueError):
                M.runs(invalid)


class DescriptorWindowSupportReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = M.build_report()

    def test_complete_report_replays_exactly(self):
        self.assertEqual(EVIDENCE.read_bytes(), M.canonical(self.report))
        self.assertEqual(6144, self.report["origin_inventory_family_cases"])
        self.assertEqual(18432, self.report["method_summaries_evaluated"])
        self.assertEqual(48, self.report["unchanged_descriptor_crosschecks_passed"])
        self.assertTrue(self.report["consumed_coherent_development_period_identity_verified"])

    def test_every_origin_and_method_is_retained_not_cherry_picked(self):
        for family in self.report["families"]:
            self.assertEqual(1024, family["unique_rotated_frames_checked"])
            self.assertEqual(16, family["unchanged_descriptor_crosschecks_passed"])
            for inv in family["inventories"]:
                for method in M.METHODS:
                    summary = inv["methods"][method]
                    labels = expand(summary["complete_origin_class_runs"])
                    self.assertEqual(1024, len(labels))
                    self.assertEqual({key: labels.count(key) for key in M.CLASSES}, summary["class_counts"])
                    self.assertEqual(sum(label != labels[0] for label in labels), summary["different_class_from_origin_zero_count"])

    def test_coherent_origin_and_inventory_effects_are_preserved(self):
        coherent = self.report["families"][0]
        self.assertEqual({"tonal": 47, "non_tonal": 899, "indeterminate": 78, "unsupported": 0}, coherent["inventories"][0]["methods"][M.METHODS[0]]["class_counts"])
        self.assertEqual(172, coherent["changed_class_between_11_and_12_frames"][M.METHODS[0]])
        ledger = {(row["frame_count"], row["origin_samples"]): row for row in coherent["coherent_mechanism_ledgers"]}
        self.assertEqual("tonal", ledger[(11, 0)]["methods"][M.METHODS[0]]["class"])
        self.assertEqual("non_tonal", ledger[(11, 512)]["methods"][M.METHODS[0]]["class"])
        self.assertEqual("indeterminate", ledger[(12, 0)]["methods"][M.METHODS[0]]["class"])
        self.assertGreater(float(ledger[(11, 0)]["methods"][M.METHODS[1]]["retained_analyzed_band_energy_fraction"]), 0.9997)

    def test_energy_admission_does_not_become_an_automatic_success(self):
        coherent = self.report["families"][0]
        counts = coherent["inventories"][0]["methods"][M.METHODS[1]]["class_counts"]
        self.assertEqual(20, counts["indeterminate"])
        self.assertEqual(20, coherent["changed_class_between_11_and_12_frames"][M.METHODS[1]])
        self.assertEqual(1024, coherent["inventories"][0]["methods"][M.METHODS[2]]["class_counts"]["non_tonal"])

    def test_impulse_and_exact_tone_controls_retain_all_outcomes(self):
        for family, expected in zip(self.report["families"][1:], ("non_tonal", "tonal"), strict=True):
            self.assertTrue(all(value == 0 for value in family["changed_class_between_11_and_12_frames"].values()))
            for inv in family["inventories"]:
                self.assertTrue(all(summary["class_counts"][expected] == 1024 for summary in inv["methods"].values()))

    def test_claims_and_actual_execution_stay_closed(self):
        self.assertTrue(all(value is False for value in self.report["claim_boundary"].values()))
        for key in ("actual_audio_accessed", "generated_audio_retained", "statistical_fits_or_perceptual_metrics_executed", "independent_scientific_validation_claimed"):
            self.assertIs(False, self.report[key])
        for marker in (b"/Users/", b".wav", b".flac", b"participant-", b"pcm_sha", b"encoded_sha"):
            self.assertNotIn(marker, M.canonical(self.report))

    def test_cli_cannot_open_inputs_or_tune_the_grid(self):
        for args in ([], ["--synthetic", "--input", "unopened.wav"], ["--synthetic", "--origin", "0"]):
            execution = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True)
            self.assertNotEqual(0, execution.returncode)


if __name__ == "__main__":
    unittest.main()
