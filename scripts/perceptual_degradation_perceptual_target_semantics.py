#!/usr/bin/env python3
"""Typed integration of frozen synthetic listening targets; no observed-data CLI."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/perceptual-target-semantics-plan.json"
PLAN_ID = "perceptual-target-semantics-20260905-001"
SCOPE = "analysis_group_conditional_at_zero_listener_and_source_random_effects"
BINDING_PATHS = {
    "research_contract": "docs/research/perceptual-degradation-contract-20260803.md",
    "research_plan": "benchmarks/perceptual-degradation-v1/research-plan.json",
    "listening_plan": "benchmarks/perceptual-degradation-v1/listening-analysis-plan.json",
    "listening_implementation": "scripts/perceptual_degradation_listening_analysis.py",
    "evaluation_plan": "benchmarks/perceptual-degradation-v1/full-reference-evaluation-plan.json",
    "evaluation_implementation": "scripts/perceptual_degradation_full_reference_evaluation.py",
}
ACCESS = {
    "synthetic_response_analysis_authorized": True,
    "bound_repository_text_read_authorized": True,
    "observed_response_input_authorized": False,
    "audio_access_authorized": False,
    "metric_execution_authorized": False,
    "human_collection_authorized": False,
    "sealed_evidence_access_authorized": False,
    "no_reference_training_authorized": False,
    "public_verdict_enabled": False,
}
STATE_LABELS = {
    "audible": ("audible", True),
    "not_demonstrably_audible": ("chance_equivalent", False),
    "audibility_indeterminate": ("indeterminate", None),
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_plan() -> dict[str, Any]:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise ValueError("target plan identity differs")
    if plan.get("plan_id") != PLAN_ID or plan.get("state") != "synthetic_target_integration_only":
        raise ValueError("target plan identity differs")
    access = plan.get("access_boundary")
    if not isinstance(access, dict) or set(access) != set(ACCESS) or any(access[key] is not value for key, value in ACCESS.items()):
        raise ValueError("target access boundary differs")
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != set(BINDING_PATHS):
        raise ValueError("target binding inventory differs")
    for key, relative in BINDING_PATHS.items():
        binding = bindings[key]
        if not isinstance(binding, dict) or binding.get("path") != relative:
            raise ValueError("target binding path differs")
        # Only known repository text paths are opened, never a plan-supplied path.
        if binding.get("sha256") != _sha(ROOT / relative):
            raise ValueError("target predecessor hash differs")
    contract = plan.get("target_contract", {})
    if not isinstance(contract, dict):
        raise ValueError("target contract differs")
    if contract.get("existing_listening_estimate_scope") != SCOPE:
        raise ValueError("target probability scope differs")
    if "indeterminate_audibility_label" not in contract or contract["indeterminate_audibility_label"] is not None:
        raise ValueError("indeterminate must remain null")
    for key in (
        "legacy_indeterminate_to_false_conversion_allowed",
        "analysis_group_to_per_source_label_broadcast_allowed",
        "legacy_brier_ece_auc_gate_transfer_to_response_target_allowed",
        "replacement_numeric_gates_selected",
        "existing_human_decision_thresholds_changed",
    ):
        if contract.get(key) is not False:
            raise ValueError("target semantics require a separate scientific amendment")
    return plan


def _module(binding: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(binding, ROOT / BINDING_PATHS[binding])
    if spec is None or spec.loader is None:
        raise ValueError("cannot load bound implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _probability(value: Any) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("invalid correct-response probability")
    return float(value)


def project_synthetic_analysis(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep the fitted probability and certification label as separate targets.

    This adapter is deliberately ineligible for per-source evaluation. A future
    live adapter needs its own target, linkage, uncertainty and execution plan.
    """
    plan = load_plan()
    if not isinstance(report, dict):
        raise ValueError("invalid synthetic listening analysis")
    if report.get("fixture_only") is not True or report.get("state") != "synthetic_listening_analysis_plumbing_only":
        raise ValueError("only synthetic listening analysis is accepted")
    for field in ("scientific_gate_evaluated", "human_collection_authorized", "human_responses_observed"):
        if report.get(field) is not False:
            raise ValueError("observed or scientific analysis is forbidden")
    if report.get("analysis_plan_sha256") != plan["bindings"]["listening_plan"]["sha256"]:
        raise ValueError("listening plan binding differs")
    if report.get("implementation_sha256") != plan["bindings"]["listening_implementation"]["sha256"]:
        raise ValueError("listening implementation binding differs")
    gate = report.get("collection_or_oracle_gate")
    if not isinstance(gate, dict) or gate.get("oracle_truth_eligible") is not False:
        raise ValueError("synthetic targets cannot be oracle truth")
    groups = report.get("primary_groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("missing synthetic analysis groups")
    output = []
    seen = set()
    listening = _module("listening_implementation")
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("invalid synthetic analysis group")
        group_id = group.get("analysis_group_id")
        if not isinstance(group_id, str) or group_id not in {"group-transparent", "group-audible-nonmaterial", "group-material-bridge"} or group_id in seen:
            raise ValueError("unknown or duplicate synthetic analysis group")
        seen.add(group_id)
        if group.get("partition") != "development":
            raise ValueError("only development fixtures are accepted")
        model = group.get("audibility")
        estimate = interval = None
        state = "audibility_indeterminate"
        if model is not None:
            if not isinstance(model, dict) or model.get("converged") is not True:
                raise ValueError("invalid or unconverged listening probability")
            estimate = _probability(model.get("estimate"))
            lower, upper = _probability(model.get("lower")), _probability(model.get("upper"))
            if not lower <= estimate <= upper:
                raise ValueError("probability interval is inconsistent")
            interval = [lower, upper]
            state = model.get("state")
            if any(type(model.get(key)) is not int or model[key] < 0 for key in ("listeners", "sources", "responses")):
                raise ValueError("invalid probability support counts")
            if state != listening._audibility_state(model):
                raise ValueError("reported audibility state conflicts with frozen decision rule")
        if not isinstance(state, str) or state not in STATE_LABELS:
            raise ValueError("unknown audibility state")
        typed_state, label = STATE_LABELS[state]
        output.append({
            "synthetic_analysis_group": group_id,
            "analysis_unit": "aggregate_analysis_group",
            "correct_response_probability": estimate,
            "correct_response_probability_interval": interval,
            "probability_scope": SCOPE,
            "population_marginal_correct_response_probability": None,
            "audibility_evidence_state": typed_state,
            "audible_condition_label": label,
            "audible_condition_probability": None,
            "per_source_evaluation_eligible": False,
            "scientific_truth_eligible": False,
        })
    return sorted(output, key=lambda item: item["synthetic_analysis_group"])


def build_synthetic_report() -> dict[str, Any]:
    plan = load_plan()
    listening = _module("listening_implementation")
    evaluation = _module("evaluation_implementation")
    baseline = listening.analyse(listening.synthetic_dataset())
    intermediate = listening.synthetic_dataset()
    index = 0
    for response in intermediate["responses"]:
        if response["analysis_group_id"] == "group-audible-nonmaterial" and response["method"] == "subtle":
            response["forced_choice_correct"] = index % 20 < 13
            index += 1
    intermediate_report = listening.analyse(intermediate)
    intermediate_target = next(
        item for item in project_synthetic_analysis(intermediate_report)
        if item["synthetic_analysis_group"] == "group-audible-nonmaterial"
    )
    if intermediate_target["audible_condition_label"] is not None:
        raise ValueError("intermediate synthetic evidence did not remain indeterminate")
    legacy_rows = evaluation.synthetic_records()
    legacy_rows[0].update(human_audible=False, human_transparent=False, human_material=False)
    all_false_accepted = not evaluation.validate_records(legacy_rows)
    # Analytic/scalar witnesses, not perceptual metric scores or human outcomes.
    witnesses = {
        "correct_response_truth": 0.5,
        "correct_response_prediction": 0.5,
        "response_brier_at_chance": evaluation.brier([False, True], [0.5, 0.5]),
        "legacy_class_brier_using_response_probability": evaluation.brier([False], [0.5]),
        "class_brier_using_correct_class_probability": evaluation.brier([False], [0.0]),
        "legacy_class_brier_ceiling": evaluation.GATES["audibility_brier_max"],
        "legacy_class_ece_using_response_probability": evaluation.expected_calibration_error([False], [0.5]),
        "legacy_boolean_schema_accepts_all_false_labels": all_false_accepted,
        "all_false_labels_establish_indeterminate_truth": False,
        "gate_transferred_to_response_scoring": False,
    }
    return {
        "schema_version": 1,
        "report_id": PLAN_ID,
        "state": "synthetic_target_integration_complete_scientific_gates_unresolved",
        "plan_sha256": _sha(PLAN),
        "implementation_sha256": _sha(Path(__file__)),
        "predecessor_bindings": plan["bindings"],
        "baseline_targets": project_synthetic_analysis(baseline),
        "intermediate_target": intermediate_target,
        "semantic_witnesses": witnesses,
        "access_boundary": ACCESS,
        "scientific_gate_evaluated": False,
        "human_responses_observed": False,
        "full_reference_oracle_validated": False,
        "objective_complete": False,
        "next_scientific_requirements": plan["next_scientific_requirements"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    args = parser.parse_args()
    if not args.synthetic:
        parser.error("only synthetic execution is available")
    print(canonical_bytes(build_synthetic_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
