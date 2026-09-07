#!/usr/bin/env python3
"""Validity-aware score-free alignment successor; never changes input samples.

The bound v1/v2 implementations and their evidence are intentionally unchanged.
This module uses their limits, not their sentinel-bearing correlation helpers.
It is not wired into any real-audio runner or perceptual oracle.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import perceptual_degradation_alignment as legacy
import perceptual_degradation_alignment_v2 as topology


RECORD_KIND = "perceptual_degradation_alignment_v3"
LIMITS_ID = "alignment-validity-successor-20260907-001"


@dataclass(frozen=True)
class Correlation:
    value: float | None
    reason: str | None
    overlap_frames: int
    sampled_frames: int

    def __post_init__(self) -> None:
        if self.value is None:
            if not isinstance(self.reason, str) or not self.reason:
                raise ValueError("undefined correlation requires a reason")
        elif self.reason is not None or not _number(self.value) or not -1 <= self.value <= 1:
            raise ValueError("defined correlation requires a finite signed value")
        if (
            type(self.sampled_frames) is not int
            or type(self.overlap_frames) is not int
            or not 0 <= self.sampled_frames <= self.overlap_frames
            or (self.value is not None and self.sampled_frames == 0)
        ):
            raise ValueError("correlation frame counts differ")

    @property
    def magnitude(self) -> float | None:
        return None if self.value is None else abs(self.value)

    def record(self) -> dict[str, Any]:
        return {**asdict(self), "magnitude": self.magnitude}


def _number(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def correlate(
    a: Sequence[float], b: Sequence[float], lag: int, *, centered: bool = False
) -> Correlation:
    """Signed cosine (or centered Pearson) with explicit invalidity.

    Scale each sampled vector before products. Scaling is internal arithmetic;
    it does not alter the inputs or authorize a normalized comparison waveform.
    """
    if type(lag) is not int or type(centered) is not bool:
        raise ValueError("correlation configuration differs")
    start_a, start_b, length = legacy._overlap(len(a), len(b), lag)
    if length < (4 if centered else 16):
        return Correlation(None, "insufficient_overlap", length, 0)
    stride = 1 if centered else max(1, length // legacy.MAX_CORRELATION_SAMPLES)
    x = list(a[start_a : start_a + length : stride])
    y = list(b[start_b : start_b + length : stride])
    count = len(x)
    if not all(_number(value) for value in (*x, *y)):
        return Correlation(None, "invalid_numeric_input", length, count)
    scale_x, scale_y = max(map(abs, x)), max(map(abs, y))
    if not scale_x or not scale_y:
        return Correlation(None, "zero_energy", length, count)
    x = [value / scale_x for value in x]
    y = [value / scale_y for value in y]
    if centered:
        mean_x, mean_y = math.fsum(x) / count, math.fsum(y) / count
        x = [value - mean_x for value in x]
        y = [value - mean_y for value in y]
        # Re-scale after centering so nearly constant inputs do not underflow.
        scale_x, scale_y = max(map(abs, x)), max(map(abs, y))
        if not scale_x or not scale_y:
            return Correlation(None, "zero_centered_energy", length, count)
        x = [value / scale_x for value in x]
        y = [value / scale_y for value in y]
    energy_x = math.fsum(value * value for value in x)
    energy_y = math.fsum(value * value for value in y)
    value = math.fsum(left * right for left, right in zip(x, y, strict=True)) / (
        math.sqrt(energy_x) * math.sqrt(energy_y)
    )
    if not math.isfinite(value) or abs(value) > 1 + 1e-12:
        return Correlation(None, "numeric_failure", length, count)
    return Correlation(max(-1.0, min(1.0, value)), None, length, count)


def valid_scores(results: dict[int, Correlation], *, magnitude: bool) -> dict[int, float]:
    return {
        lag: abs(result.value) if magnitude else result.value
        for lag, result in results.items()
        if result.value is not None
    }


def validity_counts(results: Sequence[Correlation]) -> dict[str, Any]:
    return {
        "valid": sum(result.value is not None for result in results),
        "invalid": dict(sorted(Counter(result.reason for result in results if result.reason).items())),
    }


def _rms_envelope(values: Sequence[float], block_size: int) -> list[float]:
    result = []
    for start in range(0, len(values), block_size):
        block = values[start : start + block_size]
        if len(block) < max(1, block_size // 2):
            break
        scale = max(map(abs, block))
        result.append(scale * math.sqrt(math.fsum((value / scale) ** 2 for value in block) / len(block)) if scale else 0.0)
    return result


def _peak(scores: dict[int, float]) -> tuple[int | None, float | None, float | None]:
    if not scores:
        return None, None, None
    lag, score = max(scores.items(), key=lambda item: (item[1], -abs(item[0]), -item[0]))
    alternatives = [value for other, value in scores.items() if abs(other - lag) > 1]
    margin = max(0.0, score - max(alternatives)) if alternatives else None
    fractional = legacy._fractional_peak(scores, lag) if lag - 1 in scores and lag + 1 in scores else None
    return lag, fractional, margin


def local_lag(
    reference: Sequence[float], test: Sequence[float], global_lag: int,
    center: int, half_window: int, radius: int,
) -> dict[str, Any]:
    start, end = max(0, center - half_window), min(len(reference), center + half_window)
    window = reference[start:end]
    results = {}
    for delta in range(-radius, radius + 1):
        lag = global_lag + delta
        test_start = start + lag
        if test_start < 0 or test_start + len(window) > len(test):
            continue
        results[lag] = correlate(window, test[test_start : test_start + len(window)], 0)
    scores = valid_scores(results, magnitude=True)
    lag = max(scores, key=lambda candidate: (scores[candidate], -abs(candidate - global_lag))) if scores else None
    return {
        "lag_samples": lag,
        "correlation": results[lag] if lag is not None else Correlation(None, "no_valid_local_candidate", len(window), 0),
        "candidates": validity_counts(list(results.values())),
    }


def window_audit(
    reference: Sequence[float], test: Sequence[float], rate: int, lag: int,
    *, structural: bool,
) -> dict[str, Any]:
    start, _, aligned = legacy._overlap(len(reference), len(test), lag)
    fractions = [(index + 1) / (topology.STRUCTURAL_WINDOW_COUNT + 1) for index in range(topology.STRUCTURAL_WINDOW_COUNT)] if structural else [0.15, 0.325, 0.5, 0.675, 0.85]
    result = {"window_count": len(fractions), "valid_window_count": 0, "invalid_reasons": {},
              "clock_drift_ppm": None, "residual_samples": None, "minimum_correlation": None,
              "reason": "insufficient_window_span"}
    if aligned < rate * (1 if structural else 2):
        return result
    half_window = min(rate // 4, aligned // (topology.STRUCTURAL_WINDOW_COUNT * 3)) if structural else min(rate // 2, aligned // 10)
    radius = max(2, math.ceil(rate * topology.STRUCTURAL_SEARCH_SECONDS)) if structural else max(2, math.ceil(aligned * legacy.MAX_CLOCK_DRIFT_PPM / 1_000_000) + 2)
    positions = [start + int(aligned * fraction) for fraction in fractions]
    windows = [local_lag(reference, test, lag, position, half_window, radius) for position in positions]
    result["valid_window_count"] = sum(window["lag_samples"] is not None for window in windows)
    result["invalid_reasons"] = dict(sorted(Counter(window["correlation"].reason for window in windows if window["correlation"].reason).items()))
    if result["valid_window_count"] != len(windows):
        result["reason"] = "incomplete_valid_windows"
        return result
    lags = [window["lag_samples"] for window in windows]
    mean_x, mean_y = math.fsum(positions) / len(positions), math.fsum(lags) / len(lags)
    denominator = math.fsum((position - mean_x) ** 2 for position in positions)
    if denominator <= 0:
        result["reason"] = "degenerate_window_positions"
        return result
    slope = math.fsum((position - mean_x) * (local - mean_y) for position, local in zip(positions, lags, strict=True)) / denominator
    intercept = mean_y - slope * mean_x
    result.update({"clock_drift_ppm": slope * 1_000_000,
                   "residual_samples": max(abs(local - (intercept + slope * position)) for position, local in zip(positions, lags, strict=True)),
                   "minimum_correlation": min(window["correlation"].magnitude for window in windows), "reason": None})
    return result


def gain_diagnostics(reference: Sequence[float], test: Sequence[float]) -> dict[str, Any]:
    """Fit reference to test; a zero coefficient has no dB value or polarity."""
    scale_x, scale_y = max(map(abs, reference), default=0), max(map(abs, test), default=0)
    if not scale_x:
        return {"linear_gain": None, "observed_gain_db": None, "polarity": None, "reason": "zero_reference_energy"}
    if not scale_y:
        return {"linear_gain": 0.0, "observed_gain_db": None, "polarity": None, "reason": "zero_fitted_gain"}
    x, y = [value / scale_x for value in reference], [value / scale_y for value in test]
    coefficient = math.fsum(a * b for a, b in zip(x, y, strict=True)) / math.fsum(a * a for a in x)
    if not coefficient:
        return {"linear_gain": 0.0, "observed_gain_db": None, "polarity": None, "reason": "zero_fitted_gain"}
    log_gain = math.log10(abs(coefficient)) + math.log10(scale_y) - math.log10(scale_x)
    try:
        gain = math.copysign(10**log_gain, coefficient)
    except OverflowError:
        gain = None
    if gain == 0.0:
        gain = None
    return {"linear_gain": gain, "observed_gain_db": 20 * log_gain,
            "polarity": "inverted" if coefficient < 0 else "preserved",
            "reason": "linear_gain_not_representable" if gain is None else None}


def _channel(reference: Sequence[float], test: Sequence[float], rate: int, minimum_active: float, maximum_delay: float) -> dict[str, Any]:
    reasons = []
    diagnostics = {key: None for key in ("integer_delay_samples", "fractional_delay_samples", "ambiguity_margin", "aligned_frames", "active_seconds", "edge_trim_seconds", "correlation", "gain", "drift", "structural")}
    diagnostics["search"] = {}
    if not all(_number(value) for values in (reference, test) for value in values):
        return {"status": "unsupported", "reasons": ["invalid_numeric_input"], "diagnostics": diagnostics}
    block = max(1, round(rate / legacy.ENVELOPE_RATE_HZ))
    ref_env, test_env = _rms_envelope(reference, block), _rms_envelope(test, block)
    maximum = math.ceil(maximum_delay * rate / block)
    coarse = {lag: correlate(ref_env, test_env, lag, centered=True) for lag in range(-maximum, maximum + 1)}
    diagnostics["search"]["coarse"] = validity_counts(list(coarse.values()))
    candidates = legacy._candidate_lags(valid_scores(coarse, magnitude=False), count=8, exclusion=2)
    if not candidates:
        return {"status": "unsupported", "reasons": ["no_valid_coarse_correlation"], "diagnostics": diagnostics}
    lags = sorted({lag for candidate in candidates for lag in range(candidate * block - block, candidate * block + block + 1)})
    sampled = {lag: correlate(reference, test, lag) for lag in lags}
    diagnostics["search"]["sample"] = validity_counts(list(sampled.values()))
    lag, fractional, margin = _peak(valid_scores(sampled, magnitude=True))
    if lag is None:
        return {"status": "unsupported", "reasons": ["no_valid_sample_correlation"], "diagnostics": diagnostics}
    start_a, start_b, frames = legacy._overlap(len(reference), len(test), lag)
    ref, tst = reference[start_a : start_a + frames], test[start_b : start_b + frames]
    gain = gain_diagnostics(ref, tst)
    envelope = _rms_envelope(ref, max(1, rate // 20))
    relative_floor = max(envelope, default=0) * 0.001
    active = sum(value >= relative_floor and value > 1e-12 for value in envelope) * max(1, rate // 20) / rate
    drift = window_audit(reference, test, rate, lag, structural=False)
    structural = window_audit(reference, test, rate, round(lag + fractional), structural=True) if fractional is not None else {
        "window_count": topology.STRUCTURAL_WINDOW_COUNT, "valid_window_count": 0,
        "invalid_reasons": {}, "clock_drift_ppm": None, "residual_samples": None,
        "minimum_correlation": None, "reason": "fractional_peak_unavailable",
    }
    trim = len(reference) + len(test) - 2 * frames
    diagnostics.update({"integer_delay_samples": lag, "fractional_delay_samples": fractional, "ambiguity_margin": margin,
                        "aligned_frames": frames, "active_seconds": active, "edge_trim_seconds": trim / rate,
                        "correlation": sampled[lag].record(), "gain": gain, "drift": drift, "structural": structural})
    if fractional is None:
        reasons.append("fractional_peak_unavailable")
    if margin is None:
        reasons.append("ambiguity_margin_unavailable")
    elif margin < legacy.MIN_AMBIGUITY_MARGIN:
        reasons.append("ambiguous_alignment_peak")
    if active < minimum_active:
        reasons.append("insufficient_active_audio")
    if sampled[lag].magnitude < legacy.MIN_ALIGNMENT_CORRELATION:
        reasons.append("low_alignment_correlation")
    for name, audit in (("drift", drift), ("structural", structural)):
        if audit["reason"] is not None:
            reasons.append(f"{name}_windows_unavailable")
        elif audit["minimum_correlation"] < legacy.MIN_ALIGNMENT_CORRELATION:
            reasons.append("low_alignment_correlation" if name == "drift" else "low_structural_window_correlation")
    if drift["clock_drift_ppm"] is not None and abs(drift["clock_drift_ppm"]) > legacy.MAX_CLOCK_DRIFT_PPM:
        reasons.append("clock_drift_exceeds_limit")
    if drift["residual_samples"] is not None and drift["residual_samples"] > legacy.MAX_NONLINEAR_DRIFT_RESIDUAL_SAMPLES:
        reasons.append("nonlinear_drift")
    if structural["residual_samples"] is not None and structural["residual_samples"] > topology.MAX_STRUCTURAL_RESIDUAL_SAMPLES:
        reasons.append("structural_edit_suspected")
    if gain["reason"] is not None:
        reasons.append("gain_or_polarity_unavailable")
    elif abs(gain["observed_gain_db"]) > legacy.MAX_GAIN_ABS_DB:
        reasons.append("gain_exceeds_limit")
    if trim / rate > legacy.MAX_EDGE_TRIM_SECONDS or trim / min(len(reference), len(test)) > legacy.MAX_EDGE_TRIM_FRACTION:
        reasons.append("excessive_trim")
    return {"status": "unsupported" if reasons else "supported", "reasons": sorted(set(reasons)), "diagnostics": diagnostics}


def _complete(values: Sequence[float | None], operation) -> float | None:
    return operation(values) if values and all(value is not None for value in values) else None


def align_channels(
    *, reference_channels: Sequence[Sequence[float]], test_channels: Sequence[Sequence[float]],
    reference_channel_map: Sequence[str], test_channel_map: Sequence[str], sample_rate_hz: int,
    recipe_identity: str, minimum_active_seconds: float = 4.0, maximum_delay_seconds: float = 2.0,
) -> dict[str, Any]:
    """Emit only score-free diagnostics with explicit missing values and reasons."""
    if type(sample_rate_hz) is not int or sample_rate_hz < 1 or any(not _number(value) or value <= 0 for value in (minimum_active_seconds, maximum_delay_seconds)):
        raise ValueError("alignment configuration differs")
    if not isinstance(recipe_identity, str) or not recipe_identity:
        raise ValueError("recipe identity differs")
    reasons = []
    if not topology._valid_shape(reference_channels) or not topology._valid_shape(test_channels):
        reasons.append("invalid_channel_shape")
    ref_map, test_map = tuple(reference_channel_map), tuple(test_channel_map)
    if ref_map not in topology.SUPPORTED_CHANNEL_MAPS or test_map not in topology.SUPPORTED_CHANNEL_MAPS:
        reasons.append("unsupported_channel_map")
    if len(reference_channels) != len(test_channels):
        reasons.append("channel_topology_mismatch")
    if ref_map != test_map or len(ref_map) != len(reference_channels) or len(test_map) != len(test_channels):
        reasons.append("channel_map_mismatch")
    channels = []
    if not reasons:
        channels = [{"channel": name, **_channel(ref, tst, sample_rate_hz, minimum_active_seconds, maximum_delay_seconds)} for name, ref, tst in zip(ref_map, reference_channels, test_channels, strict=True)]
        reasons.extend(reason for channel in channels for reason in channel["reasons"])
    diagnostics = [channel["diagnostics"] for channel in channels]
    total_lags = [item["integer_delay_samples"] + item["fractional_delay_samples"] if item["integer_delay_samples"] is not None and item["fractional_delay_samples"] is not None else None for item in diagnostics]
    common = _complete(total_lags, lambda values: math.fsum(values) / len(values))
    spread = _complete(total_lags, lambda values: max(values) - min(values))
    if spread is not None and spread > topology.MAX_CHANNEL_LAG_DISAGREEMENT_SAMPLES:
        reasons.append("channel_alignment_disagreement")
    summary = {
        "integer_delay_samples": math.floor(common + 0.5) if common is not None else None,
        "fractional_delay_samples": common - math.floor(common + 0.5) if common is not None else None,
        "channel_lag_spread_samples": spread,
        "minimum_correlation": _complete([item["correlation"]["magnitude"] if item["correlation"] else None for item in diagnostics], min),
        "minimum_structural_window_correlation": _complete([item["structural"]["minimum_correlation"] if item["structural"] else None for item in diagnostics], min),
        "clock_drift_ppm": _complete([item["drift"]["clock_drift_ppm"] if item["drift"] else None for item in diagnostics], lambda values: math.fsum(values) / len(values)),
        "aligned_frames": _complete([item["aligned_frames"] for item in diagnostics], min),
        "active_seconds": _complete([item["active_seconds"] for item in diagnostics], min),
    }
    return {"schema_version": 1, "record_kind": RECORD_KIND, "case_id": legacy.case_id(recipe_identity),
            "status": "unsupported" if reasons else "supported", "public_verdict_enabled": False,
            "input": {"sample_rate_hz": sample_rate_hz, "reference": topology._side(reference_channels, reference_channel_map), "test": topology._side(test_channels, test_channel_map)},
            "alignment": {"summary": summary, "channels": channels},
            "support": {"reasons": sorted(set(reasons)), "limits_id": LIMITS_ID,
                        "predecessor_limits_ids": [legacy.LIMITS_ID, topology.LIMITS_ID]},
            "sample_correction_applied": False, "perceptual_claim": False}
