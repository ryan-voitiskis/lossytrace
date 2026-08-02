#!/usr/bin/env python3
"""Validate the path-free v2 source and toolchain inventory."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


SHA256 = re.compile(r"^[0-9a-f]{64}$")
PROVIDER_CHECKSUM = re.compile(r"^(md5:[0-9a-f]{32}|sha256:[0-9a-f]{64})$")
PARTITIONS = {"mechanism_development", "encoder_transfer", "external_transfer"}
CODECS = {"mp3", "aac_lc", "opus", "vorbis"}
MIN_ENCODER_LINEAGES = {
    "mechanism_development": {"mp3": 2, "aac_lc": 2, "opus": 1, "vorbis": 1},
    "encoder_transfer": {"mp3": 1, "aac_lc": 1, "opus": 1, "vorbis": 1},
}
MIN_SOURCE_PARTITIONS = {
    "mechanism_development": 150,
    "encoder_transfer": 100,
    "external_transfer": 150,
}
MIN_SOURCE_DOMAINS = {
    "mechanism_development": 5,
    "encoder_transfer": 4,
    "external_transfer": 3,
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("inventory root must be an object")
    return value


def unique_ids(rows: Any, field: str, label: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        errors.append(f"{label} must be a list")
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        value = row.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{label}[{index}].{field} must be a nonempty string")
        elif value in indexed:
            errors.append(f"duplicate {label} {field}: {value}")
        else:
            indexed[value] = row
    return indexed


def validate(inventory: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if inventory.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if inventory.get("state") != "inventory_only_not_frozen":
        errors.append("state must remain inventory_only_not_frozen")
    for field in ("audio_generated", "scores_opened", "selection_authorized"):
        if inventory.get(field) is not False:
            errors.append(f"{field} must be false")

    tools = unique_ids(inventory.get("installed_tools"), "tool_id", "installed_tools", errors)
    for tool_id, tool in tools.items():
        if not SHA256.fullmatch(str(tool.get("binary_sha256", ""))):
            errors.append(f"installed tool {tool_id} has invalid binary_sha256")
        components = tool.get("linked_component_hashes")
        if not isinstance(components, dict):
            errors.append(f"installed tool {tool_id} linked_component_hashes must be an object")
        else:
            for name, digest in components.items():
                if not isinstance(name, str) or not SHA256.fullmatch(str(digest)):
                    errors.append(f"installed tool {tool_id} has invalid component hash")

    encoders = unique_ids(inventory.get("encoder_candidates"), "encoder_id", "encoder_candidates", errors)
    lineages: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for encoder_id, encoder in encoders.items():
        codec = encoder.get("codec_family")
        partition = encoder.get("recommended_partition")
        lineage = encoder.get("lineage_id")
        if codec not in CODECS:
            errors.append(f"encoder {encoder_id} has invalid codec_family")
        if partition not in {"mechanism_development", "encoder_transfer"}:
            errors.append(f"encoder {encoder_id} has invalid recommended_partition")
        if not isinstance(lineage, str) or not lineage:
            errors.append(f"encoder {encoder_id} has invalid lineage_id")
        if codec in CODECS and partition in PARTITIONS and isinstance(lineage, str):
            lineages[partition][codec].add(lineage)

    for partition, required in MIN_ENCODER_LINEAGES.items():
        for codec, minimum in required.items():
            actual = len(lineages[partition][codec])
            if actual < minimum:
                errors.append(
                    f"{partition} needs {minimum} {codec} lineages, found {actual}"
                )
    for codec in CODECS:
        overlap = lineages["mechanism_development"][codec] & lineages["encoder_transfer"][codec]
        if overlap:
            errors.append(f"{codec} development/transfer lineages overlap: {sorted(overlap)}")

    unique_ids(inventory.get("decoder_candidates"), "decoder_id", "decoder_candidates", errors)
    sources = unique_ids(inventory.get("source_candidates"), "source_id", "source_candidates", errors)
    allocated: dict[str, set[str]] = defaultdict(set)
    planned_source_archive_bytes = 0
    for source_id, source in sources.items():
        partition = source.get("recommended_partition")
        if partition not in PARTITIONS:
            errors.append(f"source {source_id} has invalid recommended_partition")
            continue
        allocated[partition].add(source_id)
        groups = source.get("conservative_partition_groups")
        if not isinstance(groups, int) or isinstance(groups, bool) or groups < 1:
            errors.append(f"source {source_id} has invalid conservative_partition_groups")
        domains = source.get("source_domains")
        if not isinstance(domains, list) or not domains or not all(isinstance(v, str) and v for v in domains):
            errors.append(f"source {source_id} has invalid source_domains")
        artifacts: list[Any] = []
        if source.get("artifact") is not None:
            artifacts.append(source.get("artifact"))
        if source.get("artifacts") is not None:
            if not isinstance(source.get("artifacts"), list):
                errors.append(f"source {source_id} artifacts must be a list")
            else:
                artifacts.extend(source["artifacts"])
        for artifact_index, artifact in enumerate(artifacts):
            label = f"source {source_id} artifact {artifact_index}"
            if not isinstance(artifact, dict):
                errors.append(f"{label} must be an object")
                continue
            if not isinstance(artifact.get("filename"), str) or not artifact["filename"]:
                errors.append(f"{label} has invalid filename")
            byte_count = artifact.get("bytes")
            if not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count < 1:
                errors.append(f"{label} has invalid byte count")
            else:
                planned_source_archive_bytes += byte_count
            if not PROVIDER_CHECKSUM.fullmatch(str(artifact.get("provider_checksum", ""))):
                errors.append(f"{label} has invalid provider checksum")

    if inventory.get("planned_source_archive_bytes") != planned_source_archive_bytes:
        errors.append("planned_source_archive_bytes differs from source artifacts")
    reserve = inventory.get("minimum_free_space_reserve_bytes")
    if not isinstance(reserve, int) or isinstance(reserve, bool) or reserve < 1:
        errors.append("minimum_free_space_reserve_bytes must be a positive integer")

    summary = inventory.get("projected_partition_summary")
    if not isinstance(summary, dict):
        errors.append("projected_partition_summary must be an object")
        return errors
    for partition in PARTITIONS:
        row = summary.get(partition)
        if not isinstance(row, dict):
            errors.append(f"missing projected summary for {partition}")
            continue
        source_ids = row.get("source_ids")
        if not isinstance(source_ids, list) or set(source_ids) != allocated[partition]:
            errors.append(f"{partition} projected source_ids differ from source candidates")
            continue
        groups = sum(sources[source_id]["conservative_partition_groups"] for source_id in source_ids)
        domains = {
            domain
            for source_id in source_ids
            for domain in sources[source_id]["source_domains"]
        }
        if row.get("conservative_partition_groups") != groups:
            errors.append(f"{partition} projected partition count differs")
        if row.get("source_domain_count") != len(domains):
            errors.append(f"{partition} projected source-domain count differs")
        if groups < MIN_SOURCE_PARTITIONS[partition]:
            errors.append(f"{partition} projects only {groups} partition groups")
        if len(domains) < MIN_SOURCE_DOMAINS[partition]:
            errors.append(f"{partition} projects only {len(domains)} source domains")

    source_partitions: dict[str, set[str]] = defaultdict(set)
    for partition, source_ids in allocated.items():
        for source_id in source_ids:
            source_partitions[source_id].add(partition)
    for source_id, partitions in source_partitions.items():
        if len(partitions) != 1:
            errors.append(f"source {source_id} spans partitions")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    args = parser.parse_args()
    errors = validate(load_json(args.inventory))
    if errors:
        print("inventory validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("inventory valid: tool lineages and projected source partitions are disjoint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
