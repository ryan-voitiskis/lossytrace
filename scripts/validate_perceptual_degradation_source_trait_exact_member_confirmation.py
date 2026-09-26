#!/usr/bin/env python3
"""Independently validate the path-free exact-member confirmation result."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1"
    / "source-trait-exact-member-confirmation-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence"
    / "perceptual-degradation-source-trait-exact-member-confirmation-20260818-001.json"
)
REPORT_ID = "perceptual-degradation-source-trait-exact-member-confirmation-20260818-001"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dbfs_power(numerator: int, denominator: int) -> str | None:
    if numerator == 0:
        return None
    return f"{10.0 * math.log10(numerator / denominator):.6f}"


def _dbfs_peak(peak: int, full_scale: int) -> str | None:
    if peak == 0:
        return None
    return f"{20.0 * math.log10(peak / full_scale):.6f}"


def _validate_common(
    descriptor: dict[str, Any], expected_channels: int, errors: list[str], label: str
) -> None:
    frame_count = descriptor.get("frame_count")
    sample_count = descriptor.get("sample_count")
    full_scale = descriptor.get("full_scale_magnitude")
    channels = descriptor.get("channels", [])
    if not isinstance(frame_count, int) or frame_count <= 0:
        errors.append(f"{label} frame count differs")
        return
    if sample_count != frame_count * expected_channels:
        errors.append(f"{label} sample geometry differs")
    if full_scale != 1 << 23:
        errors.append(f"{label} full scale differs")
    if not isinstance(channels, list) or len(channels) != expected_channels:
        errors.append(f"{label} channel inventory differs")
        return
    if any(row.get("sample_count") != frame_count for row in channels):
        errors.append(f"{label} channel sample count differs")
    sum_squares = sum(row.get("sum_squares", -1) for row in channels)
    peak = max(row.get("peak_abs_code", -1) for row in channels)
    if descriptor.get("sum_squares") != sum_squares:
        errors.append(f"{label} sum of squares differs")
    if descriptor.get("peak_abs_code") != peak:
        errors.append(f"{label} peak differs")
    if descriptor.get("rms_dbfs") != _dbfs_power(
        sum_squares, sample_count * full_scale * full_scale
    ):
        errors.append(f"{label} RMS display differs")
    if descriptor.get("peak_dbfs") != _dbfs_peak(peak, full_scale):
        errors.append(f"{label} peak display differs")
    for index, row in enumerate(channels):
        if row.get("rms_dbfs") != _dbfs_power(
            row["sum_squares"], row["sample_count"] * full_scale * full_scale
        ):
            errors.append(f"{label} channel {index} RMS display differs")
        if row.get("peak_dbfs") != _dbfs_peak(row["peak_abs_code"], full_scale):
            errors.append(f"{label} channel {index} peak display differs")


def validate_report(
    report: dict[str, Any], plan: dict[str, Any] | None = None
) -> list[str]:
    errors: list[str] = []
    plan = plan or load_json(PLAN_PATH)
    if report.get("schema_version") != 1 or report.get("report_id") != REPORT_ID:
        errors.append("report identity differs")
    if report.get("plan_id") != plan.get("plan_id"):
        errors.append("report plan identity differs")
    if report.get("plan_sha256") != sha256_file(PLAN_PATH):
        errors.append("report plan SHA-256 differs")
    if report.get("state") != (
        "two_provider_originals_acquired_two_score_free_integer_pcm_replays_complete"
    ):
        errors.append("report state differs")
    if report.get("execution") != {
        "decoded_or_derived_pcm_retained": False,
        "exact_provider_original_count_acquired": 2,
        "maximum_workers": 1,
        "minimum_free_disk_gib_preserved": 15,
        "private_replay_count": 2,
        "private_reports_byte_identical": True,
    }:
        errors.append("execution boundary differs")
    observations = report.get("descriptor_observations", {})
    quiet = observations.get("quiet", {})
    clipped = observations.get("clipped", {})
    _validate_common(quiet, 2, errors, "quiet")
    _validate_common(clipped, 1, errors, "clipped")
    if quiet.get("descriptor_ids") != [
        "absolute_pcm_level_measurement",
        "nonzero_activity_support",
    ]:
        errors.append("quiet descriptor inventory differs")
    if quiet.get("quiet_classification_threshold_applied") is not False:
        errors.append("quiet classification threshold must remain unapplied")
    if quiet.get("nonzero_activity_present") != (
        isinstance(quiet.get("nonzero_frame_count"), int)
        and quiet["nonzero_frame_count"] > 0
    ):
        errors.append("quiet nonzero support predicate differs")
    if quiet.get("nonzero_sample_count") != sum(
        row.get("nonzero_sample_count", -1) for row in quiet.get("channels", [])
    ):
        errors.append("quiet nonzero sample total differs")
    if quiet.get("active_one_second_block_count", -1) > quiet.get(
        "one_second_block_count", -2
    ):
        errors.append("quiet active block count differs")
    if clipped.get("descriptor_ids") != [
        "plateau_or_saturation_support_measurement"
    ]:
        errors.append("clipped descriptor inventory differs")
    support = any(
        clipped.get(key, 0) > 0
        for key in (
            "exact_rail_sample_count",
            "identical_high_magnitude_plateau_run_count",
            "near_flat_high_magnitude_window_count",
        )
    )
    if clipped.get("plateau_or_saturation_support_event_present") != support:
        errors.append("clipped support predicate differs")
    if clipped.get("intentional_waveform_exclusion_derived_from_pcm") is not False:
        errors.append("clipped provenance boundary differs")
    if clipped.get("trait_assignment_made") is not False:
        errors.append("clipped trait assignment must remain false")
    decision = report.get("decision", {})
    if decision.get("quiet_absolute_pcm_level_measured") is not True:
        errors.append("quiet measurement decision differs")
    if decision.get("quiet_nonzero_activity_support_observed") != quiet.get(
        "nonzero_activity_present"
    ):
        errors.append("quiet decision differs")
    if decision.get("clipped_plateau_or_saturation_support_event_observed") != support:
        errors.append("clipped decision differs")
    for key in (
        "quiet_or_clipped_trait_assigned",
        "source_allocation_performed",
        "source_trait_manifest_frozen",
        "perceptual_or_validation_claim_available",
        "public_verdict_enabled",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision must remain false: {key}")
    if report.get("publication_boundary") != {
        "audio_exposed": False,
        "encoded_or_pcm_hashes_exposed": False,
        "private_paths_exposed": False,
        "provider_scores_or_processed_conditions_exposed": False,
    }:
        errors.append("publication boundary differs")
    claims = report.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    serialized = json.dumps(report, sort_keys=True)
    for forbidden in (
        "/Users/",
        "Application Support",
        "provider-originals",
        "encoded_sha256",
        "pcm_sha256",
        "relative_path",
    ):
        if forbidden in serialized:
            errors.append(f"public report exposes forbidden material: {forbidden}")
    return sorted(set(errors))


def audit_private_projection(private_root: Path) -> dict[str, Any]:
    if private_root.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("private replay root must remain outside the repository")
    replay_root = private_root.resolve() / "private-replays"
    first_bytes = (replay_root / "replay-1.json").read_bytes()
    second_bytes = (replay_root / "replay-2.json").read_bytes()
    if first_bytes != second_bytes:
        raise ValueError("private replay payloads differ")
    private = json.loads(first_bytes)
    public = load_json(REPORT_PATH)
    errors = validate_report(public)
    if private.get("plan_sha256") != public.get("plan_sha256"):
        errors.append("private/public plan binding differs")
    expected_runner = load_json(PLAN_PATH)["bindings"]["runner"]["sha256"]
    if private.get("implementation_sha256") != expected_runner:
        errors.append("private runner provenance differs")
    projected = {
        row["trait_id"]: row["descriptor"] for row in private.get("observations", [])
    }
    if projected != public.get("descriptor_observations"):
        errors.append("private/public descriptor projection differs")
    access = private.get("access_boundary", {})
    if access.get("exact_provider_original_count_read") != 2 or any(
        access.get(key) is not False
        for key in (
            "other_source_members_accessed",
            "provider_processed_conditions_or_scores_accessed",
            "decoded_or_derived_pcm_retained",
            "codec_generated",
            "perceptual_metric_executed",
            "playback_performed",
            "listener_response_collected",
            "sealed_evidence_opened",
            "no_reference_training_performed",
            "trait_assignment_made",
            "source_manifest_allocation_performed",
            "validation_claim_or_public_verdict_issued",
        )
    ):
        errors.append("private access boundary differs")
    return {
        "private_replays_byte_identical": first_bytes == second_bytes,
        "private_public_descriptor_projection_exact": projected
        == public.get("descriptor_observations"),
        "public_report_validation_errors": sorted(set(errors)),
        "public_report_path_free_and_hash_redacted": not any(
            marker in json.dumps(public, sort_keys=True)
            for marker in (
                "/Users/",
                "Application Support",
                "provider-originals",
                "encoded_sha256",
                "pcm_sha256",
                "relative_path",
            )
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", type=Path)
    args = parser.parse_args()
    errors = validate_report(load_json(REPORT_PATH))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if args.private_root:
        audit = audit_private_projection(args.private_root)
        if audit["public_report_validation_errors"]:
            for error in audit["public_report_validation_errors"]:
                print(f"ERROR: {error}")
            return 1
        print(json.dumps(audit, sort_keys=True))
    else:
        print(f"validated {REPORT_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
