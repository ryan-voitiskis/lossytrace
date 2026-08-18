#!/usr/bin/env python3
"""Refresh the objective audit after adjudication and relationship readiness."""

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
    / "objective-completion-audit-plan-20260818-012.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence"
    / "perceptual-degradation-objective-completion-audit-20260818-012.json"
)
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260818-012"
REPORT_ID = PLAN_ID

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

EXPECTED_BINDINGS = {
    "adjudication_relationship_implementation",
    "adjudication_relationship_plan",
    "adjudication_relationship_report",
    "predecessor_audit_implementation",
    "predecessor_audit_plan",
    "predecessor_audit_report",
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


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "score_blind_completion_audit_refresh_after_adjudication_and_relationship_readiness"
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
    for key in (
        "bound_committed_evidence_read_authorized",
        "post_observation_policy_reconciliation_authorized",
        "synthetic_audit_execution_authorized",
    ):
        if authorization.get(key) is not True:
            errors.append(f"authorization differs: {key}")
    for key, value in authorization.items():
        if key not in {
            "bound_committed_evidence_read_authorized",
            "post_observation_policy_reconciliation_authorized",
            "synthetic_audit_execution_authorized",
        } and value is not False:
            errors.append(f"authorization must remain false: {key}")
    if plan.get("requirement_ids") != REQUIREMENTS:
        errors.append("objective requirement inventory differs")
    policy = plan.get("completion_policy", {})
    for key in (
        "all_completion_required_requirements_must_be_satisfied",
        "all_requirement_ids_must_be_present",
        "source_trait_manifest_requires_separately_authorized_assignments_and_allocation",
    ):
        if policy.get(key) is not True:
            errors.append(f"completion policy differs: {key}")
    for key in (
        "adjudication_policy_counts_as_trait_assignment",
        "clipped_descriptor_and_provenance_readiness_counts_as_trait_assignment",
        "current_quiet_observation_may_receive_post_hoc_numeric_cutoff",
        "metadata_capacity_counts_as_independent_sparse_tonal_contrasts",
        "relationship_policy_counts_as_partition_allocation",
    ):
        if policy.get(key) is not False:
            errors.append(f"completion policy differs: {key}")
    if policy.get("current_recommendation") is not None:
        errors.append("current recommendation must remain null")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    serialized = json.dumps(plan, sort_keys=True)
    if "/Users/" in serialized or "Application Support" in serialized:
        errors.append("plan exposes a private path")
    return sorted(set(errors))


def _requirements(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["requirement_id"]: row for row in report["requirements"]}


def build_report(
    plan: dict[str, Any], plan_path: Path = PLAN_PATH
) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))

    predecessor = _load_module(
        _bound(plan, "predecessor_audit_implementation"), "objective_audit_v11"
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

    readiness = _load_module(
        _bound(plan, "adjudication_relationship_implementation"),
        "adjudication_relationship",
    )
    readiness_plan = readiness.load_json(_bound(plan, "adjudication_relationship_plan"))
    readiness_report = readiness.load_json(
        _bound(plan, "adjudication_relationship_report")
    )
    readiness_errors = readiness.validate_report(readiness_report, readiness_plan)
    if readiness_errors:
        raise ValueError(
            "bound adjudication and relationship report no longer validates: "
            + "; ".join(readiness_errors)
        )

    report = json.loads(json.dumps(predecessor_report))
    requirements = _requirements(report)
    next_gate = readiness_report["decision"]["next_gate"]
    requirements["truth_bearing_source_manifest_feasible_and_frozen"].update(
        {
            "state": "adjudication_and_relationship_policy_frozen_quiet_post_hoc_route_rejected_clipped_ready_sparse_tonal_and_allocation_unfrozen",
            "satisfied": False,
            "evidence": [
                "predecessor_audit.requirements.truth_bearing_source_manifest",
                "adjudication_relationship.adjudication",
                "adjudication_relationship.relationship_audit",
                "adjudication_relationship.decision",
                "adjudication_relationship.claim_boundary",
            ],
            "reason": (
                "The adjudication and relationship policy now prevents a post-hoc quiet "
                "cutoff and reconciles the clipped candidate's pre-access provenance and "
                "technical support predicate without assigning a trait. TinySOL metadata "
                "exposes 2,273 eligible candidates but only one conservative partition group; "
                "no sparse non-tonal or tonal non-sparse exact-member contrast is established. "
                "No source trait was assigned and no manifest or partition was allocated."
            ),
            "next_gate": next_gate,
        }
    )
    requirements[
        "difficult_natural_and_production_negatives_preserved_in_evaluation"
    ].update(
        {
            "state": "clipped_assignment_ready_quiet_requires_fresh_protocol_sparse_tonal_contrasts_and_evaluation_missing",
            "satisfied": False,
            "evidence": [
                "predecessor_audit.requirements.difficult_negatives",
                "adjudication_relationship.adjudication",
                "adjudication_relationship.relationship_audit",
                "adjudication_relationship.claim_boundary",
            ],
            "reason": (
                "The clipped exact member is ready for a separately authorized assignment "
                "gate, while the current quiet observation cannot be relabelled with a newly "
                "chosen cutoff. Sparse and tonal independent contrasts remain absent, and no "
                "natural or production negative has been allocated to evaluation."
            ),
            "next_gate": next_gate,
        }
    )
    if [row["requirement_id"] for row in report["requirements"]] != REQUIREMENTS:
        raise ValueError("refreshed requirement order differs")
    satisfied_count = sum(row["satisfied"] for row in report["requirements"])
    complete = all(row["satisfied"] for row in report["requirements"])
    if complete or satisfied_count != 4:
        raise ValueError("readiness evidence unexpectedly promoted scientific completion")

    report.update(
        {
            "report_id": REPORT_ID,
            "state": "objective_incomplete_adjudication_and_relationship_readiness_reconciled_without_trait_or_scientific_promotion",
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
            "source_trait_adjudication_relationship_audit_complete": True,
            "quiet_post_hoc_threshold_route_rejected": True,
            "quiet_trait_truth_established": False,
            "clipped_descriptor_and_provenance_assignment_ready": True,
            "naturally_clipped_trait_truth_established": False,
            "tinysol_eligible_exact_member_candidate_count": 2273,
            "tinysol_conservative_partition_group_count": 1,
            "independent_sparse_and_tonal_contrasts_established": False,
            "source_trait_manifest_frozen": False,
            "source_manifest_frozen": False,
            "nearest_authority_dependent_decisions": [
                next_gate,
                report["requirements"][4].get("next_gate"),
                report["requirements"][5].get("next_gate"),
            ],
        }
    )
    report["evidence_checks"].update(
        {
            "source_trait_adjudication_relationship_audit_complete": True,
            "quiet_post_hoc_threshold_route_rejected": True,
            "quiet_trait_truth_established": False,
            "clipped_descriptor_and_provenance_assignment_ready": True,
            "clipped_trait_truth_established": False,
            "tinysol_eligible_exact_member_candidate_count": 2273,
            "tinysol_conservative_partition_group_count": 1,
            "independent_sparse_and_tonal_contrasts_established": False,
            "new_source_audio_accessed": False,
            "new_exact_member_selected": False,
            "source_trait_assignment_performed": False,
            "source_manifest_allocation_performed": False,
            "source_trait_manifest_frozen": False,
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report(load_json(args.plan), args.plan)
    payload = canonical_json_bytes(report)
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != payload:
            print("ERROR: committed report differs from deterministic replay")
            return 1
        print(f"validated {REPORT_ID}")
        return 0
    args.output.write_bytes(payload)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
