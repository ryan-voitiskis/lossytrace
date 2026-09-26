#!/usr/bin/env python3
"""Refresh the objective audit after private ODAQ clean-reference delivery."""

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
    "objective-completion-audit-plan-20260814-007.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-objective-completion-audit-20260814-007.json"
)
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260814-007"
REPORT_ID = PLAN_ID

AUTHORIZATION = {
    "bound_metadata_and_source_read_authorized": True,
    "synthetic_audit_execution_authorized": True,
    "private_delivery_result_reconciliation_authorized": True,
    "retained_clean_reference_delivery_access_completed": True,
    "retained_drift_validation_protocol_readiness_authorized": True,
    "retained_drift_validation_audio_access_authorized": False,
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
    "private_delivery_completion_counts_as_stimulus_generation": False,
    "private_delivery_completion_counts_as_perceptual_truth": False,
    "private_delivery_completion_counts_as_metric_evidence": False,
    "private_delivery_completion_counts_as_listening_evidence": False,
    "private_delivery_completion_counts_as_retained_drift_validation": False,
    "private_delivery_completion_counts_as_full_reference_oracle_pass": False,
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
    "odaq_delivery_result",
    "odaq_delivery_result_validator",
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
    if plan.get("state") != "score_blind_completion_audit_refresh_for_private_odaq_delivery_completion":
        errors.append("plan state differs")
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != EXPECTED_BINDINGS:
        errors.append("binding inventory differs")
        bindings = {}
    for binding_id, binding in bindings.items():
        relative = Path(str(binding.get("path", "")))
        path = root / relative
        if relative.is_absolute() or ".." in relative.parts:
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
        _bound(plan, "predecessor_audit_implementation"), "objective_audit_v6"
    )
    predecessor_plan = _bound(plan, "predecessor_audit_plan")
    predecessor_report = predecessor.build_report(
        predecessor.load_json(predecessor_plan), predecessor_plan
    )
    if sha256_file(_bound(plan, "predecessor_audit_report")) != plan["bindings"][
        "predecessor_audit_report"
    ]["sha256"] or canonical_json_bytes(predecessor_report) != _bound(
        plan, "predecessor_audit_report"
    ).read_bytes():
        raise ValueError("replayed predecessor report differs from bound report")

    delivery_validator = _load_module(
        _bound(plan, "odaq_delivery_result_validator"), "odaq_delivery_result"
    )
    delivery = load_json(_bound(plan, "odaq_delivery_result"))
    delivery_errors = delivery_validator.validate_result(delivery)
    if delivery_errors:
        raise ValueError("bound delivery result no longer validates: " + "; ".join(delivery_errors))
    delivery_complete = (
        delivery.get("state")
        == "private_canonical_integer_pcm_delivery_complete_two_replays_verified"
        and delivery["delivery_inventory"].get("reference_count_per_replay") == 16
        and delivery["delivery_inventory"].get("replay_trees_byte_identical") is True
        and delivery["attribution"].get("attachments_byte_identical") is True
    )

    report = json.loads(json.dumps(predecessor_report))
    requirement = _requirement_index(report)[
        "deterministic_human_calibrated_full_reference_oracle_passed"
    ]
    requirement.update(
        {
            "state": "retained_clean_reference_delivery_complete_drift_validation_authorization_and_execution_pending",
            "satisfied": False,
            "evidence": [
                "predecessor_audit.requirements.full_reference_oracle",
                "odaq_delivery_result.input_inventory",
                "odaq_delivery_result.delivery_inventory",
                "odaq_delivery_result.attribution",
                "odaq_delivery_result.claim_boundary",
            ],
            "reason": (
                "The exact 16 retained ODAQ clean references were reverified and "
                "projected into two byte-identical private canonical integer-PCM "
                "delivery trees with attribution attached. This completes authorized "
                "delivery plumbing only. No controlled drift case, real-content "
                "estimator validation, perceptual metric, rating or listening truth "
                "was produced, so the full-reference requirement remains unsatisfied."
            ),
            "next_gate": delivery["next_gate"],
        }
    )
    if [item["requirement_id"] for item in report["requirements"]] != REQUIREMENTS:
        raise ValueError("refreshed requirement order differs from frozen inventory")
    satisfied_count = sum(item["satisfied"] for item in report["requirements"])
    complete = all(item["satisfied"] for item in report["requirements"])
    if complete or satisfied_count != 4:
        raise ValueError("delivery evidence unexpectedly promoted scientific completion")

    report.update(
        {
            "report_id": REPORT_ID,
            "state": "objective_incomplete_private_odaq_delivery_reconciled_without_scientific_promotion",
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
            "odaq_clean_reference_delivery_authorization_present": True,
            "odaq_clean_reference_delivery_runner_implemented": True,
            "odaq_clean_reference_delivery_executed": delivery_complete,
            "odaq_clean_reference_delivery_source_count": 16,
            "odaq_clean_reference_delivery_replay_count": 2,
            "odaq_clean_reference_delivery_replays_byte_identical": True,
            "odaq_clean_reference_delivery_attribution_attached": True,
            "odaq_clean_reference_delivery_is_perceptual_evidence": False,
            "retained_drift_validation_authorization_present": False,
            "retained_drift_validation_executed": False,
            "retained_drift_validation_complete": False,
            "nearest_authority_dependent_decisions": [
                report["requirements"][2].get("next_gate"),
                report["requirements"][4].get("next_gate"),
                delivery["next_gate"],
            ],
        }
    )
    report["evidence_checks"].update(
        {
            "odaq_clean_reference_delivery_authorized": True,
            "odaq_clean_reference_audio_accessed": True,
            "odaq_clean_reference_delivery_projected": True,
            "odaq_clean_reference_delivery_two_replays_complete": delivery_complete,
            "odaq_clean_reference_delivery_replays_byte_identical": True,
            "odaq_clean_reference_delivery_attribution_attached": True,
            "odaq_clean_reference_delivery_is_stimulus_generation": False,
            "odaq_clean_reference_delivery_is_perceptual_truth": False,
            "odaq_clean_reference_delivery_is_metric_evidence": False,
            "odaq_clean_reference_delivery_is_listening_evidence": False,
            "retained_drift_responsible_human_authorization_present": False,
            "retained_drift_live_execution_authorized": False,
            "retained_drift_validation_complete": False,
            "retained_drift_real_content_estimation_validated": False,
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
