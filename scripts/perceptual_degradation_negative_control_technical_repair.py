#!/usr/bin/env python3
"""Synthetic-only technical repair for negative/control candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import perceptual_degradation_alignment_v2 as alignment  # noqa: E402


PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/"
    "negative-control-technical-repair-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-negative-control-technical-repair-20260814-001.json"
)

EXPECTED_AUTHORIZATION = {
    "synthetic_numeric_fixture_execution_authorized": True,
    "synthetic_pcm_fixture_execution_authorized": True,
    "actual_source_audio_access_authorized": False,
    "provider_audio_access_authorized": False,
    "retained_audio_access_authorized": False,
    "listening_condition_selection_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "human_collection_authorized": False,
    "recruitment_authorized": False,
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if plan.get("plan_id") != (
        "perceptual-degradation-negative-control-technical-repair-"
        "20260814-001"
    ):
        errors.append("plan_id differs")
    if plan.get("state") != (
        "score_blind_synthetic_technical_repair_frozen_before_replay"
    ):
        errors.append("state differs")
    expected_bindings = {
        "research_contract",
        "research_plan",
        "factor_levels",
        "historical_toolchain_bindings",
        "alignment_mono_implementation",
        "alignment_topology_implementation",
        "alignment_fixture_freeze",
        "alignment_topology_freeze",
        "production_generation_plan",
        "production_generation_replay",
        "negative_control_topology_plan",
        "negative_control_topology_report",
    }
    bindings = plan.get("bindings")
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        errors.append("bindings differ")
    else:
        for binding_id, binding in bindings.items():
            if not isinstance(binding, dict):
                errors.append(f"binding {binding_id} must be an object")
                continue
            relative = binding.get("path")
            if not isinstance(relative, str) or Path(relative).is_absolute():
                errors.append(f"binding {binding_id} path must be relative")
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
    dither = plan.get("isolated_dither_candidate", {})
    if (
        dither.get("class_id") != "dither"
        or dither.get("noise_minimum_lsb") != -1
        or dither.get("noise_maximum_lsb") != 1
        or dither.get("bit_depth_change") is not False
        or dither.get("human_truth") != "absent"
    ):
        errors.append("isolated dither candidate differs")
    src = plan.get("sample_rate_conversion_candidate", {})
    if (
        src.get("class_id") != "sample_rate_conversion"
        or src.get("source_sample_rate_hz") != 48000
        or src.get("intermediate_sample_rate_hz") != 32000
        or src.get("output_sample_rate_hz") != 48000
        or src.get("dither_applied") is not False
        or src.get("normalization_applied") is not False
        or src.get("historical_ffmpeg_8_1_2_binding_reused") is not False
    ):
        errors.append("sample-rate conversion candidate differs")
    drift = plan.get("bounded_clock_drift_candidate", {})
    if (
        drift.get("actual_drift_ppm_cases") != [75, -60, 0]
        or drift.get("candidate_drift_ppm_minimum") != -100
        or drift.get("candidate_drift_ppm_maximum") != 100
        or drift.get("candidate_drift_ppm_step") != 5
        or drift.get("training_window_positions") != [0, 2, 4, 6, 8]
        or drift.get("held_out_window_positions") != [1, 3, 5, 7, 9]
        or drift.get("fixture_interpolator_is_frozen_oracle_resampler")
        is not False
        or drift.get("production_resampler_execution_authorized") is not False
    ):
        errors.append("bounded-clock-drift candidate differs")
    edge = plan.get("paired_edge_silence_candidate", {})
    if (
        edge.get("supported_case", {}).get("expected_status") != "supported"
        or edge.get("over_limit_case", {}).get("expected_status")
        != "unsupported"
        or edge.get("over_limit_case", {}).get("expected_reason")
        != "excessive_trim"
    ):
        errors.append("paired edge-silence candidate differs")
    claims = plan.get("claim_boundary")
    if not isinstance(claims, dict) or not claims:
        errors.append("claim boundary missing")
    elif any(value is not False for value in claims.values()):
        errors.append("claim boundary must contain only false values")
    return errors


def require_disk_reserve(path: Path, minimum_free_gib: int) -> int:
    free = shutil.disk_usage(path).free
    if free < minimum_free_gib * 1024**3:
        raise ValueError(f"free disk is below {minimum_free_gib} GiB reserve")
    return free


def saturate_s16(value: int) -> int:
    return max(-32768, min(32767, value))


def pcm_bytes(samples: Sequence[int]) -> bytes:
    if any(value < -32768 or value > 32767 for value in samples):
        raise ValueError("sample is outside signed-16 range")
    return struct.pack(f"<{len(samples)}h", *samples)


def synthetic_pcm_samples(
    fixture: dict[str, Any], recipe_id: str
) -> list[int]:
    sample_rate = fixture["sample_rate_hz"]
    channels = fixture["channel_count"]
    seconds = fixture["duration_seconds"]
    if (sample_rate, channels, seconds) != (48000, 2, 2):
        raise ValueError("synthetic PCM fixture geometry differs")
    phase = int.from_bytes(hashlib.sha256(recipe_id.encode()).digest()[:4], "big")
    result = []
    for frame in range(sample_rate * seconds):
        left = ((frame * 7919 + phase) % 60001) - 30000
        right = ((frame * 6151 + phase // 3) % 60001) - 30000
        pulse = 12000 if (frame // 1200) % 2 == 0 else -12000
        result.extend(
            (
                saturate_s16((3 * left + pulse) // 4),
                saturate_s16((3 * right - pulse) // 4),
            )
        )
    return result


def apply_isolated_dither(
    samples: Sequence[int], *, seed_prefix: str, recipe_id: str
) -> tuple[list[int], dict[int, int]]:
    if not samples:
        raise ValueError("dither input must not be empty")
    prefix = seed_prefix.encode() + recipe_id.encode() + b"\0"
    output = []
    histogram = {-1: 0, 0: 0, 1: 0}
    for index, sample in enumerate(samples):
        digest = hashlib.sha256(prefix + index.to_bytes(8, "big")).digest()
        noise = (digest[0] & 1) - (digest[1] & 1)
        histogram[noise] += 1
        output.append(saturate_s16(sample + noise))
    return output, histogram


def _process_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {"LC_ALL": "C", "LANG": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "0"}
    )
    return environment


def verify_bound_ffmpeg(candidate: dict[str, Any]) -> tuple[Path, str]:
    found = shutil.which("ffmpeg")
    if found is None:
        raise ValueError("bound FFmpeg successor is unavailable")
    path = Path(found).resolve()
    tool = candidate["tool"]
    if sha256_file(path) != tool["binary_sha256"]:
        raise ValueError("bound FFmpeg successor binary hash differs")
    completed = subprocess.run(
        [str(path), "-version"],
        capture_output=True,
        env=_process_environment(),
        stdin=subprocess.DEVNULL,
        timeout=30,
        check=True,
    )
    if sha256_bytes(completed.stdout) != tool["version_output_sha256"]:
        raise ValueError("bound FFmpeg successor version output hash differs")
    version_line = completed.stdout.decode().splitlines()[0]
    if version_line != tool["version_line"]:
        raise ValueError("bound FFmpeg successor version line differs")
    return path, version_line


def _run_ffmpeg(command: list[str]) -> None:
    completed = subprocess.run(
        command,
        capture_output=True,
        env=_process_environment(),
        stdin=subprocess.DEVNULL,
        timeout=120,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.decode(errors="replace").strip()[-500:]
        raise ValueError(
            f"sample-rate conversion failed with exit {completed.returncode}: {detail}"
        )


def _resample_raw(
    *,
    ffmpeg: Path,
    input_path: Path,
    output_path: Path,
    source_rate: int,
    target_rate: int,
    channels: int,
    filter_template: str,
) -> bytes:
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-fflags",
        "+bitexact",
        "-f",
        "s16le",
        "-ar",
        str(source_rate),
        "-ac",
        str(channels),
        "-i",
        str(input_path),
        "-map",
        "0:a:0",
        "-af",
        filter_template.format(target=target_rate),
        "-ar",
        str(target_rate),
        "-ac",
        str(channels),
        "-c:a",
        "pcm_s16le",
        "-f",
        "s16le",
        "-fflags",
        "+bitexact",
        str(output_path),
    ]
    _run_ffmpeg(command)
    payload = output_path.read_bytes()
    if not payload or len(payload) % (2 * channels):
        raise ValueError("sample-rate conversion output shape differs")
    return payload


def replay_dither_case(plan: dict[str, Any]) -> dict[str, Any]:
    candidate = plan["isolated_dither_candidate"]
    fixture = plan["synthetic_pcm_fixture"]
    samples = synthetic_pcm_samples(fixture, candidate["recipe_id"])
    output, histogram = apply_isolated_dither(
        samples,
        seed_prefix=candidate["seed_prefix"],
        recipe_id=candidate["recipe_id"],
    )
    input_payload = pcm_bytes(samples)
    output_payload = pcm_bytes(output)
    changed = sum(left != right for left, right in zip(samples, output, strict=True))
    return {
        "recipe_id": candidate["recipe_id"],
        "class_id": candidate["class_id"],
        "sample_rate_hz": fixture["sample_rate_hz"],
        "channel_count": fixture["channel_count"],
        "frame_count": len(samples) // fixture["channel_count"],
        "input_pcm_sha256": sha256_bytes(input_payload),
        "output_pcm_sha256": sha256_bytes(output_payload),
        "changed_sample_count": changed,
        "changed_sample_fraction": changed / len(samples),
        "noise_histogram": {str(key): value for key, value in histogram.items()},
        "noise_minimum_lsb": min(histogram),
        "noise_maximum_lsb": max(histogram),
        "bit_depth_change": False,
        "frame_shape_preserved": len(input_payload) == len(output_payload),
        "perceptual_truth_included": False,
    }


def replay_sample_rate_conversion_case(
    plan: dict[str, Any], temporary_root: Path
) -> dict[str, Any]:
    candidate = plan["sample_rate_conversion_candidate"]
    fixture = plan["synthetic_pcm_fixture"]
    ffmpeg, version_line = verify_bound_ffmpeg(candidate)
    samples = synthetic_pcm_samples(fixture, candidate["recipe_id"])
    input_payload = pcm_bytes(samples)
    input_path = temporary_root / "input.s16le"
    intermediate_path = temporary_root / "intermediate.s16le"
    output_path = temporary_root / "output.s16le"
    input_path.write_bytes(input_payload)
    intermediate = _resample_raw(
        ffmpeg=ffmpeg,
        input_path=input_path,
        output_path=intermediate_path,
        source_rate=candidate["source_sample_rate_hz"],
        target_rate=candidate["intermediate_sample_rate_hz"],
        channels=candidate["channel_count"],
        filter_template=candidate["ffmpeg_filter_template"],
    )
    output = _resample_raw(
        ffmpeg=ffmpeg,
        input_path=intermediate_path,
        output_path=output_path,
        source_rate=candidate["intermediate_sample_rate_hz"],
        target_rate=candidate["output_sample_rate_hz"],
        channels=candidate["channel_count"],
        filter_template=candidate["ffmpeg_filter_template"],
    )
    channels = candidate["channel_count"]
    return {
        "recipe_id": candidate["recipe_id"],
        "class_id": candidate["class_id"],
        "tool_id": candidate["tool"]["tool_id"],
        "tool_binary_sha256": candidate["tool"]["binary_sha256"],
        "tool_version_output_sha256": candidate["tool"][
            "version_output_sha256"
        ],
        "tool_version_line": version_line,
        "source_sample_rate_hz": candidate["source_sample_rate_hz"],
        "intermediate_sample_rate_hz": candidate["intermediate_sample_rate_hz"],
        "output_sample_rate_hz": candidate["output_sample_rate_hz"],
        "channel_count": channels,
        "input_frame_count": len(input_payload) // (2 * channels),
        "intermediate_frame_count": len(intermediate) // (2 * channels),
        "output_frame_count": len(output) // (2 * channels),
        "input_pcm_sha256": sha256_bytes(input_payload),
        "intermediate_pcm_sha256": sha256_bytes(intermediate),
        "output_pcm_sha256": sha256_bytes(output),
        "input_output_differ": input_payload != output,
        "output_geometry_preserved": (
            len(output) // (2 * channels)
            == len(input_payload) // (2 * channels)
        ),
        "dither_applied": False,
        "normalization_applied": False,
        "historical_ffmpeg_binding_reused": False,
        "perceptual_truth_included": False,
    }


def synthetic_alignment_fixture(sample_rate: int, seconds: int) -> list[float]:
    return [
        (0.2 + 0.8 * ((index // 137) % 7) / 6)
        * (
            0.55 * math.sin(2 * math.pi * 113 * index / sample_rate)
            + 0.31 * math.sin(
                2 * math.pi * 271 * index / sample_rate + 0.2
            )
            + 0.14
            * math.sin(
                2 * math.pi * 419 * index / sample_rate
                + index * index * 1e-7
            )
        )
        for index in range(sample_rate * seconds)
    ]


def linear_interpolate(values: Sequence[float], position: float) -> float:
    if position < 0.0 or position >= len(values) - 1:
        return 0.0
    lower = int(position)
    fraction = position - lower
    return values[lower] * (1.0 - fraction) + values[lower + 1] * fraction


def apply_synthetic_drift(values: Sequence[float], drift_ppm: int) -> list[float]:
    ratio = 1.0 + drift_ppm / 1_000_000.0
    length = math.floor(len(values) * ratio)
    return [linear_interpolate(values, index / ratio) for index in range(length)]


def correct_synthetic_drift(
    values: Sequence[float], output_length: int, correction_ppm: int
) -> list[float]:
    ratio = 1.0 + correction_ppm / 1_000_000.0
    return [linear_interpolate(values, index * ratio) for index in range(output_length)]


def cosine_window(
    left: Sequence[float], right: Sequence[float], start: int, end: int
) -> float:
    if end > min(len(left), len(right)) or end <= start:
        raise ValueError("correlation window differs")
    dot = math.fsum(
        left[index] * right[index] for index in range(start, end)
    )
    energy_left = math.fsum(left[index] ** 2 for index in range(start, end))
    energy_right = math.fsum(right[index] ** 2 for index in range(start, end))
    if energy_left <= 0.0 or energy_right <= 0.0:
        raise ValueError("correlation window has no energy")
    return dot / math.sqrt(energy_left * energy_right)


def mean_window_correlation(
    left: Sequence[float],
    right: Sequence[float],
    windows: Sequence[tuple[int, int]],
    positions: Sequence[int],
) -> float:
    return math.fsum(
        cosine_window(left, right, *windows[position]) for position in positions
    ) / len(positions)


def replay_drift_case(candidate: dict[str, Any], actual_ppm: int) -> dict[str, Any]:
    sample_rate = candidate["sample_rate_hz"]
    reference = synthetic_alignment_fixture(
        sample_rate, candidate["duration_seconds"]
    )
    observed = apply_synthetic_drift(reference, actual_ppm)
    windows = [
        (
            int(second * sample_rate),
            int((second + candidate["window_seconds"]) * sample_rate),
        )
        for second in candidate["window_start_seconds"]
    ]
    training_positions = candidate["training_window_positions"]
    held_positions = candidate["held_out_window_positions"]
    scored = []
    for correction_ppm in range(
        candidate["candidate_drift_ppm_minimum"],
        candidate["candidate_drift_ppm_maximum"] + 1,
        candidate["candidate_drift_ppm_step"],
    ):
        corrected = correct_synthetic_drift(
            observed, len(reference), correction_ppm
        )
        scored.append(
            (
                mean_window_correlation(
                    reference, corrected, windows, training_positions
                ),
                correction_ppm,
                corrected,
            )
        )
    scored.sort(key=lambda value: (value[0], -abs(value[1]), -value[1]), reverse=True)
    best_score, selected_ppm, corrected = scored[0]
    selection_margin = best_score - scored[1][0]
    held_before = mean_window_correlation(
        reference, observed, windows, held_positions
    )
    held_after = mean_window_correlation(
        reference, corrected, windows, held_positions
    )
    improvement = held_after - held_before
    apply_correction = (
        selected_ppm != 0
        and selection_margin >= candidate["minimum_selection_margin"]
        and held_after
        >= candidate["minimum_held_out_correlation_after_correction"]
        and improvement
        >= candidate["minimum_held_out_correlation_improvement_to_apply"]
    )
    return {
        "actual_drift_ppm": actual_ppm,
        "selected_correction_ppm": selected_ppm,
        "selection_mean_correlation": best_score,
        "selection_margin": selection_margin,
        "held_out_mean_correlation_before": held_before,
        "held_out_mean_correlation_after": held_after,
        "held_out_mean_correlation_improvement": improvement,
        "apply_correction": apply_correction,
        "selection_used_held_out_windows": False,
        "fixture_interpolator_is_frozen_oracle_resampler": False,
        "production_resampler_executed": False,
        "perceptual_truth_included": False,
    }


def replay_drift_cases(plan: dict[str, Any]) -> list[dict[str, Any]]:
    candidate = plan["bounded_clock_drift_candidate"]
    rows = [
        replay_drift_case(candidate, actual_ppm)
        for actual_ppm in candidate["actual_drift_ppm_cases"]
    ]
    for row in rows:
        if row["selected_correction_ppm"] != row["actual_drift_ppm"]:
            raise ValueError("synthetic drift selection differs")
        if row["actual_drift_ppm"] == 0:
            if row["apply_correction"] is not candidate["zero_drift_apply_correction"]:
                raise ValueError("zero-drift decision differs")
        elif not row["apply_correction"]:
            raise ValueError("bounded synthetic drift correction was not applied")
    return rows


def replay_edge_silence_case(
    candidate: dict[str, Any], case_id: str, spec: dict[str, Any]
) -> dict[str, Any]:
    sample_rate = candidate["sample_rate_hz"]
    reference = synthetic_alignment_fixture(
        sample_rate, candidate["active_duration_seconds"]
    )
    leading_frames = round(spec["leading_silence_seconds"] * sample_rate)
    trailing_frames = round(spec["trailing_silence_seconds"] * sample_rate)
    test = [0.0] * leading_frames + reference + [0.0] * trailing_frames
    record = alignment.align_channels(
        reference_channels=[reference],
        test_channels=[test],
        reference_channel_map=["M"],
        test_channel_map=["M"],
        sample_rate_hz=sample_rate,
        recipe_identity=f"{candidate['fixture_id']}\0{case_id}",
    )
    reasons = record["support"]["reasons"]
    if record["status"] != spec["expected_status"]:
        raise ValueError(f"edge-silence status differs: {case_id}")
    expected_reason = spec.get("expected_reason")
    if expected_reason is not None and expected_reason not in reasons:
        raise ValueError(f"edge-silence reason differs: {case_id}")
    aligned = record["alignment"]
    return {
        "case_id": case_id,
        "leading_silence_seconds": spec["leading_silence_seconds"],
        "trailing_silence_seconds": spec["trailing_silence_seconds"],
        "leading_edge_exact_zero": all(value == 0.0 for value in test[:leading_frames]),
        "trailing_edge_exact_zero": all(
            value == 0.0 for value in test[len(test) - trailing_frames :]
        ),
        "alignment_status": record["status"],
        "alignment_reason_codes": reasons,
        "estimated_integer_delay_samples": aligned["integer_delay_samples"],
        "estimated_fractional_delay_samples": aligned[
            "fractional_delay_samples"
        ],
        "reported_total_edge_trim_seconds": aligned["edge_trim_seconds"],
        "expected_total_edge_silence_seconds": (
            spec["leading_silence_seconds"] + spec["trailing_silence_seconds"]
        ),
        "perceptual_truth_included": False,
    }


def replay_edge_silence_cases(plan: dict[str, Any]) -> list[dict[str, Any]]:
    candidate = plan["paired_edge_silence_candidate"]
    return [
        replay_edge_silence_case(
            candidate, "supported-paired-edges", candidate["supported_case"]
        ),
        replay_edge_silence_case(
            candidate, "over-limit-paired-edges", candidate["over_limit_case"]
        ),
    ]


def build_payload(plan: dict[str, Any], temporary_root: Path) -> dict[str, Any]:
    return {
        "isolated_dither_case": replay_dither_case(plan),
        "sample_rate_conversion_case": replay_sample_rate_conversion_case(
            plan, temporary_root
        ),
        "bounded_clock_drift_cases": replay_drift_cases(plan),
        "paired_edge_silence_cases": replay_edge_silence_cases(plan),
    }


def build_report(
    plan: dict[str, Any], plan_path: Path = PLAN_PATH
) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    topology = load_json(_bound(plan, "negative_control_topology_report"))
    if topology["decision"]["negative_class_scientific_coverage_complete"]:
        raise ValueError("bound topology unexpectedly reports scientific completion")
    historical_tools = load_json(_bound(plan, "historical_toolchain_bindings"))
    historical_ffmpeg = next(
        value
        for value in historical_tools["tool_bindings"]
        if value["tool_id"] == "ffmpeg_8_1_2_1"
    )
    new_ffmpeg = plan["sample_rate_conversion_candidate"]["tool"]
    if historical_ffmpeg["binary_sha256"] == new_ffmpeg["binary_sha256"]:
        raise ValueError("new FFmpeg successor must not reuse historical binary hash")
    require_disk_reserve(
        ROOT, plan["resources"]["minimum_free_disk_gib"]
    )
    payloads = []
    for _ in range(plan["resources"]["replay_count"]):
        with tempfile.TemporaryDirectory(
            prefix="lossytrace-negative-repair-"
        ) as temporary:
            payloads.append(build_payload(plan, Path(temporary)))
    payload_hashes = [sha256_bytes(canonical_bytes(value)) for value in payloads]
    if len(set(payload_hashes)) != 1:
        raise ValueError("synthetic technical repair replays differ")
    payload = payloads[0]
    return {
        "schema_version": 1,
        "report_id": plan["plan_id"],
        "state": "score_blind_synthetic_technical_repair_replayed",
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "authority": plan["authorization"],
        "resources": {
            "minimum_free_disk_gib_enforced": plan["resources"][
                "minimum_free_disk_gib"
            ],
            "maximum_workers_used": 1,
            "generated_audio_retained": False,
        },
        "replay_observation": {
            "fresh_temporary_replay_count": len(payloads),
            "payload_sha256s": payload_hashes,
            "byte_identical": len(set(payload_hashes)) == 1,
            "paths_included": False,
            "timing_included": False,
        },
        **payload,
        "summary": {
            "technical_candidate_count": 4,
            "isolated_dither_candidate_replayed": True,
            "sample_rate_conversion_candidate_replayed": True,
            "bounded_drift_cross_validation_replayed": True,
            "paired_leading_trailing_silence_replayed": True,
            "historical_ffmpeg_binding_reused": False,
            "actual_audio_accessed": False,
            "perceptual_metric_executed": False,
            "perceptual_truth_included": False,
            "listener_response_collected": False,
            "condition_selected": False,
            "public_verdict_enabled": False,
        },
        "decision": {
            "isolated_dither_technical_candidate_ready": True,
            "sample_rate_conversion_technical_candidate_ready": True,
            "bounded_drift_synthetic_decision_fixture_ready": True,
            "paired_edge_silence_synthetic_fixture_ready": True,
            "production_oracle_resampler_selected": False,
            "retained_audio_correction_validated": False,
            "perceptual_condition_selected": False,
            "human_truth_present": False,
            "negative_class_scientific_coverage_complete": False,
            "human_collection_authorized": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "next_responsible_human_decision": (
                "Decide whether these four repaired technical candidates and "
                "the corrected resource envelope justify exact condition and "
                "source-trait selection. A production drift resampler still "
                "requires separate binding and retained-audio validation; "
                "every perceptual and collection gate remains closed."
            ),
        },
        "claim_boundary": plan["claim_boundary"],
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != 1:
        errors.append("report schema_version differs")
    if report.get("state") != (
        "score_blind_synthetic_technical_repair_replayed"
    ):
        errors.append("report state differs")
    if report.get("authority") != EXPECTED_AUTHORIZATION:
        errors.append("report authority differs")
    replay = report.get("replay_observation", {})
    if (
        replay.get("fresh_temporary_replay_count") != 2
        or replay.get("byte_identical") is not True
        or len(set(replay.get("payload_sha256s", []))) != 1
        or replay.get("paths_included") is not False
        or replay.get("timing_included") is not False
    ):
        errors.append("replay observation differs")
    dither = report.get("isolated_dither_case", {})
    if (
        dither.get("noise_minimum_lsb") != -1
        or dither.get("noise_maximum_lsb") != 1
        or dither.get("bit_depth_change") is not False
        or dither.get("frame_shape_preserved") is not True
        or dither.get("changed_sample_count", 0) <= 0
        or dither.get("perceptual_truth_included") is not False
    ):
        errors.append("isolated dither replay differs")
    src = report.get("sample_rate_conversion_case", {})
    if (
        src.get("source_sample_rate_hz") != 48000
        or src.get("intermediate_sample_rate_hz") != 32000
        or src.get("output_sample_rate_hz") != 48000
        or src.get("input_output_differ") is not True
        or src.get("output_geometry_preserved") is not True
        or src.get("historical_ffmpeg_binding_reused") is not False
        or src.get("perceptual_truth_included") is not False
    ):
        errors.append("sample-rate conversion replay differs")
    drift = report.get("bounded_clock_drift_cases", [])
    if len(drift) != 3:
        errors.append("bounded-drift case count differs")
    else:
        for row in drift:
            if row.get("selected_correction_ppm") != row.get("actual_drift_ppm"):
                errors.append("bounded-drift selection differs")
            expected_apply = row.get("actual_drift_ppm") != 0
            if row.get("apply_correction") is not expected_apply:
                errors.append("bounded-drift apply decision differs")
            if row.get("selection_used_held_out_windows") is not False:
                errors.append("bounded-drift held-out isolation differs")
    edge = report.get("paired_edge_silence_cases", [])
    if len(edge) != 2:
        errors.append("paired-edge case count differs")
    else:
        by_id = {value["case_id"]: value for value in edge}
        if by_id.get("supported-paired-edges", {}).get("alignment_status") != "supported":
            errors.append("supported paired-edge status differs")
        over = by_id.get("over-limit-paired-edges", {})
        if (
            over.get("alignment_status") != "unsupported"
            or "excessive_trim" not in over.get("alignment_reason_codes", [])
        ):
            errors.append("over-limit paired-edge status differs")
    summary = report.get("summary", {})
    for key in (
        "historical_ffmpeg_binding_reused",
        "actual_audio_accessed",
        "perceptual_metric_executed",
        "perceptual_truth_included",
        "listener_response_collected",
        "condition_selected",
        "public_verdict_enabled",
    ):
        if summary.get(key) is not False:
            errors.append(f"summary {key} must be false")
    decision = report.get("decision", {})
    for key in (
        "production_oracle_resampler_selected",
        "retained_audio_correction_validated",
        "perceptual_condition_selected",
        "human_truth_present",
        "negative_class_scientific_coverage_complete",
        "human_collection_authorized",
        "no_reference_work_eligible",
        "public_verdict_enabled",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision {key} must be false")
    claims = report.get("claim_boundary")
    if not isinstance(claims, dict) or any(
        value is not False for value in claims.values()
    ):
        errors.append("report claim boundary must remain false")
    return sorted(set(errors))


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


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
                "technical_candidate_count": report["summary"][
                    "technical_candidate_count"
                ],
                "replays_byte_identical": report["replay_observation"][
                    "byte_identical"
                ],
                "actual_audio_accessed": report["summary"][
                    "actual_audio_accessed"
                ],
                "collection_authorized": report["decision"][
                    "human_collection_authorized"
                ],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
