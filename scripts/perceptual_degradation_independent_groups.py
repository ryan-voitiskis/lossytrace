#!/usr/bin/env python3
"""Synthetic-only audit of independent-group counts in boundary-rate inference."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from fractions import Fraction
from functools import lru_cache
from itertools import product
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/independent-group-audit-plan.json"
PLAN_SHA = "38f1880c090eb80c756f5065bba7b75aab2fc3b8311e490d5c893f83132c43ae"
BINDING_PATHS = {
    "evaluation_plan": "benchmarks/perceptual-degradation-v1/full-reference-evaluation-plan.json",
    "evaluation_engine": "scripts/perceptual_degradation_full_reference_evaluation.py",
    "predecessor_resampling_report": "research/toolchains/evidence/perceptual-degradation-paired-resampling-synthetic-20260905-001.json",
}
METHODS = ("legacy_source_wilson", "partition_wilson", "partition_exact_binomial")
EVENTS = ("upper_noncoverage", "lower_noncoverage", "safety_guard_pass", "sensitivity_guard_pass")
ALPHA, SAFETY_POINT, SAFETY_UPPER, SENSITIVITY_LOWER = map(Fraction, (".05", ".05", ".10", ".80"))


def canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rounded(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite report value")
        return round(value, 10)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [rounded(item) for item in value]
    return value


def load_plan():
    if sha(PLAN) != PLAN_SHA:
        raise ValueError("audit plan bytes differ")
    plan = json.loads(PLAN.read_bytes())
    for key, expected in BINDING_PATHS.items():
        binding = plan["bindings"][key]
        if binding["path"] != expected or sha(ROOT / expected) != binding["sha256"]:
            raise ValueError("predecessor binding differs: " + key)
    return plan


def load_engine():
    load_plan()
    spec = importlib.util.spec_from_file_location("independent_groups_legacy", ROOT / BINDING_PATHS["evaluation_engine"])
    if spec is None or spec.loader is None:
        raise ValueError("bound engine unavailable")
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    errors = engine.validate_plan(engine.load_json(engine.PLAN))
    if errors:
        raise ValueError("transitive predecessor validation failed: " + "; ".join(errors))
    return engine


def probability(value):
    if not isinstance(value, Fraction) or not 0 <= value <= 1:
        raise ValueError("exact probability differs")
    return f"{value.numerator}/{value.denominator}"


def validate_count(value, maximum=40):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError("count outside bounded audit")


@lru_cache(maxsize=128, typed=True)
def binomial_masses(count, theta):
    validate_count(count)
    if not isinstance(theta, Fraction) or not 0 <= theta <= 1:
        raise ValueError("binomial probability differs")
    a, b = theta.numerator, theta.denominator
    masses = tuple(Fraction(math.comb(count, k) * a**k * (b-a)**(count-k), b**count) for k in range(count+1))
    if sum(masses) != 1:
        raise ValueError("binomial mass lost")
    return masses


@lru_cache(maxsize=128, typed=True)
def tails(count, theta):
    masses = binomial_masses(count, theta)
    cdf, total = [], Fraction(0)
    for mass in masses:
        total += mass
        cdf.append(total)
    upper_tail = [Fraction(1)] + [1-value for value in cdf[:-1]]
    return tuple(cdf), tuple(upper_tail)


def exact_events(k, count, theta):
    validate_count(count)
    if type(k) is not int or not 0 <= k <= count:
        raise ValueError("event count differs")
    cdf, upper_tail = tails(count, theta)
    safety_cdf, _ = tails(count, SAFETY_UPPER)
    _, sensitivity_tail = tails(count, SENSITIVITY_LOWER)
    return {
        "upper_noncoverage": k < count and cdf[k] < ALPHA,
        "lower_noncoverage": k > 0 and upper_tail[k] < ALPHA,
        "safety_guard_pass": Fraction(k, count) <= SAFETY_POINT and k < count and safety_cdf[k] <= ALPHA,
        "sensitivity_guard_pass": k > 0 and sensitivity_tail[k] <= ALPHA,
    }


def wilson_events(engine, k, count, copies, theta):
    validate_count(count)
    validate_count(copies)
    if type(k) is not int or not 0 <= k <= count:
        raise ValueError("event count differs")
    if not isinstance(theta, Fraction) or not 0 <= theta <= 1:
        raise ValueError("Wilson target differs")
    lower, upper = engine.wilson_bounds(k*copies, count*copies)
    return {
        "upper_noncoverage": upper < float(theta),
        "lower_noncoverage": lower > float(theta),
        "safety_guard_pass": Fraction(k, count) <= SAFETY_POINT and upper <= float(SAFETY_UPPER),
        "sensitivity_guard_pass": lower >= float(SENSITIVITY_LOWER),
    }


def enumerate_case(engine, count, copies, theta):
    validate_count(copies)
    masses = binomial_masses(count, theta)
    totals = {method: dict.fromkeys(EVENTS, Fraction(0)) for method in METHODS}
    for k, mass in enumerate(masses):
        decisions = {
            METHODS[0]: wilson_events(engine, k, count, copies, theta),
            METHODS[1]: wilson_events(engine, k, count, 1, theta),
            METHODS[2]: exact_events(k, count, theta),
        }
        for method, events in decisions.items():
            for event, occurs in events.items():
                totals[method][event] += mass * occurs
    for event in EVENTS[:2]:
        if totals[METHODS[2]][event] > ALPHA:
            raise ValueError("exact-tail inversion violates its declared binomial model")
    zero = wilson_events(engine, 0, count, copies, theta)
    all_events = wilson_events(engine, count, count, copies, theta)
    return {
        "independent_partitions": count, "sources_per_partition": copies, "source_count": count*copies,
        "theta": probability(theta), "outcomes_enumerated": count+1, "probability_mass": probability(sum(masses)),
        "variance_inflation_vs_independent_source_working_model": copies,
        "safety_claim_would_be_false": theta > SAFETY_UPPER,
        "sensitivity_claim_would_be_false": theta < SENSITIVITY_LOWER,
        "guard_probabilities": {method: {event: probability(value) for event, value in events.items()} for method, events in totals.items()},
        "false_combined_safety_component_zero_event_lower_bound": probability(masses[0] if theta > SAFETY_UPPER and zero["safety_guard_pass"] else Fraction(0)),
        "false_combined_sensitivity_component_all_event_lower_bound": probability(masses[-1] if theta < SENSITIVITY_LOWER and all_events["sensitivity_guard_pass"] else Fraction(0)),
        "full_reference_gate_probability_evaluated": False,
    }


def exact_boundary_brackets(count):
    validate_count(count)
    lo, hi = Fraction(0), Fraction(1)
    for _ in range(64):
        middle = (lo+hi)/2
        if middle**count < ALPHA:
            lo = middle
        else:
            hi = middle
    if not lo**count <= ALPHA <= hi**count:
        raise ValueError("root bracket lost")
    return {"all_event_lower": [probability(lo), probability(hi)],
            "zero_event_upper": [probability(1-hi), probability(1-lo)]}


def boundary_rows(engine, experiment):
    rows = []
    for count, copies in product(experiment["independent_partition_counts"], experiment["sources_per_partition"]):
        guards = []
        for event in (False, True):
            records = [{"source_group_id": f"synthetic-source-{group}-{source}",
                        "partition_group_id": f"synthetic-partition-{group}",
                        "oracle": {"materially_degraded": event}}
                       for group in range(count) for source in range(copies)]
            guard = engine._source_group_guard(records, "materially_degraded", mode="all_success" if event else "any_event")
            expected = engine.wilson_bounds(count*copies if event else 0, count*copies)
            if (guard["lower_one_sided_95"], guard["upper_one_sided_95"]) != expected:
                raise ValueError("actual source guard differs from enumerated formula")
            guards.append(guard)
        upper = float(guards[0]["upper_one_sided_95"])
        lower = float(guards[1]["lower_one_sided_95"])
        rows.append({"independent_partitions": count, "sources_per_partition": copies, "source_count": count*copies,
                     "legacy_zero_event_upper": upper, "legacy_all_event_lower": lower,
                     "zero_event_combined_safety_component_pass": upper <= float(SAFETY_UPPER),
                     "all_event_combined_sensitivity_component_pass": lower >= float(SENSITIVITY_LOWER),
                     "exact_partition_binomial_brackets": exact_boundary_brackets(count)})
    return rows


def partition_variant(records, partitions):
    groups = sorted({record["source_group_id"] for record in records})
    if type(partitions) is not int or partitions < 1 or len(groups) % partitions:
        raise ValueError("partition regrouping differs")
    group_index = {group: index for index, group in enumerate(groups)}
    result = copy.deepcopy(records)
    for record in result:
        index = group_index[record["source_group_id"]] // (len(groups)//partitions)
        record["partition_group_id"] = "partition-group-" + hashlib.sha256(f"independence-audit-{index}".encode()).hexdigest()
    stripped = lambda items: [{key: value for key, value in record.items() if key != "partition_group_id"} for record in items]
    if stripped(result) != stripped(records):
        raise ValueError("regrouping changed an observation")
    return result


def rate_projection(engine, summary, safety):
    guard = summary["source_group_boundary_guard"]
    limit = summary["gate_upper_one_sided_95" if safety else "gate_lower_one_sided_95"]
    passes = (summary["point"] <= engine.GATES["transparent_material_rate_point_max"] and limit <= engine.GATES["transparent_material_rate_upper_ci_max"]) if safety else limit >= engine.GATES["material_sensitivity_lower_ci"]
    return {"case_count": summary["case_count"], "source_count": summary["source_group_count"],
            "partition_count": summary["partition_group_count"], "point": float(summary["point"]),
            "bootstrap_lower": float(summary["lower_one_sided_95"]), "bootstrap_upper": float(summary["upper_one_sided_95"]),
            "guard_lower": float(guard["lower_one_sided_95"]), "guard_upper": float(guard["upper_one_sided_95"]),
            "combined_limit": float(limit), "component_numeric_pass": passes,
            "bootstrap_draws": summary["requested_replicates"], "valid_draws": summary["valid_replicates"]}


def fixture_audit(engine, experiment):
    base = engine.synthetic_records()
    variants = []
    for count in experiment["fixture_boundary_check"]["partition_counts"]:
        records = partition_variant(base, count)
        errors = engine.validate_records(records)
        if errors:
            raise ValueError("synthetic variant rejected: " + "; ".join(errors))
        rates = {}
        for safety in (True, False):
            name = "transparent_safety" if safety else "material_sensitivity"
            subset = [record for record in records if record["human_transparent" if safety else "human_material"]]
            summary = engine._rate_summary(subset, "materially_degraded", replicates=10_000,
                                           seed_suffix="independence-audit-"+name,
                                           guard_mode="any_event" if safety else "all_success")
            rates[name] = rate_projection(engine, summary, safety)
        variants.append({"partition_count": count, "legacy_record_validation_accepted": True,
                         "only_partition_ids_changed": True, "rate_components": rates})
    comparable = [{name: {key: value for key, value in rate.items() if key != "partition_count"}
                   for name, rate in variant["rate_components"].items()} for variant in variants]
    return {"variants": variants, "rate_components_invariant_to_partition_regrouping": all(value == comparable[0] for value in comparable),
            "full_evaluator_executed": False}


def weighting_examples(experiment):
    sizes = experiment["weighting_counterexample"]["partition_source_counts"]
    result = []
    for values in experiment["weighting_counterexample"]["partition_event_patterns"]:
        result.append({"partition_source_counts": sizes, "partition_events": values,
                       "equal_partition_mean": probability(Fraction(sum(values), len(values))),
                       "equal_source_mean": probability(Fraction(sum(size*value for size, value in zip(sizes, values, strict=True)), sum(sizes)))})
    return result


def build_report():
    plan, engine = load_plan(), load_engine()
    experiment = plan["experiment"]
    cases = [enumerate_case(engine, count, copies, Fraction(*theta))
             for count, copies, theta in product(experiment["independent_partition_counts"], experiment["sources_per_partition"], experiment["event_probabilities"])]
    result = {
        "schema_version": 1, "report_id": plan["plan_id"], "state": "synthetic_independence_audit_complete",
        "plan_sha256": PLAN_SHA, "implementation_sha256": sha(Path(__file__)), "bindings": plan["bindings"],
        "access_boundary": plan["access_boundary"], "estimand": experiment["estimand"], "model": experiment["model"],
        "probability_encoding": "reduced_numerator_slash_positive_denominator_strings",
        "case_count": len(cases), "grid": cases, "extreme_outcome_bounds": boundary_rows(engine, experiment),
        "legacy_fixture_boundary_check": fixture_audit(engine, experiment), "weighting_counterexamples": weighting_examples(experiment),
        "all_outcomes_enumerated": True, "monte_carlo_used_for_grid": False,
        "all_grid_probability_mass_exactly_one": True, "exact_binomial_validity_conditional_on_declared_iid_partition_model": True,
        "method_selected": False, "population_sampling_frame_established": False,
        "human_interval_coverage_validated": False, "human_responses_observed": False,
        "metric_scores_observed": False, "scientific_gate_evaluated": False,
        "oracle_truth_eligible": False, "no_reference_training_eligible": False, "objective_complete": False,
    }
    return rounded(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.parse_args()
    print(canonical(build_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
