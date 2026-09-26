#!/usr/bin/env python3
"""Refresh the objective audit after exact-member source-trait metadata work."""

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
    / "objective-completion-audit-plan-20260817-009.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence"
    / "perceptual-degradation-objective-completion-audit-20260817-009.json"
)
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260817-009"
REPORT_ID = PLAN_ID

AUTHORIZATION = {
    "bound_metadata_and_source_read_authorized": True,
    "synthetic_audit_execution_authorized": True,
    "exact_member_metadata_audit_reconciliation_authorized": True,
    "public_and_provider_metadata_read_completed": True,
    "audio_sample_access_authorized": False,
    "audio_descriptor_computation_authorized": False,
    "provider_score_or_processed_condition_access_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "human_response_access_authorized": False,
    "human_collection_authorized": False,
    "sealed_evidence_access_authorized": False,
    "actual_codec_generation_authorized": False,
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
    "exact_metadata_candidate_counts_as_candidate_record": True,
    "exact_metadata_candidate_counts_as_trait_truth": False,
    "metadata_only_quiet_route_rejection_counts_as_quiet_coverage": False,
    "closed_descriptor_obligation_counts_as_satisfied": False,
    "candidate_without_partition_allocation_counts_as_frozen_manifest": False,
    "green_tests_count_as_scientific_evidence": False,
    "missing_or_indirect_evidence_counts_as_satisfied": False,
    "current_recommendation": None,
    "allowed_final_recommendations": [
        "reject_perceptual_estimation",
        "retain_full_reference_only",
        "continue_no_reference_research",
        "freeze_blind_final_validation",
    ],
}

EXPECTED_BINDINGS = {
    "predecessor_audit_plan",
    "predecessor_audit_implementation",
    "predecessor_audit_report",
    "source_trait_metadata_audit_plan",
    "source_trait_metadata_audit_report",
    "source_trait_metadata_audit_validator",
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
        "score_blind_completion_audit_refresh_for_exact_member_source_trait_metadata_result"
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


def _requirement_index(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["requirement_id"]: item for item in report["requirements"]}


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    predecessor = _load_module(
        _bound(plan, "predecessor_audit_implementation"), "objective_audit_v8"
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

    metadata_validator = _load_module(
        _bound(plan, "source_trait_metadata_audit_validator"),
        "source_trait_metadata_audit",
    )
    metadata_plan = load_json(_bound(plan, "source_trait_metadata_audit_plan"))
    metadata_report = load_json(_bound(plan, "source_trait_metadata_audit_report"))
    metadata_errors = metadata_validator.validate_plan(
        metadata_plan
    ) + metadata_validator.validate_report(metadata_report, metadata_plan)
    if metadata_errors:
        raise ValueError(
            "bound source-trait metadata audit no longer validates: "
            + "; ".join(sorted(set(metadata_errors)))
        )

    report = json.loads(json.dumps(predecessor_report))
    requirements = _requirement_index(report)
    source_manifest = requirements["truth_bearing_source_manifest_feasible_and_frozen"]
    source_manifest.update(
        {
            "state": "arithmetic_feasible_six_trait_candidate_records_quiet_missing_exact_manifest_unfrozen",
            "satisfied": False,
            "evidence": [
                "predecessor_audit.requirements.truth_bearing_source_manifest",
                "source_trait_metadata_audit.quiet_audit",
                "source_trait_metadata_audit.clipped_audit",
                "source_trait_metadata_audit.decision",
            ],
            "reason": (
                "The metadata-only exact-member audit identified one naturally clipped "
                "candidate that clears the frozen pre-audio rights, lossless-origin, "
                "capture-chain, transformation and intentional-waveform gates. The SONYC "
                "route was rejected for quiet identification because no exact-member level "
                "or gain-preservation metadata exists. Six of seven trait classes now have "
                "candidate records, but quiet, independent sparse and tonal contrasts, "
                "descriptor confirmation, relationships and partition allocation remain "
                "unfrozen."
            ),
            "next_gate": metadata_report["decision"]["next_gate"],
        }
    )
    difficult = requirements[
        "difficult_natural_and_production_negatives_preserved_in_evaluation"
    ]
    difficult.update(
        {
            "state": "proof_contract_ready_clipped_exact_metadata_candidate_identified_quiet_and_independent_contrasts_missing_not_evaluated",
            "satisfied": False,
            "evidence": [
                "predecessor_audit.requirements.difficult_negatives",
                "source_trait_metadata_audit.summary",
                "source_trait_metadata_audit.claim_boundary",
            ],
            "reason": (
                "The clipped class now has one exact metadata candidate, but no audio "
                "descriptor or trait assignment was authorized. Quiet remains without a "
                "candidate, sparse and tonal remain non-independent, and no natural or "
                "production negative has entered scientific evaluation."
            ),
            "next_gate": metadata_report["decision"]["next_gate"],
        }
    )
    if [item["requirement_id"] for item in report["requirements"]] != REQUIREMENTS:
        raise ValueError("refreshed requirement order differs from frozen inventory")
    satisfied_count = sum(item["satisfied"] for item in report["requirements"])
    complete = all(item["satisfied"] for item in report["requirements"])
    if complete or satisfied_count != 4:
        raise ValueError("metadata evidence unexpectedly promoted scientific completion")

    report.update(
        {
            "report_id": REPORT_ID,
            "state": "objective_incomplete_exact_clipped_metadata_candidate_reconciled_quiet_route_rejected_without_scientific_promotion",
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
            "source_trait_exact_member_metadata_audit_complete": True,
            "source_trait_required_count": 7,
            "source_trait_candidate_record_count": 6,
            "quiet_exact_candidate_identified": False,
            "quiet_metadata_only_route_rejected": True,
            "naturally_clipped_candidate_identified": True,
            "naturally_clipped_exact_metadata_candidate_identified": True,
            "naturally_clipped_trait_truth_established": False,
            "source_trait_audio_accessed_by_metadata_audit": False,
            "source_trait_audio_descriptor_computed": False,
            "source_trait_manifest_frozen": False,
            "nearest_authority_dependent_decisions": [
                metadata_report["decision"]["next_gate"],
                report["requirements"][4].get("next_gate"),
                report["requirements"][5].get("next_gate"),
            ],
        }
    )
    report["evidence_checks"].update(
        {
            "source_trait_exact_member_metadata_audit_authorized": True,
            "source_trait_exact_member_metadata_audit_complete": True,
            "source_trait_metadata_audit_audio_accessed": False,
            "source_trait_metadata_audit_descriptor_computed": False,
            "quiet_metadata_only_route_rejected": True,
            "source_trait_candidate_record_count": 6,
            "naturally_clipped_exact_candidate_identified": True,
            "clipped_exact_metadata_candidate_identified": True,
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
