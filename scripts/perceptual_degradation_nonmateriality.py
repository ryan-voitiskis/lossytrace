#!/usr/bin/env python3
"""Synthetic evidence-state integration; no observed-input or scientific gate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/nonmateriality-evidence-plan.json"
PLAN_ID = "nonmateriality-evidence-20260905-001"
BINDINGS = {
    "analysis_plan": "benchmarks/perceptual-degradation-v1/listening-analysis-plan.json",
    "analysis": "scripts/perceptual_degradation_listening_analysis.py",
    "paired_plan": "benchmarks/perceptual-degradation-v1/paired-rating-protocol-plan.json",
    "paired": "scripts/perceptual_degradation_paired_rating.py",
}
ACCESS = {"synthetic_execution_only": True, **dict.fromkeys((
    "observed_response_input_authorized", "audio_access_authorized", "playback_authorized",
    "human_collection_authorized", "metric_execution_authorized", "sealed_evidence_access_authorized",
    "no_reference_training_authorized", "public_verdict_enabled",
), False)}
COORDINATES = {
    "mean_range_roundoff_tolerance": 1e-9,
    "minimum_support": {"listeners": 24, "sources": 12, "responses": 96},
    "paired_sdg_material_boundary": -1.0,
    "mushra_loss_material_boundary": 10.0,
    "audibility_chance": 0.5,
    "audibility_point_gate": 0.75,
    "chance_equivalence_interval": [0.45, 0.55],
    "use": "legacy_numbers_as_synthetic_diagnostic_coordinates_only_not_selected_paired_scientific_thresholds",
}
CONTRACT = {
    "nonmateriality": "supported_interval_wholly_on_nonmaterial_side_of_boundary",
    "materiality": "supported_interval_wholly_on_material_side_of_boundary",
    "boundary_equality_or_crossing": "indeterminate",
    "missing_insufficient_or_unconverged": "indeterminate_with_reason",
    "bridge": "all_declared_methods_required_no_dropping_missing_methods",
    "bridge_conflict": "explicit_material_and_nonmaterial_support_not_material_and_unknown",
    "detectability": "separate_axis_never_inferred_from_severity",
    "labels": "synthetic_research_summary_only_no_scientific_truth",
    "analysis_unit": "aggregate_analysis_group_not_individual_source",
    "scientific_interval_coverage_validated": False,
    "scientific_thresholds_selected": False,
    "legacy_evidence_reclassified": False,
    "legacy_single_grade_fit_migrated_to_paired_target": False,
}
EXECUTION = {
    "workers": 1, "replay_count": 2, "byte_identical_required": True,
    "legacy_witness": "generate_original_fixture_retain_two_subtle_groups_set_every_sdg_to_minus_one_then_validate_and_run_original_primary_classifier",
    "paired_integration": "replay_five_unchanged_paired_scenarios_plus_declared_half_complete_symmetric_error_fixture_into_bound_numerical_solvers",
    "missingness_witness": "half_complete_uses_only_first_twelve_listeners_complete_pairs_for_severity_all_locked_choices_for_numerical_audibility_preview_not_a_selected_human_missingness_policy",
    "report": "path_free_aggregate_synthetic_output_only",
}
DESIGNS = {"paired": ("paired_sdg",), "mushra": ("mushra_loss",), "bridge": ("paired_sdg", "mushra_loss"),
           "legacy_subtle_diagnostic": ("legacy_sdg_diagnostic",)}
FIT_FIELDS = {"estimate", "lower", "upper", "listeners", "sources", "responses", "converged"}
MODEL_SCOPE = "aggregate_intercept_fixed_variance_numerical_preview_not_validated_population_or_source_truth"


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(value: Any, names: set[str]) -> None:
    if type(value) is not dict or set(value) != names:
        raise ValueError("unexpected fields")


def load_plan() -> dict[str, Any]:
    plan = json.loads(PLAN.read_text())
    if type(plan) is not dict or type(plan.get("schema_version")) is not int or plan["schema_version"] != 1:
        raise ValueError("invalid plan schema")
    if plan.get("plan_id") != PLAN_ID or plan.get("state") != "synthetic_decision_semantics_only":
        raise ValueError("invalid plan identity")
    for key, expected in (("access_boundary", ACCESS), ("diagnostic_coordinates", COORDINATES), ("decision_contract", CONTRACT), ("execution", EXECUTION)):
        if canonical_bytes(plan.get(key)) != canonical_bytes(expected):
            raise ValueError("plan boundary or contract differs")
    fields(plan.get("bindings"), set(BINDINGS))
    for key, relative in BINDINGS.items():
        fields(plan["bindings"][key], {"path", "sha256"})
        if plan["bindings"][key] != {"path": relative, "sha256": sha(ROOT / relative)}:
            raise ValueError("predecessor binding differs")
    return plan


def module(name: str):
    load_plan()
    if name not in ("analysis", "paired"):
        raise ValueError("unknown executable binding")
    spec = importlib.util.spec_from_file_location("nonmateriality_" + name, ROOT / BINDINGS[name])
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def fit_view(fit: dict[str, Any] | None) -> dict[str, Any] | None:
    if fit == {"fit_failure": "nonconvergence"}:
        return dict(fit)
    return None if fit is None else {key: fit[key] for key in sorted(FIT_FIELDS)}


def readiness(fit: Any, family: str) -> str | None:
    if fit is None:
        return "missing_estimate"
    if type(fit) is dict and set(fit) == {"fit_failure"}:
        if fit["fit_failure"] != "nonconvergence":
            raise ValueError("unknown fit failure")
        return "unconverged_estimate"
    fields(fit, FIT_FIELDS)
    for key in ("estimate", "lower", "upper"):
        value = fit[key]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("invalid finite interval")
    if not fit["lower"] <= fit["estimate"] <= fit["upper"]:
        raise ValueError("inconsistent interval")
    if family == "audibility" and not 0 <= fit["lower"] <= fit["upper"] <= 1:
        raise ValueError("probability outside unit interval")
    if family in ("paired_sdg", "legacy_sdg_diagnostic", "mushra_loss"):
        bound = 100 if family == "mushra_loss" else 4
        upper_bound = 0 if family == "legacy_sdg_diagnostic" else bound
        tolerance = COORDINATES["mean_range_roundoff_tolerance"]
        if not -bound - tolerance <= fit["estimate"] <= upper_bound + tolerance:
            raise ValueError("severity estimate outside response support")
        # Only accommodate model-mean roundoff at response endpoints; interval
        # values and materiality comparisons are never rounded or clipped here.
    if type(fit["converged"]) is not bool:
        raise ValueError("invalid convergence flag")
    for key in ("listeners", "sources", "responses"):
        if type(fit[key]) is not int or fit[key] < 0:
            raise ValueError("invalid support count")
    if max(fit["listeners"], fit["sources"]) > fit["responses"]:
        raise ValueError("inconsistent support counts")
    if not fit["converged"]:
        return "unconverged_estimate"
    if any(fit[key] < count for key, count in COORDINATES["minimum_support"].items()):
        return "insufficient_support"
    return None


def evidence(fit: Any, family: str) -> dict[str, str]:
    if family not in ("audibility", "paired_sdg", "legacy_sdg_diagnostic", "mushra_loss"):
        raise ValueError("unknown measurement family")
    reason = readiness(fit, family)
    if reason:
        return {"state": "indeterminate", "reason": reason}
    lower, upper = fit["lower"], fit["upper"]
    if family == "audibility":
        if lower > COORDINATES["audibility_chance"] and fit["estimate"] >= COORDINATES["audibility_point_gate"]:
            return {"state": "audible", "reason": "diagnostic_audibility_rule_satisfied"}
        lo, hi = COORDINATES["chance_equivalence_interval"]
        if lower > lo and upper < hi:
            return {"state": "chance_equivalent", "reason": "interval_inside_diagnostic_equivalence_region"}
        return {"state": "indeterminate", "reason": "detectability_not_resolved"}
    if family in ("paired_sdg", "legacy_sdg_diagnostic"):
        # D = condition - hidden reference. More negative D means more impairment.
        lower, upper = -upper, -lower
        margin = -COORDINATES["paired_sdg_material_boundary"]
    else:
        margin = COORDINATES["mushra_loss_material_boundary"]
    if lower > margin:
        return {"state": "material_supported", "reason": "interval_wholly_material"}
    if upper < margin:
        return {"state": "nonmaterial_supported", "reason": "interval_wholly_nonmaterial"}
    return {"state": "indeterminate", "reason": "material_boundary_not_separated"}


def envelope(design: str, models: dict[str, Any]) -> dict[str, Any]:
    return {"state": "synthetic_model_envelope_only", "fixture_only": True,
            "scientific_truth_eligible": False, "analysis_unit": "aggregate_analysis_group",
            "model_scope": MODEL_SCOPE, "design": design, "models": models}


def evaluate_synthetic(enclosed: dict[str, Any]) -> dict[str, Any]:
    load_plan()
    fields(enclosed, {"state", "fixture_only", "scientific_truth_eligible", "analysis_unit", "model_scope", "design", "models"})
    expected = envelope(enclosed["design"], enclosed["models"])
    if canonical_bytes(enclosed) != canonical_bytes(expected):
        raise ValueError("only aggregate synthetic model envelopes are accepted")
    design = enclosed["design"]
    if type(design) is not str or design not in DESIGNS:
        raise ValueError("unknown required-method design")
    models = enclosed["models"]
    required = DESIGNS[design]
    fields(models, {"audibility", *required})
    detectability = evidence(models["audibility"], "audibility")
    methods = {name: evidence(models[name], name) for name in required}
    states = {item["state"] for item in methods.values()}
    if states == {"material_supported"}:
        severity = "material_supported"
    elif states == {"nonmaterial_supported"}:
        severity = "nonmaterial_supported"
    elif {"material_supported", "nonmaterial_supported"} <= states:
        severity = "discordant"
    else:
        severity = "indeterminate"
    audible = detectability["state"]
    summary = "indeterminate"
    if audible == "audible" and severity == "material_supported":
        summary = "materially_degraded"
    elif audible == "audible" and severity == "nonmaterial_supported":
        summary = "audible_nonmaterial"
    elif audible == "chance_equivalent" and severity == "nonmaterial_supported":
        summary = "transparent"
    return {
        "detectability": detectability, "severity_by_required_method": methods,
        "severity_evidence_state": severity, "synthetic_research_summary": summary,
        "detectability_severity_conflict": audible == "chance_equivalent" and severity == "material_supported",
        "material_condition_label": True if summary == "materially_degraded" else False if summary != "indeterminate" else None,
        "scientific_truth_eligible": False, "per_source_evaluation_eligible": False,
        "interval_coverage_validated": False, "scientific_thresholds_selected": False,
    }


def example_fit(estimate: float, lower: float, upper: float) -> dict[str, Any]:
    return {"estimate": estimate, "lower": lower, "upper": upper,
            "listeners": 24, "sources": 12, "responses": 288, "converged": True}


def decision_grid() -> list[dict[str, Any]]:
    audible = {"audible": example_fit(.85, .78, .92), "chance_equivalent": example_fit(.5, .46, .54),
               "indeterminate": example_fit(.6, .45, .75)}
    paired = {"material": example_fit(-1.5, -1.8, -1.2), "nonmaterial": example_fit(-.4, -.6, -.2),
              "unresolved": example_fit(-1, -1.2, -.8), "missing": None}
    mushra = {"material": example_fit(15, 12, 18), "nonmaterial": example_fit(4, 2, 6),
              "unresolved": example_fit(10, 8, 12), "missing": None}
    output = []
    for a, s, m in itertools.product(audible, paired, mushra):
        result = evaluate_synthetic(envelope("bridge", {"audibility": audible[a], "paired_sdg": paired[s], "mushra_loss": mushra[m]}))
        output.append({"detectability_case": a, "paired_case": s, "mushra_case": m, "result": result})
    return output


def legacy_witness(analysis) -> list[dict[str, Any]]:
    dataset = analysis.synthetic_dataset()
    dataset["responses"] = [row for row in dataset["responses"] if row["analysis_group_id"] in ("group-transparent", "group-audible-nonmaterial")]
    for row in dataset["responses"]:
        row["sdg"] = -1.0
    errors = analysis.validate_dataset(dataset)
    if errors:
        raise ValueError("legacy synthetic fixture validation failed: " + "; ".join(errors))
    output = []
    for group in analysis._analyse_groups(dataset, sensitivity=False):
        result = evaluate_synthetic(envelope("legacy_subtle_diagnostic", {"audibility": fit_view(group["audibility"]), "legacy_sdg_diagnostic": fit_view(group["sdg"])}))
        output.append({"synthetic_group": group["analysis_group_id"], "legacy_summary": group["human_truth"],
                       "legacy_sdg_interval": [group["sdg"]["lower"], group["sdg"]["upper"]], "successor": result})
    return output


def paired_integration(analysis, paired) -> list[dict[str, Any]]:
    paired.load_plan()
    output = []
    for scenario in (*paired.SCENARIOS, "half-complete"):
        rows = []
        for listener in range(24):
            for source in range(12):
                assignment = paired.synthetic_assignment("symmetric-error" if scenario == "half-complete" else scenario, listener, source)
                events = paired.synthetic_events(assignment)
                if scenario == "half-complete" and listener >= 12:
                    events = events[:2]
                rows.append(paired.resolve_response(assignment, paired.reduce_events(paired.presentation_assignment(assignment), events)))
        complete = [row for row in rows if row["complete_pair_analysis_eligible"]]
        sdg = analysis._fit_gaussian(complete, lambda row: row["paired_sdg"], "sdg") if complete else None
        try:
            audibility = analysis._fit_logistic(rows)
        except ValueError as error:
            if str(error) != "hierarchical logistic model did not converge":
                raise
            # Retain the failed numerical fit; never substitute a point forecast.
            audibility = {"fit_failure": "nonconvergence"}
        result = evaluate_synthetic(envelope("paired", {"audibility": fit_view(audibility), "paired_sdg": fit_view(sdg)}))
        output.append({"synthetic_scenario": scenario, "assigned_trials": len(rows), "complete_pairs": len(complete),
                       "incomplete_pairs": len(rows) - len(complete),
                       "paired_fit": fit_view(sdg), "correct_response_fit": fit_view(audibility), "result": result})
    return output


def rounded(value: Any) -> Any:
    if type(value) is float:
        return round(value, 10)
    if type(value) is list:
        return [rounded(item) for item in value]
    if type(value) is dict:
        return {key: rounded(item) for key, item in value.items()}
    return value


def build_synthetic_report() -> dict[str, Any]:
    plan = load_plan()
    analysis, paired = module("analysis"), module("paired")
    errors = analysis.validate_plan(json.loads((ROOT / BINDINGS["analysis_plan"]).read_text()))
    if errors:
        raise ValueError("legacy analysis plan validation failed")
    grid = decision_grid()
    return rounded({
        "schema_version": 1, "report_id": PLAN_ID, "state": "synthetic_nonmateriality_semantics_replayed_not_scientific_validation",
        "plan_sha256": sha(PLAN), "implementation_sha256": sha(Path(__file__)), "bindings": plan["bindings"],
        "access_boundary": ACCESS, "diagnostic_coordinates": COORDINATES, "model_scope": MODEL_SCOPE,
        "legacy_generated_counterfactuals": legacy_witness(analysis), "paired_numerical_integration": paired_integration(analysis, paired),
        "bridge_grid": {"cases": len(grid), "summary_counts": {name: sum(row["result"]["synthetic_research_summary"] == name for row in grid)
                         for name in ("transparent", "audible_nonmaterial", "materially_degraded", "indeterminate")},
                        "explicit_method_conflicts": sum(row["result"]["severity_evidence_state"] == "discordant" for row in grid)},
        "legacy_evidence_reclassified": False, "scientific_thresholds_selected": False,
        "interval_coverage_validated": False, "human_responses_observed": False, "oracle_truth_eligible": False,
        "per_source_evaluation_eligible": False, "objective_complete": False,
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.parse_args()
    print(canonical_bytes(build_synthetic_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
