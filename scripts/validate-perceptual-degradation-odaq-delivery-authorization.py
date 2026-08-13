#!/usr/bin/env python3
"""Validate the pending ODAQ clean-reference delivery authorization gate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "odaq-reference-delivery-execution-plan.json"
)
AUTHORIZATION_ID = re.compile(
    r"^perceptual-degradation-odaq-reference-delivery-authorization-\d{8}-\d{3}$"
)
CANONICAL_DECISION = (
    "Authorize reading only the 16 retained ODAQ clean references and projecting "
    "them into deterministic canonical integer-PCM private delivery copies under "
    "the frozen preparation and execution plans, including two byte-identical "
    "private replays and attribution attachment. Do not authorize ODAQ processed "
    "conditions, scores, metrics, degradation ratings, listener collection, sealed "
    "evidence, or public verdicts."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _validate_binding(binding_id: str, binding: Any, errors: list[str]) -> None:
    if not isinstance(binding, dict):
        errors.append(f"invalid binding object: {binding_id}")
        return
    relative = Path(str(binding.get("path", "")))
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        errors.append(f"invalid repository-relative binding: {binding_id}")
        return
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing bound file: {binding_id}")
    elif sha256_file(path) != binding.get("sha256"):
        errors.append(f"bound file hash differs: {binding_id}")


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema version differs")
    if plan.get("plan_id") != "odaq-reference-delivery-execution-plan-20260813-001":
        errors.append("execution plan identity differs")
    if plan.get("state") != "execution_contract_frozen_responsible_human_authorization_pending":
        errors.append("execution plan state differs")

    expected_bindings = {
        "acquisition_result",
        "delivery_preparation",
        "playback_qualification_result",
        "attribution_audit",
        "projection_implementation",
        "authorization_schema",
        "authorization_validator",
        "authorization_tests",
        "authorization_report",
    }
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        errors.append("execution plan binding set differs")
    elif isinstance(bindings, dict):
        for binding_id, binding in bindings.items():
            _validate_binding(binding_id, binding, errors)

    evidence = plan.get("qualified_evidence", {})
    expected_evidence = {
        "retained_reference_count": 16,
        "retained_audio_bytes": 54_633_154,
        "retained_inventory_sha256": "d7f244da55b510b639300d55271b1ebd5fb9f7454b258bec30588bf18eefde2f",
        "sample_rate_hz": 48_000,
        "channel_count": 2,
        "float32_reference_count": 7,
        "extensible_s24_reference_count": 9,
        "attribution_notice_ready_source_count": 16,
        "physical_playback_chain_qualified": True,
        "perceptual_truth_collected": False,
    }
    if evidence != expected_evidence:
        errors.append("qualified evidence differs")

    gate = plan.get("authorization_gate", {})
    if gate != {
        "responsible_human_authorization_present": False,
        "committed_successor_authorization_path": None,
        "authorization_schema_frozen": True,
        "live_runner_implementation_authorized": False,
        "retained_reference_read_authorized": False,
        "retained_reference_projection_authorized": False,
    }:
        errors.append("pending authorization gate differs")

    execution = plan.get("future_execution_constraints", {})
    if execution != expected_execution_constraints():
        errors.append("future execution constraints differ")

    for key, expected in {
        "synthetic_authorization_fixture_validation_authorized": True,
        "retained_reference_access_authorized": False,
        "retained_reference_projection_authorized": False,
        "processed_condition_access_authorized": False,
        "listening_score_access_authorized": False,
        "perceptual_metric_execution_authorized": False,
        "degradation_rating_collection_authorized": False,
        "listener_response_collection_authorized": False,
        "sealed_evidence_access_authorized": False,
        "public_verdict_authorized": False,
    }.items():
        if plan.get("access_boundary", {}).get(key) is not expected:
            errors.append(f"access boundary differs: {key}")

    if plan.get("canonical_authorization_decision") != CANONICAL_DECISION:
        errors.append("canonical authorization decision differs")
    if plan.get("authorized_next_step") != (
        "Obtain and commit the responsible-human successor authorization matching "
        "the frozen schema. Until then, do not implement or execute a live retained-"
        "audio runner and do not read or project any retained ODAQ reference."
    ):
        errors.append("authorized next step differs")
    serialized = json.dumps(plan, sort_keys=True)
    if "/Users/" in serialized or "Application Support" in serialized:
        errors.append("execution plan must not contain a private absolute path")
    return errors


def expected_execution_constraints() -> dict[str, Any]:
    return {
        "maximum_workers": 1,
        "minimum_free_disk_gib": 15,
        "private_paths_outside_repository": True,
        "source_inventory_reverified_before_projection": True,
        "atomic_partial_then_rename": True,
        "journaled_resume": True,
        "two_fresh_output_roots": True,
        "replay_inventories_byte_identical": True,
        "per_reference_attribution_record_ids_attached_out_of_band": True,
        "public_report_paths_redacted": True,
        "public_report_per_reference_hashes_redacted": True,
    }


def expected_authorization_scope(plan: dict[str, Any]) -> dict[str, Any]:
    evidence = plan["qualified_evidence"]
    return {
        "retained_reference_count": evidence["retained_reference_count"],
        "retained_inventory_sha256": evidence["retained_inventory_sha256"],
        "retained_reference_access_authorized": True,
        "retained_reference_projection_authorized": True,
        "private_delivery_copy_creation_authorized": True,
        "two_fresh_private_replays_authorized": True,
        "attribution_attachment_authorized": True,
        "provider_processed_condition_access_authorized": False,
        "provider_listening_score_access_authorized": False,
        "perceptual_metric_execution_authorized": False,
        "degradation_rating_collection_authorized": False,
        "listener_response_collection_authorized": False,
        "sealed_evidence_access_authorized": False,
        "public_verdict_authorized": False,
    }


def expected_claim_boundary() -> dict[str, bool]:
    return {
        "development_only": True,
        "one_provider_stratum": True,
        "projection_is_stimulus_generation": False,
        "projection_is_perceptual_truth": False,
        "projection_is_metric_execution": False,
        "independent_transfer_supported": False,
        "final_validation_supported": False,
    }


def expected_authorization_bindings(plan: dict[str, Any]) -> dict[str, Any]:
    bindings = plan["bindings"]
    selected = {
        key: copy.deepcopy(bindings[key])
        for key in (
            "acquisition_result",
            "delivery_preparation",
            "playback_qualification_result",
            "attribution_audit",
            "projection_implementation",
            "authorization_schema",
        )
    }
    selected["delivery_execution_plan"] = {
        "path": str(PLAN.relative_to(ROOT)),
        "sha256": sha256_file(PLAN),
    }
    return selected


def validate_authorization(
    authorization: dict[str, Any], plan: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    expected_keys = {
        "schema_version",
        "authorization_id",
        "authorized_on",
        "state",
        "responsible_human_authorization_present",
        "bindings",
        "authorization_scope",
        "execution_constraints",
        "claim_boundary",
        "canonical_decision",
    }
    if set(authorization) != expected_keys:
        errors.append("authorization field set differs")
    if authorization.get("schema_version") != 1:
        errors.append("authorization schema version differs")
    if not AUTHORIZATION_ID.fullmatch(str(authorization.get("authorization_id", ""))):
        errors.append("authorization identity differs")
    try:
        date.fromisoformat(str(authorization.get("authorized_on", "")))
    except ValueError:
        errors.append("authorization date differs")
    if authorization.get("state") != (
        "responsible_human_authorized_exact_clean_reference_projection_only"
    ):
        errors.append("authorization state differs")
    if authorization.get("responsible_human_authorization_present") is not True:
        errors.append("responsible-human authorization is absent")
    if authorization.get("bindings") != expected_authorization_bindings(plan):
        errors.append("authorization evidence bindings differ")
    if authorization.get("authorization_scope") != expected_authorization_scope(plan):
        errors.append("authorization scope differs")
    if authorization.get("execution_constraints") != expected_execution_constraints():
        errors.append("authorization execution constraints differ")
    if authorization.get("claim_boundary") != expected_claim_boundary():
        errors.append("authorization claim boundary differs")
    if authorization.get("canonical_decision") != CANONICAL_DECISION:
        errors.append("authorization canonical decision differs")
    serialized = json.dumps(authorization, sort_keys=True)
    if "/Users/" in serialized or "Application Support" in serialized:
        errors.append("authorization must not contain a private absolute path")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    validate_plan_parser = subcommands.add_parser("validate-plan")
    validate_plan_parser.add_argument("--plan", type=Path, default=PLAN)
    validate_authorization_parser = subcommands.add_parser("validate-authorization")
    validate_authorization_parser.add_argument("--plan", type=Path, default=PLAN)
    validate_authorization_parser.add_argument("--authorization", type=Path, required=True)
    args = parser.parse_args()

    plan = load_json(args.plan)
    errors = validate_plan(plan)
    if args.command == "validate-authorization" and not errors:
        errors.extend(validate_authorization(load_json(args.authorization), plan))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if args.command == "validate-plan":
        result = {
            "status": "delivery_authorization_contract_frozen_authorization_pending",
            "retained_reference_access_authorized": False,
        }
    else:
        result = {
            "status": "exact_clean_reference_projection_authorized",
            "authorization_sha256": sha256_file(args.authorization),
        }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
