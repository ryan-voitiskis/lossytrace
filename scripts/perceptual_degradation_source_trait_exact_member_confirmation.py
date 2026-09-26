#!/usr/bin/env python3
"""Acquire and measure the two frozen source-trait exact members.

The provider originals remain private. Decoded integer PCM is streamed from
FFmpeg and is never written to disk. Public output is path-free and omits
encoded-file and decoded-PCM hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Any, BinaryIO


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1"
    / "source-trait-exact-member-confirmation-plan.json"
)
SCRIPT_PATH = Path(__file__).resolve()
RESERVE_BYTES = 15 * 1024**3
READ_BYTES = 1024 * 1024


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(READ_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(canonical_json_bytes(value))
        handle.flush()
        os.fsync(handle.fileno())
    temporary.chmod(0o600)
    temporary.replace(path)


def inside_repository(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


def require_private_root(path: Path) -> Path:
    resolved = path.resolve()
    if inside_repository(resolved):
        raise ValueError("private root must remain outside the repository")
    resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
    resolved.chmod(0o700)
    if shutil.disk_usage(resolved).free < RESERVE_BYTES:
        raise ValueError("private volume is below the frozen 15 GiB reserve")
    return resolved


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("plan schema differs")
    if plan.get("plan_id") != (
        "perceptual-degradation-source-trait-exact-member-confirmation-20260818-001"
    ):
        errors.append("plan identity differs")
    if plan.get("state") != (
        "two_exact_provider_originals_and_score_free_integer_pcm_descriptors_frozen_before_audio_access"
    ):
        errors.append("plan state differs")
    resources = plan.get("resources", {})
    if resources != {
        "maximum_workers": 1,
        "minimum_free_disk_gib": 15,
        "private_replay_count": 2,
        "private_replays_must_be_byte_identical": True,
        "retain_decoded_or_derived_pcm": False,
        "retain_provider_originals_privately": True,
    }:
        errors.append("resource boundary differs")
    authorization = plan.get("authorization", {})
    expected_true = {
        "two_exact_provider_originals_acquisition_authorized",
        "original_audio_sample_read_authorized",
        "frozen_integer_pcm_descriptor_execution_authorized",
        "private_original_retention_authorized",
        "path_free_score_free_publication_authorized",
    }
    expected_false = {
        "other_source_member_access_authorized",
        "provider_processed_condition_or_score_access_authorized",
        "derived_pcm_retention_authorized",
        "codec_generation_authorized",
        "perceptual_metric_execution_authorized",
        "playback_authorized",
        "human_collection_authorized",
        "sealed_evidence_access_authorized",
        "no_reference_training_authorized",
        "source_trait_assignment_authorized",
        "source_manifest_allocation_authorized",
        "validation_claim_or_public_verdict_authorized",
    }
    for key in expected_true:
        if authorization.get(key) is not True:
            errors.append(f"authorization must remain true: {key}")
    for key in expected_false:
        if authorization.get(key) is not False:
            errors.append(f"authorization must remain false: {key}")
    members = plan.get("members", [])
    if [item.get("member_id") for item in members] != [
        "freesound_sound_426894",
        "freesound_sound_610933",
    ]:
        errors.append("exact member inventory differs")
    if [item.get("trait_id") for item in members] != ["quiet", "clipped"]:
        errors.append("trait inventory differs")
    for member in members:
        if member.get("licence") != "CC0 1.0":
            errors.append(f"member licence differs: {member.get('member_id')}")
        if member.get("provider_original_only") is not True:
            errors.append(f"member original-only boundary differs: {member.get('member_id')}")
    descriptors = plan.get("descriptor_contract", {})
    if descriptors.get("integer_pcm_bit_depth") != 24:
        errors.append("integer PCM bit depth differs")
    if descriptors.get("classification_threshold_frozen") is not False:
        errors.append("post-observation classification must remain closed")
    if descriptors.get("quiet", {}).get("block_duration_frames") != "sample_rate_hz":
        errors.append("quiet block geometry differs")
    clipped = descriptors.get("clipped", {})
    if clipped.get("near_rail_minimum_ratio") != {"numerator": 99, "denominator": 100}:
        errors.append("near-rail threshold differs")
    if clipped.get("high_magnitude_minimum_ratio") != {
        "numerator": 95,
        "denominator": 100,
    }:
        errors.append("high-magnitude threshold differs")
    if clipped.get("minimum_identical_plateau_frames") != 3:
        errors.append("plateau length differs")
    if clipped.get("near_flat_window_frames") != 3:
        errors.append("near-flat window differs")
    if clipped.get("near_flat_maximum_range_lsb") != 8388:
        errors.append("near-flat range differs")
    bindings = plan.get("bindings", {})
    for binding_id, binding in bindings.items():
        relative = Path(str(binding.get("path", "")))
        bound = root / relative
        if relative.is_absolute() or ".." in relative.parts or not bound.is_file():
            errors.append(f"invalid or missing binding: {binding_id}")
        elif sha256_file(bound) != binding.get("sha256"):
            errors.append(f"binding sha256 differs: {binding_id}")
    publication = plan.get("publication_boundary", {})
    if publication.get("path_free_aggregate_descriptor_observations_allowed") is not True:
        errors.append("aggregate publication boundary differs")
    for key in (
        "private_paths_allowed",
        "provider_original_bytes_allowed",
        "per_reference_encoded_or_pcm_hashes_allowed",
        "perceptual_claims_allowed",
        "trait_assignments_allowed",
        "validation_claims_or_verdicts_allowed",
    ):
        if publication.get(key) is not False:
            errors.append(f"publication boundary must remain false: {key}")
    serialized = json.dumps(plan, sort_keys=True)
    if "/Users/" in serialized or "Application Support" in serialized:
        errors.append("plan exposes a private path")
    return sorted(set(errors))


def require_committed_freeze(plan: dict[str, Any]) -> None:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    for path in (PLAN_PATH, SCRIPT_PATH):
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path.relative_to(ROOT))],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        clean = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", str(path.relative_to(ROOT))],
            cwd=ROOT,
        )
        if tracked.returncode or clean.returncode:
            raise ValueError("plan and runner must be committed and clean before audio access")


def command_version(path: Path) -> str:
    result = subprocess.run(
        [str(path), "-version"], check=True, capture_output=True, text=True
    )
    return result.stdout.splitlines()[0]


def validate_toolchain(plan: dict[str, Any], ffmpeg: Path, ffprobe: Path) -> dict[str, Any]:
    expected = plan["toolchain"]
    observed = {
        "ffmpeg_sha256": sha256_file(ffmpeg),
        "ffmpeg_version": command_version(ffmpeg),
        "ffprobe_sha256": sha256_file(ffprobe),
        "ffprobe_version": command_version(ffprobe),
    }
    if observed != expected:
        raise ValueError("live FFmpeg/FFprobe provenance differs from the frozen toolchain")
    return observed


def probe_audio(ffprobe: Path, path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(result.stdout)
    streams = [row for row in value.get("streams", []) if row.get("codec_type") == "audio"]
    if len(streams) != 1 or len(value.get("streams", [])) != 1:
        raise ValueError("provider original must contain exactly one audio stream")
    stream = streams[0]
    format_row = value.get("format", {})
    return {
        "codec_name": stream.get("codec_name"),
        "sample_rate_hz": int(stream.get("sample_rate", 0)),
        "channel_count": int(stream.get("channels", 0)),
        "bit_depth": int(stream.get("bits_per_raw_sample") or stream.get("bits_per_sample") or 0),
        "duration_seconds": float(stream.get("duration") or format_row.get("duration") or 0),
        "format_names": str(format_row.get("format_name", "")).split(","),
        "byte_length": path.stat().st_size,
    }


def validate_member_probe(member: dict[str, Any], observed: dict[str, Any]) -> None:
    expected = member["expected_original"]
    for key in ("codec_name", "sample_rate_hz", "channel_count", "bit_depth"):
        if observed.get(key) != expected.get(key):
            raise ValueError(f"provider original geometry differs for {member['member_id']}: {key}")
    if expected["format_name"] not in observed["format_names"]:
        raise ValueError(f"provider original container differs for {member['member_id']}")
    if not expected["duration_seconds_minimum"] <= observed["duration_seconds"] <= expected["duration_seconds_maximum"]:
        raise ValueError(f"provider original duration differs for {member['member_id']}")
    if not expected["byte_length_minimum"] <= observed["byte_length"] <= expected["byte_length_maximum"]:
        raise ValueError(f"provider original byte length differs for {member['member_id']}")


def opaque_name(plan_sha256: str, member: dict[str, Any]) -> str:
    digest = hashlib.sha256(f"{plan_sha256}:{member['member_id']}".encode()).hexdigest()[:24]
    return f"source-{digest}.{member['expected_original']['extension']}"


def verify_record(root: Path, record: dict[str, Any], member: dict[str, Any], ffprobe: Path) -> Path:
    path = root / record["relative_path"]
    if path.is_symlink() or not path.is_file():
        raise ValueError("retained provider original is missing or not regular")
    if sha256_file(path) != record.get("encoded_sha256"):
        raise ValueError("retained provider original SHA-256 differs")
    observed = probe_audio(ffprobe, path)
    validate_member_probe(member, observed)
    if observed != record.get("probe"):
        raise ValueError("retained provider original probe differs")
    return path


def import_originals(
    plan: dict[str, Any], private_root: Path, inputs: dict[str, Path], ffprobe: Path
) -> dict[str, Any]:
    root = require_private_root(private_root)
    journal_path = root / "acquisition.json"
    plan_sha = sha256_file(PLAN_PATH)
    if journal_path.exists():
        journal = load_json(journal_path)
        if journal.get("plan_sha256") != plan_sha:
            raise ValueError("existing acquisition journal binds a different plan")
    else:
        journal = {
            "schema_version": 1,
            "state": "two_exact_provider_originals_acquisition_in_progress",
            "plan_sha256": plan_sha,
            "processed_conditions_or_scores_accessed": False,
            "other_source_members_accessed": False,
            "records": [],
        }
        atomic_json(journal_path, journal)
    records = {row["member_id"]: row for row in journal.get("records", [])}
    members = {row["member_id"]: row for row in plan["members"]}
    if set(records) - set(members):
        raise ValueError("existing acquisition journal contains an out-of-scope member")
    sources = root / "provider-originals"
    sources.mkdir(exist_ok=True, mode=0o700)
    for member_id, record in records.items():
        verify_record(root, record, members[member_id], ffprobe)
    pending_bytes = sum(
        inputs[member_id].stat().st_size
        for member_id in members
        if member_id not in records
    )
    if shutil.disk_usage(root).free - pending_bytes < RESERVE_BYTES:
        raise ValueError("acquisition would cross the frozen 15 GiB reserve")
    for member_id in ("freesound_sound_426894", "freesound_sound_610933"):
        if member_id in records:
            continue
        source = inputs.get(member_id)
        if source is None or source.is_symlink() or not source.is_file():
            raise ValueError(f"missing regular provider original input: {member_id}")
        member = members[member_id]
        observed = probe_audio(ffprobe, source)
        validate_member_probe(member, observed)
        digest = sha256_file(source)
        destination = sources / opaque_name(plan_sha, member)
        if destination.exists():
            raise ValueError("unjournaled retained provider original exists")
        source.replace(destination)
        destination.chmod(0o600)
        record = {
            "member_id": member_id,
            "relative_path": str(destination.relative_to(root)),
            "encoded_sha256": digest,
            "probe": observed,
            "licence": member["licence"],
            "source_url": member["source_url"],
        }
        journal["records"].append(record)
        journal["records"].sort(key=lambda row: row["member_id"])
        atomic_json(journal_path, journal)
        records[member_id] = record
    journal["state"] = "two_exact_provider_originals_acquired_and_verified"
    journal["completed_count"] = len(journal["records"])
    journal["retained_original_bytes"] = sum(row["probe"]["byte_length"] for row in journal["records"])
    atomic_json(journal_path, journal)
    atomic_json(
        root / "attribution.json",
        {
            "schema_version": 1,
            "records": [
                {
                    "member_id": member["member_id"],
                    "licence": member["licence"],
                    "recommended_attribution": member["recommended_attribution"],
                    "source_url": member["source_url"],
                }
                for member in plan["members"]
            ],
        },
    )
    return journal


def dbfs_from_power(numerator: int, denominator: int) -> str | None:
    if numerator == 0:
        return None
    return f"{10.0 * math.log10(numerator / denominator):.6f}"


def dbfs_from_peak(peak: int, full_scale: int) -> str | None:
    if peak == 0:
        return None
    return f"{20.0 * math.log10(peak / full_scale):.6f}"


def iter_s24_frames(stream: BinaryIO, channels: int):
    frame_bytes = channels * 4
    remainder = b""
    while True:
        chunk = stream.read(READ_BYTES)
        if not chunk:
            break
        chunk = remainder + chunk
        complete = len(chunk) - (len(chunk) % frame_bytes)
        body, remainder = chunk[:complete], chunk[complete:]
        for offset in range(0, len(body), frame_bytes):
            values = struct.unpack_from("<" + "i" * channels, body, offset)
            if any(value & 0xFF for value in values):
                raise ValueError("FFmpeg s32 decode did not preserve 24-bit padding")
            yield tuple(value >> 8 for value in values)
    if remainder:
        raise ValueError("decoded PCM stream ended mid-frame")


def measure_member(
    ffmpeg: Path, path: Path, member: dict[str, Any], probe: dict[str, Any], plan: dict[str, Any]
) -> dict[str, Any]:
    command = [
        str(ffmpeg), "-v", "error", "-nostdin", "-i", str(path),
        "-map", "0:a:0", "-vn", "-sn", "-dn", "-c:a", "pcm_s32le",
        "-f", "s32le", "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    channels = probe["channel_count"]
    sample_rate = probe["sample_rate_hz"]
    full_scale = 1 << 23
    sample_count = 0
    frame_count = 0
    nonzero_samples = 0
    nonzero_frames = 0
    peak = 0
    sum_squares = 0
    channel = [
        {"sample_count": 0, "nonzero_sample_count": 0, "peak_abs_code": 0, "sum_squares": 0}
        for _ in range(channels)
    ]
    active_blocks: set[int] = set()
    rail_samples = 0
    near_rail_samples = 0
    identical_plateau_runs = 0
    identical_plateau_samples = 0
    maximum_identical_plateau_frames = 0
    near_flat_windows = 0
    run_value: list[int | None] = [None] * channels
    run_length = [0] * channels
    history: list[list[int]] = [[] for _ in range(channels)]
    clipped_contract = plan["descriptor_contract"]["clipped"]
    for frame in iter_s24_frames(process.stdout, channels):
        any_nonzero = False
        for index, value in enumerate(frame):
            magnitude = abs(value)
            sample_count += 1
            channel[index]["sample_count"] += 1
            sum_squares += value * value
            channel[index]["sum_squares"] += value * value
            peak = max(peak, magnitude)
            channel[index]["peak_abs_code"] = max(channel[index]["peak_abs_code"], magnitude)
            if value:
                any_nonzero = True
                nonzero_samples += 1
                channel[index]["nonzero_sample_count"] += 1
            if value in {-(1 << 23), (1 << 23) - 1}:
                rail_samples += 1
            if magnitude * 100 >= full_scale * 99:
                near_rail_samples += 1
            if run_value[index] == value:
                run_length[index] += 1
            else:
                if (
                    run_value[index] is not None
                    and abs(run_value[index]) * 100 >= full_scale * 95
                    and run_length[index] >= clipped_contract["minimum_identical_plateau_frames"]
                ):
                    identical_plateau_runs += 1
                    identical_plateau_samples += run_length[index]
                    maximum_identical_plateau_frames = max(maximum_identical_plateau_frames, run_length[index])
                run_value[index] = value
                run_length[index] = 1
            history[index].append(value)
            if len(history[index]) > clipped_contract["near_flat_window_frames"]:
                history[index].pop(0)
            if len(history[index]) == clipped_contract["near_flat_window_frames"]:
                values = history[index]
                same_sign = all(item >= 0 for item in values) or all(item <= 0 for item in values)
                high = all(abs(item) * 100 >= full_scale * 95 for item in values)
                if same_sign and high and max(values) - min(values) <= clipped_contract["near_flat_maximum_range_lsb"]:
                    near_flat_windows += 1
        if any_nonzero:
            nonzero_frames += 1
            active_blocks.add(frame_count // sample_rate)
        frame_count += 1
    for index in range(channels):
        value = run_value[index]
        if (
            value is not None
            and abs(value) * 100 >= full_scale * 95
            and run_length[index] >= clipped_contract["minimum_identical_plateau_frames"]
        ):
            identical_plateau_runs += 1
            identical_plateau_samples += run_length[index]
            maximum_identical_plateau_frames = max(maximum_identical_plateau_frames, run_length[index])
    stderr = process.stderr.read() if process.stderr is not None else b""
    return_code = process.wait()
    process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()
    if return_code:
        raise ValueError(f"FFmpeg decode failed: {stderr.decode(errors='replace').strip()}")
    if frame_count == 0:
        raise ValueError("decoded PCM stream is empty")
    for row in channel:
        row["rms_dbfs"] = dbfs_from_power(
            row["sum_squares"], row["sample_count"] * full_scale * full_scale
        )
        row["peak_dbfs"] = dbfs_from_peak(row["peak_abs_code"], full_scale)
    common = {
        "frame_count": frame_count,
        "sample_count": sample_count,
        "full_scale_magnitude": full_scale,
        "peak_abs_code": peak,
        "peak_dbfs": dbfs_from_peak(peak, full_scale),
        "sum_squares": sum_squares,
        "rms_dbfs": dbfs_from_power(sum_squares, sample_count * full_scale * full_scale),
        "channels": channel,
    }
    if member["trait_id"] == "quiet":
        block_count = (frame_count + sample_rate - 1) // sample_rate
        return {
            "descriptor_ids": ["absolute_pcm_level_measurement", "nonzero_activity_support"],
            **common,
            "nonzero_sample_count": nonzero_samples,
            "nonzero_frame_count": nonzero_frames,
            "one_second_block_count": block_count,
            "active_one_second_block_count": len(active_blocks),
            "nonzero_activity_present": nonzero_frames > 0,
            "quiet_classification_threshold_applied": False,
        }
    support = rail_samples > 0 or identical_plateau_runs > 0 or near_flat_windows > 0
    return {
        "descriptor_ids": ["plateau_or_saturation_support_measurement"],
        **common,
        "exact_rail_sample_count": rail_samples,
        "near_rail_sample_count": near_rail_samples,
        "identical_high_magnitude_plateau_run_count": identical_plateau_runs,
        "identical_high_magnitude_plateau_sample_count": identical_plateau_samples,
        "maximum_identical_high_magnitude_plateau_frames": maximum_identical_plateau_frames,
        "near_flat_high_magnitude_window_count": near_flat_windows,
        "plateau_or_saturation_support_event_present": support,
        "intentional_waveform_exclusion_derived_from_pcm": False,
        "trait_assignment_made": False,
    }


def build_private_report(
    plan: dict[str, Any], private_root: Path, ffmpeg: Path, ffprobe: Path
) -> dict[str, Any]:
    root = require_private_root(private_root)
    journal = load_json(root / "acquisition.json")
    if journal.get("state") != "two_exact_provider_originals_acquired_and_verified":
        raise ValueError("acquisition is incomplete")
    members = {row["member_id"]: row for row in plan["members"]}
    records = {row["member_id"]: row for row in journal["records"]}
    if set(records) != set(members):
        raise ValueError("acquisition member inventory differs")
    observations = []
    for member_id in ("freesound_sound_426894", "freesound_sound_610933"):
        record = records[member_id]
        member = members[member_id]
        source = verify_record(root, record, member, ffprobe)
        observations.append(
            {
                "member_id": member_id,
                "trait_id": member["trait_id"],
                "encoded_sha256": record["encoded_sha256"],
                "probe": record["probe"],
                "descriptor": measure_member(ffmpeg, source, member, record["probe"], plan),
            }
        )
    return {
        "schema_version": 1,
        "report_id": "perceptual-degradation-source-trait-exact-member-confirmation-private-replay",
        "plan_sha256": sha256_file(PLAN_PATH),
        "implementation_sha256": sha256_file(SCRIPT_PATH),
        "toolchain": validate_toolchain(plan, ffmpeg, ffprobe),
        "observations": observations,
        "access_boundary": {
            "exact_provider_original_count_read": 2,
            "other_source_members_accessed": False,
            "provider_processed_conditions_or_scores_accessed": False,
            "decoded_or_derived_pcm_retained": False,
            "codec_generated": False,
            "perceptual_metric_executed": False,
            "playback_performed": False,
            "listener_response_collected": False,
            "sealed_evidence_opened": False,
            "no_reference_training_performed": False,
            "trait_assignment_made": False,
            "source_manifest_allocation_performed": False,
            "validation_claim_or_public_verdict_issued": False,
        },
    }


def run_replays(plan: dict[str, Any], private_root: Path, ffmpeg: Path, ffprobe: Path) -> dict[str, Any]:
    root = require_private_root(private_root)
    replay_root = root / "private-replays"
    replay_root.mkdir(exist_ok=True, mode=0o700)
    payloads: list[bytes] = []
    for index in (1, 2):
        if shutil.disk_usage(root).free < RESERVE_BYTES:
            raise ValueError("private volume fell below the frozen 15 GiB reserve")
        report = build_private_report(plan, root, ffmpeg, ffprobe)
        payload = canonical_json_bytes(report)
        payloads.append(payload)
        path = replay_root / f"replay-{index}.json"
        atomic_json(path, report)
    if payloads[0] != payloads[1]:
        raise ValueError("private replay reports are not byte-identical")
    summary = {
        "schema_version": 1,
        "state": "two_private_replays_complete_and_byte_identical",
        "private_replay_count": 2,
        "byte_identical": True,
        "payload_sha256": sha256_bytes(payloads[0]),
    }
    atomic_json(replay_root / "replay-summary.json", summary)
    return summary


def public_report(plan: dict[str, Any], private_root: Path) -> dict[str, Any]:
    replay_root = require_private_root(private_root) / "private-replays"
    first = (replay_root / "replay-1.json").read_bytes()
    second = (replay_root / "replay-2.json").read_bytes()
    if first != second:
        raise ValueError("private replay reports are not byte-identical")
    private = json.loads(first)
    observations = {row["trait_id"]: row["descriptor"] for row in private["observations"]}
    quiet = observations["quiet"]
    clipped = observations["clipped"]
    return {
        "schema_version": 1,
        "report_id": "perceptual-degradation-source-trait-exact-member-confirmation-20260818-001",
        "state": "two_provider_originals_acquired_two_score_free_integer_pcm_replays_complete",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(PLAN_PATH),
        "execution": {
            "exact_provider_original_count_acquired": 2,
            "private_replay_count": 2,
            "private_reports_byte_identical": True,
            "maximum_workers": 1,
            "minimum_free_disk_gib_preserved": 15,
            "decoded_or_derived_pcm_retained": False,
        },
        "descriptor_observations": {
            "quiet": quiet,
            "clipped": clipped,
        },
        "decision": {
            "quiet_absolute_pcm_level_measured": True,
            "quiet_nonzero_activity_support_observed": quiet["nonzero_activity_present"],
            "clipped_plateau_or_saturation_support_event_observed": clipped[
                "plateau_or_saturation_support_event_present"
            ],
            "quiet_or_clipped_trait_assigned": False,
            "source_trait_manifest_frozen": False,
            "source_allocation_performed": False,
            "perceptual_or_validation_claim_available": False,
            "public_verdict_enabled": False,
        },
        "claim_boundary": {
            "absolute_level_measurement_is_quiet_trait_truth": False,
            "plateau_or_saturation_event_is_clipping_provenance": False,
            "metadata_plus_descriptor_is_perceptual_truth": False,
            "source_trait_scientific_coverage_complete": False,
            "full_objective_complete": False,
            "public_cli_changed": False,
            "public_verdict_enabled": False,
        },
        "publication_boundary": {
            "private_paths_exposed": False,
            "encoded_or_pcm_hashes_exposed": False,
            "audio_exposed": False,
            "provider_scores_or_processed_conditions_exposed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-plan")
    acquire = sub.add_parser("import-originals")
    acquire.add_argument("--private-root", type=Path, required=True)
    acquire.add_argument("--quiet-input", type=Path, required=True)
    acquire.add_argument("--clipped-input", type=Path, required=True)
    replay = sub.add_parser("run-replays")
    replay.add_argument("--private-root", type=Path, required=True)
    publish = sub.add_parser("write-public-report")
    publish.add_argument("--private-root", type=Path, required=True)
    publish.add_argument("--output", type=Path, required=True)
    for command in (acquire, replay):
        command.add_argument("--ffmpeg", type=Path, default=Path("/opt/homebrew/bin/ffmpeg"))
        command.add_argument("--ffprobe", type=Path, default=Path("/opt/homebrew/bin/ffprobe"))
    args = parser.parse_args()
    plan = load_json(PLAN_PATH)
    errors = validate_plan(plan)
    if errors:
        raise SystemExit("; ".join(errors))
    if args.command == "validate-plan":
        print(f"validated {plan['plan_id']}")
        return 0
    require_committed_freeze(plan)
    if args.command == "import-originals":
        validate_toolchain(plan, args.ffmpeg, args.ffprobe)
        result = import_originals(
            plan,
            args.private_root,
            {
                "freesound_sound_426894": args.quiet_input,
                "freesound_sound_610933": args.clipped_input,
            },
            args.ffprobe,
        )
    elif args.command == "run-replays":
        validate_toolchain(plan, args.ffmpeg, args.ffprobe)
        result = run_replays(plan, args.private_root, args.ffmpeg, args.ffprobe)
    else:
        result = public_report(plan, args.private_root)
        atomic_json(args.output, result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
