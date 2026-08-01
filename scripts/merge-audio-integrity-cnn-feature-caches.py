#!/usr/bin/env python3
"""Merge verified development CNN feature caches without restoring audio."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import tarfile
import tempfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

import torch

TRAINING_SCRIPT = Path(__file__).with_name("train-audio-integrity-cnn.py")


def load_training_module():
    spec = importlib.util.spec_from_file_location(
        "reklaw_audio_integrity_cnn_training",
        TRAINING_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"could not load training implementation: {TRAINING_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CNN = load_training_module()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_atomic(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace cache record: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def normalized_archive_member(value: str) -> str:
    path = PurePosixPath(value.removeprefix("./"))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise SystemExit(f"unsafe archive member path: {value}")
    return path.as_posix()


def archive_member_sha256(
    archive: Path,
    member_name: str,
    zstd: str,
) -> tuple[int, str]:
    wanted = normalized_archive_member(member_name)
    decompressor = subprocess.Popen(
        [zstd, "-dc", str(archive)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if decompressor.stdout is None or decompressor.stderr is None:
        decompressor.kill()
        raise SystemExit("failed to open archive decompressor")
    matches: list[tuple[int, str]] = []
    try:
        with tarfile.open(fileobj=decompressor.stdout, mode="r|") as source:
            for member in source:
                if member.name.removeprefix("./") in {"", "."}:
                    continue
                relative = normalized_archive_member(member.name)
                if relative != wanted:
                    continue
                if not member.isfile():
                    raise SystemExit(
                        f"archive cache member is not a regular file: {wanted}"
                    )
                extracted = source.extractfile(member)
                if extracted is None:
                    raise SystemExit(f"could not read archive member: {wanted}")
                digest = hashlib.sha256()
                size = 0
                for chunk in iter(lambda: extracted.read(1024 * 1024), b""):
                    size += len(chunk)
                    digest.update(chunk)
                matches.append((size, digest.hexdigest()))
    except (tarfile.TarError, OSError) as error:
        decompressor.kill()
        decompressor.wait()
        raise SystemExit(f"could not stream source archive: {error}") from error
    finally:
        decompressor.stdout.close()
    stderr = decompressor.stderr.read().decode("utf-8", errors="replace")
    return_code = decompressor.wait()
    if return_code != 0:
        raise SystemExit(
            f"source archive decompression failed with status {return_code}: "
            f"{stderr.strip()}"
        )
    if len(matches) != 1:
        raise SystemExit(
            f"archive member must occur exactly once: {wanted}; "
            f"found {len(matches)}"
        )
    return matches[0]


def validate_archive_cache(
    cache: Path,
    record_path: Path,
    member_name: str,
    zstd: str,
) -> dict:
    record = load_json(record_path)
    archive = Path(record.get("archive_path", "")).expanduser().resolve()
    if archive.is_symlink() or not archive.is_file():
        raise SystemExit(f"source archive is not a regular file: {archive}")
    if archive.stat().st_size != record.get("archive_bytes"):
        raise SystemExit(f"source archive byte count differs: {archive}")
    archive_sha256 = sha256_file(archive)
    if archive_sha256 != record.get("archive_sha256"):
        raise SystemExit(f"source archive SHA-256 differs: {archive}")
    member_bytes, member_sha256 = archive_member_sha256(
        archive,
        member_name,
        zstd,
    )
    if cache.stat().st_size != member_bytes or sha256_file(cache) != member_sha256:
        raise SystemExit(
            f"extracted cache differs from archived member: {cache}"
        )
    return {
        "archive_record": str(record_path),
        "archive_record_sha256": sha256_file(record_path),
        "archive_path": str(archive),
        "archive_bytes": record["archive_bytes"],
        "archive_sha256": archive_sha256,
        "archive_member": normalized_archive_member(member_name),
        "archive_member_bytes": member_bytes,
        "archive_member_sha256": member_sha256,
    }


def load_domain_rules(path: Path) -> tuple[dict, list[dict]]:
    value = load_json(path)
    rules = value.get("rules")
    if not isinstance(rules, list) or not rules:
        raise SystemExit("domain map contains no rules")
    domain_ids = [rule.get("domain_id") for rule in rules]
    prefixes = [rule.get("source_group_prefix") for rule in rules]
    if any(not isinstance(item, str) or not item for item in domain_ids):
        raise SystemExit("domain map contains an invalid domain ID")
    if any(not isinstance(item, str) or not item for item in prefixes):
        raise SystemExit("domain map contains an invalid source-group prefix")
    if len(set(domain_ids)) != len(domain_ids):
        raise SystemExit("domain map contains duplicate domain IDs")
    if len(set(prefixes)) != len(prefixes):
        raise SystemExit("domain map contains duplicate prefixes")
    return value, rules


def assign_domains(
    cases: list[dict],
    domain_map: dict,
    rules: list[dict],
) -> tuple[dict[str, str], dict[str, dict]]:
    case_domain: dict[str, str] = {}
    for case in cases:
        matches = [
            rule["domain_id"]
            for rule in rules
            if case["source_group"].startswith(
                rule["source_group_prefix"]
            )
        ]
        if len(matches) != 1:
            raise SystemExit(
                f"{case['case_id']}: expected one source domain, found "
                f"{matches}"
            )
        case_domain[case["case_id"]] = matches[0]

    stats = {}
    for rule in rules:
        domain_id = rule["domain_id"]
        selected = [
            case
            for case in cases
            if case_domain[case["case_id"]] == domain_id
        ]
        measured = {
            "partition_group_count": len(
                {
                    case.get("partition_group", case["source_group"])
                    for case in selected
                }
            ),
            "case_count": len(selected),
            "negative_count": sum(
                case["expectation"] == "negative" for case in selected
            ),
            "controlled_positive_count": sum(
                case["expectation"] == "controlled_positive"
                for case in selected
            ),
        }
        for field, expected_field in (
            ("partition_group_count", "expected_partition_group_count"),
            ("case_count", "expected_case_count"),
            ("negative_count", "expected_negative_count"),
            (
                "controlled_positive_count",
                "expected_controlled_positive_count",
            ),
        ):
            if measured[field] != rule.get(expected_field):
                raise SystemExit(
                    f"{domain_id}: {field} differs from domain map"
                )
        stats[domain_id] = measured

    totals = domain_map.get("expected_totals", {})
    measured_totals = {
        "domain_count": len(stats),
        "partition_group_count": len(
            {
                case.get("partition_group", case["source_group"])
                for case in cases
            }
        ),
        "case_count": len(cases),
        "negative_count": sum(
            case["expectation"] == "negative" for case in cases
        ),
        "controlled_positive_count": sum(
            case["expectation"] == "controlled_positive"
            for case in cases
        ),
    }
    if measured_totals != totals:
        raise SystemExit("measured totals differ from domain map")
    return case_domain, stats


def validate_cache_metadata(
    *,
    cache: Path,
    payload: dict,
    cases_by_id: dict[str, dict],
    case_domain: dict[str, str],
) -> tuple[list[dict], set[str]]:
    features = payload.get("features")
    metadata = payload.get("metadata")
    if not isinstance(features, torch.Tensor):
        raise SystemExit(f"{cache}: features are not a tensor")
    if not isinstance(metadata, list) or len(features) != len(metadata):
        raise SystemExit(f"{cache}: feature and metadata counts differ")
    if features.ndim != 3 or tuple(features.shape[1:]) != (
        CNN.FRAME_SIZE // 2 + 1,
        CNN.IMAGE_WIDTH,
    ):
        raise SystemExit(f"{cache}: feature tensor shape differs")
    if features.dtype != torch.float16:
        raise SystemExit(f"{cache}: feature tensor is not float16")
    for start in range(0, len(features), 1024):
        if not torch.isfinite(features[start : start + 1024]).all():
            raise SystemExit(f"{cache}: feature tensor contains non-finite data")

    observed: dict[str, list[dict]] = defaultdict(list)
    for item in metadata:
        if not isinstance(item, dict) or not isinstance(
            item.get("case_id"),
            str,
        ):
            raise SystemExit(f"{cache}: invalid feature metadata")
        if item["case_id"] not in cases_by_id:
            raise SystemExit(
                f"{cache}: unknown case in metadata: {item['case_id']}"
            )
        observed[item["case_id"]].append(item)

    expected_clip_indices = list(range(len(CNN.CLIP_FRACTIONS)))
    for case_id, items in observed.items():
        case = cases_by_id[case_id]
        clip_indices = [item.get("clip_index") for item in items]
        if any(not isinstance(index, int) for index in clip_indices) or (
            sorted(clip_indices) != expected_clip_indices
        ):
            raise SystemExit(f"{cache}: {case_id} clip indices differ")
        for item in items:
            expected_identity = {
                "source_group": case["source_group"],
                "partition_group": case.get(
                    "partition_group",
                    case["source_group"],
                ),
                "class": case["class"],
                "expectation": case["expectation"],
            }
            observed_identity = {
                "source_group": item.get("source_group"),
                "partition_group": item.get(
                    "partition_group",
                    item.get("source_group"),
                ),
                "class": item.get("class"),
                "expectation": item.get("expectation"),
            }
            if observed_identity != expected_identity:
                raise SystemExit(
                    f"{cache}: {case_id} metadata identity differs"
                )
            sample_rate = item.get("sample_rate")
            if not isinstance(sample_rate, int) or sample_rate <= 0:
                raise SystemExit(
                    f"{cache}: {case_id} sample rate is invalid"
                )
    normalized = [
        {
            **item,
            "partition_group": cases_by_id[item["case_id"]].get(
                "partition_group",
                cases_by_id[item["case_id"]]["source_group"],
            ),
            "source_domain": case_domain[item["case_id"]],
        }
        for item in metadata
    ]
    return normalized, set(observed)


def save_cache_atomic(path: Path, payload: dict) -> None:
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace merged feature cache: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".incomplete",
        dir=path.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        torch.save(payload, temporary)
        temporary.chmod(0o600)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def command(args: argparse.Namespace) -> int:
    manifests = [path.expanduser().resolve() for path in args.manifest]
    caches = [path.expanduser().resolve() for path in args.source_cache]
    archive_records = [
        path.expanduser().resolve()
        for path in args.source_archive_record
    ]
    if not (
        len(caches)
        == len(archive_records)
        == len(args.source_archive_member)
    ):
        raise SystemExit(
            "source cache, archive record, and archive member counts must match"
        )
    if len(caches) < 2:
        raise SystemExit("at least two source caches are required")
    for label, paths in (
        ("manifest", manifests),
        ("source cache", caches),
        ("source archive record", archive_records),
    ):
        for path in paths:
            if path.is_symlink() or not path.is_file():
                raise SystemExit(f"{label} is not a regular file: {path}")
    output = args.output.expanduser().resolve()
    record_path = args.record.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit(f"refusing to replace merged feature cache: {output}")
    if record_path.exists() or record_path.is_symlink():
        raise SystemExit(f"refusing to replace cache record: {record_path}")

    cases = CNN.merged_cases(manifests)
    cases_by_id = {case["case_id"]: case for case in cases}
    signature = CNN.manifest_signature(manifests, cases)
    domain_map_path = args.domain_map.expanduser().resolve()
    if domain_map_path.is_symlink() or not domain_map_path.is_file():
        raise SystemExit(
            f"domain map is not a regular file: {domain_map_path}"
        )
    domain_map, domain_rules = load_domain_rules(domain_map_path)
    case_domain, domain_stats = assign_domains(
        cases,
        domain_map,
        domain_rules,
    )
    allowed_legacy = {
        path.expanduser().resolve()
        for path in args.allow_legacy_source_cache
    }
    if not allowed_legacy.issubset(set(caches)):
        raise SystemExit(
            "legacy source cache exception names an unknown cache"
        )

    source_records = []
    source_features = []
    merged_metadata = []
    seen_case_ids: set[str] = set()
    for cache, archive_record, archive_member in zip(
        caches,
        archive_records,
        args.source_archive_member,
    ):
        archive_evidence = validate_archive_cache(
            cache,
            archive_record,
            archive_member,
            args.zstd,
        )
        payload = torch.load(
            cache,
            map_location="cpu",
            weights_only=False,
        )
        cached_definition = payload.get("feature_definition_sha256")
        legacy_adopted = False
        if cached_definition != CNN.FEATURE_DEFINITION_SHA256:
            if cached_definition is None and cache in allowed_legacy:
                legacy_adopted = True
            else:
                raise SystemExit(
                    f"{cache}: feature definition differs or is uncommitted"
                )
        elif payload.get("feature_definition") != CNN.FEATURE_DEFINITION:
            raise SystemExit(
                f"{cache}: feature definition body differs from its commitment"
            )
        normalized, cache_case_ids = validate_cache_metadata(
            cache=cache,
            payload=payload,
            cases_by_id=cases_by_id,
            case_domain=case_domain,
        )
        overlap = seen_case_ids & cache_case_ids
        if overlap:
            raise SystemExit(
                f"source caches overlap; first case is {sorted(overlap)[0]}"
            )
        seen_case_ids.update(cache_case_ids)
        source_features.append(payload["features"])
        merged_metadata.extend(normalized)
        source_records.append(
            {
                "cache_path": str(cache),
                "cache_bytes": cache.stat().st_size,
                "cache_sha256": sha256_file(cache),
                "cache_case_count": len(cache_case_ids),
                "cache_clip_count": len(normalized),
                "cached_manifest_signature": payload.get(
                    "manifest_signature"
                ),
                "cached_feature_definition_sha256": cached_definition,
                "legacy_feature_definition_adopted": legacy_adopted,
                "archive_evidence": archive_evidence,
            }
        )
    if seen_case_ids != set(cases_by_id):
        missing = sorted(set(cases_by_id) - seen_case_ids)
        raise SystemExit(
            "source caches do not cover every manifest case; first missing "
            f"case is {missing[0] if missing else 'unknown'}"
        )

    features = torch.cat(source_features)
    del source_features
    payload = {
        "schema_version": 2,
        "manifest_signature": signature,
        "feature_definition": CNN.FEATURE_DEFINITION,
        "feature_definition_sha256": CNN.FEATURE_DEFINITION_SHA256,
        "source_domain_map_id": domain_map["map_id"],
        "source_domain_map_sha256": sha256_file(domain_map_path),
        "features": features,
        "metadata": merged_metadata,
    }
    save_cache_atomic(output, payload)
    output_sha256 = sha256_file(output)
    record = {
        "schema_version": 1,
        "record_id": args.record_id,
        "disposition": {
            "state": "merged_development_feature_cache",
            "audio_fingerprints_reverified_live": False,
            "release_evidence": False,
            "public_verdict_enabled": False,
            "reason": (
                "Features were restored from independently verified research "
                "archives. This avoids restoring private audio but cannot "
                "replace live fingerprint verification for release evidence."
            ),
        },
        "manifest_signature": signature,
        "manifests": [
            {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in manifests
        ],
        "feature_definition": CNN.FEATURE_DEFINITION,
        "feature_definition_sha256": CNN.FEATURE_DEFINITION_SHA256,
        "domain_map": {
            "path": str(domain_map_path),
            "sha256": sha256_file(domain_map_path),
            "map_id": domain_map["map_id"],
            "domain_stats": domain_stats,
        },
        "source_caches": source_records,
        "merged_cache": {
            "path": str(output),
            "bytes": output.stat().st_size,
            "sha256": output_sha256,
            "case_count": len(cases),
            "clip_count": len(merged_metadata),
        },
        "merge_script_sha256": sha256_file(Path(__file__).resolve()),
        "training_library_sha256": sha256_file(TRAINING_SCRIPT),
        "torch_version": torch.__version__,
    }
    write_atomic(record_path, record)
    print(
        f"merged {len(cases)} cases and {len(merged_metadata)} clips "
        f"across {len(domain_stats)} source domains into {output}"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--manifest",
        type=Path,
        action="append",
        required=True,
    )
    result.add_argument(
        "--source-cache",
        type=Path,
        action="append",
        required=True,
    )
    result.add_argument(
        "--source-archive-record",
        type=Path,
        action="append",
        required=True,
    )
    result.add_argument(
        "--source-archive-member",
        action="append",
        required=True,
    )
    result.add_argument(
        "--allow-legacy-source-cache",
        type=Path,
        action="append",
        default=[],
    )
    result.add_argument("--domain-map", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--record", type=Path, required=True)
    result.add_argument("--record-id", required=True)
    result.add_argument("--zstd", default="zstd")
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
