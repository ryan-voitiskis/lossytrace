#!/usr/bin/env python3
"""Freeze exact ODAQ reference-member metadata without opening audio or scores."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, BinaryIO


ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "scripts" / "audit-perceptual-degradation-odaq.py"
FALLBACK_PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "permissive-listening-source-fallback-plan.json"
)
ATTRIBUTION_AUDIT = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-odaq-attribution-audit-20260804-001.json"
)
DEFAULT_PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "odaq-reference-acquisition-freeze.json"
)
SPEC = importlib.util.spec_from_file_location("odaq_base_audit", BASE_SCRIPT)
assert SPEC and SPEC.loader
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)
CRC32 = re.compile(r"^[0-9a-f]{8}$")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def reference_member_name(folder_id: str) -> str:
    return f"{BASE.LISTENING_PREFIX}{folder_id}/reference.wav"


def build_plan(
    record: dict[str, Any],
    source: BinaryIO,
    fallback: dict[str, Any],
    attribution: dict[str, Any],
    *,
    range_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = BASE.validate_record(record)
    if fallback.get("decision", {}).get("permissive_fallback_identified") is not True:
        raise ValueError("permissive fallback is not identified")
    if attribution.get("licence_metadata_frozen_for_selected_development_sources") is not True:
        raise ValueError("selected attribution metadata is incomplete")

    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
    by_name = {item.filename: item for item in infos}
    if len(by_name) != len(infos):
        raise ValueError("duplicate ZIP member name")

    references: list[dict[str, Any]] = []
    for group in attribution.get("listening_groups", []):
        folder_id = group.get("folder_id")
        source_id = group.get("source_id")
        if not isinstance(folder_id, str) or not isinstance(source_id, str):
            raise ValueError("selected group identity differs")
        member_name = reference_member_name(folder_id)
        info = by_name.get(member_name)
        if info is None or info.is_dir():
            raise ValueError(f"missing selected reference member: {folder_id}")
        if not BASE.safe_member_name(member_name):
            raise ValueError(f"unsafe selected reference member: {folder_id}")
        references.append(
            {
                "folder_id": folder_id,
                "source_id": source_id,
                "member_basename": "reference.wav",
                "crc32": f"{info.CRC:08x}",
                "compressed_bytes": info.compress_size,
                "uncompressed_bytes": info.file_size,
                "compression_method": info.compress_type,
                "licence_record_ids": group.get("licence_record_ids", []),
                "artifact_family_code": group.get("artifact_family_code"),
            }
        )
    references.sort(key=lambda item: item["folder_id"])
    family_counts = Counter(item["artifact_family_code"] for item in references)
    return {
        "schema_version": 1,
        "freeze_id": "perceptual-degradation-odaq-reference-acquisition-20260804-001",
        "state": "exact_reference_members_frozen_audio_and_scores_unopened_acquisition_unauthorized",
        "purpose": "Freeze exact CC BY/CC0 ODAQ clean-reference ZIP members for a possible narrow development-listening path without opening audio, processed conditions or scores and without choosing that path for the study.",
        "bindings": {
            "permissive_fallback": {
                "path": str(FALLBACK_PLAN.relative_to(ROOT)),
                "sha256": sha256_file(FALLBACK_PLAN),
            },
            "odaq_attribution_audit": {
                "path": str(ATTRIBUTION_AUDIT.relative_to(ROOT)),
                "sha256": sha256_file(ATTRIBUTION_AUDIT),
            },
        },
        "provider": {
            "record_id": BASE.RECORD_ID,
            "doi": BASE.RECORD_DOI,
            "title": provider["title"],
            "publication_date": provider["publication_date"],
            "archive_key": BASE.ARCHIVE_KEY,
            "archive_bytes": BASE.ARCHIVE_BYTES,
            "archive_checksum": BASE.ARCHIVE_CHECKSUM,
        },
        "read_boundary": {
            "zip_central_directory_opened": True,
            "licence_or_disclaimer_member_opened_in_this_freeze": False,
            "audio_member_opened": False,
            "processed_condition_opened": False,
            "score_member_opened": False,
            "archive_payload_downloaded": False,
        },
        "selection": {
            "policy": "every previously audited CC BY or CC0 ODAQ listening group, reference.wav only",
            "reference_count": len(references),
            "music_reference_count": sum(
                count for family, count in family_counts.items() if family != "DE"
            ),
            "movie_like_soundtrack_reference_count": family_counts.get("DE", 0),
            "artifact_family_code_counts": dict(sorted(family_counts.items())),
            "total_compressed_bytes": sum(
                item["compressed_bytes"] for item in references
            ),
            "total_uncompressed_bytes": sum(
                item["uncompressed_bytes"] for item in references
            ),
            "full_archive_persistence_required": False,
        },
        "references": references,
        "range_access": range_stats
        or {
            "accept_ranges_verified": False,
            "archive_payload_downloaded": False,
            "fixture_only": True,
        },
        "execution_boundary": {
            "source_track_selected": False,
            "reference_audio_acquisition_authorized": False,
            "stimulus_generation_authorized": False,
            "actual_codec_generation_authorized": False,
            "perceptual_metric_execution_authorized": False,
            "listening_score_access_authorized": False,
            "listener_response_collection_authorized": False,
            "participant_contact_authorized": False,
        },
        "storage_policy": {
            "minimum_free_disk_gib": 15,
            "maximum_sustained_workers": 1,
            "bounded_http_range_required": True,
            "private_output_root_required": True,
            "full_archive_persistence_forbidden": True,
            "repository_audio_forbidden": True,
            "atomic_member_write_and_verify_required": True,
        },
        "claim_boundary": {
            "published_processed_conditions_are_actual_codec_encodes": False,
            "published_scores_are_actual_codec_audibility_truth": False,
            "one_odaq_provider_proves_independent_music_transfer": False,
            "selected_references_are_final_validation": False,
        },
        "paths_redacted": True,
        "authorized_next_step": "After the responsible human selects the narrow permissive path and declares a qualified playback chain, commit a successor authorization that may acquire only these 16 reference members. Until then, do not open audio, processed conditions or scores and do not generate stimuli or collect responses.",
    }


def validate(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if plan.get("state") != (
        "exact_reference_members_frozen_audio_and_scores_unopened_acquisition_unauthorized"
    ):
        errors.append("freeze state differs")

    bound: dict[str, dict[str, Any]] = {}
    for key, binding in plan.get("bindings", {}).items():
        relative = Path(str(binding.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"invalid repository-relative binding: {key}")
            continue
        path = root / relative
        if not path.is_file():
            errors.append(f"missing bound file: {key}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {key}")
        elif path.suffix == ".json":
            bound[key] = load_json(path)

    provider = plan.get("provider", {})
    if provider.get("record_id") != BASE.RECORD_ID or provider.get("doi") != BASE.RECORD_DOI:
        errors.append("provider identity differs")
    if provider.get("archive_bytes") != BASE.ARCHIVE_BYTES:
        errors.append("provider archive size differs")
    if provider.get("archive_checksum") != BASE.ARCHIVE_CHECKSUM:
        errors.append("provider archive checksum differs")

    boundary = plan.get("read_boundary", {})
    if boundary.get("zip_central_directory_opened") is not True:
        errors.append("ZIP central-directory observation is absent")
    for key in (
        "licence_or_disclaimer_member_opened_in_this_freeze",
        "audio_member_opened",
        "processed_condition_opened",
        "score_member_opened",
        "archive_payload_downloaded",
    ):
        if boundary.get(key) is not False:
            errors.append(f"read boundary must remain false: {key}")

    attribution = bound.get("odaq_attribution_audit", {})
    attribution_groups = {
        item.get("folder_id"): item
        for item in attribution.get("listening_groups", [])
    }
    references = plan.get("references", [])
    folders = [item.get("folder_id") for item in references]
    sources = [item.get("source_id") for item in references]
    if len(references) != 16 or len(set(folders)) != 16 or len(set(sources)) != 16:
        errors.append("reference identity cardinality differs")
    if folders != sorted(folders):
        errors.append("references must be sorted by folder ID")
    for item in references:
        folder_id = item.get("folder_id")
        source_group = attribution_groups.get(folder_id)
        if source_group is None or item.get("source_id") != source_group.get("source_id"):
            errors.append(f"reference source binding differs: {folder_id}")
            continue
        if item.get("member_basename") != "reference.wav":
            errors.append(f"non-reference member selected: {folder_id}")
        if not CRC32.fullmatch(str(item.get("crc32", ""))):
            errors.append(f"reference CRC32 differs: {folder_id}")
        if item.get("compressed_bytes", 0) <= 0 or item.get("uncompressed_bytes", 0) <= 0:
            errors.append(f"reference byte size differs: {folder_id}")
        if item.get("compression_method") not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
            errors.append(f"reference ZIP compression differs: {folder_id}")
        if item.get("licence_record_ids") != source_group.get("licence_record_ids"):
            errors.append(f"reference licence binding differs: {folder_id}")
        if item.get("artifact_family_code") != source_group.get("artifact_family_code"):
            errors.append(f"reference artifact-family binding differs: {folder_id}")

    selection = plan.get("selection", {})
    family_counts = Counter(item.get("artifact_family_code") for item in references)
    if selection.get("reference_count") != len(references):
        errors.append("reference selection count differs")
    if selection.get("music_reference_count") != sum(
        count for family, count in family_counts.items() if family != "DE"
    ):
        errors.append("music reference count differs")
    if selection.get("movie_like_soundtrack_reference_count") != family_counts.get("DE", 0):
        errors.append("soundtrack reference count differs")
    if selection.get("artifact_family_code_counts") != dict(sorted(family_counts.items())):
        errors.append("artifact-family counts differ")
    if selection.get("total_compressed_bytes") != sum(
        item.get("compressed_bytes", 0) for item in references
    ):
        errors.append("compressed-byte total differs")
    if selection.get("total_uncompressed_bytes") != sum(
        item.get("uncompressed_bytes", 0) for item in references
    ):
        errors.append("uncompressed-byte total differs")
    if selection.get("full_archive_persistence_required") is not False:
        errors.append("full archive persistence must remain unnecessary")

    for key, value in plan.get("execution_boundary", {}).items():
        if value is not False:
            errors.append(f"execution boundary must remain false: {key}")
    storage = plan.get("storage_policy", {})
    if storage.get("minimum_free_disk_gib") != 15:
        errors.append("disk reserve differs")
    if storage.get("maximum_sustained_workers") != 1:
        errors.append("worker boundary differs")
    for key in (
        "bounded_http_range_required",
        "private_output_root_required",
        "full_archive_persistence_forbidden",
        "repository_audio_forbidden",
        "atomic_member_write_and_verify_required",
    ):
        if storage.get(key) is not True:
            errors.append(f"storage boundary differs: {key}")
    for key, value in plan.get("claim_boundary", {}).items():
        if value is not False:
            errors.append(f"claim boundary must remain false: {key}")
    if plan.get("paths_redacted") is not True:
        errors.append("paths must remain redacted")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--validate", type=Path)
    parser.add_argument("--block-bytes", type=int, default=BASE.DEFAULT_BLOCK_BYTES)
    args = parser.parse_args()
    if args.validate is not None:
        errors = validate(load_json(args.validate))
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"validated {args.validate}")
        return 0

    assert args.output is not None
    if args.output.exists() or args.output.is_symlink():
        parser.error("refusing to replace output")
    fallback = load_json(FALLBACK_PLAN)
    attribution = load_json(ATTRIBUTION_AUDIT)
    record = BASE.fetch_record()
    provider = BASE.validate_record(record)
    remote = BASE.HTTPRangeReader(
        provider["content_url"],
        expected_size=BASE.ARCHIVE_BYTES,
        block_bytes=args.block_bytes,
    )
    plan = build_plan(
        record,
        remote,
        fallback,
        attribution,
        range_stats=remote.stats(),
    )
    plan["range_access"] = remote.stats()
    errors = validate(plan)
    if errors:
        raise SystemExit("; ".join(errors))
    args.output.write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "reference_count": plan["selection"]["reference_count"],
                "total_compressed_bytes": plan["selection"]["total_compressed_bytes"],
                "total_uncompressed_bytes": plan["selection"]["total_uncompressed_bytes"],
                "range_request_count": plan["range_access"]["request_count"],
                "range_response_bytes": plan["range_access"]["response_bytes"],
                "status": "reference_metadata_frozen_audio_and_scores_unopened",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
