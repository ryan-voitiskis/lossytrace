#!/usr/bin/env python3
"""Materialize the private v2 factorial manifest without computing features."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate-audio-integrity-factorial-manifest.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "audio_integrity_v2_manifest_validator", VALIDATOR_PATH
)
if VALIDATOR_SPEC is None or VALIDATOR_SPEC.loader is None:
    raise RuntimeError(f"could not load manifest validator: {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 2
PLAN_ID = "lossytrace-v2-analysis-manifest-20260802-001"
CONTRACT_ID = "lossytrace-audio-integrity-factorial-v2-20260802-001"
CONSTRUCTION_ID = "lossytrace-v2-construction-20260802-001"
ASSIGNMENT_ID = "lossytrace-v2-fractional-assignment-20260802-004"
MANIFEST_ID = "lossytrace-v2-factorial-manifest-20260802-001"
CONSTRUCTOR_TOOL_ID = "lossytrace_v2_constructor_engine_20260802_001"
VALIDATION_PROFILES = (
    "structural",
    "mechanism_development_freeze",
    "encoder_transfer_freeze",
)
FORBIDDEN_PUBLIC_KEYS = {
    "artifact_relative_path",
    "audio_sha256",
    "case_id",
    "group_id",
    "member_id",
    "partition_group",
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


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"refusing to replace existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
        output.flush()
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(prefix: bytes, value: object) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(prefix + canonical).hexdigest()


def safe_relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} is absent")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\0" in value:
        raise ValueError(f"{label} is unsafe")
    return value


def resolve_beneath(root: Path, relative: str) -> Path:
    root = root.resolve()
    path = (root / safe_relative_path(relative, "artifact path")).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError("artifact path escapes the construction root") from error
    return path


def validate_binding(path: Path, expected: Any, label: str) -> None:
    if not isinstance(expected, str) or not path.is_file():
        raise ValueError(f"{label} binding is absent")
    if sha256_file(path) != expected:
        raise ValueError(f"{label} binding differs")


def lookup_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    output = {row.get(key): row for row in rows}
    if None in output or len(output) != len(rows):
        raise ValueError(f"{key} registry is invalid")
    return output


def case_id(assignment_id: str) -> str:
    return f"case-{assignment_id}"


def recipe_id(assignment_id: str) -> str:
    return f"recipe-{assignment_id}"


def assert_public_path_free(value: object, key: str | None = None) -> None:
    if key in FORBIDDEN_PUBLIC_KEYS:
        raise ValueError(f"public result contains private key: {key}")
    if isinstance(value, dict):
        for child_key, child in value.items():
            assert_public_path_free(child, child_key)
    elif isinstance(value, list):
        for child in value:
            assert_public_path_free(child, key)
    elif isinstance(value, str) and value.startswith("/"):
        raise ValueError("public result contains an absolute path")


def validate_plan(plan: dict[str, Any], paths: dict[str, Path]) -> None:
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("plan_id") != PLAN_ID
        or plan.get("state")
        != "analysis_manifest_materialization_frozen_before_replay"
        or plan.get("features_computed") is not False
        or plan.get("scores_opened") is not False
        or plan.get("public_verdict_enabled") is not False
        or plan.get("authorized_partitions")
        != ["mechanism_development", "encoder_transfer", "external_transfer"]
        or plan.get("authorized_validation_profiles") != list(VALIDATION_PROFILES)
        or plan.get("complete_replays_required") != 2
    ):
        raise ValueError("analysis-manifest plan state differs")
    bindings = plan.get("bindings", {})
    for path_key, binding_key, label in (
        ("generator", "generator_sha256", "manifest generator"),
        ("validator", "manifest_validator_sha256", "manifest validator"),
        ("contract", "contract_sha256", "factorial contract"),
        ("factor", "factor_levels_sha256", "factor levels"),
        ("toolchain", "toolchain_manifest_sha256", "toolchain manifest"),
        ("inventory", "inventory_sha256", "source/tool inventory"),
        ("source-allocation", "private_source_allocation_sha256", "source allocation"),
        ("assignment", "private_fractional_assignment_sha256", "fractional assignment"),
        ("constructor-manifest", "private_constructor_manifest_sha256", "constructor manifest"),
        ("constructor-result", "public_constructor_result_sha256", "constructor result"),
    ):
        validate_binding(paths[path_key], bindings.get(binding_key), label)


def source_collections(
    plan: dict[str, Any], selected: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_collection: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        by_collection[row["source_collection_id"]].append(row)
    provenance = lookup_by(plan.get("source_provenance", []), "source_collection_id")
    if set(provenance) != set(by_collection):
        raise ValueError("source-provenance registry differs from selected collections")
    output = []
    for collection_id, rows in sorted(by_collection.items()):
        fields = {
            field: {row.get(field) for row in rows}
            for field in (
                "source_lineage_id",
                "evidence_partition",
                "source_domain",
                "provenance_tier",
            )
        }
        if any(len(values) != 1 or None in values for values in fields.values()):
            raise ValueError(f"source collection is internally inconsistent: {collection_id}")
        binding = provenance[collection_id]
        output.append(
            {
                "source_collection_id": collection_id,
                **{field: next(iter(values)) for field, values in fields.items()},
                "license": binding["license"],
                "provenance_record_sha256": binding["provenance_record_sha256"],
            }
        )
    return output


def tool_registries(
    toolchain: dict[str, Any], generator_sha256: str
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    tools = [dict(row) for row in toolchain.get("tool_bindings", [])]
    tools.append(
        {
            "tool_id": CONSTRUCTOR_TOOL_ID,
            "implementation": "LossyTrace v2 deterministic constructor and PCM transform engine",
            "version": CONSTRUCTION_ID,
            "binary_sha256": generator_sha256,
            "license": "MIT OR Apache-2.0",
        }
    )
    tools.sort(key=lambda row: row["tool_id"])
    return tools, lookup_by(tools, "tool_id")


def encoder_registries(
    cells: list[dict[str, Any]],
    toolchain: dict[str, Any],
    tools: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    expanded = lookup_by(
        toolchain.get("expanded_encoder_settings", []), "expanded_setting_id"
    )
    used_settings = sorted(
        {
            cell["expanded_setting_id"]
            for cell in cells
            if cell.get("expectation") == "controlled_positive"
        }
    )
    settings = []
    encoder_tools: dict[str, str] = {}
    encoder_lineages: dict[str, str] = {}
    for setting_id in used_settings:
        row = expanded.get(setting_id)
        if row is None:
            raise ValueError(f"assigned encoder setting is absent: {setting_id}")
        tool_id = row.get("tool_id")
        binding_tool_ids = row.get("binding_tool_ids") or [tool_id]
        if (
            not isinstance(tool_id, str)
            or tool_id not in tools
            or not isinstance(binding_tool_ids, list)
            or tool_id not in binding_tool_ids
            or any(value not in tools for value in binding_tool_ids)
        ):
            raise ValueError(f"encoder setting tool binding differs: {setting_id}")
        encoder_id = row["encoder_id"]
        previous = encoder_tools.setdefault(encoder_id, tool_id)
        if previous != tool_id:
            raise ValueError(f"encoder maps to multiple tools: {encoder_id}")
        lineage = row["lineage_id"]
        previous_lineage = encoder_lineages.setdefault(encoder_id, lineage)
        if previous_lineage != lineage:
            raise ValueError(f"encoder maps to multiple lineages: {encoder_id}")
        settings.append(
            {
                "setting_id": setting_id,
                "codec_family": row["codec_family"],
                "encoder_id": encoder_id,
                "rate_control": row["rate_control"],
                "bitrate_or_quality": row["bitrate_or_quality"],
                "sample_rate_hz": row["expected_sample_rate_hz"],
                "channel_mode": row["channel_treatment_id"],
                "encoder_lowpass": row["nominal_encoder_lowpass"],
            }
        )
    encoders = []
    for encoder_id, tool_id in sorted(encoder_tools.items()):
        tool = tools[tool_id]
        encoders.append(
            {
                "encoder_id": encoder_id,
                "lineage_id": encoder_lineages[encoder_id],
                "implementation": tool["implementation"],
                "version": tool["version"],
                "binary_sha256": tool["binary_sha256"],
                "license": tool["license"],
            }
        )
    return encoders, settings, expanded


def decoder_registry(
    cells: list[dict[str, Any]],
    toolchain: dict[str, Any],
    tools: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]]:
    bindings = lookup_by(
        toolchain.get("history_decoder_bindings", []), "history_decoder_id"
    )
    used = sorted(
        {
            cell["history_decoder_id"]
            for cell in cells
            if cell.get("history_decoder_id") is not None
        }
    )
    decoders = []
    tool_by_decoder = {}
    for decoder_id in used:
        binding = bindings.get(decoder_id)
        if binding is None or binding.get("tool_id") not in tools:
            raise ValueError(f"history decoder binding is absent: {decoder_id}")
        tool = tools[binding["tool_id"]]
        tool_by_decoder[decoder_id] = binding["tool_id"]
        decoders.append(
            {
                "decoder_id": decoder_id,
                "implementation": tool["implementation"],
                "version": tool["version"],
                "binary_sha256": tool["binary_sha256"],
                "license": tool["license"],
            }
        )
    analysis = toolchain.get("analysis_decoder_binding", {})
    analysis_id = analysis.get("analysis_decoder_id")
    analysis_tool_id = analysis.get("tool_id")
    if not isinstance(analysis_id, str) or analysis_tool_id not in tools:
        raise ValueError("analysis decoder binding is absent")
    analysis_tool = tools[analysis_tool_id]
    tool_by_decoder[analysis_id] = analysis_tool_id
    decoders.append(
        {
            "decoder_id": analysis_id,
            "implementation": analysis["implementation"],
            "version": analysis_tool["version"],
            "binary_sha256": analysis_tool["binary_sha256"],
            "license": analysis_tool["license"],
        }
    )
    decoders.sort(key=lambda row: row["decoder_id"])
    return decoders, bindings, tool_by_decoder


def transform_registry(
    factor: dict[str, Any], toolchain: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]]:
    factor_rows = lookup_by(factor.get("pcm_transform_levels", []), "transform_id")
    bindings = lookup_by(
        toolchain.get("pcm_transform_bindings", []), "transform_id"
    )
    if set(factor_rows) != set(bindings):
        raise ValueError("factor and toolchain transform registries differ")
    tool_by_transform = {}
    output = []
    for transform_id, row in sorted(factor_rows.items()):
        binding = bindings[transform_id]
        if binding.get("family") != row.get("family"):
            raise ValueError(f"transform family differs: {transform_id}")
        tool_id = (
            "ffmpeg_8_1_2_1"
            if row["family"] in {"pcm_lowpass", "pcm_resample", "lossless_container"}
            else CONSTRUCTOR_TOOL_ID
        )
        tool_by_transform[transform_id] = tool_id
        output.append(
            {
                "transform_id": transform_id,
                "family": row["family"],
                "parameters": row["parameters"],
                "tool_id": tool_id,
            }
        )
    return output, factor_rows, tool_by_transform


def recipe_definition(
    *,
    cell: dict[str, Any],
    construction_plan_sha256: str,
    generator_sha256: str,
    toolchain_sha256: str,
    source_assignment_id: str,
    tool_ids: list[str],
) -> dict[str, Any]:
    payload = {
        "cell": cell,
        "construction_plan_sha256": construction_plan_sha256,
        "generator_sha256": generator_sha256,
        "toolchain_sha256": toolchain_sha256,
        "source_assignment_id": source_assignment_id,
        "tool_ids": tool_ids,
    }
    return {
        "recipe_id": recipe_id(cell["assignment_id"]),
        "output_case_id": case_id(cell["assignment_id"]),
        "source_case_id": case_id(source_assignment_id),
        "command_sha256": sha256_json(
            b"lossytrace-v2-materialized-render-recipe-20260802\0", payload
        ),
        "tool_ids": tool_ids,
    }


def build_manifest(
    *,
    plan: dict[str, Any],
    contract: dict[str, Any],
    factor: dict[str, Any],
    toolchain: dict[str, Any],
    allocation: dict[str, Any],
    assignment: dict[str, Any],
    constructor_manifest: dict[str, Any],
    audio_root: Path,
    input_hashes: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if contract.get("contract_id") != CONTRACT_ID:
        raise ValueError("factorial contract ID differs")
    if (
        assignment.get("assignment_id") != ASSIGNMENT_ID
        or assignment.get("scores_opened") is not False
        or assignment.get("absolute_paths_recorded") is not False
    ):
        raise ValueError("fractional assignment state differs")
    if (
        constructor_manifest.get("construction_id") != CONSTRUCTION_ID
        or constructor_manifest.get("scope") != "full"
        or constructor_manifest.get("state") != "constructed_full_private_manifest"
        or constructor_manifest.get("features_computed") is not False
        or constructor_manifest.get("scores_opened") is not False
        or constructor_manifest.get("public_verdict_enabled") is not False
    ):
        raise ValueError("constructor manifest state differs")

    selected = allocation.get("selected", [])
    groups = assignment.get("groups", [])
    cells = assignment.get("cells", [])
    checkpoints = constructor_manifest.get("checkpoints", [])
    if not all(isinstance(value, list) for value in (selected, groups, cells, checkpoints)):
        raise ValueError("private input collections are absent")
    selected_by_group = {row.get("group_id"): row for row in selected}
    group_by_id = {row.get("group_id"): row for row in groups}
    cell_by_id = {row.get("assignment_id"): row for row in cells}
    checkpoint_by_id = {
        row.get("cell", {}).get("assignment_id"): row for row in checkpoints
    }
    if (
        len(selected_by_group) != len(selected)
        or len(group_by_id) != len(groups)
        or len(cell_by_id) != len(cells)
        or len(checkpoint_by_id) != len(checkpoints)
        or set(selected_by_group) != set(group_by_id)
        or set(cell_by_id) != set(checkpoint_by_id)
    ):
        raise ValueError("private source, cell, or checkpoint identity differs")
    if len(cells) != 12885 or len(groups) != 793:
        raise ValueError("full assignment count differs")

    collections = source_collections(plan, selected)
    tools_list, tools = tool_registries(
        toolchain, constructor_manifest["generator_sha256"]
    )
    encoders, settings, expanded = encoder_registries(cells, toolchain, tools)
    decoders, _, tool_by_decoder = decoder_registry(cells, toolchain, tools)
    transforms, transform_factors, tool_by_transform = transform_registry(
        factor, toolchain
    )
    wrapper_by_id = lookup_by(toolchain.get("wrapper_bindings", []), "wrapper_id")
    analysis_decoder_id = toolchain.get("analysis_decoder_binding", {}).get(
        "analysis_decoder_id"
    )
    if not isinstance(analysis_decoder_id, str):
        raise ValueError("global analysis decoder binding is absent")

    materialized_cases = []
    recipes = []
    artifact_hashes = []
    analysis_pcm_hashes = []
    total_artifact_bytes = 0
    for assignment_id in sorted(cell_by_id):
        cell = cell_by_id[assignment_id]
        checkpoint = checkpoint_by_id[assignment_id]
        if checkpoint.get("cell") != cell:
            raise ValueError(f"checkpoint cell differs: {assignment_id}")
        relative = safe_relative_path(
            checkpoint.get("artifact_relative_path"), "checkpoint artifact path"
        )
        artifact = resolve_beneath(audio_root, relative)
        if not artifact.is_file():
            raise ValueError(f"constructed artifact is absent: {assignment_id}")
        artifact_sha256 = sha256_file(artifact)
        if artifact_sha256 != checkpoint.get("artifact_sha256"):
            raise ValueError(f"constructed artifact hash differs: {assignment_id}")
        artifact_bytes = artifact.stat().st_size
        if artifact_bytes != checkpoint.get("artifact_bytes"):
            raise ValueError(f"constructed artifact size differs: {assignment_id}")
        analysis_pcm = checkpoint.get("analysis_pcm", {})
        if not isinstance(analysis_pcm, dict):
            raise ValueError(f"analysis PCM checkpoint is absent: {assignment_id}")
        group = selected_by_group.get(cell["group_id"])
        if group is None:
            raise ValueError(f"source group is absent: {assignment_id}")
        wrapper = wrapper_by_id.get(cell["wrapper_id"])
        if wrapper is None:
            raise ValueError(f"wrapper is absent: {assignment_id}")
        transform_id = cell["transform_id"]
        row: dict[str, Any] = {
            "case_id": case_id(assignment_id),
            "source_group": cell["group_id"],
            "partition_group": group["partition_group"],
            "source_collection_id": group["source_collection_id"],
            "source_lineage_id": group["source_lineage_id"],
            "source_domain": group["source_domain"],
            "evidence_partition": cell["evidence_partition"],
            "relative_path": relative,
            "audio_sha256": artifact_sha256,
            "audio_bytes": artifact_bytes,
            "provenance_tier": group["provenance_tier"],
            "expectation": cell["expectation"],
            "history_class": cell["history_class"],
            "assessment_eligibility": "eligible",
            "current_container": wrapper["container"],
            "current_codec": "pcm",
            "sample_rate_hz": analysis_pcm["sample_rate_hz"],
            "channel_count": analysis_pcm["channel_count"],
            "frame_count": analysis_pcm["frame_count"],
            "analysis_decoder_id": analysis_decoder_id,
            "post_transform_ids": [] if transform_id == "identity" else [transform_id],
            "channel_treatment_id": cell["channel_treatment_id"],
            "lossless_wrapper_id": cell["wrapper_id"],
        }
        if cell.get("analysis_decoder_id", analysis_decoder_id) != analysis_decoder_id:
            raise ValueError(f"cell analysis decoder differs: {assignment_id}")
        source_assignment_id = cell.get("source_reference_assignment_id")
        tool_ids = {CONSTRUCTOR_TOOL_ID, wrapper["tool_id"], tool_by_transform[transform_id]}
        if cell["history_class"] == "controlled_lossy_history":
            if not isinstance(source_assignment_id, str):
                source_assignment_id = cell["matched_reference_assignment_id"]
            setting = expanded[cell["expanded_setting_id"]]
            setting_tools = setting.get("binding_tool_ids") or [setting.get("tool_id")]
            tool_ids.update(value for value in setting_tools if isinstance(value, str))
            tool_ids.add(tool_by_decoder[cell["history_decoder_id"]])
            row.update(
                {
                    "reference_case_id": case_id(cell["matched_reference_assignment_id"]),
                    "encoder_setting_id": cell["expanded_setting_id"],
                    "encoder_id": cell["encoder_id"],
                    "encoder_lineage_id": cell["lineage_id"],
                    "codec_family": cell["codec_family"],
                    "history_decoder_id": cell["history_decoder_id"],
                    "assignment_role": cell["assignment_role"],
                    "recipe_id": recipe_id(assignment_id),
                }
            )
        elif cell["history_class"] == "pcm_hard_negative":
            if not isinstance(source_assignment_id, str):
                raise ValueError(f"hard negative source is absent: {assignment_id}")
            row.update(
                {
                    "reference_case_id": case_id(source_assignment_id),
                    "hard_negative_class": transform_factors[transform_id]["hard_negative_class"],
                    "recipe_id": recipe_id(assignment_id),
                }
            )
        elif cell["history_class"] != "pcm_reference":
            raise ValueError(f"history class differs: {assignment_id}")

        if cell["history_class"] != "pcm_reference":
            if not isinstance(source_assignment_id, str):
                raise ValueError(f"generated source is absent: {assignment_id}")
            recipes.append(
                recipe_definition(
                    cell=cell,
                    construction_plan_sha256=constructor_manifest["plan_sha256"],
                    generator_sha256=constructor_manifest["generator_sha256"],
                    toolchain_sha256=input_hashes["toolchain_sha256"],
                    source_assignment_id=source_assignment_id,
                    tool_ids=sorted(tool_ids),
                )
            )
        materialized_cases.append(row)
        artifact_hashes.append(artifact_sha256)
        analysis_pcm_hashes.append(analysis_pcm["pcm_sha256"])
        total_artifact_bytes += artifact_bytes

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_id": MANIFEST_ID,
        "contract_id": CONTRACT_ID,
        "state": "factorial_manifest_materialized_without_scores",
        "feature_version": 0,
        "features_computed": False,
        "scores_opened": False,
        "public_verdict_enabled": False,
        "existing_v1_holdouts_included": False,
        "inputs": input_hashes,
        "source_collections": collections,
        "tools": tools_list,
        "encoders": encoders,
        "encoder_settings": sorted(settings, key=lambda row: row["setting_id"]),
        "decoders": decoders,
        "transforms": transforms,
        "recipes": sorted(recipes, key=lambda row: row["recipe_id"]),
        "cases": materialized_cases,
    }
    observations = {
        "artifact_bytes": total_artifact_bytes,
        "artifact_sha256_set_digest": sha256_json(
            b"lossytrace-v2-analysis-artifact-set-20260802\0", sorted(artifact_hashes)
        ),
        "analysis_pcm_sha256_set_digest": sha256_json(
            b"lossytrace-v2-analysis-pcm-set-20260802\0", sorted(analysis_pcm_hashes)
        ),
    }
    return manifest, observations


def compose(paths: dict[str, Path]) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = load_object(paths["plan"])
    validate_plan(plan, paths)
    inputs = {
        "analysis_manifest_plan_sha256": sha256_file(paths["plan"]),
        "manifest_validator_sha256": sha256_file(paths["validator"]),
        "contract_sha256": sha256_file(paths["contract"]),
        "factor_levels_sha256": sha256_file(paths["factor"]),
        "toolchain_sha256": sha256_file(paths["toolchain"]),
        "inventory_sha256": sha256_file(paths["inventory"]),
        "source_allocation_sha256": sha256_file(paths["source-allocation"]),
        "fractional_assignment_sha256": sha256_file(paths["assignment"]),
        "constructor_manifest_sha256": sha256_file(paths["constructor-manifest"]),
        "constructor_result_sha256": sha256_file(paths["constructor-result"]),
        "generator_sha256": sha256_file(paths["generator"]),
    }
    manifest, observations = build_manifest(
        plan=plan,
        contract=load_object(paths["contract"]),
        factor=load_object(paths["factor"]),
        toolchain=load_object(paths["toolchain"]),
        allocation=load_object(paths["source-allocation"]),
        assignment=load_object(paths["assignment"]),
        constructor_manifest=load_object(paths["constructor-manifest"]),
        audio_root=paths["audio-root"],
        input_hashes=inputs,
    )
    return manifest, observations


def validate_materialized(
    contract: dict[str, Any], manifest: dict[str, Any], input_hashes: dict[str, str]
) -> dict[str, Any]:
    reports = {}
    for profile in VALIDATION_PROFILES:
        errors, report = VALIDATOR.validate(
            contract,
            manifest,
            profile=profile,
            contract_sha256=input_hashes["contract_sha256"],
            manifest_sha256=None,
        )
        if errors:
            raise ValueError(
                f"materialized manifest failed {profile}:\n- " + "\n- ".join(errors)
            )
        reports[profile] = report
    return reports


def public_run(
    *,
    plan: dict[str, Any],
    manifest: dict[str, Any],
    manifest_sha256: str,
    observations: dict[str, Any],
    validations: dict[str, Any],
) -> dict[str, Any]:
    structural = validations["structural"]
    cases = manifest["cases"]
    result = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "manifest_id": MANIFEST_ID,
        "state": "analysis_manifest_path_free_run_evidence",
        "feature_version": 0,
        "features_computed": False,
        "scores_opened": False,
        "public_verdict_enabled": False,
        "external_positive_count": 0,
        "inputs": {
            **manifest["inputs"],
            "private_analysis_manifest_sha256": manifest_sha256,
        },
        "inventory": structural["inventory"],
        "partition_summary": structural["partition_summary"],
        "split_checks": structural["split_checks"],
        "validation_profiles": {
            profile: {
                "valid": report["valid"],
                "validation_profile": report["validation_profile"],
            }
            for profile, report in validations.items()
        },
        "summary": {
            "case_count": len(cases),
            "negative_count": sum(row["expectation"] == "negative" for row in cases),
            "controlled_positive_count": sum(
                row["expectation"] == "controlled_positive" for row in cases
            ),
            "all_artifacts_rehashed": True,
            **observations,
        },
        "partition_opening": plan["partition_opening"],
    }
    assert_public_path_free(result)
    return result


def attest(
    *,
    plan_path: Path,
    manifests: list[Path],
    runs: list[Path],
) -> dict[str, Any]:
    if len(manifests) != 2 or len(runs) != 2:
        raise ValueError("analysis-manifest attestation requires exactly two replays")
    if manifests[0].read_bytes() != manifests[1].read_bytes():
        raise ValueError("private analysis manifests are not byte-identical")
    if runs[0].read_bytes() != runs[1].read_bytes():
        raise ValueError("analysis-manifest run reports are not byte-identical")
    run = load_object(runs[0])
    if (
        run.get("state") != "analysis_manifest_path_free_run_evidence"
        or run.get("inputs", {}).get("analysis_manifest_plan_sha256")
        != sha256_file(plan_path)
        or run.get("inputs", {}).get("private_analysis_manifest_sha256")
        != sha256_file(manifests[0])
    ):
        raise ValueError("analysis-manifest run binding differs")
    result = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "manifest_id": MANIFEST_ID,
        "state": "analysis_manifest_path_free_evidence",
        "feature_version": 0,
        "features_computed": False,
        "scores_opened": False,
        "public_verdict_enabled": False,
        "external_positive_count": 0,
        "inputs": run["inputs"],
        "inventory": run["inventory"],
        "partition_summary": run["partition_summary"],
        "split_checks": run["split_checks"],
        "validation_profiles": run["validation_profiles"],
        "summary": run["summary"],
        "partition_opening": run["partition_opening"],
        "reproducibility": {
            "complete_replays_required": 2,
            "complete_replays_observed": 2,
            "private_manifests_byte_identical": True,
            "run_reports_byte_identical": True,
            "plan_sha256": sha256_file(plan_path),
            "private_manifest_sha256": sha256_file(manifests[0]),
            "run_report_sha256": sha256_file(runs[0]),
        },
    }
    assert_public_path_free(result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    compose_parser = subparsers.add_parser("compose")
    for name in (
        "plan",
        "contract",
        "factor",
        "toolchain",
        "inventory",
        "source-allocation",
        "assignment",
        "constructor-manifest",
        "constructor-result",
        "audio-root",
        "output",
        "run",
    ):
        compose_parser.add_argument(f"--{name}", required=True, type=Path)
    attest_parser = subparsers.add_parser("attest")
    attest_parser.add_argument("--plan", required=True, type=Path)
    attest_parser.add_argument("--manifest", required=True, type=Path, action="append")
    attest_parser.add_argument("--run", required=True, type=Path, action="append")
    attest_parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "attest":
        result = attest(
            plan_path=args.plan.expanduser().resolve(),
            manifests=[path.expanduser().resolve() for path in args.manifest],
            runs=[path.expanduser().resolve() for path in args.run],
        )
        write_new(args.output.expanduser().resolve(), result)
        print("attested two byte-identical private analysis manifests")
        return 0

    names = (
        "plan",
        "contract",
        "factor",
        "toolchain",
        "inventory",
        "source_allocation",
        "assignment",
        "constructor_manifest",
        "constructor_result",
        "audio_root",
        "output",
        "run",
    )
    paths = {
        name.replace("_", "-"): getattr(args, name).expanduser().resolve()
        for name in names
    }
    paths["generator"] = Path(__file__).resolve()
    paths["validator"] = VALIDATOR_PATH
    manifest, observations = compose(paths)
    validations = validate_materialized(
        load_object(paths["contract"]), manifest, manifest["inputs"]
    )
    write_new(paths["output"], manifest)
    run = public_run(
        plan=load_object(paths["plan"]),
        manifest=manifest,
        manifest_sha256=sha256_file(paths["output"]),
        observations=observations,
        validations=validations,
    )
    write_new(paths["run"], run)
    print(
        f"materialized {run['summary']['case_count']} private cases without features or scores"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
