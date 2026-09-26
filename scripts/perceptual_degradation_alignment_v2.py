#!/usr/bin/env python3
"""Topology-aware score-free alignment for perceptual-degradation research."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import perceptual_degradation_alignment as mono


SUPPORTED_CHANNEL_MAPS = {("M",), ("L", "R")}
MAX_CHANNEL_LAG_DISAGREEMENT_SAMPLES = 1.0
STRUCTURAL_WINDOW_COUNT = 7
STRUCTURAL_SEARCH_SECONDS = 0.10
MAX_STRUCTURAL_RESIDUAL_SAMPLES = 1.5
LIMITS_ID = "perceptual-degradation-v1-topology-fixtures-20260803-001"


def _valid_shape(channels: Sequence[Sequence[float]]) -> bool:
    if not channels or len(channels) not in (1, 2):
        return False
    frame_count = len(channels[0])
    return frame_count > 0 and all(len(channel) == frame_count for channel in channels)


def _side(
    channels: Sequence[Sequence[float]], channel_map: Sequence[str]
) -> dict[str, Any]:
    return {
        "channel_count": len(channels),
        "channel_map": list(channel_map),
        "frames": len(channels[0]) if channels else 0,
    }


def _empty_alignment() -> dict[str, Any]:
    return {
        "integer_delay_samples": 0,
        "fractional_delay_samples": 0.0,
        "clock_drift_ppm": 0.0,
        "aligned_frames": 0,
        "active_seconds": 0.0,
        "minimum_correlation": 0.0,
        "minimum_ambiguity_margin": 0.0,
        "edge_trim_seconds": 0.0,
        "channel_lag_spread_samples": 0.0,
        "structural_residual_samples": 0.0,
        "minimum_structural_window_correlation": 0.0,
        "channels": [],
    }


def _unsupported_topology(
    *,
    reference_channels: Sequence[Sequence[float]],
    test_channels: Sequence[Sequence[float]],
    reference_channel_map: Sequence[str],
    test_channel_map: Sequence[str],
    sample_rate_hz: int,
    recipe_identity: str,
    reasons: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "record_kind": "perceptual_degradation_alignment_v2",
        "case_id": mono.case_id(recipe_identity),
        "status": "unsupported",
        "public_verdict_enabled": False,
        "input": {
            "sample_rate_hz": sample_rate_hz,
            "reference": _side(reference_channels, reference_channel_map),
            "test": _side(test_channels, test_channel_map),
        },
        "alignment": _empty_alignment(),
        "support": {"reasons": sorted(set(reasons)), "limits_id": LIMITS_ID},
    }


def _structural_audit(
    reference: Sequence[float],
    test: Sequence[float],
    sample_rate_hz: int,
    global_lag: int,
) -> tuple[float, float]:
    start_reference, _, aligned = mono._overlap(len(reference), len(test), global_lag)
    if aligned < sample_rate_hz:
        return 0.0, -1.0
    half_window = min(sample_rate_hz // 4, aligned // (STRUCTURAL_WINDOW_COUNT * 3))
    radius = max(2, math.ceil(sample_rate_hz * STRUCTURAL_SEARCH_SECONDS))
    positions = [
        start_reference + int(aligned * (index + 1) / (STRUCTURAL_WINDOW_COUNT + 1))
        for index in range(STRUCTURAL_WINDOW_COUNT)
    ]
    points = [
        (
            position,
            *mono._local_lag(
                reference,
                test,
                global_lag,
                position,
                half_window,
                radius,
            ),
        )
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
    residual = max(
        abs(point[1] - (intercept + slope * point[0])) for point in points
    )
    return residual, min(point[2] for point in points)


def align_channels(
    *,
    reference_channels: Sequence[Sequence[float]],
    test_channels: Sequence[Sequence[float]],
    reference_channel_map: Sequence[str],
    test_channel_map: Sequence[str],
    sample_rate_hz: int,
    recipe_identity: str,
    minimum_active_seconds: float = 4.0,
    maximum_delay_seconds: float = 2.0,
) -> dict[str, Any]:
    """Align mono or stereo channels without computing a perceptual score."""

    if sample_rate_hz < 1:
        raise ValueError("sample rate must be positive")
    reasons: list[str] = []
    if not _valid_shape(reference_channels) or not _valid_shape(test_channels):
        reasons.append("invalid_channel_shape")
    reference_map = tuple(reference_channel_map)
    test_map = tuple(test_channel_map)
    if reference_map not in SUPPORTED_CHANNEL_MAPS or test_map not in SUPPORTED_CHANNEL_MAPS:
        reasons.append("unsupported_channel_map")
    if len(reference_channels) != len(test_channels):
        reasons.append("channel_topology_mismatch")
    if reference_map != test_map:
        reasons.append("channel_map_mismatch")
    if len(reference_map) != len(reference_channels) or len(test_map) != len(test_channels):
        reasons.append("channel_map_mismatch")
    if reasons:
        return _unsupported_topology(
            reference_channels=reference_channels,
            test_channels=test_channels,
            reference_channel_map=reference_channel_map,
            test_channel_map=test_channel_map,
            sample_rate_hz=sample_rate_hz,
            recipe_identity=recipe_identity,
            reasons=reasons,
        )

    channel_records = [
        mono.align_mono(
            reference=reference,
            test=test,
            sample_rate_hz=sample_rate_hz,
            recipe_identity=f"{recipe_identity}\0channel-{index}",
            minimum_active_seconds=minimum_active_seconds,
            maximum_delay_seconds=maximum_delay_seconds,
        )
        for index, (reference, test) in enumerate(
            zip(reference_channels, test_channels, strict=True)
        )
    ]
    channel_summaries = [record["alignment"] for record in channel_records]
    reasons.extend(
        reason
        for record in channel_records
        for reason in record["support"]["reasons"]
    )
    total_lags = [
        summary["integer_delay_samples"] + summary["fractional_delay_samples"]
        for summary in channel_summaries
    ]
    lag_spread = max(total_lags) - min(total_lags)
    if lag_spread > MAX_CHANNEL_LAG_DISAGREEMENT_SAMPLES:
        reasons.append("channel_alignment_disagreement")

    structural = [
        _structural_audit(reference, test, sample_rate_hz, round(total_lag))
        for reference, test, total_lag in zip(
            reference_channels, test_channels, total_lags, strict=True
        )
    ]
    structural_residual = max(value[0] for value in structural)
    minimum_structural_correlation = min(value[1] for value in structural)
    if structural_residual > MAX_STRUCTURAL_RESIDUAL_SAMPLES:
        reasons.append("structural_edit_suspected")
    if minimum_structural_correlation < mono.MIN_ALIGNMENT_CORRELATION:
        reasons.append("low_structural_window_correlation")

    common_lag = math.fsum(total_lags) / len(total_lags)
    common_integer = math.floor(common_lag + 0.5)
    common_fractional = common_lag - common_integer
    return {
        "schema_version": 1,
        "record_kind": "perceptual_degradation_alignment_v2",
        "case_id": mono.case_id(recipe_identity),
        "status": "unsupported" if reasons else "supported",
        "public_verdict_enabled": False,
        "input": {
            "sample_rate_hz": sample_rate_hz,
            "reference": _side(reference_channels, reference_channel_map),
            "test": _side(test_channels, test_channel_map),
        },
        "alignment": {
            "integer_delay_samples": common_integer,
            "fractional_delay_samples": common_fractional,
            "clock_drift_ppm": math.fsum(
                summary["clock_drift_ppm"] for summary in channel_summaries
            )
            / len(channel_summaries),
            "aligned_frames": min(
                summary["aligned_frames"] for summary in channel_summaries
            ),
            "active_seconds": min(
                summary["active_seconds"] for summary in channel_summaries
            ),
            "minimum_correlation": min(
                summary["correlation"] for summary in channel_summaries
            ),
            "minimum_ambiguity_margin": min(
                summary["ambiguity_margin"] for summary in channel_summaries
            ),
            "edge_trim_seconds": max(
                summary["edge_trim_seconds"] for summary in channel_summaries
            ),
            "channel_lag_spread_samples": lag_spread,
            "structural_residual_samples": structural_residual,
            "minimum_structural_window_correlation": minimum_structural_correlation,
            "channels": [
                {
                    "channel": channel,
                    "integer_delay_samples": summary["integer_delay_samples"],
                    "fractional_delay_samples": summary["fractional_delay_samples"],
                    "observed_gain_db": summary["observed_gain_db"],
                    "polarity": summary["polarity"],
                    "correlation": summary["correlation"],
                }
                for channel, summary in zip(
                    reference_channel_map, channel_summaries, strict=True
                )
            ],
        },
        "support": {"reasons": sorted(set(reasons)), "limits_id": LIMITS_ID},
    }
