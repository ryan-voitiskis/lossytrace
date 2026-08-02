#!/usr/bin/env python3
"""Audit the VCTK-derived clean 56-speaker source without selecting audio."""

from __future__ import annotations

import argparse
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
SOURCE_ID = "vctk_clean_56spk_2017"
AUDIO_ROOT = "clean_trainset_56spk_wav/"
TRANSCRIPT_ROOT = "trainset_56spk_txt/"
AUDIO_MEMBER = re.compile(r"^clean_trainset_56spk_wav/(p[0-9]{3})_([0-9]{3})\.wav$")
TRANSCRIPT_MEMBER = re.compile(
    r"^trainset_56spk_txt/(p[0-9]{3})_([0-9]{3})\.txt$"
)
LOG_KEY = re.compile(r"^(p[0-9]{3})_([0-9]{3})$")
PROVIDER_CHECKSUM = re.compile(r"^md5:([0-9a-f]{32})$")
CAP_RANKING_ALGORITHM = "sha256_ascending_domain_separated_speaker_id"
CAP_RANKING_PREFIX = "lossytrace-v2-vctk-provider-count-cap-20260802\0"
CAP_RANKING_INPUT = (
    "UTF-8 ranking_prefix bytes followed by the UTF-8 provider speaker identifier; "
    "rank ascending by the 32-byte SHA-256 digest within each provider gender and "
    "use speaker identifier ascending only as a digest-collision tie break"
)


def digest_file(path: Path, algorithm: str) -> str:
    return digest_file_many(path, (algorithm,))[algorithm]


def digest_file_many(path: Path, algorithms: tuple[str, ...]) -> dict[str, str]:
    digests = {algorithm: hashlib.new(algorithm) for algorithm in algorithms}
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            for digest in digests.values():
                digest.update(chunk)
    return {algorithm: digest.hexdigest() for algorithm, digest in digests.items()}


def load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError("VCTK rules must be a JSON object")
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
        raise ValueError("VCTK archive contains an unsafe or noncanonical path")
    return value


def validate_file_binding(path: Path, binding: Any, label: str) -> dict[str, Any]:
    if not isinstance(binding, dict) or binding.get("filename") != path.name:
        raise ValueError(f"VCTK {label} filename binding differs")
    provider_checksum = binding.get("provider_checksum")
    algorithms = ("sha256", "md5") if provider_checksum is not None else ("sha256",)
    digests = digest_file_many(path, algorithms)
    if (
        path.stat().st_size != binding.get("bytes")
        or digests["sha256"] != binding.get("local_sha256")
    ):
        raise ValueError(f"VCTK {label} byte binding differs")
    result: dict[str, Any] = {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "local_sha256": digests["sha256"],
    }
    if provider_checksum is not None:
        match = PROVIDER_CHECKSUM.fullmatch(str(provider_checksum))
        if match is None or digests["md5"] != match.group(1):
            raise ValueError(f"VCTK {label} provider checksum differs")
        result["provider_md5"] = match.group(1)
        result["provider_checksum_verified"] = True
    provider_identity = binding.get("provider_identity")
    if provider_identity is not None:
        if not isinstance(provider_identity, dict):
            raise ValueError(f"VCTK {label} provider identity differs")
        result["provider_identity"] = provider_identity
    return result


