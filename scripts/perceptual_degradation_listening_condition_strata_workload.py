#!/usr/bin/env python3
"""Score-blind condition-strata listening workload sensitivity."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/"
    "listening-condition-strata-workload-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-listening-condition-strata-workload-"
    "20260814-001.json"
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


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


EXPECTED_AUTHORIZATION = {
    "score_blind_metadata_arithmetic_authorized": True,
    "condition_selection_authorized": False,
    "source_member_selection_authorized": False,
    "retained_audio_read_authorized": False,
    "new_audio_acquisition_authorized": False,
    "stimulus_generation_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "human_collection_authorized": False,
    "recruitment_authorized": False,
    "response_or_outcome_access_authorized": False,
    "sealed_evidence_access_authorized": False,
    "no_reference_training_authorized": False,
    "public_verdict_enabled": False,
}

EXPECTED_SCENARIOS = [
    ("aggregate-only", 1),
    ("codec-family-only", 4),
    ("codec-encoder-cells", 8),
    ("codec-recipe-grid", 16),
    ("codec-grid-plus-control-families", 22),
    ("codec-grid-plus-control-recipes", 28),
]

EXPECTED_WORKLOAD = {
    "retention_rates": [0.85, 0.90, 0.95],
    "partition_counts": [1, 4],
    "device_class_counts": [1, 2],
    "eligible_listener_retention_rate": 0.646,
    "maximum_subtle_trials_per_session": 15,
    "maximum_mushra_trials_per_session": 6,
    "maximum_additional_conditions_per_mushra_trial": 8,
    "dedicated_stratum_model": (
        "multiply_retained_design_eligible_prefix_before_enrollment_rounding"
    ),
    "exact_block_no_mushra_packing_model": (
        "a_session_may_carry_only_complete_per_stratum_subtle_and_mushra_blocks"
    ),
    "optimistic_mushra_packing_model": (
        "mushra_conditions_share_source_trials_and_only_the_subtle_block_"
        "limits_complete_strata_per_session"
    ),
    "unique_people_from_session_slots": (
        "not_identifiable_without_reuse_fatigue_and_correlation_policy"
    ),
}


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if plan.get("plan_id") != (
        "perceptual-degradation-listening-condition-strata-workload-"
        "20260814-001"
    ):
        errors.append("plan_id differs")
    if plan.get("state") != (
        "score_blind_condition_strata_workload_sensitivity_no_design_selection"
    ):
        errors.append("state differs")
    expected_bindings = {
        "research_contract",
        "listening_protocol",
        "toolchain_bindings",
        "toolchain_observation",
        "production_generation_control_plan",
        "production_generation_replay",
        "feasibility_plan",
        "feasibility_report",
        "retained_design_plan",
        "retained_design_report",
    }
    bindings = plan.get("bindings")
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        errors.append("bindings differ")
    else:
        for binding_id, binding in bindings.items():
            if not isinstance(binding, dict):
                errors.append(f"binding {binding_id} must be an object")
                continue
            relative = binding.get("path")
            if not isinstance(relative, str) or Path(relative).is_absolute():
                errors.append(f"binding {binding_id} path must be relative")
                continue
            path = root / relative
            if not path.is_file():
                errors.append(f"binding {binding_id} path is missing")
            elif sha256_file(path) != binding.get("sha256"):
                errors.append(f"binding {binding_id} sha256 differs")
    if plan.get("authorization") != EXPECTED_AUTHORIZATION:
        errors.append("authorization differs")
    scenarios = plan.get("strata_scenarios", [])
    observed_scenarios = [
        (value.get("scenario_id"), value.get("strata_count"))
        for value in scenarios
        if isinstance(value, dict)
    ]
    if observed_scenarios != EXPECTED_SCENARIOS:
        errors.append("strata scenarios differ")
    if plan.get("workload_contract") != EXPECTED_WORKLOAD:
        errors.append("workload contract differs")
    grid = plan.get("candidate_codec_grid", {})
    if grid.get("state") != (
        "arithmetic_candidate_only_not_selected_or_truth_bearing"
    ):
        errors.append("candidate codec grid state differs")
    if grid.get("channel_treatment_id") != "stereo":
        errors.append("candidate codec grid channel differs")
    if set(grid.get("codec_families", {})) != {
        "mp3",
        "aac_lc",
        "opus",
        "vorbis",
    }:
        errors.append("candidate codec families differ")
    claims = plan.get("claim_boundary")
    if not isinstance(claims, dict) or not claims:
        errors.append("claim boundary missing")
    elif any(value is not False for value in claims.values()):
        errors.append("claim boundary must contain only false values")
    return errors


def audit_candidate_grid(
    plan: dict[str, Any], toolchain: dict[str, Any]
) -> dict[str, Any]:
    settings = toolchain["expanded_encoder_settings"]
    by_id = {value["expanded_setting_id"]: value for value in settings}
    if len(by_id) != len(settings):
        raise ValueError("toolchain setting IDs are not unique")
    selected_ids: list[str] = []
    codec_rows = []
    for codec_family, codec_spec in plan["candidate_codec_grid"][
        "codec_families"
    ].items():
        expected_quality = codec_spec["quality_levels"]
        encoders = codec_spec["encoder_settings"]
        if len(encoders) != 2:
            raise ValueError(f"candidate codec requires two encoders: {codec_family}")
        encoder_rows = []
        for encoder_id, setting_ids in encoders.items():
            if len(setting_ids) != 2:
                raise ValueError(
                    f"candidate encoder requires two settings: {encoder_id}"
                )
            rows = []
            for setting_id in setting_ids:
                if setting_id not in by_id:
                    raise ValueError(f"candidate setting missing: {setting_id}")
                setting = by_id[setting_id]
                if setting["codec_family"] != codec_family:
                    raise ValueError(f"candidate codec differs: {setting_id}")
                if setting["encoder_id"] != encoder_id:
                    raise ValueError(f"candidate encoder differs: {setting_id}")
                if setting["channel_treatment_id"] != "stereo":
                    raise ValueError(f"candidate is not stereo: {setting_id}")
                rows.append(setting)
                selected_ids.append(setting_id)
            quality = [value["bitrate_or_quality"] for value in rows]
            if quality != expected_quality:
                raise ValueError(f"candidate quality grid differs: {encoder_id}")
            encoder_rows.append(
                {
                    "encoder_id": encoder_id,
                    "evidence_partitions": sorted(
                        {value["evidence_partition"] for value in rows}
                    ),
                    "quality_levels": quality,
                    "setting_count": len(rows),
                    "setting_ids_sha256": canonical_sha256(setting_ids),
                }
            )
        codec_rows.append(
            {
                "codec_family": codec_family,
                "quality_levels": expected_quality,
                "encoder_count": len(encoders),
                "setting_count": sum(
                    value["setting_count"] for value in encoder_rows
                ),
                "encoders": encoder_rows,
            }
        )
    if len(selected_ids) != 16 or len(set(selected_ids)) != 16:
        raise ValueError("candidate codec recipe grid must contain 16 settings")
    inventory_codec_families = sorted(
        {value["codec_family"] for value in settings}
    )
    inventory_encoder_ids = sorted({value["encoder_id"] for value in settings})
    return {
        "toolchain_expanded_setting_count": len(settings),
        "toolchain_stereo_setting_count": sum(
            value["channel_treatment_id"] == "stereo" for value in settings
        ),
        "toolchain_codec_family_count": len(inventory_codec_families),
        "toolchain_codec_families": inventory_codec_families,
        "toolchain_encoder_count": len(inventory_encoder_ids),
        "candidate_codec_family_count": len(codec_rows),
        "candidate_encoder_count": sum(
            value["encoder_count"] for value in codec_rows
        ),
        "candidate_quality_cell_count": len(selected_ids),
        "candidate_setting_ids_sha256": canonical_sha256(sorted(selected_ids)),
        "codec_rows": codec_rows,
        "candidate_selected_for_listening": False,
        "candidate_perceptual_truth_assigned": False,
    }


def audit_controls(
    control_plan: dict[str, Any], replay: dict[str, Any]
) -> dict[str, Any]:
    production = control_plan["production_control_recipes"]
    generation = control_plan["codec_generation_recipes"]
    production_families = sorted({value["family"] for value in production})
    generation_families = sorted({value["family"] for value in generation})
    if len(production) != 4 or len(generation) != 8:
        raise ValueError("bound control recipe counts differ")
    summary = replay["summary"]
    if (
        summary["production_case_count"] != len(production)
        or summary["generation_case_count"] != len(generation)
        or summary["perceptual_truth_included"]
    ):
        raise ValueError("bound synthetic control replay differs")
    return {
        "production_recipe_count": len(production),
        "production_family_count": len(production_families),
        "production_families": production_families,
        "generation_recipe_count": len(generation),
        "generation_family_count": len(generation_families),
        "generation_families": generation_families,
        "control_family_count": len(production_families)
        + len(generation_families),
        "control_recipe_count": len(production) + len(generation),
        "synthetic_replay_passed": replay["decision"][
            "synthetic_recipe_replay_complete"
        ],
        "actual_stimuli_generated": False,
        "perceptual_truth_assigned": False,
    }


def _minimum_multiplier(
    report: dict[str, Any], option_id: str, retention_rate: float
) -> float:
    option = report["minimum_reserve_multiplier_by_option_kind_and_retention"][
        option_id
    ]
    key = f"retention_{retention_rate:.2f}"
    session = option["hash_mcar_session"][key]
    trial = option["hash_mcar_trial"][key]
    if session is None or trial is None:
        raise ValueError(f"bounded reserve missing: {option_id} {key}")
    return max(session, trial)


def _reserve_row(
    report: dict[str, Any], option_id: str, multiplier: float
) -> dict[str, Any]:
    option = next(
        value for value in report["option_results"] if value["option_id"] == option_id
    )
    return next(
        value
        for value in option["reserve_rows"]
        if value["issued_reserve_multiplier"] == multiplier
    )


def _totals(
    enrolled_per_partition_device: int,
    partition_counts: list[int],
    device_counts: list[int],
) -> list[dict[str, int]]:
    return [
        {
            "partition_count": partition_count,
            "device_class_count": device_count,
            "enrolled_session_slots": (
                enrolled_per_partition_device * partition_count * device_count
            ),
        }
        for partition_count in partition_counts
        for device_count in device_counts
    ]


def workload_row(
    *,
    plan: dict[str, Any],
    option: dict[str, Any],
    scenario: dict[str, Any],
    retention_rate: float,
    reserve_multiplier: float,
    issued_prefix: int,
) -> dict[str, Any]:
    contract = plan["workload_contract"]
    strata_count = scenario["strata_count"]
    subtle_limit = option["trial_limits"]["subtle"]
    mushra_limit = option["trial_limits"]["mushra"]
    no_mushra_packing_capacity = min(
        contract["maximum_subtle_trials_per_session"] // subtle_limit,
        contract["maximum_mushra_trials_per_session"] // mushra_limit,
    )
    optimistic_capacity = min(
        contract["maximum_subtle_trials_per_session"] // subtle_limit,
        contract["maximum_additional_conditions_per_mushra_trial"],
    )
    if min(no_mushra_packing_capacity, optimistic_capacity) <= 0:
        raise ValueError("session capacity is zero")
    session_stratum_memberships = issued_prefix * strata_count
    models = []
    for model_id, theoretical_capacity in (
        ("dedicated_stratum", 1),
        ("exact_blocks_without_mushra_condition_packing", no_mushra_packing_capacity),
        ("optimistic_mushra_condition_packing", optimistic_capacity),
    ):
        capacity = min(theoretical_capacity, strata_count)
        eligible_sessions = math.ceil(session_stratum_memberships / capacity)
        enrolled_sessions = math.ceil(
            eligible_sessions / contract["eligible_listener_retention_rate"]
        )
        models.append(
            {
                "model_id": model_id,
                "theoretical_complete_strata_capacity_per_session": (
                    theoretical_capacity
                ),
                "complete_strata_capacity_per_session": capacity,
                "eligible_session_slots_per_partition_device": eligible_sessions,
                "enrolled_session_slots_per_partition_device": enrolled_sessions,
                "totals": _totals(
                    enrolled_sessions,
                    contract["partition_counts"],
                    contract["device_class_counts"],
                ),
            }
        )
    return {
        "option_id": option["option_id"],
        "trial_limits": option["trial_limits"],
        "scenario_id": scenario["scenario_id"],
        "strata_count": strata_count,
        "retention_rate": retention_rate,
        "joint_reserve_multiplier": reserve_multiplier,
        "issued_eligible_prefix_per_stratum": issued_prefix,
        "session_stratum_memberships_per_partition_device": (
            session_stratum_memberships
        ),
        "models": models,
        "session_timing_evaluated": False,
        "unique_people_evaluated": False,
        "allocator_or_player_packing_evaluated": False,
    }


def _minimums(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    minimums = []
    retention_rates = sorted({value["retention_rate"] for value in rows})
    scenario_ids = sorted({value["scenario_id"] for value in rows})
    model_ids = sorted(
        {
            model["model_id"]
            for value in rows
            for model in value["models"]
        }
    )
    for retention_rate in retention_rates:
        for scenario_id in scenario_ids:
            candidates = [
                value
                for value in rows
                if value["retention_rate"] == retention_rate
                and value["scenario_id"] == scenario_id
            ]
            for model_id in model_ids:
                ranked = []
                for candidate in candidates:
                    model = next(
                        value
                        for value in candidate["models"]
                        if value["model_id"] == model_id
                    )
                    ranked.append(
                        (
                            model[
                                "enrolled_session_slots_per_partition_device"
                            ],
                            candidate["option_id"],
                            candidate,
                            model,
                        )
                    )
                enrolled, option_id, candidate, model = min(ranked)
                four_partition_one_device = next(
                    value["enrolled_session_slots"]
                    for value in model["totals"]
                    if value["partition_count"] == 4
                    and value["device_class_count"] == 1
                )
                minimums.append(
                    {
                        "retention_rate": retention_rate,
                        "scenario_id": scenario_id,
                        "strata_count": candidate["strata_count"],
                        "model_id": model_id,
                        "arithmetic_minimum_option_id": option_id,
                        "enrolled_session_slots_per_partition_device": enrolled,
                        "enrolled_session_slots_four_partitions_one_device": (
                            four_partition_one_device
                        ),
                        "option_selected": False,
                        "session_timing_evaluated": False,
                    }
                )
    return minimums


def build_report(
    plan: dict[str, Any], plan_path: Path = PLAN_PATH
) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    toolchain = load_json(_bound(plan, "toolchain_bindings"))
    toolchain_observation = load_json(_bound(plan, "toolchain_observation"))
    if (
        toolchain_observation["summary"]["expanded_setting_count"] != 46
        or not toolchain_observation["summary"][
            "all_encoder_bitstreams_deterministic"
        ]
    ):
        raise ValueError("bound toolchain observation differs")
    candidate_grid = audit_candidate_grid(plan, toolchain)
    controls = audit_controls(
        load_json(_bound(plan, "production_generation_control_plan")),
        load_json(_bound(plan, "production_generation_replay")),
    )
    feasibility_plan = load_json(_bound(plan, "feasibility_plan"))
    if feasibility_plan["score_blind_stress_assumptions"][
        "eligible_listener_retention_rate"
    ] != plan["workload_contract"]["eligible_listener_retention_rate"]:
        raise ValueError("eligible-listener retention differs")
    retained_report = load_json(_bound(plan, "retained_design_report"))
    if not retained_report["decision"][
        "all_mcar_sensitivity_cells_have_bounded_reserve_option"
    ]:
        raise ValueError("retained-design reserve frontier is not bounded")
    options = [
        {
            "option_id": value["option_id"],
            "trial_limits": value["trial_limits"],
        }
        for value in retained_report["option_results"]
    ]
    rows = []
    for retention_rate in plan["workload_contract"]["retention_rates"]:
        for option in options:
            multiplier = _minimum_multiplier(
                retained_report, option["option_id"], retention_rate
            )
            reserve = _reserve_row(
                retained_report, option["option_id"], multiplier
            )
            for scenario in plan["strata_scenarios"]:
                rows.append(
                    workload_row(
                        plan=plan,
                        option=option,
                        scenario=scenario,
                        retention_rate=retention_rate,
                        reserve_multiplier=multiplier,
                        issued_prefix=reserve["issued_eligible_prefix"],
                    )
                )
    minimums = _minimums(rows)
    return {
        "schema_version": 1,
        "report_id": plan["plan_id"],
        "state": "score_blind_condition_strata_workload_sensitivity_complete",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "audio_accessed": False,
        "condition_audio_generated": False,
        "perceptual_truth_assigned": False,
        "responses_or_outcomes_accessed": False,
        "human_collection_performed": False,
        "public_verdict_enabled": False,
        "candidate_codec_grid_audit": candidate_grid,
        "control_inventory_audit": controls,
        "workload_rows": rows,
        "arithmetic_minimums_across_unselected_options": minimums,
        "decision": {
            "comparable_sixteen_recipe_codec_grid_available": (
                candidate_grid["candidate_quality_cell_count"] == 16
            ),
            "six_control_families_available": (
                controls["control_family_count"] == 6
            ),
            "twelve_control_recipes_available": (
                controls["control_recipe_count"] == 12
            ),
            "historical_toolchain_inventory_selected_for_listening": False,
            "candidate_codec_grid_selected": False,
            "condition_strata_count_frozen": False,
            "condition_perceptual_roles_frozen": False,
            "mushra_condition_packing_proven": False,
            "session_timing_proven": False,
            "unique_listener_count_identified": False,
            "partition_or_device_policy_selected": False,
            "human_collection_authorized": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "next_responsible_human_decision": (
                "Decide whether the condition-specific session-slot envelope "
                "is acceptable enough to justify exact codec, encoder, quality "
                "and control selection plus a score-blind pilot. The optimistic "
                "packing rows require a new multi-condition allocator, player, "
                "timing and covariance audit and are not operational evidence."
            ),
        },
        "claim_boundary": plan["claim_boundary"],
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != 1:
        errors.append("report schema_version differs")
    if report.get("state") != (
        "score_blind_condition_strata_workload_sensitivity_complete"
    ):
        errors.append("report state differs")
    for key in (
        "audio_accessed",
        "condition_audio_generated",
        "perceptual_truth_assigned",
        "responses_or_outcomes_accessed",
        "human_collection_performed",
        "public_verdict_enabled",
    ):
        if report.get(key) is not False:
            errors.append(f"report {key} must be false")
    decision = report.get("decision", {})
    for key in (
        "historical_toolchain_inventory_selected_for_listening",
        "candidate_codec_grid_selected",
        "condition_strata_count_frozen",
        "condition_perceptual_roles_frozen",
        "mushra_condition_packing_proven",
        "session_timing_proven",
        "unique_listener_count_identified",
        "partition_or_device_policy_selected",
        "human_collection_authorized",
        "no_reference_work_eligible",
        "public_verdict_enabled",
    ):
        if decision.get(key) is not False:
            errors.append(f"decision {key} must be false")
    claims = report.get("claim_boundary")
    if not isinstance(claims, dict) or any(
        value is not False for value in claims.values()
    ):
        errors.append("report claim boundary must remain false")
    if len(report.get("workload_rows", [])) != 72:
        errors.append("workload row count differs")
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
    codec_recipe_minimum = next(
        value
        for value in report["arithmetic_minimums_across_unselected_options"]
        if value["retention_rate"] == 0.90
        and value["scenario_id"] == "codec-recipe-grid"
        and value["model_id"] == "optimistic_mushra_condition_packing"
    )
    print(
        json.dumps(
            {
                "report_id": report["report_id"],
                "candidate_codec_recipes": report[
                    "candidate_codec_grid_audit"
                ]["candidate_quality_cell_count"],
                "optimistic_four_partition_slots_at_90_percent": (
                    codec_recipe_minimum[
                        "enrolled_session_slots_four_partitions_one_device"
                    ]
                ),
                "collection_authorized": report["decision"][
                    "human_collection_authorized"
                ],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
