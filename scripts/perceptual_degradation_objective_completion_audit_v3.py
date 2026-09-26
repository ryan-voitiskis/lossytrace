#!/usr/bin/env python3
"""Refresh the objective audit for source traits and drift correction."""

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
    / "benchmarks/perceptual-degradation-v1/"
    "objective-completion-audit-plan-20260814-003.json"
)
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260814-003"
REPORT_ID = "perceptual-degradation-objective-completion-audit-20260814-003"

AUTHORIZATION = {
    "bound_metadata_and_source_read_authorized": True,
    "synthetic_audit_execution_authorized": True,
    "immutable_record_preservation_authorized": False,
    "exact_member_metadata_audit_authorized": False,
    "exact_member_selection_authorized": False,
    "source_trait_assignment_authorized": False,
    "provider_catalog_query_authorized": False,
    "new_audio_acquisition_authorized": False,
    "retained_odaq_reference_read_authorized": False,
    "retained_reference_projection_authorized": False,
    "drift_resampler_integration_authorized": False,
    "stimulus_generation_authorized": False,
    "processed_condition_access_authorized": False,
    "listening_score_access_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "human_collection_authorized": False,
    "recruitment_authorized": False,
    "sealed_evidence_access_authorized": False,
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
    "provider_capability_counts_as_exact_trait_candidate": False,
    "missing_natural_trait_candidate_counts_as_negative_coverage": False,
    "frozen_resampler_counts_as_oracle_integration": False,
    "legacy_metric_rate_conversion_counts_as_drift_integration": False,
    "preparation_or_synthetic_replay_counts_as_scientific_completion": False,
    "green_tests_count_as_perceptual_evidence": False,
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
    "oracle_drift_resampler_freeze",
    "oracle_drift_resampler_report",
    "source_trait_plan",
    "source_trait_report",
    "source_trait_provider_screen",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "score_blind_completion_audit_refreshed_for_source_traits_and_drift_no_new_authority"
    ):
        errors.append("plan state differs")
    if set(plan.get("bindings", {})) != EXPECTED_BINDINGS:
        errors.append("binding inventory differs")
    for binding_id, binding in plan.get("bindings", {}).items():
        path = root / str(binding.get("path", ""))
        if not path.is_file():
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
    return sorted(set(errors))


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def _load_predecessor_module(plan: dict[str, Any]) -> ModuleType:
    path = _bound(plan, "predecessor_audit_implementation")
    spec = importlib.util.spec_from_file_location("objective_audit_v2", path)
    if spec is None or spec.loader is None:
        raise ValueError("could not load predecessor audit implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _requirement_index(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["requirement_id"]: item for item in report["requirements"]}


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))

    predecessor_plan_path = _bound(plan, "predecessor_audit_plan")
    predecessor = _load_predecessor_module(plan)
    predecessor_report = predecessor.build_report(
        predecessor.load_json(predecessor_plan_path), predecessor_plan_path
    )
    expected_predecessor_sha256 = plan["bindings"]["predecessor_audit_report"][
        "sha256"
    ]
    if hashlib.sha256(canonical_json_bytes(predecessor_report)).hexdigest() != (
        expected_predecessor_sha256
    ):
        raise ValueError("replayed predecessor report differs from bound report")

    report = json.loads(json.dumps(predecessor_report))
    source_trait_plan = load_json(_bound(plan, "source_trait_plan"))
    source_trait = load_json(_bound(plan, "source_trait_report"))
    provider_screen = load_json(_bound(plan, "source_trait_provider_screen"))
    resampler_freeze = load_json(_bound(plan, "oracle_drift_resampler_freeze"))
    resampler = load_json(_bound(plan, "oracle_drift_resampler_report"))

    traits = source_trait.get("summary", {})
    trait_decision = source_trait.get("decision", {})
    provider_decision = provider_screen.get("decision", {})
    resampler_summary = resampler.get("summary", {})
    resampler_decision = resampler.get("decision", {})

    required_trait_count = traits.get("required_source_trait_count")
    candidate_record_count = traits.get("explicit_candidate_record_count")
    quiet_route_found = provider_decision.get("quiet_provider_capability_route_found") is True
    quiet_candidate = provider_decision.get("quiet_candidate_identified") is True
    clipped_candidate = (
        provider_decision.get("naturally_clipped_candidate_identified") is True
    )
    source_trait_manifest_frozen = (
        trait_decision.get("exact_source_trait_members_frozen") is True
        and trait_decision.get("source_trait_scientific_coverage_complete") is True
        and provider_decision.get("source_trait_manifest_frozen") is True
    )

    resampler_selected = (
        resampler_decision.get("candidate_selected_as_frozen_oracle_resampler")
        is True
        and resampler_summary.get("all_predeclared_gates_pass") is True
    )
    resampler_integrated = (
        resampler_decision.get("retained_audio_correction_executed") is True
        and resampler_decision.get("retained_audio_correction_validated") is True
    )

    requirements = _requirement_index(report)
    source = requirements["truth_bearing_source_manifest_feasible_and_frozen"]
    source.update(
        {
            "state": "arithmetic_feasible_trait_candidates_incomplete_exact_manifest_unfrozen",
            "satisfied": source["satisfied"] and source_trait_manifest_frozen,
            "evidence": [
                "predecessor_audit.requirements.truth_bearing_source_manifest",
                "source_trait_report.summary",
                "source_trait_provider_screen.trait_disposition",
            ],
            "reason": (
                "Provider-pure source arithmetic is feasible, but the seven-trait "
                "proof contract has only five candidate records. Quiet has a "
                "provider-level audit route but no exact candidate, naturally "
                "clipped has no candidate, and exact members, provenance, "
                "relationships, selection and allocation remain unfrozen."
            ),
            "next_gate": provider_decision.get("next_gate"),
        }
    )

    oracle = requirements[
        "deterministic_human_calibrated_full_reference_oracle_passed"
    ]
    oracle.update(
        {
            "state": "technical_resampler_frozen_integration_and_scientific_validation_closed",
            "satisfied": oracle["satisfied"] and resampler_integrated,
            "evidence": [
                "predecessor_audit.requirements.full_reference_oracle",
                "oracle_drift_resampler_report.summary",
                "oracle_drift_resampler_report.decision",
            ],
            "reason": (
                "The score-free envelope and grouped statistics are deterministic, "
                "and the bounded-drift resampler passed all nine synthetic gates. "
                "It has not been integrated after a held-out drift decision or "
                "validated on retained development pairs; the older 44.1-to-48 "
                "kHz metric-rate view is not drift correction. No human-calibrated "
                "scientific gate has been evaluated."
            ),
            "next_gate": resampler_decision.get("next_gate"),
        }
    )

    negatives = requirements[
        "difficult_natural_and_production_negatives_preserved_in_evaluation"
    ]
    negatives.update(
        {
            "state": "proof_contract_ready_candidate_coverage_incomplete_not_evaluated",
            "satisfied": negatives["satisfied"] and source_trait_manifest_frozen,
            "evidence": [
                "predecessor_audit.requirements.difficult_negatives",
                "source_trait_plan.trait_proof_obligations",
                "source_trait_report.decision",
            ],
            "reason": (
                "All twenty negative classes remain required and the seven natural "
                "source-trait proof obligations are frozen. Quiet and naturally "
                "clipped candidates are still absent, sparse and tonal require "
                "independent contrasts, and no negative class has entered "
                "scientific evaluation."
            ),
            "next_gate": trait_decision.get("next_gate"),
        }
    )

    if [item["requirement_id"] for item in report["requirements"]] != REQUIREMENTS:
        raise ValueError("refreshed requirement order differs from frozen inventory")
    complete = all(item["satisfied"] for item in report["requirements"])
    if complete:
        raise ValueError("current bound evidence unexpectedly satisfies the objective")
    satisfied_count = sum(item["satisfied"] for item in report["requirements"])

    report.update(
        {
            "report_id": REPORT_ID,
            "state": "objective_incomplete_latest_source_trait_and_oracle_evidence_reconciled",
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
            "required_source_trait_count": required_trait_count,
            "source_trait_candidate_record_count": candidate_record_count,
            "quiet_provider_capability_route_found": quiet_route_found,
            "quiet_candidate_identified": quiet_candidate,
            "naturally_clipped_candidate_identified": clipped_candidate,
            "source_trait_manifest_frozen": source_trait_manifest_frozen,
            "oracle_drift_resampler_selected": resampler_selected,
            "oracle_drift_resampler_integrated": resampler_integrated,
            "nearest_authority_dependent_decisions": [
                provider_decision.get("next_gate"),
                report["requirements"][4].get("next_gate"),
                resampler_decision.get("next_gate"),
            ],
        }
    )
    report["evidence_checks"].update(
        {
            "required_source_trait_count": required_trait_count,
            "source_trait_candidate_record_count": candidate_record_count,
            "quiet_provider_capability_route_found": quiet_route_found,
            "quiet_exact_candidate_identified": quiet_candidate,
            "naturally_clipped_exact_candidate_identified": clipped_candidate,
            "source_trait_manifest_frozen": source_trait_manifest_frozen,
            "oracle_drift_resampler_selected": resampler_selected,
            "oracle_drift_resampler_all_synthetic_gates_pass": (
                resampler_summary.get("all_predeclared_gates_pass") is True
            ),
            "oracle_drift_resampler_integration_authorized": plan[
                "authorization"
            ]["drift_resampler_integration_authorized"],
            "oracle_drift_resampler_integrated": resampler_integrated,
            "legacy_metric_rate_conversion_is_drift_integration": False,
        }
    )
    return report


def write_report(report: dict[str, Any], output: Path) -> None:
    output.write_bytes(canonical_json_bytes(report))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(load_json(args.plan), args.plan)
    write_report(report, args.output)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
