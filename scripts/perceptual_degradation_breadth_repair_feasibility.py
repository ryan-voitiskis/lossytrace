#!/usr/bin/env python3
"""Evaluate source-breadth public-record capacity sensitivities."""

from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Any, NamedTuple


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/breadth-repair-provider-allocation-feasibility-plan.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-breadth-repair-provider-allocation-feasibility-20260814-001.json"
PLAN_ID = "perceptual-degradation-breadth-repair-provider-allocation-feasibility-20260814-001"
REPORT_ID = PLAN_ID


class State(NamedTuple):
    totals: tuple[int, ...]
    provider_counts: tuple[int, ...]
    capability_totals: tuple[int, ...]
    capability_provider_counts: tuple[int, ...]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bindings(plan: dict[str, Any], root: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for binding_id, binding in plan.get("bindings", {}).items():
        path = root / str(binding.get("path", ""))
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")
        else:
            result[binding_id] = load_json(path)
    return result


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != "score_blind_public_record_capacity_sensitivity_no_member_allocation":
        errors.append("plan state differs")
    bound = _bindings(plan, root, errors)
    observation = bound.get("breadth_repair_observation", {})
    stable_music_observation = bound.get("stable_music_observation", {})
    predecessor = bound.get("predecessor_plan", {})
    if observation.get("observation_id") != "perceptual-degradation-breadth-repair-public-metadata-observation-20260814-001":
        errors.append("observation identity differs")
    if predecessor.get("plan_id") != "perceptual-degradation-additional-permissive-provider-allocation-feasibility-20260814-001":
        errors.append("predecessor identity differs")
    if stable_music_observation.get("observation_id") != "perceptual-degradation-stable-music-provider-public-record-observation-20260814-001":
        errors.append("stable-music observation identity differs")

    access = observation.get("access_boundary", {})
    for key in (
        "official_public_collection_pages_read",
        "official_public_papers_or_structured_metadata_read",
        "mutable_release_pages_read",
    ):
        if access.get(key) is not True:
            errors.append(f"observation access fact must remain true: {key}")
    for key, value in access.items():
        if key not in {
            "official_public_collection_pages_read",
            "official_public_papers_or_structured_metadata_read",
            "mutable_release_pages_read",
        } and value is not False:
            errors.append(f"observation access boundary must remain false: {key}")

    policy = observation.get("screen_policy", {})
    if policy.get("allowed_dataset_licences") != ["CC BY 4.0", "CC0 1.0"]:
        errors.append("licence policy differs")
    required_true = {
        "immutable_or_versioned_record_required_before_exact_member_audit",
        "mutable_public_page_can_enter_labelled_arithmetic_sensitivity",
        "documented_direct_recording_or_artist_release_required",
    }
    for key, value in policy.items():
        if key == "allowed_dataset_licences":
            continue
        if value is not (key in required_true):
            errors.append(f"screen policy differs: {key}")

    immutable = observation.get("immutable_or_stable_record_candidates", [])
    provisional = observation.get("preservation_required_provisional_candidates", [])
    stable_music = stable_music_observation.get("stable_controlled_music_candidates", [])
    observed = {item.get("provider_id"): item for item in [*immutable, *provisional, *stable_music]}
    expected = {
        "english_children_speech": ("english_children_speech_200495", "immutable_or_stable", ["speech"], 11),
        "gesma": ("gesma_18315044", "immutable_or_stable", ["natural"], 18),
        "datastorre_acoustic_examples": ("datastorre_acoustic_index_examples_v1", "immutable_or_stable", ["natural"], 67),
        "icsi_meeting": ("icsi_meeting_corpus_public_record", "preservation_required_provisional", ["speech"], 53),
        "grumbles_pretty_bad_good": ("grumbles_a_pretty_bad_good_bandcamp", "preservation_required_provisional", ["music", "mastered_music"], 8),
        "stranger_self_imposed_exile": ("stranger_self_imposed_exile_bandcamp", "preservation_required_provisional", ["music", "mastered_music"], 20),
        "wangleline_honey": ("wangleline_honey_bandcamp", "preservation_required_provisional", ["music", "mastered_music"], 9),
        "vienna_4x22": ("vienna_4x22_v1", "immutable_or_stable", ["music", "controlled_performance_music"], 22),
        "raga_ornamentation_detection": ("raga_ornamentation_detection_17851882_v4", "immutable_or_stable", ["music", "controlled_performance_music"], 2),
    }
    new_providers = {item.get("provider_id"): item for item in plan.get("new_providers", [])}
    if set(observed) != set(expected) or set(new_providers) != set(expected):
        errors.append("new provider set differs")
    for provider_id, expected_values in expected.items():
        item = new_providers.get(provider_id, {})
        if (
            item.get("source_id"),
            item.get("record_status"),
            item.get("capabilities"),
            item.get("available_group_capacity"),
        ) != expected_values:
            errors.append(f"new provider binding differs: {provider_id}")
        source = observed.get(provider_id, {})
        observed_capacity = source.get("candidate_group_capacity", source.get("candidate_group_capacity_ceiling"))
        if item.get("source_id") != source.get("source_id") or item.get("available_group_capacity") != observed_capacity:
            errors.append(f"observation capacity differs: {provider_id}")
    datastorre = new_providers.get("datastorre_acoustic_examples", {})
    if datastorre.get("conservative_relationship_floor") != 8:
        errors.append("DataSTORRE conservative relationship floor differs")
    if observation.get("aggregate_observation") != {
        "new_immutable_or_stable_candidate_provider_count": 3,
        "new_provisional_provider_count": 4,
        "new_public_record_candidate_capacity_at_recording_ceiling": 186,
        "new_public_record_candidate_capacity_at_conservative_datastorre_floor": 127,
        "qualified_reference_group_count": 0,
        "allocated_group_count": 0,
    }:
        errors.append("observation aggregate differs")
    if stable_music_observation.get("aggregate_observation") != {
        "new_stable_controlled_music_candidate_provider_count": 2,
        "new_stable_controlled_music_candidate_group_capacity": 24,
        "new_stable_mastered_music_candidate_provider_count": 0,
        "new_stable_mastered_music_candidate_group_capacity": 0,
        "screened_not_added_provider_or_collection_count": 7,
        "qualified_reference_group_count": 0,
        "allocated_group_count": 0,
    }:
        errors.append("stable-music observation aggregate differs")
    for key, value in observation.get("observation_limits", {}).items():
        if value is not False:
            errors.append(f"observation limit must remain false: {key}")
    if {item.get("source_id") for item in observation.get("screened_not_added", [])} != {
        "freidi_20285754",
        "clarity_speech_corpus",
        "daps",
        "trustworthy_intent_corpus",
        "anechoic_high_fidelity_speech_corpus",
        "el_dorado_smoke_rings_bandcamp",
        "deep_russian_depression_bandcamp",
    }:
        errors.append("screened-not-added set differs")

    expected_authorization = {
        "aggregate_public_metadata_computation_authorized": True,
        "immutable_record_preservation_authorized": False,
        "exact_member_selection_authorized": False,
        "new_audio_acquisition_authorized": False,
        "retained_odaq_reference_read_authorized": False,
        "retained_reference_projection_authorized": False,
        "processed_condition_access_authorized": False,
        "target_perceptual_degradation_score_access_authorized": False,
        "perceptual_metric_execution_authorized": False,
        "human_collection_authorized": False,
        "sealed_evidence_access_authorized": False,
        "no_reference_training_authorized": False,
        "public_verdict_enabled": False,
    }
    if plan.get("authorization") != expected_authorization:
        errors.append("authorization boundary differs")
    if plan.get("partitions") != predecessor.get("partitions"):
        errors.append("partition order differs from predecessor")
    if plan.get("solver_policy") != {
        "predecessor_candidates_always_included": True,
        "provider_may_be_assigned_to_at_most_one_partition": True,
        "unused_provider_allowed": True,
        "capacity_is_capped_for_state_search_at_each_scenario_threshold": True,
        "full_provider_capacity_is_not_an_exact_member_selection": True,
        "recording_ceiling_is_not_independent_group_truth": True,
        "mutable_provisional_record_is_not_exact_member_audit_eligible": True,
        "scenario_record_status_filter_is_explicit": True,
        "deterministic_provider_order": "constraint_weight_then_capacity_descending_then_provider_id",
        "deterministic_assignment_order": "maximum_unmet_constraint_reduction_then_partition_order_then_unused",
    }:
        errors.append("solver policy differs")
    statuses = {"immutable_or_stable", "preservation_required_provisional"}
    scenario_ids: set[str] = set()
    known_providers = set(expected)
    known_capabilities = {
        capability
        for item in [*predecessor.get("providers", []), *plan.get("new_providers", [])]
        for capability in item.get("capabilities", [])
    }
    for scenario in plan.get("scenarios", []):
        scenario_id = scenario.get("scenario_id")
        if not isinstance(scenario_id, str) or scenario_id in scenario_ids:
            errors.append("scenario IDs must be unique strings")
        scenario_ids.add(scenario_id)
        included = scenario.get("included_new_record_statuses")
        if not isinstance(included, list) or not included or not set(included) <= statuses:
            errors.append(f"scenario record-status filter differs: {scenario_id}")
        for provider_id, capacity in scenario.get("capacity_overrides", {}).items():
            if provider_id not in known_providers or not isinstance(capacity, int) or capacity <= 0:
                errors.append(f"scenario capacity override differs: {scenario_id}")
        if scenario.get("minimum_groups_each_partition") not in {39, 120}:
            errors.append(f"scenario source floor differs: {scenario_id}")
        minimum_providers = scenario.get("minimum_providers_each_partition")
        if not isinstance(minimum_providers, int) or minimum_providers < 0:
            errors.append(f"scenario provider floor differs: {scenario_id}")
        for field in ("capability_minimums_by_partition", "capability_provider_minimums_by_partition"):
            for partition, requirements in scenario.get(field, {}).items():
                if partition not in plan.get("partitions", []):
                    errors.append(f"scenario partition differs: {scenario_id}")
                for capability, value in requirements.items():
                    if capability not in known_capabilities or value not in {2, 8}:
                        errors.append(f"scenario capability threshold differs: {scenario_id}")
        if scenario.get("expected_arithmetic_feasible") not in {True, False}:
            errors.append(f"scenario expectation differs: {scenario_id}")
        if not isinstance(scenario.get("reason_not_eligible"), str):
            errors.append(f"scenario reason missing: {scenario_id}")

    decision = plan.get("decision_boundary", {})
    if decision.get("selected_source_successor") is not None:
        errors.append("source successor was prematurely selected")
    if decision.get("selected_metric_successor") is not None:
        errors.append("metric successor was prematurely selected")
    for key, value in decision.items():
        if not key.startswith("selected_") and value is not False:
            errors.append(f"decision gate must remain false: {key}")
    for key, value in plan.get("claim_boundary", {}).items():
        if value is not False:
            errors.append(f"claim boundary must remain false: {key}")
    return errors


def _slots(partitions: list[str], requirements: dict[str, dict[str, int]]) -> tuple[list[tuple[int, str]], tuple[int, ...]]:
    slots: list[tuple[int, str]] = []
    thresholds: list[int] = []
    for partition_index, partition in enumerate(partitions):
        for capability in sorted(requirements.get(partition, {})):
            slots.append((partition_index, capability))
            thresholds.append(int(requirements[partition][capability]))
    return slots, tuple(thresholds)


def _scenario_providers(plan: dict[str, Any], scenario: dict[str, Any]) -> list[dict[str, Any]]:
    predecessor_path = ROOT / plan["bindings"]["predecessor_plan"]["path"]
    predecessor = load_json(predecessor_path)
    statuses = set(scenario["included_new_record_statuses"])
    providers = [dict(item) for item in predecessor["providers"]]
    providers.extend(dict(item) for item in plan["new_providers"] if item["record_status"] in statuses)
    overrides = scenario["capacity_overrides"]
    for provider in providers:
        if provider["provider_id"] in overrides:
            provider["available_group_capacity"] = overrides[provider["provider_id"]]
    constrained = {
        capability
        for field in (
            "capability_minimums_by_partition",
            "capability_provider_minimums_by_partition",
        )
        for requirements in scenario[field].values()
        for capability in requirements
    }
    return sorted(
        providers,
        key=lambda item: (
            -len(set(item["capabilities"]) & constrained),
            -int(item["available_group_capacity"]),
            item["provider_id"],
        ),
    )


def solve_scenario(plan: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    partitions = list(plan["partitions"])
    providers = _scenario_providers(plan, scenario)
    minimum_groups = int(scenario["minimum_groups_each_partition"])
    minimum_providers = int(scenario["minimum_providers_each_partition"])
    capability_slots, capability_thresholds = _slots(partitions, scenario["capability_minimums_by_partition"])
    provider_slots, provider_thresholds = _slots(partitions, scenario["capability_provider_minimums_by_partition"])
    initial = State((0,) * len(partitions), (0,) * len(partitions), (0,) * len(capability_slots), (0,) * len(provider_slots))
    target = State((minimum_groups,) * len(partitions), (minimum_providers,) * len(partitions), capability_thresholds, provider_thresholds)

    remaining_total = [0] * (len(providers) + 1)
    remaining_capability = [[0] * len(capability_slots) for _ in range(len(providers) + 1)]
    remaining_provider_capability = [[0] * len(provider_slots) for _ in range(len(providers) + 1)]
    for index in range(len(providers) - 1, -1, -1):
        provider = providers[index]
        capacity = int(provider["available_group_capacity"])
        capabilities = set(provider["capabilities"])
        remaining_total[index] = remaining_total[index + 1] + min(minimum_groups, capacity)
        remaining_capability[index] = list(remaining_capability[index + 1])
        remaining_provider_capability[index] = list(remaining_provider_capability[index + 1])
        for slot_index, (_, capability) in enumerate(capability_slots):
            if capability in capabilities:
                remaining_capability[index][slot_index] += min(capability_thresholds[slot_index], capacity)
        for slot_index, (_, capability) in enumerate(provider_slots):
            if capability in capabilities:
                remaining_provider_capability[index][slot_index] += 1

    def impossible(index: int, state: State) -> bool:
        if sum(minimum_groups - value for value in state.totals) > remaining_total[index]:
            return True
        if any(minimum_groups - value > remaining_total[index] for value in state.totals):
            return True
        if any(
            threshold - state.capability_totals[slot_index] > remaining_capability[index][slot_index]
            for slot_index, threshold in enumerate(capability_thresholds)
        ):
            return True
        if any(
            threshold - state.capability_provider_counts[slot_index] > remaining_provider_capability[index][slot_index]
            for slot_index, threshold in enumerate(provider_thresholds)
        ):
            return True
        return False

    def assigned(state: State, provider: dict[str, Any], partition_index: int) -> State:
        capacity = int(provider["available_group_capacity"])
        capabilities = set(provider["capabilities"])
        totals = list(state.totals)
        counts = list(state.provider_counts)
        capability_totals = list(state.capability_totals)
        capability_counts = list(state.capability_provider_counts)
        totals[partition_index] = min(minimum_groups, totals[partition_index] + capacity)
        counts[partition_index] = min(minimum_providers, counts[partition_index] + 1)
        for slot_index, (slot_partition, capability) in enumerate(capability_slots):
            if slot_partition == partition_index and capability in capabilities:
                capability_totals[slot_index] = min(capability_thresholds[slot_index], capability_totals[slot_index] + capacity)
        for slot_index, (slot_partition, capability) in enumerate(provider_slots):
            if slot_partition == partition_index and capability in capabilities:
                capability_counts[slot_index] = min(provider_thresholds[slot_index], capability_counts[slot_index] + 1)
        return State(tuple(totals), tuple(counts), tuple(capability_totals), tuple(capability_counts))

    def benefit(state: State, next_state: State, partition_index: int) -> tuple[int, int]:
        reduction = (
            sum(b - a for a, b in zip(state.totals, next_state.totals, strict=True))
            + minimum_groups * sum(b - a for a, b in zip(state.provider_counts, next_state.provider_counts, strict=True))
            + minimum_groups * sum(b - a for a, b in zip(state.capability_totals, next_state.capability_totals, strict=True))
            + minimum_groups * sum(b - a for a, b in zip(state.capability_provider_counts, next_state.capability_provider_counts, strict=True))
        )
        return (-reduction, partition_index)

    @lru_cache(maxsize=None)
    def search(index: int, state: State) -> tuple[int | None, ...] | None:
        if state == target:
            return (None,) * (len(providers) - index)
        if index == len(providers) or impossible(index, state):
            return None
        provider = providers[index]
        candidates = [(partition_index, assigned(state, provider, partition_index)) for partition_index in range(len(partitions))]
        candidates.sort(key=lambda item: benefit(state, item[1], item[0]))
        for partition_index, next_state in [*candidates, (None, state)]:
            suffix = search(index + 1, next_state)
            if suffix is not None:
                return (partition_index, *suffix)
        return None

    assignment = search(0, initial)
    witness: list[dict[str, Any]] = []
    capacity_by_partition = {partition: 0 for partition in partitions}
    if assignment is not None:
        for provider, partition_index in zip(providers, assignment, strict=True):
            if partition_index is None:
                continue
            partition = partitions[partition_index]
            capacity_by_partition[partition] += provider["available_group_capacity"]
            witness.append({
                "provider_id": provider["provider_id"],
                "partition": partition,
                "capabilities": provider["capabilities"],
                "available_group_capacity": provider["available_group_capacity"],
                "record_status": provider.get("record_status", "predecessor_bound_candidate"),
            })
    feasible = assignment is not None
    return {
        "scenario_id": scenario["scenario_id"],
        "arithmetic_feasible": feasible,
        "expected_arithmetic_feasible": scenario["expected_arithmetic_feasible"],
        "result_matches_frozen_expectation": feasible == scenario["expected_arithmetic_feasible"],
        "scientifically_eligible": False,
        "reason_not_eligible": scenario["reason_not_eligible"],
        "included_new_record_statuses": scenario["included_new_record_statuses"],
        "capacity_overrides": scenario["capacity_overrides"],
        "eligible_provider_count": len(providers),
        "eligible_available_group_capacity": sum(item["available_group_capacity"] for item in providers),
        "capacity_witness": witness,
        "available_capacity_by_partition": capacity_by_partition,
        "exact_member_selection_frozen": False,
    }


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH, implementation_path: Path = Path(__file__)) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    results = [solve_scenario(plan, scenario) for scenario in plan["scenarios"]]
    mismatches = [item["scenario_id"] for item in results if not item["result_matches_frozen_expectation"]]
    if mismatches:
        raise ValueError(f"scenario result differs from frozen expectation: {mismatches}")
    by_id = {item["scenario_id"]: item for item in results}
    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "score_blind_breadth_repair_capacity_sensitivity_complete_no_member_allocation",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(implementation_path),
        "audio_accessed": False,
        "exact_members_selected": False,
        "target_perceptual_degradation_scores_opened": False,
        "metrics_executed": False,
        "sealed_evidence_opened": False,
        "human_collection_authorized": False,
        "public_verdict_enabled": False,
        "scenario_results": results,
        "decision": {
            "public_record_pool_clears_three_domains_every_partition": by_id["public_record_three_domains_every_partition"]["arithmetic_feasible"],
            "stable_record_pool_clears_three_domains_every_partition": by_id["stable_record_three_domains_every_partition"]["arithmetic_feasible"],
            "public_record_pool_clears_mastered_music_every_partition": by_id["public_record_mastered_music_every_partition"]["arithmetic_feasible"],
            "stable_record_pool_clears_mastered_music_every_partition": by_id["stable_record_mastered_music_every_partition"]["arithmetic_feasible"],
            "public_record_pool_clears_two_mastered_providers_in_final": by_id["public_record_final_two_mastered_music_providers"]["arithmetic_feasible"],
            "recording_ceiling_clears_reference_120_each_partition": by_id["public_record_reference_120_recording_ceiling"]["arithmetic_feasible"],
            "conservative_relationship_floor_clears_reference_120_each_partition": by_id["public_record_reference_120_conservative_relationship_floor"]["arithmetic_feasible"],
            "stable_record_pool_clears_reference_120_each_partition": by_id["stable_record_reference_120_recording_ceiling"]["arithmetic_feasible"],
            "qualified_reference_group_count": 0,
            "allocated_group_count": 0,
            "source_successor_selected": False,
            "metric_successor_selected": False,
            "no_reference_work_eligible": False,
            "next_responsible_human_decision": "Choose whether to authorize bounded preservation and exact-member metadata audit of the identified records, narrow the primary-domain claim, or reject the current truth-source design; this does not authorize audio access.",
        },
        "claim_boundary": plan["claim_boundary"],
    }


def write_report(report: dict[str, Any], output: Path) -> None:
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_committed_report(plan_path: Path = PLAN_PATH, report_path: Path = REPORT_PATH) -> list[str]:
    plan = load_json(plan_path)
    errors = validate_plan(plan)
    if errors:
        return errors
    if not report_path.is_file():
        return ["committed report is missing"]
    if load_json(report_path) != build_report(plan, plan_path):
        return ["committed report differs from deterministic regeneration"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        write_report(build_report(load_json(args.plan), args.plan), args.output)
        print(f"wrote {REPORT_ID} to {args.output}")
        return 0
    errors = validate_committed_report(args.plan, REPORT_PATH)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated {PLAN_ID} and deterministic committed report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
