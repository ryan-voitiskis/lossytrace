#!/usr/bin/env python3
"""Confirm the frozen sparse non-tonal v3 successor without retaining PCM."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import struct
import tempfile
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-exact-member-confirmation-v3-plan.json"
PUBLIC_REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v3-20260819-001.json"
PLAN_ID = "perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v3-20260819-001"
REPORT_ID = PLAN_ID
PCM_SUBFORMAT_GUID = bytes.fromhex("0100000000001000800000aa00389b71")
EXPECTED_BINDINGS = {
    "confirmation_implementation",
    "confirmation_tests",
    "current_objective_audit",
    "descriptor_implementation",
    "descriptor_plan",
    "descriptor_report",
    "failed_exact_member_v2_audit",
    "failed_exact_member_v2_report",
    "metadata_search_implementation",
    "metadata_search_plan",
    "metadata_search_plan_validator",
    "metadata_search_report",
    "research_contract",
}
TRUE_AUTHORIZATIONS = {
    "actual_audio_access_authorized",
    "exact_selected_provider_original_acquisition_authorized",
    "private_replay_and_redaction_audit_authorized",
    "sparse_tonal_descriptor_execution_authorized",
    "synthetic_fixture_execution_authorized",
}


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
    if plan.get("state") != "one_exact_sparse_non_tonal_successor_v3_confirmation_frozen_before_audio_access":
        errors.append("plan state differs")
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != EXPECTED_BINDINGS:
        errors.append("binding inventory differs")
        bindings = {}
    for binding_id, binding in bindings.items():
        path = Path(str(binding.get("path", "")))
        if path.is_absolute() or ".." in path.parts or not (ROOT / path).is_file():
            errors.append(f"invalid binding: {binding_id}")
        elif sha256_file(ROOT / path) != binding.get("sha256"):
            errors.append(f"binding hash differs: {binding_id}")

    authorization = plan.get("authorization", {})
    if set(authorization) != TRUE_AUTHORIZATIONS | {
        "actual_codec_generation_authorized",
        "derived_pcm_retention_authorized",
        "human_collection_authorized",
        "no_reference_training_authorized",
        "perceptual_metric_execution_authorized",
        "playback_authorized",
        "provider_processed_condition_or_score_access_authorized",
        "public_verdict_enabled",
        "sealed_evidence_access_authorized",
        "source_manifest_allocation_authorized",
        "source_trait_assignment_authorized",
    }:
        errors.append("authorization inventory differs")
    for key, value in authorization.items():
        if value is not (key in TRUE_AUTHORIZATIONS):
            errors.append(f"authorization differs: {key}")
    if plan.get("resources") != {
        "fresh_temporary_directories": True,
        "maximum_workers": 1,
        "minimum_free_disk_gib": 15,
        "replay_count": 2,
        "retain_derived_pcm": False,
    }:
        errors.append("resource boundary differs")

    member = plan.get("member", {})
    if member.get("exact_member_id") != "freesound_sound_476736":
        errors.append("exact member differs")
    if member.get("provider_id") != "freesound" or member.get("licence") != "CC0 1.0":
        errors.append("provider or licence differs")
    if member.get("provider_record_url") != "https://freesound.org/people/elmoustachio/sounds/476736/":
        errors.append("provider record differs")
    if member.get("expected_descriptor_class") != "sparse_non_tonal_contrast":
        errors.append("expected descriptor class differs")
    if member.get("expected_container") != {
        "bits_per_sample": 24,
        "channel_count": 2,
        "duration_seconds_maximum": "26.800000",
        "duration_seconds_minimum": "26.700000",
        "sample_format": "signed_integer_pcm",
        "sample_rate_hz": 48000,
    }:
        errors.append("expected container differs")
    if member.get("maximum_encoded_bytes") != 10485760:
        errors.append("encoded size boundary differs")

    execution = plan.get("execution_contract", {})
    required_true = {
        "all_supported_channels_must_agree",
        "attribution_attachment_required",
        "candidate_detail_page_may_be_opened_only_to_use_official_authenticated_download",
        "exact_provider_original_may_be_retained_privately",
        "private_reports_must_be_byte_identical",
        "public_report_must_exclude_channel_measurements",
        "public_report_must_exclude_encoded_and_pcm_hashes",
        "public_report_must_exclude_private_paths",
        "public_report_must_exclude_provider_scores_and_processed_conditions",
    }
    if execution.get("private_report_count") != 2:
        errors.append("private report count differs")
    for key in required_true:
        if execution.get(key) is not True:
            errors.append(f"execution contract differs: {key}")
    for key in ("descriptor_threshold_change_after_observation_allowed", "member_substitution_after_observation_allowed"):
        if execution.get(key) is not False:
            errors.append(f"execution contract differs: {key}")
    if set(execution) != required_true | {
        "descriptor_threshold_change_after_observation_allowed",
        "member_substitution_after_observation_allowed",
        "private_report_count",
    }:
        errors.append("execution contract inventory differs")
    negative = plan.get("negative_result_policy", {})
    if not negative or any(value is not True for value in negative.values()):
        errors.append("negative-result policy must remain true")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")

    if not errors:
        metadata = load_json(_binding_path(plan, "metadata_search_report"))
        if metadata["decision"]["nominated_exact_member_id"] != member["exact_member_id"]:
            errors.append("metadata nomination differs")
        if metadata["audio_accessed"] is not False:
            errors.append("metadata search unexpectedly accessed audio")
        failed = load_json(_binding_path(plan, "failed_exact_member_v2_report"))
        if failed["decision"]["descriptor_confirmation_passed"] is not False:
            errors.append("predecessor class mismatch differs")
        descriptor_report = load_json(_binding_path(plan, "descriptor_report"))
        if descriptor_report["decision"]["synthetic_fixture_gate_pass_count"] != 3:
            errors.append("bound descriptor synthetic gates differ")
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


def parse_signed_24bit_pcm_wav(value: bytes) -> tuple[dict[str, Any], list[list[int]], bytes]:
    chunks = _chunk_map(value)
    fmt = chunks[b"fmt "]
    if len(fmt) < 16:
        raise ValueError("short WAVE format chunk")
    format_tag, channel_count, sample_rate, byte_rate, block_align, bits = struct.unpack_from("<HHIIHH", fmt)
    if format_tag == 0xFFFE:
        if len(fmt) < 40 or fmt[24:40] != PCM_SUBFORMAT_GUID:
            raise ValueError("unsupported WAVE_FORMAT_EXTENSIBLE subformat")
        valid_bits = struct.unpack_from("<H", fmt, 18)[0]
        if valid_bits != 24:
            raise ValueError("valid bits differ from 24-bit PCM")
    elif format_tag != 1:
        raise ValueError("source is not signed integer PCM")
    if channel_count not in (1, 2) or bits != 24:
        raise ValueError("unsupported signed PCM channel count or bit depth")
    width = 3
    if block_align != channel_count * width or byte_rate != sample_rate * block_align:
        raise ValueError("inconsistent signed PCM format fields")
    pcm = chunks[b"data"]
    if len(pcm) == 0 or len(pcm) % block_align:
        raise ValueError("invalid PCM data byte length")
    channels: list[list[int]] = [[] for _ in range(channel_count)]
    for frame_offset in range(0, len(pcm), block_align):
        for channel in range(channel_count):
            offset = frame_offset + channel * width
            sample = int.from_bytes(pcm[offset : offset + width], "little")
            if sample >= 1 << 23:
                sample -= 1 << 24
            channels[channel].append(sample)
    frame_count = len(pcm) // block_align
    facts = {
        "bits_per_sample": bits,
        "channel_count": channel_count,
        "duration_seconds": f"{frame_count / sample_rate:.9f}",
        "frame_count": frame_count,
        "sample_format": "signed_integer_pcm",
        "sample_rate_hz": sample_rate,
    }
    return facts, channels, pcm


def _measure(descriptor: ModuleType, record: dict[str, Any], encoded: bytes) -> tuple[dict[str, Any], bytes]:
    if len(encoded) > record["maximum_encoded_bytes"]:
        raise ValueError("encoded source exceeds frozen size limit")
    facts, channels, pcm = parse_signed_24bit_pcm_wav(encoded)
    expected = record["expected_container"]
    for key in ("bits_per_sample", "channel_count", "sample_format", "sample_rate_hz"):
        if facts.get(key) != expected.get(key):
            raise ValueError(f"container metadata differs: {key}")
    duration = Decimal(facts["duration_seconds"])
    if not Decimal(expected["duration_seconds_minimum"]) <= duration <= Decimal(expected["duration_seconds_maximum"]):
        raise ValueError("container duration differs")
    observations = [descriptor.classify(samples) for samples in channels]
    expected_class = record["expected_descriptor_class"]
    agreement = all(row.get(expected_class) is True and row.get("abstain") is False for row in observations)
    terminal = "passed" if agreement else ("abstained" if any(row.get("abstain") is True for row in observations) else "class_mismatch")
    return {
        "all_supported_channels_agree": agreement,
        "channel_descriptors": observations,
        "container": facts,
        "descriptor_confirmation_passed": agreement,
        "expected_descriptor_class": expected_class,
        "terminal_outcome": terminal,
    }, pcm


def _private_replay(plan: dict[str, Any], descriptor: ModuleType, provider_original: Path) -> dict[str, Any]:
    record = plan["member"]
    encoded = provider_original.read_bytes()
    measurement, pcm = _measure(descriptor, record, encoded)
    result = {
        "report_id": REPORT_ID + "-private-replay",
        "schema_version": 1,
        "source_observation": {
            "attribution": record["attribution"],
            "encoded_sha256": sha256_bytes(encoded),
            "exact_member_id": record["exact_member_id"],
            "licence": record["licence"],
            "measurement": measurement,
            "pcm_sha256": sha256_bytes(pcm),
            "provider_id": record["provider_id"],
            "provider_record_url": record["provider_record_url"],
        },
    }
    del pcm
    return result


def _public_report(plan: dict[str, Any], private: dict[str, Any], plan_path: Path) -> dict[str, Any]:
    observation = private["source_observation"]
    measurement = observation["measurement"]
    passed = measurement["descriptor_confirmation_passed"]
    return {
        "claim_boundary": plan["claim_boundary"],
        "decision": {
            "candidate_replacement_performed": False,
            "descriptor_confirmation_complete": True,
            "descriptor_confirmation_passed": passed,
            "source_manifest_allocated": False,
            "source_trait_assignment_complete": False,
            "terminal_outcome": measurement["terminal_outcome"],
            "thresholds_changed_after_observation": False,
        },
        "execution": {
            "decoded_or_derived_pcm_retained": False,
            "exact_member_count": 1,
            "maximum_workers": 1,
            "minimum_free_disk_gib_preserved": plan["resources"]["minimum_free_disk_gib"],
            "private_replay_count": 2,
            "private_reports_byte_identical": True,
        },
        "implementation_sha256": sha256_file(Path(__file__)),
        "nominated_exact_member_id": observation["exact_member_id"],
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "publication_boundary": {
            "audio_exposed": False,
            "channel_measurements_exposed": False,
            "encoded_or_pcm_hashes_exposed": False,
            "private_paths_exposed": False,
            "provider_scores_or_processed_conditions_exposed": False,
        },
        "report_id": REPORT_ID,
        "schema_version": 1,
        "state": "one_exact_sparse_non_tonal_successor_v3_score_free_descriptor_replays_complete",
    }


def _validate_public_redaction(report: dict[str, Any]) -> None:
    forbidden_keys = {"channel_descriptors", "container", "encoded_sha256", "pcm_sha256", "private_path"}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in forbidden_keys:
                    raise ValueError(f"public report exposes forbidden key: {key}")
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str) and (value.startswith("/") or value.startswith("file:")):
            raise ValueError("public report exposes a path-like value")

    walk(report)


def run(
    plan: dict[str, Any],
    plan_path: Path,
    provider_original: Path,
    private_output_dir: Path,
    public_output: Path,
) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    if not provider_original.is_file():
        raise ValueError("private provider original is absent")
    reserve = plan["resources"]["minimum_free_disk_gib"] * 1024**3
    volume = private_output_dir.parent if private_output_dir.parent.exists() else ROOT
    if shutil.disk_usage(volume).free < reserve:
        raise ValueError("private volume is below the frozen 15 GiB reserve")
    descriptor = _load_module(_binding_path(plan, "descriptor_implementation"), "sparse_tonal_descriptor_v3")
    payloads: list[bytes] = []
    for _ in range(plan["resources"]["replay_count"]):
        with tempfile.TemporaryDirectory(prefix="lossytrace-sparse-nontonal-confirm-v3-"):
            payloads.append(canonical_json_bytes(_private_replay(plan, descriptor, provider_original)))
    if payloads[0] != payloads[1]:
        raise ValueError("private replay reports are not byte-identical")
    private_output_dir.mkdir(parents=True, exist_ok=True)
    (private_output_dir / "private-replay-a.json").write_bytes(payloads[0])
    (private_output_dir / "private-replay-b.json").write_bytes(payloads[1])
    attribution = {
        "attribution": plan["member"]["attribution"],
        "exact_member_id": plan["member"]["exact_member_id"],
        "licence": plan["member"]["licence"],
        "provider_record_url": plan["member"]["provider_record_url"],
        "schema_version": 1,
    }
    (private_output_dir / "source-attribution.json").write_bytes(canonical_json_bytes(attribution))
    report = _public_report(plan, json.loads(payloads[0]), plan_path)
    _validate_public_redaction(report)
    public_output.parent.mkdir(parents=True, exist_ok=True)
    public_output.write_bytes(canonical_json_bytes(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--check-plan", action="store_true")
    parser.add_argument("--provider-original", type=Path)
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
    if args.provider_original is None or args.private_output_dir is None:
        parser.error("live run requires --provider-original and --private-output-dir")
    report = run(plan, args.plan, args.provider_original, args.private_output_dir, args.public_output)
    print(json.dumps(report["decision"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
