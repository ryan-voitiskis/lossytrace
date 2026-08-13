#!/usr/bin/env python3
"""Bounded, atomic ODAQ reference extraction with live acquisition fail-closed."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path
from typing import Any, BinaryIO, Callable


ROOT = Path(__file__).resolve().parents[1]
FREEZE = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "odaq-reference-acquisition-freeze.json"
)
PREPARATION_PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "odaq-reference-extractor-preparation-plan.json"
)
BASE_SCRIPT = ROOT / "scripts" / "audit-perceptual-degradation-odaq.py"
SPEC = importlib.util.spec_from_file_location("odaq_base_audit", BASE_SCRIPT)
assert SPEC and SPEC.loader
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)
FOLDER_ID = re.compile(r"^[A-Za-z0-9._-]+$")
SOURCE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CRC32 = re.compile(r"^[0-9a-f]{8}$")
READ_BYTES = 1024 * 1024
LIVE_MAXIMUM_RANGE_BYTES = 56 * 1024 * 1024
LIVE_BLOCK_BYTES = 64 * 1024
LIVE_CACHE_BLOCKS = 16
REFERENCE_FREEZE_SHA256 = (
    "1a39f50013a4274f60ca7c1771ebad22dcafda6950db87d2ffe4acdfb58ab0e7"
)
FREEZE_EXECUTION_BOUNDARIES = {
    "actual_codec_generation_authorized",
    "listener_response_collection_authorized",
    "listening_score_access_authorized",
    "participant_contact_authorized",
    "perceptual_metric_execution_authorized",
    "reference_audio_acquisition_authorized",
    "source_track_selected",
    "stimulus_generation_authorized",
}
FREEZE_CLAIM_BOUNDARIES = {
    "one_odaq_provider_proves_independent_music_transfer",
    "published_processed_conditions_are_actual_codec_encodes",
    "published_scores_are_actual_codec_audibility_truth",
    "selected_references_are_final_validation",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(READ_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as output:
        temporary = Path(output.name)
        output.write(canonical_json_bytes(value))
        output.flush()
        os.fsync(output.fileno())
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def inside_repository(path: Path) -> bool:
    try:
        path.relative_to(ROOT)
    except ValueError:
        return False
    return True


def opaque_reference_id(plan_sha256: str, folder_id: str) -> str:
    return "odaq-ref-" + hashlib.sha256(
        f"{plan_sha256}\0{folder_id}".encode()
    ).hexdigest()[:24]


def member_name(folder_id: str) -> str:
    if not FOLDER_ID.fullmatch(folder_id):
        raise ValueError("ODAQ folder identifier is unsafe")
    return f"{BASE.LISTENING_PREFIX}{folder_id}/reference.wav"


def zip_binding(info: zipfile.ZipInfo) -> dict[str, Any]:
    return {
        "member_basename": Path(info.filename).name,
        "crc32": f"{info.CRC:08x}",
        "compressed_bytes": info.compress_size,
        "uncompressed_bytes": info.file_size,
        "compression_method": info.compress_type,
    }


def expected_zip_binding(reference: dict[str, Any]) -> dict[str, Any]:
    return {
        key: reference.get(key)
        for key in (
            "member_basename",
            "crc32",
            "compressed_bytes",
            "uncompressed_bytes",
            "compression_method",
        )
    }


def validate_freeze(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if plan.get("state") != (
        "exact_reference_members_frozen_audio_and_scores_unopened_acquisition_unauthorized"
    ):
        errors.append("reference freeze state differs")
    provider = plan.get("provider", {})
    if provider.get("record_id") != BASE.RECORD_ID or provider.get("doi") != BASE.RECORD_DOI:
        errors.append("reference freeze provider identity differs")
    if provider.get("archive_bytes") != BASE.ARCHIVE_BYTES:
        errors.append("reference freeze provider byte length differs")
    if provider.get("archive_checksum") != BASE.ARCHIVE_CHECKSUM:
        errors.append("reference freeze provider checksum differs")
    execution_boundary = plan.get("execution_boundary")
    if not isinstance(execution_boundary, dict):
        errors.append("reference freeze execution boundary is absent")
    else:
        if set(execution_boundary) != FREEZE_EXECUTION_BOUNDARIES:
            errors.append("reference freeze execution boundary keys differ")
        for key in FREEZE_EXECUTION_BOUNDARIES:
            if execution_boundary.get(key) is not False:
                errors.append(
                    f"committed reference freeze boundary must remain false: {key}"
                )
    references = plan.get("references", [])
    if not isinstance(references, list) or len(references) != 16:
        errors.append("committed reference count differs")
        return errors
    folders: set[str] = set()
    sources: set[str] = set()
    for reference in references:
        folder_id = reference.get("folder_id", "")
        source_id = reference.get("source_id", "")
        if not FOLDER_ID.fullmatch(str(folder_id)):
            errors.append("unsafe folder identifier")
        if not SOURCE_ID.fullmatch(str(source_id)):
            errors.append("unsafe source identifier")
        if folder_id in folders or source_id in sources:
            errors.append("reference identities must be unique")
        folders.add(folder_id)
        sources.add(source_id)
        if reference.get("member_basename") != "reference.wav":
            errors.append(f"non-reference member selected: {folder_id}")
        if not CRC32.fullmatch(str(reference.get("crc32", ""))):
            errors.append(f"invalid CRC32 binding: {folder_id}")
        if reference.get("compressed_bytes", 0) <= 0:
            errors.append(f"invalid compressed size: {folder_id}")
        if reference.get("uncompressed_bytes", 0) <= 0:
            errors.append(f"invalid uncompressed size: {folder_id}")
        if reference.get("compression_method") not in {
            zipfile.ZIP_STORED,
            zipfile.ZIP_DEFLATED,
        }:
            errors.append(f"unsupported ZIP compression: {folder_id}")
    selection = plan.get("selection", {})
    if selection.get("reference_count") != len(references):
        errors.append("reference freeze selection count differs")
    if selection.get("total_compressed_bytes") != sum(
        item.get("compressed_bytes", 0) for item in references
    ):
        errors.append("reference freeze compressed-byte total differs")
    if selection.get("total_uncompressed_bytes") != sum(
        item.get("uncompressed_bytes", 0) for item in references
    ):
        errors.append("reference freeze uncompressed-byte total differs")
    claim_boundary = plan.get("claim_boundary")
    if not isinstance(claim_boundary, dict):
        errors.append("reference freeze claim boundary is absent")
    else:
        if set(claim_boundary) != FREEZE_CLAIM_BOUNDARIES:
            errors.append("reference freeze claim boundary keys differ")
        for key in FREEZE_CLAIM_BOUNDARIES:
            if claim_boundary.get(key) is not False:
                errors.append(f"reference freeze claim boundary must remain false: {key}")
    if plan.get("paths_redacted") is not True:
        errors.append("reference freeze paths must remain redacted")
    return errors


def committed_clean_path(path: Path) -> bool:
    resolved = path.resolve()
    if not inside_repository(resolved):
        return False
    relative = resolved.relative_to(ROOT)
    commands = (
        ["git", "ls-files", "--error-unmatch", "--", str(relative)],
        ["git", "diff", "--quiet", "--", str(relative)],
        ["git", "diff", "--cached", "--quiet", "--", str(relative)],
    )
    return all(
        subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
        for command in commands
    )


def validate_live_authorization(
    authorization: dict[str, Any], freeze: dict[str, Any], freeze_sha256: str
) -> list[str]:
    errors: list[str] = []
    if authorization.get("schema_version") != 1:
        errors.append("authorization schema_version must equal 1")
    if authorization.get("state") != "reference_audio_acquisition_authorized":
        errors.append("reference acquisition is not authorized")
    if authorization.get("parent_freeze_sha256") != freeze_sha256:
        errors.append("authorization parent freeze differs")
    if authorization.get("source_track") != "permissive_odaq_cc_by_cc0":
        errors.append("authorized source track differs")
    if authorization.get("responsible_human_source_choice_present") is not True:
        errors.append("responsible-human source choice is absent")
    if authorization.get("physical_playback_declaration_present") is not True:
        errors.append("physical playback declaration is absent")
    if authorization.get("reference_audio_acquisition_authorized") is not True:
        errors.append("reference audio acquisition flag is false")
    for key in (
        "processed_condition_access_authorized",
        "listening_score_access_authorized",
        "stimulus_generation_authorized",
        "perceptual_metric_execution_authorized",
        "listener_response_collection_authorized",
    ):
        if authorization.get(key) is not False:
            errors.append(f"authorization boundary must remain false: {key}")
    if authorization.get("provider") != freeze.get("provider"):
        errors.append("authorized provider differs from freeze")
    if authorization.get("references") != freeze.get("references"):
        errors.append("authorized references differ from freeze")
    return errors


def validate_preparation_plan(
    plan: dict[str, Any], root: Path = ROOT
) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("preparation schema_version must equal 1")
    if plan.get("state") != (
        "synthetic_extractor_verified_live_provider_acquisition_unauthorized"
    ):
        errors.append("extractor preparation state differs")
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
    for key, value in plan.get("access_boundary", {}).items():
        if value is not False:
            errors.append(f"access boundary must remain false: {key}")
    implementation = plan.get("implementation", {})
    expected = {
        "remote_block_bytes": LIVE_BLOCK_BYTES,
        "remote_cache_blocks": LIVE_CACHE_BLOCKS,
        "remote_cumulative_response_limit_bytes": LIVE_MAXIMUM_RANGE_BYTES,
        "stream_chunk_bytes": READ_BYTES,
        "minimum_live_free_disk_gib": 15,
        "maximum_sustained_workers": 1,
    }
    for key, value in expected.items():
        if implementation.get(key) != value:
            errors.append(f"extractor implementation boundary differs: {key}")
    for key in (
        "exact_zip_binding_verified_before_member_open",
        "reference_basename_only",
        "opaque_output_names",
        "atomic_partial_write_and_rename",
        "per_member_sha256_and_crc32_verified",
        "pcm_geometry_verified",
        "journaled_resume_and_retained_reverification",
        "resume_journal_paths_and_bindings_revalidated",
        "private_output_outside_repository_required",
        "full_archive_persistence_forbidden",
        "authorization_checked_before_provider_request",
        "exact_freeze_path_and_sha256_required",
        "authorization_file_committed_and_clean_required",
    ):
        if implementation.get(key) is not True:
            errors.append(f"extractor implementation guarantee differs: {key}")
    testing = plan.get("testing", {})
    for key in (
        "synthetic_reference_extraction_passed",
        "processed_and_score_members_ignored",
        "binding_mismatch_failure_passed",
        "disk_reserve_failure_passed",
        "resume_reverification_failure_passed",
        "tampered_journal_path_rejection_passed",
        "repository_output_rejection_passed",
        "unsafe_identifier_rejection_passed",
        "live_refusal_before_provider_access_passed",
        "range_budget_bound_test_passed",
    ):
        if testing.get(key) is not True:
            errors.append(f"extractor test evidence differs: {key}")
    decision = plan.get("decision", {})
    if decision.get("synthetic_extractor_ready") is not True:
        errors.append("synthetic extractor is not ready")
    for key in (
        "source_track_selected",
        "live_authorization_present",
        "provider_audio_acquired",
        "processed_conditions_opened",
        "listening_scores_opened",
        "stimuli_generated",
        "human_collection_authorized",
    ):
        if decision.get(key) is not False:
            errors.append(f"extractor decision boundary must remain false: {key}")
    return errors


def wav_facts(path: Path) -> dict[str, int | str]:
    file_bytes = path.stat().st_size
    with path.open("rb") as source:
        header = source.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
            raise ValueError("extracted member is not a RIFF/WAVE file")
        riff_bytes = struct.unpack_from("<I", header, 4)[0]
        if riff_bytes + 8 != file_bytes:
            raise ValueError("extracted RIFF byte length differs")

        format_fields: tuple[int, int, int, int, int, int] | None = None
        data_bytes: int | None = None
        fact_frames: int | None = None
        while source.tell() < file_bytes:
            chunk_header = source.read(8)
            if len(chunk_header) != 8:
                raise ValueError("extracted WAV chunk header is truncated")
            chunk_id = chunk_header[:4]
            chunk_bytes = struct.unpack_from("<I", chunk_header, 4)[0]
            chunk_start = source.tell()
            chunk_end = chunk_start + chunk_bytes
            padded_end = chunk_end + (chunk_bytes & 1)
            if padded_end > file_bytes:
                raise ValueError("extracted WAV chunk exceeds RIFF length")
            if chunk_id == b"fmt ":
                if format_fields is not None or chunk_bytes not in {16, 18}:
                    raise ValueError("extracted WAV format chunk differs")
                payload = source.read(chunk_bytes)
                format_fields = struct.unpack_from("<HHIIHH", payload)
                if chunk_bytes == 18 and struct.unpack_from("<H", payload, 16)[0] != 0:
                    raise ValueError("extracted WAV format extension is unsupported")
            elif chunk_id == b"fact":
                if fact_frames is not None or chunk_bytes != 4:
                    raise ValueError("extracted WAV fact chunk differs")
                fact_frames = struct.unpack("<I", source.read(4))[0]
            elif chunk_id == b"data":
                if data_bytes is not None:
                    raise ValueError("extracted WAV has multiple data chunks")
                data_bytes = chunk_bytes
            source.seek(padded_end)

    if format_fields is None or data_bytes is None:
        raise ValueError("extracted WAV is missing format or data")
    format_tag, channels, sample_rate, byte_rate, block_align, bits = format_fields
    if format_tag == 1 and bits in {16, 24, 32}:
        sample_encoding = "signed_integer_pcm"
    elif format_tag == 3 and bits == 32:
        sample_encoding = "ieee_float_pcm"
    else:
        raise ValueError("extracted WAV sample encoding is unsupported")
    expected_block_align = channels * (bits // 8)
    if (
        channels not in {1, 2}
        or sample_rate not in {44_100, 48_000}
        or block_align != expected_block_align
        or byte_rate != sample_rate * block_align
        or data_bytes == 0
        or data_bytes % block_align != 0
    ):
        raise ValueError("extracted WAV geometry is unsupported")
    frames = data_bytes // block_align
    if sample_encoding == "ieee_float_pcm" and fact_frames != frames:
        raise ValueError("extracted float WAV fact count differs")
    return {
        "sample_rate_hz": sample_rate,
        "channel_count": channels,
        "bit_depth": bits,
        "frame_count": frames,
        "sample_encoding": sample_encoding,
    }


def verify_retained(path: Path, record: dict[str, Any]) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError("retained reference is not a regular file")
    if path.stat().st_size != record.get("byte_length"):
        raise ValueError("retained reference byte length differs")
    if sha256_file(path) != record.get("sha256"):
        raise ValueError("retained reference SHA-256 differs")
    if wav_facts(path) != record.get("pcm_geometry"):
        raise ValueError("retained reference PCM geometry differs")


def completed_inventory_sha256(completed: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(completed, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_resume_state(
    state: dict[str, Any], plan: dict[str, Any], plan_sha256: str, minimum_free_bytes: int
) -> None:
    if state.get("schema_version") != 1:
        raise ValueError("existing acquisition journal differs: schema version")
    if state.get("state") not in {
        "reference_acquisition_in_progress",
        "reference_acquisition_complete",
    }:
        raise ValueError("existing acquisition journal differs: state")
    if state.get("plan_sha256") != plan_sha256:
        raise ValueError("existing acquisition journal differs: plan SHA-256")
    if state.get("minimum_free_bytes") != minimum_free_bytes:
        raise ValueError("existing acquisition journal differs: disk reserve")
    for key in (
        "processed_condition_opened",
        "listening_score_opened",
        "metric_score_opened",
    ):
        if state.get(key) is not False:
            raise ValueError(f"existing acquisition journal differs: {key}")
    completed = state.get("completed")
    if not isinstance(completed, list):
        raise ValueError("existing acquisition journal differs: completed inventory")
    expected = {
        reference["folder_id"]: reference for reference in plan.get("references", [])
    }
    seen: set[str] = set()
    for record in completed:
        if not isinstance(record, dict):
            raise ValueError("existing acquisition journal differs: completed record")
        folder_id = record.get("folder_id")
        reference = expected.get(folder_id)
        if reference is None or folder_id in seen:
            raise ValueError("existing acquisition journal differs: reference identity")
        seen.add(folder_id)
        opaque_id = opaque_reference_id(plan_sha256, folder_id)
        if record.get("opaque_reference_id") != opaque_id or record.get(
            "relative_path"
        ) != f"sources/{opaque_id}.wav":
            raise ValueError("existing acquisition journal differs: retained path")
        if (
            record.get("source_id") != reference["source_id"]
            or record.get("crc32") != reference["crc32"]
            or record.get("byte_length") != reference["uncompressed_bytes"]
            or record.get("licence_record_ids") != reference["licence_record_ids"]
            or not SHA256.fullmatch(str(record.get("sha256", "")))
            or not isinstance(record.get("pcm_geometry"), dict)
        ):
            raise ValueError("existing acquisition journal differs: retained binding")
    if state.get("completed_count", len(completed)) != len(completed):
        raise ValueError("existing acquisition journal differs: completed count")
    if state["state"] == "reference_acquisition_complete":
        if len(completed) != len(expected):
            raise ValueError("existing acquisition journal differs: incomplete final state")
        if state.get("retained_audio_bytes") != sum(
            record["byte_length"] for record in completed
        ):
            raise ValueError("existing acquisition journal differs: retained byte total")
        if state.get("completed_inventory_sha256") != completed_inventory_sha256(
            completed
        ):
            raise ValueError("existing acquisition journal differs: inventory SHA-256")


def stream_member(source: BinaryIO, destination: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    crc32 = 0
    byte_length = 0
    with destination.open("xb") as output:
        for chunk in iter(lambda: source.read(READ_BYTES), b""):
            output.write(chunk)
            digest.update(chunk)
            crc32 = zlib.crc32(chunk, crc32)
            byte_length += len(chunk)
        output.flush()
        os.fsync(output.fileno())
    return {
        "sha256": digest.hexdigest(),
        "crc32": f"{crc32 & 0xFFFFFFFF:08x}",
        "byte_length": byte_length,
    }


def extract_references(
    *,
    plan: dict[str, Any],
    plan_sha256: str,
    source: BinaryIO,
    output_root: Path,
    minimum_free_bytes: int,
    disk_free: Callable[[Path], int] | None = None,
) -> dict[str, Any]:
    if minimum_free_bytes < 0:
        raise ValueError("minimum free-byte reserve must be non-negative")
    root = output_root.resolve()
    if inside_repository(root):
        raise ValueError("reference output root must remain outside the repository")
    state_path = root / "acquisition.json"
    sources_root = root / "sources"
    partial_root = root / ".partial"
    if state_path.exists():
        if state_path.is_symlink() or not state_path.is_file():
            raise ValueError("existing acquisition journal must be a regular file")
        for directory in (sources_root, partial_root):
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError("existing acquisition directory differs")
        state = load_json(state_path)
        validate_resume_state(state, plan, plan_sha256, minimum_free_bytes)
    else:
        if root.exists() and any(root.iterdir()):
            raise ValueError("refusing non-empty output root without state")
        sources_root.mkdir(parents=True, mode=0o700)
        partial_root.mkdir(mode=0o700)
        root.chmod(0o700)
        state = {
            "schema_version": 1,
            "state": "reference_acquisition_in_progress",
            "plan_sha256": plan_sha256,
            "minimum_free_bytes": minimum_free_bytes,
            "processed_condition_opened": False,
            "listening_score_opened": False,
            "metric_score_opened": False,
            "completed": [],
        }
        atomic_json(state_path, state)
    completed = {item["folder_id"]: item for item in state.get("completed", [])}
    for record in completed.values():
        verify_retained(root / record["relative_path"], record)

    get_free = disk_free or (lambda path: shutil.disk_usage(path).free)
    references = plan.get("references", [])
    with zipfile.ZipFile(source) as archive:
        infos = {item.filename: item for item in archive.infolist()}
        for reference in references:
            folder_id = reference["folder_id"]
            if folder_id in completed:
                continue
            name = member_name(folder_id)
            info = infos.get(name)
            if info is None or info.is_dir():
                raise ValueError(f"frozen reference member is absent: {folder_id}")
            if zip_binding(info) != expected_zip_binding(reference):
                raise ValueError(f"frozen reference ZIP binding differs: {folder_id}")
            required = reference["uncompressed_bytes"]
            if get_free(root) - required < minimum_free_bytes:
                raise ValueError("reference extraction would cross disk reserve")
            opaque_id = opaque_reference_id(plan_sha256, folder_id)
            partial = partial_root / f"{opaque_id}.wav.partial"
            destination = sources_root / f"{opaque_id}.wav"
            if partial.exists() or destination.exists():
                raise ValueError(f"unjournaled reference output exists: {folder_id}")
            with archive.open(info, "r") as member:
                facts = stream_member(member, partial)
            if (
                facts["byte_length"] != reference["uncompressed_bytes"]
                or facts["crc32"] != reference["crc32"]
            ):
                raise ValueError(f"extracted reference verification differs: {folder_id}")
            geometry = wav_facts(partial)
            partial.replace(destination)
            destination.chmod(0o600)
            record = {
                "folder_id": folder_id,
                "source_id": reference["source_id"],
                "opaque_reference_id": opaque_id,
                "relative_path": f"sources/{opaque_id}.wav",
                "sha256": facts["sha256"],
                "crc32": facts["crc32"],
                "byte_length": facts["byte_length"],
                "pcm_geometry": geometry,
                "licence_record_ids": reference["licence_record_ids"],
            }
            state["completed"].append(record)
            state["completed"].sort(key=lambda item: item["folder_id"])
            state["completed_count"] = len(state["completed"])
            atomic_json(state_path, state)
            completed[folder_id] = record

    if len(completed) != len(references):
        raise ValueError("reference acquisition did not complete")
    state["state"] = "reference_acquisition_complete"
    state["completed_count"] = len(state["completed"])
    state["retained_audio_bytes"] = sum(
        item["byte_length"] for item in state["completed"]
    )
    state["completed_inventory_sha256"] = completed_inventory_sha256(
        state["completed"]
    )
    atomic_json(state_path, state)
    return state


def command_acquire(args: argparse.Namespace) -> int:
    freeze_path = args.freeze.resolve()
    authorization_path = args.authorization.resolve()
    output_root = args.output_root.resolve()
    freeze = load_json(freeze_path)
    freeze_errors = validate_freeze(freeze)
    if freeze_errors:
        raise SystemExit("; ".join(freeze_errors))
    freeze_sha256 = sha256_file(freeze_path)
    if freeze_path != FREEZE.resolve() or freeze_sha256 != REFERENCE_FREEZE_SHA256:
        raise SystemExit("reference freeze path or SHA-256 differs from the exact freeze")
    authorization = load_json(authorization_path)
    authorization_errors = validate_live_authorization(
        authorization, freeze, freeze_sha256
    )
    if authorization_errors:
        raise SystemExit("; ".join(authorization_errors))
    if not committed_clean_path(freeze_path):
        raise SystemExit("reference freeze must be committed and clean")
    if not committed_clean_path(authorization_path):
        raise SystemExit("acquisition authorization must be committed and clean")
    if inside_repository(output_root):
        raise SystemExit("reference output root must remain outside the repository")
    if not output_root.parent.is_dir():
        raise SystemExit("reference output parent must already exist")
    free = shutil.disk_usage(output_root.parent).free
    minimum_free_bytes = 15 * 1024**3
    if free - freeze["selection"]["total_uncompressed_bytes"] < minimum_free_bytes:
        raise SystemExit("reference acquisition would cross the 15 GiB reserve")
    record = BASE.fetch_record()
    provider = BASE.validate_record(record)
    remote = BASE.HTTPRangeReader(
        provider["content_url"],
        expected_size=BASE.ARCHIVE_BYTES,
        block_bytes=LIVE_BLOCK_BYTES,
        cache_blocks=LIVE_CACHE_BLOCKS,
        maximum_response_bytes=LIVE_MAXIMUM_RANGE_BYTES,
    )
    state = extract_references(
        plan=authorization,
        plan_sha256=sha256_file(authorization_path),
        source=remote,
        output_root=output_root,
        minimum_free_bytes=minimum_free_bytes,
    )
    state["range_access"] = remote.stats()
    atomic_json(output_root / "acquisition.json", state)
    print(
        json.dumps(
            {
                "completed_count": state["completed_count"],
                "retained_audio_bytes": state["retained_audio_bytes"],
                "status": state["state"],
            },
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    validate = subcommands.add_parser("validate-freeze")
    validate.add_argument("--freeze", type=Path, default=FREEZE)
    validate_preparation = subcommands.add_parser("validate-preparation")
    validate_preparation.add_argument(
        "--plan", type=Path, default=PREPARATION_PLAN
    )
    acquire = subcommands.add_parser("acquire")
    acquire.add_argument("--freeze", type=Path, default=FREEZE)
    acquire.add_argument("--authorization", type=Path, required=True)
    acquire.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "validate-freeze":
        errors = validate_freeze(load_json(args.freeze))
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"validated {args.freeze}")
        return 0
    if args.command == "validate-preparation":
        errors = validate_preparation_plan(load_json(args.plan))
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"validated {args.plan}")
        return 0
    return command_acquire(args)


if __name__ == "__main__":
    raise SystemExit(main())
