#!/usr/bin/env python3
"""Replay score-blind listening allocation at the 120-source frontier."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "listening-operational-resource-frontier-plan.json"
)
PLAN_ID = "perceptual-degradation-listening-operational-resource-frontier-20260814-001"
REPORT_ID = PLAN_ID

ALLOCATOR_PATH = ROOT / "scripts/perceptual_degradation_listening_allocation_v2.py"
SPEC = importlib.util.spec_from_file_location("listening_allocation_v2", ALLOCATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load v2 listening allocator")
ALLOCATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ALLOCATOR)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "score_blind_operational_resource_frontier_no_design_or_collection_authority"
    ):
        errors.append("plan state differs")
    expected_bindings = {
        "feasibility_plan",
        "feasibility_report",
        "allocator_v2",
        "allocator_v1",
        "manifest_v2_schema",
        "listening_protocol",
        "breadth_repair_report",
    }
    if set(plan.get("bindings", {})) != expected_bindings:
        errors.append("binding inventory differs")
    for binding_id, binding in plan.get("bindings", {}).items():
        path = root / str(binding.get("path", ""))
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")

    authorization = plan.get("authorization", {})
    if authorization.get("synthetic_symbolic_allocation_replay_authorized") is not True:
        errors.append("symbolic allocation replay must be authorized")
    for key, value in authorization.items():
        if key != "synthetic_symbolic_allocation_replay_authorized" and value is not False:
            errors.append(f"authorization boundary must remain false: {key}")

    grid = plan.get("design_grid", {})
    if (
        grid.get("independent_source_groups_per_partition") != 120
        or grid.get("truth_bearing_partitions")
        != ["development", "calibration", "transfer", "final_validation"]
        or grid.get("source_groups_may_cross_partitions") is not False
        or grid.get("device_class_count") != 1
        or grid.get("transparent_trials_per_eligible_listener") != [3, 5, 8, 15]
        or grid.get("maximum_mushra_trials_per_eligible_listener") != 6
        or grid.get("aggregate_condition_stratum_count_frozen") is not False
        or grid.get("listener_identity_reuse_across_partitions_frozen") is not False
        or grid.get("allocation_index_assigned_after_eligibility_frozen") is not False
        or grid.get("selected_design_option") is not None
        or grid.get("listener_count_frozen") is not False
        or grid.get("session_timing_qualified") is not False
    ):
        errors.append("design grid differs")
    fixture = plan.get("symbolic_fixture", {})
    for key in (
        "contains_audio",
        "contains_real_member_identity",
        "contains_condition_recipe",
        "is_study_stimulus_manifest",
    ):
        if fixture.get(key) is not False:
            errors.append(f"symbolic fixture boundary must remain false: {key}")
    balance = plan.get("balance_audit", {})
    if (
        balance.get("complete_trial_exposure_cycle_eligible_listener_slots")
        != 120
        or balance.get("maximum_trial_exposure_range") != 0
        or balance.get("maximum_candidate_position_range") != 1
        or balance.get(
            "trial_exposure_cycle_rounded_sensitivity_is_selected_policy"
        )
        is not False
        or balance.get("post_eligibility_allocation_indexing_is_selected_policy")
        is not False
        or balance.get("missingness_balance_is_proven") is not False
    ):
        errors.append("balance audit boundary differs")
    for key, value in plan.get("claim_boundary", {}).items():
        if value is not False:
            errors.append(f"claim boundary must remain false: {key}")
    return errors


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def _delivery(recipe_id: str) -> dict[str, Any]:
    return {
        "delivery_class": "generated_synthetic",
        "recipe_id": recipe_id,
        "recipe_id_sha256": hashlib.sha256(recipe_id.encode()).hexdigest(),
        "generator_source_sha256": sha256_file(Path(__file__)),
    }


def _stimulus(
    source_group_id: str,
    suffix: str,
    *,
    role: str,
    condition_class: str,
    recipe_id: str,
    controlled: bool,
) -> dict[str, Any]:
    return {
        "stimulus_id": f"stimulus-{source_group_id}-{suffix}",
        "source_group_id": source_group_id,
        "partition_group_id": f"partition-{source_group_id}",
        "partition": "development",
        "domain": "synthetic",
        "role": role,
        "condition_class": condition_class,
        "controlled_codec_intervention": controlled,
        "duration_seconds": 8,
        "active_seconds": 8,
        "sample_rate_hz": 48000,
        "channel_count": 2,
        "channel_map": "L_R",
        "delivery": _delivery(recipe_id),
        "licence_record_id": "licence-symbolic-no-audio-v1",
    }


def make_symbolic_manifest(plan: dict[str, Any]) -> dict[str, Any]:
    fixture = plan["symbolic_fixture"]
    source_count = plan["design_grid"]["independent_source_groups_per_partition"]
    stimuli: list[dict[str, Any]] = []
    trials: list[dict[str, Any]] = []
    for index in range(source_count):
        source_id = f"{fixture['source_group_prefix']}-{index:03d}"
        reference_recipe = f"symbolic-reference-{index:03d}-v1"
        reference = _stimulus(
            source_id,
            "reference",
            role="reference",
            condition_class="reference",
            recipe_id=reference_recipe,
            controlled=False,
        )
        subtle_hidden = _stimulus(
            source_id,
            "subtle-hidden-reference",
            role="hidden_reference",
            condition_class="reference",
            recipe_id=reference_recipe,
            controlled=False,
        )
        subtle_condition = _stimulus(
            source_id,
            "subtle-condition",
            role="condition",
            condition_class="transparency_candidate",
            recipe_id=f"symbolic-subtle-condition-{index:03d}-v1",
            controlled=True,
        )
        mushra_hidden = _stimulus(
            source_id,
            "mushra-hidden-reference",
            role="hidden_reference",
            condition_class="reference",
            recipe_id=reference_recipe,
            controlled=False,
        )
        mushra_condition = _stimulus(
            source_id,
            "mushra-condition",
            role="condition",
            condition_class="controlled_codec",
            recipe_id=f"symbolic-mushra-condition-{index:03d}-v1",
            controlled=True,
        )
        anchor_low = _stimulus(
            source_id,
            "mushra-anchor-low",
            role="anchor_low",
            condition_class="anchor",
            recipe_id=f"symbolic-anchor-low-{index:03d}-v1",
            controlled=False,
        )
        anchor_mid = _stimulus(
            source_id,
            "mushra-anchor-mid",
            role="anchor_mid",
            condition_class="anchor",
            recipe_id=f"symbolic-anchor-mid-{index:03d}-v1",
            controlled=False,
        )
        stimuli.extend(
            [
                reference,
                subtle_hidden,
                subtle_condition,
                mushra_hidden,
                mushra_condition,
                anchor_low,
                anchor_mid,
            ]
        )
        trials.extend(
            [
                {
                    "trial_id": f"trial-subtle-{index:03d}",
                    "method": "subtle",
                    "partition": "development",
                    "visible_reference_id": reference["stimulus_id"],
                    "candidate_ids": [
                        subtle_hidden["stimulus_id"],
                        subtle_condition["stimulus_id"],
                    ],
                },
                {
                    "trial_id": f"trial-mushra-{index:03d}",
                    "method": "mushra",
                    "partition": "development",
                    "visible_reference_id": reference["stimulus_id"],
                    "candidate_ids": [
                        mushra_hidden["stimulus_id"],
                        mushra_condition["stimulus_id"],
                        anchor_low["stimulus_id"],
                        anchor_mid["stimulus_id"],
                    ],
                },
            ]
        )
    return {
        "schema_version": 2,
        "manifest_id": fixture["manifest_id"],
        "state": "score_blind_preparation",
        "human_collection_authorized": False,
        "condition_recipes_visible_to_listener": False,
        "stimuli": stimuli,
        "trials": trials,
    }


def _balance(
    manifest: dict[str, Any],
    *,
    participant_count: int,
    allocation_seed: str,
    subtle_limit: int,
    mushra_limit: int,
) -> dict[str, Any]:
    trial_ids = [trial["trial_id"] for trial in manifest["trials"]]
    exposures = {trial_id: 0 for trial_id in trial_ids}
    positions: dict[str, dict[int, int]] = {}
    for allocation_index in range(participant_count):
        assignment = ALLOCATOR.allocate(
            manifest,
            f"symbolic-participant-{allocation_index:06d}",
            allocation_seed,
            allocation_index,
        )
        for block in assignment["blocks"]:
            limit = subtle_limit if block["method"] == "subtle" else mushra_limit
            for trial in block["trials"][:limit]:
                exposures[trial["trial_id"]] += 1
                for item in trial["candidate_positions"]:
                    counts = positions.setdefault(item["stimulus_id"], {})
                    position = item["position"]
                    counts[position] = counts.get(position, 0) + 1

    def method_exposures(method: str) -> list[int]:
        return [
            count
            for trial_id, count in exposures.items()
            if trial_id.startswith(f"trial-{method}-")
        ]

    def maximum_position_range(method: str, position_count: int) -> int:
        ranges = []
        marker = f"-{method}-"
        for stimulus_id, counts in positions.items():
            if marker not in stimulus_id:
                continue
            values = [counts.get(position, 0) for position in range(1, position_count + 1)]
            ranges.append(max(values) - min(values))
        return max(ranges, default=0)

    subtle = method_exposures("subtle")
    mushra = method_exposures("mushra")
    return {
        "participant_count": participant_count,
        "subtle_trial_exposure_min": min(subtle),
        "subtle_trial_exposure_max": max(subtle),
        "subtle_trial_exposure_range": max(subtle) - min(subtle),
        "mushra_trial_exposure_min": min(mushra),
        "mushra_trial_exposure_max": max(mushra),
        "mushra_trial_exposure_range": max(mushra) - min(mushra),
        "subtle_candidate_position_maximum_range": maximum_position_range(
            "subtle", 2
        ),
        "mushra_candidate_position_maximum_range": maximum_position_range(
            "mushra", 4
        ),
        "responses_included": False,
    }


def _balance_passes(balance: dict[str, Any], plan: dict[str, Any]) -> bool:
    audit = plan["balance_audit"]
    return (
        balance["subtle_trial_exposure_range"]
        <= audit["maximum_trial_exposure_range"]
        and balance["mushra_trial_exposure_range"]
        <= audit["maximum_trial_exposure_range"]
        and balance["subtle_candidate_position_maximum_range"]
        <= audit["maximum_candidate_position_range"]
        and balance["mushra_candidate_position_maximum_range"]
        <= audit["maximum_candidate_position_range"]
    )


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    feasibility = load_json(_bound(plan, "feasibility_report"))
    breadth = load_json(_bound(plan, "breadth_repair_report"))
    rows = {
        row["transparent_trials_per_eligible_listener"]: row
        for row in feasibility["frontier_rows"]
        if row["source_groups"] == 120
    }
    options = plan["design_grid"]["transparent_trials_per_eligible_listener"]
    if set(rows) != set(options):
        raise ValueError("120-source feasibility rows differ from design grid")
    stable_floor_ok = breadth.get("decision", {}).get(
        "stable_record_pool_at_conservative_relationship_floor_clears_reference_120_each_partition"
    )
    if stable_floor_ok is not True:
        raise ValueError("stable 120-source arithmetic is not feasible")

    manifest = make_symbolic_manifest(plan)
    manifest_errors = ALLOCATOR.validate_manifest(manifest)
    if manifest_errors:
        raise ValueError("; ".join(manifest_errors))
    usable_rate = load_json(_bound(plan, "feasibility_plan"))[
        "score_blind_stress_assumptions"
    ]["usable_trial_rate_after_missingness"]
    eligible_retention_rate = load_json(_bound(plan, "feasibility_plan"))[
        "score_blind_stress_assumptions"
    ]["eligible_listener_retention_rate"]
    partition_count = len(plan["design_grid"]["truth_bearing_partitions"])
    complete_cycle = plan["balance_audit"][
        "complete_trial_exposure_cycle_eligible_listener_slots"
    ]
    allocation_seed = plan["symbolic_fixture"]["allocation_seed"]
    frontier = []
    for subtle_trials in options:
        row = rows[subtle_trials]
        eligible = row["minimum_eligible_listeners"]
        enrolled = row["minimum_enrolled_listener_slots"]
        mushra_trials = min(
            subtle_trials,
            plan["design_grid"]["maximum_mushra_trials_per_eligible_listener"],
        )
        minimum_prefix_balance = _balance(
            manifest,
            participant_count=eligible,
            allocation_seed=allocation_seed,
            subtle_limit=subtle_trials,
            mushra_limit=mushra_trials,
        )
        cycle_rounded_eligible = math.ceil(eligible / complete_cycle) * complete_cycle
        cycle_rounded_enrolled = math.ceil(
            cycle_rounded_eligible / eligible_retention_rate
        )
        cycle_rounded_balance = _balance(
            manifest,
            participant_count=cycle_rounded_eligible,
            allocation_seed=allocation_seed,
            subtle_limit=subtle_trials,
            mushra_limit=mushra_trials,
        )
        scheduled_subtle = eligible * subtle_trials
        scheduled_mushra = eligible * mushra_trials
        frontier.append(
            {
                "option_id": f"sources120-subtle{subtle_trials}-mushra{mushra_trials}",
                "independent_source_groups_per_partition": 120,
                "transparent_trials_per_eligible_listener": subtle_trials,
                "mushra_trials_per_eligible_listener": mushra_trials,
                "total_scored_trials_per_eligible_listener": (
                    subtle_trials + mushra_trials
                ),
                "minimum_eligible_listener_slots_per_stratum_device_partition": eligible,
                "minimum_enrolled_listener_slots_per_stratum_device_partition": enrolled,
                "minimum_enrolled_listener_slots_for_four_partitions": (
                    enrolled * partition_count
                ),
                "minimum_enrolled_listener_slots_for_four_partitions_two_devices": (
                    enrolled * partition_count * 2
                ),
                "cycle_rounded_eligible_listener_slots_per_stratum_device_partition": (
                    cycle_rounded_eligible
                ),
                "cycle_rounded_enrolled_listener_slots_per_stratum_device_partition": (
                    cycle_rounded_enrolled
                ),
                "cycle_rounded_enrolled_listener_slots_for_four_partitions": (
                    cycle_rounded_enrolled * partition_count
                ),
                "cycle_rounded_enrolled_listener_slots_for_four_partitions_two_devices": (
                    cycle_rounded_enrolled * partition_count * 2
                ),
                "scheduled_subtle_judgments_per_partition": scheduled_subtle,
                "scheduled_mushra_judgments_per_partition": scheduled_mushra,
                "expected_usable_subtle_judgments_per_source": round(
                    scheduled_subtle * usable_rate / 120, 4
                ),
                "expected_usable_mushra_judgments_per_source": round(
                    scheduled_mushra * usable_rate / 120, 4
                ),
                "equivalence_power": row["equivalence_power"],
                "audible_power_at_truth_0_80": row["audible_power_at_truth_0_80"],
                "sdg_material_power_at_truth_minus_1_25": row[
                    "sdg_material_power_at_truth_minus_1_25"
                ],
                "mushra_material_power_at_truth_15": row[
                    "mushra_material_power_at_truth_15"
                ],
                "minimum_eligible_prefix_balance": minimum_prefix_balance,
                "minimum_eligible_prefix_balance_passes": _balance_passes(
                    minimum_prefix_balance, plan
                ),
                "cycle_rounded_eligible_prefix_balance": cycle_rounded_balance,
                "cycle_rounded_eligible_prefix_balance_passes": _balance_passes(
                    cycle_rounded_balance, plan
                ),
                "cycle_rounded_sensitivity_requires_post_eligibility_allocation_indexing": True,
                "cycle_rounded_sensitivity_selected": False,
                "session_timing_qualified": False,
                "selected": False,
            }
        )

    minimum_enrolled = min(
        item["minimum_enrolled_listener_slots_per_stratum_device_partition"]
        for item in frontier
    )
    minimum_cycle_rounded_enrolled = min(
        item[
            "cycle_rounded_enrolled_listener_slots_per_stratum_device_partition"
        ]
        for item in frontier
    )
    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "score_blind_resource_frontier_complete_no_operational_design_selected",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "symbolic_manifest_sha256": canonical_sha256(manifest),
        "symbolic_manifest_source_group_count": 120,
        "symbolic_manifest_stimulus_count": len(manifest["stimuli"]),
        "symbolic_manifest_trial_count": len(manifest["trials"]),
        "audio_accessed": False,
        "audio_generated": False,
        "listener_responses_opened": False,
        "human_collection_performed": False,
        "frontier": frontier,
        "decision": {
            "stable_source_arithmetic_supports_120_per_partition": True,
            "qualified_source_group_count": breadth["decision"][
                "qualified_reference_group_count"
            ],
            "allocated_source_group_count": breadth["decision"][
                "allocated_group_count"
            ],
            "minimum_enrolled_listener_slots_per_single_aggregate_stratum_device_partition": (
                minimum_enrolled
            ),
            "minimum_enrolled_listener_slots_for_four_partitions_at_protocol_caps": (
                minimum_enrolled * partition_count
            ),
            "minimum_cycle_rounded_enrolled_listener_slots_per_single_aggregate_"
            "stratum_device_partition": (
                minimum_cycle_rounded_enrolled
            ),
            "minimum_cycle_rounded_enrolled_listener_slots_for_four_partitions_at_protocol_caps": (
                minimum_cycle_rounded_enrolled * partition_count
            ),
            "all_raw_minimum_prefixes_pass_balance_audit": all(
                item["minimum_eligible_prefix_balance_passes"] for item in frontier
            ),
            "all_cycle_rounded_prefixes_pass_balance_audit": all(
                item["cycle_rounded_eligible_prefix_balance_passes"]
                for item in frontier
            ),
            "all_cycle_rounded_trial_exposures_pass_balance_audit": all(
                item["cycle_rounded_eligible_prefix_balance"][
                    "subtle_trial_exposure_range"
                ]
                == 0
                and item["cycle_rounded_eligible_prefix_balance"][
                    "mushra_trial_exposure_range"
                ]
                == 0
                for item in frontier
            ),
            "cycle_rounded_sensitivity_selected": False,
            "cycle_rounded_sensitivity_is_operationally_balanced": False,
            "allocation_policy_frozen": False,
            "allocator_successor_required_for_candidate_position_balance": True,
            "missingness_balance_proven": False,
            "aggregate_condition_stratum_count_frozen": False,
            "total_study_listener_slots_computable": False,
            "listener_count_frozen": False,
            "operational_design_selected": False,
            "session_timing_qualified": False,
            "human_collection_authorized": False,
            "recruitment_authorized": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "reason": (
                "The raw power minimum is not a balanced finite allocator "
                "prefix. At protocol caps it needs 352 enrollment slots for "
                "one aggregate stratum, device class and partition, or 1,408 "
                "across four partition slots. Rounding eligible assignments "
                "to complete 120-slot trial-exposure cycles raises that "
                "sensitivity to 372 and 1,488 respectively, conditional on "
                "post-eligibility indexing. It equalizes trial exposure but "
                "does not repair the existing allocator's repeated candidate-"
                "position imbalance, and missingness can disturb both. Total "
                "study workload remains unknown until condition strata, "
                "source members, session timing and participant reuse are "
                "frozen."
            ),
            "next_responsible_human_decision": (
                "Decide whether this lower-bound source and listener-session "
                "scale warrants an allocation-policy successor before "
                "authorizing exact-member source audit or collection."
            ),
        },
        "claim_boundary": plan["claim_boundary"],
    }


def write_report(report: dict[str, Any], output: Path) -> None:
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(load_json(args.plan), args.plan)
    write_report(report, args.output)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
