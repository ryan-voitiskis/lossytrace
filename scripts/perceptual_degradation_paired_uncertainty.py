#!/usr/bin/env python3
"""Bounded synthetic paired-interval audit; never accepts observed responses."""

from __future__ import annotations

import argparse
import functools
import hashlib
import importlib.util
import json
import math
import random
from collections import Counter
from pathlib import Path
from statistics import NormalDist, mean, stdev
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/paired-uncertainty-audit-plan.json"
PLAN_SHA = "8f293719548862263aa7956953c543b665dcd3aec1c3bec33ece163b19777f92"
BINDINGS = {
    "analysis": "scripts/perceptual_degradation_listening_analysis.py",
    "analysis_plan": "benchmarks/perceptual-degradation-v1/listening-analysis-plan.json",
    "paired": "scripts/perceptual_degradation_paired_rating.py",
    "paired_plan": "benchmarks/perceptual-degradation-v1/paired-rating-protocol-plan.json",
    "decisions": "scripts/perceptual_degradation_nonmateriality.py",
    "decision_plan": "benchmarks/perceptual-degradation-v1/nonmateriality-evidence-plan.json",
}
NUMERICAL_FAILURES = {"hierarchical normal equations did not converge", "hierarchical normal equations are not positive definite"}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_plan() -> dict[str, Any]:
    data = PLAN.read_bytes()
    if hashlib.sha256(data).hexdigest() != PLAN_SHA:
        raise ValueError("uncertainty plan bytes differ")
    plan = json.loads(data)
    if set(plan["bindings"]) != set(BINDINGS):
        raise ValueError("binding names differ")
    for key, relative in BINDINGS.items():
        if plan["bindings"][key] != {"path": relative, "sha256": sha(ROOT / relative)}:
            raise ValueError("uncertainty predecessor binding differs")
    return plan


def load_module(name: str):
    load_plan()
    if name not in ("analysis", "paired", "decisions"):
        raise ValueError("unknown executable binding")
    spec = importlib.util.spec_from_file_location("paired_uncertainty_" + name, ROOT / BINDINGS[name])
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def distribution(items: list[list[int]]) -> dict[int, float]:
    if type(items) is not list or not items:
        raise ValueError("empty discrete distribution")
    values = {}
    for item in items:
        if type(item) is not list or len(item) != 2 or any(type(x) is not int for x in item) or item[1] <= 0 or item[0] in values:
            raise ValueError("invalid discrete distribution")
        values[item[0]] = item[1]
    total = sum(values.values())
    return {value: weight / total for value, weight in sorted(values.items())}


def convolve(left: dict[int, float], right: dict[int, float]) -> dict[int, float]:
    result: dict[int, float] = {}
    for a, pa in sorted(left.items()):
        for b, pb in sorted(right.items()):
            result[a+b] = result.get(a+b, 0.0) + pa*pb
    return dict(sorted(result.items()))


def repeated_sum(values: dict[int, float], count: int, scale: int = 1) -> dict[int, float]:
    if type(count) is not int or count < 0 or type(scale) is not int or scale < 0:
        raise ValueError("invalid repeated-sum design")
    scaled: dict[int, float] = {}
    for value, probability in values.items():
        scaled[value*scale] = scaled.get(value*scale, 0.0) + probability
    result = {0: 1.0}
    for _ in range(count):
        result = convolve(result, scaled)
    return result


def variance(values: dict[int, float]) -> float:
    center = sum(value*p for value, p in values.items())
    return sum((value-center)**2*p for value, p in values.items())


def generating_distributions(experiment: dict[str, Any]) -> list[dict[int, float]]:
    return [distribution(experiment[name + "_ticks_and_integer_weights"]) for name in ("listener", "source", "residual")]


def balanced_variance(experiment: dict[str, Any], scales: list[int]) -> float:
    listeners, sources = experiment["listeners"], experiment["sources"]
    denominators = (listeners, sources, listeners*sources)
    return sum(variance(values)*scale**2/(100*denominator) for values, scale, denominator in zip(generating_distributions(experiment), scales, denominators, strict=True))


