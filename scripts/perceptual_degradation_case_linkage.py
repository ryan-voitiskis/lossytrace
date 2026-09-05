#!/usr/bin/env python3
"""Synthetic presentation-to-case linkage; no observed-data or inference CLI."""

from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import importlib.util
import json
from fractions import Fraction
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/case-linkage-plan.json"
PLAN_SHA = "4da321b14be2d9fef2d995882418d58a2bfe2bc87cde67c95d67fe73c751682e"
BINDINGS = {
    "paired_plan": "benchmarks/perceptual-degradation-v1/paired-rating-protocol-plan.json",
    "paired_engine": "scripts/perceptual_degradation_paired_rating.py",
    "target_semantics_plan": "benchmarks/perceptual-degradation-v1/perceptual-target-semantics-plan.json",
    "target_semantics_report": "research/toolchains/evidence/perceptual-degradation-target-semantics-synthetic-20260905-001.json",
    "independence_report": "research/toolchains/evidence/perceptual-degradation-independent-groups-synthetic-20260905-001.json",
}
SCENARIOS = ("equal-top", "symmetric-error", "choice-correlated", "common-offset", "positive-difference")
VARIANTS = ("complete", "incorrect_pairs_unsubmitted", "one_case_absent", "all_absent")
FINITE_SCOPE = "finite_assigned_panel_summary"
CASE_KEYS = {"case_id", "reference_id", "condition_id", "source_group_id", "leakage_group_id", "analysis_group_id"}
COUNT_KEYS = {"assigned_listeners", "received_responses", "absent_responses", "locked_choices", "missing_choices",
              "correct_choices", "incorrect_choices_retained", "complete_pairs", "missing_pairs"}
NULL_KEYS = {"population_correct_response_probability", "population_paired_mean", "population_interval",
             "material_condition_label", "audible_condition_label", "independent_sampling_unit_count"}
MEAN_KEYS = {"observed_signed_paired_mean", "planned_panel_signed_paired_mean",
             "observed_correct_choice_fraction", "planned_panel_correct_choice_fraction"}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(value: Any, keys: set[str]) -> None:
    if type(value) is not dict or set(value) != keys:
        raise ValueError("unexpected fields")


def load_plan() -> dict[str, Any]:
    if sha(PLAN) != PLAN_SHA:
        raise ValueError("plan bytes differ")
    plan = json.loads(PLAN.read_text())
    fields(plan["bindings"], set(BINDINGS))
    for name, relative in BINDINGS.items():
        if plan["bindings"][name] != {"path": relative, "sha256": sha(ROOT / relative)}:
            raise ValueError("predecessor binding differs")
    return plan


def load_engine():
    load_plan()
    spec = importlib.util.spec_from_file_location("case_linkage_paired", ROOT / BINDINGS["paired_engine"])
    assert spec and spec.loader
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    engine.load_plan()
    return engine


def registry_for(engine, scenario: str) -> dict[str, Any]:
    if type(scenario) is not str or scenario not in SCENARIOS:
        raise ValueError("unknown synthetic scenario")
    cases, assignments = [], []
    for source in range(12):
        # Stable identities are declared independently of participant aliases.
        case_id = f"case-synthetic-{scenario}-{source:02d}"
        cases.append({
            "case_id": case_id,
            "reference_id": f"reference-synthetic-{source:02d}",
            "condition_id": f"condition-synthetic-{scenario}-{source:02d}",
            "source_group_id": f"source-synthetic-{source:02d}",
            "leakage_group_id": f"leakage-synthetic-{source // 2:02d}",
            "analysis_group_id": "group-" + scenario,
        })
        for listener in range(24):
            assignments.append({"case_id": case_id, "assignment": engine.synthetic_assignment(scenario, listener, source)})
    return {"state": "generated_synthetic_case_registry_only", "fixture_only": True,
            "scenario": scenario, "cases": cases, "assignments": assignments}


def validate_registry(engine, registry: Any) -> None:
    fields(registry, {"state", "fixture_only", "scenario", "cases", "assignments"})
    expected = registry_for(engine, registry["scenario"])
    if canonical(registry) != canonical(expected):
        raise ValueError("synthetic registry differs from declared assignments and case linkage")


def fixture_responses(engine, registry: dict[str, Any], variant: str) -> list[dict[str, Any]]:
    validate_registry(engine, registry)
    if type(variant) is not str or variant not in VARIANTS:
        raise ValueError("unknown synthetic response variant")
    if variant != "complete" and registry["scenario"] != "choice-correlated":
        raise ValueError("missingness variants are declared only for choice-correlated")
    output = []
    for entry in registry["assignments"]:
        assignment = entry["assignment"]
        if variant == "all_absent" or (variant == "one_case_absent" and assignment["source_index"] == 11):
            continue
        events = engine.synthetic_events(assignment)
        if variant == "incorrect_pairs_unsubmitted" and events[0]["position"] != assignment["condition_position"]:
            events = events[:1]
        response = engine.reduce_events(engine.presentation_assignment(assignment), events)
        output.append({"assignment_id": assignment["assignment_id"], "response": response})
    return output


