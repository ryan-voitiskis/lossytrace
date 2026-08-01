#!/usr/bin/env python3
"""Development helpers for the verified-MP3 two-grid v29 policy.

This module is research-only. Feature version 0 and the public verdict remain
disabled until a frozen successor passes a new external-transfer gate and the
separate release gate.
"""

from __future__ import annotations

import math


PROFILE = "verified-mp3-two-grid-v29"
POLICY_ID = "verified-mp3-two-grid-edge-v29"
DEVELOPMENT_CANDIDATE_ID = "verified-mp3-two-grid-edge-v29-development"

MP3_VERIFICATION_MEDIAN_THRESHOLD = 3.0
VORBIS_AGGREGATE_THRESHOLD = 2.0
RELATIVE_MEDIAN_THRESHOLD = -0.75
EDGE_DROP_THRESHOLD_DB = 3.0
EDGE_PERSISTENCE_THRESHOLD = 0.0015

MP3_VERIFICATION_MINIMUM_AUDIO_BLOCK_COUNT = 3
MP3_VERIFICATION_MAXIMUM_AUDIO_BLOCK_COUNT = 4
MP3_VERIFICATION_FRAMES_PER_PHASE = 16
MP3_VERIFICATION_CONTROL_PHASE_STRIDE = 24

MINIMUM_ACTIVE_BIN_FRACTION = 0.075
MINIMUM_HIGH_BAND_FRAMES = 32
MINIMUM_HIGH_BAND_FRAME_RATIO = 0.06
ACTIVE_BIN_REFERENCE_SAMPLE_RATE_HZ = 44_100
LOW_UPPER_BAND_POWER_SHARE = 0.000001
LOW_EDGE_DROP_DB = 20.0
LOW_EDGE_PERSISTENCE = 0.2
LOW_EDGE_UPPER_POWER_SHARE = 0.00001


def contract() -> dict:
    return {
        "candidate_id": DEVELOPMENT_CANDIDATE_ID,
        "candidate_frozen": False,
        "policy_id": POLICY_ID,
        "transform_profile": PROFILE,
        "feature_version": 0,
        "public_verdict_enabled": False,
        "support_policy": {
            "id": "sample_rate_normalized_support_v3",
            "minimum_active_bin_fraction": MINIMUM_ACTIVE_BIN_FRACTION,
            "active_bin_reference_sample_rate_hz": (
                ACTIVE_BIN_REFERENCE_SAMPLE_RATE_HZ
            ),
            "minimum_high_band_frames": MINIMUM_HIGH_BAND_FRAMES,
            "minimum_high_band_frame_ratio": (
                MINIMUM_HIGH_BAND_FRAME_RATIO
            ),
            "low_upper_band_power_share_exclusive": (
                LOW_UPPER_BAND_POWER_SHARE
            ),
            "low_edge_drop_db_inclusive": LOW_EDGE_DROP_DB,
            "low_edge_persistence_inclusive": LOW_EDGE_PERSISTENCE,
            "low_edge_upper_power_share_exclusive": (
                LOW_EDGE_UPPER_POWER_SHARE
            ),
        },
        "thresholds": {
            "mp3_verification_peak_z_median_exclusive": (
                MP3_VERIFICATION_MEDIAN_THRESHOLD
            ),
            "mp3_verification_phase_distance_inclusive": (
                "candidate_radius_samples"
            ),
            "vorbis_aggregate_peak_z_exclusive": (
                VORBIS_AGGREGATE_THRESHOLD
            ),
            "relative_median_exclusive": RELATIVE_MEDIAN_THRESHOLD,
            "spectral_edge_drop_db_exclusive": EDGE_DROP_THRESHOLD_DB,
            "spectral_edge_persistence_inclusive": (
                EDGE_PERSISTENCE_THRESHOLD
            ),
        },
        "verification_contract": {
            "emission": (
                "optional when fewer than three complete measurable "
                "regions remain"
            ),
            "minimum_audio_block_count": (
                MP3_VERIFICATION_MINIMUM_AUDIO_BLOCK_COUNT
            ),
            "maximum_audio_block_count": (
                MP3_VERIFICATION_MAXIMUM_AUDIO_BLOCK_COUNT
            ),
            "frames_per_phase": MP3_VERIFICATION_FRAMES_PER_PHASE,
            "control_phase_stride_samples": (
                MP3_VERIFICATION_CONTROL_PHASE_STRIDE
            ),
        },
        "branches": {
            "mp3_verified": (
                "persistent spectral edge AND MP3 discovery phase "
                "independently reidentified within the candidate radius "
                "AND regional median confirmation above threshold"
            ),
            "vorbis_aggregate": (
                "persistent spectral edge AND Vorbis-grid aggregate peak"
            ),
            "relative_median": (
                "persistent spectral edge AND MP3-minus-Vorbis median "
                "phase-peak contrast"
            ),
        },
        "positive_reason_families": [
            "persistent_spectral_edge",
            "transform_frame_periodicity",
        ],
        "evidence_status": (
            "Observed development evidence only. A new provenance-locked "
            "external-transfer gate is required before any transfer claim."
        ),
    }


