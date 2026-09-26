#!/usr/bin/env python3
"""Replay synthetic v2 source-preconditioning paths without benchmark audio."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
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
PRECONDITION = import_script("v2_preconditioning", PRECONDITION_PATH)
TOOLCHAIN = import_script("v2_frozen_toolchains", TOOLCHAIN_PATH)

SCHEMA_VERSION = 1
AUDIT_ID = "lossytrace-v2-preconditioning-audit-20260802-001"
MINIMUM_FREE_RESERVE_BYTES = 15 * 1024**3
FORBIDDEN_PUBLIC_KEYS = {
    "group_id",
    "member_id",
    "path",
    "relative_path",
    "source_group",
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
        temporary = Path(output.name)
    temporary.replace(path)


def validate_binding(path: Path, expected: Any, label: str) -> None:
    if not isinstance(expected, str) or not path.is_file():
        raise ValueError(f"{label} binding is absent")
    if sha256_file(path) != expected:
        raise ValueError(f"{label} binding differs")


def validate_plan(
    plan: dict[str, Any],
    factor_path: Path,
    toolchain_path: Path,
    toolchain_result_path: Path,
    decoder_result_path: Path,
    feasibility_result_path: Path,
    tool_paths_path: Path,
) -> None:
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("audit_id") != AUDIT_ID
        or plan.get("state")
        != "preconditioning_audit_frozen_before_synthetic_replay"
        or plan.get("benchmark_source_audio_read") is not False
        or plan.get("benchmark_audio_generated") is not False
        or plan.get("features_computed") is not False
        or plan.get("scores_opened") is not False
        or plan.get("construction_authorized") is not False
    ):
        raise ValueError("preconditioning audit plan state differs")
    bindings = plan.get("bindings", {})
    for path, key, label in (
        (Path(__file__).resolve(), "audit_generator_sha256", "audit generator"),
        (PRECONDITION_PATH, "preconditioning_module_sha256", "preconditioning module"),
        (TOOLCHAIN_PATH, "toolchain_generator_sha256", "toolchain generator"),
        (factor_path, "factor_levels_sha256", "factor levels"),
        (toolchain_path, "toolchain_manifest_sha256", "toolchain manifest"),
        (toolchain_result_path, "toolchain_result_sha256", "toolchain result"),
        (decoder_result_path, "public_decoder_result_sha256", "public decoder result"),
        (
            feasibility_result_path,
            "construction_feasibility_result_sha256",
            "construction feasibility result",
        ),
        (tool_paths_path, "private_tool_paths_sha256", "private tool paths"),
    ):
        validate_binding(path, bindings.get(key), label)
    if plan.get("storage", {}).get("minimum_free_space_reserve_bytes") != (
        MINIMUM_FREE_RESERVE_BYTES
    ):
        raise ValueError("preconditioning audit reserve differs")


def bind_tool_paths(
    manifest: dict[str, Any], private_paths: dict[str, Any]
) -> dict[str, Path]:
    config = TOOLCHAIN.build_base_probe_config(manifest, private_paths)
    bound, _ = TOOLCHAIN.BASE.bind_tools(config)
    return {tool_id: row["resolved_path"] for tool_id, row in bound.items()}


def write_synthetic_s16_wave(
    path: Path, *, sample_rate_hz: int, channel_count: int, frame_count: int
) -> None:
    if sample_rate_hz < 1 or channel_count not in (1, 2) or frame_count < 1:
        raise ValueError("synthetic fixture shape differs")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channel_count)
        output.setsampwidth(2)
        output.setframerate(sample_rate_hz)
        chunk_frames = 8192
        for start in range(0, frame_count, chunk_frames):
            end = min(frame_count, start + chunk_frames)
            samples = []
            for frame in range(start, end):
                for channel in range(channel_count):
                    samples.append(
                        ((frame * 97 + channel * 811 + (frame // 257) * 37) % 60001)
                        - 30000
                    )
            output.writeframesraw(struct.pack(f"<{len(samples)}h", *samples))


def convert_fixture_format(
    ffmpeg: Path, source: Path, output: Path, source_format: str
) -> None:
    codec = {"pcm_s24le": "pcm_s24le", "pcm_f32le": "pcm_f32le"}.get(
        source_format
    )
    if codec is None:
        raise ValueError("synthetic conversion format differs")
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-fflags",
        "+bitexact",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-c:a",
        codec,
        "-fflags",
        "+bitexact",
        str(output),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=PRECONDITION.process_environment(),
        timeout=120,
    )
    if completed.returncode or not output.is_file():
        raise ValueError(
            "synthetic format conversion failed: " + completed.stderr.strip()[-500:]
        )


def probe_header(ffprobe: Path, path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,duration_ts,time_base",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        env=PRECONDITION.process_environment(),
        timeout=120,
    )
    if completed.returncode:
        raise ValueError("synthetic header probe failed")
    streams = json.loads(completed.stdout).get("streams")
    if not isinstance(streams, list) or len(streams) != 1:
        raise ValueError("synthetic fixture stream count differs")
    stream = streams[0]
    sample_rate = int(stream["sample_rate"])
    time_base_numerator, time_base_denominator = map(
        int, stream["time_base"].split("/", 1)
    )
    duration_frames_numerator = (
        int(stream["duration_ts"]) * time_base_numerator * sample_rate
    )
    if duration_frames_numerator % time_base_denominator:
        raise ValueError("synthetic duration does not resolve to frames")
    return {
        "codec_name": stream["codec_name"],
        "sample_rate_hz": sample_rate,
        "channel_count": int(stream["channels"]),
        "frame_count": duration_frames_numerator // time_base_denominator,
    }


def run_probe(
    plan: dict[str, Any], tool_paths: dict[str, Path], work_root: Path, plan_sha256: str
) -> dict[str, Any]:
    ffmpeg = tool_paths["ffmpeg_8_1_2_1"]
    ffprobe = tool_paths["ffprobe_8_1_2_1"]
    results = []
    with tempfile.TemporaryDirectory(
        prefix="lossytrace-v2-preconditioning-", dir=work_root
    ) as name:
        temporary = Path(name)
        for case in plan["synthetic_cases"]:
            fixture_id = case["fixture_id"]
            s16_path = temporary / f"{fixture_id}-source-s16.wav"
            source_path = temporary / f"{fixture_id}-source.wav"
            write_synthetic_s16_wave(
                s16_path,
                sample_rate_hz=case["native_sample_rate_hz"],
                channel_count=case["native_channel_count"],
                frame_count=case["native_frame_count"],
            )
            if case["source_codec_name"] == "pcm_s16le":
                source_path = s16_path
            else:
                convert_fixture_format(
                    ffmpeg, s16_path, source_path, case["source_codec_name"]
                )
            header = probe_header(ffprobe, source_path)
            if header != {
                "codec_name": case["source_codec_name"],
                "sample_rate_hz": case["native_sample_rate_hz"],
                "channel_count": case["native_channel_count"],
                "frame_count": case["native_frame_count"],
            }:
                raise ValueError(f"synthetic header differs: {fixture_id}")
            outputs = []
            for replay in (1, 2):
                output = temporary / f"{fixture_id}-output-{replay}.wav"
                observation = PRECONDITION.precondition_to_wave(
                    ffmpeg=ffmpeg,
                    input_path=source_path,
                    output_path=output,
                    group_id=f"synthetic-{fixture_id}",
                    member_id=f"synthetic/{fixture_id}.wav",
                    provider_start_frame=case["provider_start_frame"],
                    provider_end_frame_exclusive=case[
                        "provider_end_frame_exclusive"
                    ],
                    native_sample_rate_hz=case["native_sample_rate_hz"],
                    native_channel_count=case["native_channel_count"],
                    channel_treatment_id=case["channel_treatment_id"],
                    target_sample_rate_hz=case["target_sample_rate_hz"],
                )
                outputs.append(observation)
            if outputs[0] != outputs[1]:
                raise ValueError(f"synthetic preconditioning differs: {fixture_id}")
            results.append(
                {
                    "fixture_id": fixture_id,
                    "source_codec_name": case["source_codec_name"],
                    "native_sample_rate_hz": case["native_sample_rate_hz"],
                    "native_channel_count": case["native_channel_count"],
                    "provider_frame_count": (
                        case["provider_end_frame_exclusive"]
                        - case["provider_start_frame"]
                    ),
                    "channel_treatment_id": case["channel_treatment_id"],
                    "target_sample_rate_hz": case["target_sample_rate_hz"],
                    "input_file_sha256": sha256_file(source_path),
                    **outputs[0],
                    "within_run_replays_byte_identical": True,
                }
            )
    result = {
        "schema_version": SCHEMA_VERSION,
        "audit_id": AUDIT_ID,
        "state": "preconditioning_synthetic_run_evidence",
        "plan_sha256": plan_sha256,
        "preconditioning_module_sha256": sha256_file(PRECONDITION_PATH),
        "toolchain_freeze_id": plan["toolchain_freeze_id"],
        "benchmark_source_audio_read": False,
        "benchmark_audio_generated": False,
        "synthetic_audio_generated": True,
        "features_computed": False,
        "scores_opened": False,
        "construction_authorized": False,
        "paths_redacted": True,
        "cases": results,
        "summary": {
            "synthetic_case_count": len(results),
            "within_run_replays_byte_identical": True,
            "source_codec_names": sorted({row["source_codec_name"] for row in results}),
            "native_channel_counts": sorted(
                {row["native_channel_count"] for row in results}
            ),
            "native_sample_rates_hz": sorted(
                {row["native_sample_rate_hz"] for row in results}
            ),
            "target_sample_rates_hz": sorted(
                {row["target_sample_rate_hz"] for row in results}
            ),
            "channel_treatment_ids": sorted(
                {row["channel_treatment_id"] for row in results}
            ),
        },
        "reproducibility": {
            "complete_replays_required": 2,
            "complete_replays_observed": 1,
            "byte_identical": None,
        },
    }
    assert_public_path_free(result)
    return result


def assert_public_path_free(value: Any, key: str | None = None) -> None:
    if key in FORBIDDEN_PUBLIC_KEYS:
        raise ValueError(f"public preconditioning evidence contains private key: {key}")
    if isinstance(value, dict):
        for child_key, child in value.items():
            assert_public_path_free(child, child_key)
    elif isinstance(value, list):
        for child in value:
            assert_public_path_free(child, key)
    elif isinstance(value, str) and (
        value.startswith("/") or "Library/Application Support" in value
    ):
        raise ValueError("public preconditioning evidence contains a private path")


def attest(run_paths: list[Path], plan_path: Path) -> dict[str, Any]:
    if len(run_paths) != 2:
        raise ValueError("attestation requires exactly two complete replays")
    if run_paths[0].read_bytes() != run_paths[1].read_bytes():
        raise ValueError("synthetic preconditioning replays differ")
    result = load_object(run_paths[0])
    if (
        result.get("state") != "preconditioning_synthetic_run_evidence"
        or result.get("plan_sha256") != sha256_file(plan_path)
    ):
        raise ValueError("synthetic preconditioning replay binding differs")
    final = dict(result)
    final["state"] = "preconditioning_synthetic_evidence"
    final["reproducibility"] = {
        "complete_replays_required": 2,
        "complete_replays_observed": 2,
        "run_reports_byte_identical": True,
        "run_report_sha256": sha256_file(run_paths[0]),
        "plan_sha256": sha256_file(plan_path),
    }
    assert_public_path_free(final)
    return final


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    for name in (
        "plan",
        "factor",
        "toolchain",
        "toolchain-result",
        "public-decoder-result",
        "construction-feasibility-result",
        "tool-paths",
        "work-root",
        "output",
    ):
        run.add_argument(f"--{name}", required=True, type=Path)
    attest_parser = subparsers.add_parser("attest")
    attest_parser.add_argument("--plan", required=True, type=Path)
    attest_parser.add_argument("--run", required=True, type=Path, action="append")
    attest_parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "attest":
        result = attest(
            [path.expanduser().resolve() for path in args.run],
            args.plan.expanduser().resolve(),
        )
        write_json_atomic(args.output.expanduser().resolve(), result)
        print("attested two byte-identical synthetic preconditioning replays")
        return 0

    paths = {
        name.replace("_", "-"): getattr(args, name).expanduser().resolve()
        for name in (
            "plan",
            "factor",
            "toolchain",
            "toolchain_result",
            "public_decoder_result",
            "construction_feasibility_result",
            "tool_paths",
            "work_root",
            "output",
        )
    }
    plan = load_object(paths["plan"])
    validate_plan(
        plan,
        paths["factor"],
        paths["toolchain"],
        paths["toolchain-result"],
        paths["public-decoder-result"],
        paths["construction-feasibility-result"],
        paths["tool-paths"],
    )
    paths["work-root"].mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(paths["work-root"]).free < MINIMUM_FREE_RESERVE_BYTES:
        raise ValueError("work volume is below the frozen 15 GiB reserve")
    manifest = load_object(paths["toolchain"])
    private_paths = load_object(paths["tool-paths"])
    tool_paths = bind_tool_paths(manifest, private_paths)
    result = run_probe(plan, tool_paths, paths["work-root"], sha256_file(paths["plan"]))
    write_json_atomic(paths["output"], result)
    print(
        f"replayed {result['summary']['synthetic_case_count']} synthetic "
        "preconditioning cases without benchmark audio or scores"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
