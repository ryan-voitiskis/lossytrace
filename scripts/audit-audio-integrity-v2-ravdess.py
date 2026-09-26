#!/usr/bin/env python3
"""Audit RAVDESS audio-only actor identities without selecting benchmark audio."""

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
from typing import Any


REPORT_SCHEMA_VERSION = 1
SOURCE_ID = "ravdess_audio_1_0_0"
AUDIO_MEMBER = re.compile(
    r"^Actor_(\d{2})/"
    r"(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})\.wav$"
)


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
            ancillary_chunks[chunk_id_bytes.decode("latin-1")] += 1
        offset = chunk_end + (chunk_size & 1)
    if offset != len(payload):
        raise ValueError("invalid RIFF padding")
    if format_payload is None or pcm_payload is None:
        raise ValueError("WAVE member lacks format or data chunk")
    format_tag, channels, rate, average_bytes, block_align, bits = struct.unpack(
        "<HHIIHH", format_payload[:16]
    )
    if block_align < 1 or len(pcm_payload) % block_align:
        raise ValueError("WAVE data size is not frame aligned")
    if average_bytes != rate * block_align:
        raise ValueError("WAVE average byte rate is inconsistent")
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


def validate_factor_fields(
    archive_kind: str,
    directory_actor: str,
    fields: tuple[str, str, str, str, str, str, str],
) -> tuple[str, str, str, str, str, str, str]:
    modality, channel, emotion, intensity, statement, repetition, actor = fields
    expected_channel = {"speech": "01", "song": "02"}[archive_kind]
    if modality != "03" or channel != expected_channel:
        raise ValueError("RAVDESS modality or channel differs from archive kind")
    allowed_emotions = set(f"{value:02d}" for value in range(1, 9))
    if archive_kind == "song":
        allowed_emotions = set(f"{value:02d}" for value in range(1, 7))
    if emotion not in allowed_emotions:
        raise ValueError("RAVDESS emotion is outside the documented factorial grid")
    allowed_intensities = {"01"} if emotion == "01" else {"01", "02"}
    if intensity not in allowed_intensities:
        raise ValueError("RAVDESS intensity is invalid for the emotion")
    if statement not in {"01", "02"} or repetition not in {"01", "02"}:
        raise ValueError("RAVDESS statement or repetition is invalid")
    if not 1 <= int(actor) <= 24 or actor != directory_actor:
        raise ValueError("RAVDESS directory and filename actor identities differ")
    return fields


