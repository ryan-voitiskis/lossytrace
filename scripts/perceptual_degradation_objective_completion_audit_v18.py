#!/usr/bin/env python3
"""Refresh objective audit after sparse successor v3 nomination and freeze."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/objective-completion-audit-plan-20260819-018.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-objective-completion-audit-20260819-018.json"
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260819-018"
REPORT_ID = PLAN_ID
EXPECTED_BINDINGS = {
    "confirmation_implementation",
    "confirmation_plan",
    "metadata_result_implementation",
    "metadata_result_report",
    "predecessor_audit_implementation",
    "predecessor_audit_plan",
    "predecessor_audit_report",
}
TRUE_AUTHORIZATIONS = {
    "bound_committed_evidence_read_authorized",
    "exact_member_confirmation_readiness_reconciliation_authorized",
    "metadata_nomination_reconciliation_authorized",
    "synthetic_audit_execution_authorized",
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
    if plan.get("state") != "score_blind_completion_audit_refresh_after_sparse_successor_v3_nomination_and_confirmation_freeze":
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
        "metadata_nomination_counts_as_scientific_coverage": False,
        "source_trait_manifest_requires_assignments_relationships_and_allocation": True,
        "technical_descriptor_confirmation_is_not_perceptual_truth": True,
    }:
        errors.append("completion policy differs")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    predecessor = _load_module(_bound(plan, "predecessor_audit_implementation"), "objective_v17")
    predecessor_plan_path = _bound(plan, "predecessor_audit_plan")
    report = predecessor.build_report(predecessor.load_json(predecessor_plan_path), predecessor_plan_path)
    if predecessor.canonical_json_bytes(report) != _bound(plan, "predecessor_audit_report").read_bytes():
        raise ValueError("replayed predecessor differs")

    metadata = _load_module(_bound(plan, "metadata_result_implementation"), "metadata_search_v3_result")
    metadata_plan_path = metadata.PLAN_PATH
    metadata_report = metadata.build_report(metadata.load_json(metadata_plan_path), metadata_plan_path)
    if metadata.canonical_json_bytes(metadata_report) != _bound(plan, "metadata_result_report").read_bytes():
        raise ValueError("replayed metadata result differs")
    if metadata_report["decision"]["eligible_successor_count"] != 1 or metadata_report["audio_accessed"] is not False:
        raise ValueError("metadata result did not nominate exactly one unopened successor")

    confirmation = _load_module(_bound(plan, "confirmation_implementation"), "sparse_confirmation_v3")
    confirmation_plan = confirmation.load_json(_bound(plan, "confirmation_plan"))
    confirmation_errors = confirmation.validate_plan(confirmation_plan)
    if confirmation_errors:
        raise ValueError("confirmation plan differs: " + "; ".join(confirmation_errors))
    exact_member_id = metadata_report["decision"]["nominated_exact_member_id"]
    if confirmation_plan["member"]["exact_member_id"] != exact_member_id:
        raise ValueError("confirmation member differs from metadata nomination")

    next_gate = (
        "Pass exact-head CI for the frozen one-member v3 checkpoint, then acquire only Freesound sound 476736 through the official "
        "authenticated original-download route and run two one-worker private descriptor replays without playback or derived PCM retention."
    )
    requirements = {row["requirement_id"]: row for row in report["requirements"]}
    requirements["truth_bearing_source_manifest_feasible_and_frozen"].update({
        "state": "tonal_contrast_confirmed_third_sparse_successor_metadata_nominated_confirmation_frozen_audio_unopened_manifest_unfrozen",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.truth_bearing_source_manifest",
            "metadata_search_v3_result.record_dispositions",
            "metadata_search_v3_result.selected_candidate_metadata",
            "exact_member_confirmation_v3_plan",
        ],
        "reason": "The bounded text-only v3 search preserved both failed exact sparse candidates and stopped after Freesound sound 476736 met the narrower unchanged-descriptor metadata prerequisites. A one-member integer-PCM confirmation checkpoint is frozen. The provider original has not been acquired or measured, metadata is not descriptor evidence or trait truth, and assignment, relationships and manifest allocation remain unfrozen.",
        "next_gate": next_gate,
    })
    requirements["difficult_natural_and_production_negatives_preserved_in_evaluation"].update({
        "state": "tonal_exact_contrast_confirmed_third_sparse_successor_nominated_confirmation_pending_evaluation_unallocated",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.difficult_negatives",
            "metadata_search_v3_result.selected_candidate_metadata",
            "exact_member_confirmation_v3_plan",
        ],
        "reason": "The tonal non-sparse technical contrast remains confirmed and a third sparse non-tonal candidate is metadata-qualified, but its descriptor has not run and neither contrast is assigned or allocated to scientific evaluation.",
        "next_gate": next_gate,
    })
    satisfied = sum(row["satisfied"] for row in report["requirements"])
    if satisfied != 4 or all(row["satisfied"] for row in report["requirements"]):
        raise ValueError("readiness unexpectedly promoted objective completion")

    report.update({
        "implementation_sha256": sha256_file(Path(__file__)),
        "new_candidate_audio_accessed": False,
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "report_id": REPORT_ID,
        "state": "objective_incomplete_third_sparse_successor_nominated_confirmation_checkpoint_frozen_audio_unopened",
    })
    report["summary"].update({
        "independent_sparse_and_tonal_contrasts_established": False,
        "nearest_authority_dependent_decisions": [
            next_gate,
            requirements["perceptual_metric_execution_and_legal_gate_passed"].get("next_gate"),
            requirements["deterministic_human_calibrated_full_reference_oracle_passed"].get("next_gate"),
        ],
        "objective_complete": False,
        "satisfied_count": 4,
        "source_trait_manifest_frozen": False,
        "sparse_non_tonal_eligible_successor_v3_count": 1,
        "sparse_non_tonal_exact_member_confirmation_v3_audio_accessed": False,
        "sparse_non_tonal_exact_member_confirmation_v3_plan_frozen": True,
        "sparse_non_tonal_metadata_search_v3_distinct_primary_record_count": 11,
        "sparse_non_tonal_metadata_search_v3_primary_record_timeout_count": 6,
        "sparse_non_tonal_successor_v3_selected": True,
        "unsatisfied_count": 10,
    })
    report["evidence_checks"].update({
        "independent_sparse_and_tonal_contrasts_established": False,
        "source_manifest_allocation_performed": False,
        "source_trait_assignment_performed": False,
        "source_trait_manifest_frozen": False,
        "sparse_non_tonal_eligible_successor_v3_count": 1,
        "sparse_non_tonal_exact_member_confirmation_v3_audio_accessed": False,
        "sparse_non_tonal_exact_member_confirmation_v3_complete": False,
        "sparse_non_tonal_exact_member_confirmation_v3_plan_frozen": True,
        "sparse_non_tonal_metadata_search_v3_audio_accessed": False,
        "sparse_non_tonal_metadata_search_v3_complete": True,
        "sparse_non_tonal_metadata_search_v3_discovery_query_count": 8,
        "sparse_non_tonal_metadata_search_v3_distinct_primary_record_count": 11,
        "sparse_non_tonal_metadata_search_v3_primary_record_timeout_count": 6,
        "sparse_non_tonal_previous_negatives_preserved": True,
        "sparse_non_tonal_successor_v3_selected": True,
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
