#!/usr/bin/env python3
"""Refresh objective audit after sparse/tonal exact-member confirmation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/objective-completion-audit-plan-20260819-014.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-objective-completion-audit-20260819-014.json"
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260819-014"
REPORT_ID = PLAN_ID
EXPECTED_BINDINGS = {
    "confirmation_audit",
    "confirmation_plan",
    "confirmation_report",
    "confirmation_runner",
    "confirmation_validator",
    "predecessor_audit_implementation",
    "predecessor_audit_plan",
    "predecessor_audit_report",
    "selection_plan",
    "selection_report",
}
NEXT_GATE = (
    "Freeze a new metadata-only sparse non-tonal successor selection checkpoint. "
    "Preserve this abstention; do not alter thresholds or substitute inside the observed checkpoint. "
    "Before any successor audio access, bind exact-member rights, original-lossless provenance, "
    "capture and transformation history, and the same frozen descriptor."
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
    if plan.get("state") != "score_blind_completion_audit_refresh_after_sparse_tonal_exact_member_confirmation":
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
        "exact_member_confirmation_reconciliation_authorized",
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
    for key in (
        "abstaining_candidate_may_be_reclassified",
        "exact_member_descriptor_confirmation_counts_as_trait_assignment",
        "one_confirmed_contrast_counts_as_independent_sparse_tonal_pair",
    ):
        if policy.get(key) is not False:
            errors.append(f"promotion boundary differs: {key}")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def _verify_bound_inputs(plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    selection_plan = load_json(_bound(plan, "selection_plan"))
    selection_report = load_json(_bound(plan, "selection_report"))
    confirmation_plan = load_json(_bound(plan, "confirmation_plan"))
    confirmation_report = load_json(_bound(plan, "confirmation_report"))
    confirmation_audit = load_json(_bound(plan, "confirmation_audit"))

    runner = _load_module(_bound(plan, "confirmation_runner"), "sparse_tonal_confirmation")
    runner_errors = runner.validate_plan(confirmation_plan)
    if runner_errors:
        raise ValueError("confirmation plan invalid: " + "; ".join(runner_errors))
    validator = _load_module(_bound(plan, "confirmation_validator"), "sparse_tonal_confirmation_validator")
    report_errors = validator.validate_report(confirmation_report, confirmation_plan)
    audit_errors = validator.validate_audit(confirmation_audit, confirmation_report)
    if report_errors or audit_errors:
        raise ValueError("confirmation audit invalid: " + "; ".join(report_errors + audit_errors))

    selected_ids = {row["exact_member_id"] for row in selection_report["selected_candidates"]}
    confirmation_ids = {row["exact_member_id"] for row in confirmation_plan["members"]}
    observed_ids = {row["exact_member_id"] for row in confirmation_report["source_observations"]}
    if selected_ids != confirmation_ids or confirmation_ids != observed_ids:
        raise ValueError("selected, bound and observed exact-member identities differ")
    if selection_report.get("plan_id") != selection_plan.get("plan_id"):
        raise ValueError("selection report is not bound to the selection plan")

    observations = {row["exact_member_id"]: row for row in confirmation_report["source_observations"]}
    freesound = observations["freesound_sound_856645"]
    tinysol = observations["tinysol_6_0__ob_ord_dsharp4_mf_n_n"]
    if freesound["descriptor_confirmation_passed"] is not False:
        raise ValueError("sparse candidate outcome differs")
    if not all(channel["abstain"] is True for channel in freesound["measurement"]["channel_descriptors"]):
        raise ValueError("sparse candidate abstention differs")
    if tinysol["descriptor_confirmation_passed"] is not True:
        raise ValueError("tonal candidate outcome differs")
    decision = confirmation_report["decision"]
    if decision != {
        "all_exact_member_descriptor_confirmations_passed": False,
        "candidate_replacement_performed": False,
        "descriptor_confirmation_complete": True,
        "source_manifest_allocated": False,
        "source_trait_assignment_complete": False,
        "thresholds_changed_after_observation": False,
    }:
        raise ValueError("confirmation decision differs")
    return confirmation_report, confirmation_audit


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    predecessor = _load_module(_bound(plan, "predecessor_audit_implementation"), "objective_v13")
    predecessor_plan_path = _bound(plan, "predecessor_audit_plan")
    report = predecessor.build_report(predecessor.load_json(predecessor_plan_path), predecessor_plan_path)
    if canonical_json_bytes(report) != _bound(plan, "predecessor_audit_report").read_bytes():
        raise ValueError("replayed predecessor differs")
    confirmation, confirmation_audit = _verify_bound_inputs(plan)

    requirements = {row["requirement_id"]: row for row in report["requirements"]}
    requirements["truth_bearing_source_manifest_feasible_and_frozen"].update({
        "state": "tonal_non_sparse_exact_contrast_confirmed_sparse_non_tonal_candidate_abstained_successor_and_manifest_unfrozen",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.truth_bearing_source_manifest",
            "sparse_tonal_exact_member_confirmation.source_observations",
            "sparse_tonal_exact_member_confirmation.decision",
            "sparse_tonal_exact_member_confirmation_audit.gates",
            "sparse_tonal_exact_member_confirmation_audit.decision",
        ],
        "reason": "The bound TinySOL exact member passed the frozen tonal non-sparse descriptor. The bound Freesound candidate abstained with three active time blocks and a tonal spectrum, so it did not establish the sparse non-tonal contrast. The two private replays were byte-identical and independently projected into a path-free, hash-redacted public result. No threshold changed, trait was assigned, relationship was promoted or manifest was allocated.",
        "next_gate": NEXT_GATE,
    })
    requirements["difficult_natural_and_production_negatives_preserved_in_evaluation"].update({
        "state": "one_exact_tonal_contrast_confirmed_sparse_successor_and_evaluation_allocation_missing",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.difficult_negatives",
            "sparse_tonal_exact_member_confirmation.source_observations",
            "sparse_tonal_exact_member_confirmation.decision",
            "sparse_tonal_exact_member_confirmation_audit.decision",
        ],
        "reason": "One exact tonal non-sparse contrast is technically confirmed, but the sparse non-tonal candidate abstained and neither contrast has been assigned to a source-trait manifest or evaluation partition. Quiet, clipped, source-relationship and production-negative gates retain their predecessor boundaries.",
        "next_gate": NEXT_GATE,
    })
    satisfied = sum(row["satisfied"] for row in report["requirements"])
    if satisfied != 4 or all(row["satisfied"] for row in report["requirements"]):
        raise ValueError("exact-member confirmation unexpectedly promoted completion")

    report.update({
        "report_id": REPORT_ID,
        "state": "objective_incomplete_sparse_tonal_exact_member_negative_reconciled_without_trait_or_scientific_promotion",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
    })
    report["summary"].update({
        "satisfied_count": 4,
        "unsatisfied_count": 10,
        "objective_complete": False,
        "sparse_tonal_exact_member_confirmation_complete": True,
        "sparse_tonal_exact_member_count": confirmation["execution"]["exact_member_count"],
        "sparse_tonal_exact_member_confirmation_pass_count": 1,
        "sparse_non_tonal_candidate_abstained": True,
        "tonal_non_sparse_candidate_confirmed": True,
        "independent_sparse_and_tonal_contrasts_established": False,
        "source_trait_manifest_frozen": False,
        "nearest_authority_dependent_decisions": [
            NEXT_GATE,
            requirements["perceptual_metric_execution_and_legal_gate_passed"].get("next_gate"),
            requirements["deterministic_human_calibrated_full_reference_oracle_passed"].get("next_gate"),
        ],
    })
    report["evidence_checks"].update({
        "sparse_tonal_candidate_audio_accessed": True,
        "sparse_tonal_exact_member_selected": True,
        "sparse_tonal_exact_member_confirmation_complete": True,
        "sparse_tonal_exact_member_count": 2,
        "sparse_tonal_exact_member_confirmation_pass_count": 1,
        "sparse_non_tonal_candidate_abstained": True,
        "tonal_non_sparse_candidate_confirmed": True,
        "sparse_tonal_private_replays_byte_identical": confirmation["execution"]["private_reports_byte_identical"],
        "sparse_tonal_public_projection_independently_audited": (
            confirmation_audit["gates"]["attribution_attachment_matches_plan"]
            and confirmation_audit["gates"]["private_audio_hashes_well_formed"]
            and confirmation_audit["gates"]["private_public_projection_exact"]
            and confirmation_audit["gates"]["private_replays_byte_identical"]
            and confirmation_audit["gates"]["public_report_path_free_and_audio_hash_redacted"]
            and confirmation_audit["gates"]["public_report_validation_errors"] == []
        ),
        "new_exact_member_selected": True,
        "new_source_audio_accessed": True,
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
