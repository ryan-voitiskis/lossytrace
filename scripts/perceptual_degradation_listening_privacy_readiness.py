#!/usr/bin/env python3
"""Audit score-blind listening privacy readiness without collection."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/"
    "listening-privacy-readiness-audit-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-listening-privacy-readiness-20260814-001.json"
)
PLAN_ID = "perceptual-degradation-listening-privacy-readiness-audit-20260814-001"
REPORT_ID = "perceptual-degradation-listening-privacy-readiness-20260814-001"

EXPECTED_AUTHORIZATION = {
    "committed_metadata_schema_and_source_read_authorized": True,
    "synthetic_structural_audit_authorized": True,
    "operational_privacy_values_selection_authorized": False,
    "responsible_human_approval_authorized": False,
    "participant_contact_authorized": False,
    "recruitment_authorized": False,
    "consent_collection_authorized": False,
    "response_storage_authorized": False,
    "human_collection_authorized": False,
    "response_or_outcome_access_authorized": False,
    "public_individual_response_release_authorized": False,
    "public_small_cell_release_authorized": False,
    "no_reference_training_authorized": False,
    "public_verdict_enabled": False,
}

EXPECTED_POLICY = {
    "stable_or_repeated_participant_code_is_pseudonymous": True,
    "pseudonymous_response_data_is_deidentified": False,
    "absence_of_direct_identifiers_is_anonymous": False,
    "contact_and_payment_data_must_be_separate": True,
    "consent_record_must_be_separate_from_trial_data": True,
    "withdrawal_link_must_be_separate_and_time_bounded": True,
    "response_schema_may_contain_direct_identity_contact_or_network_fields": False,
    "public_individual_responses_may_be_released": False,
    "public_small_cells_may_be_released": False,
}

EXPECTED_BINDINGS = {
    "listening_preparation_gate",
    "listener_information_draft",
    "response_envelope_schema",
    "local_player",
    "local_player_tests",
    "allocation_journal_audit",
}

EXPECTED_CHECKS = [
    "response_schema_is_closed_world",
    "response_schema_contains_no_forbidden_direct_identifier_field",
    "participant_code_links_sessions_and_responses",
    "response_data_classified_as_pseudonymous_not_deidentified",
    "local_player_has_no_network_identity_microphone_or_persistence_api",
    "consent_version_and_timestamp_absent_from_trial_envelope",
    "withdrawal_code_absent_from_trial_envelope",
    "operational_privacy_fields_remain_unresolved",
    "response_storage_and_collection_remain_unauthorized",
    "allocation_journal_privacy_ownership_and_backup_policy_remains_unfrozen",
]

FORBIDDEN_PLAYER_TOKENS = (
    "fetch(",
    "XMLHttpRequest",
    "WebSocket",
    "sendBeacon",
    "localStorage",
    "sessionStorage",
    "indexedDB",
    "getUserMedia",
    "MediaRecorder",
    "document.cookie",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def canonical_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "score_blind_privacy_readiness_audit_frozen_no_collection_authority"
    ):
        errors.append("plan state differs")
    if set(plan.get("bindings", {})) != EXPECTED_BINDINGS:
        errors.append("binding inventory differs")
    for binding_id, binding in plan.get("bindings", {}).items():
        path = root / str(binding.get("path", ""))
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")
    if plan.get("authorization") != EXPECTED_AUTHORIZATION:
        errors.append("authorization boundary differs")
    if plan.get("privacy_classification_policy") != EXPECTED_POLICY:
        errors.append("privacy classification policy differs")
    forbidden = plan.get("forbidden_response_field_tokens")
    if not isinstance(forbidden, list) or len(forbidden) != len(set(forbidden)):
        errors.append("forbidden response field inventory differs")
    operational = plan.get("required_operational_fields")
    if not isinstance(operational, list) or len(operational) != 10:
        errors.append("required operational field inventory differs")
    if plan.get("predeclared_checks") != EXPECTED_CHECKS:
        errors.append("predeclared check inventory differs")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def _field_names(value: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            names.update(properties)
        for item in value.values():
            names.update(_field_names(item))
    elif isinstance(value, list):
        for item in value:
            names.update(_field_names(item))
    return names


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))

    gate = load_json(_bound(plan, "listening_preparation_gate"))
    schema = load_json(_bound(plan, "response_envelope_schema"))
    journal = load_json(_bound(plan, "allocation_journal_audit"))
    player = _bound(plan, "local_player").read_text(encoding="utf-8")
    listener_info = _bound(plan, "listener_information_draft").read_text(
        encoding="utf-8"
    )

    field_names = _field_names(schema)
    forbidden = set(plan["forbidden_response_field_tokens"])
    forbidden_present = sorted(field_names & forbidden)
    participant_id_present = "participant_id" in field_names
    response_schema_closed = schema.get("additionalProperties") is False
    local_player_forbidden_present = sorted(
        token for token in FORBIDDEN_PLAYER_TOKENS if token in player
    )
    consent_fields = {"consent_version", "consent_timestamp"} & field_names
    withdrawal_fields = {
        "withdrawal_code",
        "withdrawal_deadline",
        "deidentification_cutoff",
    } & field_names
    gate_completed = gate.get("completed", {})
    gate_privacy = gate.get("privacy", {})
    journal_decision = journal.get("decision", {})

    checks = {
        "response_schema_is_closed_world": response_schema_closed,
        "response_schema_contains_no_forbidden_direct_identifier_field": (
            not forbidden_present
        ),
        "participant_code_links_sessions_and_responses": participant_id_present,
        "response_data_classified_as_pseudonymous_not_deidentified": (
            participant_id_present
            and plan["privacy_classification_policy"][
                "pseudonymous_response_data_is_deidentified"
            ]
            is False
        ),
        "local_player_has_no_network_identity_microphone_or_persistence_api": (
            not local_player_forbidden_present
        ),
        "consent_version_and_timestamp_absent_from_trial_envelope": (
            not consent_fields
        ),
        "withdrawal_code_absent_from_trial_envelope": not withdrawal_fields,
        "operational_privacy_fields_remain_unresolved": (
            gate_completed.get("privacy_operational_fields_resolved") is False
            and gate_completed.get("compensation_and_withdrawal_resolved") is False
        ),
        "response_storage_and_collection_remain_unauthorized": (
            gate.get("response_storage_authorized") is False
            and gate.get("human_collection_authorized") is False
        ),
        "allocation_journal_privacy_ownership_and_backup_policy_remains_unfrozen": (
            journal_decision.get("privacy_ownership_and_backup_policy_frozen")
            is False
        ),
    }
    if list(checks) != EXPECTED_CHECKS or not all(checks.values()):
        raise ValueError("one or more predeclared privacy checks did not pass")

    direct_identifier_excluded = all(
        gate_privacy.get(key) is False
        for key in (
            "participant_identity_in_response_data",
            "raw_ip_address_recorded",
            "precise_location_recorded",
            "microphone_recorded",
        )
    )
    public_release_closed = (
        gate_privacy.get("public_individual_responses_authorized") is False
        and gate_privacy.get("public_small_cell_results_authorized") is False
    )
    required_operational_fields = plan["required_operational_fields"]
    operational_values = {key: None for key in required_operational_fields}
    structurally_ready = (
        response_schema_closed
        and not forbidden_present
        and not local_player_forbidden_present
        and direct_identifier_excluded
        and public_release_closed
        and "Consent is versioned and timestamped separately from trial data."
        in listener_info
    )
    operationally_ready = all(value is not None for value in operational_values.values())

    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "privacy_structure_minimized_operational_values_unresolved_collection_closed",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "access_boundary": {
            "committed_metadata_schema_and_source_read": True,
            "human_response_accessed": False,
            "participant_contacted": False,
            "consent_collected": False,
            "response_stored": False,
            "human_collection_performed": False,
            "operational_privacy_values_selected": False,
            "no_reference_training_performed": False,
            "public_verdict_enabled": False,
        },
        "response_data_classification": {
            "direct_identifiers_present": False,
            "participant_code_present": participant_id_present,
            "cross_record_linkage_present": participant_id_present,
            "classification": "pseudonymous_research_response_data",
            "deidentified_or_anonymous": False,
            "schema_title_claim": schema.get("title"),
            "successor_must_not_call_linkable_data_deidentified": True,
        },
        "structural_observations": {
            "response_schema_closed_world": response_schema_closed,
            "response_schema_field_count": len(field_names),
            "forbidden_direct_identifier_fields_present": forbidden_present,
            "local_player_forbidden_api_tokens_present": local_player_forbidden_present,
            "consent_version_or_timestamp_in_trial_envelope": sorted(consent_fields),
            "withdrawal_link_fields_in_trial_envelope": sorted(withdrawal_fields),
            "contact_and_payment_data_separate": gate_privacy.get(
                "contact_and_payment_data_separate"
            ),
            "public_individual_release_authorized": gate_privacy.get(
                "public_individual_responses_authorized"
            ),
            "public_small_cell_release_authorized": gate_privacy.get(
                "public_small_cell_results_authorized"
            ),
        },
        "predeclared_checks": checks,
        "operational_fields": operational_values,
        "decision": {
            "data_minimization_structure_ready_for_successor_design": structurally_ready,
            "pseudonymous_classification_correction_required": True,
            "consent_and_withdrawal_successor_required": True,
            "operational_privacy_values_complete": operationally_ready,
            "privacy_package_operationally_ready": False,
            "response_storage_authorized": False,
            "human_collection_authorized": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "next_gate": (
                "A responsible human must resolve every operational field and "
                "approve a successor package that calls linkable response data "
                "pseudonymous, keeps consent and withdrawal linkage separate, "
                "freezes storage, access, retention, deletion, incident, "
                "compensation and publication controls, and only then considers "
                "a separate storage and collection authorization."
            ),
        },
        "claim_boundary": plan["claim_boundary"],
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != 1 or report.get("report_id") != REPORT_ID:
        errors.append("report identity differs")
    if report.get("state") != (
        "privacy_structure_minimized_operational_values_unresolved_collection_closed"
    ):
        errors.append("report state differs")
    access = report.get("access_boundary", {})
    expected_true = {"committed_metadata_schema_and_source_read"}
    for key, value in access.items():
        expected = key in expected_true
        if value is not expected:
            errors.append(f"access boundary differs: {key}")
    classification = report.get("response_data_classification", {})
    if (
        classification.get("classification")
        != "pseudonymous_research_response_data"
        or classification.get("deidentified_or_anonymous") is not False
        or classification.get("cross_record_linkage_present") is not True
    ):
        errors.append("response data classification differs")
    operational = report.get("operational_fields", {})
    if len(operational) != 10 or any(value is not None for value in operational.values()):
        errors.append("operational fields must remain unresolved")
    decision = report.get("decision", {})
    if decision.get("data_minimization_structure_ready_for_successor_design") is not True:
        errors.append("data minimization readiness differs")
    for key in (
        "operational_privacy_values_complete",
        "privacy_package_operationally_ready",
        "response_storage_authorized",
        "human_collection_authorized",
        "no_reference_work_eligible",
        "public_verdict_enabled",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision must remain false: {key}")
    claims = report.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    report = build_report(load_json(args.plan), args.plan)
    errors = validate_report(report)
    if errors:
        raise ValueError("; ".join(errors))
    args.output.write_bytes(canonical_bytes(report))
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
