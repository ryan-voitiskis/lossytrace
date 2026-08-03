#!/usr/bin/env python3
"""Validate the metadata-only permissive listening-source fallback."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "permissive-listening-source-fallback-plan.json"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if plan.get("state") != (
        "metadata_only_permissive_fallback_identified_audio_and_scores_closed"
    ):
        errors.append("fallback must remain metadata-only")

    bound: dict[str, dict[str, Any]] = {}
    for key, binding in plan.get("bindings", {}).items():
        path = root / str(binding.get("path", ""))
        if not path.is_file():
            errors.append(f"missing bound file: {key}")
            continue
        if sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {key}")
            continue
        if path.suffix == ".json":
            bound[key] = load_json(path)

    boundary = plan.get("access_boundary", {})
    expected_boundary = {
        "provider_audio_acquisition_authorized",
        "audio_member_opened",
        "published_processed_condition_opened",
        "listening_score_opened",
        "actual_codec_generation_authorized",
        "perceptual_metric_execution_authorized",
        "listener_response_collection_authorized",
        "participant_contact_authorized",
        "retained_audio_access_authorized",
        "sealed_evidence_access_authorized",
    }
    if set(boundary) != expected_boundary:
        errors.append("access boundary fields differ")
    for key in expected_boundary:
        if boundary.get(key) is not False:
            errors.append(f"access boundary must remain false: {key}")

    attribution = bound.get("odaq_attribution_audit", {})
    selection = attribution.get("selection", {})
    policy = plan.get("licence_policy", {})
    expected_classes = {"cc_by", "cc0"}
    if set(policy.get("allowed_classes", [])) != expected_classes:
        errors.append("permissive licence classes differ")
    if policy.get("selected_source_record_count") != selection.get("source_count"):
        errors.append("selected source count differs from attribution evidence")
    class_counts = selection.get("licence_class_counts", {})
    if policy.get("cc_by_source_record_count") != class_counts.get("cc_by"):
        errors.append("CC BY source count differs")
    if policy.get("cc0_source_record_count") != class_counts.get("cc0"):
        errors.append("CC0 source count differs")
    if policy.get("attribution_notice_ready_source_count") != selection.get(
        "attribution_notice_ready_source_count"
    ):
        errors.append("attribution-ready count differs")
    if policy.get("attribution_dependency_record_count") != selection.get(
        "dependency_licence_record_count"
    ):
        errors.append("attribution dependency count differs")
    if policy.get("noncommercial_determination_required_for_this_fallback") is not False:
        errors.append("fallback must not depend on a noncommercial licence")
    if policy.get("share_alike_obligation_present_in_this_fallback") is not False:
        errors.append("fallback must not contain ShareAlike sources")
    observed_classes = {
        item.get("licence_class") for item in attribution.get("licence_records", [])
    }
    if not observed_classes or not observed_classes <= expected_classes:
        errors.append("attribution evidence contains a non-permissive selected class")

    population = plan.get("selected_reference_population", {})
    groups = attribution.get("listening_groups", [])
    family_counts = selection.get("artifact_family_code_counts", {})
    music_count = sum(
        count for family, count in family_counts.items() if family != "DE"
    )
    if population.get("clean_reference_record_count") != len(groups):
        errors.append("clean reference count differs")
    if population.get("music_reference_count") != music_count:
        errors.append("music reference count differs")
    if population.get("movie_like_soundtrack_reference_count") != family_counts.get("DE"):
        errors.append("soundtrack reference count differs")
    if population.get("conservative_work_group_count") != 13:
        errors.append("conservative work grouping differs")
    if population.get("provider_stratum_count") != 1:
        errors.append("ODAQ must remain one provider stratum")
    if population.get("same_upstream_work_and_related_remixes_co_located") is not True:
        errors.append("related work grouping must be explicit")
    if population.get("selected_reference_members_exactly_frozen") is not False:
        errors.append("reference members were prematurely frozen")

    roles = plan.get("eligible_future_roles", {})
    for key in (
        "published_simulated_artifacts_as_actual_codec_conditions",
        "grouped_encoder_transfer",
        "independent_music_provider_transfer",
        "fresh_final_validation",
        "broad_commercial_music_claim",
        "all_genre_music_claim",
    ):
        if roles.get(key) is not False:
            errors.append(f"ineligible future role was enabled: {key}")
    for key in (
        "reference_only_actual_codec_development_listening",
        "reference_only_production_control_development_listening",
        "published_simulated_artifact_metric_sanity_check_after_separate_score_opening",
    ):
        if roles.get(key) is not True:
            errors.append(f"eligible future role differs: {key}")

    claims = plan.get("claim_boundary", {})
    if claims.get("one_provider_is_multiple_independent_providers") is not False:
        errors.append("one provider cannot be promoted to independent providers")
    if claims.get("published_scores_calibrate_actual_codec_audibility") is not False:
        errors.append("simulated-artifact scores cannot calibrate codec audibility")

    decision = plan.get("decision", {})
    if decision.get("permissive_fallback_identified") is not True:
        errors.append("permissive fallback is not identified")
    if decision.get("selected_attribution_metadata_complete") is not True:
        errors.append("selected attribution metadata must be complete")
    for key in (
        "reference_only_acquisition_plan_frozen",
        "source_and_condition_manifest_frozen",
        "physical_playback_qualified",
        "human_collection_authorized",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision was prematurely closed: {key}")
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
