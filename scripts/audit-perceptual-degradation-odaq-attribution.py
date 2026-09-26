#!/usr/bin/env python3
"""Audit ODAQ attribution metadata without opening audio or listening scores."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, BinaryIO


ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "scripts" / "audit-perceptual-degradation-odaq.py"
PRIOR_AUDIT = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-odaq-score-blind-audit-20260803-001.json"
)
PRIOR_PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "public-development-acquisition-plan.json"
)
SPEC = importlib.util.spec_from_file_location("odaq_base_audit", BASE_SCRIPT)
assert SPEC and SPEC.loader
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)
WHITESPACE = re.compile(r"\s+")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    return WHITESPACE.sub(" ", value.strip())


def licence_record(row: dict[str, str]) -> dict[str, Any]:
    source_id = Path(row[""]).stem
    title = normalized(row["original file name"])
    creator = normalized(row["author"])
    source_url = normalized(row["source"])
    licence_url = normalized(row["license"])
    missing = []
    if not title or title.casefold() in {"n/a", "na", "none"}:
        missing.append("title")
    if not creator:
        missing.append("creator")
    if not source_url.startswith(("https://", "http://")):
        missing.append("source_url")
    if not licence_url.startswith(("https://", "http://")):
        missing.append("licence_url")
    record_id = "licence-odaq-" + hashlib.sha256(
        "\0".join(
            (BASE.RECORD_DOI, source_id, title, creator, source_url, licence_url)
        ).encode()
    ).hexdigest()[:20]
    return {
        "licence_record_id": record_id,
        "source_id": source_id,
        "title": title,
        "creator": creator,
        "source_url": source_url,
        "licence_url": licence_url,
        "licence_class": BASE.license_class(licence_url),
        "content": normalized(row["content"]),
        "original_coding": normalized(row["original coding"]),
        "original_format": normalized(row["original format"]),
        "current_format": normalized(row["current format"]),
        "duration_seconds": float(row["duration (s)"].strip()),
        "attribution_fields_complete": not missing,
        "missing_attribution_fields": missing,
        "attribution_resolution": "direct",
        "attribution_notice_title": title,
        "attribution_dependency_licence_record_ids": [],
        "attribution_notice_ready": not missing,
    }


def resolved_licence_records(
    rows: list[dict[str, str]], selected_source_ids: list[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    indexed = {Path(row[""]).stem: index for index, row in enumerate(rows)}
    primary_records = []
    dependencies: dict[str, dict[str, Any]] = {}
    for source_id in selected_source_ids:
        index = indexed[source_id]
        primary = licence_record(rows[index])
        source_note = normalized(rows[index]["source"]).casefold()
        if (
            not primary["attribution_fields_complete"]
            and "two rows above" in source_note
            and index >= 2
        ):
            dependency_records = [licence_record(row) for row in rows[index - 2 : index]]
            for dependency in dependency_records:
                dependencies[dependency["licence_record_id"]] = dependency
            primary["attribution_resolution"] = (
                "derived_mix_with_two_preceding_source_rows"
            )
            primary["attribution_notice_title"] = source_id
            primary["attribution_dependency_licence_record_ids"] = [
                item["licence_record_id"] for item in dependency_records
            ]
            primary["attribution_notice_ready"] = (
                bool(primary["creator"])
                and primary["licence_class"] in {"cc_by", "cc0"}
                and all(item["attribution_notice_ready"] for item in dependency_records)
            )
        primary_records.append(primary)
    return primary_records, [dependencies[key] for key in sorted(dependencies)]


def audit_archive(
    record: dict[str, Any],
    source: BinaryIO,
    prior_audit: dict[str, Any],
    prior_plan: dict[str, Any],
    *,
    range_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = BASE.validate_record(record)
    prior_errors = BASE.validate_frozen_evidence(prior_audit, prior_plan)
    if prior_errors:
        raise ValueError("prior score-blind ODAQ evidence differs")
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        inventory, inventory_sha256 = BASE.zip_inventory(infos)
        by_name = {info.filename: info for info in infos}
        required = {BASE.LICENSE_MEMBER, BASE.DISCLAIMER_MEMBER, BASE.SCORE_MEMBER}
        if not required <= set(by_name):
            raise ValueError("ODAQ required metadata members differ")
        licence_payload = archive.read(BASE.LICENSE_MEMBER)
        disclaimer_payload = archive.read(BASE.DISCLAIMER_MEMBER)

    reader = csv.DictReader(
        io.StringIO(licence_payload.decode("utf-8-sig")), delimiter=";"
    )
    if reader.fieldnames is None or set(reader.fieldnames) != BASE.REQUIRED_LICENSE_COLUMNS:
        raise ValueError("ODAQ detailed-license columns differ")
    rows = [
        row
        for row in reader
        if row.get("", "").strip().lower().endswith(".wav")
    ]
    by_source = {Path(row[""]).stem: row for row in rows}
    if len(by_source) != len(rows):
        raise ValueError("ODAQ attribution source IDs are not unique")

    selected_source_ids = prior_plan["selection"]["eligible_source_ids"]
    selected_folder_ids = prior_plan["selection"]["eligible_folder_ids"]
    if not set(selected_source_ids) <= set(by_source):
        raise ValueError("selected attribution source is absent")
    records, dependency_records = resolved_licence_records(rows, selected_source_ids)
    by_record_source = {item["source_id"]: item for item in records}
    prior_groups = {
        item["folder_id"]: item for item in prior_audit["listening_groups"]
    }
    groups = []
    for folder_id in selected_folder_ids:
        group = prior_groups.get(folder_id)
        if group is None or group.get("development_eligible") is not True:
            raise ValueError("selected attribution group differs")
        licence = by_record_source[group["source_id"]]
        groups.append(
            {
                "folder_id": folder_id,
                "source_id": group["source_id"],
                "licence_record_ids": [
                    licence["licence_record_id"],
                    *licence["attribution_dependency_licence_record_ids"],
                ],
                "artifact_family_code": group["artifact_family"],
                "wav_member_count": group["wav_member_count"],
                "wav_member_binding_sha256": group["wav_member_binding_sha256"],
                "development_only": True,
                "actual_codec_condition": False,
                "final_validation_eligible": False,
            }
        )

    class_counts = Counter(item["licence_class"] for item in records)
    direct_count = sum(item["attribution_fields_complete"] for item in records)
    resolved_count = sum(
        item["attribution_resolution"]
        == "derived_mix_with_two_preceding_source_rows"
        and item["attribution_notice_ready"]
        for item in records
    )
    ready_count = sum(item["attribution_notice_ready"] for item in records)
    return {
        "schema_version": 1,
        "audit_id": "odaq-attribution-metadata-audit-20260804-001",
        "state": "attribution_metadata_audited_audio_and_scores_unopened",
        "purpose": "published_simulated_artifact_development_sources_only",
        "provider": {
            "record_id": BASE.RECORD_ID,
            "doi": BASE.RECORD_DOI,
            "title": provider["title"],
            "publication_date": provider["publication_date"],
            "archive_key": BASE.ARCHIVE_KEY,
            "archive_bytes": BASE.ARCHIVE_BYTES,
            "archive_checksum": BASE.ARCHIVE_CHECKSUM,
        },
        "prior_bindings": {
            "score_blind_audit": {
                "path": str(PRIOR_AUDIT.relative_to(ROOT)),
                "sha256": sha256_file(PRIOR_AUDIT),
            },
            "acquisition_plan": {
                "path": str(PRIOR_PLAN.relative_to(ROOT)),
                "sha256": sha256_file(PRIOR_PLAN),
            },
        },
        "metadata_bindings": {
            "detailed_license_sha256": BASE.sha256_bytes(licence_payload),
            "license_disclaimer_sha256": BASE.sha256_bytes(disclaimer_payload),
            "archive_inventory_sha256": inventory_sha256,
            "archive_member_count": len(inventory),
        },
        "read_boundary": {
            "opened_archive_members": [BASE.DISCLAIMER_MEMBER, BASE.LICENSE_MEMBER],
            "score_member_present": BASE.SCORE_MEMBER in by_name,
            "score_member_opened": False,
            "audio_member_opened": False,
            "audio_downloaded": False,
            "archive_payload_downloaded": False,
        },
        "selection": {
            "source_count": len(records),
            "group_count": len(groups),
            "wav_member_count": sum(item["wav_member_count"] for item in groups),
            "artifact_family_code_counts": dict(
                sorted(Counter(item["artifact_family_code"] for item in groups).items())
            ),
            "licence_class_counts": dict(sorted(class_counts.items())),
            "direct_attribution_complete_source_count": direct_count,
            "dependency_resolved_source_count": resolved_count,
            "attribution_notice_ready_source_count": ready_count,
            "attribution_unresolved_source_count": len(records) - ready_count,
            "dependency_licence_record_count": len(dependency_records),
        },
        "licence_records": records,
        "dependency_licence_records": dependency_records,
        "listening_groups": groups,
        "range_access": range_stats
        or {
            "accept_ranges_verified": False,
            "archive_payload_downloaded": False,
            "fixture_only": True,
        },
        "licence_metadata_frozen_for_selected_development_sources": (
            ready_count == len(records)
        ),
        "source_and_condition_manifest_frozen": False,
        "audio_acquisition_authorized": False,
        "listening_score_access_authorized": False,
        "perceptual_metric_execution_authorized": False,
        "human_collection_authorized": False,
        "paths_redacted": True,
        "remaining_gaps": [
            "No selected ODAQ audio member has been opened or downloaded.",
            "ODAQ conditions are simulated artifacts, not actual codec encodes.",
            "The selected groups come from one published development provider.",
            "Transparent codec conditions, real encoder implementations, production controls, hard natural negatives, grouped transfer, and fresh final evidence remain absent.",
            "Seven selected derived mixes retain their raw placeholder titles and descriptive source fields; each attribution notice must also include the two explicitly referenced preceding source records bound in dependency_licence_records.",
            "A final attribution notice must preserve each selected title, creator, source URL, and licence URL when audio is acquired or presented.",
        ],
    }


def validate(report: dict[str, Any]) -> list[str]:
    errors = []
    if report.get("state") != "attribution_metadata_audited_audio_and_scores_unopened":
        errors.append("ODAQ attribution audit must remain score- and audio-blind")
    boundary = report.get("read_boundary", {})
    for key in (
        "score_member_opened",
        "audio_member_opened",
        "audio_downloaded",
        "archive_payload_downloaded",
    ):
        if boundary.get(key) is not False:
            errors.append(f"read_boundary.{key} must remain false")
    for key in (
        "source_and_condition_manifest_frozen",
        "audio_acquisition_authorized",
        "listening_score_access_authorized",
        "perceptual_metric_execution_authorized",
        "human_collection_authorized",
    ):
        if report.get(key) is not False:
            errors.append(f"{key} must remain false")
    selection = report.get("selection", {})
    if selection.get("source_count") != len(report.get("licence_records", [])):
        errors.append("attribution source count differs")
    if selection.get("group_count") != len(report.get("listening_groups", [])):
        errors.append("attribution group count differs")
    complete = all(
        item.get("attribution_notice_ready") is True
        for item in report.get("licence_records", [])
    )
    if report.get("licence_metadata_frozen_for_selected_development_sources") is not complete:
        errors.append("licence metadata completeness flag differs")
    for item in report.get("listening_groups", []):
        if item.get("development_only") is not True:
            errors.append("ODAQ group must remain development-only")
        if item.get("actual_codec_condition") is not False:
            errors.append("ODAQ group must not be represented as actual codec audio")
        if item.get("final_validation_eligible") is not False:
            errors.append("ODAQ group must remain outside final validation")
    if report.get("paths_redacted") is not True:
        errors.append("ODAQ attribution paths must be redacted")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--validate", type=Path)
    parser.add_argument("--block-bytes", type=int, default=BASE.DEFAULT_BLOCK_BYTES)
    args = parser.parse_args()
    if args.validate is not None:
        report = json.loads(args.validate.read_text(encoding="utf-8"))
        errors = validate(report)
        if errors:
            for error in errors:
                print(f"error: {error}")
            return 1
        print(
            json.dumps(
                {
                    "report": str(args.validate.resolve().relative_to(ROOT)),
                    "report_sha256": sha256_file(args.validate),
                    "status": report["state"],
                },
                sort_keys=True,
            )
        )
        return 0
    assert args.output is not None
    if args.output.exists() or args.output.is_symlink():
        parser.error("refusing to replace attribution output")
    prior_audit = json.loads(PRIOR_AUDIT.read_text(encoding="utf-8"))
    prior_plan = json.loads(PRIOR_PLAN.read_text(encoding="utf-8"))
    record = BASE.fetch_record()
    provider = BASE.validate_record(record)
    remote = BASE.HTTPRangeReader(
        provider["content_url"],
        expected_size=BASE.ARCHIVE_BYTES,
        block_bytes=args.block_bytes,
    )
    report = audit_archive(
        record,
        remote,
        prior_audit,
        prior_plan,
        range_stats=remote.stats(),
    )
    report["range_access"] = remote.stats()
    errors = validate(report)
    if errors:
        raise SystemExit("; ".join(errors))
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "attribution_metadata_audited_audio_and_scores_unopened",
                "source_count": report["selection"]["source_count"],
                "group_count": report["selection"]["group_count"],
                "attribution_unresolved_source_count": report["selection"][
                    "attribution_unresolved_source_count"
                ],
                "range_request_count": report["range_access"]["request_count"],
                "range_response_bytes": report["range_access"]["response_bytes"],
                "report_sha256": sha256_file(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
