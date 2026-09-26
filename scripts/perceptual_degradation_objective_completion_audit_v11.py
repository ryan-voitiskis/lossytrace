#!/usr/bin/env python3
"""Refresh the objective audit after exact-member descriptor confirmation."""

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
    / "objective-completion-audit-plan-20260818-011.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence"
    / "perceptual-degradation-objective-completion-audit-20260818-011.json"
)
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260818-011"
REPORT_ID = PLAN_ID

AUTHORIZATION = {
    "bound_committed_evidence_read_authorized": True,
    "synthetic_audit_execution_authorized": True,
    "exact_member_confirmation_reconciliation_authorized": True,
    "two_exact_provider_originals_audio_access_completed": True,
    "frozen_integer_pcm_descriptor_execution_completed": True,
    "further_audio_sample_access_authorized": False,
    "provider_score_or_processed_condition_access_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "human_response_access_authorized": False,
    "human_collection_authorized": False,
    "sealed_evidence_access_authorized": False,
    "actual_codec_generation_authorized": False,
    "source_trait_assignment_authorized": False,
    "source_manifest_allocation_authorized": False,
    "no_reference_training_authorized": False,
    "public_verdict_enabled": False,
}

REQUIREMENTS = [
    "estimand_is_degradation_not_history",
    "declared_playback_chain_qualified",
    "truth_bearing_source_manifest_feasible_and_frozen",
    "controlled_human_calibration_collected",
    "perceptual_metric_execution_and_legal_gate_passed",
    "deterministic_human_calibrated_full_reference_oracle_passed",
    "transparent_lossy_treated_as_non_degraded",
    "difficult_natural_and_production_negatives_preserved_in_evaluation",
    "grouped_source_domain_codec_encoder_transfer_passed",
    "no_reference_estimator_trained_and_independently_validated",
    "severity_audibility_artifact_support_uncertainty_abstention_reported",
    "public_cli_remains_verdict_free",
    "rigorous_negative_is_accepted_success",
    "final_research_recommendation_frozen",
]

POLICY = {
    "all_requirement_ids_must_be_present": True,
    "all_completion_required_requirements_must_be_satisfied": True,
    "two_exact_provider_originals_count_as_acquired_candidates": True,
    "frozen_descriptor_execution_counts_as_obligation_observed": True,
    "descriptor_observation_counts_as_trait_truth": False,
    "quiet_level_without_predeclared_classification_counts_as_trait_truth": False,
    "plateau_or_saturation_event_counts_as_clipping_provenance": False,
    "metadata_plus_descriptor_counts_as_trait_assignment": False,
    "seven_candidate_records_count_as_frozen_manifest": False,
    "shared_sparse_tonal_candidate_counts_as_independent_contrasts": False,
    "candidate_without_partition_allocation_counts_as_frozen_manifest": False,
    "green_tests_count_as_scientific_evidence": False,
    "current_recommendation": None,
}

