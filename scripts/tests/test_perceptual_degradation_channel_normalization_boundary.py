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
SCRIPT = ROOT / "scripts/perceptual_degradation_channel_normalization_boundary.py"
EVIDENCE = ROOT / "research/toolchains/evidence/perceptual-degradation-channel-normalization-boundary-synthetic-20260907-001.json"
SPEC = importlib.util.spec_from_file_location("channel_normalization_boundary", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class ChannelNormalizationBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.plan = M.load_plan()
        self.reference = [[4, 0], [0, 4]]

    def result(self, name):
        coefficients = M.matrix(self.plan, name)
        return M.projections(self.reference, M.transform(self.reference, coefficients), coefficients)

    def test_plan_and_every_predecessor_are_byte_bound(self):
        with mock.patch.object(M, "sha", return_value="0" * 64), self.assertRaisesRegex(ValueError, "plan bytes"):
            M.load_plan()
        actual = M.sha
        with mock.patch.object(M, "sha", side_effect=lambda path: actual(path) if path == M.PLAN else "0" * 64), self.assertRaisesRegex(ValueError, "predecessor"):
            M.load_plan()

    def test_disk_reserve_exact_boundary(self):
        for free in (0, 15 * 1024**3 - 1):
            with mock.patch.object(M.shutil, "disk_usage", return_value=SimpleNamespace(free=free)), self.assertRaisesRegex(ValueError, "reserve"):
                M.fixture(M.FAMILIES[0])
        with mock.patch.object(M.shutil, "disk_usage", return_value=SimpleNamespace(free=15 * 1024**3)):
            M.reserve()

    def test_families_have_the_declared_exact_gram_relationships(self):
        orthogonal = M.fixture(M.FAMILIES[0])
        correlated = M.fixture(M.FAMILIES[1])
        self.assertEqual([12000, 12000], [len(channel) for channel in orthogonal])
        r = M.gram(orthogonal)
        self.assertGreater(r[0][0], 0)
        self.assertEqual([[r[0][0], 0], [0, r[0][0]]], r)
        c = M.gram(correlated)
        self.assertEqual(r[0][0], c[0][0])
        self.assertEqual(Fraction(3, 4) * r[0][0], c[0][1])
        self.assertEqual(Fraction(5, 8) * r[0][0], c[1][1])
        self.assertEqual(orthogonal[0], correlated[0])

    def test_unknown_family_or_matrix_is_rejected(self):
        for family in (None, True, [], "new"):
            with self.assertRaises(ValueError):
                M.fixture(family)
        with self.assertRaises(ValueError):
            M.matrix(self.plan, "new")

    def test_explicit_stereo_integer_shape_is_required(self):
        for channels in (None, [], [[1]], [[1], []], [[1], [1, 2]], [(1,), [1]], [[True], [1]], [[1.0], [1]], [[2**23], [1]], [[-(2**23) - 1], [1]]):
            with self.assertRaises(ValueError):
                M.validate_channels(channels)
        M.validate_channels([[-(2**23)], [2**23 - 1]])

    def test_transform_validates_matrix_and_exact_integer_output(self):
        for coefficients in (None, [], [[1, 0]], [[1, 0], [0]], [[True, 0], [0, 1]], [[1.0, 0], [0, 1]]):
            with self.assertRaises(ValueError):
                M.transform(self.reference, coefficients)
        with self.assertRaisesRegex(ValueError, "integer sample"):
            M.transform([[1], [1]], [[Fraction(1, 2), 0], [0, 1]])
        with self.assertRaisesRegex(ValueError, "24-bit"):
            M.transform([[2**22], [1]], [[2, 0], [0, 1]])

    def test_transform_and_projection_preserve_inputs(self):
        original = copy.deepcopy(self.reference)
        coefficients = M.matrix(self.plan, "mid_to_dual_mono")
        test = M.transform(self.reference, coefficients)
        preserved = copy.deepcopy(test)
        M.projections(self.reference, test, coefficients)
        self.assertEqual(original, self.reference)
        self.assertEqual(preserved, test)

    def test_common_gain_and_common_inversion_have_zero_projected_residual(self):
        for name, gain, raw in (("identity", "1/1", "0/1"), ("common_half_gain", "1/2", "1/4"), ("common_polarity_inversion", "-1/1", "4/1")):
            result = self.result(name)
            self.assertEqual(gain, result["common_signed_gain"])
            self.assertEqual({"unaltered": raw, "common_signed_gain": "0/1", "independent_signed_gains": "0/1"}, result["reference_normalized_squared_residuals"])

    def test_independent_gain_projection_discards_channel_imbalance(self):
        result = self.result("left_half_gain")
        self.assertEqual("3/4", result["common_signed_gain"])
        self.assertEqual(["1/2", "1/1"], result["independent_signed_gains"])
        self.assertEqual({"unaltered": "1/8", "common_signed_gain": "1/16", "independent_signed_gains": "0/1"}, result["reference_normalized_squared_residuals"])

    def test_opposite_polarities_can_have_zero_common_fit_without_inversion(self):
        result = self.result("right_polarity_inversion")
        self.assertEqual("0/1", result["common_signed_gain"])
        self.assertTrue(result["zero_fitted_gain_is_not_inverted"])
        self.assertEqual({"unaltered": "2/1", "common_signed_gain": "1/1", "independent_signed_gains": "0/1"}, result["reference_normalized_squared_residuals"])

    def test_dropout_degeneracy_is_not_a_fidelity_pass(self):
        result = self.result("right_channel_zero")
        self.assertEqual(["1/1", "0/1"], result["independent_signed_gains"])
        self.assertEqual("0/1", result["reference_normalized_squared_residuals"]["independent_signed_gains"])
        self.assertEqual("0/1", result["test_channel_geometry"]["right_energy_share"])
        self.assertEqual("1/2", result["reference_normalized_squared_residuals"]["unaltered"])

    def test_dual_mono_removes_side_energy_but_not_all_projection_residual(self):
        result = self.result("mid_to_dual_mono")
        self.assertEqual("1/2", result["reference_channel_geometry"]["side_energy_share"])
        self.assertEqual("0/1", result["test_channel_geometry"]["side_energy_share"])
        self.assertEqual("1/4", result["reference_normalized_squared_residuals"]["independent_signed_gains"])

    def test_gram_geometry_is_not_complete_channel_identity(self):
        result = self.result("channel_swap_same_declared_map")
        self.assertEqual(result["reference_channel_geometry"], result["test_channel_geometry"])
        self.assertEqual("2/1", result["reference_normalized_squared_residuals"]["unaltered"])

    def test_zero_pair_geometry_is_null_and_zero_reference_is_rejected(self):
        self.assertTrue(all(value is None for value in M.geometry([[0, 0], [0, 0]]).values()))
        with self.assertRaisesRegex(ValueError, "no energy"):
            M.projections([[1, 1], [0, 0]], [[1, 1], [0, 0]], [[1, 0], [0, 1]])
        with self.assertRaisesRegex(ValueError, "timebase"):
            M.projections(self.reference, [[1], [1]], [[1, 0], [0, 1]])

    def test_matrix_gram_check_rejects_a_mismatched_intervention(self):
        with self.assertRaisesRegex(ValueError, "Gram identity"):
            M.projections(self.reference, self.reference, [[Fraction(1, 2), 0], [0, 1]])

    def test_finite_formatting_and_negative_zero_are_canonical(self):
        self.assertEqual("0.000000000", M.formatted(-1e-12))
        for value in (float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                M.formatted(value)

    def test_oracle_validation_failure_is_preserved_not_repaired(self):
        oracle = SimpleNamespace(assemble_score_free=mock.Mock(side_effect=ValueError("synthetic validation failure")))
        result = M.oracle_projection(oracle, {})
        self.assertEqual("rejected", result["assembly"])
        self.assertEqual("synthetic validation failure", result["validation_error"])
        self.assertFalse(result["perceptual_claim"])


class ChannelNormalizationBoundaryReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = M.build_report()
        cls.cases = {(case["reference_family"], case["matrix_id"]): case for case in cls.report["cases"]}

    def test_complete_report_replays_exactly(self):
        self.assertEqual(EVIDENCE.read_bytes(), M.canonical(self.report))
        self.assertEqual(18, self.report["case_count"])
        self.assertEqual(18, self.report["matrix_gram_crosschecks_passed"])

    def test_every_declared_case_and_all_original_support_outcomes_are_retained(self):
        self.assertEqual(18, len(self.cases))
        self.assertEqual(15, sum(case["original_alignment"]["status"] == "supported" for case in self.cases.values()))
        for case in self.cases.values():
            self.assertTrue(case["alignment_inputs_unchanged"])
            self.assertTrue(case["exact_known_zero_lag_projection"]["matrix_gram_and_pointwise_calculations_identical"])

    def test_correlated_swap_and_both_dual_mono_cases_are_alignment_supported(self):
        for key in ((M.FAMILIES[1], "channel_swap_same_declared_map"), (M.FAMILIES[0], "mid_to_dual_mono"), (M.FAMILIES[1], "mid_to_dual_mono")):
            self.assertEqual("supported", self.cases[key]["original_alignment"]["status"])
        swapped = self.cases[(M.FAMILIES[0], "channel_swap_same_declared_map")]
        self.assertEqual("unsupported", swapped["original_alignment"]["status"])
        self.assertIn("channel_alignment_disagreement", swapped["original_alignment"]["support"]["reasons"])
        self.assertEqual([1, -1], [row["integer_delay_samples"] for row in swapped["original_alignment"]["alignment"]["channels"]])

    def test_dropout_rejections_and_correlation_sentinel_are_preserved(self):
        for family in M.FAMILIES:
            result = self.cases[(family, "right_channel_zero")]["original_alignment"]
            self.assertEqual("unsupported", result["status"])
            self.assertEqual(["ambiguous_alignment_peak", "gain_exceeds_limit"], result["support"]["reasons"])
            self.assertEqual("1.000000000", result["alignment"]["channels"][1]["correlation"])
            self.assertEqual("-999.000000000", result["alignment"]["channels"][1]["observed_gain_db"])

    def test_relative_polarity_exchanges_correlated_mid_side_shares(self):
        result = self.cases[(M.FAMILIES[1], "right_polarity_inversion")]["exact_known_zero_lag_projection"]
        self.assertEqual("25/26", result["reference_channel_geometry"]["mid_energy_share"])
        self.assertEqual("1/26", result["test_channel_geometry"]["mid_energy_share"])
        self.assertEqual("25/26", result["test_channel_geometry"]["side_energy_share"])
        self.assertEqual("0/1", result["reference_normalized_squared_residuals"]["independent_signed_gains"])

    def test_original_oracle_never_promotes_alignment_to_perceptual_evidence(self):
        for case in self.cases.values():
            result = case["original_oracle_assembly"]
            self.assertEqual("accepted", result["assembly"])
            self.assertIn(result["result_state"], ("execution_blocked", "unsupported_alignment"))
            self.assertFalse(result["support"]["supported"])
            self.assertEqual("indeterminate", result["outcomes"]["categorical_state"])
            self.assertIsNone(result["outcomes"]["impairment_severity"])
            self.assertIsNone(result["outcomes"]["audibility_probability"])

    def test_claims_and_normalization_authority_remain_closed(self):
        self.assertTrue(all(value is False for value in self.report["claim_boundary"].values()))
        self.assertFalse(self.report["selected_boundary"]["alignment_support_is_normalization_authority"])
        for key in ("real_audio_accessed", "gain_or_polarity_corrected_audio_produced", "perceptual_metric_or_human_execution"):
            self.assertFalse(self.report[key])
        for marker in (b"/Users/", b".wav", b".flac", b"participant-", b"pcm_sha", b"encoded_sha"):
            self.assertNotIn(marker, M.canonical(self.report))

    def test_cli_cannot_open_audio_or_tune_interventions(self):
        for args in ([], ["--synthetic", "--input", "unopened.wav"], ["--synthetic", "--gain", "0.9"]):
            execution = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True)
            self.assertNotEqual(0, execution.returncode)


if __name__ == "__main__":
    unittest.main()
