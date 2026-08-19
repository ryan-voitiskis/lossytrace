#!/usr/bin/env python3
"""Refresh the objective audit after the sparse metadata v4 bounded negative."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/objective-completion-audit-plan-20260819-020.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-objective-completion-audit-20260819-020.json"
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260819-020"
REPORT_ID = PLAN_ID
EXPECTED_BINDINGS = {
    "metadata_result_implementation",
    "metadata_result_plan",
    "metadata_result_report",
    "metadata_result_validator",
    "predecessor_audit_implementation",
    "predecessor_audit_plan",
    "predecessor_audit_report",
}
TRUE_AUTHORIZATIONS = {
    "bound_committed_evidence_read_authorized",
    "metadata_negative_reconciliation_authorized",
    "synthetic_audit_execution_authorized",
}
NEXT_GATE = (
    "Choose whether to authorize and freeze a materially different controlled-source construction or recording route with independent "
    "trait adjudication, or terminate source-manifest feasibility as a rigorous negative. Do not repeat the exhausted metadata-only "
    "search or access another candidate audio file under this checkpoint."
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
    if plan.get("state") != "score_blind_completion_audit_refresh_after_sparse_non_tonal_metadata_v4_bounded_negative":
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
        "further_audio_sample_access_authorized",
        "human_collection_authorized",
        "no_reference_training_authorized",
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
        "metadata_only_candidate_rejection_counts_as_scientific_coverage": False,
        "repeating_same_metadata_route_after_bounded_negative_is_justified": False,
        "source_trait_manifest_requires_assignments_relationships_and_allocation": True,
    }:
        errors.append("completion policy differs")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def _verify_metadata_result(plan: dict[str, Any]) -> dict[str, Any]:
    metadata_plan = load_json(_bound(plan, "metadata_result_plan"))
    validator = _load_module(_bound(plan, "metadata_result_validator"), "metadata_v4_plan")
    validation_errors = validator.validate_plan(metadata_plan)
    if validation_errors:
        raise ValueError("metadata plan invalid: " + "; ".join(validation_errors))
    result = _load_module(_bound(plan, "metadata_result_implementation"), "metadata_v4_result")
    report = result.build_report(metadata_plan, _bound(plan, "metadata_result_plan"))
    if result.canonical_json_bytes(report) != _bound(plan, "metadata_result_report").read_bytes():
        raise ValueError("replayed metadata result differs")
    if report["audio_accessed"] is not False or report["decision"] != {
        "bounded_negative_preserved": True,
        "eligible_successor_count": 0,
        "metadata_nomination_is_descriptor_evidence": False,
        "metadata_nomination_is_source_trait_truth": False,
        "next_gate": "Reconcile this bounded negative in the objective audit before selecting a materially different source route; do not repeat the same metadata search or access candidate audio.",
        "nominated_exact_member_id": None,
        "search_exhausted_without_eligible_member": True,
        "source_manifest_allocated": False,
        "source_trait_assigned": False,
        "thresholds_changed_after_observation": False,
    }:
        raise ValueError("metadata result boundary differs")
    return report


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    predecessor = _load_module(_bound(plan, "predecessor_audit_implementation"), "objective_v19")
    predecessor_plan_path = _bound(plan, "predecessor_audit_plan")
    report = predecessor.build_report(predecessor.load_json(predecessor_plan_path), predecessor_plan_path)
    if predecessor.canonical_json_bytes(report) != _bound(plan, "predecessor_audit_report").read_bytes():
        raise ValueError("replayed predecessor differs")
    metadata = _verify_metadata_result(plan)

    requirements = {row["requirement_id"]: row for row in report["requirements"]}
    requirements["truth_bearing_source_manifest_feasible_and_frozen"].update({
        "state": "tonal_contrast_confirmed_three_sparse_exact_candidates_failed_narrow_metadata_route_exhausted_manifest_unfrozen",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.truth_bearing_source_manifest",
            "metadata_search_v4_result.record_dispositions",
            "metadata_search_v4_result.decision",
            "metadata_search_v4_result.execution",
        ],
        "reason": "After three exact sparse non-tonal candidates failed the unchanged descriptor, the separately frozen v4 metadata search executed all eight declared queries and rejected all three distinct primary records before audio access. None met the isolated lossless one-shot, quiet-context, capture-chain and transformation-history prerequisites. Repeating the same metadata route is not justified; assignment, relationships and manifest allocation remain unfrozen.",
        "next_gate": NEXT_GATE,
    })
    requirements["difficult_natural_and_production_negatives_preserved_in_evaluation"].update({
        "state": "one_exact_tonal_contrast_confirmed_three_sparse_failures_and_bounded_metadata_negative_preserved_evaluation_unallocated",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.difficult_negatives",
            "metadata_search_v4_result.record_dispositions",
            "metadata_search_v4_result.decision",
        ],
        "reason": "The exact tonal non-sparse contrast, all three failed sparse candidates and the v4 bounded metadata negative remain preserved without reclassification. No independent sparse contrast exists and no contrast is assigned or allocated to scientific evaluation.",
        "next_gate": NEXT_GATE,
    })
    satisfied = sum(row["satisfied"] for row in report["requirements"])
    if satisfied != 4 or all(row["satisfied"] for row in report["requirements"]):
        raise ValueError("metadata negative unexpectedly promoted completion")

    report.update({
        "implementation_sha256": sha256_file(Path(__file__)),
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "report_id": REPORT_ID,
        "state": "objective_incomplete_sparse_metadata_v4_bounded_negative_reconciled_without_audio_or_scientific_promotion",
    })
    report["summary"].update({
        "independent_sparse_and_tonal_contrasts_established": False,
        "nearest_authority_dependent_decisions": [
            NEXT_GATE,
            requirements["perceptual_metric_execution_and_legal_gate_passed"].get("next_gate"),
            requirements["deterministic_human_calibrated_full_reference_oracle_passed"].get("next_gate"),
        ],
        "objective_complete": False,
        "satisfied_count": 4,
        "source_trait_manifest_frozen": False,
        "sparse_non_tonal_metadata_search_v4_audio_accessed": False,
        "sparse_non_tonal_metadata_search_v4_bounded_negative": True,
        "sparse_non_tonal_metadata_search_v4_complete": True,
        "sparse_non_tonal_metadata_search_v4_eligible_successor_count": 0,
        "sparse_non_tonal_metadata_search_v4_primary_record_count": len(metadata["record_dispositions"]),
        "sparse_non_tonal_successor_v4_selected": False,
        "unsatisfied_count": 10,
    })
    report["evidence_checks"].update({
        "independent_sparse_and_tonal_contrasts_established": False,
        "source_manifest_allocation_performed": False,
        "source_trait_assignment_performed": False,
        "source_trait_manifest_frozen": False,
        "sparse_non_tonal_metadata_search_v4_audio_accessed": False,
        "sparse_non_tonal_metadata_search_v4_bounded_negative": True,
        "sparse_non_tonal_metadata_search_v4_complete": True,
        "sparse_non_tonal_metadata_search_v4_discovery_query_count": metadata["execution"]["discovery_query_count_executed"],
        "sparse_non_tonal_metadata_search_v4_eligible_successor_count": 0,
        "sparse_non_tonal_metadata_search_v4_primary_record_count": len(metadata["record_dispositions"]),
        "sparse_non_tonal_successor_v4_selected": False,
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
