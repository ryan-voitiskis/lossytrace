#!/usr/bin/env python3
"""Validate score-blind readiness for retained ODAQ drift validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/"
    "odaq-retained-drift-validation-execution-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-odaq-retained-drift-validation-readiness-20260814-001.json"
)
PLAN_ID = "perceptual-degradation-odaq-retained-drift-validation-20260814-001"
REPORT_ID = (
    "perceptual-degradation-odaq-retained-drift-validation-readiness-20260814-001"
)
AUTHORIZATION_ID = re.compile(
    r"^perceptual-degradation-odaq-retained-drift-validation-authorization-"
    r"[0-9]{8}-[0-9]{3}$"
)
ISO_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
CANONICAL_DECISION = (
    "Authorize reading only the exact 16 retained ODAQ clean references, "
    "projecting their existing PCM representation into memory under the frozen "
    "canonical rule, generating only the frozen controlled clock-drift cases, "
    "and running the frozen technical estimator, held-out apply rule, exact "
    "resampler, alignment, and score-free oracle twice. Derived PCM must remain "
    "temporary and in memory. Do not authorize ODAQ processed conditions or "
    "scores, actual codec generation, perceptual metrics, playback, ratings, "
    "listener collection, sealed evidence, no-reference training, "
    "final-validation claims, or public verdicts."
)

EXPECTED_BINDINGS = {
    "research_contract",
    "acquisition_result",
    "delivery_preparation",
    "delivery_execution_plan",
    "projection_implementation",
    "attribution_audit",
    "playback_qualification_result",
    "synthetic_estimator_plan",
    "synthetic_estimator_implementation",
    "synthetic_estimator_report",
    "authorization_schema",
    "readiness_implementation",
    "readiness_tests",
}

EXPECTED_AUTHORIZATION_GATE = {
    "responsible_human_authorization_present": False,
    "committed_successor_authorization_path": None,
    "retained_reference_read_authorized": False,
    "canonical_pcm_projection_authorized": False,
    "controlled_synthetic_drift_generation_authorized": False,
    "live_runner_implementation_authorized": False,
    "live_execution_authorized": False,
}

EXPECTED_QUALIFIED_EVIDENCE = {
    "retained_reference_count": 16,
    "retained_audio_bytes": 54633154,
    "retained_inventory_sha256": (
        "d7f244da55b510b639300d55271b1ebd5fb9f7454b258bec30588bf18eefde2f"
    ),
    "source_sample_rate_hz": 48000,
    "source_channel_count": 2,
    "minimum_source_frame_count": 360701,
    "maximum_source_frame_count": 576008,
    "float32_reference_count": 7,
    "extensible_s24_reference_count": 9,
    "attribution_notice_ready_source_count": 16,
    "physical_playback_chain_qualified": True,
    "perceptual_truth_collected": False,
    "synthetic_estimator_case_count": 7,
    "synthetic_estimator_gate_pass_count": 13,
}

EXPECTED_PROTOCOL = {
    "protocol_id": "odaq-clean-reference-controlled-drift-v1",
    "reference_count": 16,
    "source_sample_rate_hz": 48000,
    "source_channel_count": 2,
    "analysis_segment_policy": "first_288000_pcm_frames",
    "analysis_frame_count": 288000,
    "analysis_duration_seconds": 6,
    "actual_drift_ppm_cases": [75, -60, 0, 20, -20, 100, -100],
    "candidate_drift_ppm_minimum": -100,
    "candidate_drift_ppm_maximum": 100,
    "candidate_drift_ppm_step": 5,
    "window_frame_count": 24000,
    "window_start_frames": [
        24000,
        48000,
        72000,
        96000,
        120000,
        144000,
        168000,
        192000,
        216000,
        240000,
    ],
    "training_window_positions": [0, 2, 4, 6, 8],
    "held_out_window_positions": [1, 3, 5, 7, 9],
    "reference_energy_mask_only": True,
    "minimum_channel_window_rms": 0.000001,
    "minimum_eligible_training_windows_per_channel": 3,
    "minimum_eligible_held_out_windows_per_channel": 3,
    "insufficient_energy_action": "abstain_insufficient_signal_support",
    "selection_metric": "mean_cosine_correlation_across_eligible_channels_and_training_windows",
    "selection_tie_break": "higher_score_then_lower_abs_ppm_then_lower_signed_ppm",
    "selection_uses_held_out_windows": False,
    "proxy_interpolator": "binary64_linear_interpolation",
    "proxy_interpolator_is_frozen_resampler": False,
    "minimum_selection_margin": 0.0001,
    "minimum_held_out_correlation_after_correction": 0.99,
    "minimum_held_out_correlation_improvement_to_apply": 0.05,
    "correction_resampler": "oracle-bounded-drift-kaiser-sinc128-q30-v1",
    "mandatory_discard_frames_each_edge_when_applied": 64,
    "zero_drift_policy": "bit_exact_identity_bypass",
    "nonzero_no_apply_policy": "bit_exact_observed_passthrough",
    "post_decision_alignment": "perceptual_degradation_alignment_v2",
    "post_decision_oracle": "perceptual_degradation_full_reference_oracle_score_free_v1",
}

EXPECTED_FUTURE_GATES = {
    "exact_source_inventory_reverified": True,
    "all_16_sources_attempted": True,
    "all_7_drift_cases_attempted_per_source": True,
    "minimum_supported_sources_per_nonzero_drift_case": 12,
    "maximum_supported_estimation_absolute_error_ppm": 5,
    "minimum_correct_estimate_rate_across_supported_nonzero_cases": 0.95,
    "zero_drift_false_apply_count": 0,
    "applied_case_minimum_post_correction_core_correlation_each_channel": 0.999,
    "applied_case_minimum_core_correlation_improvement_each_channel": 0.01,
    "every_applied_case_must_meet_frozen_held_out_rule": True,
    "every_nonapplied_output_must_be_bit_exact": True,
    "every_abstention_must_have_predeclared_reason": True,
    "score_free_oracle_must_remain_execution_blocked": True,
    "derived_audio_must_not_be_retained": True,
    "fresh_replay_count": 2,
    "fresh_replay_reports_must_be_byte_identical": True,
    "public_report_must_exclude_paths_per_reference_hashes_and_audio": True,
}

EXPECTED_EXECUTION = {
    "maximum_workers": 1,
    "minimum_free_disk_gib": 15,
    "exact_acquired_inventory_only": True,
    "source_inventory_reverified_before_read": True,
    "canonical_projection": "perceptual-degradation-odaq-reference-delivery-preparation-20260813-001",
    "derived_pcm_lifetime": "temporary_in_memory_only",
    "private_journal_outside_repository": True,
    "public_paths_redacted": True,
    "public_per_reference_hashes_redacted": True,
    "stop_before_read_on_authorization_failure": True,
    "stop_on_unexpected_input_geometry": True,
    "stop_on_float_domain_violation": True,
}

EXPECTED_ACCESS = {
    "committed_metadata_and_source_read_authorized": True,
    "synthetic_authorization_fixture_validation_authorized": True,
    "retained_reference_access_authorized": False,
    "canonical_pcm_projection_authorized": False,
    "controlled_synthetic_clock_drift_generation_authorized": False,
    "provider_processed_condition_access_authorized": False,
    "provider_listening_score_access_authorized": False,
    "actual_codec_generation_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "human_playback_authorized": False,
    "degradation_rating_collection_authorized": False,
    "listener_response_collection_authorized": False,
    "sealed_evidence_access_authorized": False,
    "no_reference_training_authorized": False,
    "public_verdict_authorized": False,
}

EXPECTED_CLAIMS = {
    "development_only": True,
    "one_provider_stratum": True,
    "protocol_readiness_is_retained_validation": False,
    "synthetic_drift_is_actual_codec_degradation": False,
    "retained_reference_validation_is_perceptual_truth": False,
    "technical_correlation_is_a_perceptual_metric": False,
    "independent_transfer_supported": False,
    "full_reference_oracle_validated": False,
    "no_reference_work_eligible": False,
    "final_validation_supported": False,
    "public_verdict_enabled": False,
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _bound(plan: dict[str, Any], binding_id: str, root: Path = ROOT) -> Path:
    return root / plan["bindings"][binding_id]["path"]


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "score_blind_retained_reference_drift_validation_protocol_frozen_authorization_pending"
    ):
        errors.append("plan state differs")
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != EXPECTED_BINDINGS:
        errors.append("binding inventory differs")
        bindings = {}
    for binding_id, binding in bindings.items():
        path = root / str(binding.get("path", ""))
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")
    if plan.get("authorization_gate") != EXPECTED_AUTHORIZATION_GATE:
        errors.append("authorization gate differs")
    if plan.get("qualified_evidence") != EXPECTED_QUALIFIED_EVIDENCE:
        errors.append("qualified evidence differs")
    if plan.get("validation_protocol") != EXPECTED_PROTOCOL:
        errors.append("validation protocol differs")
    if plan.get("predeclared_future_gates") != EXPECTED_FUTURE_GATES:
        errors.append("future gate contract differs")
    if plan.get("execution_constraints") != EXPECTED_EXECUTION:
        errors.append("execution constraints differ")
    if plan.get("access_boundary") != EXPECTED_ACCESS:
        errors.append("access boundary differs")
    if plan.get("claim_boundary") != EXPECTED_CLAIMS:
        errors.append("claim boundary differs")
    if plan.get("canonical_authorization_decision") != CANONICAL_DECISION:
        errors.append("canonical authorization decision differs")
    return sorted(set(errors))


def expected_authorization_bindings(
    plan: dict[str, Any], plan_path: Path = PLAN_PATH
) -> dict[str, dict[str, str]]:
    mapping = {
        "validation_execution_plan": {
            "path": str(plan_path.relative_to(ROOT)),
            "sha256": sha256_file(plan_path),
        },
        "acquisition_result": plan["bindings"]["acquisition_result"],
        "delivery_preparation": plan["bindings"]["delivery_preparation"],
        "projection_implementation": plan["bindings"]["projection_implementation"],
        "synthetic_estimator_plan": plan["bindings"]["synthetic_estimator_plan"],
        "synthetic_estimator_implementation": plan["bindings"]
        ["synthetic_estimator_implementation"],
        "synthetic_estimator_report": plan["bindings"]["synthetic_estimator_report"],
        "authorization_schema": plan["bindings"]["authorization_schema"],
    }
    return json.loads(json.dumps(mapping))


def expected_authorization_scope(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "retained_reference_count": 16,
        "retained_inventory_sha256": plan["qualified_evidence"]
        ["retained_inventory_sha256"],
        "retained_reference_access_authorized": True,
        "canonical_pcm_projection_in_memory_authorized": True,
        "controlled_synthetic_clock_drift_generation_authorized": True,
        "temporary_corrected_pcm_in_memory_authorized": True,
        "retained_derived_audio_authorized": False,
        "provider_processed_condition_access_authorized": False,
        "provider_listening_score_access_authorized": False,
        "actual_codec_generation_authorized": False,
        "perceptual_metric_execution_authorized": False,
        "human_playback_authorized": False,
        "degradation_rating_collection_authorized": False,
        "listener_response_collection_authorized": False,
        "sealed_evidence_access_authorized": False,
        "no_reference_training_authorized": False,
        "public_verdict_authorized": False,
    }


def expected_authorization_execution_constraints() -> dict[str, Any]:
    return {
        "maximum_workers": 1,
        "minimum_free_disk_gib": 15,
        "exact_acquired_inventory_only": True,
        "source_inventory_reverified_before_read": True,
        "analysis_segment_policy": "first_288000_pcm_frames",
        "derived_pcm_lifetime": "temporary_in_memory_only",
        "fresh_replay_count": 2,
        "replay_reports_byte_identical": True,
        "public_paths_redacted": True,
        "public_per_reference_hashes_redacted": True,
        "private_journal_outside_repository": True,
        "stop_before_read_on_authorization_failure": True,
        "stop_on_unexpected_input_geometry": True,
        "stop_on_float_domain_violation": True,
    }


def expected_authorization_claim_boundary() -> dict[str, Any]:
    return {
        "development_only": True,
        "one_provider_stratum": True,
        "synthetic_drift_is_actual_codec_degradation": False,
        "retained_reference_validation_is_perceptual_truth": False,
        "technical_correlation_is_a_perceptual_metric": False,
        "independent_transfer_supported": False,
        "full_reference_oracle_validated": False,
        "no_reference_work_eligible": False,
        "final_validation_supported": False,
    }


def validate_authorization(
    authorization: dict[str, Any],
    plan: dict[str, Any],
    plan_path: Path = PLAN_PATH,
) -> list[str]:
    errors: list[str] = []
    if authorization.get("schema_version") != 1:
        errors.append("authorization schema version differs")
    if not AUTHORIZATION_ID.fullmatch(
        str(authorization.get("authorization_id", ""))
    ):
        errors.append("authorization identity differs")
    if not ISO_DATE.fullmatch(str(authorization.get("authorized_on", ""))):
        errors.append("authorization date differs")
    if authorization.get("state") != (
        "responsible_human_authorized_exact_odaq_clean_reference_drift_validation_only"
    ):
        errors.append("authorization state differs")
    if authorization.get("responsible_human_authorization_present") is not True:
        errors.append("responsible-human authorization is absent")
    if authorization.get("bindings") != expected_authorization_bindings(
        plan, plan_path
    ):
        errors.append("authorization evidence bindings differ")
    if authorization.get("authorization_scope") != expected_authorization_scope(plan):
        errors.append("authorization scope differs")
    if authorization.get("execution_constraints") != (
        expected_authorization_execution_constraints()
    ):
        errors.append("authorization execution constraints differ")
    if authorization.get("claim_boundary") != expected_authorization_claim_boundary():
        errors.append("authorization claim boundary differs")
    if authorization.get("canonical_decision") != CANONICAL_DECISION:
        errors.append("authorization canonical decision differs")
    encoded = json.dumps(authorization, sort_keys=True)
    if "/Users/" in encoded or "Application Support" in encoded:
        errors.append("authorization must not contain a private absolute path")
    return sorted(set(errors))


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    acquisition = load_json(_bound(plan, "acquisition_result"))
    preparation = load_json(_bound(plan, "delivery_preparation"))
    estimator = load_json(_bound(plan, "synthetic_estimator_report"))
    attribution = load_json(_bound(plan, "attribution_audit"))
    playback = load_json(_bound(plan, "playback_qualification_result"))
    inventory = acquisition["retained_inventory"]
    projection = preparation["projection_scope"]
    evidence = plan["qualified_evidence"]
    gates = {
        "retained_inventory_geometry_sufficient": (
            inventory["reference_count"] == 16
            and inventory["sample_rate_hz"] == 48000
            and inventory["channel_count"] == 2
            and inventory["minimum_frame_count"]
            >= plan["validation_protocol"]["analysis_frame_count"]
        ),
        "projection_geometry_coverage": (
            projection["float_reference_count"]
            + projection["extensible_integer_reference_count"]
            == inventory["reference_count"]
            and projection["source_sample_rate_hz"] == inventory["sample_rate_hz"]
            and projection["source_channel_count"] == inventory["channel_count"]
        ),
        "attribution_inventory_ready": (
            attribution["selection"]["attribution_notice_ready_source_count"] == 16
            and attribution["selection"]["attribution_unresolved_source_count"] == 0
        ),
        "playback_predecessor_qualified_without_truth": (
            playback["qualified_chain"]["physical_playback_qualified"] is True
            and playback["responsible_human_observations"][
                "degradation_rating_provided"
            ]
            is False
        ),
        "synthetic_estimator_predecessor_passed": (
            estimator["all_predeclared_gates_pass"] is True
            and estimator["summary"]["predeclared_gate_pass_count"] == 13
            and estimator["decision"]["full_reference_oracle_validated"] is False
        ),
        "analysis_segment_fits_every_reference": (
            evidence["minimum_source_frame_count"]
            >= plan["validation_protocol"]["analysis_frame_count"]
        ),
        "authorization_schema_frozen": _bound(
            plan, "authorization_schema"
        ).is_file(),
        "live_execution_closed": (
            not any(plan["authorization_gate"].values())
            if all(
                isinstance(value, bool)
                for value in plan["authorization_gate"].values()
                if value is not None
            )
            else False
        ),
        "retained_metric_human_and_public_boundaries_closed": all(
            plan["access_boundary"][key] is False
            for key in (
                "retained_reference_access_authorized",
                "canonical_pcm_projection_authorized",
                "controlled_synthetic_clock_drift_generation_authorized",
                "provider_processed_condition_access_authorized",
                "provider_listening_score_access_authorized",
                "actual_codec_generation_authorized",
                "perceptual_metric_execution_authorized",
                "human_playback_authorized",
                "degradation_rating_collection_authorized",
                "listener_response_collection_authorized",
                "sealed_evidence_access_authorized",
                "no_reference_training_authorized",
                "public_verdict_authorized",
            )
        ),
    }
    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "metadata_only_protocol_ready_responsible_human_authorization_pending",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "gate_audit": gates,
        "all_readiness_gates_pass": all(gates.values()),
        "qualified_evidence": evidence,
        "future_validation_case_count": 16 * 7,
        "future_nonzero_case_count": 16 * 6,
        "authorization_gate": plan["authorization_gate"],
        "access_boundary": plan["access_boundary"],
        "claim_boundary": plan["claim_boundary"],
        "execution_observation": {
            "repository_metadata_read": True,
            "retained_reference_accessed": False,
            "canonical_pcm_projected": False,
            "synthetic_drift_generated": False,
            "derived_pcm_retained": False,
            "provider_processed_condition_accessed": False,
            "provider_listening_score_accessed": False,
            "actual_codec_generated": False,
            "perceptual_metric_executed": False,
            "human_playback_performed": False,
            "human_response_accessed": False,
            "no_reference_training_performed": False,
            "public_verdict_enabled": False,
        },
        "decision": {
            "protocol_frozen": True,
            "authorization_schema_frozen": True,
            "ready_to_request_responsible_human_authorization": all(gates.values()),
            "live_runner_implementation_authorized": False,
            "live_execution_authorized": False,
            "retained_validation_complete": False,
            "real_content_drift_estimation_validated": False,
            "perceptual_validity_present": False,
            "full_reference_oracle_validated": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "next_gate": (
                "Obtain and commit the exact responsible-human successor "
                "authorization. Only after exact-head CI passes may a separate "
                "live runner be implemented and the retained-reference technical "
                "validation executed."
            ),
        },
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != 1 or report.get("report_id") != REPORT_ID:
        errors.append("report identity differs")
    gates = report.get("gate_audit", {})
    if not isinstance(gates, dict) or len(gates) != 9 or not all(gates.values()):
        errors.append("readiness gates did not all pass")
    observation = report.get("execution_observation", {})
    if observation.get("repository_metadata_read") is not True:
        errors.append("metadata-read observation differs")
    for key, value in observation.items():
        if key != "repository_metadata_read" and value is not False:
            errors.append(f"execution boundary differs: {key}")
    decision = report.get("decision", {})
    for key in (
        "protocol_frozen",
        "authorization_schema_frozen",
        "ready_to_request_responsible_human_authorization",
    ):
        if decision.get(key) is not True:
            errors.append(f"decision must be true: {key}")
    for key in (
        "live_runner_implementation_authorized",
        "live_execution_authorized",
        "retained_validation_complete",
        "real_content_drift_estimation_validated",
        "perceptual_validity_present",
        "full_reference_oracle_validated",
        "no_reference_work_eligible",
        "public_verdict_enabled",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision must be false: {key}")
    return sorted(set(errors))


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(report))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    plan = load_json(args.plan)
    payloads: list[bytes] = []
    for _ in range(2):
        with tempfile.TemporaryDirectory(
            prefix="lossytrace-odaq-drift-readiness-"
        ) as directory:
            temporary = Path(directory) / "report.json"
            temporary.write_bytes(canonical_bytes(build_report(plan, args.plan)))
            payloads.append(temporary.read_bytes())
    if len(set(payloads)) != 1:
        raise SystemExit("fresh metadata-only readiness reports differ")
    report = json.loads(payloads[0])
    errors = validate_report(report)
    if errors:
        raise SystemExit("; ".join(errors))
    write_report(report, args.output)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
