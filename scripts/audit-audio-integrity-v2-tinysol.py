#!/usr/bin/env python3
"""Audit TinySOL v6.0 source identities without selecting benchmark audio."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import struct
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


REPORT_SCHEMA_VERSION = 1
SOURCE_ID = "tinysol_6_0"
PITCH = re.compile(r"^([A-G])(#?)(-?\d+)$")
MISC = re.compile(r"^(?:N|T\d+[ud]|R100[ud]|T\d+[ud]_R100[ud])$")
DYNAMICS_IDS = {"pp": 0, "p": 1, "mf": 2, "f": 3, "ff": 4}
PITCH_CLASS = {
    "C": 0,
    "C#": 1,
    "D": 2,
    "D#": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "G": 7,
    "G#": 8,
    "A": 9,
    "A#": 10,
    "B": 11,
}


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


def read_wave(payload: bytes) -> dict[str, int | str | dict[str, int]]:
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


def safe_archive_member_id(value: str) -> str:
    member = PurePosixPath(value)
    if (
        not value
        or member.is_absolute()
        or ".." in member.parts
        or member.as_posix() != value
    ):
        raise ValueError("TinySOL archive contains an unsafe or noncanonical path")
    return value


def midi_pitch(pitch: str) -> int:
    match = PITCH.fullmatch(pitch)
    if match is None:
        raise ValueError("TinySOL pitch text is invalid")
    name = match.group(1) + match.group(2)
    octave = int(match.group(3))
    return (octave + 1) * 12 + PITCH_CLASS[name]


def expected_instance_token(row: dict[str, str]) -> str:
    try:
        instance = int(row["Instance ID"])
    except ValueError as error:
        raise ValueError("TinySOL instance ID is invalid") from error
    if not 0 <= instance <= 5:
        raise ValueError("TinySOL instance ID is outside the observed v6 range")
    string_id = row["String ID (if applicable)"]
    if string_id:
        if not re.fullmatch(r"[1-4]\.0", string_id):
            raise ValueError("TinySOL string ID is invalid")
        string = int(float(string_id))
        if instance != string - 1:
            raise ValueError("TinySOL string and instance IDs differ")
        return f"{string}c"
    return "N" if instance == 0 else f"alt{instance}"


def parse_metadata(
    metadata_path: Path, expected: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    expected_columns = expected.get("metadata_columns")
    if not isinstance(expected_columns, list):
        raise ValueError("TinySOL metadata column rules are absent")
    with metadata_path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != expected_columns:
            raise ValueError("TinySOL metadata columns differ")
        raw_rows = list(reader)
    if len(raw_rows) != expected.get("metadata_row_count"):
        raise ValueError("TinySOL metadata row count differs")

    instrument_rules = expected.get("instruments")
    if not isinstance(instrument_rules, list):
        raise ValueError("TinySOL instrument rules are absent")
    instruments_by_abbreviation: dict[str, dict[str, Any]] = {}
    for rule in instrument_rules:
        if not isinstance(rule, dict) or not isinstance(
            rule.get("abbreviation"), str
        ):
            raise ValueError("TinySOL instrument rule is invalid")
        abbreviation = str(rule["abbreviation"])
        if abbreviation in instruments_by_abbreviation:
            raise ValueError("TinySOL instrument rule is duplicated")
        instruments_by_abbreviation[abbreviation] = rule

    rows: dict[str, dict[str, Any]] = {}
    family_counts: collections.Counter[str] = collections.Counter()
    fold_counts: collections.Counter[str] = collections.Counter()
    instrument_counts: collections.Counter[str] = collections.Counter()
    dynamics_counts: collections.Counter[str] = collections.Counter()
    instance_counts: collections.Counter[str] = collections.Counter()
    retuning_counts: collections.Counter[str] = collections.Counter()
    natural_instrument_counts: collections.Counter[str] = collections.Counter()
    digitally_retuned_instrument_counts: collections.Counter[str] = (
        collections.Counter()
    )

    for row_number, row in enumerate(raw_rows, start=2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"TinySOL metadata row {row_number} has extra fields")
        archive_member_id = safe_archive_member_id(row["Path"])
        if archive_member_id in rows:
            raise ValueError("TinySOL metadata path is duplicated")
        path = PurePosixPath(archive_member_id)
        if len(path.parts) != 4 or path.suffix != ".wav":
            raise ValueError("TinySOL metadata path shape differs")
        family, instrument_folder, technique_folder, filename = path.parts
        abbreviation = row["Instrument (abbr.)"]
        instrument_rule = instruments_by_abbreviation.get(abbreviation)
        if instrument_rule is None:
            raise ValueError("TinySOL metadata instrument abbreviation differs")
        if (
            family != row["Family"]
            or family != instrument_rule.get("family")
            or instrument_folder != instrument_rule.get("folder")
            or row["Instrument (in full)"] != instrument_rule.get("full_name")
            or technique_folder != "ordinario"
            or row["Technique (abbr.)"] != "ord"
            or row["Technique (in full)"] != "ordinario"
        ):
            raise ValueError("TinySOL metadata path and instrument fields differ")

        filename_fields = PurePosixPath(filename).stem.split("-")
        if len(filename_fields) != 6:
            raise ValueError("TinySOL filename factor count differs")
        (
            filename_abbreviation,
            filename_technique,
            filename_pitch,
            filename_dynamics,
            filename_instance,
            filename_misc,
        ) = filename_fields
        instance_token = expected_instance_token(row)
        if (
            filename_abbreviation != abbreviation
            or filename_technique != row["Technique (abbr.)"]
            or filename_pitch != row["Pitch"]
            or filename_dynamics != row["Dynamics"]
            or filename_instance != instance_token
            or MISC.fullmatch(filename_misc) is None
        ):
            raise ValueError("TinySOL filename and metadata factors differ")

        try:
            pitch_id = int(row["Pitch ID"])
            dynamics_id = int(row["Dynamics ID"])
        except ValueError as error:
            raise ValueError("TinySOL numeric factor is invalid") from error
        if pitch_id != midi_pitch(row["Pitch"]):
            raise ValueError("TinySOL pitch and MIDI ID differ")
        if DYNAMICS_IDS.get(row["Dynamics"]) != dynamics_id:
            raise ValueError("TinySOL dynamics and dynamics ID differ")
        if row["Fold"] not in {"0", "1", "2", "3", "4"}:
            raise ValueError("TinySOL fold ID differs")

        retuning_flag = row["Needed digital retuning"]
        if retuning_flag not in {"TRUE", "FALSE"}:
            raise ValueError("TinySOL digital-retuning flag is invalid")
        digitally_retuned = filename_misc != "N"
        if digitally_retuned != (retuning_flag == "TRUE"):
            raise ValueError("TinySOL retuning flag and filename differ")
        has_resampling = "R" in filename_misc
        has_tuning = "T" in filename_misc
        retuning_class = (
            "natural"
            if not digitally_retuned
            else "resampled_and_tuned"
            if has_resampling and has_tuning
            else "resampled_only"
            if has_resampling
            else "tuning_only"
        )
        rows[archive_member_id] = {
            "instrument_abbreviation": abbreviation,
            "digitally_retuned": digitally_retuned,
            "retuning_class": retuning_class,
            "pitch_id": pitch_id,
            "dynamics": row["Dynamics"],
            "instance_token": instance_token,
            "misc": filename_misc,
        }
        family_counts[family] += 1
        fold_counts[row["Fold"]] += 1
        instrument_counts[abbreviation] += 1
        dynamics_counts[row["Dynamics"]] += 1
        instance_counts[row["Instance ID"]] += 1
        retuning_counts[retuning_class] += 1
        if digitally_retuned:
            digitally_retuned_instrument_counts[abbreviation] += 1
        else:
            natural_instrument_counts[abbreviation] += 1

    expected_instrument_counts = {
        str(rule["abbreviation"]): rule.get("row_count") for rule in instrument_rules
    }
    if dict(sorted(instrument_counts.items())) != dict(
        sorted(expected_instrument_counts.items())
    ):
        raise ValueError("TinySOL instrument counts differ")
    if dict(sorted(family_counts.items())) != expected.get("family_counts"):
        raise ValueError("TinySOL family counts differ")
    if dict(sorted(fold_counts.items())) != expected.get("fold_counts"):
        raise ValueError("TinySOL fold counts differ")
    count_expectations = {
        "natural": "natural_reference_row_count",
        "tuning_only": "tuning_only_row_count",
        "resampled_only": None,
        "resampled_and_tuned": "resampled_and_tuned_row_count",
    }
    for retuning_class, expected_field in count_expectations.items():
        if expected_field is not None and retuning_counts[retuning_class] != expected.get(
            expected_field
        ):
            raise ValueError(f"TinySOL {retuning_class} row count differs")
    if (
        retuning_counts["resampled_only"]
        + retuning_counts["resampled_and_tuned"]
        != expected.get("resampled_row_count")
        or sum(
            count
            for key, count in retuning_counts.items()
            if key != "natural"
        )
        != expected.get("digitally_retuned_row_count")
    ):
        raise ValueError("TinySOL digital-retuning totals differ")

    factor_index: collections.defaultdict[
        tuple[str, int, str, str, str], list[str]
    ] = collections.defaultdict(list)
    for archive_member_id, row in rows.items():
        factor_index[
            (
                str(row["instrument_abbreviation"]),
                int(row["pitch_id"]),
                str(row["dynamics"]),
                str(row["instance_token"]),
                str(row["misc"]),
            )
        ].append(archive_member_id)
    if any(len(member_ids) != 1 for member_ids in factor_index.values()):
        raise ValueError("TinySOL metadata factor key is duplicated")

    resampled_parent_mappings: list[dict[str, str]] = []
    resampled_parent_classes: collections.Counter[str] = collections.Counter()
    for archive_member_id, row in rows.items():
        misc = str(row["misc"])
        resampling = re.search(r"R100([ud])$", misc)
        if resampling is None:
            continue
        parent_pitch_id = int(row["pitch_id"]) + (
            -1 if resampling.group(1) == "u" else 1
        )
        parent_misc = misc.split("_R", maxsplit=1)[0] if misc.startswith("T") else "N"
        candidates = factor_index[
            (
                str(row["instrument_abbreviation"]),
                parent_pitch_id,
                str(row["dynamics"]),
                str(row["instance_token"]),
                parent_misc,
            )
        ]
        if len(candidates) != 1:
            raise ValueError("TinySOL resampled parent identity is not unique")
        parent_member_id = candidates[0]
        resampled_parent_mappings.append(
            {
                "derived_archive_member_id": archive_member_id,
                "parent_archive_member_id": parent_member_id,
            }
        )
        resampled_parent_classes[str(rows[parent_member_id]["retuning_class"])] += 1
    if len(resampled_parent_mappings) != expected.get("resampled_row_count"):
        raise ValueError("TinySOL resampled parent mapping count differs")

    return rows, {
        "metadata_column_count": len(expected_columns),
        "metadata_row_count": len(rows),
        "metadata_paths_unique": True,
        "family_counts": dict(sorted(family_counts.items())),
        "fold_counts": dict(sorted(fold_counts.items())),
        "instrument_row_counts": dict(sorted(instrument_counts.items())),
        "dynamics_counts": dict(sorted(dynamics_counts.items())),
        "instance_id_counts": dict(sorted(instance_counts.items())),
        "retuning_class_counts": dict(sorted(retuning_counts.items())),
        "natural_reference_row_counts_by_instrument": dict(
            sorted(natural_instrument_counts.items())
        ),
        "digitally_retuned_row_counts_by_instrument": dict(
            sorted(digitally_retuned_instrument_counts.items())
        ),
        "metadata_factor_keys_unique": True,
        "resampled_parent_mapping_count": len(resampled_parent_mappings),
        "distinct_resampled_parent_count": len(
            {row["parent_archive_member_id"] for row in resampled_parent_mappings}
        ),
        "resampled_parent_class_counts": dict(
            sorted(resampled_parent_classes.items())
        ),
        "resampled_parent_mappings": sorted(
            resampled_parent_mappings,
            key=lambda row: row["derived_archive_member_id"],
        ),
        "provider_description_discrepancies": [
            "The v6 description says 13 metadata columns but enumerates and distributes 14.",
            "The v6 description says Instance ID ranges from 0 to 4, but three rows use 5.",
        ],
    }


def format_rows(
    counts: collections.Counter[str], values: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for key, count in sorted(counts.items()):
        row = dict(values[key])
        row["file_count"] = count
        rows.append(row)
    return rows


def audit(audio_path: Path, metadata_path: Path, rules_path: Path) -> dict[str, Any]:
    rules = load_object(rules_path)
    if rules.get("schema_version") != 1:
        raise ValueError("unsupported TinySOL source-group rule schema")
    for field, expected_value in {
        "state": "source_identity_rules_not_allocation",
        "source_id": SOURCE_ID,
        "record_id": 3685367,
        "record_version": "6.0",
        "audio_generated": False,
        "scores_opened": False,
        "selection_authorized": False,
    }.items():
        if rules.get(field) != expected_value:
            raise ValueError(f"TinySOL source-group rule {field} differs")
    expected = rules.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("TinySOL expected counts are absent")
    if (
        expected.get("conservative_partition_group_count") != 1
        or expected.get("source_group_count") != 1
    ):
        raise ValueError("TinySOL conservative partition-group rule differs")

    artifact_rules = rules.get("artifacts")
    if not isinstance(artifact_rules, dict) or set(artifact_rules) != {
        "audio",
        "metadata",
    }:
        raise ValueError("TinySOL artifact rules differ")
    archive_bindings: dict[str, dict[str, Any]] = {}
    for kind, path in {"audio": audio_path, "metadata": metadata_path}.items():
        rule = artifact_rules[kind]
        if not isinstance(rule, dict) or rule.get("filename") != path.name:
            raise ValueError(f"TinySOL {kind} artifact identity differs")
        provider_md5, local_sha256 = hash_file(path)
        if path.stat().st_size != rule.get("bytes") or f"md5:{provider_md5}" != rule.get(
            "provider_checksum"
        ):
            raise ValueError(f"TinySOL {kind} artifact binding differs")
        archive_bindings[kind] = {
            "filename": path.name,
            "bytes": path.stat().st_size,
            "provider_md5": provider_md5,
            "provider_checksum_verified": True,
            "sha256": local_sha256,
        }

    metadata_rows, metadata_observed = parse_metadata(metadata_path, expected)
    archive_bindings["metadata"]["csv_parsed_verified"] = True
    root_prefix = expected.get("archive_member_root_prefix")
    if not isinstance(root_prefix, str):
        raise ValueError("TinySOL archive root-prefix rule is absent")
    ancillary_rules = expected.get("ancillary_regular_members")
    if not isinstance(ancillary_rules, list):
        raise ValueError("TinySOL ancillary-member rules are absent")
    expected_ancillary_by_path: dict[str, int] = {}
    for rule in ancillary_rules:
        if (
            not isinstance(rule, dict)
            or not isinstance(rule.get("path"), str)
            or not isinstance(rule.get("bytes"), int)
        ):
            raise ValueError("TinySOL ancillary-member rule is invalid")
        ancillary_id = safe_archive_member_id(str(rule["path"]))
        if ancillary_id in expected_ancillary_by_path:
            raise ValueError("TinySOL ancillary-member rule is duplicated")
        expected_ancillary_by_path[ancillary_id] = int(rule["bytes"])

    observed_audio_member_ids: set[str] = set()
    observed_ancillary_members: dict[str, dict[str, Any]] = {}
    directory_member_count = 0
    special_member_count = 0
    unexpected_regular_member_ids: list[str] = []
    uncompressed_audio_member_bytes = 0
    frame_counts: list[int] = []
    frame_count_members: collections.defaultdict[int, list[str]] = (
        collections.defaultdict(list)
    )
    data_byte_counts: list[int] = []
    pcm_digests: collections.Counter[str] = collections.Counter()
    pcm_digest_members: collections.defaultdict[str, list[str]] = (
        collections.defaultdict(list)
    )
    natural_pcm_digests: collections.Counter[str] = collections.Counter()
    natural_pcm_digest_members: collections.defaultdict[str, list[str]] = (
        collections.defaultdict(list)
    )
    format_counts: collections.Counter[str] = collections.Counter()
    format_values: dict[str, dict[str, Any]] = {}

    with tarfile.open(audio_path, mode="r|gz") as archive:
        for member in archive:
            if member.isdir() and member.name in {"", ".", "./"}:
                directory_member_count += 1
                continue
            if not member.name.startswith(root_prefix):
                raise ValueError("TinySOL archive member root prefix differs")
            member_name = member.name[len(root_prefix) :]
            member_name = member_name.rstrip("/") if member.isdir() else member_name
            if member.isdir() and member_name in {"", "."}:
                directory_member_count += 1
                continue
            member_id = safe_archive_member_id(member_name)
            if member.isdir():
                directory_member_count += 1
                continue
            if not member.isfile():
                special_member_count += 1
                continue
            if member_id in expected_ancillary_by_path:
                if member_id in observed_ancillary_members:
                    raise ValueError("TinySOL ancillary member is duplicated")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError("TinySOL ancillary member could not be read")
                payload = extracted.read()
                if (
                    len(payload) != member.size
                    or member.size != expected_ancillary_by_path[member_id]
                ):
                    raise ValueError("TinySOL ancillary member size differs")
                observed_ancillary_members[member_id] = {
                    "path": member_id,
                    "bytes": member.size,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
                continue
            if member_id not in metadata_rows:
                unexpected_regular_member_ids.append(member_id)
                continue
            if member_id in observed_audio_member_ids:
                raise ValueError("TinySOL archive audio member path is duplicated")
            observed_audio_member_ids.add(member_id)
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError("TinySOL regular member could not be read")
            payload = extracted.read()
            if len(payload) != member.size:
                raise ValueError("TinySOL archive member size differs")
            wave = read_wave(payload)
            pcm_digest = str(wave.pop("pcm_sha256"))
            pcm_digests[pcm_digest] += 1
            pcm_digest_members[pcm_digest].append(member_id)
            if not metadata_rows[member_id]["digitally_retuned"]:
                natural_pcm_digests[pcm_digest] += 1
                natural_pcm_digest_members[pcm_digest].append(member_id)
            frames = int(wave["frame_count"])
            data_bytes = int(wave["data_bytes"])
            frame_counts.append(frames)
            frame_count_members[frames].append(member_id)
            data_byte_counts.append(data_bytes)
            uncompressed_audio_member_bytes += member.size
            format_identity = dict(wave)
            format_identity.pop("frame_count")
            format_identity.pop("data_bytes")
            format_key = json.dumps(
                format_identity, sort_keys=True, separators=(",", ":")
            )
            format_counts[format_key] += 1
            format_values[format_key] = format_identity

    missing_metadata_member_ids = sorted(
        set(metadata_rows) - observed_audio_member_ids
    )
    if unexpected_regular_member_ids or special_member_count:
        raise ValueError("TinySOL archive contains unexpected members")
    if set(observed_ancillary_members) != set(expected_ancillary_by_path):
        raise ValueError("TinySOL ancillary member identities differ")
    if directory_member_count != expected.get("directory_member_count"):
        raise ValueError("TinySOL directory member count differs")
    if missing_metadata_member_ids:
        raise ValueError("TinySOL metadata paths are missing from the archive")
    if len(observed_audio_member_ids) != expected.get("metadata_row_count"):
        raise ValueError("TinySOL archive audio count differs")
    archive_bindings["audio"]["gzip_tar_stream_verified"] = True

    observed_format_rows = format_rows(format_counts, format_values)
    expected_audio_format = expected.get("audio_format")
    if not isinstance(expected_audio_format, dict) or len(observed_format_rows) != 1:
        raise ValueError("TinySOL audio format count differs")
    if any(
        observed_format_rows[0].get(field) != value
        for field, value in expected_audio_format.items()
    ):
        raise ValueError("TinySOL audio format differs")

    minimum_frames = min(frame_counts)
    maximum_frames = max(frame_counts)
    if minimum_frames < 2 * 44100 or maximum_frames > 10 * 44100:
        metadata_observed["provider_description_discrepancies"].append(
            "The v6 description says clips span 2 to 10 seconds, but the bound "
            "archive contains shorter and longer WAVs."
        )

    duplicate_pcm_groups = {
        digest: count for digest, count in pcm_digests.items() if count > 1
    }
    duplicate_natural_pcm_groups = {
        digest: count for digest, count in natural_pcm_digests.items() if count > 1
    }
    natural_retuned_pcm_collision_groups = {
        digest
        for digest, count in natural_pcm_digests.items()
        if pcm_digests[digest] > count
    }
    eligible_natural_audio_file_count = sum(
        count == 1 and pcm_digests[digest] == 1
        for digest, count in natural_pcm_digests.items()
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
            **metadata_observed,
            "archive_audio_file_count": len(observed_audio_member_ids),
            "archive_paths_match_metadata_exactly": True,
            "archive_member_root_prefix": root_prefix,
            "directory_member_count": directory_member_count,
            "ancillary_regular_members": [
                observed_ancillary_members[key]
                for key in sorted(observed_ancillary_members)
            ],
            "special_member_count": special_member_count,
            "unexpected_regular_member_count": len(unexpected_regular_member_ids),
            "uncompressed_audio_member_bytes": uncompressed_audio_member_bytes,
            "riff_formats": observed_format_rows,
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
            "distinct_natural_pcm_digest_count": len(natural_pcm_digests),
            "duplicate_natural_pcm_digest_group_count": len(
                duplicate_natural_pcm_groups
            ),
            "duplicate_natural_pcm_archive_member_groups": sorted(
                sorted(natural_pcm_digest_members[digest])
                for digest in duplicate_natural_pcm_groups
            ),
            "natural_retuned_pcm_collision_group_count": len(
                natural_retuned_pcm_collision_groups
            ),
        },
        "conservative_reference_boundary": {
            "rule": [
                "metadata path matches exactly one canonical archive WAV",
                "Needed digital retuning is FALSE and filename MISC is N",
                "PCM digest occurs exactly once across the full archive",
            ],
            "eligible_audio_file_count": eligible_natural_audio_file_count,
            "eligible_group_count": 1,
            "source_grouping_unit": "individual non-retuned distributed WAV path",
            "resampled_source_grouping_unit": "uniquely resolved parent WAV path",
            "partition_grouping_unit": "common TinySOL/SOL collection",
            "future_selection_constraint": (
                "Digitally retuned rows cannot be base encoder references; retain "
                "them only as declared PCM-transform candidates. Every R row must "
                "share source lineage with its resolved parent; tuning-only rows have "
                "no distributed pre-retuning PCM. The N marker means no per-note "
                "retuning, not untouched studio audio. Preserve family, instrument, "
                "pitch, dynamics, instance, fold, and retuning fields."
            ),
            "independence_limit": (
                "Instrument labels do not establish independent performers, physical "
                "instruments, microphones, or sessions. Keep every TinySOL row in one "
                "partition group and report it as one provider stratum."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-archive", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(args.audio_archive, args.metadata, args.rules)
    if args.output:
        write_json_atomic(args.output, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
