#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "listening-preparation-gate.json"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_operator_check(evidence: dict[str, Any]) -> list[str]:
    errors = []
    if evidence.get("schema_version") != 1:
        errors.append("operator check schema_version must equal 1")
    if evidence.get("state") != (
        "synthetic_dry_run_and_operator_audibility_check_passed_not_listener_evidence"
    ):
        errors.append("operator check must remain explicitly non-evidentiary")
    operator_check = evidence.get("operator_check", {})
    if operator_check.get("confirmation_source") != (
        "direct_operator_statement_after_v2_control_playback"
    ):
        errors.append("operator check confirmation source differs")
    if operator_check.get("operator_confirmed_all_generated_sounds_audible") is not True:
        errors.append("current generated sounds must have an explicit audibility check")
    for key in (
        "rating_requested",
        "rating_collected",
        "degradation_judgment_requested",
        "degradation_judgment_collected",
        "participant_identity_recorded",
    ):
        if operator_check.get(key) is not False:
            errors.append(f"operator_check.{key} must remain false")
    if (
        evidence.get("observed_checks", {}).get(
            "operator_audibility_confirmation_collected"
        )
        is not True
    ):
        errors.append("current operator audibility confirmation must remain recorded")
    boundary = evidence.get("privacy_and_evidence_boundary", {})
    for key in (
        "participant_identity_collected",
        "listener_response_collected",
        "operator_confirmation_is_listening_truth",
        "operator_confirmation_is_calibration_evidence",
        "browser_automation_values_are_listening_truth",
        "prior_v1_operator_confirmation_reused_for_v2",
        "metric_score_opened",
        "audio_score_opened",
        "retained_audio_opened",
        "screenshot_committed",
        "browser_artifacts_committed",
        "network_storage_used",
    ):
        if boundary.get(key) is not False:
            errors.append(f"privacy_and_evidence_boundary.{key} must remain false")
    for key in (
        "player_implementation_frozen",
        "playback_qualification_frozen",
        "human_collection_authorized",
        "recruitment_authorized",
        "response_storage_authorized",
        "public_verdict_enabled",
    ):
        if evidence.get(key) is not False:
            errors.append(f"operator evidence {key} must remain false")
    return errors


def validate(gate: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = []
    if gate.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if gate.get("state") != "protocol_prepared_human_collection_unauthorized":
        errors.append("listening gate must remain in preparation state")
    for key in (
        "human_collection_authorized",
        "recruitment_authorized",
        "real_listener_software_authorized",
        "participant_contact_authorized",
        "response_storage_authorized",
    ):
        if gate.get(key) is not False:
            errors.append(f"{key} must remain false")

    completed = gate.get("completed", {})
    allowed_complete = {
        "protocol_draft_present",
        "participant_information_draft_present",
        "power_report_frozen",
        "synthetic_dry_run_passed",
        "private_lossless_delivery_dry_run_passed",
    }
    for key, value in completed.items():
        expected = key in allowed_complete
        if value is not expected:
            errors.append(f"completed.{key} must be {str(expected).lower()}")
    if set(completed) != {
        "protocol_draft_present",
        "participant_information_draft_present",
        "source_and_condition_manifest_frozen",
        "licences_frozen",
        "player_implementation_frozen",
        "synthetic_dry_run_passed",
        "private_lossless_delivery_dry_run_passed",
        "playback_qualification_frozen",
        "power_report_frozen",
        "privacy_operational_fields_resolved",
        "compensation_and_withdrawal_resolved",
        "analysis_hashes_frozen",
        "responsible_human_approval_present",
    }:
        errors.append("completed prerequisite fields differ")

    methods = gate.get("methods", {})
    if methods.get("maximum_subtle_trials_per_session", 99) > 15:
        errors.append("subtle trial limit must not exceed 15")
    if methods.get("maximum_mushra_trials_per_session", 99) > 6:
        errors.append("MUSHRA trial limit must not exceed 6")
    if methods.get("maximum_signals_per_mushra_trial", 99) > 12:
        errors.append("MUSHRA signal limit must not exceed 12")
    for key in (
        "feedback_during_scored_trials",
        "condition_recipe_visible",
        "metric_score_visible",
    ):
        if methods.get(key) is not False:
            errors.append(f"methods.{key} must remain false")

    privacy = gate.get("privacy", {})
    for key in (
        "participant_identity_in_response_data",
        "raw_ip_address_recorded",
        "precise_location_recorded",
        "microphone_recorded",
        "public_individual_responses_authorized",
        "public_small_cell_results_authorized",
    ):
        if privacy.get(key) is not False:
            errors.append(f"privacy.{key} must remain false")
    if privacy.get("contact_and_payment_data_separate") is not True:
        errors.append("contact and payment data must remain separate")

    if not gate.get("unresolved_operational_fields"):
        errors.append("unresolved operational fields must remain explicit")
    for key, binding in gate.get("bindings", {}).items():
        relative = binding.get("path", "")
        path = root / relative
        if not path.is_file():
            errors.append(f"missing bound file {key}: {relative}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"hash mismatch for bound file {key}: {relative}")
    operator_binding = gate.get("bindings", {}).get("synthetic_player_dry_run_evidence")
    if operator_binding:
        operator_path = root / operator_binding.get("path", "")
        if operator_path.is_file():
            try:
                operator_evidence = json.loads(operator_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                errors.append(f"invalid operator evidence JSON: {error}")
            else:
                errors.extend(validate_operator_check(operator_evidence))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gate", nargs="?", type=Path, default=DEFAULT_GATE)
    args = parser.parse_args()
    path = args.gate.resolve()
    gate = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(gate)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print(
        json.dumps(
            {
                "gate": str(path.relative_to(ROOT)),
                "gate_sha256": sha256_file(path),
                "status": "human_collection_unauthorized_as_required",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
