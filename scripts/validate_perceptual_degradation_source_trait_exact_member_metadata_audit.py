#!/usr/bin/env python3
"""Validate the bounded source-trait exact-member metadata audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1"
    / "source-trait-exact-member-metadata-audit-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence"
    / "perceptual-degradation-source-trait-exact-member-metadata-audit-20260817-001.json"
)
AUDIT_ID = "perceptual-degradation-source-trait-exact-member-metadata-audit-20260817-001"

EXPECTED_BINDINGS = {
    "research_contract",
    "source_trait_plan",
    "source_trait_report",
    "provider_capability_screen",
    "sonyc_source_identity_audit",
    "sonyc_path_free_observation",
}

EXPECTED_AUTHORIZATION = {
    "public_and_provider_metadata_read_authorized": True,
    "licensing_and_attribution_metadata_read_authorized": True,
    "provenance_and_transformation_metadata_read_authorized": True,
    "relationship_metadata_read_authorized": True,
    "technical_container_metadata_read_authorized": True,
    "exact_member_metadata_inspection_authorized": True,
    "audio_sample_access_authorized": False,
    "audio_descriptor_computation_authorized": False,
    "provider_score_or_processed_condition_access_authorized": False,
    "codec_generation_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "playback_authorized": False,
    "human_collection_authorized": False,
    "sealed_evidence_access_authorized": False,
    "no_reference_training_authorized": False,
    "frozen_retained_drift_result_mutation_authorized": False,
    "validation_claim_or_public_verdict_authorized": False,
}

EXPECTED_CLOSED_ACCESS = {
    "audio_samples_read",
    "audio_descriptors_computed_or_read",
    "audio_downloaded",
    "provider_scores_or_processed_conditions_accessed",
    "codec_generated",
    "perceptual_metric_executed",
    "playback_performed",
    "listener_response_collected",
    "sealed_evidence_opened",
    "no_reference_training_performed",
    "frozen_retained_drift_result_altered",
    "public_verdict_enabled",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != AUDIT_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "bounded_metadata_only_exact_member_audit_authorized_before_audio_access"
    ):
        errors.append("plan state differs")
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != EXPECTED_BINDINGS:
        errors.append("binding inventory differs")
        bindings = {}
    for binding_id, binding in bindings.items():
        relative = Path(str(binding.get("path", "")))
        path = root / relative
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            errors.append(f"invalid binding: {binding_id}")
        elif not path.is_file():
            errors.append(f"missing binding: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"binding sha256 differs: {binding_id}")
    if plan.get("authorization") != EXPECTED_AUTHORIZATION:
        errors.append("authorization boundary differs")
    resources = plan.get("resources", {})
    if resources != {
        "minimum_free_disk_gib": 15,
        "maximum_workers": 1,
        "new_audio_download_bytes": 0,
        "retained_generated_audio": False,
    }:
        errors.append("resource boundary differs")
    policy = plan.get("audit_policy", {})
    if policy.get("trait_ids") != ["quiet", "clipped"]:
        errors.append("trait scope differs")
    for key in (
        "provider_background_label_can_substitute_for_quiet_level",
        "uploader_clipped_tag_can_substitute_for_capture_chain_record",
        "lossless_container_alone_can_substitute_for_origin_provenance",
        "exact_metadata_candidate_can_substitute_for_descriptor_confirmation",
        "metadata_candidate_can_substitute_for_trait_truth",
        "candidate_can_be_allocated_without_separate_freeze",
    ):
        if policy.get(key) is not False:
            errors.append(f"audit policy must remain false: {key}")
    if policy.get("reject_route_when_pre_audio_requirement_unestablished") is not True:
        errors.append("route rejection policy differs")
    publication = plan.get("publication_boundary", {})
    if publication.get("public_urls_and_non_sensitive_metadata_allowed") is not True:
        errors.append("public metadata boundary differs")
    for key, value in publication.items():
        if key != "public_urls_and_non_sensitive_metadata_allowed" and value is not False:
            errors.append(f"publication boundary must remain false: {key}")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("plan claim boundary must remain false")
    serialized = json.dumps(plan, sort_keys=True)
    if "/Users/" in serialized or "Application Support" in serialized:
        errors.append("plan exposes a private path")
    return sorted(set(errors))


def validate_report(
    report: dict[str, Any], plan: dict[str, Any] | None = None
) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != 1 or report.get("report_id") != AUDIT_ID:
        errors.append("report identity differs")
    if report.get("state") != (
        "bounded_metadata_only_exact_member_audit_complete_one_clipped_candidate_quiet_route_rejected"
    ):
        errors.append("report state differs")
    if report.get("plan_id") != AUDIT_ID:
        errors.append("report plan identity differs")
    if plan is None:
        plan = load_json(PLAN_PATH)
    if report.get("plan_sha256") != sha256_file(PLAN_PATH):
        errors.append("report plan sha256 differs")
    access = report.get("access_boundary", {})
    for key in EXPECTED_CLOSED_ACCESS:
        if access.get(key) is not False:
            errors.append(f"closed access boundary differs: {key}")
    for key in (
        "official_provider_records_read",
        "public_exact_member_records_read",
        "licence_and_attribution_metadata_read",
        "provenance_and_transformation_metadata_read",
        "relationship_metadata_read",
        "technical_container_metadata_read",
    ):
        if access.get(key) is not True:
            errors.append(f"authorized metadata access missing: {key}")

    quiet = report.get("quiet_audit", {})
    if quiet.get("provider_id") != "sonyc_backgrounds_5129078":
        errors.append("quiet provider differs")
    if quiet.get("exact_member_candidate_identified") is not False:
        errors.append("quiet candidate must remain unidentified")
    if quiet.get("route_disposition") != (
        "rejected_for_metadata_only_quiet_identification"
    ):
        errors.append("quiet route disposition differs")
    quiet_metadata = quiet.get("archive_member_metadata", {})
    if quiet_metadata.get("wav_member_count") != 550:
        errors.append("quiet member count differs")
    if quiet_metadata.get("member_level_sound_level_field_present") is not False:
        errors.append("quiet level metadata boundary differs")
    if quiet.get("descriptor_obligations") != {
        "absolute_pcm_level_measurement": "closed_not_computed",
        "nonzero_activity_support": "closed_not_computed",
    }:
        errors.append("quiet descriptor boundary differs")

    clipped = report.get("clipped_audit", {})
    if clipped.get("exact_member_id") != "freesound_sound_610933":
        errors.append("clipped exact member differs")
    if clipped.get("licence") != "CC0 1.0":
        errors.append("clipped licence differs")
    if clipped.get("exact_member_candidate_identified") is not True:
        errors.append("clipped metadata candidate is missing")
    if clipped.get("trait_assigned") is not False:
        errors.append("clipped trait must remain unassigned")
    if clipped.get("member_acquired") is not False:
        errors.append("clipped member must remain unacquired")
    container = clipped.get("public_container_metadata", {})
    if (
        container.get("original_upload_type") != "flac"
        or container.get("original_upload_is_lossless") is not True
    ):
        errors.append("clipped original lossless metadata differs")
    capture = clipped.get("capture_and_transformation_record", {})
    for key in (
        "physical_source_recorded",
        "microphone_model_documented",
        "audio_interface_model_documented",
        "capture_software_documented",
        "capture_rate_and_depth_documented",
        "capture_chain_clipping_explicitly_documented",
        "intentional_flat_top_waveform_excluded_by_record",
        "provider_original_file_download_is_byte_preserving",
    ):
        if capture.get(key) is not True:
            errors.append(f"clipped provenance differs: {key}")
    if capture.get("processing_or_editing_applied") is not False:
        errors.append("clipped transformation history differs")
    if clipped.get("descriptor_obligations") != {
        "plateau_or_saturation_support_measurement": "closed_not_computed"
    }:
        errors.append("clipped descriptor boundary differs")

    summary = report.get("summary", {})
    expected_summary = {
        "required_source_trait_count": 7,
        "explicit_candidate_record_count_before_audit": 5,
        "explicit_candidate_record_count_after_audit": 6,
        "quiet_exact_candidate_identified": False,
        "naturally_clipped_exact_metadata_candidate_identified": True,
        "source_trait_assigned": False,
        "source_member_acquired": False,
        "audio_accessed": False,
        "audio_descriptor_computed": False,
        "source_trait_manifest_frozen": False,
        "public_verdict_enabled": False,
    }
    if summary != expected_summary:
        errors.append("summary differs")
    decision = report.get("decision", {})
    for key in (
        "quiet_metadata_only_route_accepted",
        "naturally_clipped_trait_truth_established",
        "source_trait_manifest_frozen",
        "human_collection_authorized",
        "perceptual_metric_execution_authorized",
        "no_reference_work_eligible",
        "public_verdict_enabled",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision must remain false: {key}")
    if decision.get("quiet_metadata_only_route_rejected") is not True:
        errors.append("quiet route rejection missing")
    if decision.get("naturally_clipped_exact_metadata_candidate_identified") is not True:
        errors.append("clipped candidate decision missing")
    if not isinstance(decision.get("next_gate"), str):
        errors.append("next gate missing")
    claims = report.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("report claim boundary must remain false")
    serialized = json.dumps(report, sort_keys=True)
    if "/Users/" in serialized or "Application Support" in serialized:
        errors.append("report exposes a private path")
    return sorted(set(errors))


def validate_committed() -> list[str]:
    if not PLAN_PATH.is_file() or not REPORT_PATH.is_file():
        return ["committed audit artifact is missing"]
    plan = load_json(PLAN_PATH)
    return sorted(set(validate_plan(plan) + validate_report(load_json(REPORT_PATH), plan)))


def main() -> int:
    errors = validate_committed()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated {AUDIT_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
