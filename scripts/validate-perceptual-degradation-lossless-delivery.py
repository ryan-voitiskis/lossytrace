#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "private-lossless-delivery-plan.json"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_evidence(evidence: dict[str, Any]) -> list[str]:
    errors = []
    if evidence.get("schema_version") != 1:
        errors.append("evidence schema_version must equal 1")
    if evidence.get("state") != (
        "headed_browser_lossless_delivery_observed_not_playback_or_listener_evidence"
    ):
        errors.append("evidence state must remain delivery-only")
    environment = evidence.get("environment", {})
    if environment.get("headed") is not True:
        errors.append("headed browser evidence is required")
    if environment.get("browser_binary_binding_complete") is not True:
        errors.append("browser binary binding must be complete")
    fixture = evidence.get("fixture", {})
    for key in (
        "generated_synthetic",
        "created_outside_repository",
        "moved_to_trash_after_observation",
        "recoverable_from_trash_at_observation_time",
    ):
        if fixture.get(key) is not True:
            errors.append(f"fixture.{key} must be true")
    for key in ("committed", "retained"):
        if fixture.get(key) is not False:
            errors.append(f"fixture.{key} must be false")
    projection = evidence.get("browser_visible_session_projection", {})
    for key in (
        "private_path_included",
        "condition_recipe_included",
        "source_role_included",
        "metric_score_included",
        "participant_identity_included",
        "listener_response_included",
    ):
        if projection.get(key) is not False:
            errors.append(f"browser_visible_session_projection.{key} must be false")
    observed = evidence.get("observed_checks", {})
    for key in (
        "all_page_resources_local",
        "session_projection_loaded",
        "browser_sha256_and_pcm_geometry_verified",
        "play_control_invoked",
        "left_only_control_invoked",
        "right_only_control_invoked",
    ):
        if observed.get(key) is not True:
            errors.append(f"observed_checks.{key} must be true")
    if observed.get("audio_context_state") != "running":
        errors.append("audio context must have been running")
    if observed.get("audio_context_sample_rate_hz") != observed.get(
        "required_sample_rate_hz"
    ):
        errors.append("observed browser sample rate differs")
    for key in (
        "browser_resampling_requested",
        "operator_audibility_confirmation_collected",
    ):
        if observed.get(key) is not False:
            errors.append(f"observed_checks.{key} must be false")
    if observed.get("non_local_request_count") != 0:
        errors.append("non-local page request count must be zero")
    for key in (
        "cookie_count",
        "local_storage_item_count",
        "session_storage_item_count",
    ):
        if observed.get(key) != 0:
            errors.append(f"observed_checks.{key} must equal zero")
    boundary = evidence.get("privacy_and_evidence_boundary", {})
    for key, value in boundary.items():
        if value is not False:
            errors.append(f"privacy_and_evidence_boundary.{key} must be false")
    for key in (
        "operator_audibility_check_observed",
        "lossless_study_stimuli_frozen",
        "licences_frozen",
        "player_implementation_frozen",
        "physical_playback_chain_frozen",
        "human_collection_authorized",
        "recruitment_authorized",
        "response_storage_authorized",
        "metric_execution_authorized",
        "public_verdict_enabled",
    ):
        if evidence.get(key) is not False:
            errors.append(f"evidence {key} must remain false")
    if evidence.get("headed_browser_delivery_dry_run_observed") is not True:
        errors.append("headed browser delivery observation must be true")
    if evidence.get("paths_redacted") is not True:
        errors.append("evidence paths must be redacted")
    return errors


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = []
    if plan.get("schema_version") != 1:
        errors.append("plan schema_version must equal 1")
    if plan.get("state") != "headed_browser_delivery_observed_playback_unqualified":
        errors.append("plan must remain browser-observed and playback-unqualified")
    for key in (
        "human_collection_authorized",
        "recruitment_authorized",
        "participant_contact_authorized",
        "response_storage_authorized",
        "metric_execution_authorized",
        "public_verdict_enabled",
        "retained_audio_access_authorized",
        "provider_audio_acquisition_authorized",
        "committed_audio_authorized",
    ):
        if plan.get(key) is not False:
            errors.append(f"plan {key} must remain false")
    runtime = plan.get("runtime", {})
    if runtime.get("listen_host") != "127.0.0.1":
        errors.append("runtime must remain loopback-only")
    for key in (
        "external_network_enabled",
        "request_logging_enabled",
        "write_routes_enabled",
    ):
        if runtime.get(key) is not False:
            errors.append(f"runtime.{key} must remain false")
    for key in (
        "private_delivery_map_outside_repository",
        "private_audio_outside_repository",
    ):
        if runtime.get(key) is not True:
            errors.append(f"runtime.{key} must remain true")
    accepted = plan.get("accepted_audio", {})
    if accepted.get("browser_media_decoder_used") is not False:
        errors.append("browser media decoder must remain unused")
    if accepted.get("sample_rate_mismatch_action") != "unsupported":
        errors.append("sample-rate mismatch must remain unsupported")
    projection = plan.get("browser_projection", {})
    for key in (
        "private_path_included",
        "condition_recipe_included",
        "source_role_included",
        "metric_score_included",
        "participant_identity_included",
        "listener_response_included",
    ):
        if projection.get(key) is not False:
            errors.append(f"browser_projection.{key} must remain false")
    completed = plan.get("completed", {})
    expected_true = {
        "delivery_contract_frozen",
        "loopback_server_implemented",
        "manual_pcm_wav_parser_implemented",
        "private_path_redaction_tested",
        "authorization_failure_tested",
        "hash_and_file_mutation_failure_tested",
        "sample_rate_failure_tested",
        "browser_source_parsing_tested",
        "headed_browser_delivery_dry_run_observed",
    }
    for key, value in completed.items():
        expected = key in expected_true
        if value is not expected:
            errors.append(f"completed.{key} must be {str(expected).lower()}")
    for key, binding in plan.get("bindings", {}).items():
        relative = binding.get("path", "")
        path = root / relative
        if not path.is_file():
            errors.append(f"missing bound file {key}: {relative}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"hash mismatch for bound file {key}: {relative}")
    evidence_binding = plan.get("bindings", {}).get("browser_dry_run_evidence")
    if evidence_binding:
        evidence_path = root / evidence_binding.get("path", "")
        if evidence_path.is_file():
            try:
                evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                errors.append(f"invalid browser dry-run evidence JSON: {error}")
            else:
                errors.extend(validate_evidence(evidence))
    else:
        errors.append("browser dry-run evidence binding is required")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", nargs="?", type=Path, default=DEFAULT_PLAN)
    args = parser.parse_args()
    path = args.plan.resolve()
    plan = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_plan(plan)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print(
        json.dumps(
            {
                "plan": str(path.relative_to(ROOT)),
                "plan_sha256": sha256_file(path),
                "status": "headed_browser_delivery_observed_playback_unqualified",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
