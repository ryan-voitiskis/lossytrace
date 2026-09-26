#!/usr/bin/env python3
"""Refresh the objective audit after sparse non-tonal confirmation v2."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/objective-completion-audit-plan-20260819-017.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-objective-completion-audit-20260819-017.json"
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260819-017"
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
}
TRUE_AUTHORIZATIONS = {
    "bound_committed_evidence_read_authorized",
    "exact_member_confirmation_reconciliation_authorized",
    "synthetic_audit_execution_authorized",
}
NEXT_GATE = (
    "Freeze a new metadata-only sparse non-tonal successor search. Preserve both failed exact candidates and the unchanged descriptor; "
    "before any further audio access, bind a distinct exact member with permissive rights, provider-original lossless provenance, a complete "
    "capture and transformation history, and a separate one-member confirmation checkpoint."
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
    if plan.get("state") != "score_blind_completion_audit_refresh_after_sparse_non_tonal_exact_member_v2_class_mismatch":
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
        "failed_exact_member_must_be_preserved": True,
        "source_trait_manifest_requires_assignments_relationships_and_allocation": True,
        "technical_descriptor_confirmation_is_not_perceptual_truth": True,
    }:
        errors.append("completion policy differs")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def _verify_confirmation(plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    confirmation_plan = load_json(_bound(plan, "confirmation_plan"))
    confirmation_report = load_json(_bound(plan, "confirmation_report"))
    confirmation_audit = load_json(_bound(plan, "confirmation_audit"))
    runner = _load_module(_bound(plan, "confirmation_runner"), "sparse_non_tonal_confirmation_v2")
    runner_errors = runner.validate_plan(confirmation_plan)
    if runner_errors:
        raise ValueError("confirmation plan invalid: " + "; ".join(runner_errors))
    validator = _load_module(_bound(plan, "confirmation_validator"), "sparse_non_tonal_confirmation_v2_validator")
    report_errors = validator.validate_report(confirmation_report, confirmation_plan)
    audit_errors = validator.validate_audit(confirmation_audit, confirmation_report)
    if report_errors or audit_errors:
        raise ValueError("confirmation audit invalid: " + "; ".join(report_errors + audit_errors))
    if confirmation_report["nominated_exact_member_id"] != confirmation_plan["member"]["exact_member_id"]:
        raise ValueError("bound and observed exact-member identities differ")
    if confirmation_report["decision"] != {
        "candidate_replacement_performed": False,
        "descriptor_confirmation_complete": True,
        "descriptor_confirmation_passed": False,
        "source_manifest_allocated": False,
        "source_trait_assignment_complete": False,
        "terminal_outcome": "class_mismatch",
        "thresholds_changed_after_observation": False,
    }:
        raise ValueError("confirmation decision differs")
    if confirmation_audit["decision"]["rigorous_negative_preserved"] is not True:
        raise ValueError("confirmation negative was not preserved")
    return confirmation_report, confirmation_audit


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    predecessor = _load_module(_bound(plan, "predecessor_audit_implementation"), "objective_v16")
    predecessor_plan_path = _bound(plan, "predecessor_audit_plan")
    report = predecessor.build_report(predecessor.load_json(predecessor_plan_path), predecessor_plan_path)
    if predecessor.canonical_json_bytes(report) != _bound(plan, "predecessor_audit_report").read_bytes():
        raise ValueError("replayed predecessor differs")
    confirmation, confirmation_audit = _verify_confirmation(plan)

    requirements = {row["requirement_id"]: row for row in report["requirements"]}
    requirements["truth_bearing_source_manifest_feasible_and_frozen"].update({
        "state": "tonal_non_sparse_exact_contrast_confirmed_second_sparse_non_tonal_candidate_class_mismatch_successor_and_manifest_unfrozen",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.truth_bearing_source_manifest",
            "sparse_non_tonal_exact_member_confirmation_v2.decision",
            "sparse_non_tonal_exact_member_confirmation_v2.execution",
            "sparse_non_tonal_exact_member_confirmation_v2_audit.gates",
            "sparse_non_tonal_exact_member_confirmation_v2_audit.decision",
        ],
        "reason": "Freesound sound 703342 matched the precommitted provider-original container and completed two byte-identical private replays, but it returned a class mismatch under the unchanged sparse non-tonal descriptor. The independent audit verified the private predicates and exact redacted public terminal result. The candidate was not replaced, no threshold changed, and assignment, relationships and manifest allocation remain unfrozen.",
        "next_gate": NEXT_GATE,
    })
    requirements["difficult_natural_and_production_negatives_preserved_in_evaluation"].update({
        "state": "one_exact_tonal_contrast_confirmed_two_sparse_candidates_failed_successor_and_evaluation_allocation_missing",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.difficult_negatives",
            "sparse_non_tonal_exact_member_confirmation_v2.decision",
            "sparse_non_tonal_exact_member_confirmation_v2_audit.decision",
        ],
        "reason": "The exact tonal non-sparse contrast remains technically confirmed, while the first sparse candidate abstained and the second produced a class mismatch. Neither contrast is assigned or allocated to scientific evaluation, and the negative candidates remain preserved without post-observation reclassification.",
        "next_gate": NEXT_GATE,
    })
    satisfied = sum(row["satisfied"] for row in report["requirements"])
    if satisfied != 4 or all(row["satisfied"] for row in report["requirements"]):
        raise ValueError("exact-member class mismatch unexpectedly promoted completion")

    report.update({
        "implementation_sha256": sha256_file(Path(__file__)),
        "new_candidate_audio_accessed": True,
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "report_id": REPORT_ID,
        "state": "objective_incomplete_second_sparse_candidate_class_mismatch_reconciled_without_trait_or_scientific_promotion",
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
        "sparse_non_tonal_exact_member_confirmation_v2_audio_accessed": True,
        "sparse_non_tonal_exact_member_confirmation_v2_complete": True,
        "sparse_non_tonal_exact_member_confirmation_v2_passed": False,
        "sparse_non_tonal_exact_member_confirmation_v2_terminal_outcome": "class_mismatch",
        "sparse_non_tonal_failed_exact_candidate_count": 2,
        "unsatisfied_count": 10,
    })
    gates = confirmation_audit["gates"]
    report["evidence_checks"].update({
        "independent_sparse_and_tonal_contrasts_established": False,
        "new_source_audio_accessed": True,
        "source_manifest_allocation_performed": False,
        "source_trait_assignment_performed": False,
        "source_trait_manifest_frozen": False,
        "sparse_non_tonal_exact_member_confirmation_v2_audio_accessed": True,
        "sparse_non_tonal_exact_member_confirmation_v2_complete": True,
        "sparse_non_tonal_exact_member_confirmation_v2_pass_count": 0,
        "sparse_non_tonal_exact_member_confirmation_v2_plan_frozen": True,
        "sparse_non_tonal_exact_member_confirmation_v2_terminal_class_mismatch": True,
        "sparse_non_tonal_exact_member_confirmation_v2_private_replays_byte_identical": confirmation["execution"]["private_reports_byte_identical"],
        "sparse_non_tonal_exact_member_confirmation_v2_public_projection_independently_audited": (
            gates["attribution_attachment_matches_plan"]
            and gates["private_audio_hashes_well_formed"]
            and gates["private_public_projection_exact"]
            and gates["private_replays_byte_identical"]
            and gates["public_report_path_measurement_and_audio_hash_redacted"]
            and gates["public_report_validation_errors"] == []
        ),
        "sparse_non_tonal_failed_exact_candidate_count": 2,
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
