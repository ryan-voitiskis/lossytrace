#!/usr/bin/env python3
"""Replay score-free synthetic integration of the frozen drift resampler."""

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
import perceptual_degradation_oracle_drift_resampler as resampler


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/oracle-drift-integration-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-oracle-drift-integration-20260814-001.json"
)
PLAN_ID = "perceptual-degradation-oracle-drift-integration-20260814-001"
REPORT_ID = "perceptual-degradation-oracle-drift-integration-20260814-001"

EXPECTED_BINDINGS = {
    "research_contract",
    "technical_repair_plan",
    "technical_repair_report",
    "resampler_freeze",
    "resampler_report",
    "resampler_implementation",
    "alignment_implementation",
    "score_free_oracle_plan",
    "score_free_oracle_implementation",
    "score_free_oracle_replay",
}

EXPECTED_AUTHORIZATION = {
    "committed_metadata_and_source_read_authorized": True,
    "synthetic_numeric_fixture_execution_authorized": True,
    "synthetic_pcm_fixture_execution_authorized": True,
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

EXPECTED_INTEGRATION = {
    "decision_source": "bound_technical_repair_report_bounded_clock_drift_cases",
    "decision_cases_ppm": [75, -60, 0],
    "decision_selection_uses_held_out_windows": False,
    "apply_requires_bound_held_out_improvement_gate": True,
    "observation_generator": "bound_binary64_linear_interpolation_fixture",
    "observation_generator_is_frozen_resampler": False,
    "correction_implementation": "oracle-bounded-drift-kaiser-sinc128-q30-v1",
    "coefficient_table_sha256": (
        "dbe4442199b56cd56880f1f45c09889721519dd7a165a4de76117b5e219dab82"
    ),
    "output_frame_count": "reference_frame_count",
    "mandatory_discard_frames_each_edge_when_applied": 64,
    "zero_drift_policy": "bit_exact_identity_bypass",
    "post_correction_alignment": "perceptual_degradation_alignment_v2",
    "post_correction_oracle_envelope": (
        "perceptual_degradation_full_reference_oracle_score_free_v1"
    ),
    "corrected_pcm_lifetime": "temporary_in_memory_only",
    "metric_execution": False,
}

EXPECTED_GATES = {
    "expected_case_count": 3,
    "expected_applied_case_count": 2,
    "minimum_post_correction_core_correlation_each_channel": 0.999,
    "minimum_applied_case_core_correlation_improvement_each_channel": 0.1,
    "maximum_abs_post_correction_alignment_drift_ppm": 1.0,
    "post_correction_alignment_must_be_supported": True,
    "zero_drift_output_must_be_bit_exact": True,
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
    if plan.get("state") != "score_blind_synthetic_oracle_drift_integration_frozen":
        errors.append("plan state differs")
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != EXPECTED_BINDINGS:
        errors.append("binding inventory differs")
        bindings = {}
    for binding_id, binding in bindings.items():
        if not isinstance(binding, dict):
            errors.append(f"binding differs: {binding_id}")
            continue
        path = root / str(binding.get("path", ""))
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")
    if plan.get("authorization") != EXPECTED_AUTHORIZATION:
        errors.append("authorization boundary differs")
    if plan.get("resources") != EXPECTED_RESOURCES:
        errors.append("resource boundary differs")
    if plan.get("integration") != EXPECTED_INTEGRATION:
        errors.append("integration contract differs")
    if plan.get("predeclared_gates") != EXPECTED_GATES:
        errors.append("predeclared gates differ")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def _decision_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    report = load_json(_bound(plan, "technical_repair_report"))
    if report.get("decision", {}).get("bounded_drift_synthetic_decision_fixture_ready") is not True:
        raise ValueError("bound held-out drift decision is not ready")
    rows = report.get("bounded_clock_drift_cases")
    if not isinstance(rows, list):
        raise ValueError("bound held-out drift decision cases differ")
    expected_ppm = plan["integration"]["decision_cases_ppm"]
    if [row.get("actual_drift_ppm") for row in rows] != expected_ppm:
        raise ValueError("bound held-out drift decision inventory differs")
    for row in rows:
        ppm = row.get("actual_drift_ppm")
        if (
            row.get("selected_correction_ppm") != ppm
            or row.get("apply_correction") is not (ppm != 0)
            or row.get("selection_used_held_out_windows") is not False
            or row.get("production_resampler_executed") is not False
            or row.get("perceptual_truth_included") is not False
        ):
            raise ValueError(f"bound held-out drift decision differs: {ppm}")
    return rows


def _reference_channels(sample_rate: int, seconds: int) -> list[list[float]]:
    left = technical.synthetic_alignment_fixture(sample_rate, seconds)
    right = [
        0.83 * value + 0.09 * ((index % 257) / 256.0 - 0.5)
        for index, value in enumerate(left)
    ]
    return [left, right]


def _observed_channels(
    reference: Sequence[Sequence[float]], correction_ppm: int
) -> list[list[float]]:
    if correction_ppm == 0:
        return [[float(value) for value in channel] for channel in reference]
    return [
        technical.apply_synthetic_drift(channel, correction_ppm)
        for channel in reference
    ]


def _correlation(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("correlation geometry differs")
    dot = math.fsum(a * b for a, b in zip(left, right, strict=True))
    left_energy = math.fsum(value * value for value in left)
    right_energy = math.fsum(value * value for value in right)
    if left_energy <= 0.0 or right_energy <= 0.0:
        raise ValueError("correlation energy differs")
    return dot / math.sqrt(left_energy * right_energy)


def integrate_case(
    plan: dict[str, Any],
    decision: dict[str, Any],
    table: Sequence[Sequence[int]],
) -> dict[str, Any]:
    repair_plan = load_json(_bound(plan, "technical_repair_plan"))
    fixture = repair_plan["bounded_clock_drift_candidate"]
    sample_rate = fixture["sample_rate_hz"]
    seconds = fixture["duration_seconds"]
    reference = _reference_channels(sample_rate, seconds)
    actual_ppm = decision["actual_drift_ppm"]
    selected_ppm = decision["selected_correction_ppm"]
    apply_correction = decision["apply_correction"]
    correction_ppm = selected_ppm if apply_correction else 0
    observed = _observed_channels(reference, actual_ppm)

    freeze = load_json(_bound(plan, "resampler_freeze"))
    candidate = freeze["candidate"]
    corrected = resampler.resample_channels(
        observed,
        output_frames=len(reference[0]),
        correction_ppm=correction_ppm,
        candidate=candidate,
        table=table,
    )
    discard = (
        plan["integration"]["mandatory_discard_frames_each_edge_when_applied"]
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
    correlations = []
    for channel_index, (expected, before, after) in enumerate(
        zip(reference_core, observed_core, corrected_core, strict=True)
    ):
        before_correlation = _correlation(expected, before)
        after_correlation = _correlation(expected, after)
        correlations.append(
            {
                "channel_index": channel_index,
                "core_frame_count": len(expected),
                "correlation_before": before_correlation,
                "correlation_after": after_correlation,
                "correlation_improvement": after_correlation - before_correlation,
            }
        )

    aligned = alignment.align_channels(
        reference_channels=reference_core,
        test_channels=corrected_core,
        reference_channel_map=["L", "R"],
        test_channel_map=["L", "R"],
        sample_rate_hz=sample_rate,
        recipe_identity=f"{PLAN_ID}\0drift-{actual_ppm:+d}-ppm",
    )
    score_free = oracle.assemble_score_free(aligned)
    metric_states = [family["execution_state"] for family in score_free["metric_families"]]
    return {
        "actual_drift_ppm": actual_ppm,
        "selected_correction_ppm": selected_ppm,
        "apply_correction": apply_correction,
        "selection_used_held_out_windows": False,
        "reference_frame_count": len(reference[0]),
        "observed_frame_count": len(observed[0]),
        "output_frame_count": len(corrected[0]),
        "mandatory_discard_frames_each_edge": discard,
        "input_f64le_sha256": sha256_bytes(resampler.pack_f64_channels(observed)),
        "output_f64le_sha256": sha256_bytes(resampler.pack_f64_channels(corrected)),
        "identity_output_bit_exact": (
            resampler.pack_f64_channels(observed)
            == resampler.pack_f64_channels(corrected)
            if not apply_correction
            else None
        ),
        "channel_core_metrics": correlations,
        "post_correction_alignment": {
            "status": aligned["status"],
            "reasons": aligned["support"]["reasons"],
            "clock_drift_ppm": aligned["alignment"]["clock_drift_ppm"],
            "minimum_correlation": aligned["alignment"]["minimum_correlation"],
            "minimum_structural_window_correlation": aligned["alignment"][
                "minimum_structural_window_correlation"
            ],
        },
        "score_free_oracle": {
            "record_sha256": sha256_bytes(oracle.canonical_bytes(score_free)),
            "result_state": score_free["result_state"],
            "metric_execution_states": metric_states,
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
    freeze = load_json(_bound(plan, "resampler_freeze"))
    frozen_report = load_json(_bound(plan, "resampler_report"))
    if resampler.validate_report(frozen_report):
        raise ValueError("bound frozen-resampler report no longer validates")
    if frozen_report["decision"]["candidate_selected_as_frozen_oracle_resampler"] is not True:
        raise ValueError("bound resampler candidate is not selected")
    if freeze["candidate"]["resampler_id"] != plan["integration"]["correction_implementation"]:
        raise ValueError("bound resampler identity differs")
    table = resampler.coefficient_table(freeze["candidate"])
    table_hash = sha256_bytes(resampler.coefficient_table_bytes(table))
    if table_hash != plan["integration"]["coefficient_table_sha256"]:
        raise ValueError("bound resampler coefficient table differs")
    if oracle.validate_replay(load_json(_bound(plan, "score_free_oracle_replay"))):
        raise ValueError("bound score-free oracle replay no longer validates")

    cases = [integrate_case(plan, row, table) for row in _decision_rows(plan)]
    gates = plan["predeclared_gates"]
    applied = [case for case in cases if case["apply_correction"]]
    identity = [case for case in cases if not case["apply_correction"]]
    gate_audit = {
        "case_inventory": (
            len(cases) == gates["expected_case_count"]
            and [case["actual_drift_ppm"] for case in cases]
            == plan["integration"]["decision_cases_ppm"]
        ),
        "apply_decision_projection": (
            len(applied) == gates["expected_applied_case_count"]
            and all(case["actual_drift_ppm"] != 0 for case in applied)
            and len(identity) == 1
            and identity[0]["actual_drift_ppm"] == 0
        ),
        "mandatory_edge_discard": all(
            case["mandatory_discard_frames_each_edge"]
            == (
                plan["integration"]["mandatory_discard_frames_each_edge_when_applied"]
                if case["apply_correction"]
                else 0
            )
            for case in cases
        ),
        "output_geometry": all(
            case["output_frame_count"] == case["reference_frame_count"]
            for case in cases
        ),
        "post_correction_core_correlation": all(
            metric["correlation_after"]
            >= gates["minimum_post_correction_core_correlation_each_channel"]
            for case in cases
            for metric in case["channel_core_metrics"]
        ),
        "applied_case_correlation_improvement": all(
            metric["correlation_improvement"]
            >= gates[
                "minimum_applied_case_core_correlation_improvement_each_channel"
            ]
            for case in applied
            for metric in case["channel_core_metrics"]
        ),
        "post_correction_alignment_supported": all(
            case["post_correction_alignment"]["status"] == "supported"
            and not case["post_correction_alignment"]["reasons"]
            for case in cases
        ),
        "post_correction_alignment_drift": all(
            abs(case["post_correction_alignment"]["clock_drift_ppm"])
            <= gates["maximum_abs_post_correction_alignment_drift_ppm"]
            for case in cases
        ),
        "zero_drift_identity": (
            identity[0]["identity_output_bit_exact"]
            is gates["zero_drift_output_must_be_bit_exact"]
        ),
        "score_free_oracle_closed": all(
            case["score_free_oracle"]["result_state"] == "execution_blocked"
            and set(case["score_free_oracle"]["metric_execution_states"])
            == {"not_authorized"}
            and case["score_free_oracle"]["impairment_severity"] is None
            and case["score_free_oracle"]["audibility_probability"] is None
            for case in cases
        ),
        "metric_and_human_boundaries": all(
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
            prefix="lossytrace-oracle-drift-integration-"
        ) as directory:
            path = Path(directory) / "payload.json"
            path.write_bytes(canonical_bytes(build_payload(plan)))
            payloads.append(path.read_bytes())
    if len(set(payloads)) != 1:
        raise ValueError("fresh synthetic integration replays differ")
    payload = json.loads(payloads[0])
    report = {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "score_blind_synthetic_oracle_drift_integration_replayed",
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
            "applied_correction_case_count": sum(
                case["apply_correction"] for case in payload["cases"]
            ),
            "technical_integration_gate_count": len(payload["gate_audit"]),
            "technical_integration_gate_pass_count": sum(
                payload["gate_audit"].values()
            ),
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
            "held_out_apply_decision_bound": True,
            "exact_frozen_resampler_integrated_on_synthetic_pcm": (
                payload["all_predeclared_gates_pass"]
            ),
            "score_free_oracle_envelope_preserved": (
                payload["gate_audit"]["score_free_oracle_closed"]
            ),
            "retained_audio_correction_executed": False,
            "retained_audio_correction_validated": False,
            "real_audio_drift_estimation_validated": False,
            "human_or_perceptual_validity_present": False,
            "full_reference_oracle_validated": False,
            "human_collection_authorized": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "next_gate": (
                "Under separate authority, validate the exact integrated correction "
                "and real drift-estimation behavior on retained development pairs "
                "before any perceptual metric execution."
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
    if report.get("state") != "score_blind_synthetic_oracle_drift_integration_replayed":
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
    if [case.get("actual_drift_ppm") for case in cases] != [75, -60, 0]:
        errors.append("case inventory differs")
    else:
        for case in cases:
            ppm = case.get("actual_drift_ppm")
            if (
                case.get("selected_correction_ppm") != ppm
                or case.get("apply_correction") is not (ppm != 0)
                or case.get("selection_used_held_out_windows") is not False
            ):
                errors.append(f"case decision differs: {ppm}")
            for key in (
                "retained_audio_accessed",
                "perceptual_metric_executed",
                "perceptual_truth_included",
                "human_response_accessed",
                "public_verdict_enabled",
            ):
                if case.get(key) is not False:
                    errors.append(f"case boundary differs: {ppm}:{key}")
    gates = report.get("gate_audit")
    if not isinstance(gates, dict) or len(gates) != 11 or not all(gates.values()):
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
        "held_out_apply_decision_bound",
        "exact_frozen_resampler_integrated_on_synthetic_pcm",
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
