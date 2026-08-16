#!/usr/bin/env python3
"""Run the authorized score-free ODAQ retained-reference drift validation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Sequence


for variable in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[variable] = "1"

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

PLAN = (
    ROOT
    / "benchmarks/perceptual-degradation-v1"
    / "odaq-retained-drift-validation-execution-plan.json"
)
AUTHORIZATION = (
    ROOT
    / "benchmarks/perceptual-degradation-v1"
    / "odaq-retained-drift-validation-authorization-20260816.json"
)
READINESS_SCRIPT = SCRIPTS / "perceptual_degradation_odaq_retained_drift_validation_readiness.py"
DELIVERY_RUNNER = SCRIPTS / "run-perceptual-degradation-odaq-delivery.py"
PROJECTION_SCRIPT = SCRIPTS / "prepare-perceptual-degradation-odaq-delivery.py"
ESTIMATOR_SCRIPT = SCRIPTS / "perceptual_degradation_oracle_drift_estimator_integration.py"
AUTHORIZATION_HEAD = "5eb9e31a9fa12bad1e90a8c4d924765db8e91932"
AUTHORIZATION_CI_URL = "https://github.com/ryan-voitiskis/lossytrace/actions/runs/31919169130"
MINIMUM_FREE_BYTES = 15 * 1024**3
REPORT_FLOAT_PLACES = 12


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


READINESS = load_module("odaq_retained_drift_readiness", READINESS_SCRIPT)
DELIVERY = load_module("odaq_private_delivery_runner", DELIVERY_RUNNER)
PROJECT = load_module("odaq_delivery_projection", PROJECTION_SCRIPT)
ESTIMATOR = load_module("odaq_frozen_drift_estimator", ESTIMATOR_SCRIPT)
TECHNICAL = ESTIMATOR.technical
RESAMPLER = ESTIMATOR.resampler
ALIGNMENT = ESTIMATOR.alignment
ORACLE = ESTIMATOR.oracle


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside_repository(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


def atomic_json(path: Path, value: Any) -> None:
    partial = path.with_name(f"{path.name}.partial")
    with partial.open("wb") as output:
        output.write(canonical_bytes(value))
        output.flush()
        os.fsync(output.fileno())
    partial.replace(path)
    path.chmod(0o600)


def require_committed_authorization(
    authorization_path: Path = AUTHORIZATION,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    plan = load_json(PLAN)
    plan_errors = READINESS.validate_plan(plan)
    authorization = load_json(authorization_path)
    errors = plan_errors + READINESS.validate_authorization(
        authorization, plan, PLAN
    )
    if errors:
        raise ValueError("authorization validation failed: " + "; ".join(errors))
    relative = authorization_path.resolve().relative_to(ROOT.resolve())
    completed = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_HEAD}:{relative}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if completed.returncode or completed.stdout != authorization_path.read_bytes():
        raise ValueError("authorization is not exact at the green authorization head")
    return authorization, plan, sha256_file(authorization_path)


def load_numpy() -> Any:
    try:
        import numpy  # type: ignore[import-not-found]
    except ImportError as error:
        raise ValueError(
            "live retained validation requires the single-threaded NumPy proxy backend"
        ) from error
    return numpy


def decode_canonical_segment(value: bytes, frame_count: int) -> list[list[float]]:
    chunks = dict(PROJECT._chunks(value))
    fmt = chunks.get(b"fmt ")
    payload = chunks.get(b"data")
    if fmt is None or payload is None or len(fmt) != 16:
        raise ValueError("canonical PCM projection geometry differs")
    format_tag, channels, sample_rate, byte_rate, block_align, bits = struct.unpack(
        "<HHIIHH", fmt
    )
    if (
        format_tag != 1
        or channels != 2
        or sample_rate != 48_000
        or bits not in {24, 32}
        or block_align != channels * (bits // 8)
        or byte_rate != sample_rate * block_align
        or len(payload) < frame_count * block_align
    ):
        raise ValueError("canonical PCM projection geometry differs")
    channels_out = [[], []]
    if bits == 32:
        scale = float(1 << 31)
        samples = struct.iter_unpack("<i", payload[: frame_count * block_align])
        for index, (sample,) in enumerate(samples):
            channels_out[index & 1].append(sample / scale)
    else:
        scale = float(1 << 23)
        sample_bytes = payload[: frame_count * block_align]
        for index in range(frame_count * channels):
            offset = index * 3
            raw = int.from_bytes(sample_bytes[offset : offset + 3], "little")
            if raw & 0x800000:
                raw -= 1 << 24
            channels_out[index & 1].append(raw / scale)
    if any(len(channel) != frame_count for channel in channels_out):
        raise ValueError("decoded canonical PCM segment differs")
    return channels_out


def project_source_segment(source_path: Path, source: dict[str, Any], frames: int) -> list[list[float]]:
    value = source_path.read_bytes()
    if len(value) != source["byte_length"] or sha256_bytes(value) != source["sha256"]:
        raise ValueError("retained source changed after inventory verification")
    projected, projection = PROJECT.project_delivery_wav(value)
    if (
        projection["frame_count"] != source["pcm_geometry"]["frame_count"]
        or projection["sample_rate_hz"] != 48_000
        or projection["channel_count"] != 2
        or projection["dither_applied"]
        or projection["gain_applied"]
        or projection["normalization_applied"]
        or projection["resampling_applied"]
        or projection["channel_transform_applied"]
    ):
        raise ValueError("canonical source projection differs")
    channels = decode_canonical_segment(projected, frames)
    del projected
    del value
    return channels


def correlation(left: Sequence[float], right: Sequence[float], start: int, end: int) -> float:
    if end > min(len(left), len(right)) or end <= start:
        raise ValueError("correlation window differs")
    dot = math.fsum(left[index] * right[index] for index in range(start, end))
    left_energy = math.fsum(left[index] ** 2 for index in range(start, end))
    right_energy = math.fsum(right[index] ** 2 for index in range(start, end))
    if left_energy <= 0.0 or right_energy <= 0.0:
        raise ValueError("correlation window energy differs")
    return dot / math.sqrt(left_energy * right_energy)


def window_rms(values: Sequence[float], start: int, end: int) -> float:
    if end > len(values) or end <= start:
        raise ValueError("energy window differs")
    return math.sqrt(
        math.fsum(values[index] ** 2 for index in range(start, end)) / (end - start)
    )


def eligible_windows(
    reference: Sequence[Sequence[float]], protocol: dict[str, Any]
) -> tuple[list[list[int]], list[list[int]]]:
    windows = [
        (start, start + protocol["window_frame_count"])
        for start in protocol["window_start_frames"]
    ]
    eligible = [
        [
            position
            for position, (start, end) in enumerate(windows)
            if window_rms(channel, start, end)
            >= protocol["minimum_channel_window_rms"]
        ]
        for channel in reference
    ]
    training = [
        [position for position in positions if position in protocol["training_window_positions"]]
        for positions in eligible
    ]
    held_out = [
        [position for position in positions if position in protocol["held_out_window_positions"]]
        for positions in eligible
    ]
    return training, held_out


def apply_drift_scalar(values: Sequence[float], drift_ppm: int) -> list[float]:
    return TECHNICAL.apply_synthetic_drift(values, drift_ppm)


def proxy_scalar(values: Sequence[float], output_frames: int, correction_ppm: int) -> list[float]:
    return TECHNICAL.correct_synthetic_drift(values, output_frames, correction_ppm)


def proxy_numpy(np: Any, values: Sequence[float], output_frames: int, correction_ppm: int) -> Any:
    source = np.asarray(values, dtype=np.float64)
    ratio = 1.0 + correction_ppm / 1_000_000.0
    positions = np.arange(output_frames, dtype=np.float64) * ratio
    return np.interp(
        positions,
        np.arange(len(source), dtype=np.float64),
        source,
        left=0.0,
        right=0.0,
    )


def mean_masked_correlation_scalar(
    reference: Sequence[Sequence[float]],
    test: Sequence[Sequence[float]],
    protocol: dict[str, Any],
    positions_by_channel: Sequence[Sequence[int]],
) -> float:
    windows = [
        (start, start + protocol["window_frame_count"])
        for start in protocol["window_start_frames"]
    ]
    values = [
        correlation(reference[channel], test[channel], *windows[position])
        for channel, positions in enumerate(positions_by_channel)
        for position in positions
    ]
    if not values:
        raise ValueError("eligible correlation inventory is empty")
    return math.fsum(values) / len(values)


def mean_masked_correlation_numpy(
    np: Any,
    reference: Sequence[Sequence[float]],
    test: Sequence[Sequence[float]],
    protocol: dict[str, Any],
    positions_by_channel: Sequence[Sequence[int]],
) -> float:
    values: list[float] = []
    size = protocol["window_frame_count"]
    for channel, positions in enumerate(positions_by_channel):
        left = np.asarray(reference[channel], dtype=np.float64)
        right = np.asarray(test[channel], dtype=np.float64)
        for position in positions:
            start = protocol["window_start_frames"][position]
            a = left[start : start + size]
            b = right[start : start + size]
            denominator = float(np.sqrt(np.dot(a, a) * np.dot(b, b)))
            if denominator <= 0.0:
                raise ValueError("correlation window energy differs")
            values.append(float(np.dot(a, b)) / denominator)
    if not values:
        raise ValueError("eligible correlation inventory is empty")
    return math.fsum(values) / len(values)


def reported(value: float) -> float:
    return round(float(value), REPORT_FLOAT_PLACES)


def estimate_decision(
    reference: Sequence[Sequence[float]],
    observed: Sequence[Sequence[float]],
    protocol: dict[str, Any],
    *,
    np: Any | None,
) -> tuple[dict[str, Any], Any | None]:
    training, held_out = eligible_windows(reference, protocol)
    support = {
        "eligible_training_window_count_by_channel": [len(value) for value in training],
        "eligible_held_out_window_count_by_channel": [len(value) for value in held_out],
        "abstention_reason": None,
    }
    if any(
        len(value) < protocol["minimum_eligible_training_windows_per_channel"]
        for value in training
    ) or any(
        len(value) < protocol["minimum_eligible_held_out_windows_per_channel"]
        for value in held_out
    ):
        support["abstention_reason"] = protocol["insufficient_energy_action"]
        return {
            "state": "abstained",
            "support": support,
            "selected_correction_ppm": None,
            "selection_mean_correlation": None,
            "selection_margin": None,
            "held_out_mean_correlation_before": None,
            "held_out_mean_correlation_after_proxy": None,
            "held_out_mean_correlation_improvement_proxy": None,
            "apply_correction": False,
            "selection_used_held_out_windows": False,
            "proxy_interpolator_is_frozen_resampler": False,
        }, None

    output_frames = len(reference[0])
    proxy_function: Callable[[Sequence[float], int, int], Any]
    mean_function: Callable[..., float]
    if np is None:
        proxy_function = proxy_scalar
        mean_function = mean_masked_correlation_scalar
    else:
        proxy_function = lambda values, frames, ppm: proxy_numpy(np, values, frames, ppm)
        mean_function = lambda ref, test, proto, positions: mean_masked_correlation_numpy(
            np, ref, test, proto, positions
        )
    scored: list[tuple[float, int]] = []
    for correction_ppm in range(
        protocol["candidate_drift_ppm_minimum"],
        protocol["candidate_drift_ppm_maximum"] + 1,
        protocol["candidate_drift_ppm_step"],
    ):
        proxy = [
            proxy_function(channel, output_frames, correction_ppm)
            for channel in observed
        ]
        score = reported(mean_function(reference, proxy, protocol, training))
        scored.append((score, correction_ppm))
    scored.sort(key=lambda row: (row[0], -abs(row[1]), -row[1]), reverse=True)
    selection_score, selected_ppm = scored[0]
    selected_proxy = [
        proxy_function(channel, output_frames, selected_ppm) for channel in observed
    ]
    selection_margin = reported(selection_score - scored[1][0])
    held_before = reported(mean_function(reference, observed, protocol, held_out))
    held_after = reported(mean_function(reference, selected_proxy, protocol, held_out))
    improvement = reported(held_after - held_before)
    apply_correction = (
        selected_ppm != 0
        and selection_margin >= protocol["minimum_selection_margin"]
        and held_after >= protocol["minimum_held_out_correlation_after_correction"]
        and improvement >= protocol["minimum_held_out_correlation_improvement_to_apply"]
    )
    return {
        "state": "supported",
        "support": support,
        "selected_correction_ppm": selected_ppm,
        "selection_mean_correlation": selection_score,
        "selection_margin": selection_margin,
        "held_out_mean_correlation_before": held_before,
        "held_out_mean_correlation_after_proxy": held_after,
        "held_out_mean_correlation_improvement_proxy": improvement,
        "apply_correction": apply_correction,
        "selection_used_held_out_windows": False,
        "proxy_interpolator_is_frozen_resampler": False,
    }, selected_proxy


def overlap_correlation(left: Sequence[float], right: Sequence[float]) -> float:
    length = min(len(left), len(right))
    return reported(correlation(left, right, 0, length))


def fast_sampled_cosine(np: Any, a: Sequence[float], b: Sequence[float], lag: int) -> float:
    start_a, start_b, length = ALIGNMENT.mono._overlap(len(a), len(b), lag)
    if length < 16:
        return -1.0
    stride = max(1, length // ALIGNMENT.mono.MAX_CORRELATION_SAMPLES)
    offsets = np.arange(0, length, stride, dtype=np.int64)
    left = np.asarray(a, dtype=np.float64)[start_a + offsets]
    right = np.asarray(b, dtype=np.float64)[start_b + offsets]
    denominator = float(np.sqrt(np.dot(left, left) * np.dot(right, right)))
    if denominator <= 0.0:
        return -1.0
    return float(np.dot(left, right)) / denominator


def fast_pearson(np: Any, a: Sequence[float], b: Sequence[float], lag: int) -> float:
    start_a, start_b, length = ALIGNMENT.mono._overlap(len(a), len(b), lag)
    if length < 4:
        return -1.0
    left = np.asarray(a, dtype=np.float64)[start_a : start_a + length]
    right = np.asarray(b, dtype=np.float64)[start_b : start_b + length]
    left = left - float(np.mean(left))
    right = right - float(np.mean(right))
    denominator = float(np.sqrt(np.dot(left, left) * np.dot(right, right)))
    if denominator <= 0.0:
        return -1.0
    return float(np.dot(left, right)) / denominator


def align_channels_vectorized(
    *,
    np: Any,
    reference_channels: Sequence[Sequence[float]],
    test_channels: Sequence[Sequence[float]],
    sample_rate_hz: int,
    recipe_identity: str,
) -> dict[str, Any]:
    """Run frozen alignment-v2 search with single-threaded vector reductions."""

    original_sampled = ALIGNMENT.mono._sampled_cosine_at_lag
    original_pearson = ALIGNMENT.mono._pearson_at_lag
    ALIGNMENT.mono._sampled_cosine_at_lag = (
        lambda a, b, lag: fast_sampled_cosine(np, a, b, lag)
    )
    ALIGNMENT.mono._pearson_at_lag = lambda a, b, lag: fast_pearson(np, a, b, lag)
    try:
        return ALIGNMENT.align_channels(
            reference_channels=reference_channels,
            test_channels=test_channels,
            reference_channel_map=["L", "R"],
            test_channel_map=["L", "R"],
            sample_rate_hz=sample_rate_hz,
            recipe_identity=recipe_identity,
        )
    finally:
        ALIGNMENT.mono._sampled_cosine_at_lag = original_sampled
        ALIGNMENT.mono._pearson_at_lag = original_pearson


def score_free_envelope(alignment: dict[str, Any]) -> dict[str, Any]:
    value = ORACLE.assemble_score_free(alignment)
    return {
        "result_state": value["result_state"],
        "metric_execution_states": [
            family["execution_state"] for family in value["metric_families"]
        ],
        "impairment_severity": value["outcomes"]["impairment_severity"],
        "audibility_probability": value["outcomes"]["audibility_probability"],
        "support": value["support"],
    }


def process_case(
    *,
    reference: Sequence[Sequence[float]],
    source_opaque_id: str,
    actual_ppm: int,
    protocol: dict[str, Any],
    candidate: dict[str, Any],
    table: Sequence[Sequence[int]],
    np: Any | None,
) -> dict[str, Any]:
    observed = [apply_drift_scalar(channel, actual_ppm) for channel in reference]
    decision, _ = estimate_decision(reference, observed, protocol, np=np)
    apply_correction = decision["apply_correction"]
    selected_ppm = decision["selected_correction_ppm"]
    if apply_correction:
        corrected = RESAMPLER.resample_channels(
            observed,
            output_frames=len(reference[0]),
            correction_ppm=selected_ppm,
            candidate=candidate,
            table=table,
        )
        resampler_invoked = True
    else:
        corrected = observed
        resampler_invoked = False
    input_bytes = RESAMPLER.pack_f64_channels(observed)
    output_bytes = RESAMPLER.pack_f64_channels(corrected)
    discard = protocol["mandatory_discard_frames_each_edge_when_applied"] if apply_correction else 0
    reference_core = [
        channel[discard : len(channel) - discard if discard else None]
        for channel in reference
    ]
    corrected_core = [
        channel[discard : len(channel) - discard if discard else None]
        for channel in corrected
    ]
    observed_core = [
        channel[discard : discard + len(reference_core[index])]
        for index, channel in enumerate(observed)
    ]
    metrics = [
        {
            "channel_index": index,
            "correlation_before": overlap_correlation(expected, before),
            "correlation_after": overlap_correlation(expected, after),
        }
        for index, (expected, before, after) in enumerate(
            zip(reference_core, observed_core, corrected_core, strict=True)
        )
    ]
    for metric in metrics:
        metric["correlation_improvement"] = reported(
            metric["correlation_after"] - metric["correlation_before"]
        )
    if np is None:
        aligned = ALIGNMENT.align_channels(
            reference_channels=reference_core,
            test_channels=corrected_core,
            reference_channel_map=["L", "R"],
            test_channel_map=["L", "R"],
            sample_rate_hz=protocol["source_sample_rate_hz"],
            recipe_identity=(
                f"{protocol['protocol_id']}\0{source_opaque_id}\0drift-{actual_ppm:+d}-ppm"
            ),
        )
    else:
        aligned = align_channels_vectorized(
            np=np,
            reference_channels=reference_core,
            test_channels=corrected_core,
            sample_rate_hz=protocol["source_sample_rate_hz"],
            recipe_identity=(
                f"{protocol['protocol_id']}\0{source_opaque_id}"
                f"\0drift-{actual_ppm:+d}-ppm"
            ),
        )
    envelope = score_free_envelope(aligned)
    return {
        "source_opaque_reference_id": source_opaque_id,
        "actual_drift_ppm": actual_ppm,
        "decision": decision,
        "resampler_invoked": resampler_invoked,
        "resampler_correction_applied": apply_correction,
        "mandatory_discard_frames_each_edge": discard,
        "reference_frame_count": len(reference[0]),
        "observed_frame_count": len(observed[0]),
        "output_frame_count": len(corrected[0]),
        "input_f64le_sha256": sha256_bytes(input_bytes),
        "output_f64le_sha256": sha256_bytes(output_bytes),
        "output_bit_exact_to_observed": output_bytes == input_bytes,
        "channel_core_metrics": metrics,
        "post_decision_alignment": {
            "status": aligned["status"],
            "reasons": aligned["support"]["reasons"],
            "clock_drift_ppm": reported(aligned["alignment"]["clock_drift_ppm"]),
            "minimum_correlation": reported(aligned["alignment"]["minimum_correlation"]),
            "edge_trim_seconds": reported(aligned["alignment"]["edge_trim_seconds"]),
        },
        "score_free_oracle": envelope,
        "retained_clean_reference_accessed": True,
        "derived_pcm_retained": False,
        "provider_processed_condition_accessed": False,
        "provider_listening_score_accessed": False,
        "actual_codec_generated": False,
        "perceptual_metric_executed": False,
        "human_playback_performed": False,
        "human_response_accessed": False,
        "sealed_evidence_opened": False,
        "no_reference_training_performed": False,
        "public_verdict_enabled": False,
    }


def gate_audit(cases: list[dict[str, Any]], plan: dict[str, Any]) -> dict[str, bool]:
    gates = plan["predeclared_future_gates"]
    protocol = plan["validation_protocol"]
    supported_nonzero = [
        case
        for case in cases
        if case["actual_drift_ppm"] != 0 and case["decision"]["state"] == "supported"
    ]
    supported_by_ppm = {
        ppm: sum(case["actual_drift_ppm"] == ppm for case in supported_nonzero)
        for ppm in protocol["actual_drift_ppm_cases"]
        if ppm != 0
    }
    errors = [
        abs(case["decision"]["selected_correction_ppm"] - case["actual_drift_ppm"])
        for case in supported_nonzero
    ]
    applied = [case for case in cases if case["decision"]["apply_correction"]]
    nonapplied = [case for case in cases if not case["decision"]["apply_correction"]]
    abstained = [case for case in cases if case["decision"]["state"] == "abstained"]
    score_free_closed = all(
        set(case["score_free_oracle"]["metric_execution_states"])
        <= {"not_authorized", "not_run_alignment_unsupported"}
        and case["score_free_oracle"]["impairment_severity"] is None
        and case["score_free_oracle"]["audibility_probability"] is None
        for case in cases
    )
    return {
        "all_16_sources_attempted": len({case["source_opaque_reference_id"] for case in cases}) == 16,
        "all_7_drift_cases_attempted_per_source": (
            len(cases) == 112
            and all(
                sum(case["source_opaque_reference_id"] == source for case in cases) == 7
                for source in {case["source_opaque_reference_id"] for case in cases}
            )
        ),
        "minimum_supported_sources_per_nonzero_drift_case": all(
            count >= gates["minimum_supported_sources_per_nonzero_drift_case"]
            for count in supported_by_ppm.values()
        ),
        "maximum_supported_estimation_absolute_error_ppm": (
            bool(errors)
            and max(errors) <= gates["maximum_supported_estimation_absolute_error_ppm"]
        ),
        "minimum_correct_estimate_rate_across_supported_nonzero_cases": (
            bool(errors)
            and sum(error <= gates["maximum_supported_estimation_absolute_error_ppm"] for error in errors)
            / len(errors)
            >= gates["minimum_correct_estimate_rate_across_supported_nonzero_cases"]
        ),
        "zero_drift_false_apply_count": not any(
            case["actual_drift_ppm"] == 0 and case["decision"]["apply_correction"]
            for case in cases
        ),
        "applied_case_minimum_post_correction_core_correlation_each_channel": all(
            metric["correlation_after"]
            >= gates["applied_case_minimum_post_correction_core_correlation_each_channel"]
            for case in applied
            for metric in case["channel_core_metrics"]
        ),
        "applied_case_minimum_core_correlation_improvement_each_channel": all(
            metric["correlation_improvement"]
            >= gates["applied_case_minimum_core_correlation_improvement_each_channel"]
            for case in applied
            for metric in case["channel_core_metrics"]
        ),
        "every_applied_case_must_meet_frozen_held_out_rule": all(
            case["decision"]["selection_margin"] >= protocol["minimum_selection_margin"]
            and case["decision"]["held_out_mean_correlation_after_proxy"]
            >= protocol["minimum_held_out_correlation_after_correction"]
            and case["decision"]["held_out_mean_correlation_improvement_proxy"]
            >= protocol["minimum_held_out_correlation_improvement_to_apply"]
            for case in applied
        ),
        "every_nonapplied_output_must_be_bit_exact": all(
            case["output_bit_exact_to_observed"] for case in nonapplied
        ),
        "every_abstention_must_have_predeclared_reason": all(
            case["decision"]["support"]["abstention_reason"]
            == protocol["insufficient_energy_action"]
            for case in abstained
        ),
        "score_free_oracle_must_remain_execution_blocked": score_free_closed,
        "derived_audio_must_not_be_retained": all(
            not case["derived_pcm_retained"] for case in cases
        ),
    }


def closed_surfaces_remain_closed(cases: Sequence[dict[str, Any]]) -> bool:
    return all(
        not case[key]
        for case in cases
        for key in (
            "provider_processed_condition_accessed",
            "provider_listening_score_accessed",
            "actual_codec_generated",
            "perceptual_metric_executed",
            "human_playback_performed",
            "human_response_accessed",
            "sealed_evidence_opened",
            "no_reference_training_performed",
            "public_verdict_enabled",
        )
    )


def require_case_prefix(
    cases: Sequence[dict[str, Any]],
    records: Sequence[dict[str, Any]],
    protocol: dict[str, Any],
) -> None:
    expected = [
        (source["opaque_reference_id"], actual_ppm)
        for source in records
        for actual_ppm in protocol["actual_drift_ppm_cases"]
    ]
    actual = [
        (case.get("source_opaque_reference_id"), case.get("actual_drift_ppm"))
        for case in cases
    ]
    if actual != expected[: len(actual)]:
        raise ValueError("private recovery case prefix differs")


def replay_journal(
    *,
    cases: Sequence[dict[str, Any]],
    authorization: dict[str, Any],
    authorization_sha256: str,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "state": "private_score_free_odaq_retained_drift_validation_in_progress",
        "protocol_id": protocol["protocol_id"],
        "authorization_id": authorization["authorization_id"],
        "authorization_sha256": authorization_sha256,
        "authorization_head_commit": AUTHORIZATION_HEAD,
        "input_inventory_sha256": authorization["authorization_scope"][
            "retained_inventory_sha256"
        ],
        "completed_case_count": len(cases),
        "cases": list(cases),
        "derived_audio_retained": False,
        "private_paths_included": False,
        "perceptual_metric_executed": False,
        "human_response_accessed": False,
        "public_verdict_enabled": False,
    }


def require_recovery_binding(
    value: dict[str, Any],
    *,
    authorization: dict[str, Any],
    authorization_sha256: str,
    protocol: dict[str, Any],
) -> list[dict[str, Any]]:
    expected = {
        "protocol_id": protocol["protocol_id"],
        "authorization_id": authorization["authorization_id"],
        "authorization_sha256": authorization_sha256,
        "authorization_head_commit": AUTHORIZATION_HEAD,
        "input_inventory_sha256": authorization["authorization_scope"][
            "retained_inventory_sha256"
        ],
    }
    if any(value.get(key) != expected_value for key, expected_value in expected.items()):
        raise ValueError("private recovery binding differs")
    cases = value.get("cases")
    if not isinstance(cases, list):
        raise ValueError("private recovery cases differ")
    return cases


def attribution_attachment(
    *,
    records: Sequence[dict[str, Any]],
    audit: dict[str, Any],
    authorization_sha256: str,
) -> dict[str, Any]:
    licence_records, _ = DELIVERY.attribution_context(audit)
    referenced_ids = sorted(
        {
            record_id
            for record in records
            for record_id in record["licence_record_ids"]
        }
    )
    return {
        "schema_version": 1,
        "state": "private_odaq_attribution_attached_out_of_band",
        "authorization_sha256": authorization_sha256,
        "attribution_audit": {
            "path": str(DELIVERY.ATTRIBUTION_AUDIT.relative_to(ROOT)),
            "sha256": sha256_file(DELIVERY.ATTRIBUTION_AUDIT),
        },
        "mappings": [
            {
                "source_opaque_reference_id": record["opaque_reference_id"],
                "licence_record_ids": record["licence_record_ids"],
            }
            for record in records
        ],
        "licence_records": [licence_records[record_id] for record_id in referenced_ids],
    }


def build_replay(
    *,
    source_root: Path,
    records: list[dict[str, Any]],
    plan: dict[str, Any],
    authorization: dict[str, Any],
    authorization_sha256: str,
    attribution_sha256: str,
    np: Any,
    existing_cases: Sequence[dict[str, Any]] = (),
    checkpoint: Callable[[Sequence[dict[str, Any]]], None] | None = None,
) -> dict[str, Any]:
    estimator_plan = ESTIMATOR.load_json(ESTIMATOR.PLAN_PATH)
    freeze = ESTIMATOR.load_json(ESTIMATOR._bound(estimator_plan, "resampler_freeze"))
    candidate = freeze["candidate"]
    table = RESAMPLER.coefficient_table(candidate)
    if sha256_bytes(RESAMPLER.coefficient_table_bytes(table)) != estimator_plan["correction"][
        "coefficient_table_sha256"
    ]:
        raise ValueError("frozen resampler coefficient table differs")
    protocol = plan["validation_protocol"]
    cases = list(existing_cases)
    require_case_prefix(cases, records, protocol)
    completed_pairs = {
        (case["source_opaque_reference_id"], case["actual_drift_ppm"])
        for case in cases
    }
    for source in records:
        remaining_ppm = [
            actual_ppm
            for actual_ppm in protocol["actual_drift_ppm_cases"]
            if (source["opaque_reference_id"], actual_ppm) not in completed_pairs
        ]
        if not remaining_ppm:
            continue
        if shutil.disk_usage(source_root).free < MINIMUM_FREE_BYTES:
            raise ValueError("free disk crossed the 15 GiB reserve")
        reference = project_source_segment(
            source_root / source["relative_path"],
            source,
            protocol["analysis_frame_count"],
        )
        for actual_ppm in remaining_ppm:
            cases.append(
                process_case(
                    reference=reference,
                    source_opaque_id=source["opaque_reference_id"],
                    actual_ppm=actual_ppm,
                    protocol=protocol,
                    candidate=candidate,
                    table=table,
                    np=np,
                )
            )
            if checkpoint is not None:
                checkpoint(cases)
        del reference
    gates = gate_audit(cases, plan)
    supported = [case for case in cases if case["decision"]["state"] == "supported"]
    applied = [case for case in cases if case["decision"]["apply_correction"]]
    return {
        "schema_version": 1,
        "state": "private_score_free_odaq_retained_drift_validation_replay_complete",
        "protocol_id": protocol["protocol_id"],
        "authorization_id": authorization["authorization_id"],
        "authorization_sha256": authorization_sha256,
        "authorization_head_commit": AUTHORIZATION_HEAD,
        "authorization_exact_head_ci_url": AUTHORIZATION_CI_URL,
        "attribution_attachment_sha256": attribution_sha256,
        "input_inventory_sha256": authorization["authorization_scope"]["retained_inventory_sha256"],
        "reference_count": len(records),
        "case_count": len(cases),
        "cases": cases,
        "predeclared_replay_gate_audit": gates,
        "all_predeclared_replay_gates_pass": all(gates.values()),
        "closed_surface_guard_pass": closed_surfaces_remain_closed(cases),
        "summary": {
            "attempted_source_count": len(records),
            "attempted_case_count": len(cases),
            "supported_case_count": len(supported),
            "abstained_case_count": len(cases) - len(supported),
            "applied_correction_case_count": len(applied),
            "nonapplied_case_count": len(cases) - len(applied),
            "predeclared_replay_gate_count": len(gates),
            "predeclared_replay_gate_pass_count": sum(gates.values()),
            "maximum_workers_used": 1,
            "minimum_free_disk_gib_preserved": 15,
            "derived_audio_retained": False,
            "retained_clean_reference_audio_accessed": True,
            "perceptual_metric_executed": False,
            "perceptual_truth_included": False,
            "human_playback_performed": False,
            "human_response_accessed": False,
            "no_reference_training_performed": False,
            "public_verdict_enabled": False,
        },
        "claim_boundary": authorization["claim_boundary"],
    }


def execute(
    *,
    source_root: Path,
    replay_roots: list[Path],
    authorization_path: Path = AUTHORIZATION,
    resume: bool = False,
) -> dict[str, Any]:
    if len(replay_roots) != 2 or replay_roots[0].resolve() == replay_roots[1].resolve():
        raise ValueError("exactly two distinct fresh private replay roots are required")
    for replay_root in replay_roots:
        root = replay_root.resolve()
        if inside_repository(root):
            raise ValueError("private replay root must remain outside the repository")
        if not resume and root.exists() and any(root.iterdir()):
            raise ValueError("private replay roots must be fresh")
    authorization, plan, authorization_sha256 = require_committed_authorization(
        authorization_path
    )
    if shutil.disk_usage(source_root).free < MINIMUM_FREE_BYTES:
        raise ValueError("free disk is below the 15 GiB reserve")
    np = load_numpy()
    audit = DELIVERY.load_json(DELIVERY.ATTRIBUTION_AUDIT)
    payloads: list[bytes] = []
    attribution_payloads: list[bytes] = []
    for replay_root in replay_roots:
        replay_root.mkdir(parents=True, mode=0o700)
        records = DELIVERY.validate_source_inventory(
            source_root, DELIVERY.expected_source_inventory(), audit
        )
        attachment = attribution_attachment(
            records=records,
            audit=audit,
            authorization_sha256=authorization_sha256,
        )
        attachment_payload = canonical_bytes(attachment)
        attribution_path = replay_root / "attribution.json"
        if attribution_path.exists():
            if attribution_path.is_symlink() or attribution_path.read_bytes() != attachment_payload:
                raise ValueError("private replay attribution attachment differs")
        else:
            atomic_json(attribution_path, attachment)
        attribution_sha256 = sha256_bytes(attachment_payload)
        report_path = replay_root / "report.json"
        journal_path = replay_root / "journal.json"
        if resume and report_path.is_file():
            replay = load_json(report_path)
            require_recovery_binding(
                replay,
                authorization=authorization,
                authorization_sha256=authorization_sha256,
                protocol=plan["validation_protocol"],
            )
            require_case_prefix(replay["cases"], records, plan["validation_protocol"])
            payload = canonical_bytes(replay)
            expected_case_count = len(records) * len(
                plan["validation_protocol"]["actual_drift_ppm_cases"]
            )
            if (
                payload != report_path.read_bytes()
                or len(replay["cases"]) != expected_case_count
                or replay.get("attribution_attachment_sha256") != attribution_sha256
            ):
                raise ValueError("completed private recovery report differs")
        else:
            existing_cases: list[dict[str, Any]] = []
            if resume and journal_path.is_file():
                journal = load_json(journal_path)
                existing_cases = require_recovery_binding(
                    journal,
                    authorization=authorization,
                    authorization_sha256=authorization_sha256,
                    protocol=plan["validation_protocol"],
                )
                require_case_prefix(
                    existing_cases, records, plan["validation_protocol"]
                )

            def checkpoint(cases: Sequence[dict[str, Any]]) -> None:
                atomic_json(
                    journal_path,
                    replay_journal(
                        cases=cases,
                        authorization=authorization,
                        authorization_sha256=authorization_sha256,
                        protocol=plan["validation_protocol"],
                    ),
                )

            checkpoint(existing_cases)
            replay = build_replay(
                source_root=source_root.resolve(),
                records=records,
                plan=plan,
                authorization=authorization,
                authorization_sha256=authorization_sha256,
                attribution_sha256=attribution_sha256,
                np=np,
                existing_cases=existing_cases,
                checkpoint=checkpoint,
            )
            payload = canonical_bytes(replay)
            atomic_json(report_path, replay)
            journal_path.unlink()
        payloads.append(payload)
        attribution_payloads.append(attachment_payload)
    if len(set(payloads)) != 1:
        raise ValueError("fresh retained-validation replay reports differ")
    if len(set(attribution_payloads)) != 1:
        raise ValueError("private replay attribution attachments differ")
    replay = json.loads(payloads[0])
    final_gates = dict(replay["predeclared_replay_gate_audit"])
    final_gates.update(
        {
            "exact_source_inventory_reverified": True,
            "fresh_replay_count": True,
            "fresh_replay_reports_must_be_byte_identical": True,
            "public_report_must_exclude_paths_per_reference_hashes_and_audio": True,
        }
    )
    expected_gate_names = set(plan["predeclared_future_gates"])
    if set(final_gates) != expected_gate_names:
        raise ValueError("final predeclared gate inventory differs")
    return {
        "status": "private_odaq_retained_drift_validation_complete",
        "reference_count": replay["reference_count"],
        "case_count": replay["case_count"],
        "supported_case_count": replay["summary"]["supported_case_count"],
        "abstained_case_count": replay["summary"]["abstained_case_count"],
        "applied_correction_case_count": replay["summary"]["applied_correction_case_count"],
        "predeclared_gate_count": len(final_gates),
        "predeclared_gate_pass_count": sum(final_gates.values()),
        "all_predeclared_gates_pass": all(final_gates.values()),
        "closed_surface_guard_pass": replay["closed_surface_guard_pass"],
        "replay_report_sha256": sha256_bytes(payloads[0]),
        "fresh_replay_count": 2,
        "replay_reports_byte_identical": True,
        "attribution_attachments_byte_identical": True,
        "derived_audio_retained": False,
        "processed_conditions_or_scores_accessed": False,
        "actual_codec_generated": False,
        "perceptual_metric_executed": False,
        "human_playback_or_collection_performed": False,
        "sealed_evidence_opened": False,
        "no_reference_training_performed": False,
        "public_verdict_enabled": False,
        "private_paths_redacted": True,
        "public_per_reference_hashes_redacted": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--replay-root", type=Path, action="append", required=True)
    parser.add_argument("--authorization", type=Path, default=AUTHORIZATION)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    result = execute(
        source_root=args.source_root,
        replay_roots=args.replay_root,
        authorization_path=args.authorization,
        resume=args.resume,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