def rational(numerator: int, denominator: int) -> str | None:
    if type(numerator) is not int or type(denominator) is not int or denominator < 0:
        raise ValueError("invalid exact summary counts")
    if denominator == 0:
        return None
    value = Fraction(numerator, denominator)
    return f"{value.numerator}/{value.denominator}"


def validate_summary(summary: Any) -> None:
    fields(summary, COUNT_KEYS | NULL_KEYS | MEAN_KEYS)
    if any(summary[key] is not None for key in NULL_KEYS):
        raise ValueError("finite summary cannot contain scientific labels or population evidence")
    if any(type(summary[key]) is not int or not 0 <= summary[key] <= 24 for key in COUNT_KEYS):
        raise ValueError("invalid finite-panel counts")
    if (summary["assigned_listeners"] != 24
        or summary["received_responses"] + summary["absent_responses"] != 24
        or summary["locked_choices"] + summary["missing_choices"] != 24
        or summary["complete_pairs"] + summary["missing_pairs"] != 24
        or summary["correct_choices"] + summary["incorrect_choices_retained"] != summary["locked_choices"]
        or not summary["complete_pairs"] <= summary["locked_choices"] <= summary["received_responses"]):
        raise ValueError("inconsistent finite-panel counts")
    fraction = rational(summary["correct_choices"], summary["locked_choices"])
    planned_fraction = fraction if summary["locked_choices"] == 24 else None
    if (summary["observed_correct_choice_fraction"] != fraction
        or summary["planned_panel_correct_choice_fraction"] != planned_fraction):
        raise ValueError("choice fraction differs from its denominator")
    mean = summary["observed_signed_paired_mean"]
    if summary["complete_pairs"] == 0:
        if mean is not None:
            raise ValueError("missing paired mean must remain null")
    else:
        if type(mean) is not str:
            raise ValueError("exact signed paired mean required")
        try:
            value = Fraction(mean)
        except (ValueError, ZeroDivisionError) as error:
            raise ValueError("invalid exact signed mean") from error
        if (not -4 <= value <= 4 or mean != rational(value.numerator, value.denominator)
            or (value * 10 * summary["complete_pairs"]).denominator != 1):
            raise ValueError("paired mean differs from bounded integer-tick support")
    if summary["planned_panel_signed_paired_mean"] != (mean if summary["complete_pairs"] == 24 else None):
        raise ValueError("missing planned paired mean must remain null")


def route_case_summary(target: Any, cases: list[dict[str, Any]], requested_scope: str) -> str:
    """Narrow consumer preflight, not an inference/evidence authorization API.

    This routes only summaries assembled from the bound synthetic registry.
    Flags cannot certify real identity, listener sampling or scientific truth.
    """
    if type(requested_scope) is not str or requested_scope != FINITE_SCOPE:
        raise ValueError("scientific source labels and population inference are not supported")
    fields(target, {"linkage", "analysis_unit", "summary_scope", "fixture_only", "scientific_truth_eligible", "summary"})
    if target["analysis_unit"] != "reference_condition_case" or target["summary_scope"] != FINITE_SCOPE:
        raise ValueError("aggregate targets cannot be broadcast to cases")
    if target["fixture_only"] is not True or target["scientific_truth_eligible"] is not False:
        raise ValueError("only synthetic finite summaries can be routed")
    fields(target["linkage"], CASE_KEYS)
    matches = [case for case in cases if case["case_id"] == target["linkage"]["case_id"]]
    if len(matches) != 1 or canonical(matches[0]) != canonical(target["linkage"]):
        raise ValueError("case linkage differs")
    validate_summary(target["summary"])
    return matches[0]["case_id"]


