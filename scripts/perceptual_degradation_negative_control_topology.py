#!/usr/bin/env python3
"""Audit score-blind negative/control topology and workload sensitivity."""

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
    / "benchmarks/perceptual-degradation-v1/negative-control-topology-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research/toolchains/evidence/"
    "perceptual-degradation-negative-control-topology-20260814-001.json"
)


EXPECTED_AUTHORIZATION = {
    "score_blind_metadata_arithmetic_authorized": True,
    "source_member_selection_authorized": False,
    "condition_selection_authorized": False,
    "retained_audio_read_authorized": False,
    "provider_audio_acquisition_authorized": False,
    "stimulus_generation_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "human_collection_authorized": False,
    "recruitment_authorized": False,
    "response_or_outcome_access_authorized": False,
    "sealed_evidence_access_authorized": False,
    "no_reference_training_authorized": False,
    "public_verdict_enabled": False,
}

EXPECTED_AXES = {
    "transparent_truth_axis": ["transparent_lossy_encode"],
    "source_trait_axis": [
        "natural_bandwidth_limit",
        "quiet",
        "sparse",
        "tonal",
        "synthetic",
        "noisy",
        "clipped",
    ],
    "alignment_nuisance_axis": [
        "gain",
        "polarity",
        "integer_delay",
        "fractional_delay",
        "resampling",
        "bounded_clock_drift",
        "leading_trailing_silence",
    ],
    "human_truth_production_axis": [
        "equalization",
        "limiting",
        "stereo_width",
        "dither",
        "sample_rate_conversion",
    ],
}

