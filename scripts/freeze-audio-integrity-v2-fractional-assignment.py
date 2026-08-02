#!/usr/bin/env python3
"""Freeze the v2 source-blind fractional assignment and public evidence."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
RULES_ID = "lossytrace-v2-fractional-assignment-20260802-002"
RANKING_PREFIX = "lossytrace-v2-fractional-assignment-20260802\0"
PARTITIONS = ("mechanism_development", "encoder_transfer", "external_transfer")
OBSERVED_PARTITIONS = ("mechanism_development", "encoder_transfer")
CODECS = ("mp3", "aac_lc", "opus", "vorbis")
CHANNELS = ("mono", "stereo")
SAMPLE_RATES_HZ = (44100, 48000)
EXPECTED_GROUP_COUNTS = {
    "mechanism_development": 527,
    "encoder_transfer": 102,
    "external_transfer": 164,
}
NONANCHOR_QUOTAS = {"mechanism_development": 120, "encoder_transfer": 60}
TRANSFORM_QUOTAS = {
    "mechanism_development": 40,
    "encoder_transfer": 20,
    "external_transfer": 20,
}
MINIMUM_SETTING_DOMAINS = {"mechanism_development": 5, "encoder_transfer": 4}
MINIMUM_CHANNEL_PER_CODEC = {"mechanism_development": 60, "encoder_transfer": 30}
MINIMUM_CHANNEL_PER_TEMPLATE = {
    "mechanism_development": 30,
    "encoder_transfer": 15,
}
MINIMUM_DECODER_GROUPS = {"mechanism_development": 40, "encoder_transfer": 30}
EXTERNAL_RESERVE_COUNT = 100
MINIMUM_FREE_RESERVE_BYTES = 15 * 1024**3
ALLOWED_SOURCE_FIELDS = {
    "group_id",
    "evidence_partition",
    "source_collection_id",
    "source_domain",
    "provenance_tier",
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


def hash_text(*parts: str) -> str:
    value = (RANKING_PREFIX + "\0".join(parts)).encode()
    return hashlib.sha256(value).hexdigest()


def validate_rules(
    rules: dict[str, Any],
    source_allocation_path: Path,
    factor_path: Path,
    toolchain_manifest_path: Path,
    toolchain_result_path: Path,
    public_decoder_result_path: Path,
) -> None:
    if (
        rules.get("schema_version") != SCHEMA_VERSION
        or rules.get("assignment_rules_id") != RULES_ID
        or rules.get("state")
        != "fractional_assignment_rules_frozen_before_private_assignment"
        or rules.get("audio_generated") is not False
        or rules.get("waveform_content_inspected") is not False
        or rules.get("signal_statistics_used") is not False
        or rules.get("scores_opened") is not False
        or rules.get("selection_authorized") is not False
        or rules.get("fractional_assignment_generated") is not False
        or rules.get("public_state", {}).get("public_verdict_enabled") is not False
    ):
        raise ValueError("fractional assignment rules state differs")
    bindings = (
        (
            source_allocation_path,
            rules.get("source_allocation_binding", {}).get(
                "private_source_allocation_sha256"
            ),
            "source allocation",
        ),
        (factor_path, rules.get("factor_binding", {}).get("sha256"), "factor"),
        (
            toolchain_manifest_path,
            rules.get("toolchain_binding", {}).get("manifest_sha256"),
            "toolchain manifest",
        ),
        (
            toolchain_result_path,
            rules.get("toolchain_binding", {}).get("toolchain_result_sha256"),
            "toolchain result",
        ),
        (
            public_decoder_result_path,
            rules.get("toolchain_binding", {}).get("public_decoder_result_sha256"),
            "public decoder result",
        ),
    )
    for path, expected, label in bindings:
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"{label} binding differs")
    if set(rules.get("allowed_private_source_fields", [])) != ALLOWED_SOURCE_FIELDS:
        raise ValueError("allowed private source fields differ")
    if rules.get("deterministic_ranking", {}).get("prefix") != RANKING_PREFIX:
        raise ValueError("deterministic ranking prefix differs")
    generator = rules.get("generator_binding", {})
    if (
        generator.get("path")
        != "scripts/freeze-audio-integrity-v2-fractional-assignment.py"
        or generator.get("sha256") != sha256_file(Path(__file__).resolve())
    ):
        raise ValueError("fractional assignment generator binding differs")
    partition_rules = rules.get("partitions", {})
    for partition, count in EXPECTED_GROUP_COUNTS.items():
        if partition_rules.get(partition, {}).get("source_group_count") != count:
            raise ValueError(f"{partition} source count differs")
    if rules.get("storage_and_execution", {}).get("audio_generation_authorized") is not False:
        raise ValueError("assignment rules unexpectedly authorize audio")


def source_rows(allocation: dict[str, Any]) -> list[dict[str, str]]:
    if (
        allocation.get("schema_version") != 1
        or allocation.get("state") != "source_allocation_frozen_identity_only"
        or allocation.get("audio_generated") is not False
        or allocation.get("waveform_content_inspected") is not False
        or allocation.get("duration_used_for_selection") is not False
        or allocation.get("scores_opened") is not False
        or allocation.get("absolute_paths_recorded") is not False
    ):
        raise ValueError("private source allocation state differs")
    selected = allocation.get("selected")
    if not isinstance(selected, list) or len(selected) != sum(EXPECTED_GROUP_COUNTS.values()):
        raise ValueError("private source allocation count differs")
    rows = []
    seen = set()
    for raw in selected:
        if not isinstance(raw, dict):
            raise ValueError("source allocation row must be an object")
        row = {field: raw.get(field) for field in ALLOWED_SOURCE_FIELDS}
        if any(not isinstance(value, str) or not value for value in row.values()):
            raise ValueError("source allocation row lacks an allowed identity field")
        if row["evidence_partition"] not in PARTITIONS:
            raise ValueError("source allocation partition differs")
        if row["group_id"] in seen:
            raise ValueError("source allocation has a duplicate group")
        seen.add(row["group_id"])
        rows.append(row)
    counts = collections.Counter(row["evidence_partition"] for row in rows)
    if dict(counts) != EXPECTED_GROUP_COUNTS:
        raise ValueError("source allocation partition counts differ")
    return sorted(rows, key=lambda row: row["group_id"])


def group_rank(row: dict[str, str], purpose: str) -> tuple[str, str]:
    return (
        hash_text(
            purpose,
            row["evidence_partition"],
            row["source_domain"],
            row["group_id"],
        ),
        row["group_id"],
    )


def domain_balanced_select(
    rows: list[dict[str, str]], quota: int, purpose: str
) -> list[dict[str, str]]:
    if quota < 1 or quota > len(rows):
        raise ValueError("domain-balanced quota is infeasible")
    partition_set = {row["evidence_partition"] for row in rows}
    if len(partition_set) != 1:
        raise ValueError("domain-balanced selection requires one partition")
    partition = next(iter(partition_set))
    buckets: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for row in rows:
        buckets[row["source_domain"]].append(row)
    for domain_rows in buckets.values():
        domain_rows.sort(key=lambda row: group_rank(row, purpose))
    domains = sorted(
        buckets,
        key=lambda domain: (hash_text(purpose, partition, domain), domain),
    )
    selected = []
    offset = 0
    while len(selected) < quota:
        added = False
        for domain in domains:
            if offset < len(buckets[domain]):
                selected.append(buckets[domain][offset])
                added = True
                if len(selected) == quota:
                    break
        if not added:
            raise ValueError("domain-balanced selection exhausted candidates")
        offset += 1
    return selected


def cycle_levels(levels: list[Any], purpose: str, count: int) -> list[Any]:
    if not levels:
        raise ValueError("categorical cycle has no eligible levels")
    offset = int(hash_text("cycle-offset", purpose)[:16], 16) % len(levels)
    return [levels[(offset + index) % len(levels)] for index in range(count)]


def applicable_channels(setting: dict[str, Any]) -> list[str]:
    value = setting.get("channel_treatment_id")
    if value in CHANNELS:
        return [value]
    raise ValueError(f"expanded setting has invalid channel treatment: {value}")


def assignment_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(
        b"lossytrace-v2-assignment-cell-20260802\0" + canonical
    ).hexdigest()


class CellBuilder:
    def __init__(self, group_by_id: dict[str, dict[str, str]]) -> None:
        self.group_by_id = group_by_id
        self.references: dict[tuple[str, str, int, str, str], dict[str, Any]] = {}
        self.positives: dict[str, dict[str, Any]] = {}

    def ensure_reference(
        self,
        row: dict[str, str],
        channel: str,
        target_sample_rate_hz: int,
        transform_id: str,
        wrapper_id: str,
        required_for_role: str,
    ) -> str:
        key = (
            row["group_id"],
            channel,
            target_sample_rate_hz,
            transform_id,
            wrapper_id,
        )
        existing = self.references.get(key)
        if existing is not None:
            existing["_roles"].add(required_for_role)
            return existing["assignment_id"]
        payload = {
            "group_id": row["group_id"],
            "evidence_partition": row["evidence_partition"],
            "cell_type": "matched_pcm_reference",
            "expectation": "negative",
            "history_class": (
                "pcm_reference" if transform_id == "identity" else "pcm_hard_negative"
            ),
            "channel_treatment_id": channel,
            "target_sample_rate_hz": target_sample_rate_hz,
            "transform_id": transform_id,
            "wrapper_id": wrapper_id,
        }
        cell = {**payload, "assignment_id": assignment_id(payload), "_roles": {required_for_role}}
        self.references[key] = cell
        return cell["assignment_id"]

    def add_positive(
        self,
        row: dict[str, str],
        setting: dict[str, Any],
        decoder_id: str,
        transform_id: str,
        wrapper_id: str,
        role: str,
    ) -> None:
        channel = setting["channel_treatment_id"]
        target_sample_rate_hz = setting["expected_sample_rate_hz"]
        reference_id = self.ensure_reference(
            row,
            channel,
            target_sample_rate_hz,
            transform_id,
            wrapper_id,
            role,
        )
        payload = {
            "group_id": row["group_id"],
            "evidence_partition": row["evidence_partition"],
            "cell_type": "controlled_lossy_history",
            "assignment_role": role,
            "expectation": "controlled_positive",
            "history_class": "controlled_lossy_history",
            "codec_family": setting["codec_family"],
            "expanded_setting_id": setting["expanded_setting_id"],
            "encoder_id": setting["encoder_id"],
            "lineage_id": setting["lineage_id"],
            "history_decoder_id": decoder_id,
            "analysis_decoder_id": "canonical_lossless_pcm_decoder",
            "channel_treatment_id": channel,
            "target_sample_rate_hz": target_sample_rate_hz,
            "transform_id": transform_id,
            "wrapper_id": wrapper_id,
            "matched_reference_assignment_id": reference_id,
        }
        identity = assignment_id(payload)
        if identity in self.positives:
            raise ValueError("duplicate positive assignment")
        self.positives[identity] = {**payload, "assignment_id": identity}

    def finish(self) -> list[dict[str, Any]]:
        references = []
        for cell in self.references.values():
            value = dict(cell)
            value["assignment_roles"] = sorted(value.pop("_roles"))
            references.append(value)
        return sorted(
            [*references, *self.positives.values()],
            key=lambda row: row["assignment_id"],
        )


def decoder_ids_for_codec(
    decoder_bindings: list[dict[str, Any]], codec: str
) -> list[str]:
    return sorted(
        row["history_decoder_id"]
        for row in decoder_bindings
        if codec in row["codec_families"]
    )


def choose_wrappers(
    wrapper_ids: list[str], transform_id: str, purpose: str, count: int
) -> list[str]:
    eligible = (
        [wrapper_id for wrapper_id in wrapper_ids if wrapper_id != "flac16"]
        if transform_id == "lossless-wrapper-rewrite"
        else wrapper_ids
    )
    return cycle_levels(eligible, purpose, count)


def build_assignment(
    rules: dict[str, Any],
    allocation: dict[str, Any],
    factor: dict[str, Any],
    manifest: dict[str, Any],
    source_allocation_sha256: str,
    rules_sha256: str,
) -> dict[str, Any]:
    groups = source_rows(allocation)
    group_by_id = {row["group_id"]: row for row in groups}
    by_partition = {
        partition: [row for row in groups if row["evidence_partition"] == partition]
        for partition in PARTITIONS
    }
    settings = manifest.get("expanded_encoder_settings", [])
    by_partition_settings = {
        partition: [row for row in settings if row["evidence_partition"] == partition]
        for partition in OBSERVED_PARTITIONS
    }
    anchor_template_ids: dict[tuple[str, str], str] = {}
    for partition in OBSERVED_PARTITIONS:
        for codec in CODECS:
            anchor_templates = {
                row["template_id"]
                for row in by_partition_settings[partition]
                if row["codec_family"] == codec and row.get("anchor") is True
            }
            if len(anchor_templates) != 1:
                raise ValueError(f"{partition}/{codec} anchor count differs")
            anchor_template_ids[(partition, codec)] = next(iter(anchor_templates))
    wrapper_ids = [row["wrapper_id"] for row in manifest["wrapper_bindings"]]
    decoder_bindings = manifest["history_decoder_bindings"]
    transform_ids = [row["transform_id"] for row in factor["pcm_transform_levels"]]
    nonidentity_transforms = [value for value in transform_ids if value != "identity"]
    builder = CellBuilder(group_by_id)

    for partition, partition_groups in by_partition.items():
        ordered = domain_balanced_select(
            partition_groups, len(partition_groups), f"base-reference:{partition}"
        )
        channels = cycle_levels(list(CHANNELS), f"base-reference-channel:{partition}", len(ordered))
        sample_rates = cycle_levels(
            list(SAMPLE_RATES_HZ),
            f"base-reference-sample-rate:{partition}",
            len(ordered),
        )
        wrappers = cycle_levels(wrapper_ids, f"base-reference-wrapper:{partition}", len(ordered))
        for row, channel, sample_rate, wrapper_id in zip(
            ordered, channels, sample_rates, wrappers, strict=True
        ):
            builder.ensure_reference(
                row,
                channel,
                sample_rate,
                "identity",
                wrapper_id,
                "base_reference",
            )

    for partition in OBSERVED_PARTITIONS:
        partition_groups = by_partition[partition]
        for codec in CODECS:
            template_id = anchor_template_ids[(partition, codec)]
            expansions = [
                setting
                for setting in by_partition_settings[partition]
                if setting["template_id"] == template_id
            ]
            expansion_by_channel = {
                setting["channel_treatment_id"]: setting for setting in expansions
            }
            ordered = domain_balanced_select(
                partition_groups,
                len(partition_groups),
                f"anchor:{partition}:{codec}",
            )
            eligible_channels = sorted(expansion_by_channel)
            channels = cycle_levels(
                eligible_channels, f"anchor-channel:{partition}:{codec}", len(ordered)
            )
            decoders = cycle_levels(
                decoder_ids_for_codec(decoder_bindings, codec),
                f"anchor-decoder:{partition}:{codec}",
                len(ordered),
            )
            wrappers = choose_wrappers(
                wrapper_ids, "identity", f"anchor-wrapper:{partition}:{codec}", len(ordered)
            )
            for row, channel, decoder_id, wrapper_id in zip(
                ordered, channels, decoders, wrappers, strict=True
            ):
                builder.add_positive(
                    row,
                    expansion_by_channel[channel],
                    decoder_id,
                    "identity",
                    wrapper_id,
                    "anchor_identity",
                )

        nonanchors_by_template: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for setting in by_partition_settings[partition]:
            if setting.get("anchor") is not True:
                nonanchors_by_template[setting["template_id"]].append(setting)
        for template_id, expansions in sorted(nonanchors_by_template.items()):
            selected = domain_balanced_select(
                partition_groups,
                NONANCHOR_QUOTAS[partition],
                f"nonanchor:{partition}:{template_id}",
            )
            expansion_by_channel = {
                setting["channel_treatment_id"]: setting for setting in expansions
            }
            eligible_channels = sorted(expansion_by_channel)
            channels = cycle_levels(
                eligible_channels,
                f"nonanchor-channel:{partition}:{template_id}",
                len(selected),
            )
            codec = expansions[0]["codec_family"]
            decoders = cycle_levels(
                decoder_ids_for_codec(decoder_bindings, codec),
                f"nonanchor-decoder:{partition}:{template_id}",
                len(selected),
            )
            wrappers = choose_wrappers(
                wrapper_ids,
                "identity",
                f"nonanchor-wrapper:{partition}:{template_id}",
                len(selected),
            )
            for row, channel, decoder_id, wrapper_id in zip(
                selected, channels, decoders, wrappers, strict=True
            ):
                builder.add_positive(
                    row,
                    expansion_by_channel[channel],
                    decoder_id,
                    "identity",
                    wrapper_id,
                    "nonanchor_identity",
                )

    for partition in PARTITIONS:
        partition_groups = by_partition[partition]
        for transform_id in nonidentity_transforms:
            selected = domain_balanced_select(
                partition_groups,
                TRANSFORM_QUOTAS[partition],
                f"transform:{partition}:{transform_id}",
            )
            if partition == "external_transfer":
                channels = cycle_levels(
                    list(CHANNELS),
                    f"transform-negative-channel:{partition}:{transform_id}",
                    len(selected),
                )
                sample_rates = cycle_levels(
                    list(SAMPLE_RATES_HZ),
                    f"transform-negative-sample-rate:{partition}:{transform_id}",
                    len(selected),
                )
                wrappers = choose_wrappers(
                    wrapper_ids,
                    transform_id,
                    f"transform-negative-wrapper:{partition}:{transform_id}",
                    len(selected),
                )
                for row, channel, sample_rate, wrapper_id in zip(
                    selected, channels, sample_rates, wrappers, strict=True
                ):
                    builder.ensure_reference(
                        row,
                        channel,
                        sample_rate,
                        transform_id,
                        wrapper_id,
                        "external_transform_negative",
                    )
                continue
            for codec in CODECS:
                template_id = anchor_template_ids[(partition, codec)]
                expansions = [
                    setting
                    for setting in by_partition_settings[partition]
                    if setting["template_id"] == template_id
                ]
                expansion_by_channel = {
                    setting["channel_treatment_id"]: setting for setting in expansions
                }
                eligible_channels = sorted(expansion_by_channel)
                channels = cycle_levels(
                    eligible_channels,
                    f"transform-channel:{partition}:{transform_id}:{codec}",
                    len(selected),
                )
                decoders = cycle_levels(
                    decoder_ids_for_codec(decoder_bindings, codec),
                    f"transform-decoder:{partition}:{transform_id}:{codec}",
                    len(selected),
                )
                wrappers = choose_wrappers(
                    wrapper_ids,
                    transform_id,
                    f"transform-wrapper:{partition}:{transform_id}:{codec}",
                    len(selected),
                )
                for row, channel, decoder_id, wrapper_id in zip(
                    selected, channels, decoders, wrappers, strict=True
                ):
                    builder.add_positive(
                        row,
                        expansion_by_channel[channel],
                        decoder_id,
                        transform_id,
                        wrapper_id,
                        "transform_positive",
                    )

    external_selected = domain_balanced_select(
        by_partition["external_transfer"],
        EXTERNAL_RESERVE_COUNT,
        "external-positive-reserve",
    )
    external_channels = cycle_levels(
        list(CHANNELS), "external-positive-reserve-channel", len(external_selected)
    )
    external_wrappers = cycle_levels(
        wrapper_ids, "external-positive-reserve-wrapper", len(external_selected)
    )
    external_reserve = [
        {
            "group_id": row["group_id"],
            "evidence_partition": "external_transfer",
            "reservation_type": "future_controlled_mp3_positive",
            "channel_treatment_id": channel,
            "target_sample_rate_hz": 44100,
            "wrapper_id": wrapper_id,
            "codec_family": None,
            "expanded_setting_id": None,
            "history_decoder_id": None,
            "encoder_selection_deferred": True,
            "scores_opened": False,
        }
        for row, channel, wrapper_id in zip(
            external_selected, external_channels, external_wrappers, strict=True
        )
    ]

    result = {
        "schema_version": SCHEMA_VERSION,
        "assignment_id": RULES_ID,
        "state": "fractional_assignment_frozen_identity_and_categorical_only",
        "rules_sha256": rules_sha256,
        "source_allocation_sha256": source_allocation_sha256,
        "factor_freeze_id": factor["factor_freeze_id"],
        "toolchain_freeze_id": manifest["toolchain_freeze_id"],
        "audio_generated": False,
        "waveform_content_inspected": False,
        "signal_statistics_used": False,
        "scores_opened": False,
        "selection_authorized": False,
        "absolute_paths_recorded": False,
        "groups": groups,
        "cells": builder.finish(),
        "external_positive_reserve": sorted(
            external_reserve, key=lambda row: row["group_id"]
        ),
    }
    validate_assignment(result, factor, manifest)
    return result


def positive_cells(assignment: dict[str, Any], partition: str | None = None) -> list[dict[str, Any]]:
    return [
        row
        for row in assignment["cells"]
        if row["expectation"] == "controlled_positive"
        and (partition is None or row["evidence_partition"] == partition)
    ]


def negative_cells(assignment: dict[str, Any], partition: str | None = None) -> list[dict[str, Any]]:
    return [
        row
        for row in assignment["cells"]
        if row["expectation"] == "negative"
        and (partition is None or row["evidence_partition"] == partition)
    ]


def validate_assignment(
    assignment: dict[str, Any], factor: dict[str, Any], manifest: dict[str, Any]
) -> None:
    if (
        assignment.get("schema_version") != SCHEMA_VERSION
        or assignment.get("assignment_id") != RULES_ID
        or assignment.get("state")
        != "fractional_assignment_frozen_identity_and_categorical_only"
        or assignment.get("audio_generated") is not False
        or assignment.get("waveform_content_inspected") is not False
        or assignment.get("signal_statistics_used") is not False
        or assignment.get("scores_opened") is not False
        or assignment.get("selection_authorized") is not False
        or assignment.get("absolute_paths_recorded") is not False
    ):
        raise ValueError("private assignment state differs")
    groups = assignment.get("groups", [])
    group_by_id = {row.get("group_id"): row for row in groups}
    if len(group_by_id) != sum(EXPECTED_GROUP_COUNTS.values()) or None in group_by_id:
        raise ValueError("private assignment groups differ")
    counts = collections.Counter(row["evidence_partition"] for row in groups)
    if dict(counts) != EXPECTED_GROUP_COUNTS:
        raise ValueError("private assignment partition groups differ")
    if any(set(row) != ALLOWED_SOURCE_FIELDS for row in groups):
        raise ValueError("private assignment contains a forbidden source field")

    cells = assignment.get("cells", [])
    by_id = {row.get("assignment_id"): row for row in cells}
    if len(by_id) != len(cells) or None in by_id:
        raise ValueError("assignment cell identities differ")
    settings = {
        row["expanded_setting_id"]: row
        for row in manifest["expanded_encoder_settings"]
    }
    for cell in cells:
        group = group_by_id.get(cell.get("group_id"))
        if group is None or cell.get("evidence_partition") != group["evidence_partition"]:
            raise ValueError("assignment cell crosses a group partition")
        if cell.get("channel_treatment_id") not in CHANNELS:
            raise ValueError("assignment cell channel differs")
        if cell.get("target_sample_rate_hz") not in SAMPLE_RATES_HZ:
            raise ValueError("assignment cell target sample rate differs")
        if cell.get("transform_id") not in {
            row["transform_id"] for row in factor["pcm_transform_levels"]
        }:
            raise ValueError("assignment cell transform differs")
        if cell.get("wrapper_id") not in {
            row["wrapper_id"] for row in manifest["wrapper_bindings"]
        }:
            raise ValueError("assignment cell wrapper differs")
        if cell.get("expectation") == "controlled_positive":
            setting = settings.get(cell.get("expanded_setting_id"))
            if (
                setting is None
                or cell.get("target_sample_rate_hz")
                != setting.get("expected_sample_rate_hz")
            ):
                raise ValueError("positive target sample rate differs from setting")
            reference = by_id.get(cell.get("matched_reference_assignment_id"))
            if reference is None or any(
                reference.get(field) != cell.get(field)
                for field in (
                    "group_id",
                    "evidence_partition",
                    "channel_treatment_id",
                    "target_sample_rate_hz",
                    "transform_id",
                    "wrapper_id",
                )
            ):
                raise ValueError("positive lacks an exact matched reference")
        elif cell.get("expectation") != "negative":
            raise ValueError("assignment expectation differs")
    if positive_cells(assignment, "external_transfer"):
        raise ValueError("external positive was assigned before encoder freeze")

    for partition in OBSERVED_PARTITIONS:
        partition_group_ids = {
            row["group_id"] for row in groups if row["evidence_partition"] == partition
        }
        positives = positive_cells(assignment, partition)
        for codec in CODECS:
            anchor_groups = {
                row["group_id"]
                for row in positives
                if row["codec_family"] == codec and row["assignment_role"] == "anchor_identity"
            }
            if anchor_groups != partition_group_ids:
                raise ValueError(f"{partition}/{codec} anchor coverage differs")

        templates = {
            row["template_id"]
            for row in manifest["expanded_encoder_settings"]
            if row["evidence_partition"] == partition and row.get("anchor") is not True
        }
        for template_id in templates:
            rows = [
                row
                for row in positives
                if row["assignment_role"] == "nonanchor_identity"
                and settings[row["expanded_setting_id"]]["template_id"] == template_id
            ]
            group_ids = {row["group_id"] for row in rows}
            domains = {group_by_id[group_id]["source_domain"] for group_id in group_ids}
            if len(group_ids) != NONANCHOR_QUOTAS[partition]:
                raise ValueError(f"{partition}/{template_id} nonanchor quota differs")
            if len(domains) < MINIMUM_SETTING_DOMAINS[partition]:
                raise ValueError(f"{partition}/{template_id} domain coverage differs")
            applicable = {
                row["channel_treatment_id"]
                for row in manifest["expanded_encoder_settings"]
                if row["evidence_partition"] == partition and row["template_id"] == template_id
            }
            for channel in applicable:
                channel_groups = {row["group_id"] for row in rows if row["channel_treatment_id"] == channel}
                if len(channel_groups) < MINIMUM_CHANNEL_PER_TEMPLATE[partition]:
                    raise ValueError(f"{partition}/{template_id}/{channel} coverage differs")

        for codec in CODECS:
            applicable = {
                setting["channel_treatment_id"]
                for setting in manifest["expanded_encoder_settings"]
                if setting["evidence_partition"] == partition
                and setting["codec_family"] == codec
            }
            for channel in applicable:
                channel_groups = {
                    row["group_id"]
                    for row in positives
                    if row["codec_family"] == codec
                    and row["channel_treatment_id"] == channel
                }
                if len(channel_groups) < MINIMUM_CHANNEL_PER_CODEC[partition]:
                    raise ValueError(f"{partition}/{codec}/{channel} coverage differs")
            if partition == "encoder_transfer" and codec == "vorbis" and any(
                row["channel_treatment_id"] == "mono"
                for row in positives
                if row["codec_family"] == codec
            ):
                raise ValueError("mono Vorbis encoder transfer is forbidden")

        for transform_id in (
            row["transform_id"]
            for row in factor["pcm_transform_levels"]
            if row["transform_id"] != "identity"
        ):
            negatives = {
                row["group_id"]
                for row in negative_cells(assignment, partition)
                if row["transform_id"] == transform_id
            }
            if len(negatives) != TRANSFORM_QUOTAS[partition]:
                raise ValueError(f"{partition}/{transform_id} negative coverage differs")
            for sample_rate in SAMPLE_RATES_HZ:
                rate_groups = {
                    row["group_id"]
                    for row in negative_cells(assignment, partition)
                    if row["transform_id"] == transform_id
                    and row["target_sample_rate_hz"] == sample_rate
                }
                if len(rate_groups) != TRANSFORM_QUOTAS[partition]:
                    raise ValueError(
                        f"{partition}/{transform_id}/{sample_rate} "
                        "matched sample-rate coverage differs"
                    )
            for codec in CODECS:
                positive_groups = {
                    row["group_id"]
                    for row in positives
                    if row["assignment_role"] == "transform_positive"
                    and row["transform_id"] == transform_id
                    and row["codec_family"] == codec
                }
                if len(positive_groups) != TRANSFORM_QUOTAS[partition]:
                    raise ValueError(f"{partition}/{transform_id}/{codec} positive coverage differs")

        for decoder in manifest["history_decoder_bindings"]:
            decoder_id = decoder["history_decoder_id"]
            for codec in decoder["codec_families"]:
                rows = [
                    row
                    for row in positives
                    if row["history_decoder_id"] == decoder_id
                    and row["codec_family"] == codec
                ]
                group_count = len({row["group_id"] for row in rows})
                template_count = len(
                    {settings[row["expanded_setting_id"]]["template_id"] for row in rows}
                )
                if group_count < MINIMUM_DECODER_GROUPS[partition] or template_count < 2:
                    raise ValueError(f"{partition}/{decoder_id}/{codec} decoder coverage differs")

        for wrapper_id in ("flac16", "wav16", "aiff16"):
            if not any(row["wrapper_id"] == wrapper_id for row in positives) or not any(
                row["wrapper_id"] == wrapper_id for row in negative_cells(assignment, partition)
            ):
                raise ValueError(f"{partition}/{wrapper_id} expectation coverage differs")

    external_negatives = negative_cells(assignment, "external_transfer")
    for transform_id in (
        row["transform_id"]
        for row in factor["pcm_transform_levels"]
        if row["transform_id"] != "identity"
    ):
        group_count = len(
            {
                row["group_id"]
                for row in external_negatives
                if row["transform_id"] == transform_id
            }
        )
        if group_count != TRANSFORM_QUOTAS["external_transfer"]:
            raise ValueError(f"external/{transform_id} coverage differs")
        for sample_rate in SAMPLE_RATES_HZ:
            rate_group_count = len(
                {
                    row["group_id"]
                    for row in external_negatives
                    if row["transform_id"] == transform_id
                    and row["target_sample_rate_hz"] == sample_rate
                }
            )
            if rate_group_count != TRANSFORM_QUOTAS["external_transfer"] // 2:
                raise ValueError(
                    f"external/{transform_id}/{sample_rate} coverage differs"
                )
    reserve = assignment.get("external_positive_reserve", [])
    if (
        len(reserve) != EXTERNAL_RESERVE_COUNT
        or len({row.get("group_id") for row in reserve}) != EXTERNAL_RESERVE_COUNT
        or any(
            row.get("evidence_partition") != "external_transfer"
            or row.get("target_sample_rate_hz") != 44100
            or row.get("codec_family") is not None
            or row.get("expanded_setting_id") is not None
            or row.get("history_decoder_id") is not None
            or row.get("encoder_selection_deferred") is not True
            or row.get("scores_opened") is not False
            for row in reserve
        )
    ):
        raise ValueError("external positive reserve differs")
    for group_id in group_by_id:
        if not any(
            row["group_id"] == group_id and row["transform_id"] == "identity"
            for row in negative_cells(assignment)
        ):
            raise ValueError("a source group lacks an identity reference")
    serialized = json.dumps(assignment, sort_keys=True)
    for forbidden in (
        '"locator"',
        '"member_id"',
        '"input_artifact_id"',
        '"audio_sha256"',
        '"duration"',
        '"score"',
        "/Users/",
        "\\Users\\",
    ):
        if forbidden in serialized:
            raise ValueError(f"private assignment contains forbidden value: {forbidden}")


def count_rows(counter: collections.Counter[tuple[Any, ...]], fields: list[str]) -> list[dict[str, Any]]:
    return [
        {**dict(zip(fields, key, strict=True)), "count": count}
        for key, count in sorted(counter.items(), key=lambda item: tuple(str(value) for value in item[0]))
    ]


def public_aggregate(
    assignment: dict[str, Any],
    assignment_sha256: str,
    rules_path: Path,
    factor: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    groups = assignment["groups"]
    group_by_id = {row["group_id"]: row for row in groups}
    cells = assignment["cells"]
    group_counts = collections.Counter(
        (row["evidence_partition"], row["source_domain"], row["provenance_tier"])
        for row in groups
    )
    cell_counts = collections.Counter(
        (
            row["evidence_partition"],
            row["expectation"],
            row["history_class"],
            row["channel_treatment_id"],
            row["target_sample_rate_hz"],
            row["transform_id"],
            row["wrapper_id"],
        )
        for row in cells
    )
    codec_counts = collections.Counter(
        (row["evidence_partition"], row["assignment_role"], row["codec_family"])
        for row in positive_cells(assignment)
    )
    settings = {row["expanded_setting_id"]: row for row in manifest["expanded_encoder_settings"]}
    setting_coverage = []
    for partition in OBSERVED_PARTITIONS:
        positives = positive_cells(assignment, partition)
        template_ids = sorted(
            {
                setting["template_id"]
                for setting in manifest["expanded_encoder_settings"]
                if setting["evidence_partition"] == partition
            }
        )
        for template_id in template_ids:
            rows = [
                row
                for row in positives
                if settings[row["expanded_setting_id"]]["template_id"] == template_id
                and row["transform_id"] == "identity"
            ]
            setting_coverage.append(
                {
                    "evidence_partition": partition,
                    "template_id": template_id,
                    "anchor": settings[rows[0]["expanded_setting_id"]].get("anchor", False)
                    if rows
                    else False,
                    "group_count": len({row["group_id"] for row in rows}),
                    "domain_count": len(
                        {group_by_id[row["group_id"]]["source_domain"] for row in rows}
                    ),
                    "channel_group_counts": {
                        channel: len(
                            {
                                row["group_id"]
                                for row in rows
                                if row["channel_treatment_id"] == channel
                            }
                        )
                        for channel in CHANNELS
                        if any(row["channel_treatment_id"] == channel for row in rows)
                    },
                }
            )
    transform_coverage = []
    for partition in PARTITIONS:
        for transform_id in (
            row["transform_id"]
            for row in factor["pcm_transform_levels"]
            if row["transform_id"] != "identity"
        ):
            transform_coverage.append(
                {
                    "evidence_partition": partition,
                    "transform_id": transform_id,
                    "negative_group_count": len(
                        {
                            row["group_id"]
                            for row in negative_cells(assignment, partition)
                            if row["transform_id"] == transform_id
                        }
                    ),
                    "positive_group_counts_by_codec": {
                        codec: len(
                            {
                                row["group_id"]
                                for row in positive_cells(assignment, partition)
                                if row["transform_id"] == transform_id
                                and row["codec_family"] == codec
                            }
                        )
                        for codec in CODECS
                        if partition in OBSERVED_PARTITIONS
                    },
                }
            )
    decoder_coverage = []
    for partition in OBSERVED_PARTITIONS:
        for decoder in manifest["history_decoder_bindings"]:
            for codec in decoder["codec_families"]:
                rows = [
                    row
                    for row in positive_cells(assignment, partition)
                    if row["history_decoder_id"] == decoder["history_decoder_id"]
                    and row["codec_family"] == codec
                ]
                decoder_coverage.append(
                    {
                        "evidence_partition": partition,
                        "history_decoder_id": decoder["history_decoder_id"],
                        "codec_family": codec,
                        "group_count": len({row["group_id"] for row in rows}),
                        "template_count": len(
                            {settings[row["expanded_setting_id"]]["template_id"] for row in rows}
                        ),
                    }
                )
    return {
        "schema_version": SCHEMA_VERSION,
        "assignment_id": RULES_ID,
        "state": "fractional_assignment_path_free_run_evidence",
        "rules_binding": {
            "path": "benchmarks/audio-integrity-v2/fractional-assignment-rules.json",
            "sha256": sha256_file(rules_path),
        },
        "source_allocation_sha256": assignment["source_allocation_sha256"],
        "private_assignment_sha256": assignment_sha256,
        "factor_freeze_id": factor["factor_freeze_id"],
        "toolchain_freeze_id": manifest["toolchain_freeze_id"],
        "audio_generated": False,
        "waveform_content_inspected": False,
        "signal_statistics_used": False,
        "scores_opened": False,
        "selection_authorized": False,
        "paths_redacted": True,
        "private_ids_included": False,
        "group_counts": count_rows(
            group_counts,
            ["evidence_partition", "source_domain", "provenance_tier"],
        ),
        "cell_counts": count_rows(
            cell_counts,
            [
                "evidence_partition",
                "expectation",
                "history_class",
                "channel_treatment_id",
                "target_sample_rate_hz",
                "transform_id",
                "wrapper_id",
            ],
        ),
        "positive_codec_counts": count_rows(
            codec_counts,
            ["evidence_partition", "assignment_role", "codec_family"],
        ),
        "setting_coverage": setting_coverage,
        "transform_coverage": transform_coverage,
        "decoder_coverage": decoder_coverage,
        "external_positive_reserve": {
            "group_count": len(assignment["external_positive_reserve"]),
            "encoder_selection_deferred": True,
            "scores_opened": False,
        },
        "summary": {
            "group_count": len(groups),
            "cell_count": len(cells),
            "negative_cell_count": len(negative_cells(assignment)),
            "positive_cell_count": len(positive_cells(assignment)),
            "matched_positive_count": len(positive_cells(assignment)),
            "unmatched_positive_count": 0,
            "external_reserved_group_count": len(assignment["external_positive_reserve"]),
            "all_coverage_checks_passed": True,
        },
        "reproducibility": {
            "complete_replays_required": 2,
            "complete_replays_observed": 1,
            "byte_identical": None,
        },
    }


def assert_public_path_free(aggregate: dict[str, Any]) -> None:
    serialized = json.dumps(aggregate, sort_keys=True)
    forbidden_keys = {
        "audio_sha256",
        "case_id",
        "group_id",
        "partition_group",
        "relative_path",
        "source_group",
    }

    def keys(value: Any) -> set[str]:
        found = set()
        if isinstance(value, dict):
            found.update(value)
            for child in value.values():
                found.update(keys(child))
        elif isinstance(value, list):
            for child in value:
                found.update(keys(child))
        return found

    if keys(aggregate) & forbidden_keys:
        raise ValueError("public aggregate contains a forbidden private key")
    if any(token in serialized for token in ("/Users/", "Library/Application Support", "\\Users\\")):
        raise ValueError("public aggregate contains a private path")


def attest(
    private_paths: list[Path], aggregate_paths: list[Path], rules_path: Path
) -> dict[str, Any]:
    if len(private_paths) != 2 or len(aggregate_paths) != 2:
        raise ValueError("attestation requires exactly two private and public runs")
    if private_paths[0].read_bytes() != private_paths[1].read_bytes():
        raise ValueError("private assignments differ across complete replays")
    if aggregate_paths[0].read_bytes() != aggregate_paths[1].read_bytes():
        raise ValueError("run aggregates differ across complete replays")
    aggregate = load_object(aggregate_paths[0])
    if aggregate.get("state") != "fractional_assignment_path_free_run_evidence":
        raise ValueError("run aggregate state differs")
    if aggregate.get("rules_binding", {}).get("sha256") != sha256_file(rules_path):
        raise ValueError("run aggregate rules binding differs")
    if aggregate.get("private_assignment_sha256") != sha256_file(private_paths[0]):
        raise ValueError("run aggregate private binding differs")
    final = dict(aggregate)
    final["state"] = "fractional_assignment_path_free_evidence"
    final["reproducibility"] = {
        "complete_replays_required": 2,
        "complete_replays_observed": 2,
        "private_assignments_byte_identical": True,
        "run_aggregates_byte_identical": True,
        "private_assignment_sha256": sha256_file(private_paths[0]),
        "run_aggregate_sha256": sha256_file(aggregate_paths[0]),
        "rules_sha256": sha256_file(rules_path),
    }
    assert_public_path_free(final)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    assign = subparsers.add_parser("assign")
    assign.add_argument("--rules", required=True, type=Path)
    assign.add_argument("--source-allocation", required=True, type=Path)
    assign.add_argument("--factor", required=True, type=Path)
    assign.add_argument("--toolchain-manifest", required=True, type=Path)
    assign.add_argument("--toolchain-result", required=True, type=Path)
    assign.add_argument("--public-decoder-result", required=True, type=Path)
    assign.add_argument("--output-private", required=True, type=Path)
    assign.add_argument("--output-run-aggregate", required=True, type=Path)
    attest_parser = subparsers.add_parser("attest")
    attest_parser.add_argument("--rules", required=True, type=Path)
    attest_parser.add_argument("--private", required=True, type=Path, action="append")
    attest_parser.add_argument("--run-aggregate", required=True, type=Path, action="append")
    attest_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "attest":
        result = attest(
            [path.expanduser().resolve() for path in args.private],
            [path.expanduser().resolve() for path in args.run_aggregate],
            args.rules.expanduser().resolve(),
        )
        write_json_atomic(args.output.expanduser().resolve(), result)
        print("attested two byte-identical fractional assignments")
        return 0

    rules_path = args.rules.expanduser().resolve()
    source_path = args.source_allocation.expanduser().resolve()
    factor_path = args.factor.expanduser().resolve()
    manifest_path = args.toolchain_manifest.expanduser().resolve()
    toolchain_result_path = args.toolchain_result.expanduser().resolve()
    decoder_result_path = args.public_decoder_result.expanduser().resolve()
    rules = load_object(rules_path)
    if shutil.disk_usage(Path(__file__).resolve().parents[1]).free < MINIMUM_FREE_RESERVE_BYTES:
        raise ValueError("free space is below the frozen 15 GiB reserve")
    validate_rules(
        rules,
        source_path,
        factor_path,
        manifest_path,
        toolchain_result_path,
        decoder_result_path,
    )
    factor = load_object(factor_path)
    manifest = load_object(manifest_path)
    assignment = build_assignment(
        rules,
        load_object(source_path),
        factor,
        manifest,
        sha256_file(source_path),
        sha256_file(rules_path),
    )
    private_output = args.output_private.expanduser().resolve()
    write_json_atomic(private_output, assignment)
    aggregate = public_aggregate(
        assignment,
        sha256_file(private_output),
        rules_path,
        factor,
        manifest,
    )
    assert_public_path_free(aggregate)
    write_json_atomic(args.output_run_aggregate.expanduser().resolve(), aggregate)
    print(
        f"assigned {aggregate['summary']['group_count']} groups to "
        f"{aggregate['summary']['cell_count']} cells without audio or scores"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