def assemble(engine, registry: dict[str, Any], responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validate_registry(engine, registry)
    if type(responses) is not list:
        raise ValueError("response list required")
    assignments = {entry["assignment"]["assignment_id"]: entry for entry in registry["assignments"]}
    resolved = {}
    for envelope in responses:
        fields(envelope, {"assignment_id", "response"})
        key = envelope["assignment_id"]
        if type(key) is not str or key not in assignments:
            raise ValueError("unknown response assignment")
        if key in resolved:
            raise ValueError("duplicate response assignment")
        # The predecessor checks roles, participant-facing binding and grades.
        resolved[key] = engine.resolve_response(assignments[key]["assignment"], envelope["response"])
    output = []
    for case in registry["cases"]:
        planned = [entry for entry in registry["assignments"] if entry["case_id"] == case["case_id"]]
        rows = [resolved[entry["assignment"]["assignment_id"]] for entry in planned if entry["assignment"]["assignment_id"] in resolved]
        choices = [row["forced_choice_correct"] for row in rows if row["forced_choice_correct"] is not None]
        complete = [row for row in rows if row["complete_pair_analysis_eligible"]]
        tick_sum = sum(row["condition_grade_ticks"] - row["hidden_reference_grade_ticks"] for row in complete)
        paired_mean = rational(tick_sum, 10 * len(complete))
        choice_fraction = rational(sum(choices), len(choices))
        summary = {
            "assigned_listeners": len(planned), "received_responses": len(rows),
            "absent_responses": len(planned) - len(rows),
            "locked_choices": len(choices), "missing_choices": len(planned) - len(choices),
            "correct_choices": sum(choices), "incorrect_choices_retained": len(choices) - sum(choices),
            "complete_pairs": len(complete), "missing_pairs": len(planned) - len(complete),
            "observed_signed_paired_mean": paired_mean,
            "planned_panel_signed_paired_mean": paired_mean if len(complete) == len(planned) else None,
            "observed_correct_choice_fraction": choice_fraction,
            "planned_panel_correct_choice_fraction": choice_fraction if len(choices) == len(planned) else None,
            "population_correct_response_probability": None,
            "population_paired_mean": None, "population_interval": None,
            "material_condition_label": None, "audible_condition_label": None,
            "independent_sampling_unit_count": None,
        }
        target = {"linkage": copy.deepcopy(case), "analysis_unit": "reference_condition_case",
                  "summary_scope": FINITE_SCOPE, "fixture_only": True,
                  "scientific_truth_eligible": False, "summary": summary}
        route_case_summary(target, registry["cases"], FINITE_SCOPE)
        output.append(target)
    return output


def public_summary(registry, targets, variant: str) -> dict[str, Any]:
    histogram = collections.Counter(canonical(target["summary"]).decode() for target in targets)
    entries = registry["assignments"]
    condition_aliases = {entry["assignment"]["candidate_ids"][entry["assignment"]["condition_position"]] for entry in entries}
    reference_aliases = {alias for entry in entries for position, alias in entry["assignment"]["candidate_ids"].items() if position != entry["assignment"]["condition_position"]}
    return {
        "synthetic_scenario": registry["scenario"], "variant": variant,
        "planned_presentations": len(entries), "condition_presentation_aliases": len(condition_aliases),
        "reference_presentation_aliases": len(reference_aliases),
        "stable_cases": len(registry["cases"]),
        "stable_conditions": len({case["condition_id"] for case in registry["cases"]}),
        "stable_references": len({case["reference_id"] for case in registry["cases"]}),
        "source_groups": len({case["source_group_id"] for case in registry["cases"]}),
        "leakage_groups": len({case["leakage_group_id"] for case in registry["cases"]}),
        "independent_sampling_unit_count": None,
        "case_summary_histogram": [{"case_count": count, "summary": json.loads(value)} for value, count in sorted(histogram.items())],
    }


def build_report() -> dict[str, Any]:
    plan, engine = load_plan(), load_engine()
    results, all_cases, all_entries = [], [], []
    for scenario in SCENARIOS:
        registry = registry_for(engine, scenario)
        all_cases.extend(registry["cases"])
        all_entries.extend(registry["assignments"])
        variants = VARIANTS if scenario == "choice-correlated" else ("complete",)
        for variant in variants:
            targets = assemble(engine, registry, fixture_responses(engine, registry, variant))
            results.append(public_summary(registry, targets, variant))
    prior = json.loads((ROOT / BINDINGS["target_semantics_report"]).read_text())
    aggregate_targets = prior["baseline_targets"] + [prior["intermediate_target"]]
    rejected = 0
    for target in aggregate_targets:
        try:
            route_case_summary(target, all_cases, FINITE_SCOPE)
        except ValueError:
            rejected += 1
    if rejected != len(aggregate_targets):
        raise ValueError("aggregate promotion unexpectedly accepted")
    return {
        "schema_version": 1, "report_id": plan["plan_id"],
        "state": "synthetic_case_linkage_complete_no_population_or_source_truth",
        "plan_sha256": sha(PLAN), "implementation_sha256": sha(Path(__file__)),
        "bindings": plan["bindings"], "access_boundary": plan["access_boundary"],
        "complete_fixture_inventory": {
            "scenarios": len(SCENARIOS), "listeners": 24,
            "planned_presentations": len(all_entries), "stable_cases": len(all_cases),
            "source_groups": len({case["source_group_id"] for case in all_cases}),
            "leakage_groups": len({case["leakage_group_id"] for case in all_cases}),
            "independent_sampling_unit_count": None,
        },
        "aggregate_adapter_targets_rejected": rejected, "panels": results,
        "scientific_source_labels_supported": False, "population_inference_supported": False,
        "source_identity_verified_from_media": False, "human_responses_observed": False,
        "sampling_frame_established": False, "interval_coverage_validated": False,
        "legacy_evaluator_replaced": False, "scientific_gate_evaluated": False,
        "full_reference_oracle_validated": False, "objective_complete": False,
        "next_requirements": plan["next_requirements"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.parse_args()
    print(canonical(build_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
