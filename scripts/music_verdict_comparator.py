#!/usr/bin/env python3
"""Research-only feature-v0 logistic comparator and portable fitted parameters.

The model consumes numeric measurements. The caller supplies evidence and policy.
The caller must satisfy source and execution gates before any real-data fitting
or scoring. A partition argument is a misuse guard, not proof of provenance.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math

import numpy as np

# Ordered optional measurements from CompressionTraceFeatures, feature version 0.
# Counts and durations are deliberately excluded, including duration proxies.
FEATURES = (
    "median_active_bin_fraction", "spectral_edge_hz", "spectral_edge_drop_db",
    "spectral_edge_persistence", "spectral_edge_spread_hz", "spectral_hole_ratio",
    "isolated_hole_ratio", "band_rupture_score", "transform_alignment_score",
    "transform_alignment_block_samples", "transform_alignment_phase_samples",
    "transform_alignment_small_coefficient_fraction",
)
COUNTS = ("analyzed_frame_count", "active_frame_count", "high_band_supported_frame_count")
EXCLUDED = ("feature_version", *COUNTS, "active_duration_seconds")
RATIOS = (FEATURES[0], FEATURES[3], *FEATURES[5:9], FEATURES[11])
EDGE = FEATURES[1:5]
INTEGER_FEATURES = FEATURES[9:11]
L2_PENALTY = 1.0
MAX_ITERATIONS = 100
MAX_BACKTRACKS = 40
GRADIENT_TOLERANCE = 1e-8
ARMIJO = 1e-4


def _training(partition: str) -> None:
    if partition != "train":
        raise ValueError("fitting requires the train partition; held-out data cannot refit")


def _number(value, *, integer=False, ratio=False) -> float:
    if integer:
        if type(value) is not int or not 0 <= value <= 2**32 - 1:
            raise ValueError("expected uint32 measurement")
    elif type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("expected finite numeric measurement, not a boolean")
    if not 0 <= value <= (1.0 if ratio else np.finfo(np.float32).max):
        raise ValueError("measurement outside feature-v0 range")
    return float(value)


def measurement_matrix(records: list[dict]) -> np.ndarray:
    """Strict feature-v0 objects only, never full reports or metadata columns.

    Null is genuine missingness; malformed values cannot masquerade as missing.
    Validate excluded numeric fields but never feed them to the classifier.
    """
    if not isinstance(records, list) or not records:
        raise ValueError("expected nonempty measurement records")
    result = np.empty((len(records), len(FEATURES)), dtype=np.float64)
    for i, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != set(FEATURES + EXCLUDED):
            raise ValueError("unexpected or missing measurement fields")
        if type(record["feature_version"]) is not int or record["feature_version"] != 0:
            raise ValueError("unsupported measurement definition")
        counts = [_number(record[k], integer=True) for k in COUNTS]
        if not counts[2] <= counts[1] <= counts[0]:
            raise ValueError("inconsistent support counts")
        _number(record["active_duration_seconds"])
        present = [record[k] is not None for k in EDGE]
        if any(present) and not all(present):
            raise ValueError("edge fields must be all present or all absent")
        for j, name in enumerate(FEATURES):
            value = record[name]
            result[i, j] = (np.nan if value is None else
                            _number(value, integer=name in INTEGER_FEATURES, ratio=name in RATIOS))
    return result


def _labels(values, n: int) -> np.ndarray:
    raw = np.asarray(values)
    if raw.shape != (n,) or raw.dtype.kind not in "ifu" or not np.isin(raw, (0, 1)).all():
        raise ValueError("expected one binary numeric label per case")
    return raw.astype(np.float64)


def group_class_weights(group_ids: list[str], labels) -> np.ndarray:
    """Equal component weight, half per class, equal cases within group/class.

    Identity strings determine weights only; they never become model features.
    Both classes must exist in each group. Missing cases must not silently
    disappear; the future construction audit must check the full case matrix.
    """
    if (not isinstance(group_ids, list) or not group_ids
            or any(not isinstance(g, str) or not g.strip() for g in group_ids)):
        raise ValueError("expected nonempty component IDs")
    y = _labels(labels, len(group_ids))
    counts = Counter(zip(group_ids, y))
    groups = set(group_ids)
    if any((g, c) not in counts for g in groups for c in (0, 1)):
        raise ValueError("every training group requires both classes")
    return np.array([1 / (2 * len(groups) * counts[g, c]) for g, c in zip(group_ids, y)])


def _weights(values, n: int) -> np.ndarray:
    weights = np.asarray(values, dtype=np.float64)
    if (weights.shape != (n,) or not np.isfinite(weights).all() or (weights <= 0).any()
            or not math.isclose(float(weights.sum()), 1.0, rel_tol=0, abs_tol=1e-12)):
        raise ValueError("weights must be positive, finite and sum to one")
    return weights


@dataclass(frozen=True)
class Preprocessor:
    imputation: tuple[float, ...]
    observed: tuple[bool, ...]
    center: tuple[float, ...]
    scale: tuple[float, ...]

    def transform(self, records: list[dict]) -> np.ndarray:
        raw = measurement_matrix(records)
        missing = np.isnan(raw)
        values = np.where(missing, self.imputation, raw)
        # No training observations means no justified numeric scale. Such a
        # numeric column remains zero, even if a held-out value becomes present.
        values[:, ~np.asarray(self.observed)] = 0
        expanded = np.concatenate((values, missing.astype(np.float64)), axis=1)
        result = (expanded - self.center) / self.scale
        if not np.isfinite(result).all():
            raise ValueError("non-finite transformed features")
        return result


def fit_preprocessor(records: list[dict], weights, *, partition: str) -> Preprocessor:
    _training(partition)
    raw = measurement_matrix(records)
    w = _weights(weights, len(raw))
    missing = np.isnan(raw)
    mass = (~missing).T @ w
    # Center the weighted sum on an observed value. A constant decimal column
    # must not acquire fake variance through mean-rounding and then be scaled
    # by that tiny error. The same construction is used for the expanded mean.
    anchor = np.array([raw[np.flatnonzero(~missing[:, j])[0], j] if mass[j] else 0
                       for j in range(len(FEATURES))])
    imputation = anchor + np.divide(np.where(missing, 0, raw - anchor).T @ w, mass,
                                    out=np.zeros(len(FEATURES)), where=mass > 0)
    values = np.where(missing, imputation, raw)
    expanded = np.concatenate((values, missing.astype(np.float64)), axis=1)
    center = expanded[0] + (w @ (expanded - expanded[0])) / w.sum()
    variance = (w @ np.square(expanded - center)) / w.sum()
    scale = np.sqrt(variance)
    scale[scale == 0] = 1.0
    if not all(np.isfinite(v).all() for v in (imputation, center, scale)):
        raise ValueError("non-finite training preprocessing")
    return Preprocessor(tuple(imputation), tuple(mass > 0), tuple(center), tuple(scale))


def _objective_terms(theta, design, labels, weights):
    """Weighted mean BCE + (1/2)*1.0*||coefficients||^2; intercept last."""
    z = design @ theta
    probability = np.exp(-np.logaddexp(0, -z))
    value = float(weights @ np.logaddexp(0, np.where(labels == 1, -z, z))
                  + 0.5 * L2_PENALTY * (theta[:-1] @ theta[:-1]))
    gradient = design.T @ (weights * (probability - labels))
    gradient[:-1] += L2_PENALTY * theta[:-1]
    curvature = weights * probability * (1 - probability)
    hessian = design.T @ (curvature[:, None] * design)
    hessian[:-1, :-1] += L2_PENALTY * np.eye(len(theta) - 1)
    if not (math.isfinite(value) and np.isfinite(gradient).all() and np.isfinite(hessian).all()):
        raise ValueError("non-finite logistic objective")
    return value, gradient, hessian


@dataclass(frozen=True)
class Comparator:
    preprocessing: Preprocessor
    coefficients: tuple[float, ...]
    intercept: float
    iterations: int
    gradient_infinity_norm: float

    def logits(self, records: list[dict]) -> np.ndarray:
        result = self.preprocessing.transform(records) @ self.coefficients + self.intercept
        if not np.isfinite(result).all():
            raise ValueError("non-finite comparator logits")
        return result


def fit_logistic(records: list[dict], labels, group_ids: list[str], *, partition: str) -> Comparator:
    """Deterministic float64 damped Newton solve; no retries or alternate solver.

    Initialize all coefficients/intercept at zero. Stop only on the full
    gradient infinity norm <=1e-8, otherwise fail after 100 iterations. Up to
    40 halvings with Armijo 1e-4; failure never returns a partially fitted model.
    Synthetic tests may fit generated records. Real source fitting is gated
    separately by the study, not authorized merely by calling this function.
    """
    _training(partition)
    if len(group_ids) != len(records):
        raise ValueError("component IDs must align with records")
    y = _labels(labels, len(records))
    weights = group_class_weights(group_ids, y)
    preprocessing = fit_preprocessor(records, weights, partition=partition)
    x = preprocessing.transform(records)
    design = np.column_stack((x, np.ones(len(x))))
    theta = np.zeros(design.shape[1], dtype=np.float64)
    for iteration in range(MAX_ITERATIONS + 1):
        value, gradient, hessian = _objective_terms(theta, design, y, weights)
        norm = float(np.max(np.abs(gradient)))
        if norm <= GRADIENT_TOLERANCE:
            return Comparator(preprocessing, tuple(theta[:-1]), float(theta[-1]), iteration, norm)
        if iteration == MAX_ITERATIONS:
            break
        try:
            direction = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError as exc:
            raise RuntimeError("singular comparator solve; no fallback") from exc
        decrement = float(gradient @ direction)
        if not np.isfinite(direction).all() or not math.isfinite(decrement) or decrement <= 0:
            raise RuntimeError("invalid Newton direction")
        for backtrack in range(MAX_BACKTRACKS):
            step = 0.5 ** backtrack
            proposal = theta - step * direction
            trial, _, _ = _objective_terms(proposal, design, y, weights)
            if trial <= value - ARMIJO * step * decrement:
                theta = proposal
                break
        else:
            raise RuntimeError("comparator line search failed; no fallback")
    raise RuntimeError("comparator did not converge; no partial result")


def checkpoint_bytes(model: Comparator) -> bytes:
    """Encode the fitted transform and model; thresholds are a separate calibration artifact."""
    pre = model.preprocessing
    record = {
        "schema": "lossytrace.research.measurement-logistic.v1", "features": list(FEATURES),
        "imputation": list(map(float, pre.imputation)), "observed": list(map(bool, pre.observed)),
        "center": list(map(float, pre.center)), "scale": list(map(float, pre.scale)),
        "coefficients": list(map(float, model.coefficients)), "intercept": float(model.intercept),
        "iterations": model.iterations, "gradient_infinity_norm": float(model.gradient_infinity_norm),
    }
    return (json.dumps(record, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def load_checkpoint(data: bytes, expected_sha256: str) -> Comparator:
    """Read the exact artifact committed by the caller and verify inference compatibility."""
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("comparator checkpoint digest mismatch")

    def unique(pairs):
        obj = dict(pairs)
        if len(obj) != len(pairs):
            raise ValueError("duplicate checkpoint key")
        return obj

    doc = json.loads(data, object_pairs_hook=unique)
    keys = {"schema", "features", "imputation", "observed", "center", "scale",
            "coefficients", "intercept", "iterations", "gradient_infinity_norm"}
    if (not isinstance(doc, dict) or set(doc) != keys
            or doc["schema"] != "lossytrace.research.measurement-logistic.v1"
            or doc["features"] != list(FEATURES)):
        raise ValueError("incompatible comparator checkpoint")
    width = len(FEATURES)

    def numeric(value):
        if type(value) not in (float, int):
            raise ValueError("non-numeric checkpoint value")
        try:
            number = float(value)
        except OverflowError as exc:
            raise ValueError("unrepresentable checkpoint value") from exc
        if not math.isfinite(number):
            raise ValueError("non-finite checkpoint value")
        return number

    def vector(key, length):
        values = doc[key]
        if not isinstance(values, list) or len(values) != length:
            raise ValueError(f"incorrect {key} dimension")
        return tuple(map(numeric, values))

    observed = doc["observed"]
    if not isinstance(observed, list) or len(observed) != width or any(type(v) is not bool for v in observed):
        raise ValueError("invalid observed-column mask")
    scale = vector("scale", width * 2)
    iterations = doc["iterations"]
    gradient = numeric(doc["gradient_infinity_norm"])
    if (min(scale) <= 0 or type(iterations) is not int or not 0 <= iterations <= MAX_ITERATIONS
            or not 0 <= gradient <= GRADIENT_TOLERANCE):
        raise ValueError("invalid fitted scale or solver status")
    preprocessing = Preprocessor(vector("imputation", width), tuple(observed), vector("center", width * 2), scale)
    return Comparator(preprocessing, vector("coefficients", width * 2), numeric(doc["intercept"]),
                      iterations, gradient)
