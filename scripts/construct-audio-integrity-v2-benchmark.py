#!/usr/bin/env python3
"""Construct the frozen audio-integrity-v2 benchmark with atomic checkpoints."""

from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def import_script(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PRECONDITION_PATH = ROOT / "scripts" / "audio_integrity_v2_preconditioning.py"
TOOLCHAIN_PATH = ROOT / "scripts" / "freeze-audio-integrity-v2-toolchains.py"
FEASIBILITY_PATH = (
    ROOT / "scripts" / "audit-audio-integrity-v2-construction-feasibility.py"
)
PREFLIGHT_PATH = ROOT / "scripts" / "preflight-audio-integrity-v2-construction.py"
PRECONDITION = import_script("v2_constructor_preconditioning", PRECONDITION_PATH)
TOOLCHAIN = import_script("v2_constructor_toolchain", TOOLCHAIN_PATH)
FEASIBILITY = import_script("v2_constructor_feasibility", FEASIBILITY_PATH)
PREFLIGHT = import_script("v2_constructor_preflight", PREFLIGHT_PATH)

SCHEMA_VERSION = 1
CONSTRUCTION_ID = "lossytrace-v2-construction-20260802-001"
MINIMUM_FREE_RESERVE_BYTES = 15 * 1024**3
WRAPPER_EXTENSIONS = {"flac16": ".flac", "wav16": ".wav", "aiff16": ".aiff"}
PYTHON_TRANSFORMS = {
    "gain-minus6db-q31",
    "trim-head-250ms",
    "prepend-digital-silence-500ms",
    "duration-prefix-3s",
    "requantize-12bit-tpdf",
    "alternate-channel-topology",
}
EXTERNAL_TRANSFORMS = {"lowpass-16k-cascade8", "resample-roundtrip-32k"}
NOOP_TRANSFORMS = {"identity", "lossless-wrapper-rewrite"}
FORBIDDEN_PUBLIC_KEYS = {
    "assignment_id",
    "artifact_relative_path",
    "cell",
    "group_id",
    "input_artifact_id",
    "locator",
    "member_id",
    "output_root",
    "partition_group",
    "relative_path",
    "source_group",
    "source_id",
}


def load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
        temporary = Path(output.name)
    temporary.replace(path)
    fsync_directory(path.parent)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def validate_binding(path: Path, expected: Any, label: str) -> None:
    if not isinstance(expected, str) or not path.is_file():
        raise ValueError(f"{label} binding is absent")
    if sha256_file(path) != expected:
        raise ValueError(f"{label} binding differs")


def safe_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\0" in value:
        raise ValueError("constructor relative path differs")
    return value


def bind_tool_paths(
    manifest: dict[str, Any], private_paths: dict[str, Any]
) -> dict[str, Path]:
    config = TOOLCHAIN.build_base_probe_config(manifest, private_paths)
    bound, _ = TOOLCHAIN.BASE.bind_tools(config)
    return {tool_id: row["resolved_path"] for tool_id, row in bound.items()}


def expand_command(
    command: list[str],
    *,
    tool_paths: dict[str, Path],
    input_path: Path,
    output_value: str,
) -> list[str]:
    expanded = []
    for part in command:
        if part.startswith(TOOLCHAIN.TOOL_TOKEN_PREFIX) and part.endswith(">"):
            tool_id = part[len(TOOLCHAIN.TOOL_TOKEN_PREFIX) : -1]
            expanded.append(str(tool_paths[tool_id]))
        elif part == TOOLCHAIN.INPUT_TOKEN:
            expanded.append(str(input_path))
        elif part == TOOLCHAIN.OUTPUT_TOKEN:
            expanded.append(output_value)
        else:
            expanded.append(part)
    return expanded


def run_bound_command(
    command: list[str],
    *,
    tool_paths: dict[str, Path],
    input_path: Path,
    output_path: Path,
) -> None:
    TOOLCHAIN.run_public_command(
        command,
        tool_paths=tool_paths,
        input_path=input_path,
        output_path=output_path,
        timeout_seconds=180,
    )


def lookup_by(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    result = {row.get(field): row for row in rows}
    if None in result or len(result) != len(rows):
        raise ValueError(f"toolchain {field} identities differ")
    return result


def analysis_pcm_info(
    *,
    manifest: dict[str, Any],
    tool_paths: dict[str, Path],
    ffprobe: Path,
    artifact: Path,
) -> dict[str, Any]:
    header = FEASIBILITY.probe_audio_header(ffprobe, artifact)
    binding = manifest["analysis_decoder_binding"]
    command = expand_command(
        binding["command"],
        tool_paths=tool_paths,
        input_path=artifact,
        output_value="pipe:1",
    )
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=PRECONDITION.process_environment(),
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise RuntimeError("analysis decoder pipes are absent")
    digest = hashlib.sha256()
    byte_count = 0
    for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
        digest.update(chunk)
        byte_count += len(chunk)
    error = process.stderr.read().decode(errors="replace")
    return_code = process.wait(timeout=180)
    if return_code:
        raise ValueError(
            f"analysis decode failed with exit {return_code}: {error.strip()[-500:]}"
        )
    frame_bytes = header["native_channel_count"] * 2
    if byte_count == 0 or byte_count % frame_bytes:
        raise ValueError("analysis-decoded PCM shape differs")
    frame_count = byte_count // frame_bytes
    if frame_count != header["native_frame_count"]:
        raise ValueError("analysis-decoded PCM frame count differs from wrapper")
    return {
        "pcm_sha256": digest.hexdigest(),
        "sample_rate_hz": header["native_sample_rate_hz"],
        "channel_count": header["native_channel_count"],
        "frame_count": frame_count,
        "sample_width_bytes": 2,
    }


def apply_transform(
    *,
    transform_id: str,
    group_id: str,
    input_wave: Path,
    output_wave: Path,
    manifest: dict[str, Any],
    tool_paths: dict[str, Path],
) -> Path:
    if transform_id in NOOP_TRANSFORMS:
        return input_wave
    if transform_id in PYTHON_TRANSFORMS:
        sample_rate, channels, samples = TOOLCHAIN.read_wave(input_wave)
        output_channels, transformed = TOOLCHAIN.apply_python_transform(
            transform_id,
            sample_rate=sample_rate,
            channels=channels,
            samples=samples,
            group_id=group_id,
        )
        TOOLCHAIN.write_wave(
            output_wave, sample_rate, output_channels, transformed
        )
        return output_wave
    if transform_id in EXTERNAL_TRANSFORMS:
        sample_rate, _, _ = TOOLCHAIN.read_wave(input_wave)
        command = TOOLCHAIN.transform_command_for(
            manifest, transform_id, sample_rate
        )
        run_bound_command(
            command,
            tool_paths=tool_paths,
            input_path=input_wave,
            output_path=output_wave,
        )
        return output_wave
    raise ValueError(f"constructor transform is not frozen: {transform_id}")


def render_recipe(
    *,
    cell: dict[str, Any],
    base_flac: Path,
    output_path: Path,
    work: Path,
    manifest: dict[str, Any],
    tool_paths: dict[str, Path],
) -> dict[str, Any]:
    settings = lookup_by(manifest["expanded_encoder_settings"], "expanded_setting_id")
    decoders = lookup_by(manifest["history_decoder_bindings"], "history_decoder_id")
    wrappers = lookup_by(manifest["wrapper_bindings"], "wrapper_id")
    ffmpeg_decoder = decoders["ffmpeg_native_audio_8_1_2"]
    source_wave = work / "recipe-source.wav"
    run_bound_command(
        ffmpeg_decoder["command"],
        tool_paths=tool_paths,
        input_path=base_flac,
        output_path=source_wave,
    )
    source_info = TOOLCHAIN.BASE.wave_pcm_info(source_wave)
    bitstream_sha256 = None
    history_info = source_info
    transform_input = source_wave
    bitstream = None
    if cell["expectation"] == "controlled_positive":
        setting = settings[cell["expanded_setting_id"]]
        extension = setting["output_extension"]
        bitstream = work / f"controlled-history{extension}"
        run_bound_command(
            setting["command"],
            tool_paths=tool_paths,
            input_path=source_wave,
            output_path=bitstream,
        )
        bitstream_sha256 = sha256_file(bitstream)
        source_wave.unlink()
        history_wave = work / "history-decoded.wav"
        decoder = decoders[cell["history_decoder_id"]]
        run_bound_command(
            decoder["command"],
            tool_paths=tool_paths,
            input_path=bitstream,
            output_path=history_wave,
        )
        history_info = TOOLCHAIN.BASE.wave_pcm_info(history_wave)
        transform_input = history_wave
        bitstream.unlink()
    transformed_wave = work / "transformed.wav"
    transformed = apply_transform(
        transform_id=cell["transform_id"],
        group_id=cell["group_id"],
        input_wave=transform_input,
        output_wave=transformed_wave,
        manifest=manifest,
        tool_paths=tool_paths,
    )
    transformed_info = TOOLCHAIN.BASE.wave_pcm_info(transformed)
    if transformed != transform_input:
        transform_input.unlink()
    wrapper = wrappers[cell["wrapper_id"]]
    run_bound_command(
        wrapper["command"],
        tool_paths=tool_paths,
        input_path=transformed,
        output_path=output_path,
    )
    analysis = analysis_pcm_info(
        manifest=manifest,
        tool_paths=tool_paths,
        ffprobe=tool_paths["ffprobe_8_1_2_1"],
        artifact=output_path,
    )
    if (
        analysis["pcm_sha256"] != transformed_info["pcm_sha256"]
        or analysis["sample_rate_hz"] != transformed_info["sample_rate_hz"]
        or analysis["channel_count"] != transformed_info["channel_count"]
        or analysis["frame_count"] != transformed_info["frame_count"]
    ):
        raise ValueError("final wrapper differs from transformed signed-s16 PCM")
    observation = {
        "artifact_sha256": sha256_file(output_path),
        "artifact_bytes": output_path.stat().st_size,
        "analysis_pcm": analysis,
        "source_pcm": source_info,
        "history_pcm": history_info,
        "transformed_pcm": transformed_info,
        "codec_bitstream_sha256": bitstream_sha256,
    }
    return observation


def validate_plan(plan: dict[str, Any], paths: dict[str, Path]) -> None:
    state_and_scope = (plan.get("state"), plan.get("authorized_scope"))
    allowed_states = {
        (
            "construction_recipe_frozen_before_synthetic_replay",
            "synthetic_only",
        ),
        ("construction_recipe_frozen_before_smoke_replay", "smoke"),
        ("construction_recipe_frozen_before_full_run", "full"),
    }
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("construction_id") != CONSTRUCTION_ID
        or state_and_scope not in allowed_states
        or plan.get("features_computed") is not False
        or plan.get("scores_opened") is not False
        or plan.get("public_verdict_enabled") is not False
    ):
        raise ValueError("constructor plan state differs")
    if state_and_scope[1] == "synthetic_only" and (
        plan.get("benchmark_source_audio_read") is not False
        or plan.get("benchmark_audio_generated") is not False
        or plan.get("synthetic_audio_authorized") is not True
    ):
        raise ValueError("synthetic constructor plan unexpectedly authorizes benchmark audio")
    if state_and_scope[1] in ("smoke", "full") and (
        plan.get("benchmark_source_audio_read") is not True
        or plan.get("benchmark_audio_generated") is not True
    ):
        raise ValueError("benchmark constructor plan lacks explicit audio authority")
    bindings = plan.get("bindings", {})
    for path_key, binding_key, label in (
        ("generator", "generator_sha256", "constructor generator"),
        (
            "preconditioning-module",
            "preconditioning_module_sha256",
            "preconditioning module",
        ),
        ("toolchain-generator", "toolchain_generator_sha256", "toolchain generator"),
        (
            "feasibility-generator",
            "feasibility_generator_sha256",
            "feasibility generator",
        ),
        ("preflight-generator", "preflight_generator_sha256", "preflight generator"),
        ("factor", "factor_levels_sha256", "factor levels"),
        ("toolchain", "toolchain_manifest_sha256", "toolchain manifest"),
        ("toolchain-result", "toolchain_result_sha256", "toolchain result"),
        (
            "public-decoder-result",
            "public_decoder_result_sha256",
            "public decoder result",
        ),
        (
            "preconditioning-result",
            "preconditioning_result_sha256",
            "preconditioning result",
        ),
        ("preflight-result", "preflight_result_sha256", "preflight result"),
        ("tool-paths", "private_tool_paths_sha256", "private tool paths"),
    ):
        validate_binding(paths[path_key], bindings.get(binding_key), label)
    if (
        plan.get("storage", {}).get("minimum_free_space_reserve_bytes")
        != MINIMUM_FREE_RESERVE_BYTES
        or plan.get("storage", {}).get("maximum_parallel_workers") != 1
    ):
        raise ValueError("constructor storage rule differs")
    if state_and_scope[1] in ("smoke", "full"):
        for path_key, binding_key, label in (
            (
                "source-allocation",
                "private_source_allocation_sha256",
                "source allocation",
            ),
            (
                "candidate-index",
                "private_candidate_index_sha256",
                "candidate index",
            ),
            (
                "assignment",
                "private_fractional_assignment_sha256",
                "fractional assignment",
            ),
            (
                "assignment-result",
                "public_fractional_assignment_result_sha256",
                "fractional assignment result",
            ),
            (
                "feasibility-audit",
                "private_construction_feasibility_audit_sha256",
                "construction feasibility audit",
            ),
            (
                "feasibility-result",
                "public_construction_feasibility_result_sha256",
                "construction feasibility result",
            ),
        ):
            validate_binding(paths[path_key], bindings.get(binding_key), label)
        validate_binding(
            paths["constructor-probe-result"],
            bindings.get("constructor_probe_result_sha256"),
            "constructor probe result",
        )
    if state_and_scope[1] == "full":
        validate_binding(
            paths["smoke-result"],
            bindings.get("smoke_result_sha256"),
            "constructor smoke result",
        )


def generate_synthetic_base(
    *,
    manifest: dict[str, Any],
    tool_paths: dict[str, Path],
    work: Path,
    sample_rate_hz: int,
    channel_count: int,
) -> Path:
    source_wave = work / "synthetic-base.wav"
    TOOLCHAIN.BASE.generate_probe_wave(
        source_wave,
        sample_rate_hz=sample_rate_hz,
        frame_count=sample_rate_hz * 4,
        channel_count=channel_count,
    )
    wrapper = lookup_by(manifest["wrapper_bindings"], "wrapper_id")["flac16"]
    base_flac = work / "synthetic-base.flac"
    run_bound_command(
        wrapper["command"],
        tool_paths=tool_paths,
        input_path=source_wave,
        output_path=base_flac,
    )
    source_info = TOOLCHAIN.BASE.wave_pcm_info(source_wave)
    analysis = analysis_pcm_info(
        manifest=manifest,
        tool_paths=tool_paths,
        ffprobe=tool_paths["ffprobe_8_1_2_1"],
        artifact=base_flac,
    )
    if analysis["pcm_sha256"] != source_info["pcm_sha256"]:
        raise ValueError("synthetic base FLAC differs from source PCM")
    return base_flac


def synthetic_cell(case: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    setting_id = case.get("expanded_setting_id")
    if setting_id is None:
        expectation = "negative"
        codec_fields: dict[str, Any] = {}
    else:
        setting = lookup_by(
            manifest["expanded_encoder_settings"], "expanded_setting_id"
        )[setting_id]
        expectation = "controlled_positive"
        codec_fields = {
            "codec_family": setting["codec_family"],
            "expanded_setting_id": setting_id,
            "history_decoder_id": case["history_decoder_id"],
        }
    return {
        "assignment_id": hashlib.sha256(
            f"synthetic-constructor\0{case['fixture_id']}".encode()
        ).hexdigest(),
        "group_id": "synthetic-constructor-group",
        "evidence_partition": "synthetic_only",
        "expectation": expectation,
        "channel_treatment_id": (
            "mono" if case["channel_count"] == 1 else "stereo"
        ),
        "target_sample_rate_hz": case["sample_rate_hz"],
        "transform_id": case["transform_id"],
        "wrapper_id": case["wrapper_id"],
        **codec_fields,
    }


def run_synthetic_probe(
    *,
    plan: dict[str, Any],
    plan_sha256: str,
    manifest: dict[str, Any],
    tool_paths: dict[str, Path],
    work_root: Path,
) -> dict[str, Any]:
    rows = []
    with tempfile.TemporaryDirectory(
        prefix="lossytrace-v2-constructor-probe-", dir=work_root
    ) as name:
        temporary = Path(name)
        for case in plan["synthetic_cases"]:
            case_root = temporary / case["fixture_id"]
            case_root.mkdir()
            base_flac = generate_synthetic_base(
                manifest=manifest,
                tool_paths=tool_paths,
                work=case_root,
                sample_rate_hz=case["sample_rate_hz"],
                channel_count=case["channel_count"],
            )
            cell = synthetic_cell(case, manifest)
            observations = []
            extension = WRAPPER_EXTENSIONS[cell["wrapper_id"]]
            for replay in (1, 2):
                replay_root = case_root / f"render-{replay}"
                replay_root.mkdir()
                output = replay_root / f"artifact{extension}"
                observations.append(
                    render_recipe(
                        cell=cell,
                        base_flac=base_flac,
                        output_path=output,
                        work=replay_root,
                        manifest=manifest,
                        tool_paths=tool_paths,
                    )
                )
            if observations[0] != observations[1]:
                raise ValueError(
                    f"synthetic constructor rendering differs: {case['fixture_id']}"
                )
            rows.append(
                {
                    "fixture_id": case["fixture_id"],
                    "expectation": cell["expectation"],
                    "codec_family": cell.get("codec_family"),
                    "encoder_id": (
                        lookup_by(
                            manifest["expanded_encoder_settings"],
                            "expanded_setting_id",
                        )[cell["expanded_setting_id"]]["encoder_id"]
                        if cell["expectation"] == "controlled_positive"
                        else None
                    ),
                    "history_decoder_id": cell.get("history_decoder_id"),
                    "transform_id": cell["transform_id"],
                    "wrapper_id": cell["wrapper_id"],
                    "sample_rate_hz": case["sample_rate_hz"],
                    "channel_count": case["channel_count"],
                    **observations[0],
                    "within_run_replays_byte_identical": True,
                }
            )
    result = {
        "schema_version": SCHEMA_VERSION,
        "construction_id": CONSTRUCTION_ID,
        "state": "constructor_synthetic_run_evidence",
        "plan_sha256": plan_sha256,
        "generator_sha256": sha256_file(Path(__file__).resolve()),
        "benchmark_source_audio_read": False,
        "benchmark_audio_generated": False,
        "synthetic_audio_generated": True,
        "features_computed": False,
        "scores_opened": False,
        "public_verdict_enabled": False,
        "paths_redacted": True,
        "cases": rows,
        "summary": {
            "synthetic_case_count": len(rows),
            "within_run_replays_byte_identical": True,
            "codec_families": sorted(
                {row["codec_family"] for row in rows if row["codec_family"]}
            ),
            "encoder_ids": sorted(
                {row["encoder_id"] for row in rows if row["encoder_id"]}
            ),
            "history_decoder_ids": sorted(
                {
                    row["history_decoder_id"]
                    for row in rows
                    if row["history_decoder_id"]
                }
            ),
            "transform_ids": sorted({row["transform_id"] for row in rows}),
            "wrapper_ids": sorted({row["wrapper_id"] for row in rows}),
        },
        "reproducibility": {
            "complete_replays_required": 2,
            "complete_replays_observed": 1,
            "byte_identical": None,
        },
    }
    assert_public_path_free(result)
    return result


def attest_probe(run_paths: list[Path], plan_path: Path) -> dict[str, Any]:
    if len(run_paths) != 2:
        raise ValueError("constructor probe requires exactly two complete replays")
    if run_paths[0].read_bytes() != run_paths[1].read_bytes():
        raise ValueError("constructor synthetic replay reports differ")
    result = load_object(run_paths[0])
    if (
        result.get("state") != "constructor_synthetic_run_evidence"
        or result.get("plan_sha256") != sha256_file(plan_path)
    ):
        raise ValueError("constructor synthetic replay binding differs")
    final = dict(result)
    final["state"] = "constructor_synthetic_evidence"
    final["reproducibility"] = {
        "complete_replays_required": 2,
        "complete_replays_observed": 2,
        "run_reports_byte_identical": True,
        "run_report_sha256": sha256_file(run_paths[0]),
        "plan_sha256": sha256_file(plan_path),
    }
    assert_public_path_free(final)
    return final


def smoke_cells(
    cells: list[dict[str, Any]], feasibility_by_id: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = collections.defaultdict(list)
    for cell in cells:
        if cell["expectation"] == "controlled_positive":
            buckets[("setting", cell["expanded_setting_id"])].append(cell)
            buckets[
                (
                    "decoder-codec",
                    cell["history_decoder_id"],
                    cell["codec_family"],
                )
            ].append(cell)
            buckets[
                (
                    "positive-transform-codec",
                    cell["transform_id"],
                    cell["codec_family"],
                )
            ].append(cell)
        buckets[
            (
                "partition-transform-wrapper-expectation",
                cell["evidence_partition"],
                cell["transform_id"],
                cell["wrapper_id"],
                cell["expectation"],
            )
        ].append(cell)
        header = feasibility_by_id[cell["group_id"]]
        buckets[
            (
                "native-format-channel-rate",
                header["codec_name"],
                cell["channel_treatment_id"],
                cell["target_sample_rate_hz"],
            )
        ].append(cell)
    selected = {
        min(rows, key=lambda row: row["assignment_id"])["assignment_id"]
        for rows in buckets.values()
    }
    return sorted(
        [cell for cell in cells if cell["assignment_id"] in selected],
        key=lambda row: row["assignment_id"],
    )


def artifact_relative_path(cell: dict[str, Any]) -> str:
    identity = cell["assignment_id"]
    extension = WRAPPER_EXTENSIONS[cell["wrapper_id"]]
    return safe_relative_path(f"cases/{identity[:2]}/{identity}{extension}")


def checkpoint_relative_path(cell: dict[str, Any]) -> str:
    identity = cell["assignment_id"]
    return safe_relative_path(f"checkpoints/{identity[:2]}/{identity}.json")


def checkpoint_binding(
    *,
    plan_sha256: str,
    assignment_sha256: str,
    cell: dict[str, Any],
    artifact_relative: str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "construction_id": CONSTRUCTION_ID,
        "state": "constructed_cell_checkpoint",
        "plan_sha256": plan_sha256,
        "generator_sha256": sha256_file(Path(__file__).resolve()),
        "assignment_sha256": assignment_sha256,
        "benchmark_audio_generated": True,
        "features_computed": False,
        "scores_opened": False,
        "public_verdict_enabled": False,
        "cell": cell,
        "artifact_relative_path": artifact_relative,
        **observation,
    }


def validate_checkpoint(
    *,
    checkpoint: dict[str, Any],
    checkpoint_path: Path,
    artifact_path: Path,
    artifact_relative: str,
    cell: dict[str, Any],
    plan_sha256: str,
    assignment_sha256: str,
    manifest: dict[str, Any],
    tool_paths: dict[str, Path],
) -> None:
    if (
        checkpoint.get("schema_version") != SCHEMA_VERSION
        or checkpoint.get("construction_id") != CONSTRUCTION_ID
        or checkpoint.get("state") != "constructed_cell_checkpoint"
        or checkpoint.get("plan_sha256") != plan_sha256
        or checkpoint.get("generator_sha256")
        != sha256_file(Path(__file__).resolve())
        or checkpoint.get("assignment_sha256") != assignment_sha256
        or checkpoint.get("cell") != cell
        or checkpoint.get("artifact_relative_path") != artifact_relative
        or checkpoint.get("benchmark_audio_generated") is not True
        or checkpoint.get("features_computed") is not False
        or checkpoint.get("scores_opened") is not False
        or checkpoint.get("public_verdict_enabled") is not False
        or not artifact_path.is_file()
        or checkpoint.get("artifact_bytes") != artifact_path.stat().st_size
        or checkpoint.get("artifact_sha256") != sha256_file(artifact_path)
    ):
        raise ValueError(f"constructed cell checkpoint differs: {checkpoint_path}")
    analysis = analysis_pcm_info(
        manifest=manifest,
        tool_paths=tool_paths,
        ffprobe=tool_paths["ffprobe_8_1_2_1"],
        artifact=artifact_path,
    )
    if checkpoint.get("analysis_pcm") != analysis:
        raise ValueError(f"constructed cell canonical PCM differs: {checkpoint_path}")


def commit_artifact(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as artifact:
        os.fsync(artifact.fileno())
    source.replace(target)
    fsync_directory(target.parent)


def construct_base_flac(
    *,
    source_path: Path,
    source_row: dict[str, Any],
    header: dict[str, Any],
    provider_start: int,
    provider_end: int,
    channel_treatment_id: str,
    target_sample_rate_hz: int,
    output_flac: Path,
    work: Path,
    manifest: dict[str, Any],
    tool_paths: dict[str, Path],
) -> None:
    wave_path = work / (
        f"precondition-{channel_treatment_id}-{target_sample_rate_hz}.wav"
    )
    observation = PRECONDITION.precondition_to_wave(
        ffmpeg=tool_paths["ffmpeg_8_1_2_1"],
        input_path=source_path,
        output_path=wave_path,
        group_id=source_row["group_id"],
        member_id=source_row["member_id"],
        provider_start_frame=provider_start,
        provider_end_frame_exclusive=provider_end,
        native_sample_rate_hz=header["native_sample_rate_hz"],
        native_channel_count=header["native_channel_count"],
        channel_treatment_id=channel_treatment_id,
        target_sample_rate_hz=target_sample_rate_hz,
    )
    wrapper = lookup_by(manifest["wrapper_bindings"], "wrapper_id")["flac16"]
    run_bound_command(
        wrapper["command"],
        tool_paths=tool_paths,
        input_path=wave_path,
        output_path=output_flac,
    )
    analysis = analysis_pcm_info(
        manifest=manifest,
        tool_paths=tool_paths,
        ffprobe=tool_paths["ffprobe_8_1_2_1"],
        artifact=output_flac,
    )
    if (
        analysis["pcm_sha256"] != observation["pcm_sha256"]
        or analysis["sample_rate_hz"] != observation["output_sample_rate_hz"]
        or analysis["channel_count"] != observation["output_channel_count"]
        or analysis["frame_count"] != observation["output_frame_count"]
    ):
        raise ValueError("constructed base FLAC differs from preconditioned PCM")
    wave_path.unlink()


def construct_cells(
    *,
    scope: str,
    plan: dict[str, Any],
    plan_sha256: str,
    assignment_sha256: str,
    allocation: dict[str, Any],
    assignment: dict[str, Any],
    feasibility: dict[str, Any],
    manifest: dict[str, Any],
    tool_paths: dict[str, Path],
    v1_root: Path,
    source_root: Path,
    output_root: Path,
    work_root: Path,
    private_manifest_path: Path,
    public_run_path: Path,
) -> dict[str, Any]:
    authorized_scope = plan.get("authorized_scope")
    if scope == "smoke" and authorized_scope not in ("smoke", "full"):
        raise ValueError("constructor plan does not authorize benchmark smoke audio")
    if scope == "full" and authorized_scope != "full":
        raise ValueError("constructor plan does not authorize full benchmark audio")
    if scope not in ("smoke", "full"):
        raise ValueError("constructor benchmark scope differs")
    selected_by_id = {
        row["group_id"]: row for row in allocation["selected"]
    }
    feasibility_by_id = {row["group_id"]: row for row in feasibility["groups"]}
    cells = assignment["cells"]
    scoped_cells = (
        smoke_cells(cells, feasibility_by_id) if scope == "smoke" else cells
    )
    expected_smoke_count = plan.get("smoke_selection", {}).get(
        "expected_cell_count"
    )
    if scope == "smoke" and (
        not isinstance(expected_smoke_count, int)
        or len(scoped_cells) != expected_smoke_count
    ):
        raise ValueError("constructor smoke selection count differs")
    scoped_by_group: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for cell in scoped_cells:
        scoped_by_group[cell["group_id"]].append(cell)
    output_root.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output_root).free < MINIMUM_FREE_RESERVE_BYTES:
        raise ValueError("constructor output volume is below the frozen reserve")
    checkpoints = []
    for group_id in sorted(scoped_by_group):
        group_cells = sorted(
            scoped_by_group[group_id], key=lambda row: row["assignment_id"]
        )
        pending = []
        for cell in group_cells:
            artifact_relative = artifact_relative_path(cell)
            checkpoint_relative = checkpoint_relative_path(cell)
            artifact_path = output_root / artifact_relative
            checkpoint_path = output_root / checkpoint_relative
            if checkpoint_path.is_file():
                checkpoint = load_object(checkpoint_path)
                validate_checkpoint(
                    checkpoint=checkpoint,
                    checkpoint_path=checkpoint_path,
                    artifact_path=artifact_path,
                    artifact_relative=artifact_relative,
                    cell=cell,
                    plan_sha256=plan_sha256,
                    assignment_sha256=assignment_sha256,
                    manifest=manifest,
                    tool_paths=tool_paths,
                )
                checkpoints.append(checkpoint)
            else:
                if artifact_path.exists():
                    artifact_path.unlink()
                pending.append(cell)
        if not pending:
            continue
        source_row = selected_by_id[group_id]
        expected_header = feasibility_by_id[group_id]
        with tempfile.TemporaryDirectory(
            prefix=f"lossytrace-v2-group-{group_id[:12]}-", dir=work_root
        ) as name:
            group_work = Path(name)
            source_path = FEASIBILITY.source_path_for(
                source_row, v1_root, source_root, group_work
            )
            header = FEASIBILITY.probe_audio_header(
                tool_paths["ffprobe_8_1_2_1"], source_path
            )
            for field in (
                "native_sample_rate_hz",
                "native_channel_count",
                "native_frame_count",
            ):
                if header[field] != expected_header[field]:
                    raise ValueError(f"constructor source header differs on {field}")
            provider_start, provider_end = FEASIBILITY.provider_window(
                source_row, header
            )
            base_by_key: dict[tuple[str, int], Path] = {}
            for channel_treatment_id, target_sample_rate_hz in sorted(
                {
                    (cell["channel_treatment_id"], cell["target_sample_rate_hz"])
                    for cell in pending
                }
            ):
                base_flac = group_work / (
                    f"base-{channel_treatment_id}-{target_sample_rate_hz}.flac"
                )
                construct_base_flac(
                    source_path=source_path,
                    source_row=source_row,
                    header=header,
                    provider_start=provider_start,
                    provider_end=provider_end,
                    channel_treatment_id=channel_treatment_id,
                    target_sample_rate_hz=target_sample_rate_hz,
                    output_flac=base_flac,
                    work=group_work,
                    manifest=manifest,
                    tool_paths=tool_paths,
                )
                base_by_key[(channel_treatment_id, target_sample_rate_hz)] = base_flac
            for cell in pending:
                artifact_relative = artifact_relative_path(cell)
                checkpoint_relative = checkpoint_relative_path(cell)
                artifact_path = output_root / artifact_relative
                checkpoint_path = output_root / checkpoint_relative
                artifact_path.parent.mkdir(parents=True, exist_ok=True)
                checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
                extension = WRAPPER_EXTENSIONS[cell["wrapper_id"]]
                temporary_output = artifact_path.parent / (
                    f".{cell['assignment_id']}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
                    f"{extension}"
                )
                recipe_work = group_work / f"recipe-{cell['assignment_id']}"
                recipe_work.mkdir()
                observation = render_recipe(
                    cell=cell,
                    base_flac=base_by_key[
                        (
                            cell["channel_treatment_id"],
                            cell["target_sample_rate_hz"],
                        )
                    ],
                    output_path=temporary_output,
                    work=recipe_work,
                    manifest=manifest,
                    tool_paths=tool_paths,
                )
                commit_artifact(temporary_output, artifact_path)
                checkpoint = checkpoint_binding(
                    plan_sha256=plan_sha256,
                    assignment_sha256=assignment_sha256,
                    cell=cell,
                    artifact_relative=artifact_relative,
                    observation=observation,
                )
                write_json_atomic(checkpoint_path, checkpoint)
                checkpoints.append(checkpoint)
                shutil.rmtree(recipe_work)
                if shutil.disk_usage(output_root).free < MINIMUM_FREE_RESERVE_BYTES:
                    raise ValueError(
                        "constructor output volume fell below the frozen reserve"
                    )
    checkpoints.sort(key=lambda row: row["cell"]["assignment_id"])
    if len(checkpoints) != len(scoped_cells):
        raise ValueError("constructed checkpoint count differs")
    private_manifest = {
        "schema_version": SCHEMA_VERSION,
        "construction_id": CONSTRUCTION_ID,
        "state": f"constructed_{scope}_private_manifest",
        "scope": scope,
        "plan_sha256": plan_sha256,
        "generator_sha256": sha256_file(Path(__file__).resolve()),
        "assignment_sha256": assignment_sha256,
        "benchmark_audio_generated": True,
        "features_computed": False,
        "scores_opened": False,
        "public_verdict_enabled": False,
        "checkpoints": checkpoints,
    }
    write_json_atomic(private_manifest_path, private_manifest)
    public = public_construction_aggregate(
        private_manifest, sha256_file(private_manifest_path)
    )
    write_json_atomic(public_run_path, public)
    return public


def count_rows(
    counter: collections.Counter[tuple[Any, ...]], fields: list[str]
) -> list[dict[str, Any]]:
    return [
        {**dict(zip(fields, key, strict=True)), "count": count}
        for key, count in sorted(
            counter.items(), key=lambda item: tuple(str(value) for value in item[0])
        )
    ]


def public_construction_aggregate(
    private_manifest: dict[str, Any], private_manifest_sha256: str
) -> dict[str, Any]:
    checkpoints = private_manifest["checkpoints"]
    cell_counts = collections.Counter(
        (
            row["cell"]["evidence_partition"],
            row["cell"]["expectation"],
            row["cell"].get("codec_family"),
            row["cell"]["transform_id"],
            row["cell"]["wrapper_id"],
        )
        for row in checkpoints
    )
    byte_counts = collections.Counter(
        row["cell"]["evidence_partition"] for row in checkpoints
    )
    bytes_by_partition = collections.Counter()
    for row in checkpoints:
        bytes_by_partition[row["cell"]["evidence_partition"]] += row[
            "artifact_bytes"
        ]
    artifact_digest = hashlib.sha256()
    pcm_digest = hashlib.sha256()
    for row in checkpoints:
        artifact_digest.update(bytes.fromhex(row["artifact_sha256"]))
        pcm_digest.update(bytes.fromhex(row["analysis_pcm"]["pcm_sha256"]))
    result = {
        "schema_version": SCHEMA_VERSION,
        "construction_id": CONSTRUCTION_ID,
        "state": f"constructor_{private_manifest['scope']}_path_free_run_evidence",
        "scope": private_manifest["scope"],
        "plan_sha256": private_manifest["plan_sha256"],
        "generator_sha256": private_manifest["generator_sha256"],
        "assignment_sha256": private_manifest["assignment_sha256"],
        "private_manifest_sha256": private_manifest_sha256,
        "benchmark_audio_generated": True,
        "features_computed": False,
        "scores_opened": False,
        "public_verdict_enabled": False,
        "paths_redacted": True,
        "private_ids_included": False,
        "cell_counts": count_rows(
            cell_counts,
            [
                "evidence_partition",
                "expectation",
                "codec_family",
                "transform_id",
                "wrapper_id",
            ],
        ),
        "partition_storage": [
            {
                "evidence_partition": partition,
                "cell_count": byte_counts[partition],
                "artifact_bytes": bytes_by_partition[partition],
            }
            for partition in sorted(byte_counts)
        ],
        "summary": {
            "cell_count": len(checkpoints),
            "controlled_positive_count": sum(
                row["cell"]["expectation"] == "controlled_positive"
                for row in checkpoints
            ),
            "negative_count": sum(
                row["cell"]["expectation"] == "negative"
                for row in checkpoints
            ),
            "artifact_bytes": sum(row["artifact_bytes"] for row in checkpoints),
            "artifact_sha256_set_digest": artifact_digest.hexdigest(),
            "analysis_pcm_sha256_set_digest": pcm_digest.hexdigest(),
            "all_checkpoints_validated": True,
        },
        "reproducibility": {
            "complete_replays_required": 2 if private_manifest["scope"] == "smoke" else 1,
            "complete_replays_observed": 1,
            "byte_identical": None,
        },
    }
    assert_public_path_free(result)
    return result


def assert_public_path_free(value: Any, key: str | None = None) -> None:
    if key in FORBIDDEN_PUBLIC_KEYS:
        raise ValueError(f"public constructor evidence contains private key: {key}")
    if isinstance(value, dict):
        for child_key, child in value.items():
            assert_public_path_free(child, child_key)
    elif isinstance(value, list):
        for child in value:
            assert_public_path_free(child, key)
    elif isinstance(value, str) and (
        value.startswith("/") or "Library/Application Support" in value
    ):
        raise ValueError("public constructor evidence contains a private path")


def attest_construction(
    *,
    scope: str,
    private_manifest_paths: list[Path],
    run_paths: list[Path],
    plan_path: Path,
) -> dict[str, Any]:
    required = 2 if scope == "smoke" else 1
    if len(private_manifest_paths) != required or len(run_paths) != required:
        raise ValueError("constructor attestation replay count differs")
    if required == 2 and (
        private_manifest_paths[0].read_bytes() != private_manifest_paths[1].read_bytes()
        or run_paths[0].read_bytes() != run_paths[1].read_bytes()
    ):
        raise ValueError("constructor smoke replays differ")
    result = load_object(run_paths[0])
    if (
        result.get("state") != f"constructor_{scope}_path_free_run_evidence"
        or result.get("scope") != scope
        or result.get("plan_sha256") != sha256_file(plan_path)
        or result.get("private_manifest_sha256")
        != sha256_file(private_manifest_paths[0])
    ):
        raise ValueError("constructor run binding differs")
    final = dict(result)
    final["state"] = f"constructor_{scope}_path_free_evidence"
    final["reproducibility"] = {
        "complete_replays_required": required,
        "complete_replays_observed": required,
        "private_manifests_byte_identical": True if required == 2 else None,
        "run_reports_byte_identical": True if required == 2 else None,
        "private_manifest_sha256": sha256_file(private_manifest_paths[0]),
        "run_report_sha256": sha256_file(run_paths[0]),
        "plan_sha256": sha256_file(plan_path),
    }
    assert_public_path_free(final)
    return final


def add_common_public_arguments(parser: argparse.ArgumentParser) -> None:
    for name in (
        "plan",
        "factor",
        "toolchain",
        "toolchain-result",
        "public-decoder-result",
        "preconditioning-result",
        "preflight-result",
        "tool-paths",
    ):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--constructor-probe-result", type=Path)
    parser.add_argument("--smoke-result", type=Path)


def resolved_paths(args: argparse.Namespace, names: tuple[str, ...]) -> dict[str, Path]:
    paths = {}
    for name in names:
        value = getattr(args, name)
        if value is not None:
            paths[name.replace("_", "-")] = value.expanduser().resolve()
    paths.update(
        {
            "generator": Path(__file__).resolve(),
            "preconditioning-module": PRECONDITION_PATH,
            "toolchain-generator": TOOLCHAIN_PATH,
            "feasibility-generator": FEASIBILITY_PATH,
            "preflight-generator": PREFLIGHT_PATH,
        }
    )
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    probe = subparsers.add_parser("probe")
    add_common_public_arguments(probe)
    probe.add_argument("--work-root", required=True, type=Path)
    probe.add_argument("--output", required=True, type=Path)

    attest_probe_parser = subparsers.add_parser("attest-probe")
    attest_probe_parser.add_argument("--plan", required=True, type=Path)
    attest_probe_parser.add_argument("--run", required=True, type=Path, action="append")
    attest_probe_parser.add_argument("--output", required=True, type=Path)

    construct = subparsers.add_parser("construct")
    add_common_public_arguments(construct)
    construct.add_argument("--scope", required=True, choices=("smoke", "full"))
    for name in (
        "source-allocation",
        "candidate-index",
        "assignment",
        "assignment-result",
        "feasibility-audit",
        "feasibility-result",
        "v1-root",
        "source-root",
        "output-root",
        "work-root",
        "private-manifest",
        "public-run",
    ):
        construct.add_argument(f"--{name}", required=True, type=Path)

    attest_parser = subparsers.add_parser("attest-construction")
    attest_parser.add_argument("--scope", required=True, choices=("smoke", "full"))
    attest_parser.add_argument("--plan", required=True, type=Path)
    attest_parser.add_argument(
        "--private-manifest", required=True, type=Path, action="append"
    )
    attest_parser.add_argument("--run", required=True, type=Path, action="append")
    attest_parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "attest-probe":
        result = attest_probe(
            [path.expanduser().resolve() for path in args.run],
            args.plan.expanduser().resolve(),
        )
        write_json_atomic(args.output.expanduser().resolve(), result)
        print("attested two byte-identical constructor synthetic replays")
        return 0
    if args.command == "attest-construction":
        result = attest_construction(
            scope=args.scope,
            private_manifest_paths=[
                path.expanduser().resolve() for path in args.private_manifest
            ],
            run_paths=[path.expanduser().resolve() for path in args.run],
            plan_path=args.plan.expanduser().resolve(),
        )
        write_json_atomic(args.output.expanduser().resolve(), result)
        print(f"attested constructor {args.scope} evidence")
        return 0

    common_names = (
        "plan",
        "factor",
        "toolchain",
        "toolchain_result",
        "public_decoder_result",
        "preconditioning_result",
        "preflight_result",
        "tool_paths",
        "constructor_probe_result",
        "smoke_result",
    )
    extra_names = (
        "source_allocation",
        "candidate_index",
        "assignment",
        "assignment_result",
        "feasibility_audit",
        "feasibility_result",
        "v1_root",
        "source_root",
        "output_root",
        "work_root",
        "private_manifest",
        "public_run",
    )
    paths = resolved_paths(
        args, common_names + (extra_names if args.command == "construct" else ("work_root", "output"))
    )
    plan = load_object(paths["plan"])
    validate_plan(plan, paths)
    manifest = load_object(paths["toolchain"])
    tool_paths = bind_tool_paths(manifest, load_object(paths["tool-paths"]))
    if args.command == "probe":
        paths["work-root"].mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(paths["work-root"]).free < MINIMUM_FREE_RESERVE_BYTES:
            raise ValueError("constructor probe volume is below the frozen reserve")
        result = run_synthetic_probe(
            plan=plan,
            plan_sha256=sha256_file(paths["plan"]),
            manifest=manifest,
            tool_paths=tool_paths,
            work_root=paths["work-root"],
        )
        write_json_atomic(paths["output"], result)
        print(
            f"replayed {result['summary']['synthetic_case_count']} synthetic "
            "constructor cases without benchmark audio"
        )
        return 0

    allocation = load_object(paths["source-allocation"])
    candidate_index = load_object(paths["candidate-index"])
    assignment = load_object(paths["assignment"])
    assignment_result = load_object(paths["assignment-result"])
    feasibility = load_object(paths["feasibility-audit"])
    feasibility_result = load_object(paths["feasibility-result"])
    preconditioning_result = load_object(paths["preconditioning-result"])
    factor = load_object(paths["factor"])
    groups, cells, _ = PREFLIGHT.validate_private_inputs(
        allocation,
        candidate_index,
        assignment,
        assignment_result,
        feasibility,
        feasibility_result,
        preconditioning_result,
        factor,
        manifest,
        paths,
    )
    PREFLIGHT.validate_cell_lineage(cells, groups, factor, manifest)
    try:
        os.nice(10)
    except OSError:
        pass
    result = construct_cells(
        scope=args.scope,
        plan=plan,
        plan_sha256=sha256_file(paths["plan"]),
        assignment_sha256=sha256_file(paths["assignment"]),
        allocation=allocation,
        assignment=assignment,
        feasibility=feasibility,
        manifest=manifest,
        tool_paths=tool_paths,
        v1_root=paths["v1-root"],
        source_root=paths["source-root"],
        output_root=paths["output-root"],
        work_root=paths["work-root"],
        private_manifest_path=paths["private-manifest"],
        public_run_path=paths["public-run"],
    )
    print(
        f"constructed {result['summary']['cell_count']} {args.scope} cells "
        "without features or scores"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
