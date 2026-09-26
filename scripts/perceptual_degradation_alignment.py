#!/usr/bin/env python3
"""Score-free deterministic alignment for perceptual-degradation research.

This module intentionally computes no perceptual metric and emits no verdict.
It operates on decoded mono sample sequences so decoder and channel-map policy
can be tested and bound independently.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from typing import Any


ENVELOPE_RATE_HZ = 200
MAX_CORRELATION_SAMPLES = 16384
MIN_ALIGNMENT_CORRELATION = 0.20
MIN_AMBIGUITY_MARGIN = 0.01
MAX_GAIN_ABS_DB = 12.0
MAX_CLOCK_DRIFT_PPM = 100.0
MAX_NONLINEAR_DRIFT_RESIDUAL_SAMPLES = 1.5
MAX_EDGE_TRIM_SECONDS = 2.0
MAX_EDGE_TRIM_FRACTION = 0.10
LIMITS_ID = "perceptual-degradation-v1-alignment-fixtures-20260803-001"


def case_id(recipe_identity: str) -> str:
    if not recipe_identity:
        raise ValueError("recipe identity must not be empty")
    return "case-" + hashlib.sha256(recipe_identity.encode()).hexdigest()


def _finite(values: Sequence[float]) -> bool:
    return bool(values) and all(math.isfinite(float(value)) for value in values)


def _rms_envelope(values: Sequence[float], block_size: int) -> list[float]:
    result: list[float] = []
    for start in range(0, len(values), block_size):
        block = values[start : start + block_size]
        if len(block) < max(1, block_size // 2):
            break
        result.append(math.sqrt(math.fsum(float(value) ** 2 for value in block) / len(block)))
    return result


def _overlap(length_a: int, length_b: int, lag: int) -> tuple[int, int, int]:
    start_a = max(0, -lag)
    start_b = max(0, lag)
    length = min(length_a - start_a, length_b - start_b)
    return start_a, start_b, max(0, length)


def _pearson_at_lag(a: Sequence[float], b: Sequence[float], lag: int) -> float:
    start_a, start_b, length = _overlap(len(a), len(b), lag)
    if length < 4:
        return -1.0
    a_values = a[start_a : start_a + length]
    b_values = b[start_b : start_b + length]
    mean_a = math.fsum(a_values) / length
    mean_b = math.fsum(b_values) / length
    centered_a = [value - mean_a for value in a_values]
    centered_b = [value - mean_b for value in b_values]
    energy_a = math.fsum(value * value for value in centered_a)
    energy_b = math.fsum(value * value for value in centered_b)
    if energy_a <= 0.0 or energy_b <= 0.0:
        return -1.0
    return math.fsum(x * y for x, y in zip(centered_a, centered_b, strict=True)) / math.sqrt(
        energy_a * energy_b
    )


def _sampled_cosine_at_lag(a: Sequence[float], b: Sequence[float], lag: int) -> float:
    start_a, start_b, length = _overlap(len(a), len(b), lag)
    if length < 16:
        return -1.0
    stride = max(1, length // MAX_CORRELATION_SAMPLES)
    dot = 0.0
    energy_a = 0.0
    energy_b = 0.0
    for offset in range(0, length, stride):
        x = float(a[start_a + offset])
        y = float(b[start_b + offset])
        dot += x * y
        energy_a += x * x
        energy_b += y * y
    if energy_a <= 0.0 or energy_b <= 0.0:
        return -1.0
    return dot / math.sqrt(energy_a * energy_b)


def _best_lag(scores: dict[int, float], exclusion: int) -> tuple[int, float, float]:
    best_lag, best_score = max(scores.items(), key=lambda item: (item[1], -abs(item[0]), -item[0]))
    alternatives = [
        score for lag, score in scores.items() if abs(lag - best_lag) > exclusion
    ]
    second = max(alternatives, default=-1.0)
    return best_lag, best_score, max(0.0, best_score - second)


def _candidate_lags(scores: dict[int, float], count: int, exclusion: int) -> list[int]:
    selected: list[int] = []
    for lag, _ in sorted(
        scores.items(), key=lambda item: (item[1], -abs(item[0]), -item[0]), reverse=True
    ):
        if all(abs(lag - prior) > exclusion for prior in selected):
            selected.append(lag)
        if len(selected) == count:
            break
    return selected


def _fractional_peak(scores: dict[int, float], lag: int) -> float:
    left = scores.get(lag - 1, scores[lag])
    center = scores[lag]
    right = scores.get(lag + 1, scores[lag])
    denominator = left - 2.0 * center + right
    if denominator >= -1e-15:
        return 0.0
    estimate = 0.5 * (left - right) / denominator
    return max(-0.5, min(0.5, estimate))


def _local_lag(
    reference: Sequence[float],
    test: Sequence[float],
    global_lag: int,
    center_reference: int,
    half_window: int,
    radius: int,
) -> tuple[int, float]:
    start = max(0, center_reference - half_window)
    end = min(len(reference), center_reference + half_window)
    reference_window = reference[start:end]
    scores: dict[int, float] = {}
    for delta in range(-radius, radius + 1):
        lag = global_lag + delta
        test_start = start + lag
        test_end = test_start + len(reference_window)
        if test_start < 0 or test_end > len(test):
            continue
        scores[lag] = abs(
            _sampled_cosine_at_lag(reference_window, test[test_start:test_end], 0)
        )
    if not scores:
        return global_lag, -1.0
    lag, score = max(scores.items(), key=lambda item: (item[1], -abs(item[0] - global_lag)))
    return lag, score


def _drift_estimate(
    reference: Sequence[float], test: Sequence[float], sample_rate_hz: int, lag: int
) -> tuple[float, float, float]:
    start_a, _, aligned = _overlap(len(reference), len(test), lag)
    if aligned < sample_rate_hz * 2:
        return 0.0, 0.0, 1.0
    half_window = min(sample_rate_hz // 2, aligned // 10)
    radius = max(2, math.ceil(aligned * MAX_CLOCK_DRIFT_PPM / 1_000_000.0) + 2)
    positions = [
        start_a + int(aligned * fraction)
        for fraction in (0.15, 0.325, 0.5, 0.675, 0.85)
    ]
    points = [
        (position, *_local_lag(reference, test, lag, position, half_window, radius))
        for position in positions
    ]
    mean_x = math.fsum(point[0] for point in points) / len(points)
    mean_y = math.fsum(point[1] for point in points) / len(points)
    denominator = math.fsum((point[0] - mean_x) ** 2 for point in points)
    slope = (
        math.fsum((point[0] - mean_x) * (point[1] - mean_y) for point in points)
        / denominator
        if denominator > 0.0
        else 0.0
    )
    intercept = mean_y - slope * mean_x
    residuals = [abs(point[1] - (intercept + slope * point[0])) for point in points]
    correlations = [point[2] for point in points]
    return slope * 1_000_000.0, max(residuals), min(correlations)


def _gain_and_active(
    reference: Sequence[float], test: Sequence[float], lag: int, sample_rate_hz: int
) -> tuple[float, str, float, int, float]:
    start_a, start_b, length = _overlap(len(reference), len(test), lag)
    ref = reference[start_a : start_a + length]
    tst = test[start_b : start_b + length]
    reference_energy = math.fsum(float(value) ** 2 for value in ref)
    cross = math.fsum(float(x) * float(y) for x, y in zip(ref, tst, strict=True))
    gain = cross / reference_energy if reference_energy > 0.0 else 0.0
    polarity = "inverted" if gain < 0.0 else "preserved"
    gain_db = 20.0 * math.log10(abs(gain)) if gain else -999.0

    block_size = max(1, sample_rate_hz // 20)
    envelope = _rms_envelope(ref, block_size)
    maximum = max(envelope, default=0.0)
    active_blocks = sum(value >= maximum * 0.001 and value > 1e-12 for value in envelope)
    active_seconds = active_blocks * block_size / sample_rate_hz
    correlation = abs(_sampled_cosine_at_lag(reference, test, lag))
    return gain_db, polarity, active_seconds, length, correlation


def align_mono(
    *,
    reference: Sequence[float],
    test: Sequence[float],
    sample_rate_hz: int,
    recipe_identity: str,
    minimum_active_seconds: float = 4.0,
    maximum_delay_seconds: float = 2.0,
) -> dict[str, Any]:
    """Return a path-free, score-free alignment and support record."""

    if sample_rate_hz < 1 or minimum_active_seconds <= 0.0 or maximum_delay_seconds <= 0.0:
        raise ValueError("alignment configuration differs")
    if not _finite(reference) or not _finite(test):
        return _unsupported_numeric_record(reference, test, sample_rate_hz, recipe_identity)

    block_size = max(1, round(sample_rate_hz / ENVELOPE_RATE_HZ))
    reference_envelope = _rms_envelope(reference, block_size)
    test_envelope = _rms_envelope(test, block_size)
    maximum_lag_blocks = math.ceil(maximum_delay_seconds * sample_rate_hz / block_size)
    envelope_scores = {
        lag: _pearson_at_lag(reference_envelope, test_envelope, lag)
        for lag in range(-maximum_lag_blocks, maximum_lag_blocks + 1)
    }
    coarse_candidates = _candidate_lags(envelope_scores, count=8, exclusion=2)
    sample_lags = {
        lag
        for coarse_lag in coarse_candidates
        for lag in range(
            coarse_lag * block_size - block_size,
            coarse_lag * block_size + block_size + 1,
        )
    }
    sample_scores = {
        lag: abs(_sampled_cosine_at_lag(reference, test, lag)) for lag in sample_lags
    }
    integer_lag, correlation, sample_margin = _best_lag(sample_scores, exclusion=1)
    fractional_lag = _fractional_peak(sample_scores, integer_lag)
    gain_db, polarity, active_seconds, aligned_frames, correlation = _gain_and_active(
        reference, test, integer_lag, sample_rate_hz
    )
    drift_ppm, drift_residual, minimum_window_correlation = _drift_estimate(
        reference, test, sample_rate_hz, integer_lag
    )

    edge_trim_frames = len(reference) + len(test) - 2 * aligned_frames
    edge_trim_seconds = edge_trim_frames / sample_rate_hz
    edge_trim_fraction = edge_trim_frames / max(1, min(len(reference), len(test)))
    ambiguity_margin = sample_margin
    reasons: list[str] = []
    if ambiguity_margin < MIN_AMBIGUITY_MARGIN:
        reasons.append("ambiguous_alignment_peak")
    if active_seconds < minimum_active_seconds:
        reasons.append("insufficient_active_audio")
    if correlation < MIN_ALIGNMENT_CORRELATION or minimum_window_correlation < MIN_ALIGNMENT_CORRELATION:
        reasons.append("low_alignment_correlation")
    if abs(drift_ppm) > MAX_CLOCK_DRIFT_PPM:
        reasons.append("clock_drift_exceeds_limit")
    if drift_residual > MAX_NONLINEAR_DRIFT_RESIDUAL_SAMPLES:
        reasons.append("nonlinear_drift")
    if abs(gain_db) > MAX_GAIN_ABS_DB:
        reasons.append("gain_exceeds_limit")
    if edge_trim_seconds > MAX_EDGE_TRIM_SECONDS or edge_trim_fraction > MAX_EDGE_TRIM_FRACTION:
        reasons.append("excessive_trim")

    return {
        "schema_version": 1,
        "record_kind": "perceptual_degradation_alignment",
        "case_id": case_id(recipe_identity),
        "status": "unsupported" if reasons else "supported",
        "public_verdict_enabled": False,
        "input": {
            "sample_rate_hz": sample_rate_hz,
            "channel_count": 1,
            "reference_frames": len(reference),
            "test_frames": len(test),
        },
        "alignment": {
            "integer_delay_samples": integer_lag,
            "fractional_delay_samples": fractional_lag,
            "clock_drift_ppm": drift_ppm,
            "observed_gain_db": gain_db,
            "polarity": polarity,
            "aligned_frames": aligned_frames,
            "active_seconds": active_seconds,
            "correlation": correlation,
            "ambiguity_margin": ambiguity_margin,
            "edge_trim_seconds": edge_trim_seconds,
        },
        "support": {"reasons": sorted(set(reasons)), "limits_id": LIMITS_ID},
    }


def _unsupported_numeric_record(
    reference: Sequence[float], test: Sequence[float], sample_rate_hz: int, recipe_identity: str
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "record_kind": "perceptual_degradation_alignment",
        "case_id": case_id(recipe_identity),
        "status": "unsupported",
        "public_verdict_enabled": False,
        "input": {
            "sample_rate_hz": sample_rate_hz,
            "channel_count": 1,
            "reference_frames": len(reference),
            "test_frames": len(test),
        },
        "alignment": {
            "integer_delay_samples": 0,
            "fractional_delay_samples": 0.0,
            "clock_drift_ppm": 0.0,
            "observed_gain_db": 0.0,
            "polarity": "preserved",
            "aligned_frames": 0,
            "active_seconds": 0.0,
            "correlation": 0.0,
            "ambiguity_margin": 0.0,
            "edge_trim_seconds": 0.0,
        },
        "support": {"reasons": ["invalid_numeric_input"], "limits_id": LIMITS_ID},
    }