def support(runner: dict, low_bandwidth: dict) -> dict:
    if runner.get("feature_version") != 0:
        raise ValueError("runner feature version differs")
    compression = runner.get("compression_trace")
    source_facts = runner.get("source_facts")
    if not isinstance(compression, dict) or not isinstance(source_facts, dict):
        raise ValueError("runner support inputs are missing")
    if low_bandwidth.get("supported") is not True:
        return {
            "signal_supported": False,
            "failures": [
                "low_bandwidth_probe_unsupported",
                str(
                    low_bandwidth.get(
                        "support_reason",
                        "unknown_low_bandwidth_probe_failure",
                    )
                ),
            ],
            "measurements": {},
        }

    active_frames = int(compression["active_frame_count"])
    high_frames = int(compression["high_band_supported_frame_count"])
    high_ratio = high_frames / active_frames if active_frames else 0.0
    raw_active_bins = compression.get("median_active_bin_fraction")
    source_rate = int(source_facts["sample_rate_hz"])
    normalized_active_bins = (
        float(raw_active_bins)
        * source_rate
        / ACTIVE_BIN_REFERENCE_SAMPLE_RATE_HZ
        if raw_active_bins is not None
        else None
    )
    failures: list[str] = []
    if (
        normalized_active_bins is None
        or normalized_active_bins < MINIMUM_ACTIVE_BIN_FRACTION
    ):
        failures.append("insufficient_active_bin_fraction")
    if high_frames < MINIMUM_HIGH_BAND_FRAMES:
        failures.append("insufficient_high_band_frames")
    if high_ratio < MINIMUM_HIGH_BAND_FRAME_RATIO:
        failures.append("insufficient_high_band_supported_frame_ratio")

    declared_rate = int(low_bandwidth["declared_sample_rate_hz"])
    if declared_rate < 32_000:
        failures.append("declared_low_sample_rate")
    upper_share = float(low_bandwidth["power_share_10_20khz"])
    if not math.isfinite(upper_share) or upper_share < 0.0:
        raise ValueError("invalid upper-band power share")
    if upper_share < LOW_UPPER_BAND_POWER_SHARE:
        failures.append("upper_band_power_below_minus_60_db")
    low_edge_drop = low_bandwidth.get("low_edge_drop_db")
    low_edge_persistence = low_bandwidth.get("low_edge_persistence")
    if (
        low_edge_drop is not None
        and low_edge_persistence is not None
        and float(low_edge_drop) >= LOW_EDGE_DROP_DB
        and float(low_edge_persistence) >= LOW_EDGE_PERSISTENCE
        and upper_share < LOW_EDGE_UPPER_POWER_SHARE
    ):
        failures.append("persistent_low_bandwidth_edge")

    return {
        "signal_supported": not failures,
        "failures": failures,
        "measurements": {
            "active_frame_count": active_frames,
            "high_band_supported_frame_count": high_frames,
            "high_band_supported_frame_ratio": high_ratio,
            "normalized_active_bin_fraction": normalized_active_bins,
            "declared_sample_rate_hz": declared_rate,
            "power_share_10_20khz": upper_share,
            "low_edge_drop_db": low_edge_drop,
            "low_edge_persistence": low_edge_persistence,
        },
    }


