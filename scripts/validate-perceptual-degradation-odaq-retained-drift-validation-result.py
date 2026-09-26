#!/usr/bin/env python3
"""Validate the aggregate-only retained ODAQ drift result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULT = (
    ROOT
    / "benchmarks/perceptual-degradation-v1"
    / "odaq-retained-drift-validation-result-20260817.json"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


EXPECTED_EXECUTION = {
    "authorization_exact_head_commit": "5eb9e31a9fa12bad1e90a8c4d924765db8e91932",
    "authorization_exact_head_ci_url": "https://github.com/ryan-voitiskis/lossytrace/actions/runs/31919169130",
    "runner_provenance_chain": [
        {
            "head_commit": "366ddb53254fa2ebfef56927c32a08a934685a1c",
            "exact_head_ci_url": "https://github.com/ryan-voitiskis/lossytrace/actions/runs/31921149257",
        },
        {
            "head_commit": "6effd2f972b384774def82ffb54455e271e5649a",
            "exact_head_ci_url": "https://github.com/ryan-voitiskis/lossytrace/actions/runs/31929976827",
        },
    ],
    "fresh_replay_count": 2,
    "replay_reports_byte_identical": True,
    "replay_report_sha256": "b74cc0502b650055f4abfef79625b0e5db62b5ddfad474357d2a33c443dcd602",
    "attribution_attachments_byte_identical": True,
    "maximum_workers": 1,
    "minimum_free_disk_gib_preserved": 15,
    "derived_pcm_lifetime": "temporary_in_memory_only",
    "private_outputs_retained_outside_repository": True,
    "private_paths_published": False,
    "per_reference_hashes_published": False,
    "audio_published": False,
}

EXPECTED_AGGREGATE = {
    "reference_count": 16,
    "attempted_case_count": 112,
    "supported_case_count": 112,
    "abstained_case_count": 0,
    "supported_nonzero_case_count": 96,
    "correct_supported_nonzero_case_count": 96,
    "correct_supported_nonzero_estimate_rate": 1.0,
    "maximum_supported_estimation_absolute_error_ppm": 0,
    "minimum_supported_source_count_per_nonzero_drift_case": 16,
    "applied_correction_case_count": 93,
    "nonapplied_case_count": 19,
    "zero_drift_false_apply_count": 0,
    "minimum_applied_post_correction_core_correlation": 0.998464803418,
    "applied_case_count_below_post_correction_correlation_threshold": 6,
    "applied_channel_count_below_post_correction_correlation_threshold": 12,
    "minimum_applied_core_correlation_improvement": 0.034206658269,
    "applied_held_out_rule_violation_count": 0,
    "nonapplied_non_bit_exact_count": 0,
    "supported_alignment_case_count": 105,
    "unsupported_alignment_case_count": 7,
    "score_free_oracle_execution_blocked_case_count": 105,
    "score_free_oracle_unsupported_alignment_case_count": 7,
    "retained_derived_pcm_case_count": 0,
    "prohibited_surface_violation_case_count": 0,
}

EXPECTED_GATES = {
    "exact_source_inventory_reverified": True,
    "all_16_sources_attempted": True,
    "all_7_drift_cases_attempted_per_source": True,
    "minimum_supported_sources_per_nonzero_drift_case": True,
    "maximum_supported_estimation_absolute_error_ppm": True,
    "minimum_correct_estimate_rate_across_supported_nonzero_cases": True,
    "zero_drift_false_apply_count": True,
    "applied_case_minimum_post_correction_core_correlation_each_channel": False,
    "applied_case_minimum_core_correlation_improvement_each_channel": True,
    "every_applied_case_must_meet_frozen_held_out_rule": True,
    "every_nonapplied_output_must_be_bit_exact": True,
    "every_abstention_must_have_predeclared_reason": True,
    "score_free_oracle_must_remain_execution_blocked": True,
    "derived_audio_must_not_be_retained": True,
    "fresh_replay_count": True,
    "fresh_replay_reports_must_be_byte_identical": True,
    "public_report_must_exclude_paths_per_reference_hashes_and_audio": True,
}

EXPECTED_ACCESS = {
    "retained_clean_reference_audio_read": True,
    "canonical_pcm_projected_in_memory": True,
    "controlled_synthetic_clock_drift_generated": True,
    "odaq_processed_condition_opened": False,
    "odaq_listening_score_opened": False,
    "actual_codec_generated": False,
    "perceptual_metric_executed": False,
    "human_playback_performed": False,
    "degradation_rating_collected": False,
    "listener_response_collected": False,
    "sealed_evidence_opened": False,
    "no_reference_training_performed": False,
    "public_verdict_emitted": False,
}

EXPECTED_CLAIMS = {
    "development_only": True,
    "one_provider_stratum": True,
    "controlled_clock_drift_is_actual_codec_degradation": False,
    "technical_correlation_is_a_perceptual_metric": False,
    "retained_reference_validation_is_perceptual_truth": False,
    "failed_gate_is_a_public_verdict": False,
    "independent_transfer_supported": False,
    "full_reference_oracle_validated": False,
    "no_reference_work_eligible": False,
    "final_validation_supported": False,
}


def validate_result(result: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if result.get("schema_version") != 1 or result.get("result_id") != (
        "perceptual-degradation-odaq-retained-drift-validation-result-20260817-001"
    ):
        errors.append("result identity differs")
    if result.get("state") != (
        "private_odaq_retained_drift_validation_complete_reproducible_technical_negative"
    ):
        errors.append("result state differs")

    bindings = result.get("bindings", {})
    expected_bindings = {
        "authorization",
        "execution_plan",
        "private_runner",
        "private_runner_tests",
    }
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        errors.append("result binding inventory differs")
    else:
        for binding_id, binding in bindings.items():
            relative = Path(str(binding.get("path", "")))
            if not relative.parts or relative.is_absolute() or ".." in relative.parts:
                errors.append(f"invalid result binding: {binding_id}")
                continue
            path = root / relative
            if not path.is_file():
                errors.append(f"missing result binding: {binding_id}")
            elif sha256_file(path) != binding.get("sha256"):
                errors.append(f"result binding hash differs: {binding_id}")

    if result.get("execution") != EXPECTED_EXECUTION:
        errors.append("execution observation differs")
    if result.get("aggregate_observations_per_replay") != EXPECTED_AGGREGATE:
        errors.append("aggregate observations differ")
    if result.get("predeclared_gate_audit") != EXPECTED_GATES:
        errors.append("predeclared gate audit differs")
    if result.get("gate_summary") != {
        "predeclared_gate_count": 17,
        "predeclared_gate_pass_count": 16,
        "all_predeclared_gates_pass": False,
        "failed_gate_ids": [
            "applied_case_minimum_post_correction_core_correlation_each_channel"
        ],
    }:
        errors.append("gate summary differs")
    if result.get("access_boundary") != EXPECTED_ACCESS:
        errors.append("access boundary differs")
    if result.get("claim_boundary") != EXPECTED_CLAIMS:
        errors.append("claim boundary differs")

    serialized = json.dumps(result, sort_keys=True)
    forbidden_fragments = (
        "/Users/",
        "Application Support",
        "source_opaque_reference_id",
        "input_f64le_sha256",
        "output_f64le_sha256",
        '"cases"',
    )
    for fragment in forbidden_fragments:
        if fragment in serialized:
            errors.append(f"result exposes prohibited private detail: {fragment}")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=RESULT)
    args = parser.parse_args()
    result = load_json(args.result)
    errors = validate_result(result)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        json.dumps(
            {
                "status": "aggregate_only_odaq_retained_drift_result_valid",
                "reference_count": result["aggregate_observations_per_replay"][
                    "reference_count"
                ],
                "case_count_per_replay": result["aggregate_observations_per_replay"][
                    "attempted_case_count"
                ],
                "gate_pass_count": result["gate_summary"][
                    "predeclared_gate_pass_count"
                ],
                "gate_count": result["gate_summary"]["predeclared_gate_count"],
                "paths_redacted": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
