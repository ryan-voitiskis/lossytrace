#!/usr/bin/env python3
"""Refresh the full-objective audit from an immutable predecessor audit."""

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
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "objective-completion-audit-plan-20260814-002.json"
)
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260814-002"
REPORT_ID = "perceptual-degradation-objective-completion-audit-20260814-002"

AUTHORIZATION = {
    "bound_metadata_and_source_read_authorized": True,
    "synthetic_audit_execution_authorized": True,
    "immutable_record_preservation_authorized": False,
    "exact_member_metadata_audit_authorized": False,
    "exact_member_selection_authorized": False,
    "new_audio_acquisition_authorized": False,
    "retained_odaq_reference_read_authorized": False,
    "retained_reference_projection_authorized": False,
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
    "arithmetic_feasibility_counts_as_manifest_qualification": False,
    "preregisterable_metric_successor_counts_as_selection": False,
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
    "breadth_repair_plan",
    "breadth_repair_report",
    "metric_successor_disposition",
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
        "score_blind_completion_audit_refreshed_no_new_execution_authority"
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
    if set(plan.get("claim_boundary", {}).values()) != {False}:
        errors.append("claim boundary must remain false")
    return errors


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def _load_predecessor_module(plan: dict[str, Any]) -> ModuleType:
    path = _bound(plan, "predecessor_audit_implementation")
    spec = importlib.util.spec_from_file_location("objective_audit_predecessor", path)
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
    breadth_plan = load_json(_bound(plan, "breadth_repair_plan"))
    breadth = load_json(_bound(plan, "breadth_repair_report"))
    metric_successor = load_json(_bound(plan, "metric_successor_disposition"))
    breadth_decision = breadth.get("decision", {})
    successor_decision = metric_successor.get("decision", {})
    successor_readiness = metric_successor.get("readiness", {})

    arithmetic_keys = (
        "public_record_pool_clears_mastered_music_every_partition",
        "public_record_pool_clears_three_domains_every_partition",
        "public_record_pool_clears_two_mastered_providers_in_final",
        "recording_ceiling_clears_reference_120_each_partition",
        "conservative_relationship_floor_clears_reference_120_each_partition",
        "stable_record_pool_clears_mastered_music_every_partition",
        "stable_record_pool_clears_three_domains_every_partition",
        "stable_record_pool_clears_reference_120_each_partition",
        (
            "stable_record_pool_at_conservative_relationship_floor_clears_"
            "reference_120_each_partition"
        ),
    )
    source_arithmetic_ok = all(
        breadth_decision.get(key) is True for key in arithmetic_keys
    )
    old_requirements = _requirement_index(report)
    source_manifest_ok = (
        source_arithmetic_ok
        and old_requirements[
            "truth_bearing_source_manifest_feasible_and_frozen"
        ]["satisfied"]
        and breadth_decision.get("source_successor_selected") is True
        and breadth_decision.get("qualified_reference_group_count", 0) > 0
        and breadth_decision.get("allocated_group_count", 0) > 0
    )
    metric_successor_preregisterable = (
        successor_readiness.get("visqol_only_successor_preregisterable") is True
        and successor_readiness.get("technical_synthetic_replay_readiness") is True
        and successor_readiness.get("cross_environment_numeric_replay_passed")
        is True
    )
    metric_ok = (
        metric_successor_preregisterable
        and successor_decision.get("selected_successor_option") is not None
        and successor_decision.get("new_successor_metric_gate_exists") is True
        and successor_readiness.get("eligible_audio_metric_execution_complete")
        is True
        and plan["authorization"]["perceptual_metric_execution_authorized"] is True
    )

    source = old_requirements[
        "truth_bearing_source_manifest_feasible_and_frozen"
    ]
    source.update(
        {
            "state": (
                "arithmetic_feasible_exact_manifest_unfrozen"
                if source_arithmetic_ok
                else "arithmetic_infeasible"
            ),
            "satisfied": source_manifest_ok,
            "evidence": [
                "breadth_repair_report.decision",
                "predecessor_audit.requirements.truth_bearing_source_manifest",
                "breadth_repair_plan.authorization",
            ],
            "reason": (
                "Stable public-record capacity now clears every modelled "
                "provider-pure breadth scenario, including conservative "
                "120-group and mastered-music constraints, but exact members, "
                "provenance, relationships, source selection and allocation "
                "remain unfrozen."
            ),
            "next_gate": (
                "Choose whether to authorize bounded record preservation and "
                "exact-member metadata audit, or reject the current "
                "truth-source design; this grants no archive, "
                "repository-object or audio access."
            ),
        }
    )

    metric = old_requirements[
        "perceptual_metric_execution_and_legal_gate_passed"
    ]
    metric.update(
        {
            "state": "successor_preregisterable_unselected_execution_closed",
            "satisfied": metric_ok,
            "evidence": [
                "predecessor_audit.requirements.perceptual_metric_gate",
                "metric_successor_disposition.decision",
                "metric_successor_disposition.readiness",
            ],
            "reason": (
                "The stopped two-family gate remains closed; a ViSQOL-only "
                "successor is technically preregisterable, but is unselected, "
                "scientifically unready and has no execution gate."
            ),
            "next_gate": (
                "Choose whether to authorize a score-blind ViSQOL-only "
                "successor amendment or reject the available metric path; "
                "this does not authorize execution."
            ),
        }
    )

    transfer = old_requirements[
        "grouped_source_domain_codec_encoder_transfer_passed"
    ]
    transfer.update(
        {
            "evidence": [
                "predecessor_audit.requirements.grouped_transfer",
                "breadth_repair_report.decision",
            ],
            "reason": (
                "All four holdout axes and feasible source-capacity witnesses "
                "exist, but exact allocation and grouped transfer are untested."
            ),
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
            "state": "objective_incomplete_current_evidence_reconciled",
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
            "source_arithmetic_feasible": source_arithmetic_ok,
            "source_manifest_frozen": source_manifest_ok,
            "metric_successor_preregisterable": metric_successor_preregisterable,
            "metric_successor_selected": successor_decision.get(
                "selected_successor_option"
            )
            is not None,
            "nearest_authority_dependent_decisions": [
                breadth_decision.get("next_responsible_human_decision"),
                successor_decision.get("next_responsible_human_decision"),
            ],
        }
    )
    report["summary"].pop("nearest_authority_dependent_decision", None)
    report["evidence_checks"] = {
        "odaq_clean_references_acquired": predecessor_report[
            "evidence_checks"
        ]["odaq_clean_references_acquired"],
        "odaq_transparent_truth_supported": predecessor_report[
            "evidence_checks"
        ]["odaq_transparent_truth_supported"],
        "stable_provider_arithmetic_feasible": source_arithmetic_ok,
        "qualified_reference_group_count": breadth_decision.get(
            "qualified_reference_group_count"
        ),
        "allocated_group_count": breadth_decision.get("allocated_group_count"),
        "exact_member_selection_authorized": breadth_plan.get(
            "authorization", {}
        ).get("exact_member_selection_authorized")
        is True,
        "source_successor_selected": breadth_decision.get(
            "source_successor_selected"
        )
        is True,
        "visqol_only_successor_preregisterable": metric_successor_preregisterable,
        "metric_successor_selected": successor_decision.get(
            "selected_successor_option"
        )
        is not None,
        "new_successor_metric_gate_exists": successor_decision.get(
            "new_successor_metric_gate_exists"
        )
        is True,
        "score_free_schema_replay_complete": predecessor_report[
            "evidence_checks"
        ]["score_free_schema_replay_complete"],
        "scientific_gate_evaluated": predecessor_report["evidence_checks"][
            "scientific_gate_evaluated"
        ],
    }
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