EXPECTED_BINDINGS = {
    "predecessor_audit_plan",
    "predecessor_audit_implementation",
    "predecessor_audit_report",
    "exact_member_confirmation_plan",
    "exact_member_confirmation_report",
    "exact_member_confirmation_validator",
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


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "score_blind_completion_audit_refresh_after_two_exact_member_descriptor_replays"
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
    if plan.get("authorization") != AUTHORIZATION:
        errors.append("authorization boundary differs")
    if plan.get("requirement_ids") != REQUIREMENTS:
        errors.append("objective requirement inventory differs")
    if plan.get("completion_policy") != POLICY:
        errors.append("completion policy differs")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    serialized = json.dumps(plan, sort_keys=True)
    if "/Users/" in serialized or "Application Support" in serialized:
        errors.append("plan exposes a private path")
    return sorted(set(errors))


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def _requirements(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["requirement_id"]: row for row in report["requirements"]}


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    predecessor = _load_module(
        _bound(plan, "predecessor_audit_implementation"), "objective_audit_v10"
    )
    predecessor_plan_path = _bound(plan, "predecessor_audit_plan")
    predecessor_report = predecessor.build_report(
        predecessor.load_json(predecessor_plan_path), predecessor_plan_path
    )
    predecessor_report_path = _bound(plan, "predecessor_audit_report")
    if (
        sha256_file(predecessor_report_path)
        != plan["bindings"]["predecessor_audit_report"]["sha256"]
        or canonical_json_bytes(predecessor_report) != predecessor_report_path.read_bytes()
    ):
        raise ValueError("replayed predecessor report differs from bound report")

    validator = _load_module(
        _bound(plan, "exact_member_confirmation_validator"),
        "exact_member_confirmation_validator",
    )
    confirmation_plan = load_json(_bound(plan, "exact_member_confirmation_plan"))
    confirmation = load_json(_bound(plan, "exact_member_confirmation_report"))
    confirmation_errors = validator.validate_report(confirmation, confirmation_plan)
    if confirmation_errors:
        raise ValueError(
            "bound exact-member confirmation no longer validates: "
            + "; ".join(confirmation_errors)
        )

    report = json.loads(json.dumps(predecessor_report))
    requirements = _requirements(report)
    next_gate = (
        "Freeze a separate source-trait assignment and relationship policy without "
        "retrofitting a quiet threshold to these observations; obtain independent "
        "sparse and tonal exact-member contrasts, then audit relationships and partition "
        "allocation. This does not authorize further audio access or scientific evaluation."
    )
    requirements["truth_bearing_source_manifest_feasible_and_frozen"].update(
        {
            "state": "seven_trait_candidate_records_quiet_and_clipped_descriptors_observed_trait_assignment_independent_contrasts_relationships_and_allocation_unfrozen",
            "satisfied": False,
            "evidence": [
                "predecessor_audit.requirements.truth_bearing_source_manifest",
                "exact_member_confirmation.execution",
                "exact_member_confirmation.descriptor_observations",
                "exact_member_confirmation.decision",
                "exact_member_confirmation.claim_boundary",
            ],
            "reason": (
                "The two exact provider originals were acquired and the frozen score-free "
                "integer-PCM descriptor obligations replayed twice with byte-identical "
                "private reports. Quiet absolute level and nonzero activity are now observed, "
                "and the naturally clipped candidate has technical plateau or saturation "
                "support events. No quiet classification threshold or source-trait assignment "
                "was authorized, PCM events do not establish provenance, sparse and tonal "
                "remain non-independent, and relationships and partition allocation remain "
                "unfrozen."
            ),
            "next_gate": next_gate,
        }
    )
    requirements[
        "difficult_natural_and_production_negatives_preserved_in_evaluation"
    ].update(
        {
            "state": "quiet_and_clipped_exact_candidates_descriptor_observed_trait_assignment_independent_contrasts_and_evaluation_missing",
            "satisfied": False,
            "evidence": [
                "predecessor_audit.requirements.difficult_negatives",
                "exact_member_confirmation.descriptor_observations",
                "exact_member_confirmation.decision",
                "exact_member_confirmation.claim_boundary",
            ],
            "reason": (
                "Quiet and naturally clipped exact candidates now have their frozen technical "
                "descriptor observations, but neither was assigned as trait truth or entered "
                "scientific evaluation. Sparse and tonal remain non-independent, and no natural "
                "or production negative has been allocated to an evaluation partition."
            ),
            "next_gate": next_gate,
        }
    )
    if [row["requirement_id"] for row in report["requirements"]] != REQUIREMENTS:
        raise ValueError("refreshed requirement order differs")
    satisfied_count = sum(row["satisfied"] for row in report["requirements"])
    complete = all(row["satisfied"] for row in report["requirements"])
    if complete or satisfied_count != 4:
        raise ValueError("descriptor evidence unexpectedly promoted scientific completion")

    report.update(
        {
            "report_id": REPORT_ID,
            "state": "objective_incomplete_two_exact_member_descriptor_replays_reconciled_without_trait_or_scientific_promotion",
            "plan_id": plan["plan_id"],
            "plan_sha256": sha256_file(plan_path),
            "implementation_sha256": sha256_file(Path(__file__)),
        }
    )
    report["summary"].update(
        {
            "satisfied_count": satisfied_count,
            "unsatisfied_count": len(REQUIREMENTS) - satisfied_count,
            "objective_complete": complete,
            "source_trait_exact_member_confirmation_complete": True,
            "source_trait_exact_provider_original_count_acquired": 2,
            "source_trait_private_replay_count": 2,
            "source_trait_private_replays_byte_identical": True,
            "source_trait_audio_accessed_for_confirmation": True,
            "source_trait_descriptor_computed": True,
            "quiet_absolute_pcm_level_measured": True,
            "quiet_nonzero_activity_support_observed": True,
            "clipped_plateau_or_saturation_support_event_observed": True,
            "quiet_trait_truth_established": False,
            "naturally_clipped_trait_truth_established": False,
            "source_trait_manifest_frozen": False,
            "nearest_authority_dependent_decisions": [
                next_gate,
                report["requirements"][4].get("next_gate"),
                report["requirements"][5].get("next_gate"),
            ],
        }
    )
    report["evidence_checks"].update(
        {
            "source_trait_exact_member_confirmation_authorized": True,
            "source_trait_exact_member_confirmation_complete": True,
            "source_trait_exact_provider_original_count_acquired": 2,
            "source_trait_private_replay_count": 2,
            "source_trait_private_replays_byte_identical": True,
            "source_trait_confirmation_audio_accessed": True,
            "source_trait_confirmation_descriptor_computed": True,
            "quiet_absolute_pcm_level_measured": True,
            "quiet_nonzero_activity_support_observed": True,
            "clipped_plateau_or_saturation_support_event_observed": True,
            "quiet_trait_truth_established": False,
            "clipped_trait_truth_established": False,
            "source_trait_manifest_frozen": False,
        }
    )
    return report


def write_report(report: dict[str, Any], output: Path) -> None:
    output.write_bytes(canonical_json_bytes(report))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    report = build_report(load_json(args.plan), args.plan)
    write_report(report, args.output)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
