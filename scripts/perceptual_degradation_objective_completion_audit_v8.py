#!/usr/bin/env python3
"""Refresh the objective audit after retained ODAQ drift execution."""

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
    / "objective-completion-audit-plan-20260817-008.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence"
    / "perceptual-degradation-objective-completion-audit-20260817-008.json"
)
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260817-008"
REPORT_ID = PLAN_ID

AUTHORIZATION = {
    "bound_metadata_and_source_read_authorized": True,
    "synthetic_audit_execution_authorized": True,
    "private_retained_drift_result_reconciliation_authorized": True,
    "retained_clean_reference_access_completed": True,
    "controlled_synthetic_clock_drift_execution_completed": True,
    "temporary_in_memory_pcm_execution_completed": True,
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
    "retained_drift_execution_counts_as_technical_evidence": True,
    "retained_drift_failed_gate_counts_as_scientific_completion": False,
    "retained_drift_execution_counts_as_perceptual_truth": False,
    "retained_drift_execution_counts_as_metric_evidence": False,
    "retained_drift_execution_counts_as_listening_evidence": False,
    "retained_drift_execution_counts_as_actual_codec_evidence": False,
    "retained_drift_execution_counts_as_full_reference_oracle_pass": False,
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
    "retained_drift_result",
    "retained_drift_result_validator",
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


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "score_blind_completion_audit_refresh_for_reproducible_retained_drift_technical_negative"
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


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load bound implementation: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _requirement_index(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["requirement_id"]: item for item in report["requirements"]}


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    predecessor = _load_module(
        _bound(plan, "predecessor_audit_implementation"), "objective_audit_v7"
    )
    predecessor_plan = _bound(plan, "predecessor_audit_plan")
    predecessor_report = predecessor.build_report(
        predecessor.load_json(predecessor_plan), predecessor_plan
    )
    predecessor_report_path = _bound(plan, "predecessor_audit_report")
    if (
        sha256_file(predecessor_report_path)
        != plan["bindings"]["predecessor_audit_report"]["sha256"]
        or canonical_json_bytes(predecessor_report) != predecessor_report_path.read_bytes()
    ):
        raise ValueError("replayed predecessor report differs from bound report")

    result_validator = _load_module(
        _bound(plan, "retained_drift_result_validator"), "retained_drift_result"
    )
    result = load_json(_bound(plan, "retained_drift_result"))
    result_errors = result_validator.validate_result(result)
    if result_errors:
        raise ValueError(
            "bound retained-drift result no longer validates: "
            + "; ".join(result_errors)
        )
    execution_complete = (
        result.get("state")
        == "private_odaq_retained_drift_validation_complete_reproducible_technical_negative"
        and result["execution"].get("fresh_replay_count") == 2
        and result["execution"].get("replay_reports_byte_identical") is True
        and result["aggregate_observations_per_replay"].get("attempted_case_count")
        == 112
    )

    report = json.loads(json.dumps(predecessor_report))
    requirement = _requirement_index(report)[
        "deterministic_human_calibrated_full_reference_oracle_passed"
    ]
    requirement.update(
        {
            "state": "retained_clean_reference_controlled_drift_execution_complete_reproducible_technical_negative",
            "satisfied": False,
            "evidence": [
                "predecessor_audit.requirements.full_reference_oracle",
                "retained_drift_result.execution",
                "retained_drift_result.aggregate_observations_per_replay",
                "retained_drift_result.predeclared_gate_audit",
                "retained_drift_result.access_boundary",
                "retained_drift_result.claim_boundary",
            ],
            "reason": (
                "The frozen controlled-drift protocol completed twice on the exact 16 "
                "retained clean references, producing byte-identical reports. Six applied "
                "cases missed the predeclared per-channel post-correction correlation gate, "
                "so only 16 of 17 gates passed. This is reproducible technical evidence, "
                "not human calibration, perceptual truth, actual-codec evidence, or a "
                "deterministic human-calibrated full-reference oracle pass."
            ),
            "next_gate": result["next_gate"],
        }
    )
    if [item["requirement_id"] for item in report["requirements"]] != REQUIREMENTS:
        raise ValueError("refreshed requirement order differs from frozen inventory")
    satisfied_count = sum(item["satisfied"] for item in report["requirements"])
    complete = all(item["satisfied"] for item in report["requirements"])
    if complete or satisfied_count != 4:
        raise ValueError("retained-drift evidence unexpectedly promoted scientific completion")

    report.update(
        {
            "report_id": REPORT_ID,
            "state": "objective_incomplete_reproducible_retained_drift_technical_negative_reconciled_without_scientific_promotion",
            "plan_id": plan["plan_id"],
            "plan_sha256": sha256_file(plan_path),
            "implementation_sha256": sha256_file(Path(__file__)),
            "audio_accessed": True,
        }
    )
    report["summary"].update(
        {
            "satisfied_count": satisfied_count,
            "unsatisfied_count": len(REQUIREMENTS) - satisfied_count,
            "objective_complete": complete,
            "retained_drift_validation_authorization_present": True,
            "retained_drift_validation_live_runner_implemented": True,
            "retained_drift_validation_executed": execution_complete,
            "retained_drift_protocol_execution_complete": execution_complete,
            "retained_drift_validation_complete": False,
            "retained_drift_validation_reproducible_technical_negative": True,
            "retained_drift_validation_replay_count": 2,
            "retained_drift_validation_reference_count": 16,
            "retained_drift_validation_case_count_per_replay": 112,
            "retained_drift_validation_gate_count": 17,
            "retained_drift_validation_gate_pass_count": 16,
            "retained_drift_validation_all_gates_pass": False,
            "retained_drift_validation_failed_gate_id": (
                "applied_case_minimum_post_correction_core_correlation_each_channel"
            ),
            "retained_drift_validation_is_perceptual_evidence": False,
            "oracle_drift_estimator_integrated_on_retained_audio": True,
            "oracle_drift_resampler_integrated_on_retained_audio": True,
            "oracle_drift_retained_validation_complete": False,
            "nearest_authority_dependent_decisions": [
                report["requirements"][2].get("next_gate"),
                report["requirements"][4].get("next_gate"),
                result["next_gate"],
            ],
        }
    )
    report["evidence_checks"].update(
        {
            "retained_drift_responsible_human_authorization_present": True,
            "retained_drift_live_runner_implementation_authorized": True,
            "retained_drift_live_execution_authorized": True,
            "retained_drift_retained_audio_accessed": True,
            "retained_drift_protocol_execution_complete": execution_complete,
            "retained_drift_replay_reports_byte_identical": True,
            "retained_drift_all_predeclared_gates_pass": False,
            "retained_drift_reproducible_technical_negative": True,
            "retained_drift_validation_complete": False,
            "retained_drift_real_content_estimation_validated": False,
            "retained_drift_is_perceptual_truth": False,
            "retained_drift_is_actual_codec_evidence": False,
            "retained_drift_is_full_reference_oracle_pass": False,
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
