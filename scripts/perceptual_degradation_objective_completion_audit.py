#!/usr/bin/env python3
"""Audit the full perceptual-degradation objective against bound evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "objective-completion-audit-plan.json"
)
PLAN_ID = "perceptual-degradation-objective-completion-audit-20260814-001"
REPORT_ID = "perceptual-degradation-objective-completion-audit-20260814-001"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "score_blind_completion_audit_frozen_no_new_execution_authority"
    ):
        errors.append("plan state differs")
    for binding_id, binding in plan.get("bindings", {}).items():
        path = root / str(binding.get("path", ""))
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")

    expected_authorization = {
        "bound_metadata_and_source_read_authorized": True,
        "synthetic_audit_execution_authorized": True,
        "exact_member_selection_authorized": False,
        "new_audio_acquisition_authorized": False,
        "retained_odaq_reference_read_authorized": False,
        "retained_reference_projection_authorized": False,
        "stimulus_generation_authorized": False,
        "processed_condition_access_authorized": False,
        "listening_score_access_authorized": False,
        "perceptual_metric_execution_authorized": False,
        "human_collection_authorized": False,
        "recruitment_authorized": False,
        "sealed_evidence_access_authorized": False,
        "no_reference_training_authorized": False,
        "public_verdict_enabled": False,
    }
    if plan.get("authorization") != expected_authorization:
        errors.append("authorization boundary differs")

    expected_requirements = [
        "estimand_is_degradation_not_history",
        "declared_playback_chain_qualified",
        "truth_bearing_source_manifest_feasible_and_frozen",
        "controlled_human_calibration_collected",
        "perceptual_metric_execution_and_legal_gate_passed",
        "deterministic_human_calibrated_full_reference_oracle_passed",
        "transparent_lossy_treated_as_non_degraded",
        "difficult_natural_and_production_negatives_preserved_in_evaluation",
        "grouped_source_domain_codec_encoder_transfer_passed",
        "no_reference_estimator_trained_and_independently_validated",
        "severity_audibility_artifact_support_uncertainty_abstention_reported",
        "public_cli_remains_verdict_free",
        "rigorous_negative_is_accepted_success",
        "final_research_recommendation_frozen",
    ]
    if plan.get("requirement_ids") != expected_requirements:
        errors.append("objective requirement inventory differs")

    expected_policy = {
        "all_requirement_ids_must_be_present": True,
        "all_completion_required_requirements_must_be_satisfied": True,
        "preparation_or_synthetic_replay_counts_as_scientific_completion": False,
        "green_tests_count_as_perceptual_evidence": False,
        "missing_or_indirect_evidence_counts_as_satisfied": False,
        "current_recommendation": None,
        "allowed_final_recommendations": [
            "reject_perceptual_estimation",
            "retain_full_reference_only",
            "continue_no_reference_research",
            "freeze_blind_final_validation",
        ],
    }
    if plan.get("completion_policy") != expected_policy:
        errors.append("completion policy differs")
    for key, value in plan.get("claim_boundary", {}).items():
        if value is not False:
            errors.append(f"claim boundary must remain false: {key}")
    return errors


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def _requirement(
    requirement_id: str,
    *,
    state: str,
    satisfied: bool,
    completion_required: bool,
    evidence: list[str],
    reason: str,
    next_gate: str | None,
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "state": state,
        "satisfied": satisfied,
        "completion_required": completion_required,
        "evidence": evidence,
        "reason": reason,
        "next_gate": next_gate,
    }


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))

    research = load_json(_bound(plan, "research_plan"))
    contract = _bound(plan, "research_contract").read_text(encoding="utf-8")
    metric_gate = load_json(_bound(plan, "metric_execution_gate"))
    oracle = load_json(_bound(plan, "score_free_oracle_plan"))
    evaluation = load_json(_bound(plan, "full_reference_evaluation_plan"))
    playback = load_json(_bound(plan, "playback_qualification_result"))
    feasibility = load_json(_bound(plan, "listening_feasibility_report"))
    allocation = load_json(_bound(plan, "provider_allocation_report"))
    sources = load_json(_bound(plan, "source_candidate_plan"))
    acquisition = load_json(_bound(plan, "odaq_acquisition_result"))
    public_library = _bound(plan, "public_library").read_text(encoding="utf-8")
    cli_test = _bound(plan, "public_cli_test").read_text(encoding="utf-8")

    estimand_ok = (
        research.get("objective")
        == "Estimate material perceptual degradation under controlled lossy coding, not prior codec history."
        and "decoded-PCM" in contract
        and "non-identifiability result" in contract
    )
    playback_ok = (
        playback.get("qualified_chain", {}).get("physical_playback_qualified") is True
        and playback.get("responsible_human_observations", {}).get(
            "degradation_rating_provided"
        )
        is False
    )
    source_manifest_ok = all(
        sources.get("decision", {}).get(key) is True
        for key in (
            "source_manifest_frozen",
            "provider_holdout_manifest_frozen",
            "domain_allocation_frozen",
            "original_coding_history_qualified",
        )
    )
    collection_ok = (
        research.get("human_truth", {}).get("main_collection_authorized") is True
        and playback.get("access_boundary", {}).get("listener_response_collected")
        is True
    )
    proxy = metric_gate.get("metric_families", {}).get(
        "gstpeaq_proxy_v0_6_1", {}
    )
    metric_ok = (
        metric_gate.get("perceptual_metric_execution_authorized") is True
        and proxy.get("research_use_legal_record_present") is True
        and proxy.get("synthetic_replay_complete") is True
    )
    full_reference_ok = (
        evaluation.get("claim_boundary", {}).get("full_reference_gate_passed")
        is True
        and evaluation.get("claim_boundary", {}).get(
            "synthetic_gate_pass_is_scientific_evidence"
        )
        is False
    )
    no_reference_ok = (
        evaluation.get("claim_boundary", {}).get("no_reference_work_eligible")
        is True
        and research.get("no_reference", {}).get(
            "each_holdout_axis_must_pass"
        )
        is True
    )
    output_schema = load_json(
        ROOT / oracle["bindings"]["oracle_schema"]["path"]
    )
    schema_properties = output_schema.get("properties", {})
    output_schema_ok = all(
        key in schema_properties
        for key in ("outcomes", "support", "uncertainty")
    )
    output_values_available = (
        oracle.get("score_free_output_boundary", {}).get(
            "impairment_severity_available"
        )
        is True
        and oracle.get("score_free_output_boundary", {}).get(
            "audibility_probability_available"
        )
        is True
        and oracle.get("score_free_output_boundary", {}).get(
            "artifact_profile_values_available"
        )
        is True
        and oracle.get("score_free_output_boundary", {}).get(
            "uncertainty_quantified"
        )
        is True
    )
    public_boundary_ok = (
        research.get("public_state", {}).get("public_verdict_enabled") is False
        and "public_verdict_enabled: false" in public_library
        and 'report["public_verdict_enabled"], false' in cli_test
    )
    negative_success_ok = (
        "A rigorous negative result is successful completion." in contract
        and set(plan["completion_policy"]["allowed_final_recommendations"])
        == {
            "reject_perceptual_estimation",
            "retain_full_reference_only",
            "continue_no_reference_research",
            "freeze_blind_final_validation",
        }
    )
    recommendation = plan["completion_policy"]["current_recommendation"]
    recommendation_ok = recommendation in plan["completion_policy"][
        "allowed_final_recommendations"
    ]

    requirements = [
        _requirement(
            "estimand_is_degradation_not_history",
            state="satisfied_contract_boundary" if estimand_ok else "incomplete",
            satisfied=estimand_ok,
            completion_required=True,
            evidence=["research_plan.objective", "research_contract.objective_boundary"],
            reason="The estimand and decoded-PCM causal limit are frozen before outcome access.",
            next_gate=None if estimand_ok else "Repair and re-freeze the scientific contract.",
        ),
        _requirement(
            "declared_playback_chain_qualified",
            state="satisfied_prerequisite" if playback_ok else "incomplete",
            satisfied=playback_ok,
            completion_required=True,
            evidence=["playback_qualification_result.qualified_chain"],
            reason="The declared RME/Adam 48 kHz chain passed delivery, channel and comfort qualification without collecting a rating.",
            next_gate=None if playback_ok else "Qualify a declared physical playback chain.",
        ),
        _requirement(
            "truth_bearing_source_manifest_feasible_and_frozen",
            state="incomplete",
            satisfied=source_manifest_ok,
            completion_required=True,
            evidence=[
                "source_candidate_plan.decision",
                "provider_allocation_report.decision",
                "listening_feasibility_report.decision",
            ],
            reason="Raw group capacity exists, but provider/domain allocation, original coding history and exact members are not frozen.",
            next_gate="Qualify additional providers or narrow the primary-domain claim, then freeze an exact grouped manifest.",
        ),
        _requirement(
            "controlled_human_calibration_collected",
            state="not_authorized",
            satisfied=collection_ok,
            completion_required=True,
            evidence=["research_plan.human_truth", "playback_qualification_result.access_boundary"],
            reason="No degradation rating or listener response has been collected.",
            next_gate="Complete source, stimulus, privacy, power and allocation gates before requesting collection authority.",
        ),
        _requirement(
        "perceptual_metric_execution_and_legal_gate_passed",
            state="blocked_by_legal_and_execution_gate",
            satisfied=metric_ok,
            completion_required=True,
            evidence=["metric_execution_gate.metric_families.gstpeaq_proxy_v0_6_1"],
            reason="ViSQOL synthetic replay is prepared, but the GstPEAQ proxy legal record, build and execution authority remain absent.",
            next_gate="Resolve the declared proxy legal/conformance boundary or commit a score-blind contract amendment.",
        ),
        _requirement(
            "deterministic_human_calibrated_full_reference_oracle_passed",
            state="synthetic_plumbing_only",
            satisfied=full_reference_ok,
            completion_required=True,
            evidence=["score_free_oracle_plan.claim_boundary", "full_reference_evaluation_plan.synthetic_replay"],
            reason="Schemas and grouped statistics replay deterministically, but no human-calibrated scientific gate has been evaluated.",
            next_gate="Run authorized metrics against valid human-calibration and grouped-transfer evidence.",
        ),
        _requirement(
            "transparent_lossy_treated_as_non_degraded",
            state="policy_frozen_truth_absent",
            satisfied=full_reference_ok and collection_ok,
            completion_required=True,
            evidence=["research_plan.human_truth", "full_reference_evaluation_plan.numeric_gates"],
            reason="The transparent-safety rule is frozen, but no adequately powered human-transparent lossy truth exists.",
            next_gate="Collect and pass the frozen equivalence and transparent-safety gates.",
        ),
        _requirement(
            "difficult_natural_and_production_negatives_preserved_in_evaluation",
            state="specified_not_evaluated",
            satisfied=full_reference_ok,
            completion_required=True,
            evidence=["research_plan.required_negative_classes"],
            reason=f"{len(research.get('required_negative_classes', []))} negative classes are required by plan, but have not entered scientific evaluation.",
            next_gate="Freeze exact negative members and retain them through grouped human and oracle evaluation.",
        ),
        _requirement(
            "grouped_source_domain_codec_encoder_transfer_passed",
            state="not_evaluated",
            satisfied=full_reference_ok,
            completion_required=True,
            evidence=["research_plan.grouping.required_holdout_axes", "provider_allocation_report.decision"],
            reason="The four holdout axes are frozen, but provider allocation and grouped transfer are untested.",
            next_gate="Pass fresh grouped full-reference transfer on every frozen axis.",
        ),
        _requirement(
            "no_reference_estimator_trained_and_independently_validated",
            state="not_started_by_design",
            satisfied=no_reference_ok and full_reference_ok,
            completion_required=True,
            evidence=["research_plan.no_reference", "full_reference_evaluation_plan.claim_boundary"],
            reason="No-reference work correctly remains ineligible until the full-reference oracle passes.",
            next_gate="Only after the full-reference pass, freeze, train and validate the estimator on every held-out axis.",
        ),
        _requirement(
            "severity_audibility_artifact_support_uncertainty_abstention_reported",
            state="schema_ready_values_unavailable",
            satisfied=output_schema_ok and output_values_available,
            completion_required=True,
            evidence=["score_free_oracle_schema", "score_free_oracle_plan.score_free_output_boundary"],
            reason="The abstaining envelope exists, but severity, audibility, artifact and uncertainty values are unavailable without evidence.",
            next_gate="Populate only after valid metric and human calibration; retain explicit abstention otherwise.",
        ),
        _requirement(
            "public_cli_remains_verdict_free",
            state="satisfied_current_boundary" if public_boundary_ok else "violated",
            satisfied=public_boundary_ok,
            completion_required=True,
            evidence=["research_plan.public_state", "src.lib", "tests.cli"],
            reason="The public report remains feature version 0 experimental measurements with public verdicts disabled.",
            next_gate=None if public_boundary_ok else "Restore the verdict-free public contract.",
        ),
        _requirement(
            "rigorous_negative_is_accepted_success",
            state="satisfied_success_criterion" if negative_success_ok else "incomplete",
            satisfied=negative_success_ok,
            completion_required=True,
            evidence=["research_contract.stop_rules_and_successful_negative_outcomes"],
            reason="The contract accepts rejection or full-reference-only disposition as successful scientific outcomes.",
            next_gate=None if negative_success_ok else "Freeze valid negative dispositions before outcome access.",
        ),
        _requirement(
            "final_research_recommendation_frozen",
            state="absent",
            satisfied=recommendation_ok,
            completion_required=True,
            evidence=["objective_completion_audit_plan.completion_policy.current_recommendation"],
            reason="No final recommendation is justified before the human and full-reference gates resolve.",
            next_gate="Choose exactly one frozen final recommendation only after the evidence path terminates.",
        ),
    ]

    if [item["requirement_id"] for item in requirements] != plan["requirement_ids"]:
        raise ValueError("built requirement order differs from frozen inventory")
    required = [item for item in requirements if item["completion_required"]]
    complete = all(item["satisfied"] for item in required)
    if complete:
        raise ValueError("current bound evidence unexpectedly satisfies the objective")

    satisfied_count = sum(item["satisfied"] for item in requirements)
    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "objective_incomplete_score_blind_completion_audit_complete",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "audio_accessed": False,
        "scores_opened": False,
        "metrics_executed": False,
        "sealed_evidence_opened": False,
        "no_reference_training_performed": False,
        "public_verdict_enabled": False,
        "requirements": requirements,
        "summary": {
            "requirement_count": len(requirements),
            "satisfied_count": satisfied_count,
            "unsatisfied_count": len(requirements) - satisfied_count,
            "objective_complete": complete,
            "final_recommendation": recommendation,
            "blocking_sequence": [
                "truth_bearing_source_manifest_feasible_and_frozen",
                "controlled_human_calibration_collected",
                "perceptual_metric_execution_and_legal_gate_passed",
                "deterministic_human_calibrated_full_reference_oracle_passed",
                "grouped_source_domain_codec_encoder_transfer_passed",
                "no_reference_estimator_trained_and_independently_validated",
                "final_research_recommendation_frozen",
            ],
            "nearest_authority_dependent_decision": "Broaden metadata-only provider qualification or explicitly narrow the primary-domain claim; do not select members or acquire audio yet.",
        },
        "evidence_checks": {
            "odaq_clean_references_acquired": acquisition.get(
                "access_boundary", {}
            ).get("clean_reference_members_opened")
            is True,
            "odaq_transparent_truth_supported": feasibility.get(
                "odaq_narrow_path", {}
            ).get("transparent_truth_supported")
            is True,
            "provider_allocation_frozen": allocation.get("decision", {}).get(
                "provider_allocation_frozen"
            )
            is True,
            "score_free_schema_replay_complete": oracle.get(
                "completed_prerequisite", {}
            ).get("score_free_schema_replay_complete")
            is True,
            "scientific_gate_evaluated": evaluation.get("synthetic_replay", {}).get(
                "scientific_gate_evaluated"
            )
            is True,
        },
    }


def write_report(report: dict[str, Any], output: Path) -> None:
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = load_json(args.plan)
    report = build_report(plan, args.plan)
    write_report(report, args.output)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
