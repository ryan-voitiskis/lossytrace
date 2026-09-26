#!/usr/bin/env python3
"""Validate the path-free ODAQ private delivery completion checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULT = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "odaq-reference-delivery-result-20260814.json"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_result(result: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if result.get("schema_version") != 1 or result.get("result_id") != (
        "perceptual-degradation-odaq-reference-delivery-result-20260814-001"
    ):
        errors.append("result identity differs")
    if result.get("state") != "private_canonical_integer_pcm_delivery_complete_two_replays_verified":
        errors.append("result state differs")

    bindings = result.get("bindings", {})
    expected_bindings = {
        "authorization",
        "execution_plan",
        "projection_implementation",
        "private_runner",
        "private_runner_tests",
        "attribution_audit",
        "playback_qualification",
    }
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        errors.append("result binding inventory differs")
    elif isinstance(bindings, dict):
        for binding_id, binding in bindings.items():
            relative = Path(str(binding.get("path", "")))
            if not relative.parts or relative.is_absolute() or ".." in relative.parts:
                errors.append(f"invalid result binding: {binding_id}")
                continue
            path = root / relative
            if not path.is_file():
                errors.append(f"missing result binding: {binding_id}")
            elif sha256_file(path) != binding.get("sha256"):
                errors.append(f"result binding hash differs: {binding_id}")

    if result.get("execution") != {
        "exact_head_commit": "3357ac726a20e0e21150e14e48f92a6267a189f0",
        "exact_head_ci_url": "https://github.com/ryan-voitiskis/lossytrace/actions/runs/31764324379",
        "exact_head_ci_passed": True,
        "local_test_count": 868,
        "local_test_skip_count": 12,
        "maximum_workers": 1,
        "minimum_free_disk_gib_preserved": 15,
        "free_disk_kib_after_execution": 82_809_120,
        "private_output_roots": 2,
        "private_outputs_retained": True,
        "private_paths_published": False,
        "per_reference_hashes_published": False,
    }:
        errors.append("execution observation differs")
    if result.get("input_inventory") != {
        "reference_count": 16,
        "retained_audio_bytes": 54_633_154,
        "inventory_sha256": "d7f244da55b510b639300d55271b1ebd5fb9f7454b258bec30588bf18eefde2f",
        "sample_rate_hz": 48_000,
        "channel_count": 2,
        "float32_reference_count": 7,
        "extensible_s24_reference_count": 9,
        "source_inventory_reverified_before_projection": True,
        "unexpected_source_file_count": 0,
        "source_partial_file_count": 0,
    }:
        errors.append("input inventory observation differs")
    if result.get("delivery_inventory") != {
        "reference_count_per_replay": 16,
        "output_audio_bytes_per_replay": 54_631_346,
        "output_inventory_sha256": "66e20ac42ae618eb54a09fa91423f339fdca84be3aa3d7a779b220b57faf2abe",
        "replay_trees_byte_identical": True,
        "replay_inventories_byte_identical": True,
        "sample_rate_hz": 48_000,
        "channel_count": 2,
        "minimum_frame_count": 360_701,
        "maximum_frame_count": 576_008,
        "signed_integer_24_bit_reference_count": 9,
        "signed_integer_32_bit_reference_count": 7,
        "float32_to_signed_int32_reference_count": 7,
        "container_only_canonicalization_reference_count": 9,
        "ffprobe_verified_file_count": 32,
        "unexpected_output_file_count": 0,
        "output_partial_file_count": 0,
    }:
        errors.append("delivery inventory observation differs")
    if result.get("attribution") != {
        "attachment_sha256": "9bf06ed7f7acc8979a5d58fca4f78e6dca31379da25d844b9f46da94eb0295a2",
        "attachments_byte_identical": True,
        "mapping_count_per_replay": 16,
        "attached_licence_record_count_per_replay": 30,
        "attached_out_of_band": True,
        "audio_metadata_rewritten": False,
    }:
        errors.append("attribution observation differs")
    if result.get("access_boundary") != {
        "retained_clean_reference_audio_read": True,
        "retained_clean_reference_audio_projected": True,
        "odaq_processed_condition_opened": False,
        "odaq_listening_score_opened": False,
        "perceptual_metric_executed": False,
        "degradation_rating_collected": False,
        "listener_response_collected": False,
        "sealed_evidence_opened": False,
        "public_verdict_emitted": False,
    }:
        errors.append("access boundary differs")
    if result.get("claim_boundary") != {
        "development_only": True,
        "one_provider_stratum": True,
        "delivery_projection_is_stimulus_generation": False,
        "delivery_projection_is_perceptual_truth": False,
        "delivery_projection_is_metric_evidence": False,
        "delivery_projection_is_listening_evidence": False,
        "independent_transfer_supported": False,
        "full_reference_oracle_validated": False,
        "final_validation_supported": False,
    }:
        errors.append("claim boundary differs")
    expected_next = (
        "A separately committed responsible-human authorization is still required before the frozen "
        "retained-drift validation protocol may read these delivery copies, apply controlled drift "
        "corrections, execute its live runner, or claim real-content full-reference validation."
    )
    if result.get("next_gate") != expected_next:
        errors.append("next gate differs")
    serialized = json.dumps(result, sort_keys=True)
    if "/Users/" in serialized or "Application Support" in serialized:
        errors.append("result exposes a private path")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=RESULT)
    args = parser.parse_args()
    result = load_json(args.result)
    errors = validate_result(result)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        json.dumps(
            {
                "status": "private_odaq_delivery_result_valid",
                "reference_count": result["delivery_inventory"]["reference_count_per_replay"],
                "replays_byte_identical": result["delivery_inventory"]["replay_trees_byte_identical"],
                "paths_redacted": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
