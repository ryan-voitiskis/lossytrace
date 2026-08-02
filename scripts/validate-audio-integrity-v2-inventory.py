#!/usr/bin/env python3
"""Validate the path-free v2 source and toolchain inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


SHA256 = re.compile(r"^[0-9a-f]{64}$")
PROVIDER_CHECKSUM = re.compile(r"^(md5:[0-9a-f]{32}|sha256:[0-9a-f]{64})$")
STRONG_ETAG = re.compile(r'^"[^"\r\n]+"$')
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def has_valid_acquired_remote_binding(artifact: dict[str, Any]) -> bool:
    provider_identity = artifact.get("provider_identity")
    return (
        isinstance(artifact.get("url"), str)
        and artifact["url"].startswith("https://")
        and SHA256.fullmatch(str(artifact.get("local_sha256", ""))) is not None
        and isinstance(provider_identity, dict)
        and provider_identity.get("method")
        == "https_strong_etag_content_length_last_modified"
        and STRONG_ETAG.fullmatch(str(provider_identity.get("etag", ""))) is not None
        and isinstance(provider_identity.get("last_modified"), str)
        and bool(provider_identity["last_modified"])
    )


def validate(inventory: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if inventory.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if inventory.get("state") != "inventory_only_not_frozen":
        errors.append("state must remain inventory_only_not_frozen")
    for field in ("audio_generated", "scores_opened", "selection_authorized"):
        if inventory.get(field) is not False:
            errors.append(f"{field} must be false")
    if inventory.get("synthetic_probe_audio_generated") is not True:
        errors.append("synthetic_probe_audio_generated must be true after toolchain probing")

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
            provider_checksum = artifact.get("provider_checksum")
            if provider_checksum is not None:
                if not PROVIDER_CHECKSUM.fullmatch(str(provider_checksum)):
                    errors.append(f"{label} has invalid provider checksum")
            elif not has_valid_acquired_remote_binding(artifact):
                errors.append(
                    f"{label} lacks a provider checksum or valid acquired remote binding"
                )
            if artifact.get("local_sha256") is not None and not SHA256.fullmatch(
                str(artifact["local_sha256"])
            ):
                errors.append(f"{label} has invalid local_sha256")
        metadata_artifact = source.get("metadata_artifact")
        if metadata_artifact is not None:
            label = f"source {source_id} metadata_artifact"
            if not isinstance(metadata_artifact, dict):
                errors.append(f"{label} must be an object")
            else:
                if (
                    not isinstance(metadata_artifact.get("filename"), str)
                    or not metadata_artifact["filename"]
                ):
                    errors.append(f"{label} has invalid filename")
                if not isinstance(metadata_artifact.get("bytes"), int) or isinstance(
                    metadata_artifact.get("bytes"), bool
                ) or metadata_artifact["bytes"] < 1:
                    errors.append(f"{label} has invalid byte count")
                if not SHA256.fullmatch(str(metadata_artifact.get("local_sha256", ""))):
                    errors.append(f"{label} has invalid local_sha256")
                if not has_valid_acquired_remote_binding(metadata_artifact):
                    errors.append(f"{label} has invalid acquired remote binding")
        source_evidence = source.get("source_identity_evidence")
        if source_evidence is not None:
            label = f"source {source_id} source_identity_evidence"
            if not isinstance(source_evidence, dict):
                errors.append(f"{label} must be an object")
            else:
                evidence_path = source_evidence.get("aggregate_path")
                if (
                    not isinstance(evidence_path, str)
                    or not evidence_path
                    or Path(evidence_path).is_absolute()
                ):
                    errors.append(f"{label} aggregate_path must be repository-relative")
                if not SHA256.fullmatch(str(source_evidence.get("aggregate_sha256", ""))):
                    errors.append(f"{label} aggregate_sha256 is invalid")
        metadata_evidence = source.get("metadata_identity_evidence")
        if metadata_evidence is not None:
            label = f"source {source_id} metadata_identity_evidence"
            if not isinstance(metadata_evidence, dict):
                errors.append(f"{label} must be an object")
            else:
                evidence_path = metadata_evidence.get("aggregate_path")
                if (
                    not isinstance(evidence_path, str)
                    or not evidence_path
                    or Path(evidence_path).is_absolute()
                ):
                    errors.append(f"{label} aggregate_path must be repository-relative")
                if not SHA256.fullmatch(str(metadata_evidence.get("aggregate_sha256", ""))):
                    errors.append(f"{label} aggregate_sha256 is invalid")
        artist_family_rules = source.get("artist_family_rules")
        if artist_family_rules is not None:
            label = f"source {source_id} artist_family_rules"
            if not isinstance(artist_family_rules, dict):
                errors.append(f"{label} must be an object")
            else:
                rules_path = artist_family_rules.get("path")
                if (
                    not isinstance(rules_path, str)
                    or not rules_path
                    or Path(rules_path).is_absolute()
                ):
                    errors.append(f"{label} path must be repository-relative")
                if not SHA256.fullmatch(str(artist_family_rules.get("sha256", ""))):
                    errors.append(f"{label} sha256 is invalid")

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
    evidence = inventory.get("toolchain_probe_evidence")
    if not isinstance(evidence, dict):
        errors.append("toolchain_probe_evidence must be an object")
    else:
        aggregate_path = evidence.get("aggregate_path")
        if (
            not isinstance(aggregate_path, str)
            or not aggregate_path
            or Path(aggregate_path).is_absolute()
        ):
            errors.append("toolchain probe aggregate_path must be repository-relative")
        if not SHA256.fullmatch(str(evidence.get("aggregate_sha256", ""))):
            errors.append("toolchain probe aggregate_sha256 is invalid")
        for field in (
            "encoder_probe_count",
            "decoder_path_probe_count",
            "expected_capability_rejection_count",
        ):
            value = evidence.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                errors.append(f"toolchain probe {field} must be a positive integer")
        if evidence.get("complete_replays_byte_identical") is not True:
            errors.append("toolchain probe replays must be byte-identical")
    return errors


def validate_toolchain_probe_file(
    inventory: dict[str, Any], repository_root: Path
) -> list[str]:
    errors: list[str] = []
    evidence = inventory.get("toolchain_probe_evidence")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("aggregate_path"), str):
        return ["cannot validate missing toolchain probe evidence"]
    repository_root = repository_root.resolve()
    aggregate = (repository_root / evidence["aggregate_path"]).resolve()
    if not aggregate.is_relative_to(repository_root) or not aggregate.is_file():
        return ["toolchain probe aggregate is missing or outside the repository"]
    if sha256_file(aggregate) != evidence.get("aggregate_sha256"):
        errors.append("toolchain probe aggregate hash differs")
        return errors
    report = load_json(aggregate)
    expected_state = {
        "state": "synthetic_plumbing_evidence_only",
        "benchmark_audio_generated": False,
        "synthetic_probe_audio_generated": True,
        "scores_opened": False,
        "selection_authorized": False,
        "paths_redacted": True,
    }
    for field, expected in expected_state.items():
        if report.get(field) != expected:
            errors.append(f"toolchain probe report {field} differs")
    serialized = json.dumps(report, sort_keys=True)
    for forbidden in ("/Users/", "Library/Application Support", "\\Users\\"):
        if forbidden in serialized:
            errors.append("toolchain probe report contains a private path")
            break
    summary = report.get("summary")
    if not isinstance(summary, dict):
        errors.append("toolchain probe report summary is missing")
    else:
        for field in (
            "encoder_probe_count",
            "decoder_path_probe_count",
            "expected_capability_rejection_count",
        ):
            if summary.get(field) != evidence.get(field):
                errors.append(f"toolchain probe report {field} differs from inventory")
    candidate_pairs = {
        (row.get("codec_family"), row.get("lineage_id"))
        for row in inventory.get("encoder_candidates", [])
        if isinstance(row, dict)
    }
    report_pairs = {
        (row.get("codec_family"), row.get("lineage_id"))
        for row in report.get("encoders", [])
        if isinstance(row, dict)
    }
    if report_pairs != candidate_pairs:
        errors.append("toolchain probe encoder lineages differ from inventory")
    installed_hashes = {
        row.get("tool_id"): row.get("binary_sha256")
        for row in inventory.get("installed_tools", [])
        if isinstance(row, dict)
    }
    for tool in report.get("tools", []):
        if not isinstance(tool, dict):
            errors.append("toolchain probe contains an invalid tool row")
            continue
        if installed_hashes.get(tool.get("tool_id")) != tool.get("binary_sha256"):
            errors.append(f"toolchain probe tool binding differs: {tool.get('tool_id')}")
    return errors


def validate_source_identity_evidence_files(
    inventory: dict[str, Any], repository_root: Path
) -> list[str]:
    errors: list[str] = []
    repository_root = repository_root.resolve()
    for source in inventory.get("source_candidates", []):
        if not isinstance(source, dict):
            continue
        evidence = source.get("source_identity_evidence")
        if evidence is None:
            continue
        source_id = source.get("source_id")
        if not isinstance(evidence, dict) or not isinstance(
            evidence.get("aggregate_path"), str
        ):
            continue
        aggregate = (repository_root / evidence["aggregate_path"]).resolve()
        if not aggregate.is_relative_to(repository_root) or not aggregate.is_file():
            errors.append(
                f"source identity evidence is missing or outside repository: {source_id}"
            )
            continue
        if sha256_file(aggregate) != evidence.get("aggregate_sha256"):
            errors.append(f"source identity evidence hash differs: {source_id}")
            continue
        report = load_json(aggregate)
        expected_state = {
            "state": "source_identity_evidence_only",
            "source_id": source_id,
            "benchmark_audio_generated": False,
            "scores_opened": False,
            "selection_authorized": False,
            "paths_redacted": True,
        }
        for field, expected in expected_state.items():
            if report.get(field) != expected:
                errors.append(f"source identity report {source_id} {field} differs")
        serialized = json.dumps(report, sort_keys=True)
        for forbidden in ("/Users/", "Library/Application Support", "\\Users\\"):
            if forbidden in serialized:
                errors.append(f"source identity report contains a private path: {source_id}")
                break
        boundary = report.get("conservative_reference_boundary")
        group_count_fields = (
            "eligible_group_count",
            "eligible_talker_count",
            "eligible_sensor_count",
            "eligible_actor_count",
            "eligible_location_count",
            "eligible_speaker_count",
            "eligible_instrument_group_count",
        )
        boundary_group_counts = (
            [boundary[field] for field in group_count_fields if field in boundary]
            if isinstance(boundary, dict)
            else []
        )
        if len(boundary_group_counts) != 1 or boundary_group_counts[0] != source.get(
            "conservative_partition_groups"
        ):
            errors.append(f"source identity group count differs: {source_id}")
        audio_binding = report.get("archive_bindings", {}).get("audio")
        if not isinstance(audio_binding, dict):
            audio_binding = report.get("archive_binding")
        artifact = source.get("artifact")
        if isinstance(audio_binding, dict) and isinstance(artifact, dict):
            binding_sha256 = audio_binding.get("sha256")
            if binding_sha256 is None:
                binding_sha256 = audio_binding.get("local_sha256")
            if audio_binding.get("bytes") != artifact.get(
                "bytes"
            ) or binding_sha256 != artifact.get("local_sha256"):
                errors.append(f"source identity audio binding differs: {source_id}")
            provider_md5 = audio_binding.get("provider_md5")
            if provider_md5 is not None and (
                audio_binding.get("provider_checksum_verified") is not True
                or f"md5:{provider_md5}" != artifact.get("provider_checksum")
            ):
                errors.append(f"source identity provider binding differs: {source_id}")
        metadata_binding = report.get("archive_bindings", {}).get("metadata")
        metadata_artifact = source.get("metadata_artifact")
        if isinstance(metadata_binding, dict) and isinstance(metadata_artifact, dict):
            if metadata_binding.get("bytes") != metadata_artifact.get(
                "bytes"
            ) or metadata_binding.get("sha256") != metadata_artifact.get(
                "local_sha256"
            ):
                errors.append(f"source identity metadata binding differs: {source_id}")
    return errors


def validate_source_metadata_identity_evidence_files(
    inventory: dict[str, Any], repository_root: Path
) -> list[str]:
    errors: list[str] = []
    repository_root = repository_root.resolve()
    for source in inventory.get("source_candidates", []):
        if not isinstance(source, dict):
            continue
        evidence = source.get("metadata_identity_evidence")
        if evidence is None:
            continue
        source_id = source.get("source_id")
        if not isinstance(evidence, dict) or not isinstance(
            evidence.get("aggregate_path"), str
        ):
            continue
        aggregate = (repository_root / evidence["aggregate_path"]).resolve()
        if not aggregate.is_relative_to(repository_root) or not aggregate.is_file():
            errors.append(
                f"source metadata identity evidence is missing or outside repository: {source_id}"
            )
            continue
        if sha256_file(aggregate) != evidence.get("aggregate_sha256"):
            errors.append(f"source metadata identity evidence hash differs: {source_id}")
            continue
        report = load_json(aggregate)
        expected_state = {
            "state": "source_metadata_identity_evidence_only",
            "source_id": source_id,
            "audio_acquired": False,
            "benchmark_audio_generated": False,
            "scores_opened": False,
            "selection_authorized": False,
            "paths_redacted": True,
        }
        for field, expected in expected_state.items():
            if report.get(field) != expected:
                errors.append(f"source metadata report {source_id} {field} differs")
        serialized = json.dumps(report, sort_keys=True)
        for forbidden in ("/Users/", "Library/Application Support", "\\Users\\"):
            if forbidden in serialized:
                errors.append(f"source metadata report contains a private path: {source_id}")
                break
        boundary = report.get("conservative_group_boundary")
        if not isinstance(boundary, dict) or boundary.get(
            "eligible_group_count"
        ) != source.get("conservative_partition_groups"):
            errors.append(f"source metadata group count differs: {source_id}")
        binding = report.get("metadata_binding")
        if not isinstance(binding, dict) or binding.get("revision") != source.get(
            "metadata_revision"
        ) or binding.get("sha256") != source.get("metadata_sha256"):
            errors.append(f"source metadata binding differs: {source_id}")

        rules_binding = source.get("artist_family_rules")
        if not isinstance(rules_binding, dict) or not isinstance(
            rules_binding.get("path"), str
        ):
            errors.append(f"source metadata family rules are missing: {source_id}")
            continue
        rules_path = (repository_root / rules_binding["path"]).resolve()
        if not rules_path.is_relative_to(repository_root) or not rules_path.is_file():
            errors.append(f"source metadata family rules are outside repository: {source_id}")
            continue
        if sha256_file(rules_path) != rules_binding.get("sha256"):
            errors.append(f"source metadata family rules hash differs: {source_id}")
            continue
        rules = load_json(rules_path)
        for field, expected in {
            "state": "source_identity_rules_not_allocation",
            "source_id": source_id,
            "metadata_revision": source.get("metadata_revision"),
            "metadata_sha256": source.get("metadata_sha256"),
            "audio_generated": False,
            "scores_opened": False,
            "selection_authorized": False,
        }.items():
            if rules.get(field) != expected:
                errors.append(f"source metadata family rules {source_id} {field} differs")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    args = parser.parse_args()
    inventory = load_json(args.inventory)
    errors = validate(inventory)
    repository_root = Path(__file__).resolve().parents[1]
    errors.extend(validate_toolchain_probe_file(inventory, repository_root))
    errors.extend(validate_source_identity_evidence_files(inventory, repository_root))
    errors.extend(
        validate_source_metadata_identity_evidence_files(inventory, repository_root)
    )
    if errors:
        print("inventory validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("inventory valid: tool lineages and projected source partitions are disjoint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
