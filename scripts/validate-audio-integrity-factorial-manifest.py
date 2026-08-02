#!/usr/bin/env python3
"""Validate a private factorial audio-integrity manifest without scoring it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from collections import defaultdict
from pathlib import Path


IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_AGGREGATE_KEYS = {
    "audio_sha256",
    "case_id",
    "partition_group",
    "relative_path",
    "source_group",
}


def load_object(path: Path) -> dict:
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


def write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise ValueError(f"refusing to replace existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def identifier(value: object) -> bool:
    return isinstance(value, str) and bool(IDENTIFIER.fullmatch(value))


def sha256(value: object) -> bool:
    return isinstance(value, str) and bool(SHA256.fullmatch(value))


def safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def index_objects(
    values: object,
    id_field: str,
    collection_name: str,
    errors: list[str],
) -> dict[str, dict]:
    if not isinstance(values, list):
        errors.append(f"{collection_name} must be an array")
        return {}
    output: dict[str, dict] = {}
    for offset, value in enumerate(values):
        if not isinstance(value, dict):
            errors.append(f"{collection_name}[{offset}] must be an object")
            continue
        object_id = value.get(id_field)
        if not identifier(object_id):
            errors.append(
                f"{collection_name}[{offset}].{id_field} must be an opaque identifier"
            )
            continue
        if object_id in output:
            errors.append(f"duplicate {id_field}: {object_id}")
            continue
        output[object_id] = value
    return output


def require_fields(
    value: dict,
    fields: object,
    description: str,
    errors: list[str],
) -> None:
    if not isinstance(fields, list):
        errors.append(f"contract fields for {description} must be an array")
        return
    missing = [field for field in fields if field not in value]
    if missing:
        errors.append(f"{description} missing fields: {', '.join(missing)}")


def validate_registry_hashes(
    objects: dict[str, dict],
    description: str,
    errors: list[str],
) -> None:
    for object_id, value in objects.items():
        if not sha256(value.get("binary_sha256")):
            errors.append(f"{description} {object_id} has invalid binary_sha256")


def add_partition_value(
    mapping: dict[str, set[str]], value: object, partition: object
) -> None:
    if isinstance(value, str) and isinstance(partition, str):
        mapping[value].add(partition)


def validate(
    contract: dict,
    manifest: dict,
    *,
    profile: str = "structural",
    contract_sha256: str | None = None,
    manifest_sha256: str | None = None,
) -> tuple[list[str], dict]:
    errors: list[str] = []
    factors = contract.get("factor_requirements")
    if not isinstance(factors, dict):
        factors = {}
        errors.append("contract factor_requirements must be an object")

    if contract.get("schema_version") != 1:
        errors.append("contract schema_version must be 1")
    if manifest.get("schema_version") != 2:
        errors.append("manifest schema_version must be 2")
    if manifest.get("contract_id") != contract.get("contract_id"):
        errors.append("manifest contract_id differs from the contract")
    if manifest.get("feature_version") != 0:
        errors.append("manifest feature_version must remain 0")
    if manifest.get("public_verdict_enabled") is not False:
        errors.append("public verdict must remain disabled")
    if manifest.get("scores_opened") is not False:
        errors.append("construction manifest must record scores_opened false")
    if manifest.get("existing_v1_holdouts_included") is not False:
        errors.append("existing v1 holdouts must remain excluded")

    allowed_partitions = set(contract.get("allowed_evidence_partitions", []))
    allowed_expectations = set(contract.get("allowed_expectations", []))
    allowed_histories = set(contract.get("allowed_history_classes", []))
    allowed_eligibility = set(
        contract.get("allowed_assessment_eligibility", [])
    )
    allowed_tiers = set(contract.get("allowed_provenance_tiers", []))
    eligible_current_codecs = set(contract.get("eligible_current_codecs", []))
    scoped_codecs = set(contract.get("scoped_codec_families", []))

    collections = index_objects(
        manifest.get("source_collections"),
        "source_collection_id",
        "source_collections",
        errors,
    )
    tools = index_objects(manifest.get("tools"), "tool_id", "tools", errors)
    encoders = index_objects(
        manifest.get("encoders"), "encoder_id", "encoders", errors
    )
    settings = index_objects(
        manifest.get("encoder_settings"),
        "setting_id",
        "encoder_settings",
        errors,
    )
    decoders = index_objects(
        manifest.get("decoders"), "decoder_id", "decoders", errors
    )
    transforms = index_objects(
        manifest.get("transforms"), "transform_id", "transforms", errors
    )
    recipes = index_objects(
        manifest.get("recipes"), "recipe_id", "recipes", errors
    )
    cases = index_objects(manifest.get("cases"), "case_id", "cases", errors)

    for collection_id, collection in collections.items():
        require_fields(
            collection,
            factors.get("source_collection_fields"),
            f"source collection {collection_id}",
            errors,
        )
        if collection.get("evidence_partition") not in allowed_partitions:
            errors.append(
                f"source collection {collection_id} has invalid evidence_partition"
            )
        if collection.get("provenance_tier") not in allowed_tiers:
            errors.append(
                f"source collection {collection_id} has invalid provenance_tier"
            )
        if not identifier(collection.get("source_lineage_id")):
            errors.append(
                f"source collection {collection_id} has invalid source_lineage_id"
            )
        if not sha256(collection.get("provenance_record_sha256")):
            errors.append(
                f"source collection {collection_id} has invalid provenance hash"
            )

    for tool_id, tool in tools.items():
        if not sha256(tool.get("binary_sha256")):
            errors.append(f"tool {tool_id} has invalid binary_sha256")

    for encoder_id, encoder in encoders.items():
        require_fields(
            encoder,
            factors.get("encoder_fields"),
            f"encoder {encoder_id}",
            errors,
        )
        if not identifier(encoder.get("lineage_id")):
            errors.append(f"encoder {encoder_id} has invalid lineage_id")
    validate_registry_hashes(encoders, "encoder", errors)

    for decoder_id, decoder in decoders.items():
        require_fields(
            decoder,
            factors.get("decoder_fields"),
            f"decoder {decoder_id}",
            errors,
        )
    validate_registry_hashes(decoders, "decoder", errors)

    for setting_id, setting in settings.items():
        require_fields(
            setting,
            factors.get("encoder_setting_fields"),
            f"encoder setting {setting_id}",
            errors,
        )
        encoder_id = setting.get("encoder_id")
        if encoder_id not in encoders:
            errors.append(f"encoder setting {setting_id} references unknown encoder")
        if setting.get("codec_family") not in scoped_codecs:
            errors.append(f"encoder setting {setting_id} has unscoped codec_family")
        if not isinstance(setting.get("bitrate_or_quality"), str):
            errors.append(
                f"encoder setting {setting_id} must name bitrate_or_quality"
            )
        if not isinstance(setting.get("sample_rate_hz"), int) or setting.get(
            "sample_rate_hz", 0
        ) <= 0:
            errors.append(f"encoder setting {setting_id} has invalid sample rate")
        lowpass = setting.get("encoder_lowpass")
        if not isinstance(lowpass, dict) or lowpass.get("mode") not in {
            "disabled",
            "encoder_default",
            "fixed",
            "unknown",
        }:
            errors.append(f"encoder setting {setting_id} has invalid lowpass")
        elif lowpass.get("mode") == "fixed" and (
            not isinstance(lowpass.get("hz"), (int, float))
            or lowpass["hz"] <= 0
        ):
            errors.append(f"encoder setting {setting_id} has invalid fixed lowpass")

    for transform_id, transform in transforms.items():
        require_fields(
            transform,
            factors.get("transform_fields"),
            f"transform {transform_id}",
            errors,
        )
        if transform.get("tool_id") not in tools:
            errors.append(f"transform {transform_id} references unknown tool")
        if not isinstance(transform.get("parameters"), dict):
            errors.append(f"transform {transform_id} parameters must be an object")

    for recipe_id, recipe in recipes.items():
        require_fields(
            recipe,
            factors.get("recipe_fields"),
            f"recipe {recipe_id}",
            errors,
        )
        if not sha256(recipe.get("command_sha256")):
            errors.append(f"recipe {recipe_id} has invalid command_sha256")
        tool_ids = recipe.get("tool_ids")
        if not isinstance(tool_ids, list) or not tool_ids:
            errors.append(f"recipe {recipe_id} tool_ids must be a non-empty array")
        elif any(tool_id not in tools for tool_id in tool_ids):
            errors.append(f"recipe {recipe_id} references unknown tool")

    source_partitions: dict[str, set[str]] = defaultdict(set)
    partition_partitions: dict[str, set[str]] = defaultdict(set)
    collection_partitions: dict[str, set[str]] = defaultdict(set)
    lineage_partitions: dict[str, set[str]] = defaultdict(set)
    encoder_lineages_by_partition: dict[str, set[str]] = defaultdict(set)

    required_case_fields = contract.get("required_case_fields")
    for case_id, case in cases.items():
        require_fields(case, required_case_fields, f"case {case_id}", errors)
        partition = case.get("evidence_partition")
        source_group = case.get("source_group")
        partition_group = case.get("partition_group")
        collection_id = case.get("source_collection_id")
        if partition not in allowed_partitions:
            errors.append(f"case {case_id} has invalid evidence_partition")
        if not identifier(source_group):
            errors.append(f"case {case_id} has invalid source_group")
        if not identifier(partition_group):
            errors.append(f"case {case_id} has invalid partition_group")
        if not safe_relative_path(case.get("relative_path")):
            errors.append(f"case {case_id} has unsafe relative_path")
        if not sha256(case.get("audio_sha256")):
            errors.append(f"case {case_id} has invalid audio_sha256")
        if case.get("expectation") not in allowed_expectations:
            errors.append(f"case {case_id} has invalid expectation")
        if case.get("history_class") not in allowed_histories:
            errors.append(f"case {case_id} has invalid history_class")
        if case.get("assessment_eligibility") not in allowed_eligibility:
            errors.append(f"case {case_id} has invalid assessment_eligibility")
        if case.get("provenance_tier") not in allowed_tiers:
            errors.append(f"case {case_id} has invalid provenance_tier")
        if not isinstance(case.get("sample_rate_hz"), int) or case.get(
            "sample_rate_hz", 0
        ) <= 0:
            errors.append(f"case {case_id} has invalid sample_rate_hz")
        if not isinstance(case.get("channel_count"), int) or not 1 <= case.get(
            "channel_count", 0
        ) <= 32:
            errors.append(f"case {case_id} has invalid channel_count")
        if case.get("analysis_decoder_id") not in decoders:
            errors.append(f"case {case_id} references unknown analysis decoder")
        transform_ids = case.get("post_transform_ids")
        if not isinstance(transform_ids, list) or any(
            transform_id not in transforms for transform_id in transform_ids
        ):
            errors.append(f"case {case_id} has invalid post_transform_ids")
        if (
            case.get("assessment_eligibility") == "eligible"
            and case.get("current_codec") not in eligible_current_codecs
        ):
            errors.append(f"case {case_id} has ineligible current codec")

        collection = collections.get(collection_id)
        if collection is None:
            errors.append(f"case {case_id} references unknown source collection")
        else:
            for field in (
                "evidence_partition",
                "source_domain",
                "provenance_tier",
            ):
                if case.get(field) != collection.get(field):
                    errors.append(
                        f"case {case_id} {field} differs from source collection"
                    )
            add_partition_value(
                lineage_partitions, collection.get("source_lineage_id"), partition
            )

        add_partition_value(source_partitions, source_group, partition)
        add_partition_value(partition_partitions, partition_group, partition)
        add_partition_value(collection_partitions, collection_id, partition)

        history = case.get("history_class")
        expectation = case.get("expectation")
        if expectation == "negative" and history not in {
            "pcm_reference",
            "pcm_hard_negative",
        }:
            errors.append(f"case {case_id} negative history is inconsistent")
        if expectation == "controlled_positive" and history not in {
            "controlled_lossy_history",
            "lossy_original_diagnostic",
        }:
            errors.append(f"case {case_id} positive history is inconsistent")
        if history == "lossy_original_diagnostic" and case.get(
            "assessment_eligibility"
        ) != "diagnostic_only":
            errors.append(f"case {case_id} lossy original must be diagnostic only")

        if history == "controlled_lossy_history":
            require_fields(
                case,
                factors.get("positive_case_fields"),
                f"case {case_id}",
                errors,
            )
            setting = settings.get(case.get("encoder_setting_id"))
            if setting is None:
                errors.append(f"case {case_id} references unknown encoder setting")
            else:
                encoder = encoders.get(setting.get("encoder_id"))
                if encoder is not None and isinstance(partition, str):
                    encoder_lineages_by_partition[partition].add(
                        encoder["lineage_id"]
                    )
            if case.get("history_decoder_id") not in decoders:
                errors.append(f"case {case_id} references unknown history decoder")
        elif history == "pcm_hard_negative":
            require_fields(
                case,
                factors.get("generated_negative_fields"),
                f"case {case_id}",
                errors,
            )
            if not identifier(case.get("hard_negative_class")):
                errors.append(f"case {case_id} must name hard_negative_class")
        elif history == "pcm_reference":
            if any(
                field in case
                for field in ("encoder_setting_id", "recipe_id", "reference_case_id")
            ):
                errors.append(f"case {case_id} reference has generated-case fields")

    for mapping, description in (
        (source_partitions, "source_group"),
        (partition_partitions, "partition_group"),
        (collection_partitions, "source_collection"),
        (lineage_partitions, "source_lineage"),
    ):
        for object_id, partitions in mapping.items():
            if len(partitions) > 1:
                errors.append(
                    f"{description} {object_id} crosses evidence partitions: "
                    f"{sorted(partitions)}"
                )

    for case_id, case in cases.items():
        reference_id = case.get("reference_case_id")
        if reference_id is not None:
            reference = cases.get(reference_id)
            if reference is None:
                errors.append(f"case {case_id} references unknown PCM reference")
            else:
                allowed_reference_histories = (
                    {"pcm_reference", "pcm_hard_negative"}
                    if case.get("history_class") == "controlled_lossy_history"
                    else {"pcm_reference"}
                )
                if (
                    reference.get("history_class") not in allowed_reference_histories
                    or reference.get("expectation") != "negative"
                ):
                    errors.append(f"case {case_id} reference is not an eligible negative")
                for field in (
                    "source_group",
                    "partition_group",
                    "source_collection_id",
                    "evidence_partition",
                ):
                    if case.get(field) != reference.get(field):
                        errors.append(
                            f"case {case_id} differs from reference on {field}"
                        )
                if case.get("history_class") == "controlled_lossy_history":
                    for field in (
                        "sample_rate_hz",
                        "channel_count",
                        "current_container",
                        "current_codec",
                        "post_transform_ids",
                    ):
                        if case.get(field) != reference.get(field):
                            errors.append(
                                f"case {case_id} differs from matched reference on {field}"
                            )
        recipe_id = case.get("recipe_id")
        if recipe_id is not None:
            recipe = recipes.get(recipe_id)
            if recipe is None:
                errors.append(f"case {case_id} references unknown recipe")
            else:
                if recipe.get("output_case_id") != case_id:
                    errors.append(f"case {case_id} recipe output differs")
                source = cases.get(recipe.get("source_case_id"))
                if source is None:
                    errors.append(f"case {case_id} recipe source is absent")
                else:
                    if source.get("history_class") != "pcm_reference":
                        errors.append(
                            f"case {case_id} recipe source is not pcm_reference"
                        )
                    for field in (
                        "source_group",
                        "partition_group",
                        "source_collection_id",
                        "evidence_partition",
                        "sample_rate_hz",
                    ):
                        if case.get(field) != source.get(field):
                            errors.append(
                                f"case {case_id} differs from recipe source on {field}"
                            )
                if (
                    case.get("history_class") == "pcm_hard_negative"
                    and recipe.get("source_case_id") != reference_id
                ):
                    errors.append(f"case {case_id} hard-negative recipe source differs")

    for recipe_id, recipe in recipes.items():
        if recipe.get("output_case_id") not in cases:
            errors.append(f"recipe {recipe_id} output case is absent")
        if recipe.get("source_case_id") not in cases:
            errors.append(f"recipe {recipe_id} source case is absent")

    development_lineages = encoder_lineages_by_partition.get(
        "mechanism_development", set()
    )
    transfer_lineages = encoder_lineages_by_partition.get("encoder_transfer", set())
    external_lineages = encoder_lineages_by_partition.get("external_transfer", set())
    if development_lineages & transfer_lineages:
        errors.append(
            "encoder_transfer reuses an encoder lineage from mechanism_development"
        )
    if external_lineages & (development_lineages | transfer_lineages):
        errors.append("external_transfer reuses a candidate-selection encoder lineage")

    summary = summarize(manifest, cases, settings, encoders)
    if profile != "structural":
        profiles = contract.get("freeze_profiles")
        if not isinstance(profiles, dict) or profile not in profiles:
            errors.append(f"unknown validation profile: {profile}")
        else:
            validate_profile(profile, profiles[profile], summary, scoped_codecs, errors)

    report = {
        "schema_version": 1,
        "state": "factorial_manifest_validation",
        "contract_id": contract.get("contract_id"),
        "validation_profile": profile,
        "valid": not errors,
        "public_verdict_enabled": False,
        "scores_opened": False,
        "existing_v1_holdouts_included": False,
        "inputs": {
            "contract_sha256": contract_sha256,
            "manifest_sha256": manifest_sha256,
        },
        "inventory": {
            "case_count": len(cases),
            "source_collection_count": len(collections),
            "encoder_count": len(encoders),
            "encoder_setting_count": len(settings),
            "decoder_count": len(decoders),
            "transform_count": len(transforms),
            "recipe_count": len(recipes),
        },
        "partition_summary": summary,
        "split_checks": {
            "source_group_single_partition": all(
                len(values) == 1 for values in source_partitions.values()
            ),
            "partition_group_single_partition": all(
                len(values) == 1 for values in partition_partitions.values()
            ),
            "source_collection_single_partition": all(
                len(values) == 1 for values in collection_partitions.values()
            ),
            "source_lineage_single_partition": all(
                len(values) == 1 for values in lineage_partitions.values()
            ),
            "encoder_transfer_lineage_disjoint": not bool(
                development_lineages & transfer_lineages
            ),
            "external_encoder_lineage_disjoint": not bool(
                external_lineages & (development_lineages | transfer_lineages)
            ),
        },
    }
    assert_path_free(report)
    return errors, report


def summarize(
    manifest: dict,
    cases: dict[str, dict],
    settings: dict[str, dict],
    encoders: dict[str, dict],
) -> dict:
    partitions: dict[str, list[dict]] = defaultdict(list)
    for case in cases.values():
        partition = case.get("evidence_partition")
        if isinstance(partition, str):
            partitions[partition].append(case)

    output = {}
    for partition, rows in sorted(partitions.items()):
        negative_rows = [row for row in rows if row.get("expectation") == "negative"]
        positive_rows = [
            row for row in rows if row.get("expectation") == "controlled_positive"
        ]
        hard_negative_groups: dict[str, set[str]] = defaultdict(set)
        positive_groups: dict[str, set[str]] = defaultdict(set)
        lineage_by_codec: dict[str, set[str]] = defaultdict(set)
        setting_by_codec: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            if row.get("history_class") == "pcm_hard_negative" and isinstance(
                row.get("hard_negative_class"), str
            ):
                hard_negative_groups[row["hard_negative_class"]].add(
                    row["source_group"]
                )
            setting = settings.get(row.get("encoder_setting_id"))
            if setting is not None:
                codec = setting["codec_family"]
                positive_groups[codec].add(row["source_group"])
                setting_by_codec[codec].add(setting["setting_id"])
                encoder = encoders.get(setting["encoder_id"])
                if encoder is not None:
                    lineage_by_codec[codec].add(encoder["lineage_id"])
        output[partition] = {
            "case_count": len(rows),
            "source_group_count": len({row.get("source_group") for row in rows}),
            "partition_group_count": len(
                {row.get("partition_group") for row in rows}
            ),
            "source_domain_count": len({row.get("source_domain") for row in rows}),
            "negative_case_count": len(negative_rows),
            "negative_source_group_count": len(
                {row.get("source_group") for row in negative_rows}
            ),
            "tier_a_negative_partition_group_count": len(
                {
                    row.get("partition_group")
                    for row in negative_rows
                    if row.get("provenance_tier") == "tier_a_confirmed_pcm"
                }
            ),
            "controlled_positive_case_count": len(positive_rows),
            "controlled_positive_source_group_count": len(
                {row.get("source_group") for row in positive_rows}
            ),
            "hard_negative_source_groups_by_class": {
                name: len(groups)
                for name, groups in sorted(hard_negative_groups.items())
            },
            "positive_source_groups_by_codec": {
                name: len(groups) for name, groups in sorted(positive_groups.items())
            },
            "encoder_lineage_count_by_codec": {
                name: len(values) for name, values in sorted(lineage_by_codec.items())
            },
            "encoder_setting_count_by_codec": {
                name: len(values) for name, values in sorted(setting_by_codec.items())
            },
        }
    return output


def validate_profile(
    profile_name: str,
    profile: object,
    summary: dict,
    scoped_codecs: set[str],
    errors: list[str],
) -> None:
    if not isinstance(profile, dict):
        errors.append(f"profile {profile_name} must be an object")
        return
    partition = profile.get("partition")
    values = summary.get(partition)
    if values is None:
        errors.append(f"profile {profile_name} partition is absent")
        return
    count_fields = (
        "source_groups",
        "partition_groups",
        "source_domains",
        "negative_source_groups",
        "tier_a_negative_partition_groups",
        "controlled_positive_source_groups",
    )
    for stem in count_fields:
        required = profile.get(f"minimum_{stem}")
        actual = values.get(f"{stem[:-1]}_count" if stem.endswith("s") else stem)
        if stem == "source_groups":
            actual = values["source_group_count"]
        elif stem == "partition_groups":
            actual = values["partition_group_count"]
        elif stem == "source_domains":
            actual = values["source_domain_count"]
        elif stem == "negative_source_groups":
            actual = values["negative_source_group_count"]
        elif stem == "tier_a_negative_partition_groups":
            actual = values["tier_a_negative_partition_group_count"]
        elif stem == "controlled_positive_source_groups":
            actual = values["controlled_positive_source_group_count"]
        if isinstance(required, int) and actual < required:
            errors.append(
                f"profile {profile_name} requires {required} {stem}, found {actual}"
            )

    minimum_hard_classes = profile.get("minimum_hard_negative_classes", 0)
    minimum_per_hard_class = profile.get(
        "minimum_groups_per_hard_negative_class", 0
    )
    hard_counts = values["hard_negative_source_groups_by_class"]
    qualifying_hard_classes = sum(
        count >= minimum_per_hard_class for count in hard_counts.values()
    )
    if qualifying_hard_classes < minimum_hard_classes:
        errors.append(
            f"profile {profile_name} requires {minimum_hard_classes} hard-negative "
            f"classes with at least {minimum_per_hard_class} groups, found "
            f"{qualifying_hard_classes}"
        )

    positive_counts = values["positive_source_groups_by_codec"]
    minimum_positive = profile.get("minimum_positive_groups_per_scoped_codec", 0)
    required_codecs = scoped_codecs if profile.get("require_all_scoped_codecs") else {
        codec for codec in positive_counts
    }
    for codec in sorted(required_codecs):
        if positive_counts.get(codec, 0) < minimum_positive:
            errors.append(
                f"profile {profile_name} requires {minimum_positive} positive groups "
                f"for {codec}, found {positive_counts.get(codec, 0)}"
            )

    minimum_lineages = profile.get("minimum_encoder_lineages", {})
    if isinstance(minimum_lineages, dict):
        for codec, minimum in sorted(minimum_lineages.items()):
            actual = values["encoder_lineage_count_by_codec"].get(codec, 0)
            if isinstance(minimum, int) and actual < minimum:
                errors.append(
                    f"profile {profile_name} requires {minimum} encoder lineages "
                    f"for {codec}, found {actual}"
                )

    minimum_settings = profile.get("minimum_settings_per_scoped_codec", 0)
    for codec in sorted(required_codecs):
        actual = values["encoder_setting_count_by_codec"].get(codec, 0)
        if isinstance(minimum_settings, int) and actual < minimum_settings:
            errors.append(
                f"profile {profile_name} requires {minimum_settings} settings for "
                f"{codec}, found {actual}"
            )


def assert_path_free(value: object, key: str | None = None) -> None:
    if key in FORBIDDEN_AGGREGATE_KEYS:
        raise ValueError(f"aggregate contains forbidden private key: {key}")
    if isinstance(value, dict):
        for child_key, child in value.items():
            assert_path_free(child, child_key)
    elif isinstance(value, list):
        for child in value:
            assert_path_free(child, key)
    elif isinstance(value, str) and value.startswith("/"):
        raise ValueError("aggregate contains an absolute path")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--profile", default="structural")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract_path = args.contract.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    try:
        errors, report = validate(
            load_object(contract_path),
            load_object(manifest_path),
            profile=args.profile,
            contract_sha256=sha256_file(contract_path),
            manifest_sha256=sha256_file(manifest_path),
        )
        if errors:
            raise ValueError("manifest validation failed:\n- " + "\n- ".join(errors))
        if args.output is not None:
            write_new(args.output.expanduser().resolve(), report)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    inventory = report["inventory"]
    print(
        f"manifest valid under {args.profile}: {inventory['case_count']} cases, "
        f"{inventory['source_collection_count']} source collections"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