def exact_complete_case(experiment: dict[str, Any], scenario: dict[str, Any], z: float) -> dict[str, Any] | None:
    if scenario["missingness"] != "none":
        return None
    listeners, sources = experiment["listeners"], experiment["sources"]
    dl, ds, de = generating_distributions(experiment)
    sl, ss, se = scenario["scales"]
    # Common units: sum of all listener/source differences in grade ticks.
    noise = convolve(convolve(repeated_sum(dl, listeners, sources*sl), repeated_sum(ds, sources, listeners*ss)),
                     repeated_sum(de, listeners*sources, se))
    denominator = 10*listeners*sources
    assumed_variance = balanced_variance(experiment, [1, 1, 1])
    true_variance = balanced_variance(experiment, scenario["scales"])
    half_width = z*math.sqrt(assumed_variance)
    mass = sum(noise.values())
    if abs(mass - 1) > 1e-10:
        raise ValueError("enumerated probability mass differs")
    covered = sum(p for value, p in noise.items() if abs(value/denominator) <= half_width)
    return {
        "method": "finite_discrete_convolution_float64_no_normal_approximation",
        "probability_mass": mass,
        "expected_paired_difference": experiment["population_mean_difference_ticks"]/10,
        "true_standard_error": math.sqrt(true_variance), "model_standard_error": math.sqrt(assumed_variance),
        "model_interval_half_width": half_width,
        "enumerated_central_coverage": covered,
        "normal_approximation_under_true_variance": 2*NormalDist().cdf(half_width/math.sqrt(true_variance)) - 1,
        "state": "declared_synthetic_population_only_not_human_interval_validation",
    }


def draw(rng: random.Random, items: list[list[int]]) -> int:
    target = rng.randrange(sum(weight for _, weight in items))
    for value, weight in items:
        if target < weight:
            return value
        target -= weight
    raise AssertionError("unreachable discrete draw")


def generated_panel(experiment: dict[str, Any], scenario: dict[str, Any], replicate: int) -> list[tuple[int, int, int, bool]]:
    if canonical_bytes(scenario) not in [canonical_bytes(item) for item in experiment["scenarios"]] or type(replicate) is not int or not 0 <= replicate < experiment["replicates_per_scenario"]:
        raise ValueError("undeclared scenario or replicate")
    seed = int(hashlib.sha256(f'{experiment["seed"]}/{scenario["id"]}/{replicate}'.encode()).hexdigest(), 16)
    rng = random.Random(seed)
    sl, ss, se = scenario["scales"]
    listener_effects = [sl*draw(rng, experiment["listener_ticks_and_integer_weights"]) for _ in range(experiment["listeners"])]
    source_effects = [ss*draw(rng, experiment["source_ticks_and_integer_weights"]) for _ in range(experiment["sources"])]
    center = experiment["population_mean_difference_ticks"]
    result = []
    for listener, le in enumerate(listener_effects):
        for source, so in enumerate(source_effects):
            difference = center + le + so + se*draw(rng, experiment["residual_ticks_and_integer_weights"])
            # Always consume the independent missingness draw, including cases
            # using a different mechanism, so each panel's RNG order is explicit.
            independent_missing = rng.randrange(4) == 0
            missing = {"none": False, "independent_one_in_four": independent_missing,
                       "difference_ticks_less_than_or_equal_to_population_mean": difference <= center,
                       "negative_source_effect": so < 0}[scenario["missingness"]]
            if not -40 <= difference <= 40:
                raise ValueError("declared paired grades exceed response support")
            result.append((listener, source, difference, not missing))
    return result


