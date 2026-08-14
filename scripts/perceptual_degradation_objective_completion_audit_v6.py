#!/usr/bin/env python3
"""Refresh the objective audit after retained drift-validation readiness."""

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
    "objective-completion-audit-plan-20260814-006.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-objective-completion-audit-20260814-006.json"
)
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260814-006"
REPORT_ID = PLAN_ID

AUTHORIZATION = {
    "bound_metadata_and_source_read_authorized": True,
    "synthetic_audit_execution_authorized": True,
    "retained_drift_validation_protocol_readiness_authorized": True,
    "retained_audio_access_authorized": False,
    "retained_drift_correction_authorized": False,
    "real_audio_drift_estimation_validation_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "human_response_access_authorized": False,
    "human_collection_authorized": False,
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
    "retained_validation_protocol_readiness_counts_as_authorization": False,
    "retained_validation_protocol_readiness_counts_as_retained_validation": False,
    "retained_validation_protocol_readiness_counts_as_perceptual_validation": False,
    "retained_validation_protocol_readiness_counts_as_full_reference_oracle_pass": False,
    "technical_alignment_support_counts_as_human_calibration": False,
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
    "retained_drift_readiness_plan",
    "retained_drift_readiness_implementation",
    "retained_drift_readiness_report",
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
        "score_blind_completion_audit_refreshed_for_retained_drift_validation_readiness_no_scientific_promotion"
    ):
        errors.append("plan state differs")
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != EXPECTED_BINDINGS:
        errors.append("binding inventory differs")
        bindings = {}
    for binding_id, binding in bindings.items():
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


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load bound implementation: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _requirement_index(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["requirement_id"]: item for item in report["requirements"]}


def build_report(
    plan: dict[str, Any], plan_path: Path = PLAN_PATH
) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))

    predecessor = _load_module(
        _bound(plan, "predecessor_audit_implementation"), "objective_audit_v5"
    )
    predecessor_plan_path = _bound(plan, "predecessor_audit_plan")
    predecessor_report = predecessor.build_report(
        predecessor.load_json(predecessor_plan_path), predecessor_plan_path
    )
    if hashlib.sha256(canonical_json_bytes(predecessor_report)).hexdigest() != plan[
        "bindings"
    ]["predecessor_audit_report"]["sha256"]:
        raise ValueError("replayed predecessor report differs from bound report")

    readiness_module = _load_module(
        _bound(plan, "retained_drift_readiness_implementation"),
        "retained_drift_readiness",
    )
    readiness = load_json(_bound(plan, "retained_drift_readiness_report"))
    if readiness_module.validate_report(readiness):
        raise ValueError("bound retained-drift readiness report no longer validates")
    readiness_decision = readiness["decision"]
    protocol_ready = (
        readiness.get("all_readiness_gates_pass") is True
        and readiness_decision.get("protocol_frozen") is True
        and readiness_decision.get("authorization_schema_frozen") is True
        and readiness_decision.get(
            "ready_to_request_responsible_human_authorization"
        )
        is True
    )
    retained_validated = (
        readiness_decision.get("live_execution_authorized") is True
        and readiness_decision.get("retained_validation_complete") is True
        and readiness_decision.get("real_content_drift_estimation_validated") is True
    )

    report = json.loads(json.dumps(predecessor_report))
    requirement = _requirement_index(report)[
        "deterministic_human_calibrated_full_reference_oracle_passed"
    ]
    requirement.update(
        {
            "state": "retained_drift_validation_protocol_frozen_authorization_and_execution_pending",
            "satisfied": requirement["satisfied"] and retained_validated,
            "evidence": [
                "predecessor_audit.requirements.full_reference_oracle",
                "retained_drift_readiness_report.gate_audit",
                "retained_drift_readiness_report.decision",
            ],
            "reason": (
                "A metadata-only protocol and successor-authorization schema now "
                "predeclare 112 technical cases across the exact 16 acquired clean "
                "references, including signal-support abstention, estimator accuracy, "
                "correction benefit, bit-exact bypass and two-replay gates. All nine "
                "readiness gates passed. No retained reference was read or projected, "
                "no live runner was implemented, and no real-content, perceptual or "
                "human validation occurred, so the full-reference requirement remains "
                "unsatisfied."
            ),
            "next_gate": readiness_decision.get("next_gate"),
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
            "state": "objective_incomplete_retained_drift_validation_readiness_reconciled_without_scientific_promotion",
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
            "retained_drift_validation_protocol_ready": protocol_ready,
            "retained_drift_validation_authorization_present": False,
            "retained_drift_validation_live_runner_implemented": False,
            "retained_drift_validation_executed": False,
            "retained_drift_validation_complete": retained_validated,
            "retained_drift_future_source_count": 16,
            "retained_drift_future_case_count": readiness.get(
                "future_validation_case_count"
            ),
            "retained_drift_readiness_gate_pass_count": sum(
                readiness["gate_audit"].values()
            ),
            "nearest_authority_dependent_decisions": [
                report["requirements"][2].get("next_gate"),
                report["requirements"][4].get("next_gate"),
                readiness_decision.get("next_gate"),
            ],
        }
    )
    report["evidence_checks"].update(
        {
            "retained_drift_protocol_readiness_authorized": plan["authorization"]
            ["retained_drift_validation_protocol_readiness_authorized"],
            "retained_drift_protocol_frozen": readiness_decision.get(
                "protocol_frozen"
            )
            is True,
            "retained_drift_authorization_schema_frozen": readiness_decision.get(
                "authorization_schema_frozen"
            )
            is True,
            "retained_drift_responsible_human_authorization_present": False,
            "retained_drift_live_runner_implementation_authorized": False,
            "retained_drift_live_execution_authorized": False,
            "retained_drift_retained_audio_accessed": False,
            "retained_drift_validation_complete": retained_validated,
            "retained_drift_real_content_estimation_validated": False,
            "retained_drift_readiness_is_full_reference_validation": False,
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