EXPECTED_SCENARIOS = [
    ("codec-plus-required-production-families", 21),
    ("codec-plus-required-and-extra-families", 24),
    ("codec-plus-required-and-extra-recipes", 30),
    ("required-families-plus-alignment-human-truth", 28),
    ("extra-families-plus-alignment-human-truth", 31),
    ("extra-recipes-plus-alignment-human-truth", 37),
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if plan.get("plan_id") != (
        "perceptual-degradation-negative-control-topology-20260814-001"
    ):
        errors.append("plan_id differs")
    if plan.get("state") != (
        "score_blind_negative_control_topology_sensitivity_no_selection"
    ):
        errors.append("state differs")
    expected_bindings = {
        "research_contract",
        "research_plan",
        "source_condition_qualification",
        "additional_provider_plan",
        "factor_levels",
        "alignment_fixture_freeze",
        "alignment_topology_freeze",
        "audio_view_observation",
        "production_generation_plan",
        "production_generation_replay",
        "condition_workload_plan",
        "condition_workload_implementation",
        "condition_workload_report",
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
    topology = plan.get("negative_class_topology")
    if not isinstance(topology, dict) or set(topology) != set(EXPECTED_AXES):
        errors.append("negative-class topology axes differ")
    else:
        for axis_id, expected_ids in EXPECTED_AXES.items():
            rows = topology.get(axis_id)
            if not isinstance(rows, list):
                errors.append(f"topology axis must be a list: {axis_id}")
                continue
            observed = [
                value.get("class_id")
                for value in rows
                if isinstance(value, dict)
            ]
            if observed != expected_ids:
                errors.append(f"topology classes differ: {axis_id}")
    scenarios = plan.get("condition_breadth_scenarios", [])
    observed_scenarios = [
        (value.get("scenario_id"), value.get("strata_count"))
        for value in scenarios
        if isinstance(value, dict)
    ]
    if observed_scenarios != EXPECTED_SCENARIOS:
        errors.append("condition breadth scenarios differ")
    rules = plan.get("non_substitution_rules")
    if not isinstance(rules, list) or len(rules) != 10:
        errors.append("non-substitution rules differ")
    claims = plan.get("claim_boundary")
    if not isinstance(claims, dict) or not claims:
        errors.append("claim boundary missing")
    elif any(value is not False for value in claims.values()):
        errors.append("claim boundary must contain only false values")
    return errors


def _topology_rows(
    plan: dict[str, Any], axis_id: str
) -> dict[str, dict[str, Any]]:
    return {
        value["class_id"]: value
        for value in plan["negative_class_topology"][axis_id]
    }


def audit_required_inventory(
    plan: dict[str, Any], research_plan: dict[str, Any]
) -> dict[str, Any]:
    required = research_plan["required_negative_classes"]
    topology = plan["negative_class_topology"]
    axis_rows = {
        axis_id: [value["class_id"] for value in topology[axis_id]]
        for axis_id in EXPECTED_AXES
    }
    flattened = [
        class_id
        for axis_id in EXPECTED_AXES
        for class_id in axis_rows[axis_id]
    ]
    if required != flattened:
        raise ValueError("topology does not preserve required negative-class order")
    if len(flattened) != len(set(flattened)):
        raise ValueError("negative classes are not unique across topology axes")
    return {
        "required_class_count": len(required),
        "required_class_ids_sha256": hashlib.sha256(
            json.dumps(required, separators=(",", ":")).encode()
        ).hexdigest(),
        "axis_class_counts": {
            axis_id: len(class_ids) for axis_id, class_ids in axis_rows.items()
        },
        "all_required_classes_accounted_once": len(required) == len(set(flattened)),
        "source_traits_are_condition_strata": False,
        "scientific_coverage_complete": False,
    }


def audit_transparent_axis(
    plan: dict[str, Any], condition_report: dict[str, Any]
) -> dict[str, Any]:
    row = _topology_rows(plan, "transparent_truth_axis")[
        "transparent_lossy_encode"
    ]
    candidate = condition_report["candidate_codec_grid_audit"]
    if candidate["candidate_quality_cell_count"] != 16:
        raise ValueError("bound codec recipe grid differs")
    if candidate["candidate_selected_for_listening"]:
        raise ValueError("bound codec recipe grid is unexpectedly selected")
    return {
        "class_id": row["class_id"],
        "codec_recipe_candidate_count": candidate["candidate_quality_cell_count"],
        "codec_family_count": candidate["candidate_codec_family_count"],
        "encoder_count": candidate["candidate_encoder_count"],
        "candidate_record_present": True,
        "condition_selected": False,
        "human_transparency_truth_present": False,
        "nominal_setting_assigns_transparency": False,
    }


def audit_source_traits(
    plan: dict[str, Any],
    source_qualification: dict[str, Any],
    additional_provider_plan: dict[str, Any],
) -> dict[str, Any]:
    rows = _topology_rows(plan, "source_trait_axis")
    source_by_id = {
        value["source_id"]: value
        for value in source_qualification["source_candidates"]
    }
    provider_by_source = {
        value["source_id"]: value
        for value in additional_provider_plan["providers"]
    }
    expected = {
        "natural_bandwidth_limit": ("fsdd_v1_0_10", "natural_bandwidth_limit_hard_negative"),
        "sparse": ("tinysol_6_0", "sparse_tonal_hard_negative"),
        "tonal": ("tinysol_6_0", "sparse_tonal_hard_negative"),
        "noisy": ("sonyc_backgrounds_1_0_0", "noisy_natural_hard_negative"),
    }
    for class_id, (source_id, candidate_use) in expected.items():
        if source_id not in source_by_id:
            raise ValueError(f"source-trait candidate missing: {source_id}")
        if candidate_use not in source_by_id[source_id]["candidate_use"]:
            raise ValueError(f"source-trait role missing: {class_id}")
        if rows[class_id]["candidate_ids"] != [source_id]:
            raise ValueError(f"source-trait plan mapping differs: {class_id}")
    synthetic_id = "slakh2100_redux"
    if synthetic_id not in provider_by_source:
        raise ValueError("synthetic-source provider candidate missing")
    if "synthetic" not in provider_by_source[synthetic_id]["capabilities"]:
        raise ValueError("synthetic-source provider capability missing")
    if rows["synthetic"]["candidate_ids"] != [synthetic_id]:
        raise ValueError("synthetic source-trait mapping differs")
    trait_rows = []
    for class_id in EXPECTED_AXES["source_trait_axis"]:
        candidate_ids = rows[class_id]["candidate_ids"]
        trait_rows.append(
            {
                "class_id": class_id,
                "candidate_ids": candidate_ids,
                "candidate_record_present": bool(candidate_ids),
                "readiness": rows[class_id]["readiness"],
                "exact_members_frozen": False,
                "trait_qualified_on_exact_members": False,
                "partition_assignments_frozen": False,
                "independent_trait_contrast_present": False,
            }
        )
    present = [value for value in trait_rows if value["candidate_record_present"]]
    return {
        "class_count": len(trait_rows),
        "candidate_record_present_class_count": len(present),
        "missing_explicit_candidate_classes": [
            value["class_id"]
            for value in trait_rows
            if not value["candidate_record_present"]
        ],
        "unique_candidate_record_count": len(
            {candidate_id for value in present for candidate_id in value["candidate_ids"]}
        ),
        "joint_sparse_tonal_candidate": True,
        "rows": trait_rows,
        "source_trait_scientific_coverage_complete": False,
    }


def audit_alignment_axis(
    plan: dict[str, Any],
    factor_levels: dict[str, Any],
    alignment_freeze: dict[str, Any],
    topology_freeze: dict[str, Any],
    audio_view: dict[str, Any],
) -> dict[str, Any]:
    rows = _topology_rows(plan, "alignment_nuisance_axis")
    transforms = {
        value["transform_id"]: value
        for value in factor_levels["pcm_transform_levels"]
    }
    for transform_id in (
        "gain-minus6db-q31",
        "resample-roundtrip-32k",
        "prepend-digital-silence-500ms",
    ):
        if transform_id not in transforms:
            raise ValueError(f"alignment transform candidate missing: {transform_id}")
    claims = alignment_freeze["synthetic_fixture_claims"]
    required_claim_fragments = (
        "Integer delay, constant gain, and polarity",
        "quarter-sample",
        "Clock drift beyond 100 ppm",
        "Excessive edge trim",
    )
    for fragment in required_claim_fragments:
        if not any(fragment in claim for claim in claims):
            raise ValueError(f"alignment fixture claim missing: {fragment}")
    if topology_freeze["features_computed"]:
        raise ValueError("alignment topology freeze unexpectedly computed features")
    if audio_view["state"] != "score_free_decoder_and_resampler_replay_passed":
        raise ValueError("audio-view observation differs")
    partial = {
        "resampling",
        "bounded_clock_drift",
        "leading_trailing_silence",
    }
    result_rows = [
        {
            "class_id": class_id,
            "candidate_ids": rows[class_id]["candidate_ids"],
            "technical_representation_present": True,
            "readiness": rows[class_id]["readiness"],
            "known_incomplete_correction_or_fixture": class_id in partial,
            "human_truth_present": False,
            "listening_condition_role_frozen": False,
        }
        for class_id in EXPECTED_AXES["alignment_nuisance_axis"]
    ]
    return {
        "class_count": len(result_rows),
        "technical_representation_present_count": len(result_rows),
        "known_incomplete_correction_or_fixture_classes": sorted(partial),
        "rows": result_rows,
        "alignment_nuisance_role_complete": False,
    }


def audit_production_axis(
    plan: dict[str, Any],
    factor_levels: dict[str, Any],
    production_plan: dict[str, Any],
    production_replay: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = _topology_rows(plan, "human_truth_production_axis")
    production_by_id = {
        value["recipe_id"]: value
        for value in production_plan["production_control_recipes"]
    }
    replay_ids = {
        value["recipe_id"] for value in production_replay["production_cases"]
    }
    transforms = {
        value["transform_id"]: value
        for value in factor_levels["pcm_transform_levels"]
    }
    replayed_map = {
        "equalization": "production-high-shelf-minus6db-nyquist-fir3-v1",
        "limiting": "production-block-limiter-minus6dbfs-5ms-v1",
        "stereo_width": "production-stereo-width-half-mid-side-v1",
    }
    result_rows = []
    for class_id in EXPECTED_AXES["human_truth_production_axis"]:
        candidate_id = rows[class_id]["candidate_ids"][0]
        replayed = class_id in replayed_map
        if replayed:
            if candidate_id != replayed_map[class_id]:
                raise ValueError(f"production mapping differs: {class_id}")
            if candidate_id not in production_by_id or candidate_id not in replay_ids:
                raise ValueError(f"production replay missing: {class_id}")
        elif candidate_id not in transforms:
            raise ValueError(f"production transform candidate missing: {class_id}")
        result_rows.append(
            {
                "class_id": class_id,
                "candidate_ids": [candidate_id],
                "candidate_record_present": True,
                "synthetic_perceptual_recipe_replayed": replayed,
                "readiness": rows[class_id]["readiness"],
                "isolated_condition_ready": class_id != "dither" and replayed,
                "human_truth_present": False,
                "condition_selected": False,
            }
        )
    clipping_id = "production-hard-clip-minus6dbfs-v1"
    if clipping_id not in production_by_id or clipping_id not in replay_ids:
        raise ValueError("additional production-clipping replay missing")
    generation = production_plan["codec_generation_recipes"]
    replay_generation_ids = {
        value["recipe_id"] for value in production_replay["generation_cases"]
    }
    if len(generation) != 8 or {value["recipe_id"] for value in generation} != replay_generation_ids:
        raise ValueError("codec-generation replay inventory differs")
    production_audit = {
        "class_count": len(result_rows),
        "candidate_record_present_class_count": len(result_rows),
        "synthetic_perceptual_recipe_replayed_class_count": sum(
            value["synthetic_perceptual_recipe_replayed"] for value in result_rows
        ),
        "rows": result_rows,
        "human_truth_class_count": 0,
        "production_axis_scientific_coverage_complete": False,
    }
    additional_audit = {
        "production_clipping_recipe_count": 1,
        "production_clipping_substitutes_for_clipped_reference": False,
        "codec_generation_family_count": len(
            {value["family"] for value in generation}
        ),
        "codec_generation_recipe_count": len(generation),
        "synthetic_replay_complete": production_replay["decision"][
            "synthetic_recipe_replay_complete"
        ],
        "human_truth_present": False,
        "conditions_selected": False,
    }
    return production_audit, additional_audit


def _totals(enrolled: int, partitions: list[int], devices: list[int]) -> list[dict[str, int]]:
    return [
        {
            "partition_count": partition_count,
            "device_class_count": device_count,
            "enrolled_session_slots": enrolled * partition_count * device_count,
        }
        for partition_count in partitions
        for device_count in devices
    ]


def _workload_models(
    *,
    contract: dict[str, Any],
    trial_limits: dict[str, int],
    issued_prefix: int,
    strata_count: int,
) -> tuple[int, list[dict[str, Any]]]:
    no_packing = min(
        contract["maximum_subtle_trials_per_session"] // trial_limits["subtle"],
        contract["maximum_mushra_trials_per_session"] // trial_limits["mushra"],
    )
    optimistic = min(
        contract["maximum_subtle_trials_per_session"] // trial_limits["subtle"],
        contract["maximum_additional_conditions_per_mushra_trial"],
    )
    memberships = issued_prefix * strata_count
    models = []
    for model_id, theoretical_capacity in (
        ("dedicated_stratum", 1),
        ("exact_blocks_without_mushra_condition_packing", no_packing),
        ("optimistic_mushra_condition_packing", optimistic),
    ):
        capacity = min(theoretical_capacity, strata_count)
        eligible = math.ceil(memberships / capacity)
        enrolled = math.ceil(
            eligible / contract["eligible_listener_retention_rate"]
        )
        models.append(
            {
                "model_id": model_id,
                "theoretical_complete_strata_capacity_per_session": theoretical_capacity,
                "complete_strata_capacity_per_session": capacity,
                "eligible_session_slots_per_partition_device": eligible,
                "enrolled_session_slots_per_partition_device": enrolled,
                "totals": _totals(
                    enrolled,
                    contract["partition_counts"],
                    contract["device_class_counts"],
                ),
            }
        )
    return memberships, models


def workload_rows(
    plan: dict[str, Any],
    condition_plan: dict[str, Any],
    condition_report: dict[str, Any],
) -> list[dict[str, Any]]:
    base_rows = [
        value
        for value in condition_report["workload_rows"]
        if value["scenario_id"] == "aggregate-only"
    ]
    if len(base_rows) != 12:
        raise ValueError("bound aggregate workload inventory differs")
    contract = condition_plan["workload_contract"]
    rows = []
    for base in base_rows:
        for scenario in plan["condition_breadth_scenarios"]:
            memberships, models = _workload_models(
                contract=contract,
                trial_limits=base["trial_limits"],
                issued_prefix=base["issued_eligible_prefix_per_stratum"],
                strata_count=scenario["strata_count"],
            )
            rows.append(
                {
                    "retention_rate": base["retention_rate"],
                    "option_id": base["option_id"],
                    "trial_limits": base["trial_limits"],
                    "joint_reserve_multiplier": base["joint_reserve_multiplier"],
                    "issued_eligible_prefix_per_stratum": base[
                        "issued_eligible_prefix_per_stratum"
                    ],
                    "scenario_id": scenario["scenario_id"],
                    "strata_count": scenario["strata_count"],
                    "session_stratum_memberships_per_partition_device": memberships,
                    "models": models,
                    "condition_selection_performed": False,
                    "session_timing_evaluated": False,
                    "unique_people_evaluated": False,
                }
            )
    return rows


def arithmetic_minimums(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    retention_rates = sorted({value["retention_rate"] for value in rows})
    scenario_ids = sorted({value["scenario_id"] for value in rows})
    model_ids = sorted(
        {model["model_id"] for value in rows for model in value["models"]}
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
                            model["enrolled_session_slots_per_partition_device"],
                            candidate["option_id"],
                            candidate,
                            model,
                        )
                    )
                enrolled, option_id, candidate, model = min(ranked)
                four_partition = next(
                    value["enrolled_session_slots"]
                    for value in model["totals"]
                    if value["partition_count"] == 4
                    and value["device_class_count"] == 1
                )
                result.append(
                    {
                        "retention_rate": retention_rate,
                        "scenario_id": scenario_id,
                        "strata_count": candidate["strata_count"],
                        "model_id": model_id,
                        "arithmetic_minimum_option_id": option_id,
                        "enrolled_session_slots_per_partition_device": enrolled,
                        "enrolled_session_slots_four_partitions_one_device": four_partition,
                        "option_selected": False,
                        "session_timing_evaluated": False,
                    }
                )
    return result


def _reproduce_predecessor_minimums(
    condition_plan: dict[str, Any], condition_report: dict[str, Any]
) -> dict[str, Any]:
    base_rows = [
        value
        for value in condition_report["workload_rows"]
        if value["scenario_id"] == "aggregate-only"
    ]
    synthetic_plan = {
        "condition_breadth_scenarios": [
            {"scenario_id": "codec-grid-plus-control-families", "strata_count": 22},
            {"scenario_id": "codec-grid-plus-control-recipes", "strata_count": 28},
        ]
    }
    rows = []
    contract = condition_plan["workload_contract"]
    for base in base_rows:
        for scenario in synthetic_plan["condition_breadth_scenarios"]:
            memberships, models = _workload_models(
                contract=contract,
                trial_limits=base["trial_limits"],
                issued_prefix=base["issued_eligible_prefix_per_stratum"],
                strata_count=scenario["strata_count"],
            )
            rows.append(
                {
                    "retention_rate": base["retention_rate"],
                    "option_id": base["option_id"],
                    "scenario_id": scenario["scenario_id"],
                    "strata_count": scenario["strata_count"],
                    "session_stratum_memberships_per_partition_device": memberships,
                    "models": models,
                }
            )
    reproduced = arithmetic_minimums(rows)
    expected = [
        value
        for value in condition_report[
            "arithmetic_minimums_across_unselected_options"
        ]
        if value["scenario_id"]
        in {"codec-grid-plus-control-families", "codec-grid-plus-control-recipes"}
    ]
    key_fields = (
        "retention_rate",
        "scenario_id",
        "strata_count",
        "model_id",
        "arithmetic_minimum_option_id",
        "enrolled_session_slots_per_partition_device",
        "enrolled_session_slots_four_partitions_one_device",
        "option_selected",
        "session_timing_evaluated",
    )
    observed_projection = [
        {key: value[key] for key in key_fields} for value in reproduced
    ]
    expected_projection = [
        {key: value[key] for key in key_fields} for value in expected
    ]
    if observed_projection != expected_projection:
        raise ValueError("condition-workload arithmetic reproduction differs")
    return {
        "scenario_count": 2,
        "minimum_row_count": len(reproduced),
        "all_minimums_reproduced_exactly": True,
    }


def build_report(
    plan: dict[str, Any], plan_path: Path = PLAN_PATH
) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    research_plan = load_json(_bound(plan, "research_plan"))
    condition_plan = load_json(_bound(plan, "condition_workload_plan"))
    condition_report = load_json(_bound(plan, "condition_workload_report"))
    inventory = audit_required_inventory(plan, research_plan)
    transparent = audit_transparent_axis(plan, condition_report)
    source_traits = audit_source_traits(
        plan,
        load_json(_bound(plan, "source_condition_qualification")),
        load_json(_bound(plan, "additional_provider_plan")),
    )
    factor_levels = load_json(_bound(plan, "factor_levels"))
    alignment = audit_alignment_axis(
        plan,
        factor_levels,
        load_json(_bound(plan, "alignment_fixture_freeze")),
        load_json(_bound(plan, "alignment_topology_freeze")),
        load_json(_bound(plan, "audio_view_observation")),
    )
    production, additional = audit_production_axis(
        plan,
        factor_levels,
        load_json(_bound(plan, "production_generation_plan")),
        load_json(_bound(plan, "production_generation_replay")),
    )
    rows = workload_rows(plan, condition_plan, condition_report)
    minimums = arithmetic_minimums(rows)
    reproduction = _reproduce_predecessor_minimums(
        condition_plan, condition_report
    )
    represented = (
        1
        + source_traits["candidate_record_present_class_count"]
        + alignment["technical_representation_present_count"]
        + production["candidate_record_present_class_count"]
    )
    return {
        "schema_version": 1,
        "report_id": plan["plan_id"],
        "state": "score_blind_negative_control_topology_sensitivity_complete",
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "audio_accessed": False,
        "stimuli_generated": False,
        "perceptual_metric_executed": False,
        "responses_or_outcomes_accessed": False,
        "human_collection_performed": False,
        "public_verdict_enabled": False,
        "required_inventory_audit": inventory,
        "transparent_truth_axis_audit": transparent,
        "source_trait_axis_audit": source_traits,
        "alignment_nuisance_axis_audit": alignment,
        "human_truth_production_axis_audit": production,
        "additional_condition_inventory_audit": additional,
        "non_substitution_rules": plan["non_substitution_rules"],
        "workload_arithmetic_reproduction": reproduction,
        "condition_breadth_workload_rows": rows,
        "arithmetic_minimums_across_unselected_options": minimums,
        "decision": {
            "all_twenty_required_classes_accounted_once": inventory[
                "all_required_classes_accounted_once"
            ],
            "candidate_or_technical_representation_present_class_count": represented,
            "required_class_count": inventory["required_class_count"],
            "missing_explicit_source_trait_candidates": source_traits[
                "missing_explicit_candidate_classes"
            ],
            "prior_twenty_two_and_twenty_eight_strata_scenarios_are_claim_complete": False,
            "dither_isolated_condition_ready": False,
            "sample_rate_conversion_perceptual_condition_ready": False,
            "bounded_drift_correction_replay_complete": False,
            "paired_leading_trailing_silence_fixture_complete": False,
            "source_trait_exact_members_frozen": False,
            "negative_class_scientific_coverage_complete": False,
            "condition_breadth_selected": False,
            "human_collection_authorized": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "next_responsible_human_decision": (
                "Decide whether the corrected negative/control breadth and "
                "resource envelope justify exact source-trait and condition "
                "selection. Before that decision can support a pilot, add "
                "explicit quiet and naturally clipped candidates, isolate "
                "dither from bit depth, freeze a perceptual sample-rate "
                "conversion condition, and close bounded-drift plus paired "
                "leading/trailing-silence plumbing."
            ),
        },
        "claim_boundary": plan["claim_boundary"],
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != 1:
        errors.append("report schema_version differs")
    if report.get("state") != (
        "score_blind_negative_control_topology_sensitivity_complete"
    ):
        errors.append("report state differs")
    for key in (
        "audio_accessed",
        "stimuli_generated",
        "perceptual_metric_executed",
        "responses_or_outcomes_accessed",
        "human_collection_performed",
        "public_verdict_enabled",
    ):
        if report.get(key) is not False:
            errors.append(f"report {key} must be false")
    if len(report.get("condition_breadth_workload_rows", [])) != 72:
        errors.append("condition breadth workload row count differs")
    if len(report.get("arithmetic_minimums_across_unselected_options", [])) != 54:
        errors.append("arithmetic minimum row count differs")
    decision = report.get("decision", {})
    if (
        decision.get(
            "candidate_or_technical_representation_present_class_count"
        )
        != 18
    ):
        errors.append("candidate-or-representation class count differs")
    for key in (
        "prior_twenty_two_and_twenty_eight_strata_scenarios_are_claim_complete",
        "dither_isolated_condition_ready",
        "sample_rate_conversion_perceptual_condition_ready",
        "bounded_drift_correction_replay_complete",
        "paired_leading_trailing_silence_fixture_complete",
        "source_trait_exact_members_frozen",
        "negative_class_scientific_coverage_complete",
        "condition_breadth_selected",
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
    minimum = next(
        value
        for value in report["arithmetic_minimums_across_unselected_options"]
        if value["retention_rate"] == 0.90
        and value["scenario_id"] == "codec-plus-required-and-extra-families"
        and value["model_id"] == "optimistic_mushra_condition_packing"
    )
    print(
        json.dumps(
            {
                "report_id": report["report_id"],
                "required_negative_classes": report["required_inventory_audit"][
                    "required_class_count"
                ],
                "candidate_or_technical_representation_present_classes": report[
                    "decision"
                ][
                    "candidate_or_technical_representation_present_class_count"
                ],
                "corrected_family_optimistic_four_partition_slots_at_90_percent": minimum[
                    "enrolled_session_slots_four_partitions_one_device"
                ],
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