def response_factory(paired):
    paired.load_plan()

    @functools.lru_cache(maxsize=16384, typed=True)
    def response(listener: int, source: int, difference: int, complete: bool) -> dict[str, Any]:
        if type(difference) is not int or not -40 <= difference <= 40 or type(complete) is not bool:
            raise ValueError("invalid generated paired response")
        assignment = paired.synthetic_assignment("common-offset", listener, source)
        condition = assignment["condition_position"]
        hidden = "B" if condition == "A" else "A"
        grades = {condition: 50+min(difference, 0), hidden: 50-max(difference, 0)}
        events = [{"sequence": 0, "kind": "lock_choice", "position": "A"},
                  {"sequence": 1, "kind": "grade", "position": "A", "grade_ticks": grades["A"]},
                  {"sequence": 2, "kind": "grade", "position": "B", "grade_ticks": grades["B"]},
                  {"sequence": 3, "kind": "submit"}]
        if not complete:
            events = events[:2]
        resolved = paired.resolve_response(assignment, paired.reduce_events(paired.presentation_assignment(assignment), events))
        if resolved["paired_sdg"] != (difference/10 if complete else None):
            raise ValueError("paired processor disagrees with declared difference or missingness")
        # Only the analysis fields survive the bounded cache; no identity-bearing
        # stimulus or trial rows are serialized into the public aggregate report.
        return {key: resolved[key] for key in ("participant_id", "source_group_id", "paired_sdg", "complete_pair_analysis_eligible")}

    return response


def rate(successes: int, total: int) -> dict[str, Any]:
    if type(successes) is not int or type(total) is not int or not 0 <= successes <= total:
        raise ValueError("invalid rate counts")
    if total == 0:
        return {"numerator": 0, "denominator": 0, "estimate": None, "monte_carlo_standard_error": None, "wilson_95_interval": None}
    p = successes/total
    z = NormalDist().inv_cdf(.975)
    divisor = 1 + z*z/total
    center = (p + z*z/(2*total))/divisor
    radius = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/divisor
    return {"numerator": successes, "denominator": total, "estimate": p,
            "monte_carlo_standard_error": math.sqrt(p*(1-p)/total),
            "wilson_95_interval": [max(0, center-radius), min(1, center+radius)]}


def simulate_case(experiment: dict[str, Any], scenario: dict[str, Any], replicates: int, analysis, decisions, response) -> dict[str, Any]:
    if type(replicates) is not int or not 1 <= replicates <= experiment["replicates_per_scenario"]:
        raise ValueError("replicates outside declared synthetic bound")
    truth = experiment["population_mean_difference_ticks"]/10
    estimates, errors, model_se, response_counts, listener_counts, source_counts = [], [], [], [], [], []
    covered = supported = supported_covered = 0
    failures = Counter({"no_complete_data": 0, "numerical_failure": 0})
    evidence_counts = Counter({"material_supported": 0, "nonmaterial_supported": 0, "indeterminate": 0})
    max_mean_error = max_se_error = 0.0
    for replicate in range(replicates):
        generated = generated_panel(experiment, scenario, replicate)
        rows = [response(*item) for item in generated]
        complete = [row for row in rows if row["complete_pair_analysis_eligible"]]
        response_counts.append(len(complete))
        listener_counts.append(len({row["participant_id"] for row in complete}))
        source_counts.append(len({row["source_group_id"] for row in complete}))
        if not complete:
            failures["no_complete_data"] += 1
            evidence_counts["indeterminate"] += 1
            continue
        try:
            fitted = analysis._fit_gaussian(complete, lambda row: row["paired_sdg"], "sdg")
        except ValueError as error:
            if str(error) not in NUMERICAL_FAILURES:
                raise
            failures["numerical_failure"] += 1
            evidence_counts["indeterminate"] += 1
            continue
        estimates.append(fitted["estimate"])
        errors.append(fitted["estimate"]-truth)
        model_se.append(fitted["standard_error"])
        coverage = fitted["lower"] <= truth <= fitted["upper"]
        covered += coverage
        enough = analysis._enough(fitted)
        supported += enough
        supported_covered += enough and coverage
        evidence_counts[decisions.evidence(decisions.fit_view(fitted), "paired_sdg")["state"]] += 1
        if scenario["missingness"] == "none":
            max_mean_error = max(max_mean_error, abs(fitted["estimate"]-mean(row["paired_sdg"] for row in complete)))
            max_se_error = max(max_se_error, abs(fitted["standard_error"]-math.sqrt(balanced_variance(experiment, [1, 1, 1]))))
    count = len(estimates)
    if count + sum(failures.values()) != replicates or sum(evidence_counts.values()) != replicates:
        raise ValueError("replicate accounting differs")
    return {
        "replicates": replicates, "returned_intervals": count, "failures": dict(failures),
        "interval_return_rate": rate(count, replicates), "valid_and_covers_rate": rate(covered, replicates),
        "coverage_given_returned": rate(covered, count), "support_rate": rate(supported, replicates),
        "coverage_given_supported": rate(supported_covered, supported),
        "mean_estimate_given_returned": mean(estimates) if count else None,
        "bias_given_returned": mean(errors) if count else None,
        "bias_monte_carlo_standard_error": stdev(errors)/math.sqrt(count) if count > 1 else None,
        "empirical_standard_deviation_given_returned": stdev(estimates) if count > 1 else None,
        "rmse_given_returned": math.sqrt(mean(error*error for error in errors)) if count else None,
        "mean_model_standard_error_given_returned": mean(model_se) if count else None,
        "complete_response_count_range": [min(response_counts), max(response_counts)],
        "complete_listener_count_range": [min(listener_counts), max(listener_counts)],
        "complete_source_count_range": [min(source_counts), max(source_counts)],
        "diagnostic_severity_evidence_counts": dict(evidence_counts),
        "balanced_solver_comparison": {"maximum_mean_error": max_mean_error, "maximum_standard_error_error": max_se_error}
        if scenario["missingness"] == "none" else None,
    }


