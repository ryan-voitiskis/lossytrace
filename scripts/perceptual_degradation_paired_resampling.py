#!/usr/bin/env python3
"""Synthetic crossed-resampling comparison; no observed-data input surface."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import random
from collections import Counter
from fractions import Fraction
from pathlib import Path
from statistics import mean, stdev
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/paired-resampling-audit-plan.json"
PLAN_SHA = "0850f7563592df6c97cc726955dff778915d25eea7f79c2c1879762e59728d4f"
BINDINGS = {
    "engine": "scripts/perceptual_degradation_paired_uncertainty.py",
    "predecessor_report": "research/toolchains/evidence/perceptual-degradation-paired-uncertainty-synthetic-20260905-002.json",
}
METHODS = ("legacy_fixed_variance", "crossed_complete_case_basic", "crossed_bounded_missing_basic")
STATES = ("material_supported", "nonmaterial_supported", "indeterminate")


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_plan() -> dict[str, Any]:
    raw = PLAN.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA:
        raise ValueError("resampling plan bytes differ")
    plan = json.loads(raw)
    if set(plan["bindings"]) != set(BINDINGS):
        raise ValueError("resampling binding names differ")
    for key, path in BINDINGS.items():
        if plan["bindings"][key] != {"path": path, "sha256": sha(ROOT / path)}:
            raise ValueError("resampling predecessor differs")
    return plan


def load_engine():
    load_plan()
    spec = importlib.util.spec_from_file_location("resampling_predecessor", ROOT / BINDINGS["engine"])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_plan()
    return module


def rng_for(experiment: dict[str, Any], scenario: dict[str, Any], replicate: int, purpose: str) -> random.Random:
    if canonical(scenario) not in [canonical(item) for item in experiment["scenarios"]]:
        raise ValueError("undeclared resampling scenario")
    if type(replicate) is not int or not 0 <= replicate < experiment["replicates"] or purpose not in ("panel", "bootstrap"):
        raise ValueError("undeclared replicate or RNG purpose")
    token = f'{experiment["seed"]}/{scenario["id"]}/{replicate}/{purpose}'
    return random.Random(int(hashlib.sha256(token.encode()).hexdigest(), 16))


def generated_panel(experiment: dict[str, Any], scenario: dict[str, Any], replicate: int, engine):
    rng = rng_for(experiment, scenario, replicate, "panel")
    sl, ss, se = scenario["scales"]
    listeners = [sl*engine.draw(rng, experiment["listener_ticks_and_weights"]) for _ in range(experiment["listeners"])]
    sources = [ss*engine.draw(rng, experiment["source_ticks_and_weights"][scenario["source_distribution"]]) for _ in range(experiment["sources"])]
    result = []
    for listener, le in enumerate(listeners):
        for source, so in enumerate(sources):
            scale = 2 if scenario["residual_variation"] == "double_for_positive_source" and so > 0 else 1
            difference = scenario["mean_ticks"] + le + so + se*scale*engine.draw(rng, experiment["residual_ticks_and_weights"])
            missing_draw = rng.randrange(20)
            missing = {"none": False, "independent_quarter": missing_draw < 5, "independent_tenth": missing_draw < 2,
                       "at_or_below_mean": difference <= scenario["mean_ticks"], "negative_source": so < 0}[scenario["missingness"]]
            if not -40 <= difference <= 40:
                raise ValueError("generated grades outside bounded support")
            result.append((listener, source, difference, not missing))
    return result, scenario["source_distribution"] == "rare" and not any(value > 0 for value in sources)


def validate_matrix(matrix: Any) -> tuple[int, int]:
    if type(matrix) is not list or not 1 <= len(matrix) <= 24 or type(matrix[0]) is not list or not 1 <= len(matrix[0]) <= 12:
        raise ValueError("invalid bounded matrix shape")
    columns = len(matrix[0])
    for row in matrix:
        if type(row) is not list or len(row) != columns or any(value is not None and (type(value) is not int or not -40 <= value <= 40) for value in row):
            raise ValueError("invalid bounded matrix entry")
    return len(matrix), columns


def linked_matrix(generated, experiment, response):
    matrix = [[None]*experiment["sources"] for _ in range(experiment["listeners"])]
    seen, complete = set(), []
    for listener, source, difference, accepted in generated:
        if (listener, source) in seen:
            raise ValueError("duplicate assigned cell")
        seen.add((listener, source))
        row = response(listener, source, difference, accepted)
        if row["complete_pair_analysis_eligible"]:
            if row["paired_sdg"] != difference/10:
                raise ValueError("paired linkage disagrees")
            matrix[listener][source] = difference
            complete.append(row)
        elif row["paired_sdg"] is not None:
            raise ValueError("missing pair has an outcome")
    if seen != {(i, j) for i in range(experiment["listeners"]) for j in range(experiment["sources"])}:
        raise ValueError("assigned panel is incomplete")
    validate_matrix(matrix)
    return matrix, complete


def summary(matrix):
    rows, columns = validate_matrix(matrix)
    values = [value for row in matrix for value in row if value is not None]
    count, planned, total = len(values), rows*columns, sum(values)
    lower = Fraction(total-40*(planned-count), 10*planned)
    upper = Fraction(total+40*(planned-count), 10*planned)
    return {"planned": planned, "observed": count, "total_ticks": total, "finite_bounds": (lower, upper),
            "counts": {"responses": count, "listeners": sum(any(x is not None for x in row) for row in matrix),
                       "sources": sum(any(matrix[i][j] is not None for i in range(rows)) for j in range(columns))}}


def multinomial_counts(rng: random.Random, size: int) -> list[int]:
    if type(size) is not int or not 1 <= size <= 24:
        raise ValueError("invalid resampled dimension")
    result = [0]*size
    for _ in range(size):
        result[rng.randrange(size)] += 1
    return result


def weighted_totals(ticks, masks, row_counts, column_counts):
    total = observed = 0
    for i, weight in enumerate(row_counts):
        if weight:
            total += weight*math.sumprod(ticks[i], column_counts)
            observed += weight*math.sumprod(masks[i], column_counts)
    return total, observed


def bootstrap_sums(matrix, rng: random.Random, draws: int):
    rows, columns = validate_matrix(matrix)
    if type(draws) is not int or not 1 <= draws <= 2048:
        raise ValueError("bootstrap count outside declared bound")
    if not hasattr(math, "sumprod"):
        raise ValueError("Python 3.12 or newer is required")
    ticks = [[0 if value is None else value for value in row] for row in matrix]
    masks = [[int(value is not None) for value in row] for row in matrix]
    return [weighted_totals(ticks, masks, multinomial_counts(rng, rows), multinomial_counts(rng, columns)) for _ in range(draws)]


def ratio_quantile(values: list[tuple[int, int]], tail: int) -> Fraction:
    if type(values) is not list or not values or type(tail) is not int or not 0 <= tail <= 80:
        raise ValueError("invalid quantile design")
    for pair in values:
        if type(pair) is not tuple or len(pair) != 2 or any(type(x) is not int for x in pair):
            raise ValueError("invalid quantile ratio")
        numerator, denominator = pair
        if not 1 <= denominator <= 2880 or abs(numerator) > 4*denominator:
            raise ValueError("quantile ratio outside bounded design")
    # Unequal bounded ratios differ by at least 1/2880**2, far above
    # binary64 roundoff on [-4, 4]. Sorting is safe; interpolation is exact.
    ordered = sorted(values, key=lambda item: item[0]/item[1])
    index, remainder = divmod((len(ordered)-1)*tail, 80)
    low = Fraction(*ordered[index])
    return low if not remainder else ((80-remainder)*low + remainder*Fraction(*ordered[index+1]))/80


def result(interval=None, point=None, se=None, failure=None, empty=0):
    if interval is not None:
        lower, upper = interval
        if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
            raise ValueError("invalid returned interval")
    return {"interval": interval, "point": point, "se": se, "failure": failure, "empty_draws": empty}


def crossed_intervals(matrix, samples):
    info = summary(matrix)
    planned, observed, total = info["planned"], info["observed"], info["total_ticks"]
    if not samples or any(type(t) is not int or type(c) is not int or not 0 <= c <= planned or abs(t) > 40*c for t, c in samples):
        raise ValueError("invalid bootstrap totals")
    empty = sum(count == 0 for _, count in samples)
    if observed == 0 or empty:
        complete_case = result(failure="no_complete_data" if observed == 0 else "empty_bootstrap_draw", empty=empty)
    else:
        ratios = [(total_ticks, 10*count) for total_ticks, count in samples]
        estimate = Fraction(total, 10*observed)
        interval = (max(Fraction(-4), 2*estimate-ratio_quantile(ratios, 79)),
                    min(Fraction(4), 2*estimate-ratio_quantile(ratios, 1)))
        complete_case = result(interval, estimate, stdev(t/(10*c) for t, c in samples) if len(samples) > 1 else None)
    lower_values = [(t-40*(planned-c), 10*planned) for t, c in samples]
    upper_values = [(t+40*(planned-c), 10*planned) for t, c in samples]
    lo, hi = info["finite_bounds"]
    interval = (max(Fraction(-4), 2*lo-ratio_quantile(lower_values, 79)),
                min(Fraction(4), 2*hi-ratio_quantile(upper_values, 1)))
    # Bounds are set-valued information, never a midpoint or an imputed mean.
    bounded = result(interval, empty=empty)
    return {METHODS[1]: complete_case, METHODS[2]: bounded}


def legacy_interval(complete, analysis, engine):
    if not complete:
        return result(failure="no_complete_data")
    try:
        fit = analysis._fit_gaussian(complete, lambda row: row["paired_sdg"], "sdg")
    except ValueError as error:
        if str(error) not in engine.NUMERICAL_FAILURES:
            raise
        return result(failure="numerical_failure")
    return result((fit["lower"], fit["upper"]), fit["estimate"], fit["standard_error"])


def enough(counts, coordinates):
    return all(counts[key] >= value for key, value in coordinates["minimum_support"].items())


def state(fitted, counts, coordinates):
    interval = fitted["interval"]
    if interval is None or not enough(counts, coordinates):
        return "indeterminate"
    lower, upper = interval
    boundary = coordinates["paired_sdg_material_boundary"]
    return "material_supported" if upper < boundary else "nonmaterial_supported" if lower > boundary else "indeterminate"


def accumulator():
    return {"returned": 0, "covered": 0, "supported": 0, "supported_covered": 0, "widths": [], "errors": [], "ses": [],
            "failures": Counter(), "decisions": Counter(dict.fromkeys(STATES, 0)), "correct": 0, "wrong": 0,
            "empty_draws": 0, "rare_absent": 0, "rare_absent_returned": 0, "rare_absent_covered": 0}


def observe(acc, fitted, counts, truth, coordinates, rare_absent):
    label = state(fitted, counts, coordinates)
    acc["decisions"][label] += 1
    acc["empty_draws"] += fitted["empty_draws"]
    acc["rare_absent"] += rare_absent
    if label != "indeterminate":
        correct = (label == "material_supported" and truth < coordinates["paired_sdg_material_boundary"]) or (label == "nonmaterial_supported" and truth > coordinates["paired_sdg_material_boundary"])
        acc["correct"] += correct
        acc["wrong"] += not correct
    if fitted["interval"] is None:
        acc["failures"][fitted["failure"]] += 1
        return
    lower, upper = fitted["interval"]
    covered = lower <= truth <= upper
    supported = enough(counts, coordinates)
    acc["returned"] += 1
    acc["covered"] += covered
    acc["supported"] += supported
    acc["supported_covered"] += supported and covered
    acc["rare_absent_returned"] += rare_absent
    acc["rare_absent_covered"] += rare_absent and covered
    acc["widths"].append(float(upper-lower))
    if fitted["point"] is not None:
        acc["errors"].append(float(fitted["point"])-truth)
    if fitted["se"] is not None:
        acc["ses"].append(fitted["se"])


def aggregate(acc, replicates, engine):
    if acc["returned"] + sum(acc["failures"].values()) != replicates or sum(acc["decisions"].values()) != replicates:
        raise ValueError("panel accounting differs")
    if acc["correct"] + acc["wrong"] + acc["decisions"]["indeterminate"] != replicates:
        raise ValueError("decision accounting differs")
    errors = acc["errors"]
    return {
        "returned_intervals": acc["returned"], "failures": dict(acc["failures"]),
        "interval_return_rate": engine.rate(acc["returned"], replicates),
        "return_and_cover_rate": engine.rate(acc["covered"], replicates),
        "coverage_given_returned": engine.rate(acc["covered"], acc["returned"]),
        "count_supported_interval_rate": engine.rate(acc["supported"], replicates),
        "coverage_given_count_supported": engine.rate(acc["supported_covered"], acc["supported"]),
        "mean_interval_width_given_returned": mean(acc["widths"]) if acc["widths"] else None,
        "width_range_given_returned": [min(acc["widths"]), max(acc["widths"])] if acc["widths"] else None,
        "point_estimate_count": len(errors), "bias_given_point_estimate": mean(errors) if errors else None,
        "bias_monte_carlo_standard_error": stdev(errors)/math.sqrt(len(errors)) if len(errors) > 1 else None,
        "mean_sampling_se_given_point_estimate": mean(acc["ses"]) if acc["ses"] else None,
        "diagnostic_decisions": dict(acc["decisions"]), "correct_decision_rate": engine.rate(acc["correct"], replicates),
        "wrong_decision_rate": engine.rate(acc["wrong"], replicates),
        "indeterminate_rate": engine.rate(acc["decisions"]["indeterminate"], replicates),
        "empty_bootstrap_draws": acc["empty_draws"], "rare_source_absent_panels": acc["rare_absent"],
        "rare_absent_return_and_cover_rate": engine.rate(acc["rare_absent_covered"], acc["rare_absent"]),
        "rare_absent_coverage_given_returned": engine.rate(acc["rare_absent_covered"], acc["rare_absent_returned"]),
    }


def simulate_case(experiment, scenario, replicates, draws, engine, analysis, coordinates, response):
    accs = {name: accumulator() for name in METHODS}
    counts_seen, bound_widths, contained = [], [], 0
    stability = {name: {"panels": 0, "both_intervals_returned": 0, "return_state_changes": 0,
                        "decision_changes": 0, "maximum_endpoint_change": 0.0,
                        "maximum_width_change": 0.0} for name in METHODS[1:]}
    truth = scenario["mean_ticks"]/10
    for replicate in range(replicates):
        generated, rare_absent = generated_panel(experiment, scenario, replicate, engine)
        matrix, complete = linked_matrix(generated, experiment, response)
        info = summary(matrix)
        counts_seen.append(info["counts"])
        lo, hi = info["finite_bounds"]
        full_panel_mean = Fraction(sum(item[2] for item in generated), 10*info["planned"])
        contained += lo <= full_panel_mean <= hi
        bound_widths.append(float(hi-lo))
        extended = replicate < experiment["stability_replicates"]
        total_draws = 2*draws if extended else draws
        samples = bootstrap_sums(matrix, rng_for(experiment, scenario, replicate, "bootstrap"), total_draws)
        primary = crossed_intervals(matrix, samples[:draws])
        primary[METHODS[0]] = legacy_interval(complete, analysis, engine)
        for name, fitted in primary.items():
            observe(accs[name], fitted, info["counts"], truth, coordinates, rare_absent)
        if extended:
            doubled = crossed_intervals(matrix, samples)
            for name, checked in doubled.items():
                record, original = stability[name], primary[name]
                record["panels"] += 1
                record["return_state_changes"] += (original["interval"] is None) != (checked["interval"] is None)
                record["decision_changes"] += state(original, info["counts"], coordinates) != state(checked, info["counts"], coordinates)
                if original["interval"] is not None and checked["interval"] is not None:
                    record["both_intervals_returned"] += 1
                    record["maximum_endpoint_change"] = max(record["maximum_endpoint_change"], *(float(abs(a-b)) for a, b in zip(original["interval"], checked["interval"], strict=True)))
                    original_width = original["interval"][1] - original["interval"][0]
                    checked_width = checked["interval"][1] - checked["interval"][0]
                    record["maximum_width_change"] = max(record["maximum_width_change"], float(abs(checked_width-original_width)))
    if contained != replicates:
        raise ValueError("finite-panel missingness bounds exclude a possible completion")
    return {"scenario": scenario, "replicates": replicates,
            "complete_count_ranges": {key: [min(item[key] for item in counts_seen), max(item[key] for item in counts_seen)] for key in ("listeners", "sources", "responses")},
            "finite_panel_bounds": {"containment": engine.rate(contained, replicates), "mean_width": mean(bound_widths), "is_population_confidence_interval": False},
            "methods": {name: aggregate(acc, replicates, engine) for name, acc in accs.items()}, "bootstrap_doubling_diagnostic": stability}


def build_report(replicates: int | None = None, draws: int | None = None):
    plan = load_plan()
    experiment = plan["experiment"]
    replicates = experiment["replicates"] if replicates is None else replicates
    draws = experiment["bootstrap_draws"] if draws is None else draws
    if type(replicates) is not int or not 1 <= replicates <= experiment["replicates"] or type(draws) is not int or not 2 <= draws <= experiment["bootstrap_draws"]:
        raise ValueError("reduced smoke arguments outside frozen bounds")
    engine = load_engine()
    analysis, paired, decisions = (engine.load_module(name) for name in ("analysis", "paired", "decisions"))
    decisions.load_plan()
    response = engine.response_factory(paired)
    scenarios = [simulate_case(experiment, scenario, replicates, draws, engine, analysis, decisions.COORDINATES, response) for scenario in experiment["scenarios"]]
    response.cache_clear()
    return engine.rounded({
        "schema_version": 1, "report_id": plan["plan_id"], "plan_sha256": PLAN_SHA,
        "implementation_sha256": sha(Path(__file__)), "bindings": plan["bindings"], "access_boundary": plan["access_boundary"],
        "state": "synthetic_resampling_comparison_complete" if (replicates, draws) == (experiment["replicates"], experiment["bootstrap_draws"]) else "reduced_synthetic_smoke_only",
        "replicates_per_scenario": replicates, "bootstrap_draws": draws, "bootstrap_doubling_draws": 2*draws,
        "population_estimand": experiment["population_target"], "nominal_pointwise_coverage_reference": .975,
        "scenarios": scenarios, "all_planned_panels_and_empty_draws_accounted_for": True,
        "method_selected_for_human_calibration": False, "human_interval_coverage_validated": False,
        "human_materiality_margin_selected": False, "audibility_coverage_evaluated": False,
        "familywise_coverage_evaluated": False, "independent_method_validation_complete": False,
        "human_responses_observed": False, "oracle_truth_eligible": False,
        "no_reference_training_eligible": False, "objective_complete": False,
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.parse_args()
    print(canonical(build_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
