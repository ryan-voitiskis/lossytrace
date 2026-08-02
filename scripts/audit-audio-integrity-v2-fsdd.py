#!/usr/bin/env python3
"""Audit FSDD v1.0.10 source identities without selecting benchmark audio."""

from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import re
import stat
import struct
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


REPORT_SCHEMA_VERSION = 1
SOURCE_ID = "fsdd_v1_0_10"
AUDIO_MEMBER = re.compile(r"^recordings/([0-9])_([a-z]+)_([0-9]+)\.wav$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def safe_member_id(value: str) -> str:
    member = PurePosixPath(value)
    if (
        not value
        or member.is_absolute()
        or ".." in member.parts
        or member.as_posix() != value
    ):
        raise ValueError("FSDD archive contains an unsafe or noncanonical path")
    return value


def read_wave(payload: bytes) -> dict[str, int | str | dict[str, int]]:
    if len(payload) < 12 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise ValueError("FSDD member is not a little-endian RIFF/WAVE file")
    if struct.unpack("<I", payload[4:8])[0] + 8 != len(payload):
        raise ValueError("FSDD RIFF size does not equal member size")
    offset = 12
    format_payload: bytes | None = None
    pcm_payload: bytes | None = None
    ancillary_chunks: collections.Counter[str] = collections.Counter()
    while offset < len(payload):
        if offset + 8 > len(payload):
            raise ValueError("FSDD has a truncated RIFF chunk header")
        chunk_id_bytes = payload[offset : offset + 4]
        chunk_size = struct.unpack("<I", payload[offset + 4 : offset + 8])[0]
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_size
        if chunk_end > len(payload):
            raise ValueError("FSDD has a truncated RIFF chunk")
        chunk = payload[chunk_start:chunk_end]
        if chunk_id_bytes == b"fmt ":
            if format_payload is not None or len(chunk) < 16:
                raise ValueError("FSDD has an invalid or duplicate format chunk")
            format_payload = chunk
        elif chunk_id_bytes == b"data":
            if pcm_payload is not None:
                raise ValueError("FSDD has a duplicate data chunk")
            pcm_payload = chunk
        else:
            ancillary_chunks[chunk_id_bytes.decode("latin-1")] += 1
        offset = chunk_end + (chunk_size & 1)
    if offset != len(payload):
        raise ValueError("FSDD has invalid RIFF padding")
    if format_payload is None or pcm_payload is None:
        raise ValueError("FSDD member lacks a format or data chunk")
    format_tag, channels, rate, average_bytes, block_align, bits = struct.unpack(
        "<HHIIHH", format_payload[:16]
    )
    if block_align < 1 or len(pcm_payload) % block_align:
        raise ValueError("FSDD data size is not frame aligned")
    if average_bytes != rate * block_align:
        raise ValueError("FSDD average byte rate is inconsistent")
    if format_tag == 1 and block_align != channels * ((bits + 7) // 8):
        raise ValueError("FSDD PCM block alignment is inconsistent")
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
        "data_bytes": len(pcm_payload),
        "frame_count": len(pcm_payload) // block_align,
        "pcm_sha256": hashlib.sha256(pcm_payload).hexdigest(),
    }


def parse_speaker_metadata(payload: bytes, expected_speakers: set[str]) -> None:
    try:
        module = ast.parse(payload.decode("utf-8"), filename="metadata.py")
    except (SyntaxError, UnicodeDecodeError) as error:
        raise ValueError("FSDD speaker metadata is not valid Python source") from error
    assignments = [
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "metadata"
    ]
    if len(assignments) != 1:
        raise ValueError("FSDD speaker metadata assignment differs")
    try:
        metadata = ast.literal_eval(assignments[0].value)
    except (ValueError, SyntaxError) as error:
        raise ValueError("FSDD speaker metadata is not literal data") from error
    if not isinstance(metadata, dict) or set(metadata) != expected_speakers:
        raise ValueError("FSDD speaker metadata identities differ")
    for speaker_id, values in metadata.items():
        if (
            not isinstance(speaker_id, str)
            or not isinstance(values, dict)
            or set(values) != {"gender", "accent", "language"}
            or not all(isinstance(value, str) and value for value in values.values())
        ):
            raise ValueError("FSDD speaker metadata fields differ")


def format_rows(
    counts: collections.Counter[str], values: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, count in sorted(counts.items()):
        row = dict(values[key])
        row["file_count"] = count
        rows.append(row)
    return rows


def audit(archive_path: Path, rules_path: Path) -> dict[str, Any]:
    rules = load_object(rules_path)
    if rules.get("schema_version") != 1:
        raise ValueError("unsupported FSDD source-group rule schema")
    for field, expected_value in {
        "state": "source_identity_rules_not_allocation",
        "source_id": SOURCE_ID,
        "repository": "Jakobovski/free-spoken-digit-dataset",
        "tag": "v1.0.10",
        "audio_generated": False,
        "scores_opened": False,
        "selection_authorized": False,
    }.items():
        if rules.get(field) != expected_value:
            raise ValueError(f"FSDD source-group rule {field} differs")

    artifact = rules.get("artifact")
    if not isinstance(artifact, dict) or artifact.get("filename") != archive_path.name:
        raise ValueError("FSDD artifact identity differs")
    local_sha256 = sha256_file(archive_path)
    if (
        archive_path.stat().st_size != artifact.get("bytes")
        or local_sha256 != artifact.get("local_sha256")
    ):
        raise ValueError("FSDD artifact binding differs")
    provider_identity = artifact.get("provider_identity")
    if not isinstance(provider_identity, dict) or provider_identity != {
        "method": "github_codeload_tag_commit_strong_etag",
        "tag": "v1.0.10",
        "commit_sha": "d6938f9bf1545aa66d8489fc9f1385a7abd64282",
        "etag": (
            '"248f3f5caf01524ccd38bd74a1dac661854fd431de2abae9757c49b9fe1142f7"'
        ),
    }:
        raise ValueError("FSDD provider identity differs")

    expected = rules.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("FSDD expected counts are absent")
    expected_speakers_raw = expected.get("speaker_ids")
    expected_digits_raw = expected.get("digit_ids")
    expected_indices_raw = expected.get("index_ids")
    if not all(
        isinstance(value, list)
        for value in (
            expected_speakers_raw,
            expected_digits_raw,
            expected_indices_raw,
        )
    ):
        raise ValueError("FSDD factor rules are absent")
    expected_speakers = {str(value) for value in expected_speakers_raw}
    expected_digits = {int(value) for value in expected_digits_raw}
    expected_indices = {int(value) for value in expected_indices_raw}
    if (
        not expected_speakers
        or not expected_digits
        or not expected_indices
        or len(expected_speakers) != len(expected_speakers_raw)
        or len(expected_digits) != len(expected_digits_raw)
        or len(expected_indices) != len(expected_indices_raw)
        or len(expected_speakers) != expected.get("source_group_count")
        or any(value < 0 or value > 9 for value in expected_digits)
        or any(value < 0 for value in expected_indices)
        or len(expected_indices) != expected.get("files_per_digit_speaker")
    ):
        raise ValueError("FSDD factor rules differ")

    root_prefix = expected.get("archive_root_prefix")
    if not isinstance(root_prefix, str) or not root_prefix:
        raise ValueError("FSDD archive root-prefix rule is absent")
    expected_directories_raw = expected.get("archive_directory_member_ids")
    if not isinstance(expected_directories_raw, list):
        raise ValueError("FSDD directory-member rules are absent")
    expected_directories = {str(value) for value in expected_directories_raw}

    non_audio_rules = expected.get("non_audio_regular_members")
    if not isinstance(non_audio_rules, list):
        raise ValueError("FSDD non-audio member rules are absent")
    expected_non_audio: dict[str, dict[str, Any]] = {}
    for rule in non_audio_rules:
        if (
            not isinstance(rule, dict)
            or not isinstance(rule.get("path"), str)
            or not isinstance(rule.get("bytes"), int)
            or not re.fullmatch(r"[0-9a-f]{64}", str(rule.get("sha256", "")))
        ):
            raise ValueError("FSDD non-audio member rule is invalid")
        member_id = safe_member_id(str(rule["path"]))
        if member_id in expected_non_audio:
            raise ValueError("FSDD non-audio member rule is duplicated")
        expected_non_audio[member_id] = rule

    processing_chain_raw = expected.get("processing_chain_member_ids")
    if not isinstance(processing_chain_raw, list):
        raise ValueError("FSDD processing-chain rules are absent")
    processing_chain_ids = {str(value) for value in processing_chain_raw}
    if not processing_chain_ids <= set(expected_non_audio):
        raise ValueError("FSDD processing-chain member rule differs")

    observed_member_ids: set[str] = set()
    observed_directories: set[str] = set()
    observed_non_audio: dict[str, dict[str, Any]] = {}
    processing_payloads: dict[str, bytes] = {}
    audio_member_ids: set[str] = set()
    factor_keys: set[tuple[int, str, int]] = set()
    speaker_counts: collections.Counter[str] = collections.Counter()
    digit_counts: collections.Counter[str] = collections.Counter()
    index_counts: collections.Counter[str] = collections.Counter()
    speaker_digit_counts: collections.Counter[tuple[str, int]] = (
        collections.Counter()
    )
    frame_counts: list[int] = []
    frame_count_members: collections.defaultdict[int, list[str]] = (
        collections.defaultdict(list)
    )
    data_byte_counts: list[int] = []
    speaker_frame_counts: collections.defaultdict[str, list[int]] = (
        collections.defaultdict(list)
    )
    pcm_digests: collections.Counter[str] = collections.Counter()
    pcm_digest_members: collections.defaultdict[str, list[str]] = (
        collections.defaultdict(list)
    )
    format_counts: collections.Counter[str] = collections.Counter()
    format_values: dict[str, dict[str, Any]] = {}
    uncompressed_audio_member_bytes = 0
    regular_file_count = 0
    encrypted_member_count = 0
    special_member_count = 0

    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            if not info.filename.startswith(root_prefix):
                raise ValueError("FSDD archive member root prefix differs")
            raw_member_id = info.filename[len(root_prefix) :]
            member_id = raw_member_id.rstrip("/") if info.is_dir() else raw_member_id
            if member_id:
                safe_member_id(member_id)
            if member_id in observed_member_ids:
                raise ValueError("FSDD archive member path is duplicated")
            observed_member_ids.add(member_id)
            if info.flag_bits & 1:
                encrypted_member_count += 1
            unix_type = (info.external_attr >> 16) & 0o170000
            if unix_type and not (
                stat.S_ISDIR(info.external_attr >> 16)
                or stat.S_ISREG(info.external_attr >> 16)
            ):
                special_member_count += 1
                continue
            if info.is_dir():
                observed_directories.add(member_id)
                continue

            regular_file_count += 1
            payload = archive.read(info)
            if len(payload) != info.file_size:
                raise ValueError("FSDD archive member size differs")
            audio_match = AUDIO_MEMBER.fullmatch(member_id)
            if audio_match is None:
                rule = expected_non_audio.get(member_id)
                if rule is None:
                    raise ValueError("FSDD archive contains an unexpected regular member")
                digest = hashlib.sha256(payload).hexdigest()
                if info.file_size != rule["bytes"] or digest != rule["sha256"]:
                    raise ValueError("FSDD non-audio member binding differs")
                observed_non_audio[member_id] = {
                    "path": member_id,
                    "bytes": info.file_size,
                    "sha256": digest,
                }
                if member_id in processing_chain_ids:
                    processing_payloads[member_id] = payload
                continue

            digit = int(audio_match.group(1))
            speaker_id = audio_match.group(2)
            index = int(audio_match.group(3))
            if (
                digit not in expected_digits
                or speaker_id not in expected_speakers
                or index not in expected_indices
            ):
                raise ValueError("FSDD audio filename factor differs")
            factor_key = (digit, speaker_id, index)
            if factor_key in factor_keys:
                raise ValueError("FSDD audio factor key is duplicated")
            factor_keys.add(factor_key)
            audio_member_ids.add(member_id)
            speaker_counts[speaker_id] += 1
            digit_counts[str(digit)] += 1
            index_counts[str(index)] += 1
            speaker_digit_counts[(speaker_id, digit)] += 1

            wave = read_wave(payload)
            pcm_digest = str(wave.pop("pcm_sha256"))
            pcm_digests[pcm_digest] += 1
            pcm_digest_members[pcm_digest].append(member_id)
            frame_count = int(wave.pop("frame_count"))
            data_bytes = int(wave.pop("data_bytes"))
            frame_counts.append(frame_count)
            frame_count_members[frame_count].append(member_id)
            data_byte_counts.append(data_bytes)
            speaker_frame_counts[speaker_id].append(frame_count)
            uncompressed_audio_member_bytes += info.file_size
            format_identity = dict(wave)
            format_key = json.dumps(
                format_identity, sort_keys=True, separators=(",", ":")
            )
            format_counts[format_key] += 1
            format_values[format_key] = format_identity

    if encrypted_member_count or special_member_count:
        raise ValueError("FSDD archive contains encrypted or special members")
    if observed_directories != expected_directories:
        raise ValueError("FSDD directory member identities differ")
    if set(observed_non_audio) != set(expected_non_audio):
        raise ValueError("FSDD non-audio member identities differ")
    if regular_file_count != expected.get("regular_file_count"):
        raise ValueError("FSDD regular file count differs")
    if len(audio_member_ids) != expected.get("audio_file_count"):
        raise ValueError("FSDD audio file count differs")
    expected_files_per_speaker = len(expected_digits) * len(expected_indices)
    if speaker_counts != collections.Counter(
        {speaker: expected_files_per_speaker for speaker in expected_speakers}
    ):
        raise ValueError("FSDD speaker audio counts differ")
    expected_files_per_digit = len(expected_speakers) * len(expected_indices)
    if digit_counts != collections.Counter(
        {str(digit): expected_files_per_digit for digit in expected_digits}
    ):
        raise ValueError("FSDD digit audio counts differ")
    expected_files_per_index = len(expected_speakers) * len(expected_digits)
    if index_counts != collections.Counter(
        {str(index): expected_files_per_index for index in expected_indices}
    ):
        raise ValueError("FSDD repetition-index counts differ")
    if any(
        count != expected.get("files_per_digit_speaker")
        for count in speaker_digit_counts.values()
    ) or len(speaker_digit_counts) != len(expected_speakers) * len(expected_digits):
        raise ValueError("FSDD speaker-digit cell counts differ")

    metadata_payload = processing_payloads.get("metadata.py")
    if metadata_payload is None:
        raise ValueError("FSDD speaker metadata binding is absent")
    parse_speaker_metadata(metadata_payload, expected_speakers)
    if set(processing_payloads) != processing_chain_ids:
        raise ValueError("FSDD processing-chain bindings differ")

    observed_formats = format_rows(format_counts, format_values)
    expected_format = expected.get("audio_format")
    if not isinstance(expected_format, dict) or len(observed_formats) != 1:
        raise ValueError("FSDD audio format count differs")
    if any(
        observed_formats[0].get(field) != value
        for field, value in expected_format.items()
    ):
        raise ValueError("FSDD audio format differs")

    duplicate_pcm_groups = {
        digest: count for digest, count in pcm_digests.items() if count > 1
    }
    if len(pcm_digests) != len(audio_member_ids):
        raise ValueError("FSDD archive contains duplicate PCM payloads")
    eligible_speaker_count = len(
        {
            AUDIO_MEMBER.fullmatch(member_id).group(2)
            for digest, member_ids in pcm_digest_members.items()
            if pcm_digests[digest] == 1
            for member_id in member_ids
            if AUDIO_MEMBER.fullmatch(member_id) is not None
        }
    )
    if eligible_speaker_count != expected.get("source_group_count"):
        raise ValueError("FSDD eligible speaker count differs")

    minimum_frames = min(frame_counts)
    maximum_frames = max(frame_counts)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "state": "source_identity_evidence_only",
        "source_id": SOURCE_ID,
        "benchmark_audio_generated": False,
        "scores_opened": False,
        "selection_authorized": False,
        "paths_redacted": True,
        "provider_record": {
            "repository": rules["repository"],
            "tag": rules["tag"],
            "commit_sha": provider_identity["commit_sha"],
        },
        "archive_binding": {
            "filename": archive_path.name,
            "bytes": archive_path.stat().st_size,
            "local_sha256": local_sha256,
            "provider_identity": provider_identity,
            "zip_crc_verified": True,
        },
        "source_group_rules_binding": {"sha256": sha256_file(rules_path)},
        "processing_chain_bindings": [
            observed_non_audio[member_id]
            for member_id in sorted(processing_chain_ids)
        ],
        "observed": {
            "archive_root_prefix": root_prefix,
            "directory_member_ids": sorted(observed_directories),
            "directory_member_count": len(observed_directories),
            "regular_file_count": regular_file_count,
            "non_audio_regular_members": [
                observed_non_audio[member_id]
                for member_id in sorted(observed_non_audio)
            ],
            "non_audio_regular_member_count": len(observed_non_audio),
            "audio_file_count": len(audio_member_ids),
            "speaker_ids": sorted(speaker_counts),
            "speaker_count": len(speaker_counts),
            "speaker_audio_file_counts": dict(sorted(speaker_counts.items())),
            "digit_audio_file_counts": dict(sorted(digit_counts.items())),
            "repetition_index_audio_file_counts": dict(
                sorted(index_counts.items(), key=lambda row: int(row[0]))
            ),
            "speaker_digit_cells_complete": True,
            "speaker_metadata_identities_match_audio": True,
            "uncompressed_audio_member_bytes": uncompressed_audio_member_bytes,
            "riff_formats": observed_formats,
            "frame_count_range": {
                "minimum": minimum_frames,
                "minimum_archive_member_ids": sorted(
                    frame_count_members[minimum_frames]
                ),
                "maximum": maximum_frames,
                "maximum_archive_member_ids": sorted(
                    frame_count_members[maximum_frames]
                ),
            },
            "speaker_frame_count_ranges": {
                speaker_id: {
                    "minimum": min(values),
                    "maximum": max(values),
                }
                for speaker_id, values in sorted(speaker_frame_counts.items())
            },
            "data_byte_range": {
                "minimum": min(data_byte_counts),
                "maximum": max(data_byte_counts),
            },
            "distinct_pcm_digest_count": len(pcm_digests),
            "duplicate_pcm_digest_group_count": len(duplicate_pcm_groups),
            "duplicate_pcm_file_count_excess": sum(
                count - 1 for count in duplicate_pcm_groups.values()
            ),
            "duplicate_pcm_archive_member_groups": sorted(
                sorted(pcm_digest_members[digest]) for digest in duplicate_pcm_groups
            ),
            "encrypted_member_count": encrypted_member_count,
            "special_member_count": special_member_count,
        },
        "conservative_reference_boundary": {
            "rule": [
                "archive member matches one complete digit-speaker-index cell",
                "speaker identifier occurs in the bound repository metadata",
                "WAV is mono 8 kHz signed 16-bit integer PCM",
                "PCM digest occurs exactly once across the archive",
            ],
            "eligible_audio_file_count": len(audio_member_ids),
            "eligible_group_count": eligible_speaker_count,
            "source_grouping_unit": "repository speaker identifier",
            "partition_grouping_unit": "repository speaker identifier",
            "future_selection_constraint": (
                "Use at most one bounded reference excerpt per speaker. Preserve "
                "digit and repetition index, retain 8 kHz bandwidth as an explicit "
                "factor, and do not infer microphone or Audacity settings that the "
                "repository does not identify."
            ),
            "independence_limit": (
                "The repository identifies six speakers but not recording devices, "
                "Audacity versions, dates, rooms, or contributor-specific settings. "
                "Keep FSDD as one provider stratum and do not treat its 3,000 clips "
                "as independent source partitions."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(args.archive, args.rules)
    if args.output:
        write_json_atomic(args.output, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
