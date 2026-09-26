#!/usr/bin/env python3
"""Refresh the objective audit after capture authority and live-intake readiness."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/objective-completion-audit-plan-20260819-022.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-objective-completion-audit-20260819-022.json"
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260819-022"
REPORT_ID = PLAN_ID
EXPECTED_BINDINGS = {
    "live_intake_implementation",
    "live_intake_plan",
    "predecessor_audit_implementation",
    "predecessor_audit_plan",
    "predecessor_audit_report",
}
TRUE_AUTHORIZATIONS = {
    "bound_committed_evidence_read_authorized",
    "clean_capture_authority_reconciliation_authorized",
    "live_intake_readiness_audit_authorized",
}
NEXT_GATE = (
    "Identify the exact physical microphone, preamp or recorder, channel mapping, firmware, gain, position, orientation, source "
    "distance and safe event choice privately. If the local RME input is proposed, establish the attached transducer and preamp; "
    "the built-in Apple microphone is ineligible absent proof that its complete chain is known and all processing is disabled. "
    "Then freeze a separate exact capture-execution checkpoint before recording or opening audio."
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
    if plan.get("state") != "score_blind_completion_audit_refresh_after_clean_capture_authority_and_live_intake_checkpoint":
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
    expected = TRUE_AUTHORIZATIONS | {
        "capture_execution_authorized_by_this_audit",
        "external_communication_authorized",
        "further_audio_sample_access_authorized",
        "human_collection_authorized",
        "no_reference_training_authorized",
        "payment_or_purchase_authorized",
        "perceptual_metric_execution_authorized",
        "public_verdict_enabled",
        "source_manifest_allocation_authorized",
        "source_trait_assignment_authorized",
    }
    if set(authorization) != expected:
        errors.append("authorization inventory differs")
    for key, value in authorization.items():
        if value is not (key in TRUE_AUTHORIZATIONS):
            errors.append(f"authorization differs: {key}")
    if plan.get("completion_policy") != {
        "all_requirements_must_be_satisfied": True,
        "authority_or_readiness_counts_as_scientific_coverage": False,
        "live_delivery_requires_a_private_manifest_and_two_replays": True,
        "source_trait_manifest_requires_assignments_relationships_and_allocation": True,
    }:
        errors.append("completion policy differs")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def _verify_live_intake_readiness(plan: dict[str, Any]) -> dict[str, Any]:
    live = _load_module(_bound(plan, "live_intake_implementation"), "clean_capture_live_intake")
    live_plan = live.load_json(_bound(plan, "live_intake_plan"))
    errors = live.validate_plan(live_plan)
    if errors:
        raise ValueError("live intake plan invalid: " + "; ".join(errors))
    authority = live_plan["authority_received"]
    if authority != {
        "authority_source": "explicit_user_instruction_2026-08-19",
        "one_safe_clean_capture_conduct_or_arrange_authorized": True,
        "outreach_authorized": False,
        "spending_authorized": False,
    }:
        raise ValueError("live intake authority differs")
    operational = live_plan["operational_authorization"]
    if operational["live_manifest_read_authorized"] is not True:
        raise ValueError("live manifest read authority differs")
    for key in (
        "audio_access_authorized",
        "capture_execution_authorized_by_this_checkpoint",
        "external_communication_authorized",
        "payment_or_purchase_authorized",
        "source_manifest_allocation_authorized",
        "source_trait_assignment_authorized",
    ):
        if operational[key] is not False:
            raise ValueError(f"live intake operational boundary differs: {key}")
    return live_plan


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    predecessor = _load_module(_bound(plan, "predecessor_audit_implementation"), "objective_v21")
    predecessor_plan_path = _bound(plan, "predecessor_audit_plan")
    report = predecessor.build_report(predecessor.load_json(predecessor_plan_path), predecessor_plan_path)
    if predecessor.canonical_json_bytes(report) != _bound(plan, "predecessor_audit_report").read_bytes():
        raise ValueError("replayed predecessor differs")
    live_plan = _verify_live_intake_readiness(plan)

    requirements = {row["requirement_id"]: row for row in report["requirements"]}
    requirements["truth_bearing_source_manifest_feasible_and_frozen"].update({
        "state": "one_safe_capture_authorized_live_intake_frozen_physical_chain_and_delivery_absent_manifest_unfrozen",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.truth_bearing_source_manifest",
            "live_clean_capture_intake_plan.authority_received",
            "live_clean_capture_intake_plan.execution_protocol",
            "live_clean_capture_intake_plan.operational_authorization",
        ],
        "reason": "Explicit user authority now permits one safe clean capture, and the live metadata intake checkpoint is frozen. Outreach and spending remain unauthorized. No exact physical microphone/preamp chain, live private manifest, accepted delivery, recording or audio observation exists, so authority and readiness are not source evidence, trait truth, relationship adjudication or manifest allocation.",
        "next_gate": NEXT_GATE,
    })
    requirements["difficult_natural_and_production_negatives_preserved_in_evaluation"].update({
        "state": "three_sparse_exact_failures_and_metadata_negative_preserved_safe_capture_authorized_but_unexecuted_evaluation_unallocated",
        "satisfied": False,
        "evidence": [
            "predecessor_audit.requirements.difficult_negatives",
            "live_clean_capture_intake_plan.claim_boundary",
        ],
        "reason": "The three exact sparse failures and bounded metadata negative remain preserved. Capture authority and a metadata-intake checkpoint do not supply a new natural source, independent contrast or evaluation allocation.",
        "next_gate": NEXT_GATE,
    })
    satisfied = sum(row["satisfied"] for row in report["requirements"])
    if satisfied != 4 or all(row["satisfied"] for row in report["requirements"]):
        raise ValueError("authority readiness unexpectedly promoted completion")

    report.update({
        "implementation_sha256": sha256_file(Path(__file__)),
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "report_id": REPORT_ID,
        "state": "objective_incomplete_safe_capture_authorized_live_intake_ready_without_physical_chain_delivery_or_audio",
    })
    report["summary"].update({
        "clean_capture_audio_accessed": False,
        "clean_capture_capture_executed": False,
        "clean_capture_external_communication_authorized": False,
        "clean_capture_live_delivery_accepted": False,
        "clean_capture_live_delivery_present": False,
        "clean_capture_live_intake_checkpoint_frozen": True,
        "clean_capture_live_manifest_read_authorized": True,
        "clean_capture_one_safe_capture_authorized": True,
        "clean_capture_payment_or_purchase_authorized": False,
        "clean_capture_physical_chain_complete": False,
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
        "clean_capture_audio_accessed": False,
        "clean_capture_capture_executed": False,
        "clean_capture_external_communication_authorized": False,
        "clean_capture_live_delivery_accepted": False,
        "clean_capture_live_delivery_present": False,
        "clean_capture_live_intake_checkpoint_frozen": True,
        "clean_capture_live_manifest_read_authorized": True,
        "clean_capture_one_safe_capture_authorized": True,
        "clean_capture_payment_or_purchase_authorized": False,
        "clean_capture_physical_chain_complete": False,
        "independent_sparse_and_tonal_contrasts_established": False,
        "source_manifest_allocation_performed": False,
        "source_trait_assignment_performed": False,
        "source_trait_manifest_frozen": False,
    })
    if live_plan["claim_boundary"]["full_objective_complete"] is not False:
        raise ValueError("live intake claim boundary differs")
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
