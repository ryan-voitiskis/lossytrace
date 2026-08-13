#!/usr/bin/env python3
"""Validate the score-blind stable mastered-music public-record screen."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OBSERVATION_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-stable-mastered-music-provider-public-record-observation-20260814-001.json"
OBSERVATION_ID = "perceptual-degradation-stable-mastered-music-provider-public-record-observation-20260814-001"


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
        "official_public_record_pages_read": True,
        "official_public_structured_metadata_read_ephemerally": True,
        "top_level_file_names_sizes_and_checksums_read_ephemerally": True,
        "raw_provider_metadata_persisted_in_research_storage": False,
        "archive_downloaded": False,
        "archive_member_listing_accessed": False,
        "audio_member_accessed": False,
        "waveform_or_container_inspected": False,
        "exact_source_member_selected": False,
        "exact_member_relationship_audit_performed": False,
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
        "immutable_doi_record_required": True,
        "creator_or_rights_holder_release_relationship_required": True,
        "lossless_top_level_wav_or_public_lossless_archive_required": True,
        "public_album_or_release_role_required": True,
        "same_creator_catalog_may_cross_partitions": False,
        "same_composition_language_version_render_or_derivative_may_cross_partitions": False,
        "record_file_count_substitutes_for_relationship_audit": False,
        "artist_release_label_proves_mastering_or_origin_chain": False,
        "candidate_capacity_is_qualified_truth": False,
    }
    if value.get("screen_policy") != expected_policy:
        errors.append("screen policy differs")

    candidates = {item.get("provider_id"): item for item in value.get("stable_mastered_music_candidates", [])}
    expected_candidates = {
        "solar_flux_zenodo": ("solar_flux_albums_one_two_zenodo", "CC BY 4.0", 16),
        "lotte_lehmann_farewell_recital": ("lotte_lehmann_santa_barbara_14226540", "CC BY 4.0", 19),
        "remnant_tamil_worship": ("remnant_tamil_worship_albums_1_2_hd", "CC BY 4.0", 12),
    }
    if set(candidates) != set(expected_candidates):
        errors.append("stable mastered-music candidate set differs")
    for provider_id, expected in expected_candidates.items():
        item = candidates.get(provider_id, {})
        if (item.get("source_id"), item.get("licence"), item.get("candidate_group_capacity")) != expected:
            errors.append(f"candidate binding differs: {provider_id}")
        if item.get("capabilities") != ["music", "mastered_music"]:
            errors.append(f"candidate capability differs: {provider_id}")
        if not str(item.get("candidate_status", "")).startswith("immutable_"):
            errors.append(f"candidate status differs: {provider_id}")
        if "unaudited" not in str(item.get("music_role", "")):
            errors.append(f"candidate provenance limit differs: {provider_id}")

    solar = candidates.get("solar_flux_zenodo", {})
    if [
        (item.get("record_id"), item.get("top_level_wav_count"), item.get("total_bytes"))
        for item in solar.get("record_distributions", [])
    ] != [(21454470, 8, 354494816), (21454972, 8, 364210016)]:
        errors.append("Solar Flux record distributions differ")
    lehmann = candidates.get("lotte_lehmann_farewell_recital", {})
    if (
        lehmann.get("record_id"),
        lehmann.get("public_description_wav_count"),
        lehmann.get("observed_top_level_wav_count"),
        lehmann.get("observed_total_bytes"),
    ) != (14226540, 21, 19, 565304036):
        errors.append("Lehmann record discrepancy boundary differs")
    remnant = candidates.get("remnant_tamil_worship", {})
    if [
        (item.get("record_id"), item.get("public_composition_count"), item.get("top_level_wav_count"), item.get("total_bytes"))
        for item in remnant.get("record_distributions", [])
    ] != [(20969062, 6, 55, 2352378693), (21020982, 6, 60, 3178615913)]:
        errors.append("Remnant record distributions differ")

    screened = {item.get("source_id"): item for item in value.get("screened_not_added", [])}
    if set(screened) != {
        "wayze_21896670",
        "daniel_william_lawrence_five_albums",
        "solar_flux_album_three_21455104",
        "tin_men_and_the_telephone_zenodo_catalog",
    }:
        errors.append("screened-not-added set differs")
    if screened.get("daniel_william_lawrence_five_albums", {}).get("candidate_group_capacity_ceiling") != 5:
        errors.append("Daniel Lawrence capacity boundary differs")
    if screened.get("tin_men_and_the_telephone_zenodo_catalog", {}).get("candidate_group_capacity_ceiling") != 2:
        errors.append("Tin Men capacity boundary differs")

    if value.get("aggregate_observation") != {
        "new_stable_mastered_music_candidate_provider_count": 3,
        "new_stable_mastered_music_candidate_group_capacity": 47,
        "screened_not_added_provider_or_collection_count": 4,
        "qualified_reference_group_count": 0,
        "allocated_group_count": 0,
    }:
        errors.append("aggregate observation differs")
    expected_decision = {
        "stable_mastered_music_replacement_found": True,
        "stable_only_mastered_music_every_partition_established": True,
        "mutable_bandcamp_dependency_removed_for_arithmetic": True,
        "production_origin_and_mastering_chain_complete": False,
        "exact_member_relationship_audit_complete": False,
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
        "structured_cc_by_proves_recording_or_mastering_rights_chain",
        "artist_labelled_album_proves_never_lossy_origin",
        "top_level_wav_name_proves_pcm_integrity",
        "track_or_composition_count_proves_independence",
        "stable_mastered_arithmetic_selects_a_source_successor",
        "screen_authorizes_archive_member_or_audio_access",
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
