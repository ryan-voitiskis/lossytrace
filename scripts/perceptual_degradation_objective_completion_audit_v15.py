#!/usr/bin/env python3
"""Refresh objective audit after sparse non-tonal successor metadata rejection."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/objective-completion-audit-plan-20260819-015.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-objective-completion-audit-20260819-015.json"
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260819-015"
REPORT_ID = PLAN_ID
EXPECTED_BINDINGS = {
    "predecessor_audit_implementation",
    "predecessor_audit_plan",
    "predecessor_audit_report",
    "successor_metadata_audit_implementation",
    "successor_metadata_audit_plan",
    "successor_metadata_audit_report",
}


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
    if plan.get("state") != "score_blind_completion_audit_refresh_after_sparse_non_tonal_successor_metadata_rejection":
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
    allowed = {
        "bound_committed_evidence_read_authorized",
        "sparse_non_tonal_successor_metadata_reconciliation_authorized",
        "synthetic_audit_execution_authorized",
    }
    for key, value in authorization.items():
        if value is not (key in allowed):
            errors.append(f"authorization differs: {key}")
    policy = plan.get("completion_policy", {})
    if policy.get("all_requirements_must_be_satisfied") is not True:
        errors.append("all-requirements completion policy differs")
    if policy.get("source_trait_manifest_requires_assignments_relationships_and_allocation") is not True:
        errors.append("manifest completion policy differs")
    if policy.get("metadata_only_candidate_rejection_counts_as_scientific_coverage") is not False:
        errors.append("metadata rejection promotion boundary differs")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    predecessor = _load_module(_bound(plan, "predecessor_audit_implementation"), "objective_v14")
    predecessor_plan_path = _bound(plan, "predecessor_audit_plan")
    report = predecessor.build_report(predecessor.load_json(predecessor_plan_path), predecessor_plan_path)
    if canonical_json_bytes(report) != _bound(plan, "predecessor_audit_report").read_bytes():
        raise ValueError("replayed predecessor differs")
    successor = _load_module(_bound(plan, "successor_metadata_audit_implementation"), "sparse_successor_metadata")
    successor_plan_path = _bound(plan, "successor_metadata_audit_plan")
    successor_report = successor.build_report(successor.load_json(successor_plan_path), successor_plan_path)
    if successor.canonical_json_bytes(successor_report) != _bound(plan, "successor_metadata_audit_report").read_bytes():
        raise ValueError("replayed successor metadata audit differs")
    if successor_report["decision"]["eligible_successor_count"] != 0 or successor_report["audio_accessed"] is not False:
        raise ValueError("metadata audit unexpectedly selected or accessed a successor")

    next_gate = successor_report["decision"]["next_gate"]
    requirements = {row["requirement_id"]: row for row in report["requirements"]}
    requirements["truth_bearing_source_manifest_feasible_and_frozen"].update({
        "state": "tonal_contrast_confirmed_sparse_successor_metadata_routes_rejected_manifest_unfrozen",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.truth_bearing_source_manifest",
            "sparse_successor_metadata_audit.record_dispositions",
            "sparse_successor_metadata_audit.decision",
            "sparse_successor_metadata_audit.claim_boundary",
        ],
        "reason": "Five metadata-only sparse non-tonal successor routes were rejected before audio access. Each lacks at least one frozen prerequisite: sufficient duration, explicit all-channel capture chain, explicit transformation history, or natural-waveform eligibility. The previous abstention and thresholds are preserved; no replacement, trait assignment, relationship promotion or manifest allocation occurred.",
        "next_gate": next_gate,
    })
    requirements["difficult_natural_and_production_negatives_preserved_in_evaluation"].update({
        "state": "tonal_exact_contrast_confirmed_sparse_successor_still_missing_evaluation_unallocated",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.difficult_negatives",
            "sparse_successor_metadata_audit.record_dispositions",
            "sparse_successor_metadata_audit.decision",
        ],
        "reason": "The exact tonal non-sparse technical contrast remains confirmed, but no eligible sparse non-tonal successor was found and no contrast is allocated to scientific evaluation. Metadata rejection is not descriptor or source-trait evidence.",
        "next_gate": next_gate,
    })
    satisfied = sum(row["satisfied"] for row in report["requirements"])
    if satisfied != 4 or all(row["satisfied"] for row in report["requirements"]):
        raise ValueError("metadata rejection unexpectedly promoted completion")
    report.update({
        "report_id": REPORT_ID,
        "state": "objective_incomplete_sparse_successor_metadata_rejections_reconciled_without_audio_or_scientific_promotion",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
    })
    report["summary"].update({
        "satisfied_count": 4,
        "unsatisfied_count": 10,
        "objective_complete": False,
        "sparse_non_tonal_successor_metadata_audit_complete": True,
        "sparse_non_tonal_successor_metadata_candidate_count": len(successor_report["record_dispositions"]),
        "sparse_non_tonal_eligible_successor_count": 0,
        "sparse_non_tonal_successor_selected": False,
        "independent_sparse_and_tonal_contrasts_established": False,
        "source_trait_manifest_frozen": False,
        "nearest_authority_dependent_decisions": [
            next_gate,
            requirements["perceptual_metric_execution_and_legal_gate_passed"].get("next_gate"),
            requirements["deterministic_human_calibrated_full_reference_oracle_passed"].get("next_gate"),
        ],
    })
    report["evidence_checks"].update({
        "sparse_non_tonal_successor_metadata_audit_complete": True,
        "sparse_non_tonal_successor_metadata_candidate_count": 5,
        "sparse_non_tonal_eligible_successor_count": 0,
        "sparse_non_tonal_successor_metadata_audio_accessed": False,
        "sparse_non_tonal_successor_selected": False,
        "sparse_non_tonal_previous_abstention_preserved": True,
        "independent_sparse_and_tonal_contrasts_established": False,
        "source_trait_assignment_performed": False,
        "source_manifest_allocation_performed": False,
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
    args.output.write_bytes(payload)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
