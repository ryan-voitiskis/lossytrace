#!/usr/bin/env python3
"""Refresh objective audit after the sparse/tonal descriptor freeze."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/objective-completion-audit-plan-20260818-013.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-objective-completion-audit-20260818-013.json"
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260818-013"
REPORT_ID = PLAN_ID
EXPECTED_BINDINGS = {
    "predecessor_audit_implementation", "predecessor_audit_plan", "predecessor_audit_report",
    "sparse_tonal_implementation", "sparse_tonal_plan", "sparse_tonal_report",
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
    if plan.get("state") != "score_blind_completion_audit_refresh_after_sparse_tonal_descriptor_freeze":
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
    for key, value in authorization.items():
        expected = key in {
            "bound_committed_evidence_read_authorized",
            "sparse_tonal_descriptor_reconciliation_authorized",
            "synthetic_audit_execution_authorized",
        }
        if value is not expected:
            errors.append(f"authorization differs: {key}")
    policy = plan.get("completion_policy", {})
    if policy.get("all_requirements_must_be_satisfied") is not True or policy.get("source_trait_manifest_requires_assignments_relationships_and_allocation") is not True:
        errors.append("completion policy positive boundary differs")
    if policy.get("descriptor_rules_count_as_exact_member_contrasts") is not False or policy.get("synthetic_fixture_pass_counts_as_scientific_coverage") is not False:
        errors.append("completion policy promotion boundary differs")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    predecessor = _load_module(_bound(plan, "predecessor_audit_implementation"), "objective_v12")
    predecessor_plan_path = _bound(plan, "predecessor_audit_plan")
    report = predecessor.build_report(predecessor.load_json(predecessor_plan_path), predecessor_plan_path)
    if canonical_json_bytes(report) != _bound(plan, "predecessor_audit_report").read_bytes():
        raise ValueError("replayed predecessor differs")
    descriptor = _load_module(_bound(plan, "sparse_tonal_implementation"), "sparse_tonal")
    descriptor_plan_path = _bound(plan, "sparse_tonal_plan")
    descriptor_report = descriptor.build_report(descriptor.load_json(descriptor_plan_path), descriptor_plan_path)
    if descriptor.canonical_json_bytes(descriptor_report) != _bound(plan, "sparse_tonal_report").read_bytes():
        raise ValueError("replayed sparse/tonal report differs")

    requirements = {row["requirement_id"]: row for row in report["requirements"]}
    next_gate = descriptor_report["decision"]["next_gate"]
    requirements["truth_bearing_source_manifest_feasible_and_frozen"].update({
        "state": "sparse_tonal_descriptor_rules_frozen_exact_member_contrasts_selection_assignment_and_allocation_unfrozen",
        "satisfied": False,
        "evidence": ["predecessor_audit.requirements.truth_bearing_source_manifest", "sparse_tonal_descriptor.execution", "sparse_tonal_descriptor.synthetic_fixture_results", "sparse_tonal_descriptor.decision", "sparse_tonal_descriptor.claim_boundary"],
        "reason": "Time-occupancy, spectral-concentration, abstention and non-overlap rules are frozen before candidate access, and all three synthetic structure gates pass. No exact member was selected or read, synthetic fixtures are not source evidence, TinySOL metadata does not establish the sparse non-tonal contrast, and no trait or partition was assigned.",
        "next_gate": next_gate,
    })
    requirements["difficult_natural_and_production_negatives_preserved_in_evaluation"].update({
        "state": "sparse_tonal_measurement_ready_exact_contrasts_and_evaluation_missing",
        "satisfied": False,
        "evidence": ["predecessor_audit.requirements.difficult_negatives", "sparse_tonal_descriptor.synthetic_fixture_results", "sparse_tonal_descriptor.decision", "sparse_tonal_descriptor.claim_boundary"],
        "reason": "The sparse and tonal technical measurement is preregistered, but no real exact-member contrast or evaluation allocation exists. Quiet, clipped, source relationship and production-negative gates retain their predecessor boundaries.",
        "next_gate": next_gate,
    })
    satisfied = sum(row["satisfied"] for row in report["requirements"])
    if satisfied != 4 or all(row["satisfied"] for row in report["requirements"]):
        raise ValueError("descriptor freeze unexpectedly promoted completion")
    report.update({
        "report_id": REPORT_ID,
        "state": "objective_incomplete_sparse_tonal_descriptor_freeze_reconciled_without_source_or_scientific_promotion",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
    })
    report["summary"].update({
        "satisfied_count": 4,
        "unsatisfied_count": 10,
        "objective_complete": False,
        "sparse_tonal_descriptor_rules_frozen": True,
        "sparse_tonal_synthetic_fixture_gate_count": 3,
        "sparse_tonal_synthetic_fixture_gate_pass_count": 3,
        "independent_sparse_and_tonal_contrasts_established": False,
        "source_trait_manifest_frozen": False,
        "nearest_authority_dependent_decisions": [next_gate, report["requirements"][4].get("next_gate"), report["requirements"][5].get("next_gate")],
    })
    report["evidence_checks"].update({
        "sparse_tonal_descriptor_rules_frozen": True,
        "sparse_tonal_synthetic_fixture_gate_count": 3,
        "sparse_tonal_synthetic_fixture_gate_pass_count": 3,
        "sparse_tonal_candidate_audio_accessed": False,
        "sparse_tonal_exact_member_selected": False,
        "independent_sparse_and_tonal_contrasts_established": False,
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
