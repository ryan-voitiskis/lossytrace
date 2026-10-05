"""Synthetic feature objects only; no audio, real labels or checkpoints."""
import importlib.util
import math
from pathlib import Path
import unittest
from unittest.mock import patch

try:
    import numpy as np
except ModuleNotFoundError as exc:
    if exc.name != "numpy":
        raise
    np = None

if np is not None:
    import sys
    SCRIPT = Path(__file__).resolve().parents[1] / "music_verdict_comparator.py"
    SPEC = importlib.util.spec_from_file_location("music_verdict_comparator", SCRIPT)
    comparator = importlib.util.module_from_spec(SPEC)
    sys.modules[SPEC.name] = comparator
    SPEC.loader.exec_module(comparator)


@unittest.skipIf(np is None, "requires isolated synthetic-requirements research environment")
class ComparatorSyntheticTests(unittest.TestCase):
    def record(self, value=None):
        result = dict.fromkeys(comparator.FEATURES)
        result.update(feature_version=0, analyzed_frame_count=100,
                      active_frame_count=80, high_band_supported_frame_count=60,
                      active_duration_seconds=1.0, median_active_bin_fraction=value)
        return result

    def test_feature_order_and_exclusions_match_rust_definition(self):
        source = (Path(__file__).resolve().parents[2] / "src/compression_trace.rs").read_text()
        self.assertEqual(len(comparator.FEATURES), 12)
        for name in comparator.FEATURES:
            self.assertIn(f"pub {name}: Option<", source)
        self.assertFalse(set(comparator.FEATURES) & set(comparator.EXCLUDED))
        self.assertEqual(comparator.FEATURES[0], "median_active_bin_fraction")
        self.assertEqual(comparator.FEATURES[-1], "transform_alignment_small_coefficient_fraction")

    def test_only_null_means_missing(self):
        raw = comparator.measurement_matrix([self.record(0.0), self.record()])
        self.assertEqual(raw.shape, (2, 12))
        self.assertEqual(raw[0, 0], 0)
        self.assertTrue(np.isnan(raw[1, 0]))
        for value in (True, "0.1", float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                comparator.measurement_matrix([self.record(value)])

    def test_schema_version_and_metadata_rejected(self):
        for change in ({"feature_version": 1}, {"feature_version": False},
                       {"path": "song.flac"}, {"input_sha256": "a" * 64}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                comparator.measurement_matrix([self.record() | change])
        record = self.record()
        del record["spectral_edge_hz"]
        with self.assertRaises(ValueError):
            comparator.measurement_matrix([record])

    def test_upstream_support_and_edge_contract_validated(self):
        for change in ({"active_frame_count": 101}, {"high_band_supported_frame_count": 81},
                       {"analyzed_frame_count": 1.5}, {"active_duration_seconds": -1},
                       {"spectral_edge_hz": 16000}, {"transform_alignment_phase_samples": 0.5}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                comparator.measurement_matrix([self.record() | change])

    def test_counts_and_duration_do_not_become_features(self):
        original = self.record(0.4)
        altered = original | {"analyzed_frame_count": 4000, "active_frame_count": 400,
                              "high_band_supported_frame_count": 300, "active_duration_seconds": 300.0}
        np.testing.assert_equal(comparator.measurement_matrix([original]),
                                comparator.measurement_matrix([altered]))

    def test_group_and_class_weights_not_case_counts(self):
        weights = comparator.group_class_weights(["a", "a", "a", "b", "b"], [0, 1, 1, 0, 1])
        np.testing.assert_allclose(weights, [0.25, 0.125, 0.125, 0.25, 0.25])
        self.assertAlmostEqual(weights.sum(), 1)

    def test_bad_groups_and_labels_rejected(self):
        for groups, labels in (([], []), (["a"], [0]), (["a", "b"], [0, 1]),
                               (["", ""], [0, 1]), (["a", "a"], [False, True]),
                               (["a", "a"], [0, 2]), (["a", "a"], [0, float("nan")])):
            with self.subTest(groups=groups, labels=labels), self.assertRaises(ValueError):
                comparator.group_class_weights(groups, labels)

    def test_train_only_weighted_imputation_and_standardization(self):
        records = [self.record(0), self.record(1), self.record()]
        weights = np.array([0.25, 0.25, 0.5])
        transform = comparator.fit_preprocessor(records, weights, partition="train")
        self.assertAlmostEqual(transform.imputation[0], 0.5)
        result = transform.transform(records)
        self.assertEqual(result.shape, (3, 24))
        self.assertAlmostEqual(transform.scale[0], math.sqrt(0.125))
        np.testing.assert_allclose(weights @ result, 0, atol=1e-15)
        np.testing.assert_allclose(result[:, 12], [-1, -1, 1])
        self.assertTrue(np.all(result[:, 1:12] == 0))

    def test_held_out_values_cannot_modify_training_state(self):
        transform = comparator.fit_preprocessor([self.record(0.2), self.record(0.4)],
                                                [0.5, 0.5], partition="train")
        before = repr(transform)
        result = transform.transform([self.record(1)])
        self.assertAlmostEqual(result[0, 0], 7)
        self.assertEqual(repr(transform), before)
        for partition in ("selection", "calibration", "evaluation", ""):
            with self.assertRaises(ValueError):
                comparator.fit_preprocessor([self.record()], [1], partition=partition)
            with self.assertRaises(ValueError):
                comparator.fit_logistic([self.record(), self.record()], [0, 1], ["a", "a"],
                                        partition=partition)

    def test_training_all_missing_columns_remain_numeric_zero(self):
        transform = comparator.fit_preprocessor([self.record(), self.record()], [0.5, 0.5], partition="train")
        result = transform.transform([self.record(0.8)])
        self.assertTrue(np.all(result[:, :12] == 0))
        self.assertEqual(result[0, 12], -1)  # Missingness is retained separately.

    def test_invalid_weights_rejected(self):
        for weights in ([0, 1], [-1, 2], [0.1, 0.1], [float("nan"), 0.5], [1]):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                comparator.fit_preprocessor([self.record(), self.record()], weights, partition="train")

    def test_constant_decimal_columns_do_not_gain_rounding_variance(self):
        for value in (0.1, 0.2, 0.3, 0.7):
            for n in range(2, 30):
                records = [self.record(value)] * n
                transform = comparator.fit_preprocessor(records, np.full(n, 1/n), partition="train")
                self.assertEqual(transform.scale[0], 1)
                self.assertTrue(np.all(transform.transform(records) == 0))

    def test_constant_observed_values_with_missing_do_not_gain_rounding_variance(self):
        records = [self.record(0.1)] * 5 + [self.record()] * 3
        transform = comparator.fit_preprocessor(records, np.full(8, 1/8), partition="train")
        self.assertEqual(transform.imputation[0], 0.1)
        self.assertEqual(transform.scale[0], 1)
        self.assertTrue(np.all(transform.transform(records)[:, 0] == 0))

    def test_objective_gradient_and_hessian_match_finite_differences(self):
        design = np.array([[-1., 1.], [0.2, 1.], [1., 1.]])
        labels, weights = np.array([0., 1., 1.]), np.array([0.5, 0.25, 0.25])
        theta, delta = np.array([0.3, -0.2]), 1e-5
        value, gradient, hessian = comparator._objective_terms(theta, design, labels, weights)
        for i in range(2):
            offset = np.eye(2)[i] * delta
            hi = comparator._objective_terms(theta + offset, design, labels, weights)
            lo = comparator._objective_terms(theta - offset, design, labels, weights)
            self.assertAlmostEqual(gradient[i], (hi[0] - lo[0]) / (2 * delta), places=8)
            np.testing.assert_allclose(hessian[:, i], (hi[1] - lo[1]) / (2 * delta), atol=1e-9)
        self.assertTrue(math.isfinite(value))

    def test_intercept_unpenalized_and_saturated_bce_finite(self):
        design, labels, weights = np.zeros((2, 2)), np.array([0., 1.]), np.array([0.5, 0.5])
        for intercept in (0., 10000.):
            value, gradient, hessian = comparator._objective_terms(np.array([2., intercept]), design, labels, weights)
            self.assertAlmostEqual(value, math.log(2) + 2)
            np.testing.assert_equal(gradient, [2, 0])
            np.testing.assert_equal(hessian, [[1, 0], [0, 0]])
        design[:, 1] = 1
        value, gradient, _ = comparator._objective_terms(np.array([0., 10000.]), design, labels, weights)
        self.assertEqual(value, 5000)
        self.assertTrue(np.isfinite(gradient).all())

    def test_one_dimensional_synthetic_optimum(self):
        records = [self.record(0), self.record(1)]
        model = comparator.fit_logistic(records, [0, 1], ["a", "a"], partition="train")
        coefficient = model.coefficients[0]
        self.assertAlmostEqual(coefficient, 1 / (1 + math.exp(coefficient)), places=7)
        self.assertAlmostEqual(model.intercept, 0, places=10)
        self.assertLessEqual(model.gradient_infinity_norm, comparator.GRADIENT_TOLERANCE)
        np.testing.assert_allclose(model.logits(records), [-coefficient, coefficient])

    def test_constant_missing_records_have_no_spurious_discrimination(self):
        records = [self.record()] * 4
        model = comparator.fit_logistic(records, [0, 1, 0, 1], ["a", "a", "b", "b"], partition="train")
        self.assertEqual(model.iterations, 0)
        np.testing.assert_equal(model.coefficients, np.zeros(24))
        np.testing.assert_equal(model.logits([self.record(), self.record(1)]), [0, 0])

    def test_replicating_one_group_does_not_change_fit(self):
        records = [self.record(v) for v in (0, 1, 0.3, 0.7)]
        first = comparator.fit_logistic(records, [0, 1, 0, 1], ["a", "a", "b", "b"], partition="train")
        second = comparator.fit_logistic(records + records[:2] * 3, [0, 1] * 5,
                                         ["a", "a", "b", "b"] + ["a", "a"] * 3, partition="train")
        np.testing.assert_allclose(first.logits(records), second.logits(records), atol=1e-12)

    def test_permutation_and_repeatability(self):
        records = [self.record(v) for v in (0, 1, 0.3, 0.7)]
        args = (records, [0, 1, 0, 1], ["a", "a", "b", "b"])
        first = comparator.fit_logistic(*args, partition="train")
        again = comparator.fit_logistic(*args, partition="train")
        self.assertEqual(first, again)
        reverse = comparator.fit_logistic(*[list(reversed(a)) for a in args], partition="train")
        np.testing.assert_allclose(first.logits(records), reverse.logits(records), atol=1e-12)

    def test_nonconvergence_fails_without_partial_model(self):
        with patch.object(comparator, "MAX_ITERATIONS", 0), self.assertRaises(RuntimeError):
            comparator.fit_logistic([self.record(0), self.record(1)], [0, 1], ["a", "a"], partition="train")


if __name__ == "__main__":
    unittest.main()