def read_wave(payload: bytes) -> dict[str, Any]:
    if len(payload) < 12 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise ValueError("VCTK member is not a little-endian RIFF/WAVE file")
    if struct.unpack("<I", payload[4:8])[0] + 8 != len(payload):
        raise ValueError("VCTK RIFF size does not equal member size")
    offset = 12
    format_payload: bytes | None = None
    pcm_payload: bytes | None = None
    ancillary_chunks: collections.Counter[str] = collections.Counter()
    while offset < len(payload):
        if offset + 8 > len(payload):
            raise ValueError("VCTK has a truncated RIFF chunk header")
        chunk_id = payload[offset : offset + 4]
        chunk_size = struct.unpack("<I", payload[offset + 4 : offset + 8])[0]
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_size
        if chunk_end > len(payload):
            raise ValueError("VCTK has a truncated RIFF chunk")
        chunk = payload[chunk_start:chunk_end]
        if chunk_id == b"fmt ":
            if format_payload is not None or len(chunk) < 16:
                raise ValueError("VCTK has an invalid or duplicate format chunk")
            format_payload = chunk
        elif chunk_id == b"data":
            if pcm_payload is not None:
                raise ValueError("VCTK has a duplicate data chunk")
            pcm_payload = chunk
        else:
            ancillary_chunks[chunk_id.decode("latin-1")] += 1
        offset = chunk_end + (chunk_size & 1)
    if offset != len(payload):
        raise ValueError("VCTK has invalid RIFF padding")
    if format_payload is None or pcm_payload is None:
        raise ValueError("VCTK member lacks a format or data chunk")
    format_tag, channels, rate, average_bytes, block_align, bits = struct.unpack(
        "<HHIIHH", format_payload[:16]
    )
    if block_align < 1 or len(pcm_payload) % block_align:
        raise ValueError("VCTK data size is not frame aligned")
    if average_bytes != rate * block_align:
        raise ValueError("VCTK average byte rate is inconsistent")
    if format_tag == 1 and block_align != channels * ((bits + 7) // 8):
        raise ValueError("VCTK PCM block alignment is inconsistent")
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


def parse_log(
    log_archive: zipfile.ZipFile,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    bad_member = log_archive.testzip()
    if bad_member is not None:
        raise ValueError(f"VCTK log ZIP CRC failure: {bad_member}")
    member_name = "log_trainset_56spk.txt"
    try:
        payload = log_archive.read(member_name).decode("utf-8")
    except (KeyError, UnicodeDecodeError) as error:
        raise ValueError("VCTK 56-speaker log is absent or not UTF-8") from error
    rows: dict[str, dict[str, Any]] = {}
    noise_counts: collections.Counter[str] = collections.Counter()
    snr_counts: collections.Counter[str] = collections.Counter()
    speaker_counts: collections.Counter[str] = collections.Counter()
    for line_number, line in enumerate(payload.splitlines(), 1):
        fields = line.split()
        if len(fields) != 3 or LOG_KEY.fullmatch(fields[0]) is None:
            raise ValueError(f"VCTK log row {line_number} differs")
        key, noise, snr_raw = fields
        if key in rows or not re.fullmatch(r"-?[0-9]+", snr_raw):
            raise ValueError("VCTK log contains a duplicate key or invalid SNR")
        speaker_id = key.split("_", 1)[0]
        rows[key] = {"noise": noise, "snr_db": int(snr_raw)}
        noise_counts[noise] += 1
        snr_counts[snr_raw] += 1
        speaker_counts[speaker_id] += 1
    summary = {
        "member_name": member_name,
        "row_count": len(rows),
        "speaker_count": len(speaker_counts),
        "noise_counts": dict(sorted(noise_counts.items())),
        "snr_db_counts": dict(
            sorted(snr_counts.items(), key=lambda row: int(row[0]))
        ),
    }
    return rows, summary


def parse_speaker_info(path: Path) -> dict[str, dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("VCTK speaker metadata is not UTF-8") from error
    if not lines or lines[0].split()[:4] != ["ID", "AGE", "GENDER", "ACCENTS"]:
        raise ValueError("VCTK speaker metadata header differs")
    rows: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(lines[1:], 2):
        fields = line.split()
        if len(fields) < 4 or not re.fullmatch(r"[0-9]{3}", fields[0]):
            raise ValueError(f"VCTK speaker metadata row {line_number} differs")
        speaker_id = f"p{fields[0]}"
        if speaker_id in rows or fields[2] not in {"F", "M"}:
            raise ValueError("VCTK speaker metadata identity or gender differs")
        rows[speaker_id] = {
            "age": int(fields[1]),
            "gender": fields[2],
            "accent": fields[3],
            "region_tokens": fields[4:],
        }
    return rows


def transcript_keys(
    transcript_archive: zipfile.ZipFile,
) -> tuple[set[str], dict[str, Any]]:
    bad_member = transcript_archive.testzip()
    if bad_member is not None:
        raise ValueError(f"VCTK transcript ZIP CRC failure: {bad_member}")
    keys: set[str] = set()
    canonical_count = 0
    sidecar_count = 0
    directory_ids: list[str] = []
    unexpected_count = 0
    for info in transcript_archive.infolist():
        member_id = info.filename.rstrip("/") if info.is_dir() else info.filename
        safe_member_id(member_id)
        if info.is_dir():
            directory_ids.append(member_id)
            continue
        match = TRANSCRIPT_MEMBER.fullmatch(info.filename)
        if match is not None:
            if info.file_size < 1:
                raise ValueError("VCTK transcript is empty")
            key = f"{match.group(1)}_{match.group(2)}"
            if key in keys:
                raise ValueError("VCTK transcript key is duplicated")
            keys.add(key)
            canonical_count += 1
        elif info.filename.startswith("__MACOSX/"):
            sidecar_count += 1
        else:
            unexpected_count += 1
    return keys, {
        "canonical_transcript_count": canonical_count,
        "macos_sidecar_file_count": sidecar_count,
        "directory_member_count": len(directory_ids),
        "directory_member_ids": sorted(directory_ids),
        "unexpected_regular_member_count": unexpected_count,
    }


def format_rows(
    counts: collections.Counter[str], values: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, count in sorted(counts.items()):
        row = dict(values[key])
        row["file_count"] = count
        rows.append(row)
    return rows


def audit(
    audio_path: Path,
    log_path: Path,
    transcript_path: Path,
    speaker_info_path: Path,
    readme_path: Path,
    paper_path: Path,
    license_path: Path,
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
            raise ValueError(f"VCTK source-group rule {field} differs")

    audio_binding = validate_file_binding(audio_path, rules.get("artifact"), "audio")
    log_binding = validate_file_binding(
        log_path, rules.get("metadata_artifact"), "log"
    )
    supporting_rules = rules.get("supporting_artifacts")
    if not isinstance(supporting_rules, dict):
        raise ValueError("VCTK supporting artifact rules are absent")
    supporting_bindings = {
        "transcripts": validate_file_binding(
            transcript_path, supporting_rules.get("transcripts"), "transcripts"
        ),
        "speaker_info": validate_file_binding(
            speaker_info_path, supporting_rules.get("speaker_info"), "speaker info"
        ),
        "vctk_readme": validate_file_binding(
            readme_path, supporting_rules.get("vctk_readme"), "VCTK README"
        ),
        "primary_paper": validate_file_binding(
            paper_path, supporting_rules.get("primary_paper"), "primary paper"
        ),
        "license": validate_file_binding(
            license_path, supporting_rules.get("license"), "license"
        ),
    }

    expected = rules.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("VCTK expected identities are absent")
    expected_speaker_counts = expected.get("speaker_audio_file_counts")
    if not isinstance(expected_speaker_counts, dict) or not expected_speaker_counts:
        raise ValueError("VCTK expected speaker counts are absent")
    if not all(
        re.fullmatch(r"p[0-9]{3}", str(speaker))
        and isinstance(count, int)
        and not isinstance(count, bool)
        and count > 0
        for speaker, count in expected_speaker_counts.items()
    ):
        raise ValueError("VCTK expected speaker count row differs")

    with zipfile.ZipFile(log_path) as log_archive:
        log_rows, log_summary = parse_log(log_archive)
    speaker_metadata = parse_speaker_info(speaker_info_path)
    with zipfile.ZipFile(transcript_path) as transcript_archive:
        transcript_key_set, transcript_summary = transcript_keys(transcript_archive)

    audio_keys: set[str] = set()
    speaker_counts: collections.Counter[str] = collections.Counter()
    speaker_frame_counts: collections.defaultdict[str, list[int]] = (
        collections.defaultdict(list)
    )
    frame_members: collections.defaultdict[int, list[str]] = (
        collections.defaultdict(list)
    )
    frame_counts: list[int] = []
    data_byte_counts: list[int] = []
    pcm_digests: collections.Counter[str] = collections.Counter()
    pcm_digest_members: collections.defaultdict[str, list[str]] = (
        collections.defaultdict(list)
    )
    format_counts: collections.Counter[str] = collections.Counter()
    format_values: dict[str, dict[str, Any]] = {}
    directory_ids: set[str] = set()
    member_ids: set[str] = set()
    encrypted_member_count = 0
    special_member_count = 0
    uncompressed_audio_member_bytes = 0

    with zipfile.ZipFile(audio_path) as audio_archive:
        for info in audio_archive.infolist():
            member_id = info.filename.rstrip("/") if info.is_dir() else info.filename
            if member_id:
                safe_member_id(member_id)
            if member_id in member_ids:
                raise ValueError("VCTK audio member path is duplicated")
            member_ids.add(member_id)
            if info.flag_bits & 1:
                encrypted_member_count += 1
            unix_mode = info.external_attr >> 16
            unix_file_type = stat.S_IFMT(unix_mode)
            if unix_file_type not in {0, stat.S_IFDIR, stat.S_IFREG}:
                special_member_count += 1
                continue
            if info.is_dir():
                directory_ids.add(member_id)
                continue
            match = AUDIO_MEMBER.fullmatch(info.filename)
            if match is None:
                raise ValueError("VCTK audio archive contains a noncanonical member")
            speaker_id, utterance_id = match.groups()
            key = f"{speaker_id}_{utterance_id}"
            if key in audio_keys:
                raise ValueError("VCTK audio utterance key is duplicated")
            audio_keys.add(key)
            speaker_counts[speaker_id] += 1
            payload = audio_archive.read(info)
            if len(payload) != info.file_size:
                raise ValueError("VCTK audio member size differs")
            uncompressed_audio_member_bytes += info.file_size
            wave = read_wave(payload)
            pcm_digest = str(wave.pop("pcm_sha256"))
            frame_count = int(wave.pop("frame_count"))
            data_bytes = int(wave.pop("data_bytes"))
            pcm_digests[pcm_digest] += 1
            pcm_digest_members[pcm_digest].append(info.filename)
            frame_counts.append(frame_count)
            frame_members[frame_count].append(info.filename)
            speaker_frame_counts[speaker_id].append(frame_count)
            data_byte_counts.append(data_bytes)
            format_key = json.dumps(wave, sort_keys=True, separators=(",", ":"))
            format_counts[format_key] += 1
            format_values[format_key] = wave

    if encrypted_member_count or special_member_count:
        raise ValueError("VCTK audio archive contains encrypted or special members")
    if directory_ids != {AUDIO_ROOT.rstrip("/")}:
        raise ValueError("VCTK audio directory identity differs")
    if len(audio_keys) != expected.get("audio_file_count"):
        raise ValueError("VCTK audio file count differs")
    if dict(sorted(speaker_counts.items())) != expected_speaker_counts:
        raise ValueError("VCTK speaker audio counts differ")
    if len(speaker_metadata) != expected.get("speaker_metadata_row_count"):
        raise ValueError("VCTK speaker metadata row count differs")
    if set(speaker_counts) - set(speaker_metadata):
        raise ValueError("VCTK audio speaker metadata is missing")
    if set(log_rows) != audio_keys:
        raise ValueError("VCTK log/audio utterance identities differ")
    if transcript_key_set != audio_keys:
        raise ValueError("VCTK transcript/audio utterance identities differ")
    if log_summary != expected.get("log_summary"):
        raise ValueError("VCTK log summary differs")
    if transcript_summary != expected.get("transcript_summary"):
        raise ValueError("VCTK transcript summary differs")

    gender_counts = collections.Counter(
        speaker_metadata[speaker]["gender"] for speaker in speaker_counts
    )
    accent_counts = collections.Counter(
        speaker_metadata[speaker]["accent"] for speaker in speaker_counts
    )
    if dict(sorted(gender_counts.items())) != expected.get("gender_counts"):
        raise ValueError("VCTK gender counts differ")
    if dict(sorted(accent_counts.items())) != expected.get("accent_counts"):
        raise ValueError("VCTK accent counts differ")

    observed_formats = format_rows(format_counts, format_values)
    expected_format = expected.get("audio_format")
    if not isinstance(expected_format, dict) or len(observed_formats) != 1:
        raise ValueError("VCTK audio format count differs")
    if any(
        observed_formats[0].get(field) != value
        for field, value in expected_format.items()
    ):
        raise ValueError("VCTK audio format differs")

    duplicate_pcm_groups = {
        digest: count for digest, count in pcm_digests.items() if count > 1
    }
    duplicate_pcm_excess = sum(count - 1 for count in duplicate_pcm_groups.values())
    duplicate_pcm_file_count_excluded = sum(duplicate_pcm_groups.values())
    if len(duplicate_pcm_groups) != expected.get("duplicate_pcm_digest_group_count"):
        raise ValueError("VCTK duplicate PCM digest-group count differs")
    if duplicate_pcm_excess != expected.get("duplicate_pcm_file_count_excess"):
        raise ValueError("VCTK duplicate PCM excess count differs")
    if duplicate_pcm_file_count_excluded != expected.get(
        "duplicate_pcm_file_count_excluded"
    ):
        raise ValueError("VCTK duplicate PCM exclusion count differs")

    cap = rules.get("future_group_cap")
    if not isinstance(cap, dict):
        raise ValueError("VCTK future group-cap rule is absent")
    if (
        cap.get("state") != "preregistered_not_applied_before_source_freeze"
        or cap.get("ranking_algorithm") != CAP_RANKING_ALGORITHM
        or cap.get("ranking_prefix") != CAP_RANKING_PREFIX
        or cap.get("ranking_input") != CAP_RANKING_INPUT
    ):
        raise ValueError("VCTK future group-cap ranking rule differs")
    per_gender = cap.get("selected_speakers_per_gender")
    if (
        not isinstance(per_gender, int)
        or isinstance(per_gender, bool)
        or per_gender < 1
        or any(count < per_gender for count in gender_counts.values())
    ):
        raise ValueError("VCTK future group-cap count differs")
    projected_group_count = per_gender * len(gender_counts)
    if (
        projected_group_count != expected.get("conservative_partition_group_count")
        or projected_group_count != expected.get("source_group_count")
    ):
        raise ValueError("VCTK conservative partition count differs")

    minimum_frames = min(frame_counts)
    maximum_frames = max(frame_counts)
    audio_binding["zip_crc_verified"] = True
    log_binding["zip_crc_verified"] = True
    supporting_bindings["transcripts"]["zip_crc_verified"] = True
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "state": "source_identity_evidence_only",
        "source_id": SOURCE_ID,
        "benchmark_audio_generated": False,
        "scores_opened": False,
        "selection_authorized": False,
        "paths_redacted": True,
        "archive_bindings": {
            "audio": audio_binding,
            "metadata": log_binding,
        },
        "readme_binding": supporting_bindings["vctk_readme"],
        "supporting_artifact_bindings": supporting_bindings,
        "source_group_rules_binding": {"sha256": digest_file(rules_path, "sha256")},
        "provider_record": rules.get("provider_record"),
        "observed": {
            "audio_file_count": len(audio_keys),
            "audio_directory_member_ids": sorted(directory_ids),
            "audio_speaker_count": len(speaker_counts),
            "speaker_audio_file_counts": dict(sorted(speaker_counts.items())),
            "speaker_metadata_row_count": len(speaker_metadata),
            "speaker_metadata_ids_absent_from_audio": sorted(
                set(speaker_metadata) - set(speaker_counts)
            ),
            "speaker_gender_counts": dict(sorted(gender_counts.items())),
            "speaker_accent_counts": dict(sorted(accent_counts.items())),
            "log": log_summary,
            "transcripts": transcript_summary,
            "uncompressed_audio_member_bytes": uncompressed_audio_member_bytes,
            "riff_formats": observed_formats,
            "frame_count_range": {
                "minimum": minimum_frames,
                "minimum_archive_member_ids": sorted(frame_members[minimum_frames]),
                "maximum": maximum_frames,
                "maximum_archive_member_ids": sorted(frame_members[maximum_frames]),
            },
            "speaker_frame_count_ranges": {
                speaker: {"minimum": min(values), "maximum": max(values)}
                for speaker, values in sorted(speaker_frame_counts.items())
            },
            "data_byte_range": {
                "minimum": min(data_byte_counts),
                "maximum": max(data_byte_counts),
            },
            "distinct_pcm_digest_count": len(pcm_digests),
            "duplicate_pcm_digest_group_count": len(duplicate_pcm_groups),
            "duplicate_pcm_file_count_excess": duplicate_pcm_excess,
            "duplicate_pcm_file_count_excluded": duplicate_pcm_file_count_excluded,
            "duplicate_pcm_archive_member_groups": sorted(
                sorted(pcm_digest_members[digest]) for digest in duplicate_pcm_groups
            ),
            "encrypted_member_count": encrypted_member_count,
            "special_member_count": special_member_count,
        },
        "conservative_reference_boundary": {
            "rule": [
                "canonical clean_trainset_56spk_wav/pNNN_NNN.wav member",
                "exactly one matching provider log and transcript key",
                "speaker occurs in the bound VCTK speaker metadata",
                "WAV matches the bound PCM format",
                "every member of an exact repeated-PCM group is excluded",
            ],
            "eligible_audio_file_count": (
                len(audio_keys) - duplicate_pcm_file_count_excluded
            ),
            "observed_speaker_count": len(speaker_counts),
            "eligible_group_count": projected_group_count,
            "source_grouping_unit": "VCTK speaker identifier",
            "partition_grouping_unit": "VCTK speaker identifier",
            "future_group_cap": {
                "state": "preregistered_not_applied_before_source_freeze",
                "observed_gender_counts": dict(sorted(gender_counts.items())),
                "selected_speakers_per_gender": per_gender,
                "projected_group_count": projected_group_count,
                "ranking_algorithm": cap.get("ranking_algorithm"),
                "ranking_input": cap.get("ranking_input"),
                "ranking_prefix": cap.get("ranking_prefix"),
            },
            "future_selection_constraint": (
                "At source freeze, apply the preregistered content-independent "
                "speaker cap, then select at most one bounded excerpt per retained "
                "speaker. Preserve speaker, utterance, normalization/trim lineage, "
                "and provider identity. Do not treat the noisy derivatives as masters."
            ),
            "independence_limit": (
                "The archive exposes speaker identity but shares one VCTK recording "
                "collection and one clean-waveform normalization and trimming path. "
                "Keep it as one provider stratum and do not infer independent export "
                "pipelines from its utterance count."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-zip", type=Path, required=True)
    parser.add_argument("--log-zip", type=Path, required=True)
    parser.add_argument("--transcript-zip", type=Path, required=True)
    parser.add_argument("--speaker-info", type=Path, required=True)
    parser.add_argument("--vctk-readme", type=Path, required=True)
    parser.add_argument("--paper", type=Path, required=True)
    parser.add_argument("--license", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(
        args.audio_zip,
        args.log_zip,
        args.transcript_zip,
        args.speaker_info,
        args.vctk_readme,
        args.paper,
        args.license,
        args.rules,
    )
    if args.output:
        write_json_atomic(args.output, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
