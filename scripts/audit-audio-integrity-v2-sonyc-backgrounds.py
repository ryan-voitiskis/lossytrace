#!/usr/bin/env python3
"""Audit SONYC-Backgrounds identities without extracting or selecting audio.

The audit streams the retained tarball, validates its provider checksum and
WAVE members, and reports only path-free source-identity evidence. It does not
generate benchmark audio or inspect any codec-history measurement.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import io
import json
import re
import struct
import tarfile
import tempfile
from pathlib import Path
from typing import Any


REPORT_SCHEMA_VERSION = 1
SOURCE_ID = "sonyc_backgrounds_1_0_0"
README_MEMBER = "SONYC-Backgrounds/README.md"
AUDIO_MEMBER = re.compile(
    r"^SONYC-Backgrounds/(train|valid|test)/"
    r"(\d{2})_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})\.wav$"
)
README_COUNT = re.compile(r"obtain\s+(\d+)\s+background clips", re.IGNORECASE)


def hash_file(path: Path) -> tuple[str, str]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            md5.update(chunk)
            sha256.update(chunk)
    return md5.hexdigest(), sha256.hexdigest()


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
    declared_size = struct.unpack("<I", payload[4:8])[0] + 8
    if declared_size != len(payload):
        raise ValueError("RIFF size does not equal member size")

    offset = 12
    format_fields: tuple[int, int, int, int, int, int] | None = None
    format_chunk_bytes: int | None = None
    pcm_payload: bytes | None = None
    ancillary_chunk_count = 0
    while offset < len(payload):
        if offset + 8 > len(payload):
            raise ValueError("truncated RIFF chunk header")
        chunk_id = payload[offset : offset + 4]
        chunk_size = struct.unpack("<I", payload[offset + 4 : offset + 8])[0]
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_size
        if chunk_end > len(payload):
            raise ValueError("truncated RIFF chunk")
        chunk = payload[chunk_start:chunk_end]
        if chunk_id == b"fmt ":
            if format_fields is not None or len(chunk) < 16:
                raise ValueError("invalid or duplicate WAVE format chunk")
            format_fields = struct.unpack("<HHIIHH", chunk[:16])
            format_chunk_bytes = chunk_size
        elif chunk_id == b"data":
            if pcm_payload is not None:
                raise ValueError("duplicate WAVE data chunk")
            pcm_payload = chunk
        else:
            ancillary_chunk_count += 1
        offset = chunk_end + (chunk_size & 1)
    if offset != len(payload):
        raise ValueError("invalid RIFF padding")
    if format_fields is None or format_chunk_bytes is None or pcm_payload is None:
        raise ValueError("WAVE member lacks format or data chunk")

    format_tag, channels, rate, average_bytes, block_align, bits = format_fields
    if block_align < 1 or len(pcm_payload) % block_align:
        raise ValueError("WAVE data size is not frame aligned")
    if average_bytes != rate * block_align:
        raise ValueError("WAVE average byte rate is inconsistent")
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
        "ancillary_chunk_count": ancillary_chunk_count,
        "data_bytes": len(pcm_payload),
        "frame_count": len(pcm_payload) // block_align,
        "pcm_sha256": hashlib.sha256(pcm_payload).hexdigest(),
    }


def sorted_counts(counter: collections.Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))


def audit(
    archive_path: Path, expected_bytes: int, expected_provider_md5: str
) -> dict[str, Any]:
    if archive_path.stat().st_size != expected_bytes:
        raise ValueError("archive byte count differs from provider binding")
    provider_md5, local_sha256 = hash_file(archive_path)
    if provider_md5 != expected_provider_md5:
        raise ValueError("archive MD5 differs from provider binding")

    split_clips: collections.Counter[str] = collections.Counter()
    split_sensors: collections.defaultdict[str, set[str]] = collections.defaultdict(set)
    sensor_clips: collections.Counter[str] = collections.Counter()
    sensor_splits: collections.defaultdict[str, set[str]] = collections.defaultdict(set)
    format_counts: collections.Counter[str] = collections.Counter()
    format_values: dict[str, dict[str, int | str]] = {}
    pcm_digests: collections.Counter[str] = collections.Counter()
    pcm_digest_sensors: collections.defaultdict[str, set[str]] = (
        collections.defaultdict(set)
    )
    observation_keys: collections.Counter[tuple[str, str, str, str]] = (
        collections.Counter()
    )
    readme_payload: bytes | None = None
    regular_member_count = 0
    directory_member_count = 0
    unexpected_regular_members: list[str] = []
    uncompressed_audio_bytes = 0
    frame_minimum: int | None = None
    frame_maximum: int | None = None
    date_minimum: dt.date | None = None
    date_maximum: dt.date | None = None

    with tarfile.open(archive_path, mode="r|gz") as archive:
        for member in archive:
            if member.isdir():
                directory_member_count += 1
                continue
            if not member.isfile():
                raise ValueError("archive contains a non-file, non-directory member")
            regular_member_count += 1
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("regular tar member could not be read")
            payload = source.read()
            if len(payload) != member.size:
                raise ValueError("tar member size differs from extracted bytes")
            if member.name == README_MEMBER:
                readme_payload = payload
                continue

            match = AUDIO_MEMBER.fullmatch(member.name)
            if match is None:
                unexpected_regular_members.append(member.name)
                continue
            split, sensor, date_text, hour, instance = match.groups()
            observed_date = dt.date.fromisoformat(date_text)
            if observed_date.year != 2017:
                raise ValueError("audio filename is outside the documented 2017 source year")
            if not 0 <= int(hour) <= 23:
                raise ValueError("audio filename has an invalid hour")
            observation_keys[(sensor, date_text, hour, instance)] += 1
            split_clips[split] += 1
            split_sensors[split].add(sensor)
            sensor_clips[sensor] += 1
            sensor_splits[sensor].add(split)
            uncompressed_audio_bytes += member.size
            date_minimum = (
                observed_date if date_minimum is None else min(date_minimum, observed_date)
            )
            date_maximum = (
                observed_date if date_maximum is None else max(date_maximum, observed_date)
            )

            wave = read_wave(payload)
            pcm_digest = str(wave.pop("pcm_sha256"))
            pcm_digests[pcm_digest] += 1
            pcm_digest_sensors[pcm_digest].add(sensor)
            frames = int(wave["frame_count"])
            frame_minimum = frames if frame_minimum is None else min(frame_minimum, frames)
            frame_maximum = frames if frame_maximum is None else max(frame_maximum, frames)
            format_key = json.dumps(wave, sort_keys=True, separators=(",", ":"))
            format_counts[format_key] += 1
            format_values[format_key] = wave

    if readme_payload is None:
        raise ValueError("archive README is absent")
    readme_text = readme_payload.decode("utf-8")
    readme_count_match = README_COUNT.search(readme_text)
    if readme_count_match is None:
        raise ValueError("archive README clip count is absent")
    readme_declared_clip_count = int(readme_count_match.group(1))
    overlapping_sensors = {
        sensor: sorted(splits)
        for sensor, splits in sensor_splits.items()
        if len(splits) > 1
    }
    if overlapping_sensors:
        raise ValueError("sensor identities overlap provider splits")
    duplicate_observation_key_excess = sum(
        count - 1 for count in observation_keys.values() if count > 1
    )
    if duplicate_observation_key_excess:
        raise ValueError("audio observation keys are duplicated")

    duplicate_pcm_digest_groups = {
        digest: count for digest, count in pcm_digests.items() if count > 1
    }
    unique_pcm_sensors = {
        sensor
        for digest, sensors in pcm_digest_sensors.items()
        if pcm_digests[digest] == 1
        for sensor in sensors
    }
    riff_formats = []
    for key, count in sorted(format_counts.items()):
        row = dict(format_values[key])
        row["file_count"] = count
        riff_formats.append(row)

    observed_audio_count = sum(split_clips.values())
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "state": "source_identity_evidence_only",
        "source_id": SOURCE_ID,
        "benchmark_audio_generated": False,
        "scores_opened": False,
        "selection_authorized": False,
        "paths_redacted": True,
        "archive_binding": {
            "bytes": expected_bytes,
            "provider_md5": provider_md5,
            "provider_checksum_verified": True,
            "local_sha256": local_sha256,
            "gzip_and_tar_stream_verified": True,
        },
        "observed": {
            "regular_member_count": regular_member_count,
            "directory_member_count": directory_member_count,
            "unexpected_regular_member_count": len(unexpected_regular_members),
            "readme_sha256": hashlib.sha256(readme_payload).hexdigest(),
            "audio_file_count": observed_audio_count,
            "audio_uncompressed_member_bytes": uncompressed_audio_bytes,
            "split_audio_file_counts": sorted_counts(split_clips),
            "split_sensor_counts": {
                split: len(sensors) for split, sensors in sorted(split_sensors.items())
            },
            "sensor_count": len(sensor_clips),
            "audio_files_per_sensor": sorted_counts(sensor_clips),
            "audio_files_per_sensor_minimum": min(sensor_clips.values()),
            "audio_files_per_sensor_maximum": max(sensor_clips.values()),
            "sensor_sets_disjoint_across_provider_splits": True,
            "observation_keys_unique": True,
            "recording_date_minimum": date_minimum.isoformat() if date_minimum else None,
            "recording_date_maximum": date_maximum.isoformat() if date_maximum else None,
            "riff_formats": riff_formats,
            "frame_count_minimum": frame_minimum,
            "frame_count_maximum": frame_maximum,
            "distinct_pcm_digest_count": len(pcm_digests),
            "duplicate_pcm_digest_group_count": len(duplicate_pcm_digest_groups),
            "duplicate_pcm_file_count_excess": sum(
                count - 1 for count in duplicate_pcm_digest_groups.values()
            ),
            "cross_sensor_duplicate_pcm_digest_group_count": sum(
                len(pcm_digest_sensors[digest]) > 1
                for digest in duplicate_pcm_digest_groups
            ),
        },
        "reconciliation": {
            "archive_readme_declared_clip_count": readme_declared_clip_count,
            "observed_minus_readme_declared_clip_count": (
                observed_audio_count - readme_declared_clip_count
            ),
        },
        "conservative_reference_boundary": {
            "rule": [
                "canonical provider filename with a valid date and hour",
                "sensor identity belongs to exactly one provider split",
                "PCM digest occurs exactly once in the archive",
            ],
            "eligible_audio_file_count": sum(
                count == 1 for count in pcm_digests.values()
            ),
            "eligible_sensor_count": len(unique_pcm_sensors),
            "grouping_unit": "sensor identity across recording time",
            "future_selection_constraint": (
                "At most one reference excerpt per sensor; preserve provider split, "
                "sensor, date, hour, and instance identifiers."
            ),
            "independence_limit": (
                "Different sensors do not prove independent microphones, gain "
                "settings, collection software, or wider network operations; retain "
                "SONYC as one provider stratum."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--expected-bytes", type=int, required=True)
    parser.add_argument("--expected-provider-md5", required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(
        args.archive, args.expected_bytes, args.expected_provider_md5.casefold()
    )
    if args.output:
        write_json_atomic(args.output, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
