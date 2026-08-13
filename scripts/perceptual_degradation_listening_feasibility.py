#!/usr/bin/env python3
"""Compute a score-blind listening-design feasibility frontier.

This is a known-variance normal planning approximation.  It reads only a
committed plan and its bound public preparation artifacts.  It does not read
audio, scores, response records, or sealed evidence, and it cannot authorize
collection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/listening-feasibility-frontier-plan.json"
)
PLAN_ID = "perceptual-degradation-listening-feasibility-frontier-20260813-001"
REPORT_ID = "perceptual-degradation-listening-feasibility-frontier-20260813-001"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _round(value: float | None, digits: int = 10) -> float | None:
    return None if value is None else round(value, digits)


def _normal_cdf(value: float) -> float:
    return NormalDist().cdf(value)


def _normal_quantile(probability: float) -> float:
    if not 0.0 < probability < 1.0:
        raise ValueError("normal quantile probability must lie inside (0, 1)")
    return NormalDist().inv_cdf(probability)


def _validate_rate(name: str, value: Any, *, allow_one: bool = False) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    upper_ok = value <= 1.0 if allow_one else value < 1.0
    if value < 0.0 or not upper_ok:
        bracket = "[0, 1]" if allow_one else "[0, 1)"
        raise ValueError(f"{name} must lie in {bracket}")


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != "score_blind_feasibility_frontier_no_operational_design_frozen":
        errors.append("plan state differs")

    expected_authorization = {
        "retained_odaq_reference_read_authorized": False,
        "retained_reference_projection_authorized": False,
        "processed_condition_access_authorized": False,
        "listening_score_access_authorized": False,
        "human_collection_authorized": False,
        "recruitment_authorized": False,
        "perceptual_metric_execution_authorized": False,
        "sealed_evidence_access_authorized": False,
        "no_reference_training_authorized": False,
        "public_verdict_enabled": False,
        "score_blind_analytic_planning_only": True,
    }
    if plan.get("authorization") != expected_authorization:
        errors.append("authorization boundary differs")

    bindings = plan.get("bindings", {})
    if not bindings:
        errors.append("bindings are missing")
    for binding_id, binding in bindings.items():
        relative = binding.get("path")
        expected = binding.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            errors.append(f"binding differs: {binding_id}")
            continue
        path = root / relative
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif _sha256(path) != expected:
            errors.append(f"bound file hash differs: {binding_id}")

    targets = plan.get("frozen_decision_targets", {})
    expected_targets = {
        "familywise_alpha": 0.05,
        "multiplicity_families": 4,
        "target_power": 0.80,
        "audibility_chance": 0.50,
        "audibility_point_gate": 0.75,
        "audibility_equivalence_interval": [0.45, 0.55],
        "planning_audible_truth": 0.80,
        "sdg_material_threshold": -1.0,
        "planning_sdg_truth": -1.25,
        "mushra_loss_material_threshold": 10.0,
        "planning_mushra_loss_truth": 15.0,
        "planning_unified_severity_threshold": 25.0,
        "planning_unified_severity_truth": 37.5,
    }
    if targets != expected_targets:
        errors.append("frozen targets differ")

    expected_variance = {
        "audibility": {"listener_logit_sd": 0.45, "source_logit_sd": 0.35},
        "sdg": {"listener_sd": 0.25, "source_sd": 0.30, "residual_sd": 0.50},
        "mushra_loss": {"listener_sd": 4.0, "source_sd": 5.0, "residual_sd": 8.0},
        "state": "carried_forward_from_score_blind_power_model_not_estimated_from_outcomes",
    }
    if plan.get("variance_components") != expected_variance:
        errors.append("variance components differ")

    stress = plan.get("score_blind_stress_assumptions", {})
    for key in (
        "enrollment_dropout_rate",
        "training_failure_rate",
        "technical_or_quality_exclusion_rate",
    ):
        try:
            _validate_rate(key, stress.get(key))
        except ValueError as error:
            errors.append(str(error))
    try:
        _validate_rate(
            "eligible_listener_retention_rate",
            stress.get("eligible_listener_retention_rate"),
            allow_one=True,
        )
        _validate_rate(
            "usable_trial_rate_after_missingness",
            stress.get("usable_trial_rate_after_missingness"),
            allow_one=True,
        )
    except ValueError as error:
        errors.append(str(error))
    expected_retention = (
        (1.0 - stress.get("enrollment_dropout_rate", 1.0))
        * (1.0 - stress.get("training_failure_rate", 1.0))
        * (1.0 - stress.get("technical_or_quality_exclusion_rate", 1.0))
    )
    if not math.isclose(
        stress.get("eligible_listener_retention_rate", -1.0),
        expected_retention,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        errors.append("eligible listener retention product differs")
    if stress.get("status") != "planning_sensitivities_not_empirical_estimates_and_not_collection_thresholds":
        errors.append("stress assumption status differs")

    grid = plan.get("frontier_grid", {})
    if grid.get("independent_source_groups_per_partition") != [
        16,
        24,
        38,
        39,
        48,
        64,
        80,
        96,
        120,
        160,
    ]:
        errors.append("source frontier differs")
    if grid.get("transparent_trials_per_eligible_listener") != [3, 5, 8, 15]:
        errors.append("trial frontier differs")
    if grid.get("maximum_subtle_trials_per_session") != 15:
        errors.append("subtle session cap differs")
    if grid.get("maximum_mushra_trials_per_session") != 6:
        errors.append("MUSHRA session cap differs")
    if grid.get("maximum_eligible_listener_search") != 1_000_000:
        errors.append("listener search ceiling differs")
    if grid.get("minimum_effective_judgments_per_source") != 8:
        errors.append("minimum source judgment count differs")
    if grid.get("grouped_partition_counts") != [1, 3, 4]:
        errors.append("partition frontier differs")
    if grid.get("device_class_counts") != [1, 2]:
        errors.append("device frontier differs")

    device = plan.get("device_class_policy", {})
    if (
        device.get("method") != "prespecified_separate_estimands_and_reports"
        or device.get("pooled_cross_device_generalization") is not False
        or device.get("single_declared_chain_supports_other_device_classes") is not False
    ):
        errors.append("device-class policy differs")

    bridge = plan.get("bridge_uncertainty_policy", {})
    if (
        bridge.get("sdg_local_scale_points_per_grade") != 25.0
        or bridge.get("mushra_local_scale_points_per_loss_point") != 2.5
        or bridge.get("primary_material_decision_still_requires_both_direct_method_gates") is not True
        or bridge.get("mapping_uncertainty_is_sensitivity_only") is not True
    ):
        errors.append("bridge uncertainty policy differs")

    claims = plan.get("scope_and_claims", {})
    expected_false = (
        "one_provider_proves_independent_transfer",
        "source_groups_may_cross_partitions",
        "source_groups_may_be_counted_twice",
        "analysis_is_final_hierarchical_model",
        "listener_count_frozen",
        "operational_design_frozen",
        "collection_authorized",
    )
    if claims.get("odaq_clean_reference_count") != 16 or claims.get("odaq_provider_count") != 1:
        errors.append("ODAQ scope differs")
    for key in expected_false:
        if claims.get(key) is not False:
            errors.append(f"claim boundary must remain false: {key}")
    return errors


def z_threshold(plan: dict[str, Any]) -> float:
    targets = plan["frozen_decision_targets"]
    return _normal_quantile(
        1.0 - targets["familywise_alpha"] / targets["multiplicity_families"]
    )


def equivalence_standard_error_ceiling(plan: dict[str, Any]) -> float:
    targets = plan["frozen_decision_targets"]
    lower, upper = targets["audibility_equivalence_interval"]
    chance = targets["audibility_chance"]
    half_width = min(chance - lower, upper - chance)
    target_power_quantile = _normal_quantile((1.0 + targets["target_power"]) / 2.0)
    return half_width / (z_threshold(plan) + target_power_quantile)


def audibility_standard_error(
    plan: dict[str, Any],
    *,
    probability: float,
    eligible_listeners: int,
    source_groups: int,
    trials_per_listener: int,
) -> float:
    if min(eligible_listeners, source_groups, trials_per_listener) <= 0:
        raise ValueError("audibility design counts must be positive")
    variance = plan["variance_components"]["audibility"]
    usable = plan["score_blind_stress_assumptions"][
        "usable_trial_rate_after_missingness"
    ]
    slope = probability * (1.0 - probability)
    effective_judgments = eligible_listeners * trials_per_listener * usable
    return math.sqrt(
        (slope * variance["listener_logit_sd"]) ** 2 / eligible_listeners
        + (slope * variance["source_logit_sd"]) ** 2 / source_groups
        + probability * (1.0 - probability) / effective_judgments
    )


def asymptotic_audibility_standard_error(
    plan: dict[str, Any], *, probability: float, source_groups: int
) -> float:
    if source_groups <= 0:
        raise ValueError("source group count must be positive")
    source_sd = plan["variance_components"]["audibility"]["source_logit_sd"]
    slope = probability * (1.0 - probability)
    return slope * source_sd / math.sqrt(source_groups)


def equivalence_power(plan: dict[str, Any], *, estimate_truth: float, standard_error: float) -> float:
    if standard_error <= 0.0:
        raise ValueError("standard error must be positive")
    lower_margin, upper_margin = plan["frozen_decision_targets"][
        "audibility_equivalence_interval"
    ]
    z_value = z_threshold(plan)
    estimate_lower = lower_margin + z_value * standard_error
    estimate_upper = upper_margin - z_value * standard_error
    if estimate_lower >= estimate_upper:
        return 0.0
    return max(
        0.0,
        _normal_cdf((estimate_upper - estimate_truth) / standard_error)
        - _normal_cdf((estimate_lower - estimate_truth) / standard_error),
    )


def audible_power(plan: dict[str, Any], *, estimate_truth: float, standard_error: float) -> float:
    if standard_error <= 0.0:
        raise ValueError("standard error must be positive")
    targets = plan["frozen_decision_targets"]
    threshold = max(
        targets["audibility_point_gate"],
        targets["audibility_chance"] + z_threshold(plan) * standard_error,
    )
    return max(
        0.0,
        1.0 - _normal_cdf((threshold - estimate_truth) / standard_error),
    )


def continuous_standard_error(
    plan: dict[str, Any],
    *,
    family: str,
    eligible_listeners: int,
    source_groups: int,
    trials_per_listener: int,
) -> float:
    if min(eligible_listeners, source_groups, trials_per_listener) <= 0:
        raise ValueError("continuous design counts must be positive")
    variance = plan["variance_components"][family]
    usable = plan["score_blind_stress_assumptions"][
        "usable_trial_rate_after_missingness"
    ]
    effective_judgments = eligible_listeners * trials_per_listener * usable
    return math.sqrt(
        variance["listener_sd"] ** 2 / eligible_listeners
        + variance["source_sd"] ** 2 / source_groups
        + variance["residual_sd"] ** 2 / effective_judgments
    )


def sdg_material_power(plan: dict[str, Any], standard_error: float) -> float:
    targets = plan["frozen_decision_targets"]
    estimate_limit = targets["sdg_material_threshold"] - z_threshold(plan) * standard_error
    return _normal_cdf(
        (estimate_limit - targets["planning_sdg_truth"]) / standard_error
    )


def mushra_material_power(plan: dict[str, Any], standard_error: float) -> float:
    targets = plan["frozen_decision_targets"]
    estimate_limit = targets["mushra_loss_material_threshold"] + z_threshold(plan) * standard_error
    return 1.0 - _normal_cdf(
        (estimate_limit - targets["planning_mushra_loss_truth"]) / standard_error
    )


def mapped_severity_power(
    plan: dict[str, Any],
    *,
    sdg_standard_error: float,
    mushra_standard_error: float,
    mapping_standard_error: float,
) -> float:
    bridge = plan["bridge_uncertainty_policy"]
    targets = plan["frozen_decision_targets"]
    direct_mapped_se = max(
        bridge["sdg_local_scale_points_per_grade"] * sdg_standard_error,
        bridge["mushra_local_scale_points_per_loss_point"]
        * mushra_standard_error,
    )
    combined = math.sqrt(direct_mapped_se**2 + mapping_standard_error**2)
    estimate_limit = (
        targets["planning_unified_severity_threshold"]
        + z_threshold(plan) * combined
    )
    return 1.0 - _normal_cdf(
        (estimate_limit - targets["planning_unified_severity_truth"]) / combined
    )


def minimum_eligible_listeners_for_equivalence(
    plan: dict[str, Any], *, source_groups: int, trials_per_listener: int
) -> int | None:
    if min(source_groups, trials_per_listener) <= 0:
        raise ValueError("frontier counts must be positive")
    targets = plan["frozen_decision_targets"]
    chance = targets["audibility_chance"]
    slope = chance * (1.0 - chance)
    variance = plan["variance_components"]["audibility"]
    source_component = (slope * variance["source_logit_sd"]) ** 2 / source_groups
    ceiling = equivalence_standard_error_ceiling(plan)
    remaining = ceiling**2 - source_component
    if remaining <= 0.0:
        return None
    usable = plan["score_blind_stress_assumptions"][
        "usable_trial_rate_after_missingness"
    ]
    listener_and_residual = (
        (slope * variance["listener_logit_sd"]) ** 2
        + chance * (1.0 - chance) / (trials_per_listener * usable)
    )
    minimum = math.floor(listener_and_residual / remaining) + 1
    minimum_judgments = plan["frontier_grid"][
        "minimum_effective_judgments_per_source"
    ]
    coverage_minimum = math.ceil(
        minimum_judgments * source_groups / (trials_per_listener * usable)
    )
    minimum = max(minimum, coverage_minimum)
    maximum = plan["frontier_grid"]["maximum_eligible_listener_search"]
    if minimum > maximum:
        return None
    while minimum <= maximum:
        standard_error = audibility_standard_error(
            plan,
            probability=chance,
            eligible_listeners=minimum,
            source_groups=source_groups,
            trials_per_listener=trials_per_listener,
        )
        if equivalence_power(
            plan, estimate_truth=chance, standard_error=standard_error
        ) >= targets["target_power"]:
            return minimum
        minimum += 1
    return None


def _enrolled_listener_slots(plan: dict[str, Any], eligible_listeners: int) -> int:
    retention = plan["score_blind_stress_assumptions"][
        "eligible_listener_retention_rate"
    ]
    return math.ceil(eligible_listeners / retention)


def frontier_row(
    plan: dict[str, Any], *, source_groups: int, trials_per_listener: int
) -> dict[str, Any]:
    targets = plan["frozen_decision_targets"]
    chance = targets["audibility_chance"]
    source_floor = asymptotic_audibility_standard_error(
        plan, probability=chance, source_groups=source_groups
    )
    asymptotic_power = equivalence_power(
        plan, estimate_truth=chance, standard_error=source_floor
    )
    listeners = minimum_eligible_listeners_for_equivalence(
        plan,
        source_groups=source_groups,
        trials_per_listener=trials_per_listener,
    )
    row: dict[str, Any] = {
        "source_groups": source_groups,
        "transparent_trials_per_eligible_listener": trials_per_listener,
        "asymptotic_source_floor_standard_error": _round(source_floor),
        "asymptotic_maximum_equivalence_power": _round(asymptotic_power),
        "target_power_attainable_with_finite_listeners": listeners is not None,
        "minimum_eligible_listeners": listeners,
        "minimum_enrolled_listener_slots": (
            None if listeners is None else _enrolled_listener_slots(plan, listeners)
        ),
    }
    if listeners is None:
        row.update(
            {
                "planning_standard_error": None,
                "equivalence_power": None,
                "audible_power_at_truth_0_80": None,
                "effective_judgments": None,
                "effective_judgments_per_source": None,
                "sdg_material_power_at_truth_minus_1_25": None,
                "mushra_trials_per_eligible_listener_assumed": min(
                    trials_per_listener,
                    plan["frontier_grid"]["maximum_mushra_trials_per_session"],
                ),
                "mushra_material_power_at_truth_15": None,
                "bridge_direct_joint_power_lower_bound": None,
                "mapped_severity_power_by_mapping_standard_error": None,
            }
        )
        return row

    standard_error = audibility_standard_error(
        plan,
        probability=chance,
        eligible_listeners=listeners,
        source_groups=source_groups,
        trials_per_listener=trials_per_listener,
    )
    audible_se = audibility_standard_error(
        plan,
        probability=targets["planning_audible_truth"],
        eligible_listeners=listeners,
        source_groups=source_groups,
        trials_per_listener=trials_per_listener,
    )
    sdg_se = continuous_standard_error(
        plan,
        family="sdg",
        eligible_listeners=listeners,
        source_groups=source_groups,
        trials_per_listener=trials_per_listener,
    )
    mushra_trials = min(
        trials_per_listener,
        plan["frontier_grid"]["maximum_mushra_trials_per_session"],
    )
    mushra_se = continuous_standard_error(
        plan,
        family="mushra_loss",
        eligible_listeners=listeners,
        source_groups=source_groups,
        trials_per_listener=mushra_trials,
    )
    sdg_power = sdg_material_power(plan, sdg_se)
    mushra_power = mushra_material_power(plan, mushra_se)
    usable = plan["score_blind_stress_assumptions"][
        "usable_trial_rate_after_missingness"
    ]
    effective_judgments = listeners * trials_per_listener * usable
    mapping_results = []
    for mapping_se in plan["score_blind_stress_assumptions"][
        "bridge_mapping_standard_error_points"
    ]:
        mapping_results.append(
            {
                "mapping_standard_error_points": mapping_se,
                "power": _round(
                    mapped_severity_power(
                        plan,
                        sdg_standard_error=sdg_se,
                        mushra_standard_error=mushra_se,
                        mapping_standard_error=mapping_se,
                    )
                ),
            }
        )
    row.update(
        {
            "planning_standard_error": _round(standard_error),
            "equivalence_power": _round(
                equivalence_power(
                    plan, estimate_truth=chance, standard_error=standard_error
                )
            ),
            "audible_power_at_truth_0_80": _round(
                audible_power(
                    plan,
                    estimate_truth=targets["planning_audible_truth"],
                    standard_error=audible_se,
                )
            ),
            "effective_judgments": _round(effective_judgments),
            "effective_judgments_per_source": _round(
                effective_judgments / source_groups
            ),
            "sdg_material_power_at_truth_minus_1_25": _round(sdg_power),
            "mushra_trials_per_eligible_listener_assumed": mushra_trials,
            "mushra_material_power_at_truth_15": _round(mushra_power),
            "bridge_direct_joint_power_lower_bound": _round(
                max(0.0, sdg_power + mushra_power - 1.0)
            ),
            "mapped_severity_power_by_mapping_standard_error": mapping_results,
        }
    )
    return row


def _minimum_source_groups(plan: dict[str, Any]) -> int:
    targets = plan["frozen_decision_targets"]
    chance = targets["audibility_chance"]
    source_sd = plan["variance_components"]["audibility"]["source_logit_sd"]
    ceiling = equivalence_standard_error_ceiling(plan)
    slope = chance * (1.0 - chance)
    minimum = math.floor((slope * source_sd / ceiling) ** 2) + 1
    while True:
        source_floor = asymptotic_audibility_standard_error(
            plan, probability=chance, source_groups=minimum
        )
        if equivalence_power(
            plan, estimate_truth=chance, standard_error=source_floor
        ) >= targets["target_power"]:
            return minimum
        minimum += 1


def build_report(plan: dict[str, Any] | None = None) -> dict[str, Any]:
    loaded = (
        json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        if plan is None
        else plan
    )
    errors = validate_plan(loaded)
    if errors:
        raise ValueError("; ".join(errors))
    grid = loaded["frontier_grid"]
    rows = [
        frontier_row(
            loaded,
            source_groups=source_groups,
            trials_per_listener=trials,
        )
        for source_groups in grid["independent_source_groups_per_partition"]
        for trials in grid["transparent_trials_per_eligible_listener"]
    ]
    minimum_sources = _minimum_source_groups(loaded)
    odq_rows = [row for row in rows if row["source_groups"] == 16]
    practical_reference = next(
        row
        for row in rows
        if row["source_groups"] == 120
        and row["transparent_trials_per_eligible_listener"] == 5
    )
    partition_requirements = [
        {
            "partition_count": partition_count,
            "asymptotic_minimum_unique_source_groups": minimum_sources
            * partition_count,
            "reference_120_per_partition_unique_source_groups": 120
            * partition_count,
        }
        for partition_count in grid["grouped_partition_counts"]
    ]
    device_workload = [
        {
            "device_class_count": count,
            "pooled_generalization": False,
            "minimum_enrolled_listener_slots_at_reference_120_source_5_trial_design": practical_reference[
                "minimum_enrolled_listener_slots"
            ]
            * count,
            "effective_judgments_at_reference_120_source_5_trial_design": practical_reference[
                "effective_judgments"
            ]
            * count,
        }
        for count in grid["device_class_counts"]
    ]
    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "score_blind_feasibility_frontier_no_operational_design_frozen",
        "analysis_plan_id": PLAN_ID,
        "analysis_plan_sha256": _sha256(PLAN_PATH),
        "implementation_sha256": _sha256(Path(__file__).resolve()),
        "audio_accessed": False,
        "metric_scores_opened": False,
        "listener_responses_opened": False,
        "sealed_evidence_opened": False,
        "human_collection_authorized": False,
        "public_verdict_enabled": False,
        "planning_model": {
            "class": "known_variance_normal_approximation",
            "final_hierarchical_analysis_substitute": False,
            "one_sided_multiplicity_adjusted_z": _round(z_threshold(loaded)),
            "equivalence_target_standard_error_ceiling": _round(
                equivalence_standard_error_ceiling(loaded)
            ),
            "attrition_and_missingness_are_score_blind_stress_assumptions": True,
            "device_classes_are_separate_estimands": True,
            "bridge_joint_power_uses_frechet_lower_bound": True,
        },
        "odaq_narrow_path": {
            "independent_source_groups": 16,
            "provider_count": 1,
            "development_only": True,
            "asymptotic_maximum_equivalence_power": odq_rows[0][
                "asymptotic_maximum_equivalence_power"
            ],
            "target_power": loaded["frozen_decision_targets"]["target_power"],
            "target_attainable_under_frozen_model": False,
            "transparent_truth_supported": False,
            "independent_transfer_supported": False,
            "reason": "The source random-effect floor alone exceeds the standard-error ceiling required for 80% equivalence power; adding listeners or repeated judgments cannot repair a 16-source aggregate under the frozen model.",
        },
        "source_frontier": {
            "minimum_source_groups_per_independent_partition_for_asymptotic_80_percent_equivalence_power": minimum_sources,
            "source_groups_38_asymptotic_power": next(
                row["asymptotic_maximum_equivalence_power"]
                for row in rows
                if row["source_groups"] == 38
            ),
            "source_groups_39_asymptotic_power": next(
                row["asymptotic_maximum_equivalence_power"]
                for row in rows
                if row["source_groups"] == 39
            ),
            "partition_requirements": partition_requirements,
        },
        "frontier_rows": rows,
        "reference_workload_sensitivity": {
            "selected_for_decision": False,
            "reference_only": "120 independent source groups and 5 transparent trials per eligible listener",
            "row": practical_reference,
            "device_class_workload": device_workload,
        },
        "decision": {
            "odaq_narrow_path_retained_for_development_plumbing": True,
            "odaq_narrow_path_can_assign_human_transparent_truth": False,
            "minimum_source_floor_identified": True,
            "listener_count_frozen": False,
            "source_manifest_frozen": False,
            "quality_exclusion_thresholds_frozen": False,
            "operational_design_frozen": False,
            "main_collection_authorized": False,
            "no_reference_work_eligible": False,
            "reason": "At least 39 independent source groups per analysis partition are required even with infinitely many listeners, while practical finite designs require far more listeners and source coverage. The accepted 16-reference ODAQ path therefore cannot establish transparent-lossy truth or independent transfer under the frozen equivalence model.",
            "next_score_blind_requirement": "Define a broader multi-provider permissively licensed source manifest with at least 39 independent source groups in every truth-bearing partition, then run balanced incomplete-block allocation and resource feasibility before freezing listener counts. Retain explicit abstention if that source and recruitment scale is not acceptable.",
        },
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = build_report()
    if report != expected:
        errors.append("report differs from deterministic replay")
        return errors
    if report["odaq_narrow_path"]["target_attainable_under_frozen_model"] is not False:
        errors.append("ODAQ feasibility boundary differs")
    if report["decision"]["listener_count_frozen"] is not False:
        errors.append("listener count must remain unfrozen")
    if report["decision"]["main_collection_authorized"] is not False:
        errors.append("collection must remain unauthorized")
    if report["decision"]["no_reference_work_eligible"] is not False:
        errors.append("no-reference work must remain ineligible")
    return errors


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit(f"refusing to replace output: {args.output}")
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_json_bytes(report))
    print(
        json.dumps(
            {
                "minimum_source_groups_per_partition": report["source_frontier"][
                    "minimum_source_groups_per_independent_partition_for_asymptotic_80_percent_equivalence_power"
                ],
                "odaq_asymptotic_maximum_equivalence_power": report[
                    "odaq_narrow_path"
                ]["asymptotic_maximum_equivalence_power"],
                "odaq_target_attainable": report["odaq_narrow_path"][
                    "target_attainable_under_frozen_model"
                ],
                "status": report["state"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
