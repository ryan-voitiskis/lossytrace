#!/usr/bin/env python3
"""Validate the path-free ODAQ clean-reference acquisition result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "benchmarks/perceptual-degradation-v1/odaq-reference-acquisition-result-20260813.json"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if result.get("schema_version") != 1:
        errors.append("schema version differs")
    if result.get("result_id") != "perceptual-degradation-odaq-reference-acquisition-result-20260813-001":
        errors.append("result identity differs")
    if result.get("state") != "exact_clean_reference_acquisition_complete_processed_and_scores_unopened":
        errors.append("result state differs")
    if result.get("observed_on") != "2026-08-13":
        errors.append("result date differs")

    bindings = result.get("bindings", {})
    if set(bindings) != {"reference_metadata_freeze", "acquisition_authorization", "bounded_extractor"}:
        errors.append("result binding set differs")
    for binding_id, binding in bindings.items():
        relative = Path(str(binding.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"invalid repository-relative binding: {binding_id}")
            continue
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")

    execution = result.get("execution", {})
    if execution != {
        "exact_head_commit": "d94947177ffe2aad9744133d052b256181c1267e",
        "exact_head_ci_url": "https://github.com/ryan-voitiskis/lossytrace/actions/runs/31686727214",
        "exact_head_ci_passed": True,
        "acquisition_identity_sha256": "a328198da9bf4e2c6061db69c4fd961884360074a90b432f53b0ebf739cbf5d3",
        "maximum_sustained_workers": 1,
        "minimum_free_disk_gib_preserved": 15,
        "provider_archive_payload_downloaded": False,
    }:
        errors.append("execution evidence differs")

    inventory = result.get("retained_inventory", {})
    if inventory != {
        "reference_count": 16,
        "retained_audio_bytes": 54_633_154,
        "completed_inventory_sha256": "d7f244da55b510b639300d55271b1ebd5fb9f7454b258bec30588bf18eefde2f",
        "sample_rate_hz": 48_000,
        "channel_count": 2,
        "minimum_frame_count": 360_701,
        "maximum_frame_count": 576_008,
        "geometry_distribution": [
            {"container_encoding": "riff_wave", "sample_encoding": "ieee_float_pcm", "bit_depth": 32, "reference_count": 7},
            {"container_encoding": "wave_format_extensible", "sample_encoding": "signed_integer_pcm", "bit_depth": 24, "reference_count": 9},
        ],
        "partial_file_count": 0,
        "per_member_hashes_published": False,
        "retained_paths_published": False,
    }:
        errors.append("retained inventory evidence differs")

    range_access = result.get("successful_resume_range_access", {})
    if range_access != {
        "request_count": 372,
        "response_bytes": 24_268_401,
        "maximum_response_bytes": 58_720_256,
        "block_bytes": 65_536,
        "cache_blocks": 16,
        "accept_ranges_verified": True,
        "archive_payload_downloaded": False,
        "scope": "successful_resume_only_not_all_stopped_attempts",
    }:
        errors.append("successful-resume Range evidence differs")
    elif range_access["response_bytes"] > range_access["maximum_response_bytes"]:
        errors.append("successful-resume Range limit exceeded")

    audit = result.get("independent_integrity_audit", {})
    for key in ("byte_length_verified", "sha256_verified", "crc32_verified", "authorization_membership_verified", "inventory_sha256_verified", "ffprobe_geometry_verified"):
        if audit.get(key) is not True:
            errors.append(f"independent audit guarantee differs: {key}")
    if audit.get("reference_count_verified") != 16:
        errors.append("independent audit reference count differs")
    if audit.get("unexpected_retained_file_count") != 0:
        errors.append("unexpected retained files were observed")
    if audit.get("partial_file_count") != 0:
        errors.append("partial files remain")

    access = result.get("access_boundary", {})
    if access.get("clean_reference_members_opened") is not True:
        errors.append("clean reference access result differs")
    for key in ("processed_condition_opened", "listening_score_opened", "metric_score_opened", "stimulus_generated", "perceptual_metric_executed", "listener_response_collected", "sealed_evidence_opened"):
        if access.get(key) is not False:
            errors.append(f"access boundary must remain false: {key}")

    claim = result.get("claim_boundary", {})
    if claim.get("development_only") is not True:
        errors.append("development-only boundary differs")
    if claim.get("one_provider_stratum") is not True:
        errors.append("one-provider boundary differs")
    for key in ("independent_transfer_supported", "final_validation_supported", "provider_references_are_actual_codec_conditions", "physical_playback_qualified", "browser_delivery_ready_without_conversion", "float_to_integer_conversion_authorized", "stimulus_generation_authorized", "human_collection_authorized"):
        if claim.get(key) is not False:
            errors.append(f"claim boundary must remain false: {key}")

    serialized = json.dumps(result, sort_keys=True)
    if "/Users/" in serialized or "Application Support" in serialized:
        errors.append("result must not contain a private absolute path")
    if result.get("paths_redacted") is not True:
        errors.append("result paths must be redacted")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=RESULT)
    args = parser.parse_args()
    errors = validate(load_json(args.result))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(json.dumps({
        "result": str(args.result.relative_to(ROOT)),
        "result_sha256": sha256_file(args.result),
        "reference_count": 16,
        "retained_audio_bytes": 54_633_154,
        "status": "path_free_reference_acquisition_complete",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
