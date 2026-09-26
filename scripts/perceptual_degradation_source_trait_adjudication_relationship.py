#!/usr/bin/env python3
"""Audit source-trait adjudication and relationship readiness without audio."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1"
    / "source-trait-adjudication-relationship-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence"
    / "perceptual-degradation-source-trait-adjudication-relationship-20260818-001.json"
)
PLAN_ID = "perceptual-degradation-source-trait-adjudication-relationship-20260818-001"
REPORT_ID = PLAN_ID

EXPECTED_BINDINGS = {
    "exact_member_confirmation_plan",
    "exact_member_confirmation_report",
    "exact_member_confirmation_validator",
    "quiet_metadata_report",
    "source_trait_identifiability_plan",
    "source_trait_identifiability_report",
    "tinysol_path_free_observation",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load bound implementation: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bound(plan: dict[str, Any], binding_id: str, root: Path = ROOT) -> Path:
    return root / plan["bindings"][binding_id]["path"]


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "post_observation_score_blind_adjudication_and_relationship_policy_frozen_without_new_audio_access"
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
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")
    authorization = plan.get("authorization", {})
    if authorization.get("bound_committed_metadata_read_authorized") is not True:
        errors.append("committed metadata read must remain authorized")
    for key, value in authorization.items():
        if key != "bound_committed_metadata_read_authorized" and value is not False:
            errors.append(f"authorization must remain false: {key}")
    policy = plan.get("policy", {})
    required_true = {
        "clipped_pre_access_support_predicate_may_be_reconciled",
        "descriptor_observation_counts_as_provenance",
        "exact_member_assignment_requires_separate_authorization",
        "later_threshold_may_be_retrofit_to_observed_descriptor",
        "metadata_only_sparse_or_tonal_label_allowed",
        "new_quiet_threshold_requires_fresh_score_blind_candidate_or_independent_protocol",
        "partition_allocation_requires_all_trait_and_relationship_gates",
        "sparse_and_tonal_descriptor_rules_must_be_frozen_before_member_audio_access",
        "sparse_and_tonal_independent_contrasts_require_distinct_exact_members",
        "trait_assignment_requires_all_bound_proof_obligations",
    }
    for key in required_true:
        expected = key not in {
            "descriptor_observation_counts_as_provenance",
            "later_threshold_may_be_retrofit_to_observed_descriptor",
            "metadata_only_sparse_or_tonal_label_allowed",
        }
        if policy.get(key) is not expected:
            errors.append(f"policy differs: {key}")
    if policy.get("current_quiet_observation_may_be_relabelled_by_new_numeric_cutoff") is not False:
        errors.append("current quiet observation must not be relabelled post hoc")
    relationships = plan.get("relationship_rules", {})
    if relationships.get("tinysol_partition_group_count") != 1:
        errors.append("TinySOL partition group count differs")
    for key in (
        "exact_member_is_smallest_trait_assignment_unit",
        "provider_identity_does_not_establish_source_independence",
        "related_members_must_be_colocated_in_one_partition",
        "sparse_and_tonal_contrast_members_must_use_distinct_source_groups",
        "tinysol_rows_may_define_distinct_source_groups_only_after_exact_member_selection",
    ):
        if relationships.get(key) is not True:
            errors.append(f"relationship rule differs: {key}")
    if plan.get("resources") != {
        "maximum_workers": 1,
        "minimum_free_disk_gib": 15,
        "new_audio_download_bytes": 0,
        "retain_generated_audio": False,
    }:
        errors.append("resource boundary differs")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    publication = plan.get("publication_boundary", {})
    if not publication or any(value is not False for value in publication.values()):
        errors.append("publication boundary must remain false")
    serialized = json.dumps(plan, sort_keys=True)
    if "/Users/" in serialized or "Application Support" in serialized:
        errors.append("plan exposes a private path")
    return sorted(set(errors))


def build_report(
    plan: dict[str, Any], plan_path: Path = PLAN_PATH
) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))

    identifiability_plan = load_json(_bound(plan, "source_trait_identifiability_plan"))
    identifiability_report = load_json(_bound(plan, "source_trait_identifiability_report"))
    quiet_metadata = load_json(_bound(plan, "quiet_metadata_report"))
    tinysol = load_json(_bound(plan, "tinysol_path_free_observation"))
    confirmation_plan = load_json(_bound(plan, "exact_member_confirmation_plan"))
    confirmation = load_json(_bound(plan, "exact_member_confirmation_report"))
    validator = _load_module(
        _bound(plan, "exact_member_confirmation_validator"),
        "exact_member_confirmation_validator",
    )
    confirmation_errors = validator.validate_report(confirmation, confirmation_plan)
    if confirmation_errors:
        raise ValueError(
            "bound exact-member confirmation no longer validates: "
            + "; ".join(confirmation_errors)
        )

    required_traits = identifiability_plan["qualification_policy"]["required_trait_ids"]
    if len(required_traits) != 7:
        raise ValueError("required trait inventory differs")
    if identifiability_report["claim_boundary"][
        "shared_sparse_tonal_candidate_establishes_independent_contrasts"
    ]:
        raise ValueError("identifiability report unexpectedly resolves overlap")
    if quiet_metadata["quiet_audit"]["relationship_boundary"][
        "related_member_is_independent_contrast"
    ]:
        raise ValueError("quiet related-member boundary differs")
    tinysol_boundary = tinysol["conservative_reference_boundary"]
    if tinysol_boundary["eligible_group_count"] != 1:
        raise ValueError("TinySOL conservative partition grouping differs")

    quiet = confirmation["descriptor_observations"]["quiet"]
    clipped = confirmation["descriptor_observations"]["clipped"]
    if quiet["quiet_classification_threshold_applied"]:
        raise ValueError("quiet threshold was unexpectedly applied")
    if not clipped["plateau_or_saturation_support_event_present"]:
        raise ValueError("frozen clipped support predicate was not observed")

    report: dict[str, Any] = {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "adjudication_and_relationship_readiness_audited_no_trait_or_manifest_promotion",
        "observed_on": "2026-08-18",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "access_boundary": {
            "bound_committed_metadata_read": True,
            "new_audio_samples_read": False,
            "new_exact_members_selected": False,
            "audio_descriptors_computed": False,
            "provider_scores_or_processed_conditions_accessed": False,
            "perceptual_metrics_executed": False,
            "playback_performed": False,
            "listener_responses_collected": False,
            "sealed_evidence_opened": False,
            "source_traits_assigned": False,
            "source_manifest_allocated": False,
            "public_verdict_enabled": False,
        },
        "adjudication": {
            "quiet": {
                "metadata_provenance_obligation_satisfied": True,
                "absolute_level_observed": True,
                "nonzero_activity_observed": True,
                "classification_rule_frozen_before_observation": False,
                "new_numeric_cutoff_applied": False,
                "trait_assigned": False,
                "disposition": "development_descriptor_observation_not_eligible_for_post_hoc_numeric_relabelling",
            },
            "clipped": {
                "metadata_provenance_obligation_satisfied": True,
                "intentional_waveform_exclusion_satisfied_by_pre_audio_record": True,
                "technical_support_predicate_frozen_before_observation": True,
                "technical_support_event_observed": True,
                "partition_support_frozen": False,
                "trait_assigned": False,
                "disposition": "descriptor_and_provenance_ready_assignment_and_partition_support_not_authorized",
            },
            "sparse": {
                "provider_candidate_record_present": True,
                "exact_member_selected": False,
                "time_occupancy_rule_frozen": False,
                "descriptor_observed": False,
                "non_tonal_contrast_established": False,
                "trait_assigned": False,
                "disposition": "metadata_only_candidate_not_adjudicable",
            },
            "tonal": {
                "provider_candidate_record_present": True,
                "exact_member_selected": False,
                "spectral_concentration_rule_frozen": False,
                "descriptor_observed": False,
                "non_sparse_contrast_established": False,
                "trait_assigned": False,
                "disposition": "metadata_only_candidate_not_adjudicable",
            },
        },
        "relationship_audit": {
            "quiet_related_upload_is_independent": False,
            "quiet_grouping_rule_retained": plan["relationship_rules"][
                "quiet_related_upload_grouping"
            ],
            "tinysol_eligible_exact_member_candidate_count": tinysol_boundary[
                "eligible_audio_file_count"
            ],
            "tinysol_conservative_partition_group_count": tinysol_boundary[
                "eligible_group_count"
            ],
            "tinysol_provider_or_partition_independence_established": False,
            "distinct_sparse_and_tonal_exact_members_required": True,
            "distinct_sparse_and_tonal_source_groups_required": True,
            "independent_sparse_and_tonal_contrasts_established": False,
            "relationship_audit_complete_for_selected_seven_trait_manifest": False,
        },
        "summary": {
            "required_source_trait_count": len(required_traits),
            "quiet_descriptor_observed_trait_unassigned": True,
            "clipped_descriptor_and_provenance_ready_trait_unassigned": True,
            "independent_sparse_and_tonal_contrasts_established": False,
            "new_audio_accessed": False,
            "new_exact_member_selected": False,
            "source_trait_assignment_performed": False,
            "source_trait_manifest_frozen": False,
            "partition_allocation_performed": False,
            "objective_completion_count_changed": False,
            "public_verdict_enabled": False,
        },
        "decision": {
            "quiet_post_hoc_threshold_route_rejected": True,
            "clipped_evidence_ready_for_separately_authorized_assignment_gate": True,
            "tinysol_metadata_alone_establishes_sparse_tonal_contrasts": False,
            "sparse_tonal_exact_member_audio_access_authorized": False,
            "source_trait_manifest_freezable_now": False,
            "partition_allocation_authorized": False,
            "next_gate": (
                "Before any additional source audio is read, freeze deterministic sparse "
                "time-occupancy and tonal spectral-concentration implementations, thresholds, "
                "non-overlap rules and a bounded exact-member selection procedure. Then seek "
                "separate authorization for only the nominated exact members. A future quiet "
                "route must use a fresh score-blind candidate or an independently justified "
                "protocol; the observed quiet descriptor may not receive a new post-hoc cutoff."
            ),
            "public_verdict_enabled": False,
        },
        "claim_boundary": {
            "descriptor_observation_is_perceptual_truth": False,
            "clipped_readiness_is_trait_assignment": False,
            "tinysol_capacity_is_independent_contrast": False,
            "relationship_readiness_is_partition_allocation": False,
            "source_trait_scientific_coverage_complete": False,
            "full_objective_complete": False,
            "public_cli_changed": False,
            "public_verdict_enabled": False,
        },
    }
    return report


def validate_report(
    report: dict[str, Any], plan: dict[str, Any] | None = None
) -> list[str]:
    plan = plan or load_json(PLAN_PATH)
    errors = validate_plan(plan)
    try:
        expected = build_report(plan)
    except ValueError as exc:
        return sorted(set(errors + [str(exc)]))
    if report != expected:
        errors.append("report differs from deterministic replay")
    serialized = json.dumps(report, sort_keys=True)
    for forbidden in (
        "/Users/",
        "Application Support",
        "encoded_sha256",
        "pcm_sha256",
        "provider-originals",
        "relative_path",
    ):
        if forbidden in serialized:
            errors.append(f"public report exposes forbidden material: {forbidden}")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    plan = load_json(args.plan)
    report = build_report(plan, args.plan)
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != canonical_json_bytes(report):
            print("ERROR: committed report differs from deterministic replay")
            return 1
        errors = validate_report(load_json(args.output), plan)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"validated {REPORT_ID}")
        return 0
    args.output.write_bytes(canonical_json_bytes(report))
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
