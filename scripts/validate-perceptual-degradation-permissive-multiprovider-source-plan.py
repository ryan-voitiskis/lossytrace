#!/usr/bin/env python3
"""Validate the score-blind permissive multi-provider source candidate plan."""

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
    / "permissive-multiprovider-source-candidate-plan.json"
)
PLAN_ID = "perceptual-degradation-permissive-multiprovider-source-candidate-20260813-001"
OBSERVATION_ID = "perceptual-degradation-permissive-multiprovider-source-observation-20260813-001"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "score_blind_metadata_only_candidates_unallocated_manifest_not_frozen"
    ):
        errors.append("plan must remain metadata-only and unallocated")

    bound: dict[str, dict[str, Any]] = {}
    for binding_id, binding in plan.get("bindings", {}).items():
        relative = binding.get("path")
        expected = binding.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            errors.append(f"binding differs: {binding_id}")
            continue
        path = root / relative
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
            continue
        if sha256_file(path) != expected:
            errors.append(f"bound file hash differs: {binding_id}")
            continue
        if path.suffix == ".json":
            bound[binding_id] = load_json(path)

    observation = bound.get("public_metadata_observation", {})
    if observation.get("observation_id") != OBSERVATION_ID:
        errors.append("metadata observation identity differs")
    observation_boundary = observation.get("access_boundary", {})
    if observation_boundary.get("provider_metadata_read") is not True:
        errors.append("provider metadata observation must be explicit")
    for key in (
        "provider_audio_downloaded",
        "provider_audio_opened",
        "retained_odaq_audio_opened",
        "processed_condition_opened",
        "listening_score_opened",
        "perceptual_metric_executed",
        "sealed_evidence_opened",
        "human_collection_authorized",
    ):
        if observation_boundary.get(key) is not False:
            errors.append(f"metadata observation access boundary must remain false: {key}")

    expected_authorization = {
        "public_metadata_read_authorized": True,
        "new_audio_acquisition_authorized": False,
        "retained_odaq_reference_read_authorized": False,
        "retained_reference_projection_authorized": False,
        "processed_condition_access_authorized": False,
        "listening_score_access_authorized": False,
        "perceptual_metric_execution_authorized": False,
        "human_collection_authorized": False,
        "recruitment_authorized": False,
        "sealed_evidence_access_authorized": False,
        "no_reference_training_authorized": False,
        "public_verdict_enabled": False,
    }
    if plan.get("authorization") != expected_authorization:
        errors.append("authorization boundary differs")

    feasibility = bound.get("listening_feasibility_report", {})
    source_frontier = feasibility.get("source_frontier", {})
    partitions = plan.get("partition_requirements", {})
    minimum = source_frontier.get(
        "minimum_source_groups_per_independent_partition_for_asymptotic_80_percent_equivalence_power"
    )
    if minimum != 39 or partitions.get("minimum_independent_source_groups_per_partition") != minimum:
        errors.append("39-source asymptotic floor differs")
    expected_partition_totals = {
        row["partition_count"]: row
        for row in source_frontier.get("partition_requirements", [])
    }
    if partitions.get(
        "minimum_unique_source_groups_across_four_partitions"
    ) != expected_partition_totals.get(4, {}).get(
        "asymptotic_minimum_unique_source_groups"
    ):
        errors.append("four-partition minimum differs")
    if partitions.get(
        "reference_sensitivity_unique_source_groups_across_four_partitions"
    ) != expected_partition_totals.get(4, {}).get(
        "reference_120_per_partition_unique_source_groups"
    ):
        errors.append("four-partition reference sensitivity differs")
    if partitions.get("truth_bearing_partitions") != [
        "development",
        "calibration",
        "transfer",
        "final_validation",
    ]:
        errors.append("truth-bearing partitions differ")
    for key in (
        "source_group_may_cross_partitions",
        "same_work_performance_session_duplicate_midi_uploader_or_speaker_may_cross_partitions",
        "provider_assignment_is_frozen",
        "provider_spanning_partitions_counts_as_provider_held_out_evidence",
    ):
        if partitions.get(key) is not False:
            errors.append(f"partition boundary must remain false: {key}")
    if partitions.get(
        "provider_used_as_a_holdout_must_be_wholly_unseen_outside_its_holdout_partition"
    ) is not True:
        errors.append("whole-provider holdout requirement differs")
    if partitions.get("minimum_provider_count_per_partition") is not None:
        errors.append("minimum provider count was prematurely invented")

    evaluation = bound.get("full_reference_evaluation_plan", {})
    expected_domain_minimum = evaluation.get("statistics", {}).get(
        "minimum_primary_domain_source_groups"
    )
    if (
        partitions.get("minimum_primary_domain_source_groups_at_evaluation")
        != expected_domain_minimum
    ):
        errors.append("primary-domain source minimum differs")
    if partitions.get("primary_domains_must_be_declared_before_evaluation") is not True:
        errors.append("primary domains must be declared before evaluation")

    observations = observation.get("observations", [])
    by_source = {item.get("source_id"): item for item in observations}
    if len(by_source) != len(observations):
        errors.append("metadata observation source IDs must be unique")
    if set(observation.get("licence_policy", {}).get("allowed_classes", [])) != {
        "CC BY 4.0",
        "CC0 1.0",
    }:
        errors.append("permissive licence policy differs")

    tier_sources: set[str] = set()
    for tier in plan.get("candidate_tiers", []):
        source_ids = tier.get("source_ids", [])
        if not isinstance(source_ids, list) or not source_ids:
            errors.append(f"candidate tier is empty: {tier.get('tier_id')}")
            continue
        overlap = tier_sources.intersection(source_ids)
        if overlap:
            errors.append(
                f"candidate source appears in multiple tiers: {sorted(overlap)[0]}"
            )
        tier_sources.update(source_ids)
        missing = set(source_ids) - set(by_source)
        if missing:
            errors.append(
                f"candidate tier references unknown source: {sorted(missing)[0]}"
            )
        available = sum(
            int(by_source[source_id]["conservative_available_group_count"])
            for source_id in source_ids
            if source_id in by_source
        )
        providers = {
            by_source[source_id]["provider_id"]
            for source_id in source_ids
            if source_id in by_source
        }
        if tier.get("available_group_count") != available:
            errors.append(f"candidate tier group total differs: {tier.get('tier_id')}")
        if tier.get("provider_count") != len(providers):
            errors.append(f"candidate tier provider total differs: {tier.get('tier_id')}")
        if tier.get("qualified_reference_group_count") != 0:
            errors.append(
                f"candidate tier prematurely qualifies references: {tier.get('tier_id')}"
            )
        if tier.get("allocated_group_count") != 0:
            errors.append(
                f"candidate tier prematurely allocates groups: {tier.get('tier_id')}"
            )
    if tier_sources != set(by_source):
        errors.append("candidate tiers do not cover each observed source exactly once")

    expected_roles = {
        "slakh2100_redux": "candidate_after_exact_member_origin_and_attribution_audit",
        "guitarset_3371780": "candidate_after_exact_member_origin_and_attribution_audit",
        "vctk_clean_56spk_2017": "candidate_after_exact_member_origin_and_attribution_audit",
        "sonyc_backgrounds_5129078": "candidate_after_exact_member_origin_and_attribution_audit",
        "satp_soundscapes_10159673": "candidate_after_exact_member_origin_and_attribution_audit",
        "lombard_grid_3736465": "candidate_after_exact_member_origin_and_attribution_audit",
        "tinysol_3685367": "candidate_after_exact_member_origin_and_attribution_audit",
        "musicnet_5120004": "pending_upstream_coding_history_audit",
        "fsd50k_4060432_allowed_items": "negative_only_or_pending_clip_level_origin_audit",
        "nsynth": "development_only_bandwidth_limited_negative",
        "odaq_retained_clean_references": "development_only_authorization_bound",
    }
    for source_id, expected_role in expected_roles.items():
        if by_source.get(source_id, {}).get("role_status") != expected_role:
            errors.append(f"candidate role differs: {source_id}")

    tiers = {tier.get("tier_id"): tier for tier in plan.get("candidate_tiers", [])}
    audit_tier = tiers.get("exact_member_audit_candidates", {})
    allowed_classes = set(
        observation.get("licence_policy", {}).get("allowed_classes", [])
    )
    for source_id in audit_tier.get("source_ids", []):
        if by_source.get(source_id, {}).get("licence") not in allowed_classes:
            errors.append(f"audit candidate licence is not permissive: {source_id}")

    domains = plan.get("domain_capacity_observation", {})
    expected_domain_capacity = {
        "music_like_candidate_groups": sum(
            by_source[source_id]["conservative_available_group_count"]
            for source_id in (
                "slakh2100_redux",
                "guitarset_3371780",
                "tinysol_3685367",
            )
        ),
        "speech_candidate_groups": sum(
            by_source[source_id]["conservative_available_group_count"]
            for source_id in ("vctk_clean_56spk_2017", "lombard_grid_3736465")
        ),
        "natural_soundscape_candidate_groups": sum(
            by_source[source_id]["conservative_available_group_count"]
            for source_id in (
                "sonyc_backgrounds_5129078",
                "satp_soundscapes_10159673",
            )
        ),
    }
    for key, expected in expected_domain_capacity.items():
        if domains.get(key) != expected:
            errors.append(f"domain capacity differs: {key}")
    if domains.get("mastered_multigenre_real_music_candidate_groups") != 0:
        errors.append("mastered multi-genre capacity was prematurely claimed")
    for key in (
        "synthetic_music_substitutes_for_real_mastered_music_transfer",
        "isolated_notes_substitute_for_mastered_music",
        "binaural_soundscapes_generalize_to_declared_loudspeakers",
    ):
        if domains.get(key) is not False:
            errors.append(f"domain claim boundary must remain false: {key}")

    limits = observation.get("observation_limits", {})
    for key in (
        "available_group_counts_are_qualified_reference_groups",
        "available_group_counts_are_partition_allocations",
        "available_group_counts_prove_provider_independence",
        "pcm_or_lossless_container_proves_never_lossy_history",
        "metadata_observation_authorizes_acquisition",
    ):
        if limits.get(key) is not False:
            errors.append(f"metadata observation limit must remain false: {key}")

    decision = plan.get("decision", {})
    audit_capacity = int(audit_tier.get("available_group_count", 0))
    if audit_capacity <= partitions.get("minimum_unique_source_groups_across_four_partitions", 0):
        errors.append("audit-candidate capacity does not exceed the four-partition floor")
    if audit_capacity <= partitions.get(
        "reference_sensitivity_unique_source_groups_across_four_partitions", 0
    ):
        errors.append("audit-candidate capacity does not exceed reference sensitivity")
    for key in (
        "public_metadata_exposes_raw_group_capacity_above_156",
        "public_metadata_exposes_raw_group_capacity_above_480",
    ):
        if decision.get(key) is not True:
            errors.append(f"raw capacity finding differs: {key}")
    for key in (
        "raw_capacity_proves_four_partition_feasibility",
        "exact_member_manifest_frozen",
        "source_manifest_frozen",
        "provider_holdout_manifest_frozen",
        "domain_allocation_frozen",
        "original_coding_history_qualified",
        "attribution_bundle_frozen",
        "resource_feasibility_complete",
        "listener_count_frozen",
        "human_collection_authorized",
        "no_reference_work_eligible",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision was prematurely closed: {key}")

    claims = plan.get("claim_boundary", {})
    for key in (
        "metadata_capacity_is_listening_truth",
        "available_group_is_independent_human_truth_group",
        "one_large_provider_proves_provider_transfer",
        "source_count_repairs_missing_domain_or_provider_independence",
        "current_candidate_pool_supports_mastered_music_claim",
        "current_candidate_pool_authorizes_audio_access",
        "public_cli_changed",
    ):
        if claims.get(key) is not False:
            errors.append(f"claim boundary must remain false: {key}")
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
