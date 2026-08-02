#!/usr/bin/env python3
"""Bind and probe the public LossyTrace decoder on exact lossless wrappers."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts" / "probe-audio-integrity-v2-toolchains.py"
BASE_SPEC = importlib.util.spec_from_file_location("v2_public_decoder_base", BASE_PATH)
if BASE_SPEC is None or BASE_SPEC.loader is None:
    raise RuntimeError(f"cannot import {BASE_PATH}")
BASE = importlib.util.module_from_spec(BASE_SPEC)
BASE_SPEC.loader.exec_module(BASE)

PLAN_ID = "lossytrace-v2-public-decoder-equivalence-20260802-001"
BINDING_ID = "lossytrace-v2-public-decoder-binary-20260802-001"
PROBE_ID = "lossytrace-v2-public-decoder-equivalence-probe-20260802-001"
EXPECTED_TOOLCHAIN_RESULT_SHA256 = (
    "29ddfe00bb419aedcbdee8de530785f5981de279f2bd190f4a337ebbe8c3cc23"
)
MINIMUM_FREE_RESERVE_BYTES = 15 * 1024**3
WRAPPER_EXTENSIONS = {"flac16": ".flac", "wav16": ".wav", "aiff16": ".aiff"}


def load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def process_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "CARGO_INCREMENTAL": "0",
            "LANG": "C",
            "LC_ALL": "C",
            "SOURCE_DATE_EPOCH": "0",
            "TZ": "UTC",
        }
    )
    return environment


def run(command: list[str], timeout_seconds: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=process_environment(),
        timeout=timeout_seconds,
    )


def require_success(completed: subprocess.CompletedProcess[str], label: str) -> str:
    if completed.returncode:
        raise ValueError(
            f"{label} failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()[-500:]}"
        )
    return completed.stdout.strip()


def validate_plan(plan: dict[str, Any], toolchain_result_path: Path) -> None:
    if (
        plan.get("schema_version") != 1
        or plan.get("plan_id") != PLAN_ID
        or plan.get("state")
        != "public_decoder_build_and_equivalence_frozen_before_execution"
        or plan.get("binary_binding_frozen") is not False
        or plan.get("benchmark_audio_generated") is not False
        or plan.get("source_groups_assigned") is not False
        or plan.get("scores_opened") is not False
        or plan.get("selection_authorized") is not False
        or plan.get("public_state", {}).get("public_verdict_enabled") is not False
    ):
        raise ValueError("public decoder plan state differs")
    if (
        plan.get("toolchain_result_binding", {}).get("sha256")
        != EXPECTED_TOOLCHAIN_RESULT_SHA256
        or sha256_file(toolchain_result_path) != EXPECTED_TOOLCHAIN_RESULT_SHA256
    ):
        raise ValueError("toolchain result binding differs")
    source = plan.get("rust_source_binding", {})
    expected_paths = {
        "cargo_toml_sha256": ROOT / "Cargo.toml",
        "cargo_lock_sha256": ROOT / "Cargo.lock",
        "audio_rs_sha256": ROOT / "src/audio.rs",
        "lib_rs_sha256": ROOT / "src/lib.rs",
        "main_rs_sha256": ROOT / "src/main.rs",
        "compression_trace_rs_sha256": ROOT / "src/compression_trace.rs",
        "stft_rs_sha256": ROOT / "src/stft.rs",
    }
    for field, path in expected_paths.items():
        if source.get(field) != sha256_file(path):
            raise ValueError(f"Rust source binding differs: {field}")
    source_tree = require_success(
        run(
            [
                "/usr/bin/git",
                "-C",
                str(ROOT),
                "rev-parse",
                f"{source.get('checkpoint_commit')}:src",
            ]
        ),
        "Rust source tree binding",
    )
    if source_tree != source.get("src_tree_sha1"):
        raise ValueError("Rust source tree hash differs")
    build = plan.get("build_binding", {})
    if (
        require_success(run(["rustc", "--version"]), "rustc version")
        != build.get("rustc")
        or require_success(run(["cargo", "--version"]), "cargo version")
        != build.get("cargo")
    ):
        raise ValueError("Rust build tool version differs")
    if plan.get("probe_contract", {}).get("expected_wrapper_path_count") != 12:
        raise ValueError("wrapper path count differs")


def linked_libraries(binary: Path) -> list[str]:
    completed = run(["/usr/bin/otool", "-L", str(binary)])
    output = require_success(completed, "otool")
    rows = []
    for line in output.splitlines()[1:]:
        value = line.strip()
        if value:
            rows.append(value)
    return rows


def bind_binary(plan: dict[str, Any], binary: Path, toolchain_result_path: Path) -> dict[str, Any]:
    validate_plan(plan, toolchain_result_path)
    binary = binary.expanduser().resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError("public decoder binary is missing or not executable")
    version = require_success(run([str(binary), "--version"]), "lossytrace --version")
    return {
        "schema_version": 1,
        "binding_id": BINDING_ID,
        "state": "public_decoder_binary_frozen_before_equivalence_probe",
        "plan_binding": {
            "plan_id": plan["plan_id"],
            "sha256": None,
        },
        "rust_source_binding": plan["rust_source_binding"],
        "build_binding": plan["build_binding"],
        "binary": {
            "implementation": "LossyTrace public CLI using Symphonia 0.5",
            "version": version,
            "sha256": sha256_file(binary),
            "byte_count": binary.stat().st_size,
            "linked_libraries": linked_libraries(binary),
        },
        "probe_script_sha256": sha256_file(Path(__file__).resolve()),
        "base_probe_script_sha256": sha256_file(BASE_PATH),
        "benchmark_audio_generated": False,
        "source_groups_assigned": False,
        "scores_opened": False,
        "selection_authorized": False,
        "public_verdict_enabled": False,
        "equivalence_probe_executed": False,
        "authorized_next_step": (
            "Commit this path-free binding, then run two complete synthetic "
            "wrapper-equivalence replays without changing the binary or scripts."
        ),
    }


def fill_plan_hash(binding: dict[str, Any], plan_path: Path) -> dict[str, Any]:
    binding["plan_binding"]["sha256"] = sha256_file(plan_path)
    return binding


def check_free_space(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(ROOT).free < MINIMUM_FREE_RESERVE_BYTES:
        raise ValueError("local benchmark volume is below the 15 GiB reserve")


def public_command(
    command: list[str], ffmpeg: Path, input_path: Path, output_path: Path
) -> list[str]:
    result = []
    for part in command:
        if part == "<TOOL:ffmpeg_8_1_2_1>":
            result.append(str(ffmpeg))
        elif part == "<INPUT>":
            result.append(str(input_path))
        elif part == "<OUTPUT>":
            result.append(str(output_path))
        else:
            result.append(part)
    return result


def run_ffmpeg(
    command: list[str], ffmpeg: Path, input_path: Path, output_path: Path
) -> None:
    require_success(
        run(public_command(command, ffmpeg, input_path, output_path)),
        "FFmpeg wrapper command",
    )
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise ValueError("FFmpeg wrapper command produced no output")


def report_projection(report: dict[str, Any]) -> dict[str, Any]:
    source = report.get("source_facts", {})
    return {
        "schema_version": report.get("schema_version"),
        "state": report.get("state"),
        "public_verdict_enabled": report.get("public_verdict_enabled"),
        "analyzed_sample_count": report.get("analyzed_sample_count"),
        "analyzed_duration_seconds": report.get("analyzed_duration_seconds"),
        "truncated_by_limit": report.get("truncated_by_limit"),
        "source_facts": {
            "sample_rate_hz": source.get("sample_rate_hz"),
            "channel_count": source.get("channel_count"),
            "declared_bits_per_sample": source.get("declared_bits_per_sample"),
        },
        "compression_trace": report.get("compression_trace"),
    }


def run_public_decoder(binary: Path, wrapper: Path) -> tuple[dict[str, Any], str]:
    outputs = []
    raw_outputs = []
    for _ in (1, 2):
        raw = require_success(
            run([str(binary), "analyze", str(wrapper), "--max-seconds", "0"]),
            "public decoder",
        )
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("public decoder output is not an object")
        raw_outputs.append(raw)
        outputs.append(value)
    if raw_outputs[0] != raw_outputs[1]:
        raise ValueError("public decoder output is not deterministic")
    if outputs[0].get("public_verdict_enabled") is not False:
        raise ValueError("public decoder unexpectedly enabled a verdict")
    projection = report_projection(outputs[0])
    return projection, hashlib.sha256(raw_outputs[0].encode()).hexdigest()


def run_probe(
    plan: dict[str, Any],
    binding: dict[str, Any],
    manifest: dict[str, Any],
    binary: Path,
    ffmpeg: Path,
    work_root: Path,
    plan_path: Path,
    toolchain_result_path: Path,
) -> dict[str, Any]:
    validate_plan(plan, toolchain_result_path)
    if (
        binding.get("binding_id") != BINDING_ID
        or binding.get("state")
        != "public_decoder_binary_frozen_before_equivalence_probe"
        or binding.get("plan_binding", {}).get("sha256") != sha256_file(plan_path)
        or binding.get("probe_script_sha256") != sha256_file(Path(__file__).resolve())
        or binding.get("base_probe_script_sha256") != sha256_file(BASE_PATH)
        or binding.get("equivalence_probe_executed") is not False
    ):
        raise ValueError("public decoder binary binding differs")
    binary = binary.expanduser().resolve()
    ffmpeg = ffmpeg.expanduser().resolve()
    if sha256_file(binary) != binding.get("binary", {}).get("sha256"):
        raise ValueError("public decoder binary hash differs")
    ffmpeg_binding = next(
        row for row in manifest["tool_bindings"] if row["tool_id"] == "ffmpeg_8_1_2_1"
    )
    if sha256_file(ffmpeg) != ffmpeg_binding["binary_sha256"]:
        raise ValueError("FFmpeg binary hash differs")
    check_free_space(work_root)

    wrapper_bindings = {row["wrapper_id"]: row for row in manifest["wrapper_bindings"]}
    analysis_command = manifest["analysis_decoder_binding"]["command"]
    wrapper_rows = []
    triplet_rows = []
    with tempfile.TemporaryDirectory(prefix="lossytrace-v2-public-decoder-", dir=work_root) as name:
        work = Path(name)
        for sample_rate in (44_100, 48_000):
            for channel_id, channels in (("mono", 1), ("stereo", 2)):
                input_id = f"synthetic-{sample_rate}-{channel_id}"
                source = work / f"{input_id}.wav"
                BASE.generate_probe_wave(
                    source,
                    sample_rate_hz=sample_rate,
                    frame_count=sample_rate * 3,
                    channel_count=channels,
                )
                source_pcm_sha256 = BASE.wave_pcm_info(source)["pcm_sha256"]
                projections = []
                for wrapper_id in ("flac16", "wav16", "aiff16"):
                    wrapper = work / f"{input_id}-{wrapper_id}{WRAPPER_EXTENSIONS[wrapper_id]}"
                    raw = work / f"{input_id}-{wrapper_id}.s16le"
                    run_ffmpeg(
                        wrapper_bindings[wrapper_id]["command"],
                        ffmpeg,
                        source,
                        wrapper,
                    )
                    run_ffmpeg(analysis_command, ffmpeg, wrapper, raw)
                    if sha256_file(raw) != source_pcm_sha256:
                        raise ValueError(f"analysis decoder PCM differs for {input_id}/{wrapper_id}")
                    projection, public_output_sha256 = run_public_decoder(binary, wrapper)
                    projections.append(projection)
                    wrapper_rows.append(
                        {
                            "input_id": input_id,
                            "wrapper_id": wrapper_id,
                            "wrapper_sha256": sha256_file(wrapper),
                            "analysis_decoded_pcm_sha256": sha256_file(raw),
                            "analysis_decoded_pcm_exactly_matches_input": True,
                            "public_report_deterministic_across_two_runs": True,
                            "public_report_sha256": public_output_sha256,
                            "public_projection_sha256": hashlib.sha256(
                                json.dumps(
                                    projection,
                                    sort_keys=True,
                                    separators=(",", ":"),
                                    ensure_ascii=True,
                                ).encode()
                            ).hexdigest(),
                        }
                    )
                if not all(projection == projections[0] for projection in projections[1:]):
                    raise ValueError(f"public decoder wrapper projection differs for {input_id}")
                triplet_rows.append(
                    {
                        "input_id": input_id,
                        "wrapper_count": 3,
                        "exact_public_projection_equivalent": True,
                    }
                )

    report = {
        "schema_version": 1,
        "probe_id": PROBE_ID,
        "state": "public_decoder_synthetic_wrapper_equivalence_evidence_only",
        "plan_binding": {"plan_id": PLAN_ID, "sha256": sha256_file(plan_path)},
        "binary_binding": {
            "binding_id": binding["binding_id"],
            "sha256": binding["binary"]["sha256"],
        },
        "toolchain_manifest_binding": {
            "toolchain_freeze_id": manifest["toolchain_freeze_id"],
        },
        "benchmark_audio_generated": False,
        "source_groups_assigned": False,
        "scores_opened": False,
        "selection_authorized": False,
        "public_verdict_enabled": False,
        "paths_redacted": True,
        "wrapper_paths": wrapper_rows,
        "triplets": triplet_rows,
        "summary": {
            "wrapper_path_count": len(wrapper_rows),
            "triplet_count": len(triplet_rows),
            "all_analysis_decoded_pcm_exact": True,
            "all_public_reports_deterministic": True,
            "all_public_wrapper_projections_exact": True,
        },
        "authorized_next_step": (
            "After two byte-identical reports and a committed result, freeze the "
            "fractional source-to-cell assignment without opening scores."
        ),
    }
    serialized = json.dumps(report, sort_keys=True)
    sensitive = [str(binary), str(ffmpeg), str(work_root), "/Users/", "\\Users\\"]
    if any(value and value in serialized for value in sensitive):
        raise ValueError("public decoder report contains a private path")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    bind = subparsers.add_parser("bind")
    bind.add_argument("--plan", required=True, type=Path)
    bind.add_argument("--toolchain-result", required=True, type=Path)
    bind.add_argument("--binary", required=True, type=Path)
    bind.add_argument("--output", required=True, type=Path)
    probe = subparsers.add_parser("probe")
    probe.add_argument("--plan", required=True, type=Path)
    probe.add_argument("--binding", required=True, type=Path)
    probe.add_argument("--toolchain-manifest", required=True, type=Path)
    probe.add_argument("--toolchain-result", required=True, type=Path)
    probe.add_argument("--binary", required=True, type=Path)
    probe.add_argument("--ffmpeg", required=True, type=Path)
    probe.add_argument("--work-root", required=True, type=Path)
    probe.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    plan_path = args.plan.expanduser().resolve()
    plan = load_object(plan_path)
    toolchain_result_path = args.toolchain_result.expanduser().resolve()
    if args.command == "bind":
        binding = fill_plan_hash(
            bind_binary(plan, args.binary, toolchain_result_path), plan_path
        )
        write_json_atomic(args.output.expanduser().resolve(), binding)
        print(f"bound public decoder binary {binding['binary']['sha256']}")
        return 0
    report = run_probe(
        plan,
        load_object(args.binding.expanduser().resolve()),
        load_object(args.toolchain_manifest.expanduser().resolve()),
        args.binary,
        args.ffmpeg,
        args.work_root.expanduser().resolve(),
        plan_path,
        toolchain_result_path,
    )
    write_json_atomic(args.output.expanduser().resolve(), report)
    print(
        f"verified {report['summary']['wrapper_path_count']} wrapper paths and "
        f"{report['summary']['triplet_count']} public decoder triplets"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
