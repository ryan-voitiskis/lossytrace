#!/usr/bin/env python3
"""Score-blind retained-design robustness frontier for listening preparation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/"
    "listening-retained-design-robustness-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-listening-retained-design-robustness-"
    "20260814-001.json"
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FEASIBILITY = _load_module(
    "perceptual_degradation_listening_feasibility_for_retained_design",
    ROOT / "scripts/perceptual_degradation_listening_feasibility.py",
)
MISSINGNESS = _load_module(
    "perceptual_degradation_listening_missingness_for_retained_design",
    ROOT / "scripts/perceptual_degradation_listening_missingness_stress.py",
)
RESOURCE = _load_module(
    "perceptual_degradation_listening_resource_for_retained_design",
    ROOT / "scripts/perceptual_degradation_listening_resource_frontier.py",
)
ALLOCATOR = _load_module(
    "perceptual_degradation_listening_allocator_v3_for_retained_design",
    ROOT / "scripts/perceptual_degradation_listening_allocation_v3.py",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _round(value: float, digits: int = 10) -> float:
    return round(value, digits)


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if plan.get("plan_id") != (
        "perceptual-degradation-listening-retained-design-robustness-"
        "20260814-001"
    ):
        errors.append("plan_id differs")
    if plan.get("state") != (
        "score_blind_retained_design_sensitivity_no_operational_policy"
    ):
        errors.append("state differs")

    expected_bindings = {
        "feasibility_plan",
        "feasibility_report",
        "resource_frontier_plan",
        "resource_frontier_report",
        "allocator_v3_audit_plan",
        "allocator_v3_audit_report",
        "missingness_plan",
        "missingness_report",
        "power_implementation",
        "missingness_implementation",
        "allocator_v3",
        "symbolic_manifest_builder",
    }
    bindings = plan.get("bindings")
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        errors.append("bindings differ")
    else:
        for binding_id, binding in bindings.items():
            if not isinstance(binding, dict):
                errors.append(f"binding {binding_id} must be an object")
                continue
            path_value = binding.get("path")
            digest = binding.get("sha256")
            if not isinstance(path_value, str) or Path(path_value).is_absolute():
                errors.append(f"binding {binding_id} path must be relative")
                continue
            path = root / path_value
            if not path.is_file():
                errors.append(f"binding {binding_id} path is missing")
            elif sha256_file(path) != digest:
                errors.append(f"binding {binding_id} sha256 differs")

    authorization = plan.get("authorization", {})
    true_authority = {"synthetic_symbolic_retained_design_replay_authorized"}
    for key, value in authorization.items():
        if value is not (key in true_authority):
            errors.append(f"authorization {key} differs")
    if set(authorization) != {
        "synthetic_symbolic_retained_design_replay_authorized",
        "observed_response_access_authorized",
        "listener_identity_access_authorized",
        "exact_source_member_selection_authorized",
        "retained_audio_read_authorized",
        "new_audio_acquisition_authorized",
        "stimulus_generation_authorized",
        "human_collection_authorized",
        "recruitment_authorized",
        "perceptual_metric_execution_authorized",
        "sealed_evidence_access_authorized",
        "no_reference_training_authorized",
        "public_verdict_enabled",
    }:
        errors.append("authorization keys differ")

    stress = plan.get("stress_contract", {})
    expected_stress = {
        "source_group_count": 120,
        "minimum_judgments_per_source": 8,
        "replicate_count": 256,
        "retention_rates": [0.85, 0.90, 0.95],
        "issued_reserve_multipliers": [1.0, 1.1, 1.2, 1.3, 1.4],
        "source_correlated_loss_counts": [6, 12, 24],
        "replicate_joint_gate_pass_rate": 0.95,
        "power_target": 0.80,
        "planning_truth": {
            "transparent_audibility_probability": 0.50,
            "audible_probability": 0.80,
            "sdg": -1.25,
            "mushra_loss": 15.0,
        },
        "retained_design_standard_error": (
            "frozen_random_effect_variances_with_realized_synthetic_design_"
            "counts_and_kish_effective_listener_and_source_counts"
        ),
        "position_adjusted_contrast_gate": (
            "candidate_position_bipartite_graph_connected_for_every_retained_"
            "symbolic_trial"
        ),
        "source_breadth_after_structured_loss": (
            "unassessed_without_frozen_provider_domain_and_partition_membership"
        ),
        "outcomes_generated": False,
        "outcomes_read": False,
    }
    if stress != expected_stress:
        errors.append("stress contract differs")

    expected_options = [
        ("sources120-subtle3-mushra3", 3, 3, 765),
        ("sources120-subtle5-mushra5", 5, 5, 496),
        ("sources120-subtle8-mushra6", 8, 6, 345),
        ("sources120-subtle15-mushra6", 15, 6, 227),
    ]
    options = plan.get("frontier_options", [])
    observed_options = [
        (
            item.get("option_id"),
            item.get("subtle_trial_limit"),
            item.get("mushra_trial_limit"),
            item.get("base_eligible_prefix"),
        )
        for item in options
        if isinstance(item, dict)
    ]
    if observed_options != expected_options:
        errors.append("frontier options differ")

    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must contain only false values")
    return errors


def kish_effective_count(counts: list[int]) -> float:
    positive = [value for value in counts if value > 0]
    if not positive:
        return 0.0
    total = sum(positive)
    return total * total / sum(value * value for value in positive)


def _connected_components(
    candidate_ids: list[str], position_count: int, edges: set[tuple[str, int]]
) -> int:
    vertices = {f"candidate:{value}" for value in candidate_ids}
    vertices.update(f"position:{value}" for value in range(1, position_count + 1))
    adjacency: dict[str, set[str]] = {value: set() for value in vertices}
    for candidate_id, position in edges:
        candidate = f"candidate:{candidate_id}"
        position_vertex = f"position:{position}"
        if candidate not in adjacency or position_vertex not in adjacency:
            raise ValueError("candidate-position edge is outside the trial graph")
        adjacency[candidate].add(position_vertex)
        adjacency[position_vertex].add(candidate)
    components = 0
    unseen = set(vertices)
    while unseen:
        components += 1
        start = unseen.pop()
        queue: deque[str] = deque((start,))
        while queue:
            current = queue.popleft()
            for neighbour in adjacency[current]:
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    queue.append(neighbour)
    return components


def _method_design_summary(
    plan: dict[str, Any],
    feasibility_plan: dict[str, Any],
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    retained: list[dict[str, Any]],
    method: str,
) -> dict[str, Any]:
    minimum_judgments = plan["stress_contract"][
        "minimum_judgments_per_source"
    ]
    manifest_trials = {
        item["trial_id"]: item
        for item in manifest["trials"]
        if item["method"] == method
    }
    method_rows = [item for item in retained if item["method"] == method]
    scheduled_rows = [item for item in rows if item["method"] == method]
    listener_counts = Counter(item["allocation_index"] for item in method_rows)
    source_counts = Counter(item["source_group_id"] for item in method_rows)
    all_source_ids = sorted(
        {
            stimulus["source_group_id"]
            for stimulus in manifest["stimuli"]
        }
    )
    source_exposures = [source_counts[value] for value in all_source_ids]

    graph_edges: dict[str, set[tuple[str, int]]] = defaultdict(set)
    for row in method_rows:
        for item in row["candidate_positions"]:
            graph_edges[row["trial_id"]].add(
                (item["stimulus_id"], item["position"])
            )
    graph_components: dict[str, int] = {}
    graph_edge_cells: dict[str, int] = {}
    for trial_id, trial in manifest_trials.items():
        candidate_ids = trial["candidate_ids"]
        edges = graph_edges[trial_id]
        graph_components[trial_id] = _connected_components(
            candidate_ids, len(candidate_ids), edges
        )
        graph_edge_cells[trial_id] = len(edges)

    listener_ess = kish_effective_count(list(listener_counts.values()))
    source_ess = kish_effective_count(list(source_counts.values()))
    response_count = len(method_rows)
    power_target = plan["stress_contract"]["power_target"]
    variance = feasibility_plan["variance_components"]
    if min(listener_ess, source_ess, response_count) <= 0:
        audibility_se = math.inf
        continuous_se = math.inf
    elif method == "subtle":
        probability = plan["stress_contract"]["planning_truth"][
            "transparent_audibility_probability"
        ]
        slope = probability * (1.0 - probability)
        audibility_se = math.sqrt(
            (slope * variance["audibility"]["listener_logit_sd"]) ** 2
            / listener_ess
            + (slope * variance["audibility"]["source_logit_sd"]) ** 2
            / source_ess
            + probability * (1.0 - probability) / response_count
        )
        continuous_se = math.sqrt(
            variance["sdg"]["listener_sd"] ** 2 / listener_ess
            + variance["sdg"]["source_sd"] ** 2 / source_ess
            + variance["sdg"]["residual_sd"] ** 2 / response_count
        )
    else:
        audibility_se = math.inf
        continuous_se = math.sqrt(
            variance["mushra_loss"]["listener_sd"] ** 2 / listener_ess
            + variance["mushra_loss"]["source_sd"] ** 2 / source_ess
            + variance["mushra_loss"]["residual_sd"] ** 2 / response_count
        )

    summary: dict[str, Any] = {
        "scheduled_trials": len(scheduled_rows),
        "retained_trials": response_count,
        "retained_trial_rate": _round(
            response_count / len(scheduled_rows) if scheduled_rows else 0.0
        ),
        "retained_session_slots": len(listener_counts),
        "kish_effective_listener_count": _round(listener_ess),
        "retained_source_groups": sum(value > 0 for value in source_exposures),
        "kish_effective_source_count": _round(source_ess),
        "source_groups_with_zero_judgments": sum(
            value == 0 for value in source_exposures
        ),
        "source_groups_below_minimum_judgments": sum(
            value < minimum_judgments for value in source_exposures
        ),
        "minimum_source_judgments": min(source_exposures, default=0),
        "maximum_source_judgments": max(source_exposures, default=0),
        "minimum_judgment_support_gate_passed": all(
            value >= minimum_judgments for value in source_exposures
        ),
        "position_graph_disconnected_trial_count": sum(
            value != 1 for value in graph_components.values()
        ),
        "position_graph_maximum_component_count": max(
            graph_components.values(), default=0
        ),
        "position_graph_minimum_observed_edge_cells": min(
            graph_edge_cells.values(), default=0
        ),
        "position_adjusted_contrast_gate_passed": all(
            value == 1 for value in graph_components.values()
        ),
        "outcomes_included": False,
    }
    if method == "subtle":
        if math.isfinite(audibility_se):
            equivalence_power = FEASIBILITY.equivalence_power(
                feasibility_plan,
                estimate_truth=plan["stress_contract"]["planning_truth"][
                    "transparent_audibility_probability"
                ],
                standard_error=audibility_se,
            )
            audible_power = FEASIBILITY.audible_power(
                feasibility_plan,
                estimate_truth=plan["stress_contract"]["planning_truth"][
                    "audible_probability"
                ],
                standard_error=audibility_se,
            )
            sdg_power = FEASIBILITY.sdg_material_power(
                feasibility_plan, continuous_se
            )
        else:
            equivalence_power = audible_power = sdg_power = 0.0
        summary.update(
            {
                "audibility_standard_error": _round(audibility_se)
                if math.isfinite(audibility_se)
                else None,
                "audibility_equivalence_power_at_truth_0_50": _round(
                    equivalence_power
                ),
                "audible_power_at_truth_0_80": _round(audible_power),
                "sdg_standard_error": _round(continuous_se)
                if math.isfinite(continuous_se)
                else None,
                "sdg_material_power_at_truth_minus_1_25": _round(sdg_power),
                "method_power_gate_passed": min(
                    equivalence_power, audible_power, sdg_power
                )
                >= power_target,
            }
        )
    else:
        mushra_power = (
            FEASIBILITY.mushra_material_power(feasibility_plan, continuous_se)
            if math.isfinite(continuous_se)
            else 0.0
        )
        summary.update(
            {
                "mushra_standard_error": _round(continuous_se)
                if math.isfinite(continuous_se)
                else None,
                "mushra_material_power_at_truth_15": _round(mushra_power),
                "method_power_gate_passed": mushra_power >= power_target,
            }
        )
    return summary


def analyze_retained_design(
    plan: dict[str, Any],
    feasibility_plan: dict[str, Any],
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    keep: Callable[[dict[str, Any]], bool],
) -> dict[str, Any]:
    retained = [row for row in rows if keep(row)]
    methods = {
        method: _method_design_summary(
            plan,
            feasibility_plan,
            manifest,
            rows,
            retained,
            method,
        )
        for method in ("subtle", "mushra")
    }
    sdg_power = methods["subtle"][
        "sdg_material_power_at_truth_minus_1_25"
    ]
    mushra_power = methods["mushra"]["mushra_material_power_at_truth_15"]
    direct_joint_lower_bound = max(0.0, sdg_power + mushra_power - 1.0)
    power_target = plan["stress_contract"]["power_target"]
    fixed_manifest_support = all(
        value["minimum_judgment_support_gate_passed"]
        for value in methods.values()
    )
    position_contrast = all(
        value["position_adjusted_contrast_gate_passed"]
        for value in methods.values()
    )
    retained_power = (
        all(value["method_power_gate_passed"] for value in methods.values())
        and direct_joint_lower_bound >= power_target
    )
    return {
        "scheduled_session_slots": len(
            {row["allocation_index"] for row in rows}
        ),
        "retained_session_slots": len(
            {row["allocation_index"] for row in retained}
        ),
        "scheduled_trials": len(rows),
        "retained_trials": len(retained),
        "retained_trial_rate": _round(
            len(retained) / len(rows) if rows else 0.0
        ),
        "methods": methods,
        "direct_material_joint_power_lower_bound": _round(
            direct_joint_lower_bound
        ),
        "fixed_manifest_support_gate_passed": fixed_manifest_support,
        "position_adjusted_contrast_gate_passed": position_contrast,
        "retained_aggregate_power_gate_passed": retained_power,
        "joint_planning_gate_passed": (
            fixed_manifest_support and position_contrast and retained_power
        ),
        "source_breadth_gate_evaluated": False,
        "operational_collection_gate_evaluated": False,
        "outcomes_included": False,
    }


def _distribution(values: list[float | int]) -> dict[str, float | int]:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("distribution requires at least one value")

    def percentile(fraction: float) -> float | int:
        return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]

    return {
        "min": ordered[0],
        "p05": percentile(0.05),
        "median": percentile(0.50),
        "p95": percentile(0.95),
        "max": ordered[-1],
    }


def aggregate_replicates(
    summaries: list[dict[str, Any]], required_pass_rate: float
) -> dict[str, Any]:
    replicate_count = len(summaries)
    required_pass_count = math.ceil(required_pass_rate * replicate_count)
    method_metrics = {
        "subtle": (
            "kish_effective_listener_count",
            "kish_effective_source_count",
            "source_groups_below_minimum_judgments",
            "position_graph_disconnected_trial_count",
            "audibility_equivalence_power_at_truth_0_50",
            "audible_power_at_truth_0_80",
            "sdg_material_power_at_truth_minus_1_25",
        ),
        "mushra": (
            "kish_effective_listener_count",
            "kish_effective_source_count",
            "source_groups_below_minimum_judgments",
            "position_graph_disconnected_trial_count",
            "mushra_material_power_at_truth_15",
        ),
    }
    methods = {
        method: {
            metric: _distribution(
                [summary["methods"][method][metric] for summary in summaries]
            )
            for metric in metrics
        }
        for method, metrics in method_metrics.items()
    }
    pass_counts = {
        "fixed_manifest_support": sum(
            value["fixed_manifest_support_gate_passed"] for value in summaries
        ),
        "position_adjusted_contrast": sum(
            value["position_adjusted_contrast_gate_passed"]
            for value in summaries
        ),
        "retained_aggregate_power": sum(
            value["retained_aggregate_power_gate_passed"]
            for value in summaries
        ),
        "joint_planning": sum(
            value["joint_planning_gate_passed"] for value in summaries
        ),
    }
    worst_index = min(
        range(replicate_count),
        key=lambda index: (
            summaries[index]["joint_planning_gate_passed"],
            summaries[index]["retained_aggregate_power_gate_passed"],
            summaries[index]["fixed_manifest_support_gate_passed"],
            summaries[index]["position_adjusted_contrast_gate_passed"],
            summaries[index]["methods"]["subtle"][
                "audibility_equivalence_power_at_truth_0_50"
            ],
            -summaries[index]["methods"]["subtle"][
                "source_groups_below_minimum_judgments"
            ],
            -summaries[index]["methods"]["mushra"][
                "source_groups_below_minimum_judgments"
            ],
        ),
    )
    return {
        "replicate_count": replicate_count,
        "required_pass_rate": required_pass_rate,
        "required_pass_count": required_pass_count,
        "replicate_summaries_sha256": canonical_sha256(summaries),
        "pass_counts": pass_counts,
        "joint_planning_gate_meets_required_pass_rate": (
            pass_counts["joint_planning"] >= required_pass_count
        ),
        "retained_trial_rate": _distribution(
            [summary["retained_trial_rate"] for summary in summaries]
        ),
        "direct_material_joint_power_lower_bound": _distribution(
            [
                summary["direct_material_joint_power_lower_bound"]
                for summary in summaries
            ]
        ),
        "methods": methods,
        "worst_replicate_index": worst_index,
        "worst_replicate_summary": summaries[worst_index],
        "outcomes_included": False,
    }


def _mcar_aggregate(
    plan: dict[str, Any],
    feasibility_plan: dict[str, Any],
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    seed: str,
    kind: str,
    retention_rate: float,
) -> dict[str, Any]:
    scenario_id = f"{kind}-retention-{retention_rate:.2f}"
    summaries = []
    for replicate in range(plan["stress_contract"]["replicate_count"]):
        if kind == "hash_mcar_session":
            keep = lambda row, replicate=replicate: MISSINGNESS._hash_keep(
                retention_rate,
                seed,
                scenario_id,
                str(replicate),
                str(row["allocation_index"]),
            )
        elif kind == "hash_mcar_trial":
            keep = lambda row, replicate=replicate: MISSINGNESS._hash_keep(
                retention_rate,
                seed,
                scenario_id,
                str(replicate),
                str(row["allocation_index"]),
                row["method"],
                row["trial_id"],
            )
        else:
            raise ValueError(f"unsupported MCAR kind: {kind}")
        summaries.append(
            analyze_retained_design(
                plan, feasibility_plan, manifest, rows, keep
            )
        )
    return {
        "scenario_id": scenario_id,
        "kind": kind,
        "retention_rate": retention_rate,
        "aggregate": aggregate_replicates(
            summaries,
            plan["stress_contract"]["replicate_joint_gate_pass_rate"],
        ),
    }


def _source_correlated_result(
    plan: dict[str, Any],
    feasibility_plan: dict[str, Any],
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    seed: str,
    source_group_ids: list[str],
    loss_count: int,
) -> dict[str, Any]:
    scenario_id = f"source-correlated-loss-{loss_count}"
    excluded = set(
        sorted(
            source_group_ids,
            key=lambda value: hashlib.sha256(
                "\0".join((seed, scenario_id, value)).encode()
            ).hexdigest(),
        )[:loss_count]
    )
    summary = analyze_retained_design(
        plan,
        feasibility_plan,
        manifest,
        rows,
        lambda row: row["source_group_id"] not in excluded,
    )
    return {
        "scenario_id": scenario_id,
        "kind": "source_correlated",
        "excluded_source_group_count": loss_count,
        "excluded_source_group_set_sha256": canonical_sha256(sorted(excluded)),
        "summary": summary,
    }


def _minimum_passing_multiplier(
    reserve_rows: list[dict[str, Any]], kind: str, retention_rate: float
) -> float | None:
    for reserve in reserve_rows:
        scenario = next(
            value
            for value in reserve["mcar_scenarios"]
            if value["kind"] == kind
            and value["retention_rate"] == retention_rate
        )
        if scenario["aggregate"][
            "joint_planning_gate_meets_required_pass_rate"
        ]:
            return reserve["issued_reserve_multiplier"]
    return None


def build_report(
    plan: dict[str, Any], plan_path: Path = PLAN_PATH
) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    feasibility_plan = load_json(_bound(plan, "feasibility_plan"))
    feasibility_report = load_json(_bound(plan, "feasibility_report"))
    resource_plan = load_json(_bound(plan, "resource_frontier_plan"))
    missingness_report = load_json(_bound(plan, "missingness_report"))
    allocator_audit = load_json(_bound(plan, "allocator_v3_audit_report"))
    if not allocator_audit["decision"][
        "v3_all_audited_contiguous_prefixes_passed"
    ]:
        raise ValueError("bound v3 audit does not pass")
    if missingness_report["decision"][
        "all_mcar_replicates_preserve_strict_balance"
    ]:
        raise ValueError("bound missingness report no longer exposes imbalance")
    if feasibility_report["decision"]["operational_design_frozen"]:
        raise ValueError("bound feasibility report unexpectedly freezes a design")

    manifest = RESOURCE.make_symbolic_manifest(resource_plan)
    manifest_errors = ALLOCATOR.validate_manifest(manifest)
    if manifest_errors:
        raise ValueError("; ".join(manifest_errors))
    source_group_ids = sorted(
        {item["source_group_id"] for item in manifest["stimuli"]}
    )
    if len(source_group_ids) != plan["stress_contract"]["source_group_count"]:
        raise ValueError("symbolic source-group count differs")
    seed = resource_plan["symbolic_fixture"]["allocation_seed"]
    eligible_retention = feasibility_plan["score_blind_stress_assumptions"][
        "eligible_listener_retention_rate"
    ]

    option_results = []
    minimums: dict[str, Any] = {}
    for option in plan["frontier_options"]:
        reserve_rows = []
        for multiplier in plan["stress_contract"][
            "issued_reserve_multipliers"
        ]:
            issued_prefix = math.ceil(
                option["base_eligible_prefix"] * multiplier
            )
            rows = MISSINGNESS._make_schedule(
                manifest,
                seed,
                issued_prefix,
                option["subtle_trial_limit"],
                option["mushra_trial_limit"],
            )
            mcar_scenarios = [
                _mcar_aggregate(
                    plan,
                    feasibility_plan,
                    manifest,
                    rows,
                    seed,
                    kind,
                    retention_rate,
                )
                for retention_rate in plan["stress_contract"][
                    "retention_rates"
                ]
                for kind in ("hash_mcar_session", "hash_mcar_trial")
            ]
            source_scenarios = [
                _source_correlated_result(
                    plan,
                    feasibility_plan,
                    manifest,
                    rows,
                    seed,
                    source_group_ids,
                    loss_count,
                )
                for loss_count in plan["stress_contract"][
                    "source_correlated_loss_counts"
                ]
            ]
            reserve_rows.append(
                {
                    "issued_reserve_multiplier": multiplier,
                    "issued_eligible_prefix": issued_prefix,
                    "planning_enrolled_slots_per_stratum_device_partition": (
                        math.ceil(issued_prefix / eligible_retention)
                    ),
                    "planning_enrolled_slots_across_four_partitions": (
                        4 * math.ceil(issued_prefix / eligible_retention)
                    ),
                    "mcar_scenarios": mcar_scenarios,
                    "source_correlated_scenarios": source_scenarios,
                }
            )
        minimums[option["option_id"]] = {
            kind: {
                f"retention_{retention_rate:.2f}": _minimum_passing_multiplier(
                    reserve_rows, kind, retention_rate
                )
                for retention_rate in plan["stress_contract"][
                    "retention_rates"
                ]
            }
            for kind in ("hash_mcar_session", "hash_mcar_trial")
        }
        option_results.append(
            {
                "option_id": option["option_id"],
                "trial_limits": {
                    "subtle": option["subtle_trial_limit"],
                    "mushra": option["mushra_trial_limit"],
                },
                "base_eligible_prefix": option["base_eligible_prefix"],
                "reserve_rows": reserve_rows,
            }
        )

    all_mcar_cells_have_bounded_option = all(
        multiplier is not None
        for option in minimums.values()
        for kind in option.values()
        for multiplier in kind.values()
    )
    structured = [
        scenario["summary"]
        for option in option_results
        for reserve in option["reserve_rows"]
        for scenario in reserve["source_correlated_scenarios"]
    ]
    return {
        "schema_version": 1,
        "report_id": plan["plan_id"],
        "state": "score_blind_retained_design_sensitivity_complete",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "symbolic_manifest_sha256": canonical_sha256(manifest),
        "audio_accessed": False,
        "outcome_values_generated": False,
        "outcome_values_read": False,
        "listener_identities_accessed": False,
        "human_collection_performed": False,
        "public_verdict_enabled": False,
        "option_results": option_results,
        "minimum_reserve_multiplier_by_option_kind_and_retention": minimums,
        "decision": {
            "all_mcar_sensitivity_cells_have_bounded_reserve_option": (
                all_mcar_cells_have_bounded_option
            ),
            "all_source_correlated_cells_preserve_fixed_manifest_support": all(
                value["fixed_manifest_support_gate_passed"]
                for value in structured
            ),
            "any_source_correlated_cell_preserves_retained_aggregate_power": any(
                value["retained_aggregate_power_gate_passed"]
                for value in structured
            ),
            "source_correlated_breadth_gate_evaluated": False,
            "synthetic_retention_mechanism_empirically_established": False,
            "reserve_option_selected": False,
            "listener_count_frozen": False,
            "missingness_policy_selected": False,
            "exclusion_policy_selected": False,
            "adaptive_replacement_authorized": False,
            "operational_design_selected": False,
            "collection_authorized": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "next_responsible_human_decision": (
                "Decide whether the bounded reserve and resource envelope is "
                "acceptable enough to justify a separately frozen pilot and "
                "operational allocation-policy successor. Synthetic pass rates "
                "do not establish the missingness mechanism, and structured "
                "source loss still requires exact-member breadth and power "
                "recalculation with explicit abstention."
            ),
        },
        "claim_boundary": plan["claim_boundary"],
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != 1:
        errors.append("report schema_version differs")
    if report.get("state") != (
        "score_blind_retained_design_sensitivity_complete"
    ):
        errors.append("report state differs")
    for key in (
        "audio_accessed",
        "outcome_values_generated",
        "outcome_values_read",
        "listener_identities_accessed",
        "human_collection_performed",
        "public_verdict_enabled",
    ):
        if report.get(key) is not False:
            errors.append(f"report {key} must be false")
    decision = report.get("decision", {})
    for key in (
        "source_correlated_breadth_gate_evaluated",
        "synthetic_retention_mechanism_empirically_established",
        "reserve_option_selected",
        "listener_count_frozen",
        "missingness_policy_selected",
        "exclusion_policy_selected",
        "adaptive_replacement_authorized",
        "operational_design_selected",
        "collection_authorized",
        "no_reference_work_eligible",
        "public_verdict_enabled",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision {key} must be false")
    if report.get("claim_boundary") and any(
        value is not False for value in report["claim_boundary"].values()
    ):
        errors.append("report claim boundary must remain false")
    return errors


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    plan = load_json(args.plan)
    report = build_report(plan, args.plan)
    errors = validate_report(report)
    if errors:
        raise SystemExit("; ".join(errors))
    write_report(report, args.output)
    print(
        json.dumps(
            {
                "report_id": report["report_id"],
                "all_mcar_cells_bounded": report["decision"][
                    "all_mcar_sensitivity_cells_have_bounded_reserve_option"
                ],
                "source_loss_fixed_support": report["decision"][
                    "all_source_correlated_cells_preserve_fixed_manifest_support"
                ],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
