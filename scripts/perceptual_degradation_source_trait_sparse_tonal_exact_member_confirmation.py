#!/usr/bin/env python3
"""Confirm the two frozen sparse/tonal candidates without retaining decoded PCM."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import struct
import tarfile
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-tonal-exact-member-confirmation-plan.json"
PUBLIC_REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-source-trait-sparse-tonal-exact-member-confirmation-20260818-001.json"
PLAN_ID = "perceptual-degradation-source-trait-sparse-tonal-exact-member-confirmation-20260818-001"
REPORT_ID = PLAN_ID
TINYSOL_ARCHIVE_SHA256 = "a537e5de4f64edf0a56032369f66fc76adcb67db875e466f54cad2999e00364c"
PCM_SUBFORMAT_GUID = bytes.fromhex("0100000000001000800000aa00389b71")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load bound implementation: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _binding_path(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != "two_exact_member_descriptor_confirmation_frozen_before_audio_access":
        errors.append("plan state differs")
    expected_bindings = {
        "descriptor_implementation",
        "descriptor_plan",
        "descriptor_report",
        "selection_plan",
        "selection_report",
        "tinysol_public_observation",
    }
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        errors.append("binding inventory differs")
        bindings = {}
    for binding_id, binding in bindings.items():
        path = Path(str(binding.get("path", "")))
        if path.is_absolute() or ".." in path.parts or not (ROOT / path).is_file():
            errors.append(f"invalid binding: {binding_id}")
        elif sha256_file(ROOT / path) != binding.get("sha256"):
            errors.append(f"binding hash differs: {binding_id}")
    authorization = plan.get("authorization", {})
    allowed = {
        "actual_audio_access_authorized",
        "exact_selected_freesound_original_acquisition_authorized",
        "exact_selected_tinysol_member_memory_projection_authorized",
        "sparse_tonal_descriptor_execution_authorized",
    }
    for key, value in authorization.items():
        if value is not (key in allowed):
            errors.append(f"authorization differs: {key}")
    resources = plan.get("resources")
    if resources != {
        "fresh_temporary_directories": True,
        "maximum_workers": 1,
        "minimum_free_disk_gib": 15,
        "replay_count": 2,
        "retain_derived_pcm": False,
    }:
        errors.append("resource boundary differs")
    members = plan.get("members", [])
    if [row.get("exact_member_id") for row in members] != [
        "freesound_sound_856645",
        "tinysol_6_0__ob_ord_dsharp4_mf_n_n",
    ]:
        errors.append("exact member inventory differs")
    if len(members) == 2:
        if members[0].get("expected_descriptor_class") != "sparse_non_tonal_contrast":
            errors.append("Freesound expected class differs")
        if members[1].get("expected_descriptor_class") != "tonal_non_sparse_contrast":
            errors.append("TinySOL expected class differs")
        if members[1].get("selected_archive_member") != "Winds/Oboe/ordinario/Ob-ord-D#4-mf-N-N.wav":
            errors.append("TinySOL member path differs")
    execution = plan.get("execution_contract", {})
    if execution != {
        "all_supported_channels_must_agree": True,
        "attribution_attachment_required": True,
        "descriptor_threshold_change_after_observation_allowed": False,
        "freesound_original_may_be_retained_privately": True,
        "member_substitution_after_observation_allowed": False,
        "private_report_count": 2,
        "private_reports_must_be_byte_identical": True,
        "public_report_must_exclude_encoded_and_pcm_hashes": True,
        "public_report_must_exclude_private_paths": True,
        "public_report_must_exclude_provider_scores_and_processed_conditions": True,
        "tinysol_member_may_be_extracted_to_disk": False,
    }:
        errors.append("execution contract differs")
    negative = plan.get("negative_result_policy", {})
    if not negative or any(value is not True for value in negative.values()):
        errors.append("negative-result policy must remain true")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def _chunk_map(value: bytes) -> dict[bytes, bytes]:
    if len(value) < 12 or value[:4] != b"RIFF" or value[8:12] != b"WAVE":
        raise ValueError("source is not little-endian RIFF/WAVE")
    if struct.unpack_from("<I", value, 4)[0] != len(value) - 8:
        raise ValueError("RIFF byte length differs")
    chunks: dict[bytes, bytes] = {}
    offset = 12
    while offset < len(value):
        if offset + 8 > len(value):
            raise ValueError("truncated RIFF chunk header")
        chunk_id = value[offset : offset + 4]
        size = struct.unpack_from("<I", value, offset + 4)[0]
        start = offset + 8
        end = start + size
        if end > len(value):
            raise ValueError("truncated RIFF chunk")
        if chunk_id in {b"fmt ", b"data"}:
            if chunk_id in chunks:
                raise ValueError(f"duplicate required RIFF chunk: {chunk_id!r}")
            chunks[chunk_id] = value[start:end]
        offset = end + (size & 1)
    if offset != len(value) or set(chunks) != {b"fmt ", b"data"}:
        raise ValueError("invalid RIFF padding or required chunk inventory")
    return chunks


def parse_integer_pcm_wav(value: bytes) -> tuple[dict[str, Any], list[list[int]], bytes]:
    chunks = _chunk_map(value)
    fmt = chunks[b"fmt "]
    if len(fmt) < 16:
        raise ValueError("short WAVE format chunk")
    format_tag, channel_count, sample_rate, byte_rate, block_align, bits = struct.unpack_from("<HHIIHH", fmt)
    if format_tag == 0xFFFE:
        if len(fmt) < 40 or fmt[24:40] != PCM_SUBFORMAT_GUID:
            raise ValueError("unsupported WAVE_FORMAT_EXTENSIBLE subformat")
        valid_bits = struct.unpack_from("<H", fmt, 18)[0]
        if valid_bits != bits:
            raise ValueError("valid bits differ from container bits")
    elif format_tag != 1:
        raise ValueError("source is not signed integer PCM")
    if channel_count not in (1, 2) or bits not in (16, 24):
        raise ValueError("unsupported PCM channel count or bit depth")
    width = bits // 8
    if block_align != channel_count * width or byte_rate != sample_rate * block_align:
        raise ValueError("inconsistent PCM format fields")
    pcm = chunks[b"data"]
    if len(pcm) == 0 or len(pcm) % block_align:
        raise ValueError("invalid PCM data byte length")
    channels = [[] for _ in range(channel_count)]
    for frame_offset in range(0, len(pcm), block_align):
        for channel in range(channel_count):
            offset = frame_offset + channel * width
            if width == 2:
                sample = int.from_bytes(pcm[offset : offset + width], "little", signed=True)
            else:
                sample = int.from_bytes(pcm[offset : offset + width], "little")
                if sample >= 1 << 23:
                    sample -= 1 << 24
            channels[channel].append(sample)
    facts = {
        "bits_per_sample": bits,
        "channel_count": channel_count,
        "frame_count": len(pcm) // block_align,
        "sample_format": "signed_integer_pcm",
        "sample_rate_hz": sample_rate,
    }
    return facts, channels, pcm


def _read_tinysol_member(archive_path: Path, member_path: str, maximum_bytes: int) -> bytes:
    names = [member_path, "./" + member_path]
    with tarfile.open(archive_path, mode="r:gz") as archive:
        info = next((archive.getmember(name) for name in names if name in archive.getnames()), None)
        if info is None or not info.isfile() or info.size > maximum_bytes:
            raise ValueError("selected TinySOL member is absent or exceeds its frozen size limit")
        source = archive.extractfile(info)
        if source is None:
            raise ValueError("selected TinySOL member cannot be opened")
        value = source.read(maximum_bytes + 1)
    if len(value) != info.size or len(value) > maximum_bytes:
        raise ValueError("selected TinySOL member byte length differs")
    return value


def _measure(
    descriptor: ModuleType,
    record: dict[str, Any],
    encoded: bytes,
) -> tuple[dict[str, Any], bytes]:
    if len(encoded) > record["maximum_encoded_bytes"]:
        raise ValueError(f"{record['exact_member_id']}: encoded source exceeds frozen size limit")
    facts, channels, pcm = parse_integer_pcm_wav(encoded)
    expected = record["expected_container"]
    if any(facts.get(key) != value for key, value in expected.items()):
        raise ValueError(f"{record['exact_member_id']}: container metadata differs")
    observations = [descriptor.classify(samples) for samples in channels]
    expected_class = record["expected_descriptor_class"]
    agreement = all(row.get(expected_class) is True and row.get("abstain") is False for row in observations)
    return {
        "channel_descriptors": observations,
        "container": facts,
        "descriptor_confirmation_passed": agreement,
        "expected_descriptor_class": expected_class,
        "all_supported_channels_agree": agreement,
    }, pcm


def _private_replay(
    plan: dict[str, Any],
    descriptor: ModuleType,
    freesound_original: Path,
    tinysol_archive: Path,
) -> dict[str, Any]:
    freesound_record, tinysol_record = plan["members"]
    freesound_encoded = freesound_original.read_bytes()
    tinysol_encoded = _read_tinysol_member(
        tinysol_archive,
        tinysol_record["selected_archive_member"],
        tinysol_record["maximum_encoded_bytes"],
    )
    rows = []
    for record, encoded in ((freesound_record, freesound_encoded), (tinysol_record, tinysol_encoded)):
        measurement, pcm = _measure(descriptor, record, encoded)
        rows.append(
            {
                "attribution": record["attribution"],
                "encoded_sha256": sha256_bytes(encoded),
                "exact_member_id": record["exact_member_id"],
                "licence": record["licence"],
                "measurement": measurement,
                "pcm_sha256": sha256_bytes(pcm),
                "provider_id": record["provider_id"],
            }
        )
        del pcm
    return {
        "report_id": REPORT_ID + "-private-replay",
        "schema_version": 1,
        "source_observations": rows,
    }


def _public_report(plan: dict[str, Any], private: dict[str, Any], plan_path: Path) -> dict[str, Any]:
    rows = []
    for source in private["source_observations"]:
        rows.append(
            {
                "descriptor_confirmation_passed": source["measurement"]["descriptor_confirmation_passed"],
                "exact_member_id": source["exact_member_id"],
                "expected_descriptor_class": source["measurement"]["expected_descriptor_class"],
                "licence": source["licence"],
                "measurement": {
                    "all_supported_channels_agree": source["measurement"]["all_supported_channels_agree"],
                    "channel_descriptors": source["measurement"]["channel_descriptors"],
                    "container": source["measurement"]["container"],
                },
                "provider_id": source["provider_id"],
                "source_trait_assigned": False,
            }
        )
    passed = all(row["descriptor_confirmation_passed"] for row in rows)
    return {
        "claim_boundary": plan["claim_boundary"],
        "decision": {
            "all_exact_member_descriptor_confirmations_passed": passed,
            "candidate_replacement_performed": False,
            "descriptor_confirmation_complete": True,
            "source_manifest_allocated": False,
            "source_trait_assignment_complete": False,
            "thresholds_changed_after_observation": False,
        },
        "execution": {
            "decoded_or_derived_pcm_retained": False,
            "exact_member_count": 2,
            "maximum_workers": 1,
            "minimum_free_disk_gib_preserved": plan["resources"]["minimum_free_disk_gib"],
            "private_replay_count": 2,
            "private_reports_byte_identical": True,
        },
        "implementation_sha256": sha256_file(Path(__file__)),
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "publication_boundary": {
            "audio_exposed": False,
            "encoded_or_pcm_hashes_exposed": False,
            "private_paths_exposed": False,
            "provider_scores_or_processed_conditions_exposed": False,
        },
        "report_id": REPORT_ID,
        "schema_version": 1,
        "source_observations": rows,
        "state": "two_exact_member_score_free_descriptor_replays_complete",
    }


def run(
    plan: dict[str, Any],
    plan_path: Path,
    freesound_original: Path,
    tinysol_archive: Path,
    private_output_dir: Path,
    public_output: Path,
) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    reserve = plan["resources"]["minimum_free_disk_gib"] * 1024**3
    for path in (freesound_original, tinysol_archive):
        if not path.is_file():
            raise ValueError(f"private input is absent: {path.name}")
    if shutil.disk_usage(private_output_dir.parent if private_output_dir.parent.exists() else ROOT).free < reserve:
        raise ValueError("private volume is below the frozen 15 GiB reserve")
    if sha256_file(tinysol_archive) != TINYSOL_ARCHIVE_SHA256:
        raise ValueError("retained TinySOL archive identity differs")
    descriptor = _load_module(_binding_path(plan, "descriptor_implementation"), "sparse_tonal_descriptor")
    payloads: list[bytes] = []
    for _ in range(plan["resources"]["replay_count"]):
        with tempfile.TemporaryDirectory(prefix="lossytrace-sparse-tonal-confirm-"):
            payloads.append(canonical_json_bytes(_private_replay(plan, descriptor, freesound_original, tinysol_archive)))
    if payloads[0] != payloads[1]:
        raise ValueError("private replay reports are not byte-identical")
    private_output_dir.mkdir(parents=True, exist_ok=True)
    (private_output_dir / "private-replay-a.json").write_bytes(payloads[0])
    (private_output_dir / "private-replay-b.json").write_bytes(payloads[1])
    attribution = {
        "schema_version": 1,
        "sources": [
            {
                "attribution": row["attribution"],
                "exact_member_id": row["exact_member_id"],
                "licence": row["licence"],
                "provider_record_url": row["provider_record_url"],
            }
            for row in plan["members"]
        ],
    }
    (private_output_dir / "source-attribution.json").write_bytes(canonical_json_bytes(attribution))
    private = json.loads(payloads[0])
    report = _public_report(plan, private, plan_path)
    public_output.parent.mkdir(parents=True, exist_ok=True)
    public_output.write_bytes(canonical_json_bytes(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--check-plan", action="store_true")
    parser.add_argument("--freesound-original", type=Path)
    parser.add_argument("--tinysol-archive", type=Path)
    parser.add_argument("--private-output-dir", type=Path)
    parser.add_argument("--public-output", type=Path, default=PUBLIC_REPORT_PATH)
    args = parser.parse_args()
    plan = load_json(args.plan)
    errors = validate_plan(plan)
    if args.check_plan:
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"validated {PLAN_ID}")
        return 0
    required = (args.freesound_original, args.tinysol_archive, args.private_output_dir)
    if any(value is None for value in required):
        parser.error("live run requires --freesound-original, --tinysol-archive and --private-output-dir")
    report = run(plan, args.plan, args.freesound_original, args.tinysol_archive, args.private_output_dir, args.public_output)
    print(json.dumps(report["decision"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
