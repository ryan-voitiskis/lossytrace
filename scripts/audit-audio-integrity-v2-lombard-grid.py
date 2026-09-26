#!/usr/bin/env python3
"""Audit Lombard Grid source archives without generating benchmark audio.

The report is deliberately path-free.  It binds the downloaded archives,
reconciles the provider's WAV filenames with its JSON metadata, inventories
RIFF sample formats, and defines a conservative reference-eligibility rule.
It does not select excerpts or inspect any codec-history score.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import struct
import tempfile
import zipfile
from pathlib import Path
from typing import Any, BinaryIO


REPORT_SCHEMA_VERSION = 1
SOURCE_ID = "lombard_grid_2018"
PROVIDER_IDENTITIES = {
    "audio": {
        "method": "https_strong_etag_content_length_last_modified",
        "etag": '"26e61999-568649ce7ab80"',
        "last_modified": "Tue, 27 Mar 2018 13:10:22 GMT",
    },
    "metadata": {
        "method": "https_strong_etag_content_length_last_modified",
        "etag": '"fdaa-56864bb4da700"',
        "last_modified": "Tue, 27 Mar 2018 13:18:52 GMT",
    },
}
CANONICAL_AUDIO_NAME = re.compile(
    r"^lombardgrid/audio/(s\d+)_(l|p)_([a-z0-9]{6})\.wav$"
)
PREFIX_AUDIO_NAME = re.compile(
    r"^lombardgrid/audio/(s\d+)_(l|p)_([a-z0-9]+?)(?:_WRONG_.*)?\.wav$"
)
SPEAKER_AUDIO_NAME = re.compile(r"^lombardgrid/audio/(s\d+)_")
CONDITION_AUDIO_NAME = re.compile(r"^lombardgrid/audio/s\d+_(l|p)_")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def read_exact(source: BinaryIO, size: int) -> bytes:
    value = source.read(size)
    if len(value) != size:
        raise ValueError("truncated RIFF/WAVE member")
    return value


def read_wave_header(source: BinaryIO) -> dict[str, int | str]:
    header = read_exact(source, 12)
    if header[:4] != b"RIFF" or header[8:] != b"WAVE":
        raise ValueError("member is not a little-endian RIFF/WAVE file")
    format_fields: tuple[int, int, int, int, int, int] | None = None
    format_chunk_bytes: int | None = None
    data_bytes: int | None = None
    while True:
        chunk_header = source.read(8)
        if not chunk_header:
            break
        if len(chunk_header) != 8:
            raise ValueError("truncated RIFF chunk header")
        chunk_id = chunk_header[:4]
        chunk_size = struct.unpack("<I", chunk_header[4:])[0]
        if chunk_id == b"fmt ":
            payload = read_exact(source, chunk_size)
            if len(payload) < 16:
                raise ValueError("short WAVE format chunk")
            format_fields = struct.unpack("<HHIIHH", payload[:16])
            format_chunk_bytes = chunk_size
        elif chunk_id == b"data":
            data_bytes = chunk_size
            break
        else:
            read_exact(source, chunk_size)
        if chunk_size & 1:
            read_exact(source, 1)
    if format_fields is None or format_chunk_bytes is None or data_bytes is None:
        raise ValueError("WAVE member lacks format or data chunk")
    format_tag, channels, rate, average_bytes, block_align, bits = format_fields
    if block_align < 1 or data_bytes % block_align:
        raise ValueError("WAVE data size is not frame aligned")
    sample_format = {1: "signed_integer_pcm", 3: "ieee_float_pcm"}.get(
        format_tag, "other"
    )
    return {
        "format_tag": format_tag,
        "sample_format": sample_format,
        "channel_count": channels,
        "sample_rate_hz": rate,
        "bits_per_sample": bits,
        "block_align_bytes": block_align,
        "average_bytes_per_second": average_bytes,
        "format_chunk_bytes": format_chunk_bytes,
        "data_bytes": data_bytes,
        "frame_count": data_bytes // block_align,
    }


def load_metadata(metadata_archive: zipfile.ZipFile) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in sorted(metadata_archive.namelist()):
        if not name.endswith(".json"):
            continue
        value = json.loads(metadata_archive.read(name))
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
            raise ValueError(f"{name}: expected a list of metadata objects")
        rows.extend(value)
    return rows


def natural_speaker_order(speaker_id: str) -> int:
    return int(speaker_id[1:])


def sorted_counts(counter: collections.Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))


def audit(audio_path: Path, metadata_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(audio_path) as audio_archive, zipfile.ZipFile(
        metadata_path
    ) as metadata_archive:
        bad_audio_member = audio_archive.testzip()
        bad_metadata_member = metadata_archive.testzip()
        if bad_audio_member or bad_metadata_member:
            raise ValueError(
                f"CRC failure in {bad_audio_member or bad_metadata_member}"
            )
        metadata_rows = load_metadata(metadata_archive)
        audio_members = [row for row in audio_archive.infolist() if not row.is_dir()]

        metadata_status = collections.Counter(str(row.get("STATUS")) for row in metadata_rows)
        metadata_speakers = collections.Counter(str(row.get("SPKR")) for row in metadata_rows)
        metadata_conditions = collections.Counter(str(row.get("COND")) for row in metadata_rows)
        correct_metadata_keys = collections.Counter(
            (str(row.get("SPKR")), str(row.get("COND")), str(row.get("UTTERANCE")))
            for row in metadata_rows
            if row.get("STATUS") == "CORRECT"
        )
        all_metadata_keys = collections.Counter(
            (str(row.get("SPKR")), str(row.get("COND")), str(row.get("UTTERANCE")))
            for row in metadata_rows
        )

        audio_speakers: collections.Counter[str] = collections.Counter()
        audio_conditions: collections.Counter[str] = collections.Counter()
        audio_keys: collections.Counter[tuple[str, str, str]] = collections.Counter()
        format_counts: collections.Counter[str] = collections.Counter()
        format_values: dict[str, dict[str, int | str]] = {}
        format_speakers: collections.defaultdict[str, set[str]] = (
            collections.defaultdict(set)
        )
        speaker_sample_formats: collections.defaultdict[str, set[str]] = (
            collections.defaultdict(set)
        )
        wrong_suffix_count = 0
        noncanonical_count = 0
        ambiguous_or_unmapped_count = 0
        eligible_count = 0
        eligible_speakers: collections.Counter[str] = collections.Counter()
        frame_minimum: int | None = None
        frame_maximum: int | None = None
        uncompressed_member_bytes = 0

        for member in audio_members:
            uncompressed_member_bytes += member.file_size
            with audio_archive.open(member) as source:
                wave_header = read_wave_header(source)
            format_identity = dict(wave_header)
            format_identity.pop("data_bytes")
            format_identity.pop("frame_count")
            format_key = json.dumps(
                format_identity, sort_keys=True, separators=(",", ":")
            )
            format_counts[format_key] += 1
            format_values[format_key] = format_identity
            frames = int(wave_header["frame_count"])
            frame_minimum = frames if frame_minimum is None else min(frame_minimum, frames)
            frame_maximum = frames if frame_maximum is None else max(frame_maximum, frames)

            speaker_match = SPEAKER_AUDIO_NAME.match(member.filename)
            if speaker_match:
                speaker_id = speaker_match.group(1)
                audio_speakers[speaker_id] += 1
                format_speakers[format_key].add(speaker_id)
                speaker_sample_formats[speaker_id].add(str(wave_header["sample_format"]))
            condition_match = CONDITION_AUDIO_NAME.match(member.filename)
            if condition_match:
                audio_conditions[condition_match.group(1)] += 1
            prefix = PREFIX_AUDIO_NAME.fullmatch(member.filename)
            if prefix:
                speaker, condition, utterance = prefix.groups()
                audio_keys[(speaker, condition, utterance)] += 1
            if "_WRONG_" in member.filename:
                wrong_suffix_count += 1

            canonical = CANONICAL_AUDIO_NAME.fullmatch(member.filename)
            if canonical is None:
                noncanonical_count += 1
                continue
            key = canonical.groups()
            if correct_metadata_keys[key] != 1:
                ambiguous_or_unmapped_count += 1
                continue
            eligible_count += 1
            eligible_speakers[key[0]] += 1

        audio_without_metadata = audio_keys - all_metadata_keys
        metadata_without_audio = all_metadata_keys - audio_keys
        duplicate_metadata_keys = sum(
            count - 1 for count in all_metadata_keys.values() if count > 1
        )
        riff_formats = []
        for key, count in sorted(format_counts.items()):
            row = dict(format_values[key])
            row["file_count"] = count
            row["talker_count"] = len(format_speakers[key])
            riff_formats.append(row)
        representation_profiles = collections.Counter(
            "+".join(sorted(formats)) for formats in speaker_sample_formats.values()
        )

        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "state": "source_identity_evidence_only",
            "source_id": SOURCE_ID,
            "benchmark_audio_generated": False,
            "scores_opened": False,
            "selection_authorized": False,
            "paths_redacted": True,
            "archive_bindings": {
                "audio": {
                    "bytes": audio_path.stat().st_size,
                    "sha256": sha256_file(audio_path),
                    "provider_identity": PROVIDER_IDENTITIES["audio"],
                    "zip_crc_verified": True,
                },
                "metadata": {
                    "bytes": metadata_path.stat().st_size,
                    "sha256": sha256_file(metadata_path),
                    "provider_identity": PROVIDER_IDENTITIES["metadata"],
                    "zip_crc_verified": True,
                },
            },
            "observed": {
                "audio_file_count": len(audio_members),
                "audio_uncompressed_member_bytes": uncompressed_member_bytes,
                "audio_talker_count": len(audio_speakers),
                "audio_condition_counts": sorted_counts(audio_conditions),
                "audio_condition_unparseable_file_count": len(audio_members)
                - sum(audio_conditions.values()),
                "audio_files_per_talker": dict(
                    sorted(audio_speakers.items(), key=lambda row: natural_speaker_order(row[0]))
                ),
                "metadata_json_file_count": sum(
                    name.endswith(".json") for name in metadata_archive.namelist()
                ),
                "metadata_row_count": len(metadata_rows),
                "metadata_talker_count": len(metadata_speakers),
                "metadata_condition_counts": sorted_counts(metadata_conditions),
                "metadata_status_counts": sorted_counts(metadata_status),
                "metadata_rows_per_talker": dict(
                    sorted(
                        metadata_speakers.items(),
                        key=lambda row: natural_speaker_order(row[0]),
                    )
                ),
                "riff_formats": riff_formats,
                "talker_sample_representation_profile_counts": sorted_counts(
                    representation_profiles
                ),
                "frame_count_minimum": frame_minimum,
                "frame_count_maximum": frame_maximum,
            },
            "reconciliation": {
                "provider_headline_utterance_count": 5400,
                "audio_minus_headline": len(audio_members) - 5400,
                "metadata_minus_headline": len(metadata_rows) - 5400,
                "audio_key_occurrences_without_metadata": sum(audio_without_metadata.values()),
                "metadata_key_occurrences_without_audio": sum(metadata_without_audio.values()),
                "duplicate_metadata_key_excess_rows": duplicate_metadata_keys,
                "wrong_suffix_audio_file_count": wrong_suffix_count,
            },
            "conservative_reference_boundary": {
                "rule": [
                    "canonical filename sNN_{l|p}_{six-character-grid-code}.wav",
                    "exactly one matching metadata key",
                    "matching metadata status CORRECT",
                ],
                "eligible_audio_file_count": eligible_count,
                "eligible_talker_count": len(eligible_speakers),
                "eligible_files_per_talker_minimum": min(eligible_speakers.values()),
                "eligible_files_per_talker_maximum": max(eligible_speakers.values()),
                "excluded_noncanonical_filename_count": noncanonical_count,
                "excluded_ambiguous_or_unmapped_metadata_count": ambiguous_or_unmapped_count,
            },
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-zip", type=Path, required=True)
    parser.add_argument("--metadata-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(args.audio_zip, args.metadata_zip)
    if args.output:
        write_json_atomic(args.output, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
