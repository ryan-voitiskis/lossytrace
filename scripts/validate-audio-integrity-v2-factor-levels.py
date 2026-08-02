#!/usr/bin/env python3
"""Validate the frozen v2 factor levels and their source-allocation boundary."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SHA256 = re.compile(r"^[0-9a-f]{64}$")
PARTITIONS = {"mechanism_development", "encoder_transfer"}


def load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: top-level JSON must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def index_rows(
    rows: Any, key: str, label: str, errors: list[str]
) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        errors.append(f"{label} must be a list")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        identity = row.get(key)
        if not isinstance(identity, str) or not identity:
            errors.append(f"{label}[{index}].{key} must be a nonempty string")
        elif identity in result:
            errors.append(f"duplicate {label} identity: {identity}")
        else:
            result[identity] = row
    return result


def validate_repository_binding(
    repository_root: Path,
    binding: dict[str, Any],
    path_field: str,
    hash_field: str,
    label: str,
    errors: list[str],
) -> Path | None:
    relative = binding.get(path_field)
    expected_hash = binding.get(hash_field)
    if (
        not isinstance(relative, str)
        or not relative
        or Path(relative).is_absolute()
        or SHA256.fullmatch(str(expected_hash)) is None
    ):
        errors.append(f"{label} binding is invalid")
        return None
    path = (repository_root / relative).resolve()
    if not path.is_relative_to(repository_root) or not path.is_file():
        errors.append(f"{label} path is missing or outside the repository")
        return None
    if sha256_file(path) != expected_hash:
        errors.append(f"{label} hash differs")
    return path


def recursively_find_keys(value: Any, keys: set[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        found.update(keys & set(value))
        for child in value.values():
            found.update(recursively_find_keys(child, keys))
    elif isinstance(value, list):
        for child in value:
            found.update(recursively_find_keys(child, keys))
    return found


def validate(
    factors: dict[str, Any],
    contract: dict[str, Any],
    inventory: dict[str, Any],
    repository_root: Path,
) -> list[str]:
    errors: list[str] = []
    expected_state = {
        "schema_version": 1,
        "state": "factor_levels_frozen_before_toolchain_and_assignment",
        "contract_id": contract.get("contract_id"),
        "audio_generated": False,
        "scores_opened": False,
        "toolchain_bindings_frozen": False,
        "fractional_assignment_frozen": False,
        "existing_v1_holdouts_included": False,
    }
    for field, expected in expected_state.items():
        if factors.get(field) != expected:
            errors.append(f"factor freeze {field} differs")
    if factors.get("public_state") != contract.get("public_state"):
        errors.append("factor freeze public state differs from the factorial contract")

    source_binding = factors.get("source_allocation_binding")
    if not isinstance(source_binding, dict):
        errors.append("source allocation binding is absent")
        source_binding = {}
    rules_path = validate_repository_binding(
        repository_root,
        source_binding,
        "rules_path",
        "rules_sha256",
        "source allocation rules",
        errors,
    )
    aggregate_path = validate_repository_binding(
        repository_root,
        source_binding,
        "aggregate_path",
        "aggregate_sha256",
        "source allocation aggregate",
        errors,
    )
    if rules_path is not None:
        rules = load_object(rules_path)
        if rules.get("state") != "source_allocation_rules_frozen_before_execution":
            errors.append("bound source allocation rules state differs")
    if aggregate_path is not None:
        aggregate = load_object(aggregate_path)
        if (
            aggregate.get("state") != "source_allocation_path_free_evidence"
            or aggregate.get("audio_generated") is not False
            or aggregate.get("scores_opened") is not False
            or aggregate.get("reproducibility", {}).get(
                "complete_replays_byte_identical"
            )
            is not True
            or aggregate.get("private_artifact_bindings", {}).get(
                "source_allocation_sha256"
            )
            != source_binding.get("private_allocation_sha256")
            or aggregate.get("selected_summary", {}).get("selected_group_count")
            != source_binding.get("selected_group_count")
        ):
            errors.append("bound source allocation evidence differs")

    encoder_inventory = index_rows(
        inventory.get("encoder_candidates"), "encoder_id", "encoder inventory", errors
    )
    decoder_inventory = index_rows(
        inventory.get("decoder_candidates"), "decoder_id", "decoder inventory", errors
    )
    templates = index_rows(
        factors.get("codec_setting_templates"),
        "template_id",
        "codec setting templates",
        errors,
    )
    scoped_codecs = set(contract.get("scoped_codec_families", []))
    counts: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    lineages: dict[str, dict[str, set[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(set)
    )
    anchors: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    required_template_fields = {
        "template_id",
        "evidence_partition",
        "codec_family",
        "encoder_id",
        "lineage_id",
        "rate_control",
        "bitrate_or_quality",
        "sample_rate_hz",
        "stereo_channel_mode",
        "encoder_lowpass",
    }
    for template_id, template in templates.items():
        missing = required_template_fields - set(template)
        if missing:
            errors.append(f"setting template {template_id} lacks {sorted(missing)}")
            continue
        partition = str(template["evidence_partition"])
        codec = str(template["codec_family"])
        encoder_id = str(template["encoder_id"])
        lineage = str(template["lineage_id"])
        if partition not in PARTITIONS:
            errors.append(f"setting template {template_id} has invalid partition")
        if codec not in scoped_codecs:
            errors.append(f"setting template {template_id} has invalid codec")
        if not isinstance(template.get("sample_rate_hz"), int) or template.get(
            "sample_rate_hz", 0
        ) <= 0:
            errors.append(f"setting template {template_id} has invalid sample rate")
        lowpass = template.get("encoder_lowpass")
        if not isinstance(lowpass, dict) or set(lowpass) != {"mode", "hz"}:
            errors.append(f"setting template {template_id} has invalid lowpass factor")
        encoder = encoder_inventory.get(encoder_id)
        if encoder is None:
            errors.append(f"setting template {template_id} references unknown encoder")
        elif (
            encoder.get("codec_family") != codec
            or encoder.get("lineage_id") != lineage
            or encoder.get("recommended_partition") != partition
        ):
            errors.append(f"setting template {template_id} encoder boundary differs")
        if partition in PARTITIONS and codec in scoped_codecs:
            counts[partition][codec] += 1
            lineages[partition][codec].add(lineage)
            if template.get("anchor") is True:
                anchors[partition][codec] += 1

    freeze_profiles = contract.get("freeze_profiles", {})
    for partition in sorted(PARTITIONS):
        profile = freeze_profiles.get(f"{partition}_freeze", {})
        minimum_settings = profile.get("minimum_settings_per_scoped_codec")
        minimum_lineages = profile.get("minimum_encoder_lineages", {})
        for codec in sorted(scoped_codecs):
            if counts[partition][codec] < minimum_settings:
                errors.append(
                    f"{partition} {codec} needs {minimum_settings} setting templates"
                )
            if len(lineages[partition][codec]) < minimum_lineages.get(codec, 0):
                errors.append(
                    f"{partition} {codec} lacks required encoder lineages"
                )
            if anchors[partition][codec] != 1:
                errors.append(
                    f"{partition} {codec} must have exactly one anchor template"
                )
            overlap = lineages["mechanism_development"][codec] & lineages[
                "encoder_transfer"
            ][codec]
            if overlap:
                errors.append(
                    f"development/encoder-transfer {codec} lineages overlap: {sorted(overlap)}"
                )

    decoder_levels = index_rows(
        factors.get("history_decoder_levels"),
        "history_decoder_id",
        "history decoder levels",
        errors,
    )
    for decoder_id, level in decoder_levels.items():
        inventory_row = decoder_inventory.get(decoder_id)
        codec_families = level.get("codec_families")
        if not isinstance(codec_families, list) or not set(codec_families) <= scoped_codecs:
            errors.append(f"history decoder {decoder_id} has invalid codec families")
        elif inventory_row is None:
            errors.append(f"history decoder {decoder_id} is absent from inventory")
        elif set(codec_families) != set(inventory_row.get("codec_families", [])):
            errors.append(f"history decoder {decoder_id} codec scope differs")

    transforms = index_rows(
        factors.get("pcm_transform_levels"),
        "transform_id",
        "PCM transform levels",
        errors,
    )
    identity_rows = [row for row in transforms.values() if row.get("family") == "identity"]
    hard_negative_classes = [
        row.get("hard_negative_class")
        for row in transforms.values()
        if row.get("family") != "identity"
    ]
    if len(identity_rows) != 1 or identity_rows[0].get("transform_id") != "identity":
        errors.append("PCM transforms need exactly one identity level")
    if (
        len(hard_negative_classes) < 8
        or any(not isinstance(value, str) or not value for value in hard_negative_classes)
        or len(hard_negative_classes) != len(set(hard_negative_classes))
    ):
        errors.append("PCM transforms need at least eight distinct hard-negative classes")
    for transform_id, transform in transforms.items():
        if not isinstance(transform.get("parameters"), dict):
            errors.append(f"PCM transform {transform_id} parameters must be an object")
        if transform.get("applicable_to_positive_pair") is not True:
            errors.append(f"PCM transform {transform_id} must be pair-applicable")

    wrappers = index_rows(
        factors.get("wrapper_levels"), "wrapper_id", "wrapper levels", errors
    )
    if set(wrappers) != {"flac16", "wav16", "aiff16"}:
        errors.append("wrapper levels must be the frozen FLAC/WAV/AIFF set")
    if any(row.get("current_codec") != "pcm" for row in wrappers.values()):
        errors.append("all frozen wrappers must carry current PCM")

    pair_rules = factors.get("pair_and_interaction_rules")
    if not isinstance(pair_rules, dict) or any(
        pair_rules.get(field) is not True
        for field in (
            "one_nonidentity_pcm_transform_per_case",
            "no_unpreregistered_transform_interactions",
            "codec_bitstreams_are_intermediate",
        )
    ):
        errors.append("pair and interaction rules differ")

    coverage = factors.get("coverage_requirements_before_partition_opening")
    if not isinstance(coverage, dict):
        errors.append("coverage requirements are absent")
        coverage = {}
    source_counts = (
        load_object(aggregate_path)
        .get("selected_summary", {})
        .get("selected_counts_by_partition", {})
        if aggregate_path is not None
        else {}
    )
    for partition in ("mechanism_development", "encoder_transfer", "external_transfer"):
        row = coverage.get(partition)
        if not isinstance(row, dict):
            errors.append(f"{partition} coverage requirements are absent")
            continue
        if row.get("reference_source_groups") != source_counts.get(partition):
            errors.append(f"{partition} reference group coverage differs")
        profile = freeze_profiles.get(f"{partition}_freeze", {})
        if partition != "external_transfer":
            if row.get("anchor_positive_source_groups_per_codec", 0) < profile.get(
                "minimum_positive_groups_per_scoped_codec", 0
            ):
                errors.append(f"{partition} anchor coverage is below contract")
            if row.get("minimum_source_domains_per_setting_template", 0) < profile.get(
                "minimum_source_domains", 0
            ):
                errors.append(f"{partition} setting-domain coverage is below contract")
            if row.get(
                "minimum_positive_codec_families_per_nonidentity_pcm_transform"
            ) != len(scoped_codecs):
                errors.append(
                    f"{partition} transformed positive pairs must cover every codec"
                )
            if row.get(
                "minimum_setting_templates_per_history_decoder_per_compatible_codec",
                0,
            ) < 2:
                errors.append(
                    f"{partition} decoder coverage needs at least two templates per codec"
                )
            channel_per_template = row.get(
                "minimum_source_groups_per_channel_treatment_per_setting_template",
                0,
            )
            if (
                not isinstance(channel_per_template, int)
                or channel_per_template < 1
                or 2 * channel_per_template
                > row.get("minimum_source_groups_per_nonanchor_setting_template", 0)
            ):
                errors.append(
                    f"{partition} per-template channel coverage is infeasible"
                )
        else:
            if row.get("minimum_tier_a_negative_source_groups", 0) < profile.get(
                "minimum_tier_a_negative_partition_groups", 0
            ) or row.get("minimum_controlled_positive_source_groups", 0) < profile.get(
                "minimum_controlled_positive_source_groups", 0
            ):
                errors.append("external-transfer coverage is below contract")

    external = factors.get("external_transfer_encoder_boundary")
    if not isinstance(external, dict) or (
        external.get("state") != "source_identities_sealed_encoder_not_selected"
        or external.get("required_codec_family") != "mp3"
        or set(external.get("lineage_disjoint_from", []))
        != lineages["mechanism_development"]["mp3"]
        | lineages["encoder_transfer"]["mp3"]
    ):
        errors.append("external-transfer encoder boundary differs")

    storage = factors.get("construction_and_storage")
    if not isinstance(storage, dict) or (
        storage.get("maximum_parallel_workers") != 1
        or storage.get("minimum_free_space_reserve_bytes") != 15 * 1024**3
        or storage.get("source_archives_must_not_be_duplicated") is not True
    ):
        errors.append("construction/storage boundary differs")

    forbidden_keys = recursively_find_keys(
        factors, {"binary_sha256", "command", "command_sha256", "audio_sha256"}
    )
    if forbidden_keys:
        errors.append(
            f"factor freeze contains premature tool/audio bindings: {sorted(forbidden_keys)}"
        )
    serialized = json.dumps(factors, sort_keys=True)
    for private_path in ("/Users/", "Library/Application Support", "\\Users\\"):
        if private_path in serialized:
            errors.append("factor freeze contains a private machine path")
            break
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factors", type=Path, required=True)
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path("benchmarks/audio-integrity-v2/factorial-contract.json"),
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("benchmarks/audio-integrity-v2/inventory.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    factors = load_object(args.factors)
    contract = load_object(args.contract)
    inventory = load_object(args.inventory)
    repository_root = Path(__file__).resolve().parents[1]
    errors = validate(factors, contract, inventory, repository_root)
    if errors:
        print("factor-level validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("factor levels valid: source-bound, lineage-disjoint, paired, and pre-toolchain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
