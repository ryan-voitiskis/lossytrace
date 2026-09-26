#!/usr/bin/env python3
"""Validate the score-blind stable speech-provider public-record screen."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OBSERVATION_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-stable-speech-provider-public-record-observation-20260814-001.json"
OBSERVATION_ID = "perceptual-degradation-stable-speech-provider-public-record-observation-20260814-001"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def validate_observation(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if value.get("schema_version") != 1 or value.get("observation_id") != OBSERVATION_ID:
        errors.append("observation identity differs")
    if value.get("state") != "official_public_record_screen_complete_no_audio_or_member_access":
        errors.append("observation state differs")

    expected_access = {
        "official_public_dataset_pages_read": True,
        "official_public_paper_read": True,
        "small_structured_repository_metadata_read_ephemerally": True,
        "repository_object_names_and_hashes_read_ephemerally": True,
        "raw_provider_metadata_persisted_in_research_storage": False,
        "repository_data_object_opened": False,
        "parquet_content_accessed": False,
        "audio_member_accessed": False,
        "exact_source_member_selected": False,
        "retained_odaq_reference_accessed": False,
        "processed_odaq_condition_accessed": False,
        "perceptual_metric_executed": False,
        "target_perceptual_degradation_score_accessed": False,
        "listener_response_collected": False,
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
        "allowed_dataset_licences": ["CC BY 4.0", "CC0 1.0"],
        "version_or_content_addressed_record_required": True,
        "documented_direct_airborne_microphone_required": True,
        "clean_speech_subset_required": True,
        "body_conduction_channel_eligible_as_clean_reference": False,
        "noisy_or_speechless_subset_eligible_as_clean_speech_reference": False,
        "participant_crosses_partition_boundary": False,
        "repository_stability_substitutes_for_exact_member_audit": False,
        "candidate_capacity_is_qualified_truth": False,
    }
    if value.get("screen_policy") != expected_policy:
        errors.append("screen policy differs")

    candidates = value.get("stable_speech_candidates", [])
    if len(candidates) != 1:
        errors.append("stable speech candidate set differs")
    candidate = candidates[0] if len(candidates) == 1 else {}
    if (
        candidate.get("source_id"),
        candidate.get("provider_id"),
        candidate.get("doi"),
        candidate.get("doi_cited_revision"),
        candidate.get("repository_commit"),
        candidate.get("licence"),
        candidate.get("public_participant_count"),
        candidate.get("candidate_group_capacity"),
        candidate.get("capabilities"),
    ) != (
        "vibravox_hf_2727_revision_7990b7d",
        "vibravox",
        "10.57967/hf/2727",
        "7990b7d",
        "7990b7df7153f5ba543ee89d9bbb65579c21d330",
        "CC BY 4.0",
        188,
        188,
        ["speech"],
    ):
        errors.append("VibraVox candidate binding differs")
    if candidate.get("eligible_public_subset") != "speech_clean" or candidate.get("eligible_public_audio_field") != "audio.headset_microphone":
        errors.append("VibraVox eligible field boundary differs")
    if candidate.get("excluded_public_subsets") != ["speech_noisy", "speechless_clean", "speechless_noisy"]:
        errors.append("VibraVox excluded subset boundary differs")
    if set(candidate.get("excluded_public_audio_fields", [])) != {
        "audio.forehead_accelerometer",
        "audio.soft_in_ear_microphone",
        "audio.rigid_in_ear_microphone",
        "audio.temple_vibration_pickup",
        "audio.throat_microphone",
    }:
        errors.append("VibraVox excluded sensor boundary differs")
    if candidate.get("candidate_status") != "content_addressed_exact_member_metadata_audit_candidate":
        errors.append("VibraVox candidate status differs")

    if value.get("aggregate_observation") != {
        "new_stable_speech_candidate_provider_count": 1,
        "new_stable_speech_candidate_group_capacity": 188,
        "qualified_reference_group_count": 0,
        "allocated_group_count": 0,
    }:
        errors.append("aggregate observation differs")
    expected_decision = {
        "stable_fourth_speech_provider_found": True,
        "mutable_icsi_dependency_for_three_domain_arithmetic_removed": True,
        "stable_only_three_domain_every_partition_established": True,
        "stable_only_reference_120_every_partition_established": True,
        "stable_only_mastered_music_every_partition_established": False,
        "source_successor_selected": False,
        "metric_successor_selected": False,
        "no_reference_work_eligible": False,
    }
    decision = value.get("decision", {})
    for key, expected in expected_decision.items():
        if decision.get(key) is not expected:
            errors.append(f"decision differs: {key}")
    if not isinstance(decision.get("next_responsible_human_decision"), str):
        errors.append("next responsible-human decision is missing")
    expected_claims = {
        "candidate_capacity_is_scientific_feasibility",
        "repository_commit_proves_exact_member_eligibility",
        "dry_headset_reference_proves_lossless_delivered_origin",
        "stable_speech_repair_clears_mastered_music",
        "screen_authorizes_repository_data_object_or_audio_access",
        "screen_is_full_objective_positive_result",
        "public_cli_changed",
    }
    claims = value.get("claim_boundary", {})
    if set(claims) != expected_claims:
        errors.append("claim-boundary key set differs")
    for key, item in claims.items():
        if item is not False:
            errors.append(f"claim boundary must remain false: {key}")
    return errors


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
