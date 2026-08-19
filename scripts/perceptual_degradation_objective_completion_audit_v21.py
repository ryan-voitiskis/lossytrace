#!/usr/bin/env python3
"""Refresh the objective audit after clean-capture intake readiness."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/objective-completion-audit-plan-20260819-021.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-objective-completion-audit-20260819-021.json"
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260819-021"
REPORT_ID = PLAN_ID
EXPECTED_BINDINGS = {
    "acquisition_specification",
    "intake_implementation",
    "intake_plan",
    "intake_synthetic_report",
    "predecessor_audit_implementation",
    "predecessor_audit_plan",
    "predecessor_audit_report",
}
TRUE_AUTHORIZATIONS = {
    "bound_committed_evidence_read_authorized",
    "clean_capture_readiness_reconciliation_authorized",
    "synthetic_audit_execution_authorized",
}
NEXT_GATE = (
    "Obtain explicit authority either to conduct or arrange one safe clean capture under the frozen specification, or to terminate "
    "source-manifest feasibility as a rigorous negative. If a delivery is produced, keep its private metadata outside Git and freeze "
    "a separately authorized live metadata-acceptance checkpoint before any preview, download or audio access."
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != "score_blind_completion_audit_refresh_after_clean_capture_intake_readiness":
        errors.append("plan state differs")
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != EXPECTED_BINDINGS:
        errors.append("binding inventory differs")
        bindings = {}
    for binding_id, binding in bindings.items():
        path = Path(str(binding.get("path", "")))
        if path.is_absolute() or ".." in path.parts or not (ROOT / path).is_file():
            errors.append(f"invalid binding: {binding_id}")
        elif sha256_file(ROOT / path) != binding.get("sha256"):
            errors.append(f"binding hash differs: {binding_id}")
    authorization = plan.get("authorization", {})
    if set(authorization) != TRUE_AUTHORIZATIONS | {
        "collection_authorized",
        "external_communication_authorized",
        "further_audio_sample_access_authorized",
        "human_collection_authorized",
        "live_delivery_acceptance_authorized",
        "no_reference_training_authorized",
        "payment_or_purchase_authorized",
        "perceptual_metric_execution_authorized",
        "public_verdict_enabled",
        "source_manifest_allocation_authorized",
        "source_trait_assignment_authorized",
    }:
        errors.append("authorization inventory differs")
    for key, value in authorization.items():
        if value is not (key in TRUE_AUTHORIZATIONS):
            errors.append(f"authorization differs: {key}")
    if plan.get("completion_policy") != {
        "all_requirements_must_be_satisfied": True,
        "readiness_artifacts_count_as_scientific_coverage": False,
        "source_trait_manifest_requires_assignments_relationships_and_allocation": True,
        "synthetic_intake_pass_counts_as_live_delivery": False,
    }:
        errors.append("completion policy differs")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def _verify_readiness(plan: dict[str, Any]) -> dict[str, Any]:
    acquisition = load_json(_bound(plan, "acquisition_specification"))
    for key in ("audio_access_authorized", "collection_authorized", "external_communication_authorized", "payment_or_purchase_authorized"):
        if acquisition["authorization"].get(key) is not False:
            raise ValueError(f"acquisition authority differs: {key}")
    intake = _load_module(_bound(plan, "intake_implementation"), "clean_capture_intake")
    intake_plan = intake.load_json(_bound(plan, "intake_plan"))
    intake_errors = intake.validate_plan(intake_plan)
    if intake_errors:
        raise ValueError("intake plan invalid: " + "; ".join(intake_errors))
    report = intake.build_public_report(intake_plan, intake.load_json(intake.FIXTURE_PATH))
    if intake.canonical_json_bytes(report) != _bound(plan, "intake_synthetic_report").read_bytes():
        raise ValueError("replayed intake report differs")
    if report["decision"] != {
        "accepted_metadata_requires_separate_exact_member_checkpoint": True,
        "live_delivery_accepted": False,
        "synthetic_fixture_passed": True,
    }:
        raise ValueError("intake decision differs")
    if report["audio_accessed"] is not False or report["execution"]["gate_pass_count"] != 8:
        raise ValueError("intake execution boundary differs")
    return report


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    predecessor = _load_module(_bound(plan, "predecessor_audit_implementation"), "objective_v20")
    predecessor_plan_path = _bound(plan, "predecessor_audit_plan")
    report = predecessor.build_report(predecessor.load_json(predecessor_plan_path), predecessor_plan_path)
    if predecessor.canonical_json_bytes(report) != _bound(plan, "predecessor_audit_report").read_bytes():
        raise ValueError("replayed predecessor differs")
    intake = _verify_readiness(plan)

    requirements = {row["requirement_id"]: row for row in report["requirements"]}
    requirements["truth_bearing_source_manifest_feasible_and_frozen"].update({
        "state": "public_metadata_route_exhausted_clean_capture_spec_and_synthetic_intake_ready_live_delivery_absent_manifest_unfrozen",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.truth_bearing_source_manifest",
            "clean_capture_acquisition_specification",
            "clean_capture_intake_plan",
            "clean_capture_intake_synthetic_report.gates",
            "clean_capture_intake_synthetic_report.decision",
        ],
        "reason": "The exhausted public metadata route now has a safe, provenance-complete clean-capture acquisition specification and an eight-gate metadata intake implementation whose synthetic fixture passes without opening audio. No live delivery exists, live acceptance and external action remain unauthorized, and synthetic readiness is not source evidence, trait truth, relationship adjudication or manifest allocation.",
        "next_gate": NEXT_GATE,
    })
    requirements["difficult_natural_and_production_negatives_preserved_in_evaluation"].update({
        "state": "three_sparse_exact_failures_and_metadata_negative_preserved_clean_capture_readiness_only_evaluation_unallocated",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.difficult_negatives",
            "clean_capture_intake_synthetic_report.decision",
        ],
        "reason": "The three exact sparse failures and bounded metadata negative remain preserved. The synthetic intake pass validates only the future metadata gate and supplies no new natural source, independent contrast or evaluation allocation.",
        "next_gate": NEXT_GATE,
    })
    satisfied = sum(row["satisfied"] for row in report["requirements"])
    if satisfied != 4 or all(row["satisfied"] for row in report["requirements"]):
        raise ValueError("readiness unexpectedly promoted completion")

    report.update({
        "implementation_sha256": sha256_file(Path(__file__)),
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "report_id": REPORT_ID,
        "state": "objective_incomplete_clean_capture_intake_ready_without_live_delivery_audio_or_scientific_promotion",
    })
    report["summary"].update({
        "clean_capture_acquisition_specification_frozen": True,
        "clean_capture_external_action_authorized": False,
        "clean_capture_intake_gate_count": intake["execution"]["gate_count"],
        "clean_capture_intake_implementation_ready": True,
        "clean_capture_intake_synthetic_gate_pass_count": intake["execution"]["gate_pass_count"],
        "clean_capture_intake_synthetic_passed": True,
        "clean_capture_live_delivery_accepted": False,
        "clean_capture_live_delivery_present": False,
        "independent_sparse_and_tonal_contrasts_established": False,
        "nearest_authority_dependent_decisions": [
            NEXT_GATE,
            requirements["perceptual_metric_execution_and_legal_gate_passed"].get("next_gate"),
            requirements["deterministic_human_calibrated_full_reference_oracle_passed"].get("next_gate"),
        ],
        "objective_complete": False,
        "satisfied_count": 4,
        "source_trait_manifest_frozen": False,
        "unsatisfied_count": 10,
    })
    report["evidence_checks"].update({
        "clean_capture_acquisition_specification_frozen": True,
        "clean_capture_audio_accessed": False,
        "clean_capture_external_action_authorized": False,
        "clean_capture_intake_gate_count": intake["execution"]["gate_count"],
        "clean_capture_intake_implementation_ready": True,
        "clean_capture_intake_synthetic_gate_pass_count": intake["execution"]["gate_pass_count"],
        "clean_capture_intake_synthetic_passed": True,
        "clean_capture_live_delivery_accepted": False,
        "clean_capture_live_delivery_present": False,
        "independent_sparse_and_tonal_contrasts_established": False,
        "source_manifest_allocation_performed": False,
        "source_trait_assignment_performed": False,
        "source_trait_manifest_frozen": False,
    })
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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
