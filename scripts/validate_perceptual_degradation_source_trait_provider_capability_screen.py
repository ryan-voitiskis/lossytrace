#!/usr/bin/env python3
"""Validate the bounded source-trait provider-capability screen."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OBSERVATION_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-source-trait-provider-capability-screen-20260814-001.json"
)
OBSERVATION_ID = (
    "perceptual-degradation-source-trait-provider-capability-screen-20260814-001"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_observation(value: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if (
        value.get("schema_version") != 1
        or value.get("observation_id") != OBSERVATION_ID
    ):
        errors.append("observation identity differs")
    if value.get("state") != (
        "bounded_official_public_record_screen_complete_no_audio_member_or_trait_access"
    ):
        errors.append("observation state differs")

    expected_bindings = {
        "source_trait_plan",
        "source_trait_report",
        "source_candidate_plan",
        "sonyc_source_identity_audit",
    }
    bindings = value.get("bindings", {})
    if set(bindings) != expected_bindings:
        errors.append("binding inventory differs")
    else:
        for binding_id, binding in bindings.items():
            relative = binding.get("path") if isinstance(binding, dict) else None
            if not isinstance(relative, str) or Path(relative).is_absolute():
                errors.append(f"binding path differs: {binding_id}")
                continue
            path = root / relative
            if not path.is_file():
                errors.append(f"binding missing: {binding_id}")
            elif sha256_file(path) != binding.get("sha256"):
                errors.append(f"binding sha256 differs: {binding_id}")

    expected_access = {
        "committed_metadata_and_audits_read": True,
        "official_public_dataset_records_read": True,
        "official_public_system_paper_read": True,
        "official_public_api_documentation_read": True,
        "bounded_primary_source_web_search_performed": True,
        "freesound_catalog_query_executed": False,
        "public_exact_sound_record_read": False,
        "provider_audio_accessed": False,
        "retained_odaq_reference_accessed": False,
        "exact_member_metadata_inspected": False,
        "exact_member_selected": False,
        "source_trait_assigned": False,
        "stimulus_generated": False,
        "perceptual_metric_executed": False,
        "listener_response_or_score_accessed": False,
        "sealed_evidence_opened": False,
        "no_reference_training_performed": False,
        "public_verdict_enabled": False,
    }
    access = value.get("access_boundary", {})
    if access != expected_access:
        for key in sorted(set(access) | set(expected_access)):
            if access.get(key) is not expected_access.get(key):
                errors.append(f"access boundary differs: {key}")

    expected_policy = {
        "trait_ids": ["quiet", "clipped"],
        "official_primary_record_required": True,
        "allowed_licences": ["CC BY 4.0", "CC0 1.0"],
        "provider_capability_is_exact_member_evidence": False,
        "pcm_descriptor_is_provenance": False,
        "uploader_tag_alone_is_capture_chain_provenance": False,
        "lossless_container_alone_proves_original_coding_history": False,
        "bounded_search_failure_proves_global_absence": False,
        "exact_member_assignment_requires_separate_authorization": True,
    }
    if value.get("screen_policy") != expected_policy:
        errors.append("screen policy differs")

    observations = value.get("provider_capability_observations", [])
    by_trait = {
        item.get("trait_id"): item
        for item in observations
        if isinstance(item, dict)
    }
    if set(by_trait) != {"quiet", "clipped"} or len(observations) != 2:
        errors.append("provider capability inventory differs")
    quiet = by_trait.get("quiet", {})
    if (
        quiet.get("provider_id") != "sonyc_backgrounds_5129078"
        or quiet.get("licence") != "CC BY 4.0"
        or quiet.get("candidate_status")
        != "provisional_quiet_provider_capability_exact_member_audit_required"
        or quiet.get("exact_member_candidate_identified") is not False
    ):
        errors.append("quiet provider capability differs")
    if quiet.get("descriptor_obligation_status") != {
        "absolute_pcm_level_measurement": "unobserved_audio_access_closed",
        "nonzero_activity_support": "unobserved_audio_access_closed",
    }:
        errors.append("quiet descriptor boundary differs")
    if quiet.get("provenance_obligation_status") != {
        "preserved_source_gain_record": "partially_supported_common_calibrated_capture_chain",
        "no_attenuation_transform_substitution": "not_established_at_collection_level",
    }:
        errors.append("quiet provenance boundary differs")

    clipped = by_trait.get("clipped", {})
    if (
        clipped.get("provider_id") != "freesound_api_v2"
        or clipped.get("candidate_status")
        != "search_mechanism_only_no_naturally_clipped_candidate_identified"
        or clipped.get("exact_member_candidate_identified") is not False
    ):
        errors.append("clipped provider capability differs")
    if clipped.get("descriptor_obligation_status") != {
        "plateau_or_saturation_support_measurement": "unobserved_audio_access_closed"
    }:
        errors.append("clipped descriptor boundary differs")
    if clipped.get("provenance_obligation_status") != {
        "source_or_capture_chain_clipping_record": "not_structured_uploader_narrative_may_exist",
        "intentional_waveform_exclusion": "not_established_at_provider_level",
    }:
        errors.append("clipped provenance boundary differs")

    disposition = value.get("trait_disposition", {})
    expected_disposition_flags = {
        "quiet": {
            "provider_capability_identified": True,
            "exact_member_candidate_identified": False,
            "all_proof_obligations_satisfied": False,
        },
        "clipped": {
            "provider_search_capability_identified": True,
            "exact_member_candidate_identified": False,
            "all_proof_obligations_satisfied": False,
        },
    }
    for trait_id, expected in expected_disposition_flags.items():
        item = disposition.get(trait_id, {})
        for key, expected_value in expected.items():
            if item.get(key) is not expected_value:
                errors.append(f"trait disposition differs: {trait_id}.{key}")
        if not isinstance(item.get("disposition"), str):
            errors.append(f"trait disposition text missing: {trait_id}")

    expected_decision = {
        "quiet_provider_capability_route_found": True,
        "quiet_candidate_identified": False,
        "naturally_clipped_candidate_identified": False,
        "source_trait_manifest_frozen": False,
        "source_successor_selected": False,
        "metric_successor_selected": False,
        "human_collection_authorized": False,
        "no_reference_work_eligible": False,
    }
    decision = value.get("decision", {})
    for key, expected in expected_decision.items():
        if decision.get(key) is not expected:
            errors.append(f"decision differs: {key}")
    if not isinstance(decision.get("next_gate"), str):
        errors.append("next gate is missing")

    expected_claims = {
        "provider_capability_proves_quiet_trait",
        "api_search_capability_proves_clipped_trait",
        "bounded_search_proves_no_global_candidate_exists",
        "exact_member_or_trait_selected",
        "quiet_or_clipped_scientific_coverage_complete",
        "screen_authorizes_audio_or_exact_member_access",
        "screen_is_full_objective_positive_result",
        "public_cli_changed",
    }
    claims = value.get("claim_boundary", {})
    if set(claims) != expected_claims:
        errors.append("claim boundary inventory differs")
    for key, item in claims.items():
        if item is not False:
            errors.append(f"claim boundary must remain false: {key}")
    return sorted(set(errors))


def validate_committed_observation(path: Path = OBSERVATION_PATH) -> list[str]:
    if not path.is_file():
        return ["committed observation is missing"]
    return validate_observation(load_json(path))


def main() -> int:
    errors = validate_committed_observation()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated {OBSERVATION_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
