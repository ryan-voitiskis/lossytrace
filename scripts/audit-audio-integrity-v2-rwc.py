#!/usr/bin/env python3
"""Audit the five RWC v2 audio archives without selecting benchmark audio."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import stat
import struct
import tempfile
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO


REPORT_SCHEMA_VERSION = 1
SOURCE_ID = "rwc_music_v2_2026"
COLLECTION_IDS = ("C", "G", "J", "P", "R")
RWC_ID = re.compile(r"^RWC_([CGJPR])([0-9]{3}[A-Z]?)$")
AUDIO_MEMBER = re.compile(
    r"^RWC-([CGJPR])/(RWC_([CGJPR])([0-9]{3}[A-Z]?))\.wav$"
)
PROVIDER_CHECKSUM = re.compile(r"^md5:([0-9a-f]{32})$")
REQUIRED_COLUMNS = {
    "RWCID",
    "CollID",
    "PieceNo",
    "CDNo",
    "TrackNo",
    "Title",
    "Artist",
    "audio_start",
    "audio_end",
    "duration",
}


def digest_file_many(path: Path, algorithms: tuple[str, ...]) -> dict[str, str]:
    digests = {algorithm: hashlib.new(algorithm) for algorithm in algorithms}
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            for digest in digests.values():
                digest.update(chunk)
    return {algorithm: digest.hexdigest() for algorithm, digest in digests.items()}


def sha256_file(path: Path) -> str:
    return digest_file_many(path, ("sha256",))["sha256"]


def load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: top-level JSON must be an object")
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


def safe_member_id(value: str) -> str:
    member = PurePosixPath(value)
    if (
        not value
        or member.is_absolute()
        or ".." in member.parts
        or member.as_posix() != value
    ):
        raise ValueError("RWC archive contains an unsafe or noncanonical path")
    return value


def read_exact(source: BinaryIO, byte_count: int, label: str) -> bytes:
    chunks: list[bytes] = []
    remaining = byte_count
    while remaining:
        chunk = source.read(min(1024 * 1024, remaining))
        if not chunk:
            raise ValueError(f"RWC {label} is truncated")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def discard_exact(source: BinaryIO, byte_count: int, label: str) -> None:
    remaining = byte_count
    while remaining:
        chunk = source.read(min(1024 * 1024, remaining))
        if not chunk:
            raise ValueError(f"RWC {label} is truncated")
        remaining -= len(chunk)


def read_wave(source: BinaryIO, member_bytes: int) -> dict[str, Any]:
    header = read_exact(source, 12, "RIFF header")
    if header[:4] != b"RIFF" or header[8:12] != b"WAVE":
        raise ValueError("RWC member is not a little-endian RIFF/WAVE file")
    if struct.unpack("<I", header[4:8])[0] + 8 != member_bytes:
        raise ValueError("RWC RIFF size does not equal member size")

    offset = 12
    format_payload: bytes | None = None
    pcm_digest: Any | None = None
    data_bytes: int | None = None
    ancillary_chunks: collections.Counter[str] = collections.Counter()
    while offset < member_bytes:
        chunk_header = read_exact(source, 8, "RIFF chunk header")
        chunk_id = chunk_header[:4]
        chunk_size = struct.unpack("<I", chunk_header[4:8])[0]
        padded_size = chunk_size + (chunk_size & 1)
        if offset + 8 + padded_size > member_bytes:
            raise ValueError("RWC member contains a truncated RIFF chunk")
        if chunk_id == b"fmt ":
            if format_payload is not None or chunk_size < 16:
                raise ValueError("RWC member has an invalid or duplicate format chunk")
            format_payload = read_exact(source, chunk_size, "format chunk")
        elif chunk_id == b"data":
            if pcm_digest is not None:
                raise ValueError("RWC member has a duplicate data chunk")
            pcm_digest = hashlib.sha256()
            remaining = chunk_size
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("RWC PCM data is truncated")
                pcm_digest.update(chunk)
                remaining -= len(chunk)
            data_bytes = chunk_size
        else:
            ancillary_chunks[chunk_id.decode("latin-1")] += 1
            discard_exact(source, chunk_size, "ancillary chunk")
        if chunk_size & 1:
            read_exact(source, 1, "RIFF padding")
        offset += 8 + padded_size

    if offset != member_bytes:
        raise ValueError("RWC member has invalid RIFF padding")
    if source.read(1):
        raise ValueError("RWC member exceeds its ZIP size")
    if format_payload is None or pcm_digest is None or data_bytes is None:
        raise ValueError("RWC member lacks a format or data chunk")

    format_tag, channels, rate, average_bytes, block_align, bits = struct.unpack(
        "<HHIIHH", format_payload[:16]
    )
    if block_align < 1 or data_bytes % block_align:
        raise ValueError("RWC data size is not frame aligned")
    if average_bytes != rate * block_align:
        raise ValueError("RWC average byte rate is inconsistent")
    if format_tag == 1 and block_align != channels * ((bits + 7) // 8):
        raise ValueError("RWC PCM block alignment is inconsistent")
    return {
        "format_tag": format_tag,
        "sample_format": {1: "signed_integer_pcm", 3: "ieee_float_pcm"}.get(
            format_tag, "other"
        ),
        "channel_count": channels,
        "sample_rate_hz": rate,
        "bits_per_sample": bits,
        "block_align_bytes": block_align,
        "average_bytes_per_second": average_bytes,
        "format_chunk_bytes": len(format_payload),
        "ancillary_chunk_counts": dict(sorted(ancillary_chunks.items())),
        "data_bytes": data_bytes,
        "frame_count": data_bytes // block_align,
        "pcm_sha256": pcm_digest.hexdigest(),
    }


def validate_file_binding(path: Path, binding: Any, label: str) -> dict[str, Any]:
    if not isinstance(binding, dict) or binding.get("filename") != path.name:
        raise ValueError(f"RWC {label} filename binding differs")
    provider_checksum = binding.get("provider_checksum")
    algorithms = ("sha256", "md5") if provider_checksum is not None else ("sha256",)
    digests = digest_file_many(path, algorithms)
    if (
        path.stat().st_size != binding.get("bytes")
        or digests["sha256"] != binding.get("local_sha256")
    ):
        raise ValueError(f"RWC {label} byte binding differs")
    result: dict[str, Any] = {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "local_sha256": digests["sha256"],
    }
    if provider_checksum is not None:
        match = PROVIDER_CHECKSUM.fullmatch(str(provider_checksum))
        if match is None or digests["md5"] != match.group(1):
            raise ValueError(f"RWC {label} provider checksum differs")
        result["provider_md5"] = match.group(1)
        result["provider_checksum_verified"] = True
    if isinstance(binding.get("url"), str):
        result["url"] = binding["url"]
    return result


def load_metadata(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter=";")
        if (
            reader.fieldnames is None
            or not REQUIRED_COLUMNS.issubset(reader.fieldnames)
        ):
            raise ValueError("RWC metadata lacks required columns")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("RWC metadata contains malformed delimited rows")
    values: dict[str, dict[str, str]] = {}
    for row in rows:
        rwc_id = row["RWCID"]
        match = RWC_ID.fullmatch(rwc_id)
        piece_match = re.fullmatch(r"([0-9]+)([A-Z]?)", row["PieceNo"])
        expected_piece_id = (
            f"{int(piece_match.group(1)):03d}{piece_match.group(2)}"
            if piece_match is not None
            else None
        )
        if (
            match is None
            or match.group(1) != row["CollID"]
            or match.group(2) != expected_piece_id
            or rwc_id in values
        ):
            raise ValueError("RWC metadata identity differs")
        if not row["Artist"].strip():
            raise ValueError("RWC metadata contains an empty artist label")
        try:
            start = Decimal(row["audio_start"])
            end = Decimal(row["audio_end"])
            duration = Decimal(row["duration"])
        except InvalidOperation as error:
            raise ValueError("RWC metadata contains an invalid time") from error
        if (
            not all(value.is_finite() for value in (start, end, duration))
            or start < 0
            or end <= start
            or duration < end
        ):
            raise ValueError("RWC metadata audio window is invalid")
        values[rwc_id] = row
    return values


class DisjointSets:
    def __init__(self, values: set[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def family_boundary(
    metadata: dict[str, dict[str, str]], family_rules: dict[str, Any]
) -> tuple[set[str], dict[str, str]]:
    excluded: set[str] = set()
    exclusions = family_rules.get("eligibility_exclusions")
    if not isinstance(exclusions, list) or not exclusions:
        raise ValueError("RWC family exclusions are absent")
    for exclusion in exclusions:
        if not isinstance(exclusion, dict):
            raise ValueError("RWC family exclusion differs")
        collection = exclusion.get("collection_id")
        minimum = exclusion.get("piece_number_minimum")
        maximum = exclusion.get("piece_number_maximum")
        if (
            not isinstance(collection, str)
            or not isinstance(minimum, int)
            or not isinstance(maximum, int)
            or minimum > maximum
        ):
            raise ValueError("RWC family exclusion differs")
        matches = {
            rwc_id
            for rwc_id, row in metadata.items()
            if row["CollID"] == collection
            and minimum <= int(row["PieceNo"]) <= maximum
        }
        if matches & excluded:
            raise ValueError("RWC family exclusions overlap")
        excluded.update(matches)

    eligible_labels = {
        row["Artist"].strip()
        for rwc_id, row in metadata.items()
        if rwc_id not in excluded
    }
    families = DisjointSets(eligible_labels)
    merges = family_rules.get("family_merges")
    if not isinstance(merges, list):
        raise ValueError("RWC family merges are absent")
    for merge in merges:
        labels = merge.get("artist_labels") if isinstance(merge, dict) else None
        if (
            not isinstance(labels, list)
            or len(labels) < 2
            or not all(
                isinstance(label, str) and label in eligible_labels for label in labels
            )
        ):
            raise ValueError("RWC family merge differs")
        for label in labels[1:]:
            families.union(labels[0], label)
    family_by_rwc_id = {
        rwc_id: families.find(row["Artist"].strip())
        for rwc_id, row in metadata.items()
        if rwc_id not in excluded
    }
    return excluded, family_by_rwc_id


def canonical_directory_digest(rows: list[tuple[str, int, int, int]]) -> str:
    digest = hashlib.sha256()
    for filename, file_size, compress_size, crc in sorted(rows):
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(file_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(compress_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(f"{crc:08x}".encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def audit(
    audio_paths: list[Path],
    changelog_path: Path,
    metadata_path: Path,
    family_rules_path: Path,
    metadata_evidence_path: Path,
    rules_path: Path,
) -> dict[str, Any]:
    rules = load_object(rules_path)
    for field, expected_value in {
        "schema_version": 1,
        "state": "source_identity_rules_not_allocation",
        "source_id": SOURCE_ID,
        "audio_generated": False,
        "scores_opened": False,
        "selection_authorized": False,
    }.items():
        if rules.get(field) != expected_value:
            raise ValueError(f"RWC source-group rule {field} differs")
    if not isinstance(rules.get("provider_record"), dict) or not isinstance(
        rules.get("processing_chain"), str
    ) or not rules["processing_chain"]:
        raise ValueError("RWC provider provenance boundary differs")

    artifact_rules = rules.get("artifacts")
    if not isinstance(artifact_rules, list) or len(artifact_rules) != len(
        COLLECTION_IDS
    ):
        raise ValueError("RWC archive rules differ")
    rules_by_filename = {
        row.get("filename"): row for row in artifact_rules if isinstance(row, dict)
    }
    paths_by_filename = {path.name: path for path in audio_paths}
    expected_filenames = {f"RWC-{collection}.zip" for collection in COLLECTION_IDS}
    if (
        set(rules_by_filename) != expected_filenames
        or set(paths_by_filename) != expected_filenames
    ):
        raise ValueError("RWC archive filenames differ")
    archive_bindings = {
        filename: validate_file_binding(
            paths_by_filename[filename], rules_by_filename[filename], filename
        )
        for filename in sorted(expected_filenames)
    }

    changelog_binding = validate_file_binding(
        changelog_path, rules.get("changelog_artifact"), "changelog"
    )
    metadata_binding = rules.get("metadata_binding")
    if (
        not isinstance(metadata_binding, dict)
        or metadata_binding.get("filename") != metadata_path.name
        or metadata_binding.get("bytes") != metadata_path.stat().st_size
        or metadata_binding.get("sha256") != sha256_file(metadata_path)
    ):
        raise ValueError("RWC metadata binding differs")
    family_rules_binding = rules.get("artist_family_rules_binding")
    if (
        not isinstance(family_rules_binding, dict)
        or family_rules_binding.get("sha256") != sha256_file(family_rules_path)
    ):
        raise ValueError("RWC artist-family rules binding differs")
    metadata_evidence_binding = rules.get("metadata_identity_evidence_binding")
    if (
        not isinstance(metadata_evidence_binding, dict)
        or metadata_evidence_binding.get("sha256")
        != sha256_file(metadata_evidence_path)
    ):
        raise ValueError("RWC metadata evidence binding differs")

    family_rules = load_object(family_rules_path)
    metadata_evidence = load_object(metadata_evidence_path)
    if (
        family_rules.get("source_id") != SOURCE_ID
        or family_rules.get("state") != "source_identity_rules_not_allocation"
        or family_rules.get("metadata_revision") != metadata_binding.get("revision")
        or family_rules.get("metadata_sha256") != metadata_binding.get("sha256")
        or metadata_evidence.get("source_id") != SOURCE_ID
        or metadata_evidence.get("state")
        != "source_metadata_identity_evidence_only"
        or metadata_evidence.get("metadata_binding")
        != {
            "revision": metadata_binding.get("revision"),
            "sha256": metadata_binding.get("sha256"),
        }
    ):
        raise ValueError("RWC metadata identity boundary differs")
    metadata = load_metadata(metadata_path)
    excluded_ids, family_by_rwc_id = family_boundary(metadata, family_rules)

    expected = rules.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("RWC expected identities are absent")
    try:
        duration_tolerance = Decimal(
            str(expected.get("maximum_duration_error_samples"))
        )
    except InvalidOperation as error:
        raise ValueError("RWC duration tolerance differs") from error
    if not duration_tolerance.is_finite() or duration_tolerance <= 0:
        raise ValueError("RWC duration tolerance differs")

    audio_ids: set[str] = set()
    collection_file_counts: collections.Counter[str] = collections.Counter()
    directory_ids: dict[str, list[str]] = {}
    per_archive_directory_digests: dict[str, str] = {}
    frame_counts: list[int] = []
    frame_members: collections.defaultdict[int, list[str]] = (
        collections.defaultdict(list)
    )
    collection_frame_counts: collections.defaultdict[str, list[int]] = (
        collections.defaultdict(list)
    )
    data_byte_counts: list[int] = []
    pcm_digests: collections.Counter[str] = collections.Counter()
    pcm_digest_members: collections.defaultdict[str, list[str]] = (
        collections.defaultdict(list)
    )
    format_counts: collections.Counter[str] = collections.Counter()
    format_values: dict[str, dict[str, Any]] = {}
    duration_errors: dict[str, Decimal] = {}
    encrypted_member_count = 0
    special_member_count = 0
    uncompressed_audio_member_bytes = 0

    for collection in COLLECTION_IDS:
        filename = f"RWC-{collection}.zip"
        directory_rows: list[tuple[str, int, int, int]] = []
        archive_directories: set[str] = set()
        member_ids: set[str] = set()
        with zipfile.ZipFile(paths_by_filename[filename]) as archive:
            for info in archive.infolist():
                member_id = (
                    info.filename.rstrip("/") if info.is_dir() else info.filename
                )
                if member_id:
                    safe_member_id(member_id)
                if member_id in member_ids:
                    raise ValueError("RWC archive member path is duplicated")
                member_ids.add(member_id)
                directory_rows.append(
                    (info.filename, info.file_size, info.compress_size, info.CRC)
                )
                if info.flag_bits & 1:
                    encrypted_member_count += 1
                unix_mode = info.external_attr >> 16
                unix_file_type = stat.S_IFMT(unix_mode)
                if unix_file_type not in {0, stat.S_IFDIR, stat.S_IFREG}:
                    special_member_count += 1
                    continue
                if info.is_dir():
                    if info.file_size or info.CRC:
                        raise ValueError("RWC archive directory member is not empty")
                    archive_directories.add(member_id)
                    continue
                match = AUDIO_MEMBER.fullmatch(info.filename)
                if (
                    match is None
                    or match.group(1) != collection
                    or match.group(3) != collection
                ):
                    raise ValueError("RWC archive contains a noncanonical member")
                rwc_id = match.group(2)
                if rwc_id in audio_ids:
                    raise ValueError("RWC audio identity is duplicated")
                if rwc_id not in metadata or metadata[rwc_id]["CollID"] != collection:
                    raise ValueError("RWC audio identity is absent from metadata")
                audio_ids.add(rwc_id)
                collection_file_counts[collection] += 1
                with archive.open(info) as member:
                    wave = read_wave(member, info.file_size)
                uncompressed_audio_member_bytes += info.file_size
                pcm_digest = str(wave.pop("pcm_sha256"))
                frame_count = int(wave.pop("frame_count"))
                data_bytes = int(wave.pop("data_bytes"))
                pcm_digests[pcm_digest] += 1
                pcm_digest_members[pcm_digest].append(rwc_id)
                frame_counts.append(frame_count)
                frame_members[frame_count].append(rwc_id)
                collection_frame_counts[collection].append(frame_count)
                data_byte_counts.append(data_bytes)
                rate = int(wave["sample_rate_hz"])
                error_samples = abs(
                    Decimal(metadata[rwc_id]["duration"]) * rate - frame_count
                )
                if error_samples > duration_tolerance:
                    raise ValueError("RWC WAV duration differs from metadata")
                duration_errors[rwc_id] = error_samples
                format_key = json.dumps(wave, sort_keys=True, separators=(",", ":"))
                format_counts[format_key] += 1
                format_values[format_key] = wave
        expected_directory = {f"RWC-{collection}"}
        if archive_directories != expected_directory:
            raise ValueError("RWC archive directory identity differs")
        directory_ids[filename] = sorted(archive_directories)
        per_archive_directory_digests[filename] = canonical_directory_digest(
            directory_rows
        )
        archive_bindings[filename]["zip_crc_verified"] = True
        archive_bindings[filename]["central_directory_sha256"] = (
            per_archive_directory_digests[filename]
        )

    if encrypted_member_count or special_member_count:
        raise ValueError("RWC archives contain encrypted or special members")
    if audio_ids != set(metadata):
        raise ValueError("RWC audio and metadata identities differ")
    if len(metadata) != expected.get("metadata_row_count"):
        raise ValueError("RWC metadata row count differs")
    if dict(sorted(collection_file_counts.items())) != expected.get(
        "collection_audio_file_counts"
    ):
        raise ValueError("RWC collection file counts differ")

    observed_formats = []
    for key, count in sorted(format_counts.items()):
        row = dict(format_values[key])
        row["file_count"] = count
        observed_formats.append(row)
    expected_format = expected.get("audio_format")
    if not isinstance(expected_format, dict) or any(
        any(row.get(field) != value for field, value in expected_format.items())
        for row in observed_formats
    ):
        raise ValueError("RWC audio format differs")

    duplicate_pcm_groups = {
        digest: count for digest, count in pcm_digests.items() if count > 1
    }
    duplicate_pcm_excess = sum(count - 1 for count in duplicate_pcm_groups.values())
    duplicate_pcm_file_count_excluded = sum(duplicate_pcm_groups.values())
    if len(duplicate_pcm_groups) != expected.get("duplicate_pcm_digest_group_count"):
        raise ValueError("RWC duplicate PCM digest-group count differs")
    if duplicate_pcm_excess != expected.get("duplicate_pcm_file_count_excess"):
        raise ValueError("RWC duplicate PCM excess count differs")
    if duplicate_pcm_file_count_excluded != expected.get(
        "duplicate_pcm_file_count_excluded"
    ):
        raise ValueError("RWC duplicate PCM exclusion count differs")

    duplicate_ids = {
        rwc_id
        for digest in duplicate_pcm_groups
        for rwc_id in pcm_digest_members[digest]
    }
    eligible_ids = set(family_by_rwc_id) - duplicate_ids
    eligible_families = {family_by_rwc_id[rwc_id] for rwc_id in eligible_ids}
    if len(excluded_ids) != expected.get("known_instrumentation_variation_row_count"):
        raise ValueError("RWC metadata exclusion count differs")
    metadata_family_count = len(set(family_by_rwc_id.values()))
    if metadata_family_count != expected.get("metadata_artist_family_count"):
        raise ValueError("RWC metadata artist-family count differs")
    if len(eligible_families) != expected.get("source_group_count"):
        raise ValueError("RWC conservative source-group count differs")
    if metadata_evidence.get("conservative_group_boundary", {}).get(
        "eligible_group_count"
    ) != expected.get("metadata_artist_family_count"):
        raise ValueError("RWC metadata evidence group count differs")

    minimum_frames = min(frame_counts)
    maximum_frames = max(frame_counts)
    maximum_duration_error = max(duration_errors.values())
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "state": "source_identity_evidence_only",
        "source_id": SOURCE_ID,
        "benchmark_audio_generated": False,
        "scores_opened": False,
        "selection_authorized": False,
        "paths_redacted": True,
        "archive_bindings": archive_bindings,
        "changelog_binding": changelog_binding,
        "metadata_binding": {
            "bytes": metadata_binding.get("bytes"),
            "revision": metadata_binding.get("revision"),
            "sha256": metadata_binding.get("sha256"),
        },
        "artist_family_rules_binding": {
            "sha256": family_rules_binding.get("sha256")
        },
        "metadata_identity_evidence_binding": {
            "sha256": metadata_evidence_binding.get("sha256")
        },
        "source_group_rules_binding": {"sha256": sha256_file(rules_path)},
        "provider_record": rules.get("provider_record"),
        "processing_chain": rules.get("processing_chain"),
        "observed": {
            "audio_file_count": len(audio_ids),
            "collection_audio_file_counts": dict(
                sorted(collection_file_counts.items())
            ),
            "archive_directory_member_ids": directory_ids,
            "archive_central_directory_sha256": per_archive_directory_digests,
            "uncompressed_audio_member_bytes": uncompressed_audio_member_bytes,
            "riff_formats": observed_formats,
            "frame_count_range": {
                "minimum": minimum_frames,
                "minimum_rwc_ids": sorted(frame_members[minimum_frames]),
                "maximum": maximum_frames,
                "maximum_rwc_ids": sorted(frame_members[maximum_frames]),
            },
            "collection_frame_count_ranges": {
                collection: {
                    "minimum": min(values),
                    "maximum": max(values),
                }
                for collection, values in sorted(collection_frame_counts.items())
            },
            "data_byte_range": {
                "minimum": min(data_byte_counts),
                "maximum": max(data_byte_counts),
            },
            "metadata_duration_error_samples": {
                "maximum": format(maximum_duration_error, "f"),
                "maximum_rwc_ids": sorted(
                    rwc_id
                    for rwc_id, error in duration_errors.items()
                    if error == maximum_duration_error
                ),
                "required_maximum": format(duration_tolerance, "f"),
            },
            "distinct_pcm_digest_count": len(pcm_digests),
            "duplicate_pcm_digest_group_count": len(duplicate_pcm_groups),
            "duplicate_pcm_file_count_excess": duplicate_pcm_excess,
            "duplicate_pcm_file_count_excluded": duplicate_pcm_file_count_excluded,
            "duplicate_pcm_rwc_id_groups": sorted(
                sorted(pcm_digest_members[digest]) for digest in duplicate_pcm_groups
            ),
            "encrypted_member_count": encrypted_member_count,
            "special_member_count": special_member_count,
        },
        "conservative_reference_boundary": {
            "rule": [
                "canonical RWC-X/RWC_XNNN[SUFFIX].wav member",
                "exactly one matching RWCID in the bound annotation metadata",
                "WAV duration agrees with metadata within the fixed sample tolerance",
                "WAV matches the bound PCM format",
                "known RWC-J instrumentation-variation rows 1-35 are excluded",
                "every member of an exact repeated-PCM group is excluded",
            ],
            "eligible_audio_file_count": len(eligible_ids),
            "eligible_group_count": len(eligible_families),
            "metadata_artist_family_count": metadata_family_count,
            "known_instrumentation_variation_rows_excluded": len(excluded_ids),
            "source_grouping_unit": "artist family after declared merges",
            "partition_grouping_unit": "artist family after declared merges",
            "future_selection_constraint": (
                "At source freeze, select at most one bounded excerpt per artist "
                "family, never repeat a normalized work title, and preserve "
                "collection, "
                "family, work, legacy disc, track, and provider identity."
            ),
            "independence_limit": (
                "Artist families do not establish independent recording sessions, "
                "engineers, studios, or disjoint backing personnel. Keep RWC as one "
                "provider stratum and do not treat its track count as independent."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-zip", type=Path, action="append", required=True)
    parser.add_argument("--changelog", type=Path, required=True)
    parser.add_argument("--metadata-csv", type=Path, required=True)
    parser.add_argument("--family-rules", type=Path, required=True)
    parser.add_argument("--metadata-evidence", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(
        args.audio_zip,
        args.changelog,
        args.metadata_csv,
        args.family_rules,
        args.metadata_evidence,
        args.rules,
    )
    if args.output:
        write_json_atomic(args.output, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
