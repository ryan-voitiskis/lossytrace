#!/usr/bin/env python3
"""Validate and size the frozen v2 construction recipe without reading audio."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import shutil
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
PREFLIGHT_ID = "lossytrace-v2-construction-preflight-20260802-001"
EXPECTED_GROUP_COUNT = 793
EXPECTED_CELL_COUNT = 12885
EXPECTED_POSITIVE_COUNT = 6356
EXPECTED_NEGATIVE_COUNT = 6529
EXPECTED_EXTERNAL_RESERVE_COUNT = 100
MINIMUM_FREE_RESERVE_BYTES = 15 * 1024**3
CODEC_DECODE_PADDING_UPPER_FRAMES = 4096
RESAMPLE_TAIL_UPPER_FRAMES = 128
PER_ARTIFACT_CONTAINER_ALLOWANCE_BYTES = 1024**2
FLAC_WORST_CASE_NUMERATOR = 110
FLAC_WORST_CASE_DENOMINATOR = 100
WORKSPACE_ALLOWANCE_BYTES = 2 * 1024**3
PARTITIONS = ("mechanism_development", "encoder_transfer", "external_transfer")
WRAPPER_EXTENSIONS = {"flac16": ".flac", "wav16": ".wav", "aiff16": ".aiff"}
FORBIDDEN_PUBLIC_KEYS = {
    "assignment_id",
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
        temporary = Path(output.name)
    temporary.replace(path)


def validate_binding(path: Path, expected: Any, label: str) -> None:
    if not isinstance(expected, str) or not path.is_file():
        raise ValueError(f"{label} binding is absent")
    if sha256_file(path) != expected:
        raise ValueError(f"{label} binding differs")


def validate_plan(plan: dict[str, Any], paths: dict[str, Path]) -> None:
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("preflight_id") != PREFLIGHT_ID
        or plan.get("state") != "construction_preflight_frozen_before_private_replay"
        or plan.get("benchmark_source_audio_read") is not False
        or plan.get("benchmark_audio_generated") is not False
        or plan.get("features_computed") is not False
        or plan.get("scores_opened") is not False
        or plan.get("construction_authorized") is not False
    ):
        raise ValueError("construction preflight plan state differs")
    bindings = plan.get("bindings", {})
    for path_key, binding_key, label in (
        ("generator", "generator_sha256", "preflight generator"),
        ("source-allocation", "private_source_allocation_sha256", "source allocation"),
        ("candidate-index", "private_candidate_index_sha256", "candidate index"),
        ("assignment", "private_fractional_assignment_sha256", "assignment"),
        (
            "assignment-result",
            "public_fractional_assignment_result_sha256",
            "assignment result",
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
        (
            "preconditioning-result",
            "preconditioning_result_sha256",
            "preconditioning result",
        ),
        ("factor", "factor_levels_sha256", "factor levels"),
        ("toolchain", "toolchain_manifest_sha256", "toolchain manifest"),
        ("toolchain-result", "toolchain_result_sha256", "toolchain result"),
        (
            "public-decoder-result",
            "public_decoder_result_sha256",
            "public decoder result",
        ),
        ("tool-paths", "private_tool_paths_sha256", "private tool paths"),
    ):
        validate_binding(paths[path_key], bindings.get(binding_key), label)
    storage = plan.get("storage", {})
    if (
        storage.get("minimum_free_space_reserve_bytes")
        != MINIMUM_FREE_RESERVE_BYTES
        or storage.get("workspace_allowance_bytes") != WORKSPACE_ALLOWANCE_BYTES
        or storage.get("maximum_parallel_workers") != 1
    ):
        raise ValueError("construction preflight storage rule differs")


def ceil_ratio(numerator: int, denominator: int) -> int:
    if numerator < 0 or denominator < 1:
        raise ValueError("ceiling ratio differs")
    return (numerator + denominator - 1) // denominator


def preconditioned_frame_upper(
    excerpt_native_frames: int, native_sample_rate_hz: int, target_sample_rate_hz: int
) -> int:
    if (
        excerpt_native_frames < 1
        or native_sample_rate_hz < 1
        or target_sample_rate_hz not in (44100, 48000)
    ):
        raise ValueError("preconditioned frame bound differs")
    if native_sample_rate_hz == target_sample_rate_hz:
        return excerpt_native_frames
    return (
        ceil_ratio(excerpt_native_frames * target_sample_rate_hz, native_sample_rate_hz)
        + RESAMPLE_TAIL_UPPER_FRAMES
    )


def transformed_shape_upper(
    *,
    frame_count: int,
    channel_count: int,
    sample_rate_hz: int,
    transform_id: str,
) -> tuple[int, int]:
    if frame_count < 1 or channel_count not in (1, 2):
        raise ValueError("transformed shape bound differs")
    if transform_id == "trim-head-250ms":
        frame_count = max(1, frame_count - sample_rate_hz * 250 // 1000)
    elif transform_id == "prepend-digital-silence-500ms":
        frame_count += sample_rate_hz * 500 // 1000
    elif transform_id == "duration-prefix-3s":
        frame_count = min(frame_count, sample_rate_hz * 3)
    elif transform_id == "resample-roundtrip-32k":
        frame_count += RESAMPLE_TAIL_UPPER_FRAMES * 2
    elif transform_id == "alternate-channel-topology":
        channel_count = 2 if channel_count == 1 else 1
    return frame_count, channel_count


def artifact_byte_upper(
    *, frame_count: int, channel_count: int, wrapper_id: str
) -> int:
    pcm_bytes = frame_count * channel_count * 2
    if wrapper_id == "flac16":
        pcm_bytes = ceil_ratio(
            pcm_bytes * FLAC_WORST_CASE_NUMERATOR, FLAC_WORST_CASE_DENOMINATOR
        )
    elif wrapper_id not in ("wav16", "aiff16"):
        raise ValueError("wrapper byte bound differs")
    return pcm_bytes + PER_ARTIFACT_CONTAINER_ALLOWANCE_BYTES


def validate_private_inputs(
    allocation: dict[str, Any],
    candidate_index: dict[str, Any],
    assignment: dict[str, Any],
    assignment_result: dict[str, Any],
    feasibility: dict[str, Any],
    feasibility_result: dict[str, Any],
    preconditioning_result: dict[str, Any],
    factor: dict[str, Any],
    toolchain: dict[str, Any],
    paths: dict[str, Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if (
        allocation.get("state") != "source_allocation_frozen_identity_only"
        or candidate_index.get("state") != "source_candidate_index_identity_only"
        or assignment.get("state")
        != (
            "fractional_assignment_frozen_identity_categorical_and_"
            "transform_feasibility_only"
        )
        or assignment.get("assignment_id")
        != "lossytrace-v2-fractional-assignment-20260802-004"
        or assignment_result.get("state") != "fractional_assignment_path_free_evidence"
        or feasibility.get("state")
        != "construction_feasibility_private_header_evidence"
        or feasibility.get("construction_authorized") is not True
        or feasibility_result.get("state")
        != "construction_feasibility_path_free_evidence"
        or feasibility_result.get("summary", {}).get("construction_authorized")
        is not True
        or preconditioning_result.get("state")
        != "preconditioning_synthetic_evidence"
        or preconditioning_result.get("summary", {}).get(
            "within_run_replays_byte_identical"
        )
        is not True
        or factor.get("factor_freeze_id")
        != "lossytrace-v2-factor-levels-20260802-002"
        or toolchain.get("toolchain_freeze_id")
        != "lossytrace-v2-toolchain-bindings-20260802-004"
        or assignment.get("audio_generated") is not False
        or assignment.get("scores_opened") is not False
        or feasibility.get("audio_generated") is not False
        or feasibility.get("waveform_content_inspected") is not False
        or feasibility.get("features_computed") is not False
        or feasibility.get("scores_opened") is not False
    ):
        raise ValueError("private construction input state differs")
    if (
        allocation.get("candidate_index_sha256") != sha256_file(paths["candidate-index"])
        or assignment.get("source_allocation_sha256")
        != sha256_file(paths["source-allocation"])
        or assignment_result.get("private_assignment_sha256")
        != sha256_file(paths["assignment"])
        or feasibility_result.get("private_audit_sha256")
        != sha256_file(paths["feasibility-audit"])
    ):
        raise ValueError("private construction cross-binding differs")
    selected = allocation.get("selected")
    candidates = candidate_index.get("candidates")
    groups = assignment.get("groups")
    cells = assignment.get("cells")
    feasibility_groups = feasibility.get("groups")
    if not all(
        isinstance(value, list)
        for value in (selected, candidates, groups, cells, feasibility_groups)
    ):
        raise ValueError("private construction collections are absent")
    if (
        len(selected) != EXPECTED_GROUP_COUNT
        or len(groups) != EXPECTED_GROUP_COUNT
        or len(feasibility_groups) != EXPECTED_GROUP_COUNT
        or len(cells) != EXPECTED_CELL_COUNT
    ):
        raise ValueError("private construction collection count differs")
    selected_ids = {row.get("group_id") for row in selected}
    group_ids = {row.get("group_id") for row in groups}
    feasibility_by_id = {row.get("group_id"): row for row in feasibility_groups}
    if (
        None in selected_ids
        or selected_ids != group_ids
        or selected_ids != set(feasibility_by_id)
        or len(selected_ids) != EXPECTED_GROUP_COUNT
    ):
        raise ValueError("private construction group identity differs")
    reserve = assignment.get("external_positive_reserve")
    if (
        not isinstance(reserve, list)
        or len(reserve) != EXPECTED_EXTERNAL_RESERVE_COUNT
        or len({row.get("group_id") for row in reserve})
        != EXPECTED_EXTERNAL_RESERVE_COUNT
        or any(
            row.get("encoder_selection_deferred") is not True
            or row.get("codec_family") is not None
            or row.get("expanded_setting_id") is not None
            or row.get("history_decoder_id") is not None
            or row.get("scores_opened") is not False
            for row in reserve
        )
    ):
        raise ValueError("private external reserve differs")
    if any(
        row.get("unsupported_transform_ids")
        or row.get("native_channel_supported") is not True
        for row in feasibility_groups
    ):
        raise ValueError("private construction feasibility finding differs")
    return groups, cells, feasibility_by_id


def validate_cell_lineage(
    cells: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    factor: dict[str, Any],
    toolchain: dict[str, Any],
) -> None:
    group_by_id = {row["group_id"]: row for row in groups}
    by_id = {row.get("assignment_id"): row for row in cells}
    if len(by_id) != len(cells) or None in by_id:
        raise ValueError("construction cell identity differs")
    transforms = {row["transform_id"] for row in factor["pcm_transform_levels"]}
    wrappers = {row["wrapper_id"] for row in toolchain["wrapper_bindings"]}
    settings = {
        row["expanded_setting_id"]: row
        for row in toolchain["expanded_encoder_settings"]
    }
    positives = 0
    negatives = 0
    for cell in cells:
        group = group_by_id.get(cell.get("group_id"))
        if (
            group is None
            or cell.get("evidence_partition") != group["evidence_partition"]
            or cell.get("transform_id") not in transforms
            or cell.get("wrapper_id") not in wrappers
            or cell.get("channel_treatment_id") not in ("mono", "stereo")
            or cell.get("target_sample_rate_hz") not in (44100, 48000)
        ):
            raise ValueError("construction cell factor differs")
        if cell.get("expectation") == "controlled_positive":
            positives += 1
            setting = settings.get(cell.get("expanded_setting_id"))
            reference = by_id.get(cell.get("matched_reference_assignment_id"))
            source = by_id.get(cell.get("source_reference_assignment_id"))
            if (
                setting is None
                or setting.get("expected_sample_rate_hz")
                != cell["target_sample_rate_hz"]
                or reference is None
                or reference.get("expectation") != "negative"
                or source is None
                or source.get("expectation") != "negative"
                or source.get("transform_id") != "identity"
            ):
                raise ValueError("construction positive lineage differs")
            for field in (
                "group_id",
                "evidence_partition",
                "channel_treatment_id",
                "target_sample_rate_hz",
                "transform_id",
                "wrapper_id",
            ):
                if reference.get(field) != cell.get(field):
                    raise ValueError(f"construction matched reference differs on {field}")
            for field in (
                "group_id",
                "evidence_partition",
                "channel_treatment_id",
                "target_sample_rate_hz",
            ):
                if source.get(field) != cell.get(field):
                    raise ValueError(f"construction recipe source differs on {field}")
        elif cell.get("expectation") == "negative":
            negatives += 1
            if cell.get("history_class") == "pcm_hard_negative":
                source = by_id.get(cell.get("source_reference_assignment_id"))
                if source is None or source.get("transform_id") != "identity":
                    raise ValueError("construction hard-negative lineage differs")
        else:
            raise ValueError("construction cell expectation differs")
    if positives != EXPECTED_POSITIVE_COUNT or negatives != EXPECTED_NEGATIVE_COUNT:
        raise ValueError("construction expectation count differs")
    if any(
        cell.get("expectation") == "controlled_positive"
        and cell.get("evidence_partition") == "external_transfer"
        for cell in cells
    ):
        raise ValueError("construction includes an external positive before freeze")


def count_rows(
    counter: collections.Counter[tuple[Any, ...]], fields: list[str]
) -> list[dict[str, Any]]:
    return [
        {**dict(zip(fields, key, strict=True)), "count": count}
        for key, count in sorted(
            counter.items(), key=lambda item: tuple(str(value) for value in item[0])
        )
    ]


def build_preflight(
    plan: dict[str, Any],
    groups: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    feasibility_by_id: dict[str, dict[str, Any]],
    output_root: Path,
    plan_sha256: str,
) -> dict[str, Any]:
    group_by_id = {row["group_id"]: row for row in groups}
    partition_bytes: collections.Counter[str] = collections.Counter()
    wrapper_bytes: collections.Counter[str] = collections.Counter()
    wrapper_cells: collections.Counter[str] = collections.Counter()
    role_cells: collections.Counter[tuple[str, str]] = collections.Counter()
    maximum_artifact_bytes = 0
    for cell in cells:
        header = feasibility_by_id[cell["group_id"]]
        frames = preconditioned_frame_upper(
            header["excerpt_frame_count"],
            header["native_sample_rate_hz"],
            cell["target_sample_rate_hz"],
        )
        channels = 1 if cell["channel_treatment_id"] == "mono" else 2
        if cell["expectation"] == "controlled_positive":
            frames += CODEC_DECODE_PADDING_UPPER_FRAMES
        frames, channels = transformed_shape_upper(
            frame_count=frames,
            channel_count=channels,
            sample_rate_hz=cell["target_sample_rate_hz"],
            transform_id=cell["transform_id"],
        )
        byte_upper = artifact_byte_upper(
            frame_count=frames,
            channel_count=channels,
            wrapper_id=cell["wrapper_id"],
        )
        partition_bytes[cell["evidence_partition"]] += byte_upper
        wrapper_bytes[cell["wrapper_id"]] += byte_upper
        wrapper_cells[cell["wrapper_id"]] += 1
        role_cells[(cell["evidence_partition"], cell["expectation"])] += 1
        maximum_artifact_bytes = max(maximum_artifact_bytes, byte_upper)
    projected_retained_bytes = sum(partition_bytes.values())
    minimum_required_free_bytes = (
        projected_retained_bytes
        + MINIMUM_FREE_RESERVE_BYTES
        + WORKSPACE_ALLOWANCE_BYTES
    )
    repository_root = Path(__file__).resolve().parents[1]
    resolved_output_root = output_root.resolve()
    if resolved_output_root == repository_root or resolved_output_root.is_relative_to(
        repository_root
    ):
        raise ValueError("construction output root must remain outside Git")
    output_root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output_root).free < minimum_required_free_bytes:
        raise ValueError("output volume cannot retain the frozen upper bound and reserve")
    result = {
        "schema_version": SCHEMA_VERSION,
        "preflight_id": PREFLIGHT_ID,
        "state": "construction_path_free_preflight_run_evidence",
        "plan_sha256": plan_sha256,
        "benchmark_source_audio_read": False,
        "benchmark_audio_generated": False,
        "features_computed": False,
        "scores_opened": False,
        "construction_authorized": False,
        "paths_redacted": True,
        "private_ids_included": False,
        "summary": {
            "group_count": len(groups),
            "cell_count": len(cells),
            "controlled_positive_count": sum(
                row["expectation"] == "controlled_positive" for row in cells
            ),
            "negative_count": sum(row["expectation"] == "negative" for row in cells),
            "external_reserved_group_count": EXPECTED_EXTERNAL_RESERVE_COUNT,
            "all_lineage_checks_passed": True,
            "free_space_gate_passed": True,
        },
        "cell_counts": count_rows(
            role_cells, ["evidence_partition", "expectation"]
        ),
        "storage_upper_bound": {
            "projected_retained_bytes": projected_retained_bytes,
            "workspace_allowance_bytes": WORKSPACE_ALLOWANCE_BYTES,
            "minimum_free_space_reserve_bytes": MINIMUM_FREE_RESERVE_BYTES,
            "minimum_required_free_bytes": minimum_required_free_bytes,
            "maximum_single_artifact_bytes": maximum_artifact_bytes,
            "codec_decode_padding_upper_frames_per_positive": (
                CODEC_DECODE_PADDING_UPPER_FRAMES
            ),
            "resample_tail_upper_frames_per_stage": RESAMPLE_TAIL_UPPER_FRAMES,
            "per_artifact_container_allowance_bytes": (
                PER_ARTIFACT_CONTAINER_ALLOWANCE_BYTES
            ),
            "flac_worst_case_pcm_percent": FLAC_WORST_CASE_NUMERATOR,
            "by_partition": [
                {
                    "evidence_partition": partition,
                    "projected_retained_bytes": partition_bytes[partition],
                }
                for partition in PARTITIONS
            ],
            "by_wrapper": [
                {
                    "wrapper_id": wrapper_id,
                    "extension": WRAPPER_EXTENSIONS[wrapper_id],
                    "cell_count": wrapper_cells[wrapper_id],
                    "projected_retained_bytes": wrapper_bytes[wrapper_id],
                }
                for wrapper_id in sorted(WRAPPER_EXTENSIONS)
            ],
        },
        "checkpoint_contract": plan["checkpoint_contract"],
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
        raise ValueError(f"public construction preflight contains private key: {key}")
    if isinstance(value, dict):
        for child_key, child in value.items():
            assert_public_path_free(child, child_key)
    elif isinstance(value, list):
        for child in value:
            assert_public_path_free(child, key)
    elif isinstance(value, str) and (
        value.startswith("/") or "Library/Application Support" in value
    ):
        raise ValueError("public construction preflight contains a private path")


def attest(run_paths: list[Path], plan_path: Path) -> dict[str, Any]:
    if len(run_paths) != 2:
        raise ValueError("attestation requires exactly two complete preflights")
    if run_paths[0].read_bytes() != run_paths[1].read_bytes():
        raise ValueError("construction preflight reports differ")
    result = load_object(run_paths[0])
    if (
        result.get("state") != "construction_path_free_preflight_run_evidence"
        or result.get("plan_sha256") != sha256_file(plan_path)
    ):
        raise ValueError("construction preflight binding differs")
    final = dict(result)
    final["state"] = "construction_path_free_preflight_evidence"
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
        "source-allocation",
        "candidate-index",
        "assignment",
        "assignment-result",
        "feasibility-audit",
        "feasibility-result",
        "preconditioning-result",
        "factor",
        "toolchain",
        "toolchain-result",
        "public-decoder-result",
        "tool-paths",
        "output-root",
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
        print("attested two byte-identical construction preflights")
        return 0

    paths = {
        name.replace("_", "-"): getattr(args, name).expanduser().resolve()
        for name in (
            "plan",
            "source_allocation",
            "candidate_index",
            "assignment",
            "assignment_result",
            "feasibility_audit",
            "feasibility_result",
            "preconditioning_result",
            "factor",
            "toolchain",
            "toolchain_result",
            "public_decoder_result",
            "tool_paths",
            "output_root",
            "output",
        )
    }
    paths["generator"] = Path(__file__).resolve()
    plan = load_object(paths["plan"])
    validate_plan(plan, paths)
    allocation = load_object(paths["source-allocation"])
    candidate_index = load_object(paths["candidate-index"])
    assignment = load_object(paths["assignment"])
    assignment_result = load_object(paths["assignment-result"])
    feasibility = load_object(paths["feasibility-audit"])
    feasibility_result = load_object(paths["feasibility-result"])
    preconditioning_result = load_object(paths["preconditioning-result"])
    factor = load_object(paths["factor"])
    toolchain = load_object(paths["toolchain"])
    groups, cells, feasibility_by_id = validate_private_inputs(
        allocation,
        candidate_index,
        assignment,
        assignment_result,
        feasibility,
        feasibility_result,
        preconditioning_result,
        factor,
        toolchain,
        paths,
    )
    validate_cell_lineage(cells, groups, factor, toolchain)
    result = build_preflight(
        plan,
        groups,
        cells,
        feasibility_by_id,
        paths["output-root"],
        sha256_file(paths["plan"]),
    )
    write_json_atomic(paths["output"], result)
    print(
        f"preflighted {result['summary']['group_count']} groups and "
        f"{result['summary']['cell_count']} cells without reading audio"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