def format_rows(
    counts: collections.Counter[str], values: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for key, count in sorted(counts.items()):
        row = dict(values[key])
        row["file_count"] = count
        rows.append(row)
    return rows


def audit(speech_path: Path, song_path: Path, rules_path: Path) -> dict[str, Any]:
    rules = load_object(rules_path)
    if rules.get("schema_version") != 1:
        raise ValueError("unsupported RAVDESS source-group rule schema")
    for field, expected in {
        "state": "source_identity_rules_not_allocation",
        "source_id": SOURCE_ID,
        "record_id": 1188976,
        "record_version": "1.0.0",
        "audio_generated": False,
        "scores_opened": False,
        "selection_authorized": False,
    }.items():
        if rules.get(field) != expected:
            raise ValueError(f"RAVDESS source-group rule {field} differs")
    artifact_rules = rules.get("artifacts")
    if not isinstance(artifact_rules, list) or len(artifact_rules) != 2:
        raise ValueError("RAVDESS artifact rules differ")
    paths = {"speech": speech_path, "song": song_path}
    rules_by_kind: dict[str, dict[str, Any]] = {}
    archive_bindings: dict[str, dict[str, Any]] = {}
    for row in artifact_rules:
        if not isinstance(row, dict) or row.get("kind") not in paths:
            raise ValueError("RAVDESS artifact rule is invalid")
        kind = str(row["kind"])
        if kind in rules_by_kind:
            raise ValueError("RAVDESS artifact kind is duplicated")
        rules_by_kind[kind] = row
        path = paths[kind]
        if row.get("channel_id") != {"speech": "01", "song": "02"}[kind] or row.get(
            "filename"
        ) != path.name:
            raise ValueError(f"RAVDESS {kind} artifact identity differs")
        provider_md5, local_sha256 = hash_file(path)
        if path.stat().st_size != row.get("bytes") or f"md5:{provider_md5}" != row.get(
            "provider_checksum"
        ):
            raise ValueError(f"RAVDESS {kind} archive binding differs")
        archive_bindings[kind] = {
            "filename": row.get("filename"),
            "bytes": path.stat().st_size,
            "provider_md5": provider_md5,
            "provider_checksum_verified": True,
            "local_sha256": local_sha256,
            "zip_crc_verified": True,
        }
    if set(rules_by_kind) != set(paths):
        raise ValueError("RAVDESS artifact kinds are incomplete")

    file_counts: collections.Counter[str] = collections.Counter()
    actor_counts: collections.defaultdict[str, collections.Counter[str]] = (
        collections.defaultdict(collections.Counter)
    )
    actor_kinds: collections.defaultdict[str, set[str]] = collections.defaultdict(set)
    factor_keys: set[tuple[str, str, str, str, str, str, str]] = set()
    pcm_digests: collections.Counter[str] = collections.Counter()
    pcm_digest_actors: collections.defaultdict[str, set[str]] = collections.defaultdict(set)
    pcm_digest_members: collections.defaultdict[str, list[str]] = (
        collections.defaultdict(list)
    )
    non_mono_archive_member_ids: list[str] = []
    format_counts: collections.defaultdict[str, collections.Counter[str]] = (
        collections.defaultdict(collections.Counter)
    )
    format_values: collections.defaultdict[str, dict[str, dict[str, Any]]] = (
        collections.defaultdict(dict)
    )
    frame_counts: collections.defaultdict[str, list[int]] = collections.defaultdict(list)
    data_byte_counts: collections.defaultdict[str, list[int]] = collections.defaultdict(list)
    unexpected_regular_members: collections.Counter[str] = collections.Counter()
    directory_members: collections.Counter[str] = collections.Counter()
    uncompressed_audio_bytes: collections.Counter[str] = collections.Counter()

    for kind, path in paths.items():
        with zipfile.ZipFile(path) as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise ValueError(f"RAVDESS ZIP CRC failure in {bad_member}")
            for member in archive.infolist():
                if member.is_dir():
                    directory_members[kind] += 1
                    continue
                match = AUDIO_MEMBER.fullmatch(member.filename)
                if match is None:
                    unexpected_regular_members[kind] += 1
                    continue
                directory_actor = match.group(1)
                fields = validate_factor_fields(kind, directory_actor, match.groups()[1:])
                if fields in factor_keys:
                    raise ValueError("RAVDESS factorial key is duplicated")
                factor_keys.add(fields)
                actor = fields[-1]
                file_counts[kind] += 1
                actor_counts[actor][kind] += 1
                actor_kinds[actor].add(kind)
                uncompressed_audio_bytes[kind] += member.file_size

                payload = archive.read(member)
                wave = read_wave(payload)
                pcm_digest = str(wave.pop("pcm_sha256"))
                pcm_digests[pcm_digest] += 1
                pcm_digest_actors[pcm_digest].add(actor)
                pcm_digest_members[pcm_digest].append(member.filename)
                if wave["channel_count"] != 1:
                    non_mono_archive_member_ids.append(member.filename)
                frames = int(wave["frame_count"])
                data_bytes = int(wave["data_bytes"])
                frame_counts[kind].append(frames)
                data_byte_counts[kind].append(data_bytes)
                format_identity = dict(wave)
                format_identity.pop("frame_count")
                format_identity.pop("data_bytes")
                format_key = json.dumps(
                    format_identity, sort_keys=True, separators=(",", ":")
                )
                format_counts[kind][format_key] += 1
                format_values[kind][format_key] = format_identity

    expected = rules.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("RAVDESS expected counts are absent")
    actors = set(actor_counts)
    expected_actor_count = expected.get("actor_count")
    if len(actors) != expected_actor_count:
        raise ValueError("RAVDESS actor count differs")
    if expected.get("source_group_count") != expected_actor_count:
        raise ValueError("RAVDESS expected source-group count differs")
    speech_per_actor = expected.get("speech_files_per_actor")
    if any(actor_counts[actor]["speech"] != speech_per_actor for actor in actors):
        raise ValueError("RAVDESS speech actor grid differs")
    missing_song_actors = set(expected.get("missing_song_actor_ids", []))
    observed_missing_song_actors = {
        actor for actor in actors if actor_counts[actor]["song"] == 0
    }
    if observed_missing_song_actors != missing_song_actors:
        raise ValueError("RAVDESS missing-song actor identities differ")
    song_per_actor = expected.get("song_files_per_present_actor")
    if any(
        actor_counts[actor]["song"] != song_per_actor
        for actor in actors - missing_song_actors
    ):
        raise ValueError("RAVDESS song actor grid differs")
    if file_counts["speech"] != expected.get("speech_file_count") or file_counts[
        "song"
    ] != expected.get("song_file_count"):
        raise ValueError("RAVDESS archive file counts differ")
    if any(unexpected_regular_members.values()):
        raise ValueError("RAVDESS archive contains unexpected regular members")

    duplicate_pcm_groups = {
        digest: count for digest, count in pcm_digests.items() if count > 1
    }
    unique_pcm_actors = {
        actor
        for digest, digest_actors in pcm_digest_actors.items()
        if pcm_digests[digest] == 1
        for actor in digest_actors
    }
    actor_profile_counts = collections.Counter(
        "+".join(sorted(kinds)) for kinds in actor_kinds.values()
    )
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
            "record_version": rules["record_version"],
        },
        "archive_bindings": archive_bindings,
        "source_group_rules_binding": {"sha256": sha256_file(rules_path)},
        "observed": {
            "speech_file_count": file_counts["speech"],
            "song_file_count": file_counts["song"],
            "total_audio_file_count": sum(file_counts.values()),
            "actor_count": len(actors),
            "speech_files_per_actor_minimum": min(
                actor_counts[actor]["speech"] for actor in actors
            ),
            "speech_files_per_actor_maximum": max(
                actor_counts[actor]["speech"] for actor in actors
            ),
            "song_files_per_present_actor_minimum": min(
                actor_counts[actor]["song"]
                for actor in actors - missing_song_actors
            ),
            "song_files_per_present_actor_maximum": max(
                actor_counts[actor]["song"]
                for actor in actors - missing_song_actors
            ),
            "missing_song_actor_ids": sorted(observed_missing_song_actors),
            "actor_channel_profile_counts": dict(sorted(actor_profile_counts.items())),
            "factorial_keys_unique": True,
            "factorial_grid_complete": True,
            "uncompressed_audio_member_bytes": dict(
                sorted(uncompressed_audio_bytes.items())
            ),
            "directory_member_counts": dict(sorted(directory_members.items())),
            "unexpected_regular_member_counts": dict(
                sorted(unexpected_regular_members.items())
            ),
            "riff_formats": {
                kind: format_rows(format_counts[kind], format_values[kind])
                for kind in sorted(paths)
            },
            "frame_count_ranges": {
                kind: {
                    "minimum": min(frame_counts[kind]),
                    "maximum": max(frame_counts[kind]),
                }
                for kind in sorted(paths)
            },
            "data_byte_ranges": {
                kind: {
                    "minimum": min(data_byte_counts[kind]),
                    "maximum": max(data_byte_counts[kind]),
                }
                for kind in sorted(paths)
            },
            "distinct_pcm_digest_count": len(pcm_digests),
            "duplicate_pcm_digest_group_count": len(duplicate_pcm_groups),
            "duplicate_pcm_file_count_excess": sum(
                count - 1 for count in duplicate_pcm_groups.values()
            ),
            "duplicate_pcm_archive_member_groups": sorted(
                sorted(pcm_digest_members[digest]) for digest in duplicate_pcm_groups
            ),
            "cross_actor_duplicate_pcm_digest_group_count": sum(
                len(pcm_digest_actors[digest]) > 1 for digest in duplicate_pcm_groups
            ),
            "non_mono_archive_member_ids": sorted(non_mono_archive_member_ids),
        },
        "conservative_reference_boundary": {
            "rule": [
                "canonical seven-field audio-only filename",
                "directory actor equals filename actor",
                "valid speech or song factorial cell with no duplicate key",
                "PCM digest occurs exactly once across both archives",
            ],
            "eligible_audio_file_count": sum(
                count == 1 for count in pcm_digests.values()
            ),
            "eligible_actor_count": len(unique_pcm_actors),
            "grouping_unit": "actor identity across speech and song",
            "future_selection_constraint": (
                "At most one reference excerpt per actor across both channels; "
                "exclude every member of a repeated-PCM group; preserve every "
                "seven-field factor identifier and original channel count."
            ),
            "independence_limit": (
                "Actors share the recording and export pipeline; retain RAVDESS as "
                "one provider stratum and run leave-provider/domain sensitivity."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speech-zip", type=Path, required=True)
    parser.add_argument("--song-zip", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(args.speech_zip, args.song_zip, args.rules)
    if args.output:
        write_json_atomic(args.output, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
