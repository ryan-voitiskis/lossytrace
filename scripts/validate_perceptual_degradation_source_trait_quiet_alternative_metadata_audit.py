#!/usr/bin/env python3
"""Validate the bounded alternative-provider quiet metadata audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1"
    / "source-trait-quiet-alternative-metadata-audit-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence"
    / "perceptual-degradation-source-trait-quiet-alternative-metadata-audit-20260817-001.json"
)
AUDIT_ID = (
    "perceptual-degradation-source-trait-quiet-alternative-metadata-audit-20260817-001"
)

EXPECTED_BINDINGS = {
    "research_contract",
    "source_trait_plan",
    "source_trait_report",
    "predecessor_metadata_audit_plan",
    "predecessor_metadata_audit_report",
}

EXPECTED_AUTHORIZATION = {
    "public_and_provider_metadata_read_authorized": True,
    "licensing_and_attribution_metadata_read_authorized": True,
    "provenance_and_transformation_metadata_read_authorized": True,
    "relationship_metadata_read_authorized": True,
    "technical_container_metadata_read_authorized": True,
    "exact_member_metadata_inspection_authorized": True,
    "bounded_alternative_provider_search_authorized": True,
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
        "bounded_metadata_only_alternative_quiet_provider_audit_authorized_before_audio_access"
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
    if plan.get("resources") != {
        "minimum_free_disk_gib": 15,
        "maximum_workers": 1,
        "new_audio_download_bytes": 0,
        "retained_generated_audio": False,
    }:
        errors.append("resource boundary differs")
    policy = plan.get("audit_policy", {})
    if policy.get("trait_id") != "quiet":
        errors.append("trait scope differs")
    if policy.get("provider_scope") != ["freesound_public_exact_member_records"]:
        errors.append("provider scope differs")
    if policy.get("reject_route_when_pre_audio_requirement_unestablished") is not True:
        errors.append("route rejection policy differs")
    for key in (
        "provider_quiet_word_can_substitute_for_absolute_pcm_level",
        "lossless_container_alone_can_substitute_for_origin_provenance",
        "capture_device_without_gain_record_can_establish_preserved_gain",
        "no_processing_without_capture_gain_can_establish_preserved_gain",
        "exact_metadata_candidate_can_substitute_for_descriptor_confirmation",
        "metadata_candidate_can_substitute_for_trait_truth",
        "related_uploads_can_substitute_for_independent_contrasts",
        "candidate_can_be_allocated_without_separate_freeze",
    ):
        if policy.get(key) is not False:
            errors.append(f"audit policy must remain false: {key}")
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
        "bounded_metadata_only_alternative_quiet_provider_audit_complete_one_exact_candidate_identified"
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

    screened = report.get("bounded_route_screen", [])
    if len(screened) != 5 or any(
        item.get("disposition") != "rejected_before_audio_access"
        for item in screened
    ):
        errors.append("bounded rejection inventory differs")

    quiet = report.get("quiet_audit", {})
    if quiet.get("provider_id") != "freesound":
        errors.append("quiet provider differs")
    if quiet.get("exact_member_id") != "freesound_sound_426894":
        errors.append("quiet exact member differs")
    if quiet.get("licence") != "CC0 1.0":
        errors.append("quiet licence differs")
    if quiet.get("exact_member_candidate_identified") is not True:
        errors.append("quiet exact metadata candidate is missing")
    if quiet.get("trait_assigned") is not False:
        errors.append("quiet trait must remain unassigned")
    if quiet.get("member_acquired") is not False:
        errors.append("quiet member must remain unacquired")
    container = quiet.get("public_container_metadata", {})
    if (
        container.get("original_upload_type") != "wav"
        or container.get("original_upload_is_lossless") is not True
        or container.get("sample_rate_hz") != 96000
        or container.get("bit_depth") != 24
        or container.get("channel_count") != 2
    ):
        errors.append("quiet original lossless metadata differs")
    capture = quiet.get("quiet_scene_and_capture_record", {})
    for key in (
        "physical_scene_recorded",
        "scene_activity_documented",
        "provider_original_file_download_is_byte_preserving",
    ):
        if capture.get(key) is not True:
            errors.append(f"quiet provenance differs: {key}")
    if capture.get("capture_gain_setting") != "M9":
        errors.append("quiet capture gain differs")
    if capture.get("post_capture_processing_applied") is not False:
        errors.append("quiet transformation history differs")
    if capture.get("post_capture_attenuation_or_normalization_documented") is not False:
        errors.append("quiet attenuation boundary differs")
    if quiet.get("descriptor_obligations") != {
        "absolute_pcm_level_measurement": "closed_not_computed",
        "nonzero_activity_support": "closed_not_computed",
    }:
        errors.append("quiet descriptor boundary differs")
    relationship = quiet.get("relationship_boundary", {})
    if relationship.get("related_exact_member_id") != "freesound_sound_427932":
        errors.append("quiet related member differs")
    if relationship.get("related_member_is_independent_contrast") is not False:
        errors.append("related quiet member must remain non-independent")

    expected_summary = {
        "required_source_trait_count": 7,
        "explicit_candidate_record_count_before_audit": 6,
        "explicit_candidate_record_count_after_audit": 7,
        "quiet_exact_metadata_candidate_identified": True,
        "naturally_clipped_exact_metadata_candidate_retained": True,
        "independent_sparse_and_tonal_contrasts_still_missing": True,
        "source_trait_assigned": False,
        "source_member_acquired": False,
        "audio_accessed": False,
        "audio_descriptor_computed": False,
        "source_trait_manifest_frozen": False,
        "public_verdict_enabled": False,
    }
    if report.get("summary") != expected_summary:
        errors.append("summary differs")
    decision = report.get("decision", {})
    for key in (
        "quiet_trait_truth_established",
        "quiet_descriptor_confirmation_authorized",
        "source_trait_manifest_frozen",
        "human_collection_authorized",
        "perceptual_metric_execution_authorized",
        "no_reference_work_eligible",
        "public_verdict_enabled",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision must remain false: {key}")
    for key in (
        "alternative_quiet_metadata_route_accepted",
        "quiet_exact_metadata_candidate_identified",
    ):
        if decision.get(key) is not True:
            errors.append(f"candidate decision missing: {key}")
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
