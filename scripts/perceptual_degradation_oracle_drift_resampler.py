#!/usr/bin/env python3
"""Freeze and replay the score-blind oracle clock-drift resampler."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import struct
import tempfile
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/"
    "oracle-drift-resampler-freeze.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-oracle-drift-resampler-20260814-001.json"
)
FREEZE_ID = "perceptual-degradation-oracle-drift-resampler-20260814-001"
REPORT_ID = FREEZE_ID
Q30_ONE = 1 << 30

EXPECTED_AUTHORIZATION = {
    "synthetic_numeric_fixture_execution_authorized": True,
    "synthetic_pcm_fixture_execution_authorized": True,
    "retained_audio_access_authorized": False,
    "provider_audio_access_authorized": False,
    "source_member_selection_authorized": False,
    "listening_condition_selection_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "human_collection_authorized": False,
    "response_or_outcome_access_authorized": False,
    "sealed_evidence_access_authorized": False,
    "no_reference_training_authorized": False,
    "public_verdict_enabled": False,
}

EXPECTED_RESOURCES = {
    "minimum_free_disk_gib": 15,
    "maximum_workers": 1,
    "fresh_temporary_directories": True,
    "replay_count": 2,
    "byte_identical_reports_required": True,
    "retain_generated_audio": False,
}

EXPECTED_CANDIDATE = {
    "resampler_id": "oracle-bounded-drift-kaiser-sinc128-q30-v1",
    "algorithm": "fixed_phase_quantized_kaiser_windowed_sinc",
    "numeric_input": "planar_binary64",
    "numeric_output": "planar_binary64",
    "tap_count": 128,
    "tap_offset_minimum": -63,
    "tap_offset_maximum": 64,
    "phase_count": 2048,
    "phase_selection": "nearest_phase_half_up_with_carry",
    "coefficient_quantization": "signed_q30_sum_exactly_one",
    "coefficient_table_sha256": "dbe4442199b56cd56880f1f45c09889721519dd7a165a4de76117b5e219dab82",
    "normalized_cutoff_relative_to_nyquist": 0.95,
    "kaiser_beta": 9.0,
    "maximum_abs_correction_ppm": 100,
    "source_position_mapping": (
        "output_frame_times_one_plus_correction_ppm_per_million"
    ),
    "channel_processing": "independent_with_shared_position_grid",
    "out_of_range_policy": "zero_extension",
    "mandatory_discard_frames_each_edge_when_applied": 64,
    "zero_drift_policy": "bit_exact_identity_bypass",
    "normalization_applied": False,
    "dither_applied": False,
    "perceptual_metric": False,
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _bound(plan: dict[str, Any], binding_id: str, root: Path = ROOT) -> Path:
    return root / plan["bindings"][binding_id]["path"]


def require_disk_reserve(path: Path, minimum_free_gib: int) -> int:
    free = shutil.disk_usage(path).free
    if free < minimum_free_gib * 1024**3:
        raise ValueError(f"free disk is below {minimum_free_gib} GiB reserve")
    return free


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("freeze_id") != FREEZE_ID:
        errors.append("freeze identity differs")
    if plan.get("state") != (
        "score_blind_oracle_drift_resampler_frozen_before_synthetic_replay"
    ):
        errors.append("freeze state differs")
    expected_bindings = {
        "research_contract",
        "research_plan",
        "alignment_fixture_freeze",
        "alignment_topology_freeze",
        "technical_repair_plan",
        "technical_repair_report",
        "score_free_oracle_plan",
        "resampler_implementation",
    }
    bindings = plan.get("bindings")
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        errors.append("bindings differ")
    else:
        for binding_id, binding in bindings.items():
            relative = binding.get("path") if isinstance(binding, dict) else None
            if not isinstance(relative, str) or Path(relative).is_absolute():
                errors.append(f"binding {binding_id} path differs")
                continue
            path = root / relative
            if not path.is_file():
                errors.append(f"binding {binding_id} path is missing")
            elif sha256_file(path) != binding.get("sha256"):
                errors.append(f"binding {binding_id} sha256 differs")
    if plan.get("authorization") != EXPECTED_AUTHORIZATION:
        errors.append("authorization differs")
    if plan.get("resources") != EXPECTED_RESOURCES:
        errors.append("resources differ")
    if plan.get("candidate") != EXPECTED_CANDIDATE:
        errors.append("candidate differs")
    replay = plan.get("synthetic_replay", {})
    if (
        replay.get("sample_rate_hz") != 8000
        or replay.get("duration_seconds") != 12
        or replay.get("channel_count") != 2
        or replay.get("actual_and_selected_correction_ppm_cases")
        != [75, -60, 100, -100, 0]
        or replay.get("candidate_resampler_does_not_generate_observation")
        is not True
    ):
        errors.append("synthetic replay contract differs")
    gates = plan.get("predeclared_gates", {})
    if (
        gates.get("minimum_core_correlation_each_channel") != 0.999999
        or gates.get("maximum_abs_core_gain_error_db_each_channel") != 0.001
        or gates.get("maximum_core_absolute_error_each_channel") != 0.002
        or gates.get("maximum_passband_ripple_abs_db") != 0.001
        or gates.get("maximum_stopband_magnitude_db") != -55.0
        or gates.get("maximum_dc_coefficient_sum_error") != 0.0
        or gates.get("maximum_zero_channel_leakage") != 0.0
    ):
        errors.append("predeclared gates differ")
    selection = plan.get("selection_policy", {})
    if (
        selection.get("all_predeclared_gates_must_pass") is not True
        or selection.get(
            "candidate_selected_as_frozen_oracle_resampler_only_if_all_pass"
        )
        is not True
        or selection.get("retained_audio_execution_follows_from_selection")
        is not False
        or selection.get("human_or_perceptual_validity_follows_from_selection")
        is not False
    ):
        errors.append("selection policy differs")
    claims = plan.get("claim_boundary")
    if not isinstance(claims, dict) or not claims:
        errors.append("claim boundary missing")
    elif any(value is not False for value in claims.values()):
        errors.append("claim boundary must contain only false values")
    return sorted(set(errors))


def bessel_i0(value: float) -> float:
    total = 1.0
    term = 1.0
    scaled = value * value / 4.0
    for index in range(1, 80):
        term *= scaled / (index * index)
        updated = total + term
        if updated == total:
            break
        total = updated
    return total


def coefficient_table(candidate: dict[str, Any]) -> tuple[tuple[int, ...], ...]:
    taps = candidate["tap_count"]
    phase_count = candidate["phase_count"]
    cutoff = candidate["normalized_cutoff_relative_to_nyquist"]
    beta = candidate["kaiser_beta"]
    offset_minimum = candidate["tap_offset_minimum"]
    offset_maximum = candidate["tap_offset_maximum"]
    if (
        taps != offset_maximum - offset_minimum + 1
        or taps % 2
        or phase_count < 2
        or phase_count & (phase_count - 1)
        or not 0.0 < cutoff <= 1.0
    ):
        raise ValueError("coefficient geometry differs")
    half_width = taps / 2.0
    window_norm = bessel_i0(beta)
    result = []
    for phase in range(phase_count):
        fraction = phase / phase_count
        raw = []
        for offset in range(offset_minimum, offset_maximum + 1):
            distance = fraction - offset
            sinc = (
                1.0
                if distance == 0.0
                else math.sin(math.pi * cutoff * distance)
                / (math.pi * cutoff * distance)
            )
            position = distance / half_width
            window = (
                bessel_i0(beta * math.sqrt(max(0.0, 1.0 - position * position)))
                / window_norm
                if abs(position) <= 1.0
                else 0.0
            )
            raw.append(cutoff * sinc * window)
        raw_sum = math.fsum(raw)
        quantized = [round(value / raw_sum * Q30_ONE) for value in raw]
        correction_index = max(
            range(taps), key=lambda index: abs(quantized[index])
        )
        quantized[correction_index] += Q30_ONE - sum(quantized)
        result.append(tuple(quantized))
    return tuple(result)


def coefficient_table_bytes(table: Sequence[Sequence[int]]) -> bytes:
    return b"".join(
        struct.pack("<i", value) for phase in table for value in phase
    )


def _position_phase(position: float, phase_count: int) -> tuple[int, int]:
    base = math.floor(position)
    fraction = position - base
    phase = math.floor(fraction * phase_count + 0.5)
    if phase == phase_count:
        return base + 1, 0
    return base, phase


def resample_channel(
    values: Sequence[float],
    *,
    output_frames: int,
    correction_ppm: int,
    candidate: dict[str, Any],
    table: Sequence[Sequence[int]],
) -> list[float]:
    if not values or output_frames < 1:
        raise ValueError("resampler input geometry differs")
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("resampler input contains non-finite values")
    if abs(correction_ppm) > candidate["maximum_abs_correction_ppm"]:
        raise ValueError("correction exceeds frozen ppm limit")
    if correction_ppm == 0:
        if output_frames != len(values):
            raise ValueError("identity bypass requires equal frame counts")
        return [float(value) for value in values]
    ratio = 1.0 + correction_ppm / 1_000_000.0
    phase_count = candidate["phase_count"]
    offset_minimum = candidate["tap_offset_minimum"]
    result: list[float] = []
    for output_index in range(output_frames):
        base, phase = _position_phase(output_index * ratio, phase_count)
        coefficients = table[phase]
        terms = []
        for coefficient_index, coefficient in enumerate(coefficients):
            source_index = base + offset_minimum + coefficient_index
            if 0 <= source_index < len(values):
                terms.append(float(values[source_index]) * coefficient / Q30_ONE)
        result.append(math.fsum(terms))
    return result


def resample_channels(
    channels: Sequence[Sequence[float]],
    *,
    output_frames: int,
    correction_ppm: int,
    candidate: dict[str, Any],
    table: Sequence[Sequence[int]],
) -> list[list[float]]:
    if not channels or len(channels) not in (1, 2):
        raise ValueError("unsupported channel count")
    frame_count = len(channels[0])
    if frame_count < 1 or any(len(channel) != frame_count for channel in channels):
        raise ValueError("channel shape differs")
    return [
        resample_channel(
            channel,
            output_frames=output_frames,
            correction_ppm=correction_ppm,
            candidate=candidate,
            table=table,
        )
        for channel in channels
    ]


def pack_f64_channels(channels: Sequence[Sequence[float]]) -> bytes:
    if not channels:
        return b""
    frames = len(channels[0])
    if any(len(channel) != frames for channel in channels):
        raise ValueError("channel shape differs")
    return b"".join(
        struct.pack("<d", float(channels[channel][frame]))
        for frame in range(frames)
        for channel in range(len(channels))
    )


def analytic_sample(position: float, channel: int, sample_rate: int) -> float:
    time = position / sample_rate
    if channel == 0:
        carrier = (
            0.43 * math.sin(2 * math.pi * 173 * time + 0.13)
            + 0.31 * math.sin(2 * math.pi * 997 * time + 0.29)
            + 0.18 * math.sin(2 * math.pi * 2701 * time + 0.47)
        )
        envelope = 0.72 + 0.18 * math.sin(2 * math.pi * 3 * time + 0.11)
    elif channel == 1:
        carrier = (
            0.39 * math.sin(2 * math.pi * 211 * time + 0.19)
            + 0.29 * math.sin(2 * math.pi * 1291 * time + 0.37)
            + 0.21 * math.sin(2 * math.pi * 2531 * time + 0.53)
        )
        envelope = 0.69 + 0.21 * math.sin(2 * math.pi * 7 * time + 0.17)
    else:
        raise ValueError("synthetic channel differs")
    return envelope * carrier


def analytic_channels(
    *, frame_count: int, sample_rate: int, channel_count: int, source_step: float
) -> list[list[float]]:
    return [
        [
            analytic_sample(frame * source_step, channel, sample_rate)
            for frame in range(frame_count)
        ]
        for channel in range(channel_count)
    ]


def _correlation(reference: Sequence[float], test: Sequence[float]) -> float:
    if len(reference) != len(test) or not reference:
        raise ValueError("correlation geometry differs")
    dot = math.fsum(left * right for left, right in zip(reference, test, strict=True))
    left_energy = math.fsum(value * value for value in reference)
    right_energy = math.fsum(value * value for value in test)
    return dot / math.sqrt(left_energy * right_energy)


def _gain_error_db(reference: Sequence[float], test: Sequence[float]) -> float:
    reference_energy = math.fsum(value * value for value in reference)
    test_energy = math.fsum(value * value for value in test)
    return 10.0 * math.log10(test_energy / reference_energy)


def replay_time_case(
    plan: dict[str, Any], table: Sequence[Sequence[int]], correction_ppm: int
) -> dict[str, Any]:
    candidate = plan["candidate"]
    replay = plan["synthetic_replay"]
    sample_rate = replay["sample_rate_hz"]
    reference_frames = sample_rate * replay["duration_seconds"]
    reference = analytic_channels(
        frame_count=reference_frames,
        sample_rate=sample_rate,
        channel_count=replay["channel_count"],
        source_step=1.0,
    )
    ratio = 1.0 + correction_ppm / 1_000_000.0
    observed_frames = math.floor(reference_frames * ratio)
    observed = analytic_channels(
        frame_count=observed_frames,
        sample_rate=sample_rate,
        channel_count=replay["channel_count"],
        source_step=1.0 / ratio,
    )
    corrected = resample_channels(
        observed,
        output_frames=reference_frames,
        correction_ppm=correction_ppm,
        candidate=candidate,
        table=table,
    )
    discard = (
        0
        if correction_ppm == 0
        else candidate["mandatory_discard_frames_each_edge_when_applied"]
    )
    channel_metrics = []
    for channel_index, (expected, actual) in enumerate(
        zip(reference, corrected, strict=True)
    ):
        expected_core = expected[discard : reference_frames - discard or None]
        actual_core = actual[discard : reference_frames - discard or None]
        channel_metrics.append(
            {
                "channel_index": channel_index,
                "core_frame_count": len(expected_core),
                "core_correlation": _correlation(expected_core, actual_core),
                "core_gain_error_db": _gain_error_db(expected_core, actual_core),
                "core_maximum_absolute_error": max(
                    abs(left - right)
                    for left, right in zip(expected_core, actual_core, strict=True)
                ),
            }
        )
    return {
        "correction_ppm": correction_ppm,
        "reference_frame_count": reference_frames,
        "observed_frame_count": observed_frames,
        "output_frame_count": len(corrected[0]),
        "mandatory_discard_frames_each_edge": discard,
        "correction_applied": correction_ppm != 0,
        "identity_bypass_used": correction_ppm == 0,
        "input_f64le_sha256": sha256_bytes(pack_f64_channels(observed)),
        "output_f64le_sha256": sha256_bytes(pack_f64_channels(corrected)),
        "identity_output_bit_exact": (
            pack_f64_channels(corrected) == pack_f64_channels(observed)
            if correction_ppm == 0
            else None
        ),
        "channel_metrics": channel_metrics,
        "retained_audio_accessed": False,
        "perceptual_truth_included": False,
    }


def frequency_response_audit(
    candidate: dict[str, Any],
    replay: dict[str, Any],
    table: Sequence[Sequence[int]],
) -> dict[str, Any]:
    offsets = list(
        range(candidate["tap_offset_minimum"], candidate["tap_offset_maximum"] + 1)
    )
    phase_stride = replay["frequency_response_phase_stride"]
    step = replay["frequency_response_grid_step_nyquist"]
    passband = [
        index * step
        for index in range(round(replay["passband_end_relative_to_nyquist"] / step) + 1)
    ]
    stopband = [
        replay["stopband_start_relative_to_nyquist"] + index * step
        for index in range(
            round(
                (1.0 - replay["stopband_start_relative_to_nyquist"]) / step
            )
            + 1
        )
    ]

    def magnitude(coefficients: Sequence[int], nyquist_fraction: float) -> float:
        angle = math.pi * nyquist_fraction
        real = math.fsum(
            coefficient / Q30_ONE * math.cos(angle * offset)
            for coefficient, offset in zip(coefficients, offsets, strict=True)
        )
        imaginary = math.fsum(
            -coefficient / Q30_ONE * math.sin(angle * offset)
            for coefficient, offset in zip(coefficients, offsets, strict=True)
        )
        return math.hypot(real, imaginary)

    phases = range(0, candidate["phase_count"], phase_stride)
    passband_values = [
        magnitude(table[phase], frequency)
        for phase in phases
        for frequency in passband
    ]
    stopband_values = [
        magnitude(table[phase], frequency)
        for phase in phases
        for frequency in stopband
    ]
    passband_minimum_db = 20.0 * math.log10(min(passband_values))
    passband_maximum_db = 20.0 * math.log10(max(passband_values))
    stopband_maximum_db = 20.0 * math.log10(max(stopband_values))
    dc_error = max(abs(sum(row) - Q30_ONE) / Q30_ONE for row in table)
    return {
        "phase_count_evaluated": len(list(phases)),
        "passband_frequency_count": len(passband),
        "stopband_frequency_count": len(stopband),
        "passband_minimum_db": passband_minimum_db,
        "passband_maximum_db": passband_maximum_db,
        "passband_ripple_abs_db": max(
            abs(passband_minimum_db), abs(passband_maximum_db)
        ),
        "stopband_maximum_db": stopband_maximum_db,
        "maximum_dc_coefficient_sum_error": dc_error,
    }


def stereo_isolation_audit(
    candidate: dict[str, Any], table: Sequence[Sequence[int]], frame_count: int
) -> dict[str, Any]:
    left = [
        math.sin(2 * math.pi * 0.173 * frame)
        + 0.2 * math.sin(2 * math.pi * 0.311 * frame + 0.2)
        for frame in range(frame_count)
    ]
    right = [0.0] * frame_count
    output = resample_channels(
        [left, right],
        output_frames=frame_count,
        correction_ppm=75,
        candidate=candidate,
        table=table,
    )
    return {
        "input_channel_count": 2,
        "output_channel_count": len(output),
        "shared_position_grid": True,
        "maximum_zero_channel_leakage": max(abs(value) for value in output[1]),
        "nonzero_channel_output_sha256": sha256_bytes(
            b"".join(struct.pack("<d", value) for value in output[0])
        ),
        "zero_channel_output_sha256": sha256_bytes(
            b"".join(struct.pack("<d", value) for value in output[1])
        ),
    }


def golden_vector(
    plan: dict[str, Any], table: Sequence[Sequence[int]]
) -> dict[str, Any]:
    frames = plan["synthetic_replay"]["golden_vector_frame_count"]
    candidate = plan["candidate"]
    values = [
        (
            (frame * 7919 + (frame // 17) * 104729) % 60001
            - 30000
        )
        / 32768.0
        for frame in range(frames)
    ]
    output = resample_channel(
        values,
        output_frames=frames,
        correction_ppm=75,
        candidate=candidate,
        table=table,
    )
    return {
        "frame_count": frames,
        "correction_ppm": 75,
        "input_f64le_sha256": sha256_bytes(
            b"".join(struct.pack("<d", value) for value in values)
        ),
        "output_f64le_sha256": sha256_bytes(
            b"".join(struct.pack("<d", value) for value in output)
        ),
    }


def gate_audit(
    plan: dict[str, Any],
    table_hash: str,
    time_cases: Sequence[dict[str, Any]],
    response: dict[str, Any],
    isolation: dict[str, Any],
) -> dict[str, bool]:
    gates = plan["predeclared_gates"]
    metrics = [
        metric for case in time_cases for metric in case["channel_metrics"]
    ]
    identity = next(case for case in time_cases if case["correction_ppm"] == 0)
    return {
        "coefficient_table_hash": (
            table_hash == plan["candidate"]["coefficient_table_sha256"]
        ),
        "core_correlation": all(
            metric["core_correlation"]
            >= gates["minimum_core_correlation_each_channel"]
            for metric in metrics
        ),
        "core_gain": all(
            abs(metric["core_gain_error_db"])
            <= gates["maximum_abs_core_gain_error_db_each_channel"]
            for metric in metrics
        ),
        "core_absolute_error": all(
            metric["core_maximum_absolute_error"]
            <= gates["maximum_core_absolute_error_each_channel"]
            for metric in metrics
        ),
        "passband_ripple": (
            response["passband_ripple_abs_db"]
            <= gates["maximum_passband_ripple_abs_db"]
        ),
        "stopband_magnitude": (
            response["stopband_maximum_db"]
            <= gates["maximum_stopband_magnitude_db"]
        ),
        "dc_coefficient_sum": (
            response["maximum_dc_coefficient_sum_error"]
            <= gates["maximum_dc_coefficient_sum_error"]
        ),
        "stereo_zero_channel_leakage": (
            isolation["maximum_zero_channel_leakage"]
            <= gates["maximum_zero_channel_leakage"]
        ),
        "zero_drift_bit_exact": (
            identity["identity_output_bit_exact"]
            is gates["zero_drift_output_must_be_bit_exact"]
        ),
    }


def build_payload(plan: dict[str, Any]) -> dict[str, Any]:
    candidate = plan["candidate"]
    table = coefficient_table(candidate)
    table_hash = sha256_bytes(coefficient_table_bytes(table))
    time_cases = [
        replay_time_case(plan, table, correction_ppm)
        for correction_ppm in plan["synthetic_replay"][
            "actual_and_selected_correction_ppm_cases"
        ]
    ]
    response = frequency_response_audit(
        candidate, plan["synthetic_replay"], table
    )
    isolation = stereo_isolation_audit(
        candidate, table, plan["synthetic_replay"]["golden_vector_frame_count"]
    )
    golden = golden_vector(plan, table)
    gates = gate_audit(plan, table_hash, time_cases, response, isolation)
    return {
        "coefficient_table": {
            "phase_count": len(table),
            "tap_count": len(table[0]),
            "sha256": table_hash,
            "all_phase_sums_equal_q30_one": all(
                sum(row) == Q30_ONE for row in table
            ),
        },
        "time_domain_cases": time_cases,
        "frequency_response": response,
        "stereo_isolation": isolation,
        "golden_vector": golden,
        "gate_audit": gates,
        "all_predeclared_gates_pass": all(gates.values()),
    }


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    technical = load_json(_bound(plan, "technical_repair_report"))
    if technical["decision"]["production_oracle_resampler_selected"] is not False:
        raise ValueError("technical repair unexpectedly selected a resampler")
    require_disk_reserve(ROOT, plan["resources"]["minimum_free_disk_gib"])
    payloads: list[bytes] = []
    for _ in range(plan["resources"]["replay_count"]):
        with tempfile.TemporaryDirectory(
            prefix="lossytrace-oracle-drift-resampler-"
        ) as directory:
            path = Path(directory) / "payload.json"
            path.write_bytes(canonical_bytes(build_payload(plan)))
            payloads.append(path.read_bytes())
    if len(set(payloads)) != 1:
        raise ValueError("fresh resampler replays differ")
    payload_hashes = [sha256_bytes(payload) for payload in payloads]
    payload = json.loads(payloads[0])
    selected = (
        payload["all_predeclared_gates_pass"]
        and plan["selection_policy"]["all_predeclared_gates_must_pass"]
    )
    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "score_blind_oracle_drift_resampler_replayed",
        "freeze_id": plan["freeze_id"],
        "freeze_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "authority": plan["authorization"],
        "resources": {
            "minimum_free_disk_gib_preserved": plan["resources"][
                "minimum_free_disk_gib"
            ],
            "maximum_workers_used": 1,
            "generated_audio_retained": False,
        },
        "candidate": plan["candidate"],
        "replay_observation": {
            "fresh_temporary_replay_count": len(payloads),
            "payload_sha256s": payload_hashes,
            "byte_identical": len(set(payloads)) == 1,
            "paths_included": False,
            "timing_included": False,
        },
        **payload,
        "summary": {
            "time_domain_case_count": len(payload["time_domain_cases"]),
            "predeclared_gate_count": len(payload["gate_audit"]),
            "predeclared_gate_pass_count": sum(payload["gate_audit"].values()),
            "all_predeclared_gates_pass": payload["all_predeclared_gates_pass"],
            "actual_audio_accessed": False,
            "retained_audio_accessed": False,
            "perceptual_metric_executed": False,
            "perceptual_truth_included": False,
            "listener_response_collected": False,
            "public_verdict_enabled": False,
        },
        "decision": {
            "candidate_selected_as_frozen_oracle_resampler": selected,
            "bounded_drift_correction_technical_path_ready": selected,
            "retained_audio_correction_executed": False,
            "retained_audio_correction_validated": False,
            "human_or_perceptual_validity_present": False,
            "full_reference_oracle_validated": False,
            "human_collection_authorized": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "next_gate": (
                "Under separate authority, integrate this exact resampler after the "
                "held-out drift decision and validate correction on retained development "
                "pairs before any perceptual metric execution."
                if selected
                else "Reject this candidate and keep drift correction unsupported."
            ),
        },
        "claim_boundary": plan["claim_boundary"],
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != 1 or report.get("report_id") != REPORT_ID:
        errors.append("report identity differs")
    if report.get("state") != "score_blind_oracle_drift_resampler_replayed":
        errors.append("report state differs")
    if report.get("authority") != EXPECTED_AUTHORIZATION:
        errors.append("report authority differs")
    if report.get("candidate") != EXPECTED_CANDIDATE:
        errors.append("report candidate differs")
    replay = report.get("replay_observation", {})
    if (
        replay.get("fresh_temporary_replay_count") != 2
        or replay.get("byte_identical") is not True
        or len(set(replay.get("payload_sha256s", []))) != 1
        or replay.get("paths_included") is not False
        or replay.get("timing_included") is not False
    ):
        errors.append("replay observation differs")
    coefficient = report.get("coefficient_table", {})
    if (
        coefficient.get("phase_count") != 2048
        or coefficient.get("tap_count") != 128
        or coefficient.get("sha256")
        != EXPECTED_CANDIDATE["coefficient_table_sha256"]
        or coefficient.get("all_phase_sums_equal_q30_one") is not True
    ):
        errors.append("coefficient table differs")
    cases = report.get("time_domain_cases", [])
    if [case.get("correction_ppm") for case in cases] != [75, -60, 100, -100, 0]:
        errors.append("time-domain case inventory differs")
    else:
        for case in cases:
            if (
                case.get("retained_audio_accessed") is not False
                or case.get("perceptual_truth_included") is not False
                or len(case.get("channel_metrics", [])) != 2
            ):
                errors.append(f"time-domain case boundary differs: {case.get('correction_ppm')}")
        identity = cases[-1]
        if (
            identity.get("identity_bypass_used") is not True
            or identity.get("identity_output_bit_exact") is not True
            or identity.get("correction_applied") is not False
        ):
            errors.append("zero-drift identity case differs")
    gates = report.get("gate_audit")
    if not isinstance(gates, dict) or len(gates) != 9 or not all(gates.values()):
        errors.append("predeclared gates did not all pass")
    if report.get("all_predeclared_gates_pass") is not True:
        errors.append("all-gates decision differs")
    summary = report.get("summary", {})
    for key in (
        "actual_audio_accessed",
        "retained_audio_accessed",
        "perceptual_metric_executed",
        "perceptual_truth_included",
        "listener_response_collected",
        "public_verdict_enabled",
    ):
        if summary.get(key) is not False:
            errors.append(f"summary {key} must be false")
    decision = report.get("decision", {})
    if decision.get("candidate_selected_as_frozen_oracle_resampler") is not True:
        errors.append("candidate was not selected")
    for key in (
        "retained_audio_correction_executed",
        "retained_audio_correction_validated",
        "human_or_perceptual_validity_present",
        "full_reference_oracle_validated",
        "human_collection_authorized",
        "no_reference_work_eligible",
        "public_verdict_enabled",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision {key} must be false")
    claims = report.get("claim_boundary")
    if not isinstance(claims, dict) or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    plan = load_json(args.plan)
    report = build_report(plan, args.plan)
    errors = validate_report(report)
    if errors:
        raise SystemExit("; ".join(errors))
    write_report(report, args.output)
    print(
        json.dumps(
            {
                "report_id": report["report_id"],
                "candidate_selected": report["decision"][
                    "candidate_selected_as_frozen_oracle_resampler"
                ],
                "gate_pass_count": report["summary"][
                    "predeclared_gate_pass_count"
                ],
                "replays_byte_identical": report["replay_observation"][
                    "byte_identical"
                ],
                "retained_audio_accessed": report["summary"][
                    "retained_audio_accessed"
                ],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
