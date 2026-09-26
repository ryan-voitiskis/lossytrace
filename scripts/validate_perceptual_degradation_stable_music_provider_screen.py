#!/usr/bin/env python3
"""Validate the score-blind stable music-provider public-record screen."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OBSERVATION_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-stable-music-provider-public-record-observation-20260814-001.json"
OBSERVATION_ID = "perceptual-degradation-stable-music-provider-public-record-observation-20260814-001"


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
        "official_public_papers_or_repository_metadata_read": True,
        "small_structured_metadata_responses_read_ephemerally": True,
        "raw_provider_metadata_persisted_in_research_storage": False,
        "archive_downloaded": False,
        "audio_member_accessed": False,
        "archive_member_listing_accessed": False,
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
        "structured_cc_by_field_overrides_additional_noncommercial_or_conduct_restrictions": False,
        "paper_licence_substitutes_for_audio_dataset_licence": False,
        "stable_record_substitutes_for_lossless_origin_audit": False,
        "professional_recording_substitutes_for_mastered_release": False,
        "processed_controlled_performance_substitutes_for_mastered_multigenre_music": False,
        "same_performer_work_session_or_derivative_may_cross_partitions": False,
        "candidate_capacity_is_qualified_truth": False,
    }
    if value.get("screen_policy") != expected_policy:
        errors.append("screen policy differs")

    candidates = {item.get("provider_id"): item for item in value.get("stable_controlled_music_candidates", [])}
    if set(candidates) != {"vienna_4x22", "raga_ornamentation_detection"}:
        errors.append("stable controlled-music candidate set differs")
    expected = {
        "vienna_4x22": ("vienna_4x22_v1", "CC BY 4.0", 22),
        "raga_ornamentation_detection": ("raga_ornamentation_detection_17851882_v4", "CC BY 4.0", 2),
    }
    for provider_id, expected_values in expected.items():
        item = candidates.get(provider_id, {})
        if (item.get("source_id"), item.get("licence"), item.get("candidate_group_capacity")) != expected_values:
            errors.append(f"candidate binding differs: {provider_id}")
        if item.get("capabilities") != ["music", "controlled_performance_music"]:
            errors.append(f"candidate capability differs: {provider_id}")
        if "not_mastered_release" not in str(item.get("music_role")):
            errors.append(f"candidate mastered-music boundary differs: {provider_id}")
        if not str(item.get("candidate_status", "")).endswith("exact_member_metadata_audit_candidate"):
            errors.append(f"candidate status differs: {provider_id}")
    vienna = candidates.get("vienna_4x22", {})
    if vienna.get("public_audio_distribution") != {
        "key": "audio.zip",
        "bytes": 1295130820,
        "checksum_exposed_on_public_page": False,
        "accrual_periodicity": "NEVER",
    }:
        errors.append("Vienna audio-distribution boundary differs")
    rod = candidates.get("raga_ornamentation_detection", {})
    if rod.get("immutable_files") != [{
        "key": "DATA.zip",
        "bytes": 2423991916,
        "md5": "6fb3ff4e19bb38742f770b407258476b",
    }]:
        errors.append("ROD immutable file binding differs")

    screened = {item.get("source_id"): item for item in value.get("screened_not_added", [])}
    if set(screened) != {
        "spheres_17347681",
        "freidi_20285754",
        "kraisler_21082251_v1",
        "moisesdb",
        "hiaudio_happy_birthday_collection",
        "musan_slr17",
        "fma",
    }:
        errors.append("screened-not-added set differs")
    if screened.get("spheres_17347681", {}).get("structured_licence") != "CC BY-SA 4.0":
        errors.append("Spheres licence disposition differs")
    if screened.get("kraisler_21082251_v1", {}).get("structured_licence") != "CC BY 4.0" or len(screened.get("kraisler_21082251_v1", {}).get("public_description_additional_restrictions", [])) != 2:
        errors.append("KRAISLER rights-conflict disposition differs")
    if screened.get("moisesdb", {}).get("audio_dataset_licence") != "CC BY-NC-SA 4.0" or screened.get("moisesdb", {}).get("paper_licence") != "CC BY 4.0":
        errors.append("MoisesDB licence-scope disposition differs")

    if value.get("aggregate_observation") != {
        "new_stable_controlled_music_candidate_provider_count": 2,
        "new_stable_controlled_music_candidate_group_capacity": 24,
        "new_stable_mastered_music_candidate_provider_count": 0,
        "new_stable_mastered_music_candidate_group_capacity": 0,
        "screened_not_added_provider_or_collection_count": 7,
        "qualified_reference_group_count": 0,
        "allocated_group_count": 0,
    }:
        errors.append("aggregate observation differs")
    expected_decision = {
        "stable_mastered_music_replacement_found": False,
        "stable_controlled_music_breadth_improved": True,
        "mutable_bandcamp_dependency_removed": False,
        "stable_only_three_domain_every_partition_established": False,
        "stable_only_mastered_music_every_partition_established": False,
        "source_successor_selected": False,
        "metric_successor_selected": False,
        "no_reference_work_eligible": False,
    }
    decision = value.get("decision", {})
    for key, expected_value in expected_decision.items():
        if decision.get(key) is not expected_value:
            errors.append(f"decision differs: {key}")
    if not isinstance(decision.get("next_responsible_human_decision"), str):
        errors.append("next responsible-human decision is missing")
    expected_claims = {
        "bounded_search_is_exhaustive_global_search",
        "candidate_capacity_is_scientific_feasibility",
        "controlled_music_proves_mastered_music_transfer",
        "stable_record_proves_lossless_origin",
        "screen_authorizes_audio_or_member_access",
        "screen_is_full_objective_negative_result",
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
