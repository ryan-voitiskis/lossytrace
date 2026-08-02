#!/usr/bin/env python3
"""Audit frozen v2 case-construction feasibility without reading waveform samples."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
AUDIT_ID = "lossytrace-v2-construction-feasibility-20260802-002"
MINIMUM_FREE_RESERVE_BYTES = 15 * 1024**3
MAXIMUM_EXCERPT_SECONDS = 12
ALLOWED_CODECS = {
    "flac",
    "pcm_s16be",
    "pcm_s16le",
    "pcm_s24be",
    "pcm_s24le",
    "pcm_s32be",
    "pcm_s32le",
}
ARCHIVE_RELATIVE_PATHS = {
    "fsdd_audio": "fsdd-v1.0.10/free-spoken-digit-dataset-1.0.10.zip",
    "lombard_audio": "lombardgrid_audio.zip",
    "ravdess_song_audio": "ravdess-1.0.0/Audio_Song_Actors_01-24.zip",
    "ravdess_speech_audio": "ravdess-1.0.0/Audio_Speech_Actors_01-24.zip",
    "rwc_c_audio": "rwc-music-v2-2026/RWC-C.zip",
    "rwc_g_audio": "rwc-music-v2-2026/RWC-G.zip",
    "rwc_j_audio": "rwc-music-v2-2026/RWC-J.zip",
    "rwc_p_audio": "rwc-music-v2-2026/RWC-P.zip",
    "rwc_r_audio": "rwc-music-v2-2026/RWC-R.zip",
    "satp_audio": "satp-1.5/SATP WAV.zip",
    "sonyc_backgrounds_audio": "sonyc-backgrounds-1.0.0/SONYC-Backgrounds.tar.gz",
    "tinysol_audio": "tinysol-6.0/TinySOL.tar.gz",
    "vctk_clean_audio": "vctk-clean-56spk-2017/clean_trainset_56spk_wav.zip",
}
FORBIDDEN_PUBLIC_KEYS = {
    "archive_member",
    "group_id",
    "input_artifact_id",
    "locator",
    "member_id",
    "relative_path",
    "source_group",
}


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


def safe_relative_path(value: str, label: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\0" in value:
        raise ValueError(f"{label} is not a safe relative path")
    return value


def validate_binding(path: Path, expected: Any, label: str) -> None:
    if not isinstance(expected, str) or not path.is_file():
        raise ValueError(f"{label} binding is absent")
    if sha256_file(path) != expected:
        raise ValueError(f"{label} binding differs")


def validate_plan(
    plan: dict[str, Any],
    plan_path: Path,
    source_allocation_path: Path,
    candidate_index_path: Path,
    assignment_path: Path,
    factor_path: Path,
    toolchain_path: Path,
    tool_paths_path: Path,
) -> None:
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("audit_id") != AUDIT_ID
        or plan.get("state") != "construction_feasibility_frozen_before_header_audit"
        or plan.get("audio_generated") is not False
        or plan.get("waveform_content_inspected") is not False
        or plan.get("features_computed") is not False
        or plan.get("scores_opened") is not False
        or plan.get("selection_authorized") is not False
    ):
        raise ValueError("construction-feasibility plan state differs")
    bindings = plan.get("bindings", {})
    for path, key, label in (
        (source_allocation_path, "private_source_allocation_sha256", "source allocation"),
        (candidate_index_path, "private_candidate_index_sha256", "candidate index"),
        (assignment_path, "private_fractional_assignment_sha256", "assignment"),
        (factor_path, "factor_levels_sha256", "factor levels"),
        (toolchain_path, "toolchain_manifest_sha256", "toolchain manifest"),
        (tool_paths_path, "private_tool_paths_sha256", "private tool paths"),
        (Path(__file__).resolve(), "audit_generator_sha256", "audit generator"),
    ):
        validate_binding(path, bindings.get(key), label)
    if plan.get("storage", {}).get("minimum_free_space_reserve_bytes") != (
        MINIMUM_FREE_RESERVE_BYTES
    ):
        raise ValueError("construction-feasibility storage reserve differs")


def tool_path(
    toolchain: dict[str, Any], private_paths: dict[str, Any], tool_id: str
) -> Path:
    public = next(
        (row for row in toolchain.get("tool_bindings", []) if row.get("tool_id") == tool_id),
        None,
    )
    private = private_paths.get("tools", {}).get(tool_id)
    if public is None or not isinstance(private, dict):
        raise ValueError(f"tool binding is absent: {tool_id}")
    path_value = private.get("path")
    if not isinstance(path_value, str):
        raise ValueError(f"private tool path is absent: {tool_id}")
    path = Path(path_value).expanduser().resolve()
    validate_binding(path, public.get("binary_sha256"), f"tool {tool_id}")
    return path


def process_environment() -> dict[str, str]:
    import os

    environment = os.environ.copy()
    environment.update(
        {"LC_ALL": "C", "LANG": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "0"}
    )
    return environment


def probe_audio_header(ffprobe: Path, path: Path) -> dict[str, Any]:
    command = [
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
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=process_environment(),
        timeout=120,
    )
    if completed.returncode:
        raise ValueError(f"ffprobe failed with exit {completed.returncode}")
    value = json.loads(completed.stdout)
    streams = value.get("streams")
    if not isinstance(streams, list) or len(streams) != 1:
        raise ValueError("source does not contain exactly one audio stream")
    stream = streams[0]
    codec = stream.get("codec_name")
    if codec not in ALLOWED_CODECS:
        raise ValueError(f"source codec is not frozen lossless PCM: {codec!r}")
    sample_rate = int(stream["sample_rate"])
    channels = int(stream["channels"])
    duration_ts = int(stream["duration_ts"])
    time_base = Fraction(str(stream["time_base"]))
    frames = Fraction(duration_ts) * time_base * sample_rate
    if frames.denominator != 1 or frames.numerator < 1:
        raise ValueError("source duration does not resolve to an exact frame count")
    return {
        "codec_name": codec,
        "native_sample_rate_hz": sample_rate,
        "native_channel_count": channels,
        "native_frame_count": frames.numerator,
    }


def decimal_frame(value: str, sample_rate: int, rounding: str) -> int:
    mode = ROUND_CEILING if rounding == "ceiling" else ROUND_FLOOR
    return int((Decimal(value) * sample_rate).to_integral_value(rounding=mode))


def provider_window(row: dict[str, Any], header: dict[str, Any]) -> tuple[int, int]:
    start = 0
    end = header["native_frame_count"]
    factors = row.get("factors", {})
    if "audio_start_seconds" in factors or "audio_end_seconds" in factors:
        if not isinstance(factors.get("audio_start_seconds"), str) or not isinstance(
            factors.get("audio_end_seconds"), str
        ):
            raise ValueError("provider window is incomplete")
        start = decimal_frame(
            factors["audio_start_seconds"], header["native_sample_rate_hz"], "ceiling"
        )
        end = decimal_frame(
            factors["audio_end_seconds"], header["native_sample_rate_hz"], "floor"
        )
        end = min(end, header["native_frame_count"])
    if start < 0 or end <= start or end > header["native_frame_count"]:
        raise ValueError("provider window is outside the source")
    return start, end


def excerpt_frame_count(row: dict[str, Any], header: dict[str, Any]) -> int:
    start, end = provider_window(row, header)
    return min(
        end - start,
        MAXIMUM_EXCERPT_SECONDS * header["native_sample_rate_hz"],
    )


def duration_stratum(frame_count: int, sample_rate: int) -> str:
    milliseconds = Fraction(frame_count * 1000, sample_rate)
    if milliseconds < 1000:
        return "lt1"
    if milliseconds < 3000:
        return "ge1_lt3"
    if milliseconds < 6000:
        return "ge3_lt6"
    return "ge6_le12"


def transform_supported(transform_id: str, frame_count: int, sample_rate: int) -> bool:
    if transform_id == "trim-head-250ms":
        return frame_count * 1000 >= sample_rate * 500
    if transform_id == "duration-prefix-3s":
        return frame_count * 1000 >= sample_rate * 3000
    return True


def archive_path(source_root: Path, artifact_id: str) -> Path:
    relative = ARCHIVE_RELATIVE_PATHS.get(artifact_id)
    if relative is None:
        raise ValueError(f"no frozen archive mapping for {artifact_id}")
    return source_root / relative


def extract_archive_member(archive_path_value: Path, member_name: str, output: Path) -> None:
    safe_relative_path(member_name, "archive member")
    if archive_path_value.suffix == ".zip":
        with zipfile.ZipFile(archive_path_value) as archive:
            info = archive.getinfo(member_name)
            if info.is_dir():
                raise ValueError("selected archive member is a directory")
            with archive.open(info) as source, output.open("wb") as target:
                shutil.copyfileobj(source, target)
        return
    if archive_path_value.name.endswith(".tar.gz"):
        with tarfile.open(archive_path_value, "r:gz") as archive:
            info = archive.getmember(member_name)
            source = archive.extractfile(info)
            if source is None or not info.isfile():
                raise ValueError("selected archive member is not a file")
            with source, output.open("wb") as target:
                shutil.copyfileobj(source, target)
        return
    raise ValueError("selected source archive type is unsupported")


def source_path_for(
    row: dict[str, Any],
    v1_root: Path,
    source_root: Path,
    temporary: Path,
) -> Path:
    locator = row.get("locator")
    if not isinstance(locator, dict) or len(locator) != 1:
        raise ValueError("selected source locator differs")
    relative = locator.get("relative_path")
    if isinstance(relative, str):
        path = v1_root / safe_relative_path(relative, "v1 source path")
        if not path.is_file():
            raise ValueError("selected retained-v1 source is absent")
        return path
    member = locator.get("archive_member")
    artifact_id = row.get("input_artifact_id")
    if not isinstance(member, str) or not isinstance(artifact_id, str):
        raise ValueError("selected archive locator differs")
    suffix = Path(member).suffix or ".audio"
    output = temporary / f"source{suffix}"
    extract_archive_member(archive_path(source_root, artifact_id), member, output)
    return output


def verify_source_artifacts(
    allocation: dict[str, Any],
    candidate_index: dict[str, Any],
    v1_root: Path,
    source_root: Path,
    v1_manifest_relative_path: str,
) -> list[dict[str, Any]]:
    artifact_bindings = candidate_index.get("input_artifacts")
    if not isinstance(artifact_bindings, dict):
        raise ValueError("candidate-index artifact bindings are absent")
    selected = allocation.get("selected", [])
    artifact_ids = sorted(
        {
            row["input_artifact_id"]
            for row in selected
            if isinstance(row.get("locator"), dict)
            and "archive_member" in row["locator"]
        }
    )
    verified = []
    for artifact_id in artifact_ids:
        binding = artifact_bindings.get(artifact_id)
        path = archive_path(source_root, artifact_id)
        if not isinstance(binding, dict):
            raise ValueError(f"candidate-index binding is absent: {artifact_id}")
        validate_binding(path, binding.get("sha256"), f"source artifact {artifact_id}")
        if path.stat().st_size != binding.get("bytes"):
            raise ValueError(f"source artifact size differs: {artifact_id}")
        verified.append(
            {
                "input_artifact_id": artifact_id,
                "bytes": path.stat().st_size,
                "sha256": binding["sha256"],
            }
        )
    v1_manifest = v1_root / safe_relative_path(
        v1_manifest_relative_path, "v1 manifest path"
    )
    v1_binding = artifact_bindings.get("consumed_v1_non_holdout_manifest", {})
    validate_binding(
        v1_manifest,
        v1_binding.get("sha256"),
        "consumed-v1 manifest",
    )
    verified.append(
        {
            "input_artifact_id": "consumed_v1_non_holdout_manifest",
            "bytes": v1_manifest.stat().st_size,
            "sha256": v1_binding["sha256"],
        }
    )
    return verified


def audit(
    plan: dict[str, Any],
    plan_sha256: str,
    allocation: dict[str, Any],
    candidate_index: dict[str, Any],
    assignment: dict[str, Any],
    ffprobe: Path,
    v1_root: Path,
    source_root: Path,
    work_root: Path,
) -> dict[str, Any]:
    if (
        allocation.get("state") != "source_allocation_frozen_identity_only"
        or candidate_index.get("state") != "source_candidate_index_identity_only"
        or assignment.get("state")
        != "fractional_assignment_frozen_identity_and_categorical_only"
        or assignment.get("assignment_id")
        != "lossytrace-v2-fractional-assignment-20260802-003"
    ):
        raise ValueError("private input state differs")
    selected = allocation.get("selected")
    groups = assignment.get("groups")
    cells = assignment.get("cells")
    if not all(isinstance(value, list) for value in (selected, groups, cells)):
        raise ValueError("private input collections are absent")
    selected_by_group = {row.get("group_id"): row for row in selected}
    if len(selected_by_group) != len(selected) or set(selected_by_group) != {
        row.get("group_id") for row in groups
    }:
        raise ValueError("source allocation and assignment group identities differ")
    candidates = candidate_index.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("private candidate rows are absent")
    candidate_by_identity = {
        (row.get("group_id"), row.get("member_id")): row for row in candidates
    }
    for row in selected:
        if candidate_by_identity.get((row.get("group_id"), row.get("member_id"))) != row:
            raise ValueError("selected source differs from the bound candidate index")
    cells_by_group: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for cell in cells:
        cells_by_group[cell["group_id"]].append(cell)

    work_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for group_id in sorted(selected_by_group):
        source_row = selected_by_group[group_id]
        with tempfile.TemporaryDirectory(prefix="lossytrace-v2-feasibility-", dir=work_root) as name:
            source_path = source_path_for(
                source_row, v1_root, source_root, Path(name)
            )
            header = probe_audio_header(ffprobe, source_path)
        if header["native_channel_count"] not in (1, 2):
            channel_supported = False
        else:
            channel_supported = True
        frames = excerpt_frame_count(source_row, header)
        transforms = sorted(
            {
                cell["transform_id"]
                for cell in cells_by_group[group_id]
                if cell["transform_id"] != "identity"
            }
        )
        unsupported = [
            transform_id
            for transform_id in transforms
            if not transform_supported(
                transform_id, frames, header["native_sample_rate_hz"]
            )
        ]
        rows.append(
            {
                "group_id": group_id,
                "evidence_partition": source_row["evidence_partition"],
                "source_collection_id": source_row["source_collection_id"],
                "source_domain": source_row["source_domain"],
                "provenance_tier": source_row["provenance_tier"],
                "input_artifact_id": source_row["input_artifact_id"],
                "member_id": source_row["member_id"],
                "locator": source_row["locator"],
                **header,
                "provider_window_frame_count": provider_window(source_row, header)[1]
                - provider_window(source_row, header)[0],
                "excerpt_frame_count": frames,
                "duration_support_stratum": duration_stratum(
                    frames, header["native_sample_rate_hz"]
                ),
                "native_channel_supported": channel_supported,
                "assigned_nonidentity_transform_ids": transforms,
                "unsupported_transform_ids": unsupported,
            }
        )
    unsupported_group_count = sum(
        bool(row["unsupported_transform_ids"]) or not row["native_channel_supported"]
        for row in rows
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "audit_id": AUDIT_ID,
        "state": "construction_feasibility_private_header_evidence",
        "plan_sha256": plan_sha256,
        "audio_generated": False,
        "waveform_content_inspected": False,
        "headers_inspected": True,
        "duration_inspected": True,
        "features_computed": False,
        "scores_opened": False,
        "selection_authorized": False,
        "group_count": len(rows),
        "construction_authorized": unsupported_group_count == 0,
        "groups": rows,
    }


def count_rows(
    counter: collections.Counter[tuple[Any, ...]], fields: list[str]
) -> list[dict[str, Any]]:
    return [
        {**dict(zip(fields, key, strict=True)), "count": count}
        for key, count in sorted(
            counter.items(), key=lambda item: tuple(str(value) for value in item[0])
        )
    ]


def public_aggregate(
    private: dict[str, Any], private_sha256: str, artifacts: list[dict[str, Any]]
) -> dict[str, Any]:
    rows = private["groups"]
    strata = collections.Counter(
        (
            row["evidence_partition"],
            row["source_domain"],
            row["duration_support_stratum"],
        )
        for row in rows
    )
    native_formats = collections.Counter(
        (
            row["evidence_partition"],
            row["codec_name"],
            row["native_sample_rate_hz"],
            row["native_channel_count"],
        )
        for row in rows
    )
    unsupported = collections.Counter(
        (
            row["evidence_partition"],
            row["source_domain"],
            transform_id,
        )
        for row in rows
        for transform_id in row["unsupported_transform_ids"]
    )
    channel_failures = collections.Counter(
        (row["evidence_partition"], row["source_domain"])
        for row in rows
        if not row["native_channel_supported"]
    )
    aggregate = {
        "schema_version": SCHEMA_VERSION,
        "audit_id": AUDIT_ID,
        "state": "construction_feasibility_path_free_run_evidence",
        "plan_sha256": private["plan_sha256"],
        "private_audit_sha256": private_sha256,
        "audio_generated": False,
        "waveform_content_inspected": False,
        "headers_inspected": True,
        "duration_inspected": True,
        "features_computed": False,
        "scores_opened": False,
        "selection_authorized": False,
        "paths_redacted": True,
        "private_ids_included": False,
        "source_artifacts": [
            {"bytes": row["bytes"], "sha256": row["sha256"]}
            for row in artifacts
        ],
        "duration_strata": count_rows(
            strata,
            ["evidence_partition", "source_domain", "duration_support_stratum"],
        ),
        "native_format_counts": count_rows(
            native_formats,
            [
                "evidence_partition",
                "codec_name",
                "native_sample_rate_hz",
                "native_channel_count",
            ],
        ),
        "unsupported_transform_counts": count_rows(
            unsupported,
            ["evidence_partition", "source_domain", "transform_id"],
        ),
        "unsupported_channel_counts": count_rows(
            channel_failures, ["evidence_partition", "source_domain"]
        ),
        "summary": {
            "group_count": len(rows),
            "unsupported_transform_group_count": len(
                {row["group_id"] for row in rows if row["unsupported_transform_ids"]}
            ),
            "unsupported_channel_group_count": sum(
                not row["native_channel_supported"] for row in rows
            ),
            "construction_authorized": private["construction_authorized"],
        },
        "reproducibility": {
            "complete_replays_required": 2,
            "complete_replays_observed": 1,
            "byte_identical": None,
        },
    }
    assert_public_path_free(aggregate)
    return aggregate


def assert_public_path_free(value: Any, key: str | None = None) -> None:
    if key in FORBIDDEN_PUBLIC_KEYS:
        raise ValueError(f"public aggregate contains private key: {key}")
    if isinstance(value, dict):
        for child_key, child in value.items():
            assert_public_path_free(child, child_key)
    elif isinstance(value, list):
        for child in value:
            assert_public_path_free(child, key)
    elif isinstance(value, str) and (
        value.startswith("/") or "Library/Application Support" in value
    ):
        raise ValueError("public aggregate contains a private path")


def attest(
    private_paths: list[Path], aggregate_paths: list[Path], plan_path: Path
) -> dict[str, Any]:
    if len(private_paths) != 2 or len(aggregate_paths) != 2:
        raise ValueError("attestation requires exactly two complete replays")
    if private_paths[0].read_bytes() != private_paths[1].read_bytes():
        raise ValueError("private feasibility audits differ")
    if aggregate_paths[0].read_bytes() != aggregate_paths[1].read_bytes():
        raise ValueError("path-free feasibility aggregates differ")
    aggregate = load_object(aggregate_paths[0])
    if (
        aggregate.get("state")
        != "construction_feasibility_path_free_run_evidence"
        or aggregate.get("private_audit_sha256") != sha256_file(private_paths[0])
        or aggregate.get("plan_sha256") != sha256_file(plan_path)
    ):
        raise ValueError("feasibility aggregate binding differs")
    final = dict(aggregate)
    final["state"] = "construction_feasibility_path_free_evidence"
    final["reproducibility"] = {
        "complete_replays_required": 2,
        "complete_replays_observed": 2,
        "private_audits_byte_identical": True,
        "run_aggregates_byte_identical": True,
        "private_audit_sha256": sha256_file(private_paths[0]),
        "run_aggregate_sha256": sha256_file(aggregate_paths[0]),
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
        "source-allocation",
        "candidate-index",
        "assignment",
        "factor",
        "toolchain",
        "tool-paths",
        "v1-root",
        "source-root",
        "work-root",
        "output-private",
        "output-run-aggregate",
    ):
        run.add_argument(f"--{name}", required=True, type=Path)
    attest_parser = subparsers.add_parser("attest")
    attest_parser.add_argument("--plan", required=True, type=Path)
    attest_parser.add_argument("--private", required=True, type=Path, action="append")
    attest_parser.add_argument(
        "--run-aggregate", required=True, type=Path, action="append"
    )
    attest_parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "attest":
        result = attest(
            [path.expanduser().resolve() for path in args.private],
            [path.expanduser().resolve() for path in args.run_aggregate],
            args.plan.expanduser().resolve(),
        )
        write_json_atomic(args.output.expanduser().resolve(), result)
        print("attested two byte-identical construction-feasibility audits")
        return 0

    paths = {
        name.replace("_", "-"): getattr(args, name).expanduser().resolve()
        for name in (
            "plan",
            "source_allocation",
            "candidate_index",
            "assignment",
            "factor",
            "toolchain",
            "tool_paths",
            "v1_root",
            "source_root",
            "work_root",
            "output_private",
            "output_run_aggregate",
        )
    }
    plan = load_object(paths["plan"])
    validate_plan(
        plan,
        paths["plan"],
        paths["source-allocation"],
        paths["candidate-index"],
        paths["assignment"],
        paths["factor"],
        paths["toolchain"],
        paths["tool-paths"],
    )
    paths["work-root"].mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(paths["work-root"]).free < MINIMUM_FREE_RESERVE_BYTES:
        raise ValueError("work volume is below the frozen 15 GiB reserve")
    allocation = load_object(paths["source-allocation"])
    candidate_index = load_object(paths["candidate-index"])
    assignment = load_object(paths["assignment"])
    if (
        allocation.get("candidate_index_sha256")
        != sha256_file(paths["candidate-index"])
        or assignment.get("source_allocation_sha256")
        != sha256_file(paths["source-allocation"])
    ):
        raise ValueError("private source or assignment cross-binding differs")
    toolchain = load_object(paths["toolchain"])
    private_tool_paths = load_object(paths["tool-paths"])
    ffprobe = tool_path(
        toolchain, private_tool_paths, plan["tools"]["ffprobe_tool_id"]
    )
    artifacts = verify_source_artifacts(
        allocation,
        candidate_index,
        paths["v1-root"],
        paths["source-root"],
        plan["sources"]["v1_manifest_relative_path"],
    )
    private = audit(
        plan,
        sha256_file(paths["plan"]),
        allocation,
        candidate_index,
        assignment,
        ffprobe,
        paths["v1-root"],
        paths["source-root"],
        paths["work-root"],
    )
    private_output = paths["output-private"]
    write_json_atomic(private_output, private)
    aggregate = public_aggregate(private, sha256_file(private_output), artifacts)
    write_json_atomic(paths["output-run-aggregate"], aggregate)
    summary = aggregate["summary"]
    print(
        f"audited {summary['group_count']} source headers; "
        f"unsupported transform groups={summary['unsupported_transform_group_count']}; "
        f"unsupported channel groups={summary['unsupported_channel_group_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