def rounded(value: Any) -> Any:
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non-finite public result")
        result = round(value, 10)
        return 0.0 if result == 0 else result
    if type(value) is list:
        return [rounded(item) for item in value]
    if type(value) is dict:
        return {key: rounded(item) for key, item in value.items()}
    return value


def build_report(replicates: int | None = None) -> dict[str, Any]:
    plan = load_plan()
    experiment = plan["experiment"]
    count = experiment["replicates_per_scenario"] if replicates is None else replicates
    if type(count) is not int or not 1 <= count <= experiment["replicates_per_scenario"]:
        raise ValueError("replicates outside declared synthetic bound")
    analysis, paired, decisions = (load_module(name) for name in ("analysis", "paired", "decisions"))
    errors = analysis.validate_plan(json.loads((ROOT / BINDINGS["analysis_plan"]).read_text()))
    if errors:
        raise ValueError("bound analysis plan validation failed")
    decisions.load_plan()
    response = response_factory(paired)
    scenarios = []
    for scenario in experiment["scenarios"]:
        enumeration = exact_complete_case(experiment, scenario, analysis.Z_THRESHOLD)
        simulation = simulate_case(experiment, scenario, count, analysis, decisions, response)
        comparison = simulation["balanced_solver_comparison"]
        if comparison and max(comparison.values()) > plan["analysis"]["fit_oracle_comparison_absolute_tolerance"]:
            raise ValueError("balanced numerical solver disagrees with analytic oracle")
        scenarios.append({"scenario": scenario, "finite_discrete_enumeration": enumeration, "simulation": simulation})
    response.cache_clear()
    return rounded({
        "schema_version": 1, "report_id": plan["plan_id"],
        "state": "synthetic_uncertainty_sensitivity_diagnostic_complete" if count == experiment["replicates_per_scenario"] else "reduced_synthetic_smoke_only",
        "plan_sha256": PLAN_SHA, "implementation_sha256": sha(Path(__file__)), "bindings": plan["bindings"],
        "access_boundary": plan["access_boundary"], "replicates_per_scenario": count,
        "estimand": experiment["estimand"], "synthetic_population_mean_paired_difference": experiment["population_mean_difference_ticks"]/10,
        "original_interval_multiplier": analysis.Z_THRESHOLD,
        "nominal_pointwise_central_normal_coverage": 2*NormalDist().cdf(analysis.Z_THRESHOLD)-1,
        "scenarios": scenarios, "all_failed_fits_and_missing_replicates_accounted_for": True,
        "confidence_interval_coverage_on_humans_validated": False, "human_materiality_margin_selected": False,
        "audibility_coverage_evaluated": False, "familywise_coverage_evaluated": False,
        "human_responses_observed": False, "oracle_truth_eligible": False,
        "no_reference_training_eligible": False, "objective_complete": False,
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.parse_args()
    print(canonical_bytes(build_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