def _circular_distance(
    left: int,
    right: int,
    period: int,
) -> int:
    if period <= 0 or not 0 <= left < period or not 0 <= right < period:
        raise ValueError("invalid circular phase")
    direct = abs(left - right)
    return min(direct, period - direct)


def assess(runner: dict, low_bandwidth: dict) -> dict:
    support_result = support(runner, low_bandwidth)
    if not support_result["signal_supported"]:
        return {
            **support_result,
            "predicted_positive": False,
            "branches": [],
            "reason_families": [],
            "assessment": "inconclusive",
        }

    if runner.get("research_transform_grid_profile") != PROFILE:
        raise ValueError("runner transform profile differs")
    profiles = runner.get("transform_grid_probe")
    if not isinstance(profiles, dict):
        raise ValueError("runner transform probe is missing")
    if (
        profiles.get("opus_long_celt") is not None
        or profiles.get("opus_short_celt") is not None
    ):
        raise ValueError("verified two-grid profile unexpectedly ran Opus")
    mp3 = profiles.get("mp3_long_sine")
    vorbis = profiles.get("long_vorbis")
    if not isinstance(mp3, dict) or not isinstance(vorbis, dict):
        raise ValueError("verified two-grid output is missing")
    verification = mp3.get("multi_candidate_phase_verification")
    if isinstance(verification, dict) and (
        int(verification["audio_block_count"])
        < MP3_VERIFICATION_MINIMUM_AUDIO_BLOCK_COUNT
        or int(verification["audio_block_count"])
        > MP3_VERIFICATION_MAXIMUM_AUDIO_BLOCK_COUNT
        or int(verification["frames_per_phase"])
        != MP3_VERIFICATION_FRAMES_PER_PHASE
        or int(verification["control_phase_stride_samples"])
        != MP3_VERIFICATION_CONTROL_PHASE_STRIDE
    ):
        raise ValueError("MP3 phase verification contract differs")
    if verification is not None and not isinstance(verification, dict):
        raise ValueError("MP3 phase verification has invalid shape")

    compression = runner["compression_trace"]
    edge_drop = compression.get("spectral_edge_drop_db")
    edge_persistence = compression.get("spectral_edge_persistence")
    branches: list[str] = []
    if (
        edge_drop is not None
        and edge_persistence is not None
        and float(edge_drop) > EDGE_DROP_THRESHOLD_DB
        and float(edge_persistence) >= EDGE_PERSISTENCE_THRESHOLD
    ):
        if isinstance(verification, dict):
            block_samples = int(mp3["block_samples"])
            phase_distance = _circular_distance(
                int(verification["discovery_aggregate_phase_samples"]),
                int(verification["verified_phase_samples"]),
                block_samples,
            )
            if (
                float(verification["peak_z_median"])
                > MP3_VERIFICATION_MEDIAN_THRESHOLD
                and phase_distance
                <= int(verification["candidate_radius_samples"])
            ):
                branches.append("mp3_verified")
        if (
            float(vorbis["long_block_phase_aggregate_peak_z"])
            > VORBIS_AGGREGATE_THRESHOLD
        ):
            branches.append("vorbis_aggregate")
        if (
            float(mp3["long_block_phase_peak_z_median"])
            - float(vorbis["long_block_phase_peak_z_median"])
            < RELATIVE_MEDIAN_THRESHOLD
        ):
            branches.append("relative_median")

    predicted = bool(branches)
    return {
        **support_result,
        "predicted_positive": predicted,
        "branches": branches,
        "reason_families": (
            [
                "persistent_spectral_edge",
                "transform_frame_periodicity",
            ]
            if predicted
            else []
        ),
        "assessment": (
            "likely_lossy_derived"
            if predicted
            else "no_lossy_signature_detected"
        ),
    }
