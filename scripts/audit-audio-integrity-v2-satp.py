#!/usr/bin/env python3
"""Audit SATP audio and location groups without selecting benchmark content."""

from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import re
import struct
import tempfile
import zipfile
from pathlib import Path
from typing import Any


REPORT_SCHEMA_VERSION = 1
SOURCE_ID = "satp_soundscapes_1_5"
AUDIO_MEMBER = re.compile(r"^SATP WAV/([^/]+)\.wav$")
README_PROSE_VERSION = re.compile(r"SATP Dataset v([0-9.]+) contains")


def hash_file(path: Path) -> tuple[str, str]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            md5.update(chunk)
            sha256.update(chunk)
    return md5.hexdigest(), sha256.hexdigest()


def sha256_file(path: Path) -> str:
    return hash_file(path)[1]


def load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError("rules must be a JSON object")
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


def read_wave(payload: bytes) -> dict[str, int | str]:
    if len(payload) < 12 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise ValueError("member is not a little-endian RIFF/WAVE file")
    if struct.unpack("<I", payload[4:8])[0] + 8 != len(payload):
        raise ValueError("RIFF size does not equal member size")

    offset = 12
    format_payload: bytes | None = None
    pcm_payload: bytes | None = None
    ancillary_chunks: collections.Counter[str] = collections.Counter()
    while offset < len(payload):
        if offset + 8 > len(payload):
            raise ValueError("truncated RIFF chunk header")
        chunk_id_bytes = payload[offset : offset + 4]
        chunk_size = struct.unpack("<I", payload[offset + 4 : offset + 8])[0]
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_size
        if chunk_end > len(payload):
            raise ValueError("truncated RIFF chunk")
        chunk = payload[chunk_start:chunk_end]
        if chunk_id_bytes == b"fmt ":
            if format_payload is not None or len(chunk) < 16:
                raise ValueError("invalid or duplicate WAVE format chunk")
            format_payload = chunk
        elif chunk_id_bytes == b"data":
            if pcm_payload is not None:
                raise ValueError("duplicate WAVE data chunk")
            pcm_payload = chunk
        else:
            chunk_id = chunk_id_bytes.decode("latin-1")
            ancillary_chunks[chunk_id] += 1
        offset = chunk_end + (chunk_size & 1)
    if offset != len(payload):
        raise ValueError("invalid RIFF padding")
    if format_payload is None or pcm_payload is None:
        raise ValueError("WAVE member lacks format or data chunk")

    format_tag, channels, rate, average_bytes, block_align, bits = struct.unpack(
        "<HHIIHH", format_payload[:16]
    )
    logical_format_tag = format_tag
    valid_bits = bits
    if format_tag == 0xFFFE:
        if len(format_payload) < 40:
            raise ValueError("short WAVE_FORMAT_EXTENSIBLE chunk")
        valid_bits = struct.unpack("<H", format_payload[18:20])[0]
        subformat = format_payload[24:40]
        if subformat[4:] != bytes.fromhex("00001000800000aa00389b71"):
            raise ValueError("unknown WAVE_FORMAT_EXTENSIBLE subformat GUID")
        logical_format_tag = struct.unpack("<I", subformat[:4])[0]
    if block_align < 1 or len(pcm_payload) % block_align:
        raise ValueError("WAVE data size is not frame aligned")
    if average_bytes != rate * block_align:
        raise ValueError("WAVE average byte rate is inconsistent")
    sample_format = {1: "signed_integer_pcm", 3: "ieee_float_pcm"}.get(
        logical_format_tag, "other"
    )
    return {
        "container_format_tag": format_tag,
        "logical_format_tag": logical_format_tag,
        "sample_format": sample_format,
        "channel_count": channels,
        "sample_rate_hz": rate,
        "bits_per_sample": bits,
        "valid_bits_per_sample": valid_bits,
        "block_align_bytes": block_align,
        "average_bytes_per_second": average_bytes,
        "format_chunk_bytes": len(format_payload),
        "ancillary_chunk_counts": dict(sorted(ancillary_chunks.items())),
        "data_bytes": len(pcm_payload),
        "frame_count": len(pcm_payload) // block_align,
        "pcm_sha256": hashlib.sha256(pcm_payload).hexdigest(),
    }


