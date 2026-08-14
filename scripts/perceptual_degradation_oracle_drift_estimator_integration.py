#!/usr/bin/env python3
"""Replay end-to-end synthetic drift estimation and score-free correction."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path
from typing import Any, Sequence

import perceptual_degradation_alignment_v2 as alignment
import perceptual_degradation_negative_control_technical_repair as technical
import perceptual_degradation_oracle as oracle
import perceptual_degradation_oracle_drift_integration as integration
import perceptual_degradation_oracle_drift_resampler as resampler


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/"
    "oracle-drift-estimator-integration-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-oracle-drift-estimator-integration-20260814-001.json"
)
PLAN_ID = "perceptual-degradation-oracle-drift-estimator-integration-20260814-001"
REPORT_ID = PLAN_ID

EXPECTED_BINDINGS = {
    "research_contract",
    "technical_repair_plan",
    "technical_repair_report",
    "resampler_freeze",
    "resampler_report",
    "synthetic_integration_plan",
    "synthetic_integration_implementation",
    "synthetic_integration_report",
}

EXPECTED_AUTHORIZATION = {
    "committed_metadata_and_source_read_authorized": True,
    "synthetic_numeric_fixture_execution_authorized": True,
    "synthetic_pcm_fixture_execution_authorized": True,
    "synthetic_drift_estimation_authorized": True,
    "frozen_resampler_synthetic_execution_authorized": True,
    "retained_audio_access_authorized": False,
    "provider_audio_access_authorized": False,
    "source_or_condition_selection_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "human_response_access_authorized": False,
    "human_collection_authorized": False,
    "sealed_evidence_access_authorized": False,
    "no_reference_training_authorized": False,
    "public_verdict_enabled": False,
}

EXPECTED_RESOURCES = {
    "minimum_free_disk_gib": 15,
    "maximum_workers": 1,
    "fresh_temporary_directories": True,
    "replay_count": 2,
    "byte_identical_reports_required": True,
    "retain_generated_audio": False,
}

EXPECTED_ESTIMATOR = {
    "estimator_id": "bounded-drift-stereo-held-out-correlation-v1",
    "sample_rate_hz": 2000,
    "duration_seconds": 12,
    "actual_drift_ppm_cases": [75, -60, 0, 20, -20, 100, -100],
    "candidate_drift_ppm_minimum": -100,
    "candidate_drift_ppm_maximum": 100,
    "candidate_drift_ppm_step": 5,
    "window_seconds": 1,
    "window_start_seconds": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "training_window_positions": [0, 2, 4, 6, 8],
    "held_out_window_positions": [1, 3, 5, 7, 9],
    "selection_metric": "mean_cosine_correlation_across_channels_and_training_windows",
    "selection_tie_break": "higher_score_then_lower_abs_ppm_then_lower_signed_ppm",
    "selection_uses_held_out_windows": False,
    "proxy_interpolator": "binary64_linear_interpolation",
    "proxy_interpolator_is_frozen_resampler": False,
    "minimum_selection_margin": 0.0001,
    "minimum_held_out_correlation_after_correction": 0.99,
    "minimum_held_out_correlation_improvement_to_apply": 0.05,
    "expected_selected_correction_ppm": [75, -60, 0, 20, -20, 100, -100],
    "expected_apply_correction": [True, True, False, False, False, True, True],
    "reference_fixture_sample_quantization": "signed_q20_round_half_to_even",
    "reported_float_quantization_decimal_places": 12,
}

EXPECTED_CORRECTION = {
    "implementation": "oracle-bounded-drift-kaiser-sinc128-q30-v1",
    "coefficient_table_sha256": (
        "dbe4442199b56cd56880f1f45c09889721519dd7a165a4de76117b5e219dab82"
    ),
    "apply_only_after_held_out_decision": True,
    "output_frame_count_when_applied": "reference_frame_count",
    "mandatory_discard_frames_each_edge_when_applied": 64,
    "zero_drift_policy": "bit_exact_identity_bypass",
    "nonzero_no_apply_policy": "bit_exact_observed_passthrough",
    "post_decision_alignment": "perceptual_degradation_alignment_v2",
    "post_decision_oracle_envelope": (
        "perceptual_degradation_full_reference_oracle_score_free_v1"
    ),
    "pcm_lifetime": "temporary_in_memory_only",
    "metric_execution": False,
}

EXPECTED_GATES = {
    "expected_case_count": 7,
    "expected_applied_case_count": 4,
    "expected_nonzero_no_apply_case_count": 2,
    "selected_ppm_must_match_expected": True,
    "selection_must_not_use_held_out_windows": True,
    "apply_decision_must_match_expected": True,
    "minimum_applied_post_correction_core_correlation_each_channel": 0.999,
    "minimum_applied_core_correlation_improvement_each_channel": 0.1,
    "post_decision_alignment_must_be_supported": True,
    "zero_and_nonzero_no_apply_outputs_must_be_bit_exact": True,
    "score_free_oracle_must_remain_execution_blocked": True,
    "perceptual_metric_must_not_execute": True,
    "fresh_replays_must_be_byte_identical": True,
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
    if plan.get("state") != "score_blind_synthetic_drift_estimator_and_correction_frozen":
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
    if plan.get("authorization") != EXPECTED_AUTHORIZATION:
        errors.append("authorization boundary differs")
    if plan.get("resources") != EXPECTED_RESOURCES:
        errors.append("resource boundary differs")
    if plan.get("estimator") != EXPECTED_ESTIMATOR:
        errors.append("estimator contract differs")
    if plan.get("correction") != EXPECTED_CORRECTION:
        errors.append("correction contract differs")
    if plan.get("predeclared_gates") != EXPECTED_GATES:
        errors.append("predeclared gates differ")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def _reported(plan: dict[str, Any], value: float) -> float:
    places = plan["estimator"]["reported_float_quantization_decimal_places"]
    return round(float(value), places)


def _window_correlation(
    left: Sequence[float], right: Sequence[float], start: int, end: int
) -> float:
    if end > min(len(left), len(right)) or end <= start:
        raise ValueError("correlation window differs")
    dot = math.fsum(left[index] * right[index] for index in range(start, end))
    left_energy = math.fsum(left[index] ** 2 for index in range(start, end))
    right_energy = math.fsum(right[index] ** 2 for index in range(start, end))
    if left_energy <= 0.0 or right_energy <= 0.0:
        raise ValueError("correlation window energy differs")
    return dot / math.sqrt(left_energy * right_energy)


def _mean_window_correlation(
    reference: Sequence[Sequence[float]],
    test: Sequence[Sequence[float]],
    windows: Sequence[tuple[int, int]],
    positions: Sequence[int],
) -> float:
    if len(reference) != len(test) or not reference or not positions:
        raise ValueError("correlation inventory differs")
    values = [
        _window_correlation(reference_channel, test_channel, *windows[position])
        for reference_channel, test_channel in zip(reference, test, strict=True)
        for position in positions
    ]
    return math.fsum(values) / len(values)


def estimate_decision(
    plan: dict[str, Any],
    reference: Sequence[Sequence[float]],
    observed: Sequence[Sequence[float]],
) -> tuple[dict[str, Any], list[list[float]]]:
    estimator = plan["estimator"]
    sample_rate = estimator["sample_rate_hz"]
    output_frames = len(reference[0])
    windows = [
        (
            round(second * sample_rate),
            round((second + estimator["window_seconds"]) * sample_rate),
        )
        for second in estimator["window_start_seconds"]
    ]
    scored: list[tuple[float, int, list[list[float]]]] = []
    for correction_ppm in range(
        estimator["candidate_drift_ppm_minimum"],
        estimator["candidate_drift_ppm_maximum"] + 1,
        estimator["candidate_drift_ppm_step"],
    ):
        proxy = [
            technical.correct_synthetic_drift(
                channel, output_frames, correction_ppm
            )
            for channel in observed
        ]
        score = _reported(
            plan,
            _mean_window_correlation(
                reference,
                proxy,
                windows,
                estimator["training_window_positions"],
            ),
        )
        scored.append((score, correction_ppm, proxy))
    scored.sort(
        key=lambda row: (row[0], -abs(row[1]), -row[1]), reverse=True
    )
    selection_score, selected_ppm, selected_proxy = scored[0]
    selection_margin = _reported(plan, selection_score - scored[1][0])
    held_before = _reported(
        plan,
        _mean_window_correlation(
            reference,
            observed,
            windows,
            estimator["held_out_window_positions"],
        ),
    )
    held_after = _reported(
        plan,
        _mean_window_correlation(
            reference,
            selected_proxy,
            windows,
            estimator["held_out_window_positions"],
        ),
    )
    improvement = _reported(plan, held_after - held_before)
    apply_correction = (
        selected_ppm != 0
        and selection_margin >= estimator["minimum_selection_margin"]
        and held_after
        >= estimator["minimum_held_out_correlation_after_correction"]
        and improvement
        >= estimator["minimum_held_out_correlation_improvement_to_apply"]
    )
    return (
        {
            "selected_correction_ppm": selected_ppm,
            "selection_mean_correlation": selection_score,
            "selection_margin": selection_margin,
            "held_out_mean_correlation_before": held_before,
            "held_out_mean_correlation_after_proxy": held_after,
            "held_out_mean_correlation_improvement_proxy": improvement,
            "apply_correction": apply_correction,
            "selection_used_held_out_windows": False,
            "proxy_interpolator_is_frozen_resampler": False,
        },
        selected_proxy,
    )


def _overlap_correlation(
    plan: dict[str, Any], left: Sequence[float], right: Sequence[float]
) -> float:
    length = min(len(left), len(right))
    return _reported(plan, _window_correlation(left, right, 0, length))


def process_case(
    plan: dict[str, Any],
    actual_ppm: int,
    table: Sequence[Sequence[int]],
) -> dict[str, Any]:
    estimator = plan["estimator"]
    reference = integration._reference_channels(
        estimator["sample_rate_hz"], estimator["duration_seconds"]
    )
    observed = integration._observed_channels(reference, actual_ppm)
    decision, _ = estimate_decision(plan, reference, observed)
    selected_ppm = decision["selected_correction_ppm"]
    apply_correction = decision["apply_correction"]

    freeze = load_json(_bound(plan, "resampler_freeze"))
    candidate = freeze["candidate"]
    resampler_invoked = apply_correction or selected_ppm == 0
    if resampler_invoked:
        corrected = resampler.resample_channels(
            observed,
            output_frames=len(reference[0]),
            correction_ppm=selected_ppm if apply_correction else 0,
            candidate=candidate,
            table=table,
        )
    else:
        corrected = [[float(value) for value in channel] for channel in observed]

    discard = (
        plan["correction"]["mandatory_discard_frames_each_edge_when_applied"]
        if apply_correction
        else 0
    )
    reference_core = [
        channel[discard : len(channel) - discard if discard else None]
        for channel in reference
    ]
    corrected_core = [
        channel[discard : len(channel) - discard if discard else None]
        for channel in corrected
    ]
    observed_core = [
        channel[discard : discard + len(reference_core[index])]
        for index, channel in enumerate(observed)
    ]
    metrics = []
    for channel_index, (expected, before, after) in enumerate(
        zip(reference_core, observed_core, corrected_core, strict=True)
    ):
        before_correlation = _overlap_correlation(plan, expected, before)
        after_correlation = _overlap_correlation(plan, expected, after)
        metrics.append(
            {
                "channel_index": channel_index,
                "reference_core_frame_count": len(expected),
                "output_core_frame_count": len(after),
                "correlation_before": before_correlation,
                "correlation_after": after_correlation,
                "correlation_improvement": _reported(
                    plan, after_correlation - before_correlation
                ),
            }
        )

    aligned = alignment.align_channels(
        reference_channels=reference_core,
        test_channels=corrected_core,
        reference_channel_map=["L", "R"],
        test_channel_map=["L", "R"],
        sample_rate_hz=estimator["sample_rate_hz"],
        recipe_identity=f"{PLAN_ID}\0drift-{actual_ppm:+d}-ppm",
    )
    score_free = oracle.assemble_score_free(aligned)
    input_bytes = resampler.pack_f64_channels(observed)
    output_bytes = resampler.pack_f64_channels(corrected)
    return {
        "actual_drift_ppm": actual_ppm,
        "decision": decision,
        "resampler_invoked": resampler_invoked,
        "resampler_correction_applied": apply_correction,
        "mandatory_discard_frames_each_edge": discard,
        "reference_frame_count": len(reference[0]),
        "observed_frame_count": len(observed[0]),
        "output_frame_count": len(corrected[0]),
        "input_f64le_sha256": sha256_bytes(input_bytes),
        "output_f64le_sha256": sha256_bytes(output_bytes),
        "output_bit_exact_to_observed": output_bytes == input_bytes,
        "channel_core_metrics": metrics,
        "post_decision_alignment": {
            "status": aligned["status"],
            "reasons": aligned["support"]["reasons"],
            "clock_drift_ppm": _reported(
                plan, aligned["alignment"]["clock_drift_ppm"]
            ),
            "minimum_correlation": _reported(
                plan, aligned["alignment"]["minimum_correlation"]
            ),
            "edge_trim_seconds": _reported(
                plan, aligned["alignment"]["edge_trim_seconds"]
            ),
        },
        "score_free_oracle": {
            "result_state": score_free["result_state"],
            "metric_execution_states": [
                family["execution_state"] for family in score_free["metric_families"]
            ],
            "impairment_severity": score_free["outcomes"]["impairment_severity"],
            "audibility_probability": score_free["outcomes"]["audibility_probability"],
            "support": score_free["support"],
        },
        "retained_audio_accessed": False,
        "perceptual_metric_executed": False,
        "perceptual_truth_included": False,
        "human_response_accessed": False,
        "public_verdict_enabled": False,
    }


def build_payload(plan: dict[str, Any]) -> dict[str, Any]:
    integration_report = load_json(_bound(plan, "synthetic_integration_report"))
    if integration_report.get("all_predeclared_gates_pass") is not True:
        raise ValueError("bound synthetic correction integration no longer passes")
    frozen_report = load_json(_bound(plan, "resampler_report"))
    if resampler.validate_report(frozen_report):
        raise ValueError("bound frozen-resampler report no longer validates")
    freeze = load_json(_bound(plan, "resampler_freeze"))
    table = resampler.coefficient_table(freeze["candidate"])
    table_hash = sha256_bytes(resampler.coefficient_table_bytes(table))
    if table_hash != plan["correction"]["coefficient_table_sha256"]:
        raise ValueError("bound resampler coefficient table differs")

    cases = [
        process_case(plan, actual_ppm, table)
        for actual_ppm in plan["estimator"]["actual_drift_ppm_cases"]
    ]
    expected_selected = plan["estimator"]["expected_selected_correction_ppm"]
    expected_apply = plan["estimator"]["expected_apply_correction"]
    gates = plan["predeclared_gates"]
    applied = [case for case in cases if case["decision"]["apply_correction"]]
    nonzero_no_apply = [
        case
        for case in cases
        if case["actual_drift_ppm"] != 0
        and not case["decision"]["apply_correction"]
    ]
    passthrough = [
        case for case in cases if not case["decision"]["apply_correction"]
    ]
    gate_audit = {
        "case_inventory": len(cases) == gates["expected_case_count"],
        "selected_ppm": (
            [case["decision"]["selected_correction_ppm"] for case in cases]
            == expected_selected
        ),
        "training_held_out_isolation": all(
            case["decision"]["selection_used_held_out_windows"] is False
            for case in cases
        ),
        "apply_decision": (
            [case["decision"]["apply_correction"] for case in cases]
            == expected_apply
            and len(applied) == gates["expected_applied_case_count"]
            and len(nonzero_no_apply)
            == gates["expected_nonzero_no_apply_case_count"]
        ),
        "held_out_apply_rule": all(
            case["decision"]["selection_margin"]
            >= plan["estimator"]["minimum_selection_margin"]
            and case["decision"]["held_out_mean_correlation_after_proxy"]
            >= plan["estimator"][
                "minimum_held_out_correlation_after_correction"
            ]
            and case["decision"]["held_out_mean_correlation_improvement_proxy"]
            >= plan["estimator"][
                "minimum_held_out_correlation_improvement_to_apply"
            ]
            for case in applied
        ),
        "nonzero_no_apply_rule": all(
            case["decision"]["held_out_mean_correlation_improvement_proxy"]
            < plan["estimator"][
                "minimum_held_out_correlation_improvement_to_apply"
            ]
            for case in nonzero_no_apply
        ),
        "resampler_invocation": all(
            case["resampler_invoked"]
            is (
                case["decision"]["apply_correction"]
                or case["decision"]["selected_correction_ppm"] == 0
            )
            for case in cases
        ),
        "applied_core_correlation": all(
            metric["correlation_after"]
            >= gates[
                "minimum_applied_post_correction_core_correlation_each_channel"
            ]
            for case in applied
            for metric in case["channel_core_metrics"]
        ),
        "applied_core_improvement": all(
            metric["correlation_improvement"]
            >= gates["minimum_applied_core_correlation_improvement_each_channel"]
            for case in applied
            for metric in case["channel_core_metrics"]
        ),
        "passthrough_bit_exact": all(
            case["output_bit_exact_to_observed"] is True for case in passthrough
        ),
        "post_decision_alignment_supported": all(
            case["post_decision_alignment"]["status"] == "supported"
            and not case["post_decision_alignment"]["reasons"]
            for case in cases
        ),
        "score_free_oracle_closed": all(
            case["score_free_oracle"]["result_state"] == "execution_blocked"
            and set(case["score_free_oracle"]["metric_execution_states"])
            == {"not_authorized"}
            and case["score_free_oracle"]["impairment_severity"] is None
            and case["score_free_oracle"]["audibility_probability"] is None
            for case in cases
        ),
        "metric_human_and_public_boundaries": all(
            case["retained_audio_accessed"] is False
            and case["perceptual_metric_executed"] is False
            and case["perceptual_truth_included"] is False
            and case["human_response_accessed"] is False
            and case["public_verdict_enabled"] is False
            for case in cases
        ),
    }
    return {
        "coefficient_table_sha256": table_hash,
        "cases": cases,
        "gate_audit": gate_audit,
        "all_predeclared_gates_pass": all(gate_audit.values()),
    }


def build_report(
    plan: dict[str, Any], plan_path: Path = PLAN_PATH
) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    resampler.require_disk_reserve(
        ROOT, plan["resources"]["minimum_free_disk_gib"]
    )
    payloads: list[bytes] = []
    for _ in range(plan["resources"]["replay_count"]):
        with tempfile.TemporaryDirectory(
            prefix="lossytrace-oracle-drift-estimator-integration-"
        ) as directory:
            path = Path(directory) / "payload.json"
            path.write_bytes(canonical_bytes(build_payload(plan)))
            payloads.append(path.read_bytes())
    if len(set(payloads)) != 1:
        raise ValueError("fresh estimator-integration replays differ")
    payload = json.loads(payloads[0])
    report = {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "score_blind_synthetic_drift_estimator_and_correction_replayed",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "authority": plan["authorization"],
        "resources": {
            "minimum_free_disk_gib_preserved": plan["resources"][
                "minimum_free_disk_gib"
            ],
            "maximum_workers_used": 1,
            "generated_audio_retained": False,
        },
        "replay_observation": {
            "fresh_temporary_replay_count": len(payloads),
            "payload_sha256s": [sha256_bytes(value) for value in payloads],
            "byte_identical": len(set(payloads)) == 1,
            "paths_included": False,
            "timing_included": False,
        },
        **payload,
        "summary": {
            "synthetic_case_count": len(payload["cases"]),
            "estimated_case_count": len(payload["cases"]),
            "applied_correction_case_count": sum(
                case["decision"]["apply_correction"] for case in payload["cases"]
            ),
            "nonzero_no_apply_case_count": sum(
                case["actual_drift_ppm"] != 0
                and not case["decision"]["apply_correction"]
                for case in payload["cases"]
            ),
            "predeclared_gate_count": len(payload["gate_audit"]),
            "predeclared_gate_pass_count": sum(payload["gate_audit"].values()),
            "actual_audio_accessed": False,
            "retained_audio_accessed": False,
            "perceptual_metric_executed": False,
            "perceptual_truth_included": False,
            "human_response_accessed": False,
            "human_collection_performed": False,
            "no_reference_training_performed": False,
            "public_verdict_enabled": False,
        },
        "decision": {
            "synthetic_drift_estimation_executed": True,
            "training_window_selection_and_held_out_apply_rule_integrated": (
                payload["all_predeclared_gates_pass"]
            ),
            "exact_frozen_resampler_integrated_after_estimation": (
                payload["all_predeclared_gates_pass"]
            ),
            "score_free_oracle_envelope_preserved": payload["gate_audit"][
                "score_free_oracle_closed"
            ],
            "retained_audio_correction_executed": False,
            "retained_audio_correction_validated": False,
            "real_audio_drift_estimation_validated": False,
            "human_or_perceptual_validity_present": False,
            "full_reference_oracle_validated": False,
            "human_collection_authorized": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "next_gate": (
                "Under separate authority, validate the exact estimator, held-out "
                "apply rule and correction path on retained development pairs before "
                "any perceptual metric execution."
            ),
        },
        "claim_boundary": plan["claim_boundary"],
    }
    report_errors = validate_report(report)
    if report_errors:
        raise ValueError("; ".join(report_errors))
    return report


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != 1 or report.get("report_id") != REPORT_ID:
        errors.append("report identity differs")
    if report.get("state") != "score_blind_synthetic_drift_estimator_and_correction_replayed":
        errors.append("report state differs")
    if report.get("authority") != EXPECTED_AUTHORIZATION:
        errors.append("report authority differs")
    replay = report.get("replay_observation", {})
    if (
        replay.get("fresh_temporary_replay_count") != 2
        or replay.get("byte_identical") is not True
        or len(set(replay.get("payload_sha256s", []))) != 1
        or replay.get("paths_included") is not False
        or replay.get("timing_included") is not False
    ):
        errors.append("replay observation differs")
    cases = report.get("cases", [])
    if [case.get("actual_drift_ppm") for case in cases] != [75, -60, 0, 20, -20, 100, -100]:
        errors.append("case inventory differs")
    else:
        selected = [
            case.get("decision", {}).get("selected_correction_ppm") for case in cases
        ]
        applied = [case.get("decision", {}).get("apply_correction") for case in cases]
        if selected != EXPECTED_ESTIMATOR["expected_selected_correction_ppm"]:
            errors.append("selected correction inventory differs")
        if applied != EXPECTED_ESTIMATOR["expected_apply_correction"]:
            errors.append("apply decision inventory differs")
        for case in cases:
            for key in (
                "retained_audio_accessed",
                "perceptual_metric_executed",
                "perceptual_truth_included",
                "human_response_accessed",
                "public_verdict_enabled",
            ):
                if case.get(key) is not False:
                    errors.append(
                        f"case boundary differs: {case.get('actual_drift_ppm')}:{key}"
                    )
    gates = report.get("gate_audit")
    if not isinstance(gates, dict) or len(gates) != 13 or not all(gates.values()):
        errors.append("predeclared gates did not all pass")
    if report.get("all_predeclared_gates_pass") is not True:
        errors.append("all-gates decision differs")
    summary = report.get("summary", {})
    for key in (
        "actual_audio_accessed",
        "retained_audio_accessed",
        "perceptual_metric_executed",
        "perceptual_truth_included",
        "human_response_accessed",
        "human_collection_performed",
        "no_reference_training_performed",
        "public_verdict_enabled",
    ):
        if summary.get(key) is not False:
            errors.append(f"summary boundary differs: {key}")
    decision = report.get("decision", {})
    for key in (
        "synthetic_drift_estimation_executed",
        "training_window_selection_and_held_out_apply_rule_integrated",
        "exact_frozen_resampler_integrated_after_estimation",
        "score_free_oracle_envelope_preserved",
    ):
        if decision.get(key) is not True:
            errors.append(f"decision must be true: {key}")
    for key in (
        "retained_audio_correction_executed",
        "retained_audio_correction_validated",
        "real_audio_drift_estimation_validated",
        "human_or_perceptual_validity_present",
        "full_reference_oracle_validated",
        "human_collection_authorized",
        "no_reference_work_eligible",
        "public_verdict_enabled",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision must be false: {key}")
    claims = report.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    report = build_report(load_json(args.plan), args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(report))
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
