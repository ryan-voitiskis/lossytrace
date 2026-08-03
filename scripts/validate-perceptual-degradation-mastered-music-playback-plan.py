#!/usr/bin/env python3
"""Validate mastered-music and physical-playback qualification boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/mastered-music-playback-qualification-plan.json"
)
PRIMARY_SOURCE_IDS = {"rwc_music_v2_2026", "maestro_v3_0_0", "mshoxxdb_v1_2"}
DEFERRED_SOURCE_IDS = {
    "musicnet_1_0",
    "medleydb",
    "fma",
    "mtg_jamendo",
    "musdb18hq_consumed_transfer",
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
        raise ValueError(f"{path}: expected an object")
    return value


def validate(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if plan.get("state") != (
        "metadata_and_local_device_observed_audio_and_human_collection_unauthorized"
    ):
        errors.append("qualification state differs")

    for binding_id, binding in plan.get("bindings", {}).items():
        relative = binding.get("path", "")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            errors.append(f"invalid repository-relative binding: {binding_id}")
            continue
        path = root / relative
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"binding hash differs: {binding_id}")

    for field, value in plan.get("access_boundary", {}).items():
        if value is not False:
            errors.append(f"access boundary must remain false: {field}")

    primary = plan.get("current_primary_source_observations", [])
    if {item.get("source_id") for item in primary} != PRIMARY_SOURCE_IDS:
        errors.append("primary music source set differs")
    for item in primary:
        if item.get("observed_on") != "2026-08-04":
            errors.append(f"source observation date differs: {item.get('source_id')}")
        if not str(item.get("primary_record", "")).startswith("https://"):
            errors.append(f"primary source URL differs: {item.get('source_id')}")
        if "unresolved" not in item.get("operational_state", ""):
            errors.append(f"source was prematurely operationalized: {item.get('source_id')}")

    deferred = plan.get("deferred_or_excluded_sources", [])
    if {item.get("source_id") for item in deferred} != DEFERRED_SOURCE_IDS:
        errors.append("deferred music source set differs")
    dispositions = {item.get("source_id"): item.get("disposition") for item in deferred}
    if dispositions.get("fma") != "natural_hard_negative_only":
        errors.append("FMA reference boundary differs")
    if dispositions.get("mtg_jamendo") != "natural_hard_negative_only":
        errors.append("MTG-Jamendo reference boundary differs")
    if dispositions.get("musdb18hq_consumed_transfer") != "consumed_development_only":
        errors.append("consumed MUSDB boundary differs")

    claims = plan.get("claim_boundary", {})
    for field in (
        "broad_commercial_music_claim_authorized",
        "all_genre_music_claim_authorized",
        "rwc_track_count_treated_as_independent_provider_count",
        "lossy_distributed_audio_used_as_lossless_reference",
    ):
        if claims.get(field) is not False:
            errors.append(f"claim boundary differs: {field}")
    if claims.get("current_freezable_claim") != (
        "none_until_licence_and_independent_provider_gates_close"
    ):
        errors.append("music claim was prematurely frozen")

    fallback = plan.get("permissive_source_fallback", {})
    if fallback.get("source_id") != "odaq_cc_by_cc0_clean_references":
        errors.append("permissive fallback source differs")
    for field, expected in (
        ("development_reference_count", 16),
        ("music_reference_count", 9),
        ("movie_like_soundtrack_reference_count", 7),
        ("conservative_work_group_count", 13),
        ("provider_stratum_count", 1),
    ):
        if fallback.get(field) != expected:
            errors.append(f"permissive fallback count differs: {field}")
    if set(fallback.get("licence_classes", [])) != {"cc_by", "cc0"}:
        errors.append("permissive fallback licence classes differ")
    if fallback.get("attribution_metadata_complete") is not True:
        errors.append("permissive fallback attribution metadata is incomplete")
    if fallback.get("reference_member_metadata_frozen") is not True:
        errors.append("permissive fallback reference metadata is not frozen")
    if fallback.get("reference_member_metadata_sha256") != (
        "1a39f50013a4274f60ca7c1771ebad22dcafda6950db87d2ffe4acdfb58ab0e7"
    ):
        errors.append("permissive fallback reference metadata hash differs")
    if fallback.get("reference_member_metadata_replays_byte_identical") is not True:
        errors.append("permissive fallback metadata replay differs")
    if fallback.get("reference_total_compressed_bytes") != 46_721_638:
        errors.append("permissive fallback compressed-byte total differs")
    if fallback.get("reference_total_uncompressed_bytes") != 54_633_154:
        errors.append("permissive fallback uncompressed-byte total differs")
    for field in (
        "noncommercial_decision_required",
        "share_alike_obligation_present",
        "actual_codec_condition_present",
        "reference_audio_acquisition_authorized",
        "independent_provider_transfer_supported",
        "final_validation_supported",
    ):
        if fallback.get(field) is not False:
            errors.append(f"permissive fallback boundary differs: {field}")
    if fallback.get("operational_state") != (
        "metadata_only_reference_acquisition_not_authorized"
    ):
        errors.append("permissive fallback was prematurely operationalized")

    excerpt = plan.get("excerpt_policy", {})
    if excerpt.get("maximum_seconds") != 12:
        errors.append("excerpt duration differs")
    for field in (
        "identity_hashed_offset_required",
        "same_source_and_related_versions_co_located",
        "selection_before_metric_or_listener_outcomes",
        "private_member_manifest_required",
        "public_source_paths_forbidden",
    ):
        if excerpt.get(field) is not True:
            errors.append(f"excerpt policy differs: {field}")
    if excerpt.get("artifact_sensitive_manual_selection_authorized_now") is not False:
        errors.append("manual excerpt selection is prematurely authorized")

    playback = plan.get("local_playback_observation", {})
    if playback.get("default_output") != "MacBook Pro Speakers":
        errors.append("local output observation differs")
    if playback.get("output_channels") != 2 or playback.get("current_sample_rate_hz") != 44100:
        errors.append("local output geometry differs")
    for field in (
        "external_dac_or_amplifier_observed",
        "headphones_observed",
        "transducer_model_qualified",
        "ambient_noise_class_qualified",
        "level_calibration_method_qualified",
        "system_effects_state_qualified",
        "physical_playback_qualified",
        "operator_synthetic_audibility_confirmation_reused_as_qualification",
    ):
        if playback.get(field) is not False:
            errors.append(f"playback boundary differs: {field}")

    if len(plan.get("human_decisions_required", [])) != 4:
        errors.append("human decision list differs")
    decision = plan.get("decision", {})
    if decision.get("production_and_generation_recipe_gate_closed") is not True:
        errors.append("completed recipe gate was lost")
    if decision.get("mastered_music_candidates_identified") is not True:
        errors.append("mastered music candidates are not identified")
    if decision.get("permissive_source_fallback_identified") is not True:
        errors.append("permissive source fallback is not identified")
    if decision.get("permissive_reference_metadata_frozen") is not True:
        errors.append("permissive reference metadata is not frozen")
    if decision.get("excerpt_policy_frozen") is not True:
        errors.append("excerpt policy is not frozen")
    for field in (
        "independent_music_provider_gate_closed",
        "licences_frozen",
        "private_excerpt_manifest_frozen",
        "physical_playback_qualified",
        "source_and_condition_manifest_freezable",
        "human_collection_authorized",
    ):
        if decision.get(field) is not False:
            errors.append(f"premature qualification completion: {field}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    args = parser.parse_args()
    errors = validate(load_json(args.plan))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated {args.plan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