def parse_recording_table(readme_text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    in_table = False
    for line in readme_text.splitlines():
        if line.startswith("| **File Name.wav**"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("| ---"):
            continue
        if not line.startswith("|"):
            break
        cells = [cell.strip().replace("**", "") for cell in line.strip("|").split("|")]
        if len(cells) != 5 or not cells[0]:
            raise ValueError("invalid SATP recording-information table row")
        rows.append(
            {
                "recording_id": cells[0],
                "location": cells[1],
                "latitude": cells[2],
                "longitude": cells[3],
                "recording_date": cells[4],
            }
        )
    if not rows:
        raise ValueError("SATP recording-information table is absent")
    if len({row["recording_id"] for row in rows}) != len(rows):
        raise ValueError("SATP README recording IDs are duplicated")
    return rows


def coordinate_group_key(row: dict[str, str]) -> str:
    latitude = row["latitude"]
    longitude = row["longitude"]
    if latitude == "/" or longitude == "/":
        return f"missing:{row['recording_id']}"
    return f"coordinate:{latitude}|{longitude}"


def format_rows(
    formats: collections.Counter[str], values: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for key, count in sorted(formats.items()):
        row = dict(values[key])
        row["file_count"] = count
        rows.append(row)
    return rows


def audit(archive_path: Path, readme_path: Path, rules_path: Path) -> dict[str, Any]:
    rules = load_object(rules_path)
    if rules.get("schema_version") != 1:
        raise ValueError("unsupported SATP source-group rule schema")
    expected_rule_state = {
        "state": "source_identity_rules_not_allocation",
        "source_id": SOURCE_ID,
        "record_id": 18715282,
        "record_version": "v1.5",
        "audio_generated": False,
        "scores_opened": False,
        "selection_authorized": False,
    }
    for field, expected in expected_rule_state.items():
        if rules.get(field) != expected:
            raise ValueError(f"SATP source-group rule {field} differs")
    if rules.get("grouping_fields") != ["latitude", "longitude"]:
        raise ValueError("SATP grouping fields differ")

    readme_md5, readme_sha256 = hash_file(readme_path)
    if rules.get("readme_sha256") != readme_sha256 or rules.get(
        "readme_provider_checksum"
    ) != f"md5:{readme_md5}":
        raise ValueError("SATP README binding differs")
    archive_md5, archive_sha256 = hash_file(archive_path)
    if rules.get("audio_bytes") != archive_path.stat().st_size or rules.get(
        "audio_provider_checksum"
    ) != f"md5:{archive_md5}":
        raise ValueError("SATP audio archive binding differs")

    readme_text = readme_path.read_text(encoding="utf-8")
    metadata_rows = parse_recording_table(readme_text)
    readme_calibration_ids = set(rules.get("calibration_readme_recording_ids", []))
    archive_calibration_ids = set(rules.get("calibration_archive_recording_ids", []))
    metadata_ids = {row["recording_id"] for row in metadata_rows}
    if not readme_calibration_ids or not archive_calibration_ids:
        raise ValueError("SATP calibration identifiers are absent")
    if not readme_calibration_ids <= metadata_ids:
        raise ValueError("SATP README calibration identifier is absent")
    reference_metadata_rows = [
        row for row in metadata_rows if row["recording_id"] not in readme_calibration_ids
    ]
    reference_metadata_ids = {row["recording_id"] for row in reference_metadata_rows}
    coordinate_groups: collections.defaultdict[str, set[str]] = (
        collections.defaultdict(set)
    )
    for row in reference_metadata_rows:
        coordinate_groups[coordinate_group_key(row)].add(row["recording_id"])
    duplicate_coordinate_groups = {
        key: ids for key, ids in coordinate_groups.items() if len(ids) > 1
    }

    archive_reference_ids: set[str] = set()
    observed_archive_calibration_ids: set[str] = set()
    unexpected_regular_member_count = 0
    directory_member_count = 0
    reference_formats: collections.Counter[str] = collections.Counter()
    reference_format_values: dict[str, dict[str, Any]] = {}
    calibration_formats: collections.Counter[str] = collections.Counter()
    calibration_format_values: dict[str, dict[str, Any]] = {}
    reference_pcm_digests: collections.Counter[str] = collections.Counter()
    reference_pcm_recordings: collections.defaultdict[str, set[str]] = (
        collections.defaultdict(set)
    )
    reference_frame_counts: list[int] = []
    reference_data_byte_counts: list[int] = []
    calibration_frame_counts: list[int] = []
    calibration_data_byte_counts: list[int] = []
    uncompressed_reference_bytes = 0
    regular_member_count = 0

    with zipfile.ZipFile(archive_path) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"ZIP CRC failure in {bad_member}")
        for member in archive.infolist():
            if member.is_dir():
                directory_member_count += 1
                continue
            regular_member_count += 1
            match = AUDIO_MEMBER.fullmatch(member.filename)
            if match is None:
                unexpected_regular_member_count += 1
                continue
            recording_id = match.group(1)
            payload = archive.read(member)
            wave = read_wave(payload)
            pcm_digest = str(wave.pop("pcm_sha256"))
            frames = int(wave["frame_count"])
            data_bytes = int(wave["data_bytes"])
            format_identity = dict(wave)
            format_identity.pop("frame_count")
            format_identity.pop("data_bytes")
            format_key = json.dumps(
                format_identity, sort_keys=True, separators=(",", ":")
            )
            if recording_id in archive_calibration_ids:
                observed_archive_calibration_ids.add(recording_id)
                calibration_formats[format_key] += 1
                calibration_format_values[format_key] = format_identity
                calibration_frame_counts.append(frames)
                calibration_data_byte_counts.append(data_bytes)
            else:
                if recording_id in archive_reference_ids:
                    raise ValueError("SATP archive recording IDs are duplicated")
                archive_reference_ids.add(recording_id)
                reference_formats[format_key] += 1
                reference_format_values[format_key] = format_identity
                reference_pcm_digests[pcm_digest] += 1
                reference_pcm_recordings[pcm_digest].add(recording_id)
                reference_frame_counts.append(frames)
                reference_data_byte_counts.append(data_bytes)
                uncompressed_reference_bytes += member.file_size

    if observed_archive_calibration_ids != archive_calibration_ids:
        raise ValueError("SATP archive calibration identifiers differ")
    if archive_reference_ids != reference_metadata_ids:
        raise ValueError("SATP archive and README reference identities differ")
    duplicate_pcm_groups = {
        digest: count for digest, count in reference_pcm_digests.items() if count > 1
    }
    unique_pcm_recording_ids = {
        recording_id
        for digest, recording_ids in reference_pcm_recordings.items()
        if reference_pcm_digests[digest] == 1
        for recording_id in recording_ids
    }
    eligible_group_count = sum(
        bool(recording_ids & unique_pcm_recording_ids)
        for recording_ids in coordinate_groups.values()
    )
    observed_expected = {
        "readme_table_row_count": len(metadata_rows),
        "calibration_row_count": len(readme_calibration_ids),
        "recording_row_count": len(reference_metadata_rows),
        "duplicate_exact_coordinate_group_count": len(duplicate_coordinate_groups),
        "source_group_count": len(coordinate_groups),
    }
    if rules.get("expected") != observed_expected:
        raise ValueError("SATP observed counts differ from source-group rules")

    prose_version_match = README_PROSE_VERSION.search(readme_text)
    prose_version = prose_version_match.group(1) if prose_version_match else None
    record_version = str(rules["record_version"])
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "state": "source_identity_evidence_only",
        "source_id": SOURCE_ID,
        "benchmark_audio_generated": False,
        "scores_opened": False,
        "selection_authorized": False,
        "paths_redacted": True,
        "provider_record": {
            "record_id": rules["record_id"],
            "record_version": record_version,
        },
        "archive_binding": {
            "bytes": archive_path.stat().st_size,
            "provider_md5": archive_md5,
            "provider_checksum_verified": True,
            "local_sha256": archive_sha256,
            "zip_crc_verified": True,
        },
        "readme_binding": {
            "bytes": readme_path.stat().st_size,
            "provider_md5": readme_md5,
            "provider_checksum_verified": True,
            "local_sha256": readme_sha256,
        },
        "source_group_rules_binding": {
            "sha256": sha256_file(rules_path),
        },
        "observed": {
            "regular_member_count": regular_member_count,
            "directory_member_count": directory_member_count,
            "unexpected_regular_member_count": unexpected_regular_member_count,
            "reference_recording_count": len(archive_reference_ids),
            "calibration_recording_count": len(observed_archive_calibration_ids),
            "audio_uncompressed_reference_member_bytes": uncompressed_reference_bytes,
            "reference_riff_formats": format_rows(
                reference_formats, reference_format_values
            ),
            "calibration_riff_formats": format_rows(
                calibration_formats, calibration_format_values
            ),
            "reference_frame_count_minimum": min(reference_frame_counts),
            "reference_frame_count_maximum": max(reference_frame_counts),
            "reference_data_bytes_minimum": min(reference_data_byte_counts),
            "reference_data_bytes_maximum": max(reference_data_byte_counts),
            "calibration_frame_count_minimum": min(calibration_frame_counts),
            "calibration_frame_count_maximum": max(calibration_frame_counts),
            "calibration_data_bytes_minimum": min(calibration_data_byte_counts),
            "calibration_data_bytes_maximum": max(calibration_data_byte_counts),
            "distinct_reference_pcm_digest_count": len(reference_pcm_digests),
            "duplicate_reference_pcm_digest_group_count": len(duplicate_pcm_groups),
            "duplicate_reference_pcm_file_count_excess": sum(
                count - 1 for count in duplicate_pcm_groups.values()
            ),
            "readme_exact_location_label_count": len(
                {row["location"] for row in reference_metadata_rows}
            ),
            "exact_coordinate_group_count": len(coordinate_groups),
            "duplicate_exact_coordinate_group_count": len(
                duplicate_coordinate_groups
            ),
            "source_group_size_counts": dict(
                sorted(
                    collections.Counter(
                        str(len(ids)) for ids in coordinate_groups.values()
                    ).items()
                )
            ),
        },
        "reconciliation": {
            "archive_and_readme_reference_id_sets_equal": True,
            "archive_calibration_id_differs_from_readme": (
                archive_calibration_ids != readme_calibration_ids
            ),
            "record_version": record_version,
            "readme_changelog_contains_record_version": (
                f"### 2026-02-20 {record_version}" in readme_text
            ),
            "readme_prose_dataset_version": prose_version,
            "readme_prose_version_differs_from_record": (
                prose_version is not None and f"v{prose_version}" != record_version
            ),
        },
        "conservative_reference_boundary": {
            "rule": [
                "archive reference ID occurs exactly once and is present in the bound README table",
                "PCM digest occurs exactly once among the 27 recordings",
                "recordings with the same exact non-missing provider coordinates share one source group",
            ],
            "eligible_recording_count": len(unique_pcm_recording_ids),
            "eligible_group_count": eligible_group_count,
            "grouping_unit": "exact provider-reported coordinate pair with missing coordinates kept singleton",
            "future_selection_constraint": (
                "At most one reference excerpt per coordinate group; preserve "
                "recording ID, location label, coordinates, and date as factors."
            ),
            "independence_limit": (
                "Coordinate groups do not prove independent operator sessions, "
                "hardware, export software, or collection days; retain SATP as one "
                "provider stratum and run leave-provider sensitivity."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--readme", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(args.archive, args.readme, args.rules)
    if args.output:
        write_json_atomic(args.output, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
