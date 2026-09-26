#!/usr/bin/env python3
"""Evaluate additional score-blind provider-capacity sensitivities."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, NamedTuple


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "additional-permissive-provider-allocation-feasibility-plan.json"
)
REPORT_PATH = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-additional-permissive-provider-allocation-feasibility-20260814-001.json"
)
PLAN_ID = (
    "perceptual-degradation-additional-permissive-provider-allocation-"
    "feasibility-20260814-001"
)
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


def _binding_objects(
    plan: dict[str, Any], root: Path, errors: list[str]
) -> dict[str, dict[str, Any]]:
    bound: dict[str, dict[str, Any]] = {}
    for binding_id, binding in plan.get("bindings", {}).items():
        path = root / str(binding.get("path", ""))
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")
        elif path.suffix == ".json":
            bound[binding_id] = load_json(path)
    return bound


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "score_blind_aggregate_capacity_sensitivity_no_member_allocation"
    ):
        errors.append("plan state differs")

    bound = _binding_objects(plan, root, errors)
    observation = bound.get("additional_provider_observation", {})
    if observation.get("observation_id") != (
        "perceptual-degradation-additional-permissive-provider-public-"
        "metadata-observation-20260814-001"
    ):
        errors.append("additional-provider observation identity differs")
    observation_access = observation.get("access_boundary", {})
    for key in (
        "official_public_dataset_pages_read",
        "official_public_papers_and_readmes_read",
        "small_public_metadata_responses_streamed_or_read_ephemerally",
        "unrelated_urmp_synchronization_study_summary_incidentally_visible_in_search_result",
    ):
        if observation_access.get(key) is not True:
            errors.append(f"observation access fact must remain true: {key}")
    for key in (
        "raw_provider_metadata_persisted_in_research_storage",
        "audio_archive_downloaded",
        "audio_member_accessed",
        "exact_source_member_selected",
        "retained_odaq_reference_accessed",
        "processed_odaq_condition_accessed",
        "perceptual_metric_executed",
        "target_perceptual_degradation_metric_score_accessed",
        "target_perceptual_degradation_listening_score_accessed",
        "unrelated_urmp_synchronization_study_result_used_for_candidate_classification",
        "sealed_evidence_opened",
        "no_reference_training_performed",
        "public_verdict_enabled",
    ):
        if observation_access.get(key) is not False:
            errors.append(f"observation boundary must remain false: {key}")
    screen_policy = observation.get("screen_policy", {})
    if screen_policy.get("allowed_dataset_licences") != [
        "CC BY 4.0",
        "CC0 1.0",
    ]:
        errors.append("observation licence policy differs")
    for key, value in screen_policy.items():
        if key == "allowed_dataset_licences":
            continue
        expected = key in {
            "immutable_version_required_before_exact_member_audit",
            "documented_purpose_recording_chain_required",
        }
        if value is not expected:
            errors.append(f"observation screen policy differs: {key}")

    observed_candidates = observation.get("exact_member_audit_candidates", [])
    expected_candidate_counts = {
        "albumdb": ("albumdb_19683001", "CC BY 4.0", 10),
        "choralebricks": ("choralebricks_20849469", "CC BY 4.0", 10),
        "good_sounds": ("good_sounds_data2314_v1_0", "CC BY 4.0", 15),
        "urmp": ("urmp_5034983", "CC0 1.0", 28),
    }
    if {
        candidate.get("provider_id") for candidate in observed_candidates
    } != set(expected_candidate_counts):
        errors.append("observation candidate provider set differs")
    for candidate in observed_candidates:
        provider_id = candidate.get("provider_id")
        expected = expected_candidate_counts.get(provider_id, (None, None, None))
        if (
            candidate.get("source_id"),
            candidate.get("licence"),
            candidate.get("conservative_available_group_count"),
        ) != expected:
            errors.append(f"observation candidate identity differs: {provider_id}")
        if not str(candidate.get("role_status", "")).startswith(
            "candidate_after_exact_member_"
        ):
            errors.append(f"observation candidate role differs: {provider_id}")
        if not candidate.get("immutable_files"):
            errors.append(f"observation candidate lacks immutable files: {provider_id}")
    albumdb = next(
        (item for item in observed_candidates if item.get("provider_id") == "albumdb"),
        {},
    )
    if albumdb.get("music_role") != "real_mastered_single_album_indie_candidate":
        errors.append("AlbumDB mastered-music boundary differs")
    good_sounds = next(
        (
            item
            for item in observed_candidates
            if item.get("provider_id") == "good_sounds"
        ),
        {},
    )
    conflict = good_sounds.get("historical_licence_conflict", {})
    if (
        conflict.get("older_record_embedded_description") != "CC BY-NC 4.0"
        or conflict.get("candidate_scope")
        != "only_the_exact_2025_dataverse_v1_0_rerelease"
        or conflict.get("exact_archive_embedded_rights_audit_required") is not True
    ):
        errors.append("Good-sounds version-specific rights boundary differs")
    urmp = next(
        (item for item in observed_candidates if item.get("provider_id") == "urmp"),
        {},
    )
    if (
        urmp.get("public_arrangement_count") != 44
        or urmp.get("public_unique_work_count") != 28
        or urmp.get("conservative_available_group_count") != 28
    ):
        errors.append("URMP grouping boundary differs")
    aggregate = observation.get("aggregate_observation", {})
    if aggregate != {
        "new_exact_member_audit_candidate_provider_count": 4,
        "new_conservative_available_group_count": 63,
        "new_real_mastered_music_provider_count": 1,
        "new_real_mastered_music_group_count": 10,
        "new_real_controlled_performance_provider_count": 3,
        "new_real_controlled_performance_group_count": 53,
        "qualified_reference_group_count": 0,
        "allocated_group_count": 0,
    }:
        errors.append("observation aggregate differs")
    expected_screened_not_added = {
        "rwc_music_18656623",
        "musdb18_hq_3338373",
        "anechoic_string_quartet_4955282",
        "mshoxxdb_19599752",
        "waivops_edm_tr9_10278066",
        "bsd35k_cs_19187100",
        "open_multitrack_testbed",
        "orchideasol_3740399",
        "bach_violin_dataset",
    }
    if {
        item.get("source_id") for item in observation.get("screened_not_added", [])
    } != expected_screened_not_added:
        errors.append("screened-not-added candidate set differs")
    for key, value in observation.get("observation_limits", {}).items():
        if value is not False:
            errors.append(f"observation limit must remain false: {key}")
    pending = bound.get("pending_source_disposition", {})
    if pending.get("allocation_consequence", {}).get(
        "pending_provider_count_promoted_to_truth_reference"
    ) != 0:
        errors.append("rejected pending provider was promoted")
    predecessor_report = bound.get("predecessor_provider_report", {})
    if predecessor_report.get("decision", {}).get(
        "no_reference_work_eligible"
    ) is not False:
        errors.append("predecessor no-reference gate is open")

    candidate_plan = bound.get("predecessor_candidate_plan", {})
    expected_partitions = candidate_plan.get("partition_requirements", {}).get(
        "truth_bearing_partitions"
    )
    if plan.get("partitions") != expected_partitions:
        errors.append("partition order differs from predecessor")
    minimum = candidate_plan.get("partition_requirements", {}).get(
        "minimum_independent_source_groups_per_partition"
    )
    sensitivity = candidate_plan.get("partition_requirements", {}).get(
        "reference_sensitivity_source_groups_per_partition"
    )
    domain_minimum = bound.get("full_reference_evaluation_plan", {}).get(
        "statistics", {}
    ).get("minimum_primary_domain_source_groups")
    if (minimum, sensitivity, domain_minimum) != (39, 120, 8):
        errors.append("bound statistical thresholds differ")

    expected_authorization = {
        "aggregate_metadata_computation_authorized": True,
        "exact_member_selection_authorized": False,
        "new_audio_acquisition_authorized": False,
        "retained_odaq_reference_read_authorized": False,
        "retained_reference_projection_authorized": False,
        "processed_condition_access_authorized": False,
        "target_perceptual_degradation_metric_score_access_authorized": False,
        "target_perceptual_degradation_listening_score_access_authorized": False,
        "perceptual_metric_execution_authorized": False,
        "human_collection_authorized": False,
        "recruitment_authorized": False,
        "sealed_evidence_access_authorized": False,
        "no_reference_training_authorized": False,
        "public_verdict_enabled": False,
    }
    if plan.get("authorization") != expected_authorization:
        errors.append("authorization boundary differs")

    providers = plan.get("providers", [])
    provider_ids = [provider.get("provider_id") for provider in providers]
    if len(provider_ids) != len(set(provider_ids)):
        errors.append("provider IDs must be unique")
    expected_capabilities = {
        "albumdb": ["music", "mastered_music"],
        "choralebricks": ["music", "controlled_performance_music"],
        "good_sounds": ["music", "controlled_performance_music"],
        "guitarset": ["music", "controlled_performance_music"],
        "lombard_grid": ["speech"],
        "satp": ["natural"],
        "slakh": ["synthetic"],
        "sonyc_backgrounds": ["natural"],
        "tinysol": ["music", "controlled_performance_music"],
        "urmp": ["music", "controlled_performance_music"],
        "vctk_clean": ["speech"],
    }
    if set(provider_ids) != set(expected_capabilities):
        errors.append("provider sensitivity population differs")
    for provider in providers:
        provider_id = provider.get("provider_id")
        if provider.get("capabilities") != expected_capabilities.get(provider_id):
            errors.append(f"provider capabilities differ: {provider_id}")
        capacity = provider.get("available_group_capacity")
        if not isinstance(capacity, int) or capacity <= 0:
            errors.append(f"provider capacity is invalid: {provider_id}")

    predecessor_plan = bound.get("predecessor_provider_plan", {})
    predecessor_by_id = {
        provider.get("provider_id"): provider
        for provider in predecessor_plan.get("providers", [])
        if provider.get("provider_id") not in {"musicnet", "fsd50k"}
    }
    predecessor_current = {
        provider.get("provider_id"): provider
        for provider in providers
        if provider.get("provenance") == "predecessor_exact_member_audit_candidate"
    }
    if set(predecessor_current) != set(predecessor_by_id):
        errors.append("predecessor provider set differs")
    for provider_id, provider in predecessor_current.items():
        old = predecessor_by_id.get(provider_id, {})
        if (
            provider.get("source_id") != old.get("source_id")
            or provider.get("available_group_capacity")
            != old.get("available_group_capacity")
        ):
            errors.append(f"predecessor provider binding differs: {provider_id}")

    observed_new = {
        candidate.get("provider_id"): candidate
        for candidate in observation.get("exact_member_audit_candidates", [])
    }
    current_new = {
        provider.get("provider_id"): provider
        for provider in providers
        if provider.get("provenance") == "additional_exact_member_audit_candidate"
    }
    if set(current_new) != set(observed_new):
        errors.append("additional provider set differs")
    for provider_id, provider in current_new.items():
        observed = observed_new.get(provider_id, {})
        if (
            provider.get("source_id") != observed.get("source_id")
            or provider.get("available_group_capacity")
            != observed.get("conservative_available_group_count")
        ):
            errors.append(f"additional provider binding differs: {provider_id}")

    expected_policy = {
        "provider_may_be_assigned_to_at_most_one_partition": True,
        "unused_provider_allowed": True,
        "capacity_is_capped_for_state_search_at_each_scenario_threshold": True,
        "full_provider_capacity_is_not_an_exact_member_selection": True,
        "capability_labels_are_conservative": True,
        "synthetic_counts_as_music": False,
        "controlled_performance_music_counts_as_mastered_music": False,
        "capacity_witness_is_operational_allocation": False,
        "candidate_provider_can_be_scientifically_eligible_before_exact_member_audit": False,
        "deterministic_provider_order": "provider_id_ascending",
        "deterministic_assignment_order": "unused_then_partition_order",
    }
    if plan.get("solver_policy") != expected_policy:
        errors.append("solver policy differs")

    known_capabilities = {
        capability
        for provider in providers
        for capability in provider.get("capabilities", [])
    }
    scenario_ids: set[str] = set()
    for scenario in plan.get("scenarios", []):
        scenario_id = scenario.get("scenario_id")
        if not isinstance(scenario_id, str) or scenario_id in scenario_ids:
            errors.append("scenario IDs must be unique strings")
        scenario_ids.add(scenario_id)
        if scenario.get("minimum_groups_each_partition") not in {
            minimum,
            sensitivity,
        }:
            errors.append(f"scenario source floor differs: {scenario_id}")
        minimum_providers = scenario.get("minimum_providers_each_partition")
        if not isinstance(minimum_providers, int) or minimum_providers < 0:
            errors.append(f"scenario provider floor differs: {scenario_id}")
        for field in (
            "capability_minimums_by_partition",
            "capability_provider_minimums_by_partition",
        ):
            for partition, requirements in scenario.get(field, {}).items():
                if partition not in plan.get("partitions", []):
                    errors.append(f"scenario partition differs: {scenario_id}")
                for capability, value in requirements.items():
                    if capability not in known_capabilities:
                        errors.append(f"scenario capability differs: {scenario_id}")
                    expected = 8 if field == "capability_minimums_by_partition" else 2
                    if value != expected:
                        errors.append(
                            f"scenario capability threshold differs: {scenario_id}"
                        )
        if scenario.get("expected_arithmetic_feasible") not in {True, False}:
            errors.append(f"scenario expectation is invalid: {scenario_id}")
        if not isinstance(scenario.get("reason_not_eligible"), str):
            errors.append(f"scenario ineligibility reason is missing: {scenario_id}")

    decision = plan.get("decision_boundary", {})
    if decision.get("selected_source_successor") is not None:
        errors.append("source successor was prematurely selected")
    if decision.get("selected_metric_successor") is not None:
        errors.append("metric successor was prematurely selected")
    for key, value in decision.items():
        if key.startswith("selected_"):
            continue
        if value is not False:
            errors.append(f"decision gate must remain false: {key}")
    for key, value in plan.get("claim_boundary", {}).items():
        if value is not False:
            errors.append(f"claim boundary must remain false: {key}")
    return errors


def _slots(
    partitions: list[str],
    requirements: dict[str, dict[str, int]],
) -> tuple[list[tuple[int, str]], tuple[int, ...]]:
    slots: list[tuple[int, str]] = []
    thresholds: list[int] = []
    for partition_index, partition in enumerate(partitions):
        for capability in sorted(requirements.get(partition, {})):
            slots.append((partition_index, capability))
            thresholds.append(int(requirements[partition][capability]))
    return slots, tuple(thresholds)


def solve_scenario(plan: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    partitions = list(plan["partitions"])
    providers = sorted(plan["providers"], key=lambda provider: provider["provider_id"])
    minimum_groups = int(scenario["minimum_groups_each_partition"])
    minimum_providers = int(scenario["minimum_providers_each_partition"])
    capability_slots, capability_thresholds = _slots(
        partitions, scenario["capability_minimums_by_partition"]
    )
    provider_slots, provider_thresholds = _slots(
        partitions, scenario["capability_provider_minimums_by_partition"]
    )
    initial = State(
        totals=(0,) * len(partitions),
        provider_counts=(0,) * len(partitions),
        capability_totals=(0,) * len(capability_slots),
        capability_provider_counts=(0,) * len(provider_slots),
    )
    states: dict[State, tuple[int | None, ...]] = {initial: ()}

    for provider in providers:
        next_states: dict[State, tuple[int | None, ...]] = {}
        capacity = int(provider["available_group_capacity"])
        capabilities = set(provider["capabilities"])
        for state, assignment in states.items():
            for partition_index in [None, *range(len(partitions))]:
                totals = list(state.totals)
                counts = list(state.provider_counts)
                capability_totals = list(state.capability_totals)
                capability_counts = list(state.capability_provider_counts)
                if partition_index is not None:
                    totals[partition_index] = min(
                        minimum_groups, totals[partition_index] + capacity
                    )
                    counts[partition_index] = min(
                        minimum_providers, counts[partition_index] + 1
                    )
                    for slot_index, (slot_partition, capability) in enumerate(
                        capability_slots
                    ):
                        if slot_partition == partition_index and capability in capabilities:
                            capability_totals[slot_index] = min(
                                capability_thresholds[slot_index],
                                capability_totals[slot_index] + capacity,
                            )
                    for slot_index, (slot_partition, capability) in enumerate(
                        provider_slots
                    ):
                        if slot_partition == partition_index and capability in capabilities:
                            capability_counts[slot_index] = min(
                                provider_thresholds[slot_index],
                                capability_counts[slot_index] + 1,
                            )
                candidate = State(
                    tuple(totals),
                    tuple(counts),
                    tuple(capability_totals),
                    tuple(capability_counts),
                )
                if candidate not in next_states:
                    next_states[candidate] = (*assignment, partition_index)
        states = next_states

    target = State(
        totals=(minimum_groups,) * len(partitions),
        provider_counts=(minimum_providers,) * len(partitions),
        capability_totals=capability_thresholds,
        capability_provider_counts=provider_thresholds,
    )
    assignment = states.get(target)
    witness: list[dict[str, Any]] = []
    capacity_by_partition = {partition: 0 for partition in partitions}
    if assignment is not None:
        for provider, partition_index in zip(providers, assignment, strict=True):
            if partition_index is None:
                continue
            partition = partitions[partition_index]
            capacity_by_partition[partition] += provider["available_group_capacity"]
            witness.append(
                {
                    "provider_id": provider["provider_id"],
                    "partition": partition,
                    "capabilities": provider["capabilities"],
                    "available_group_capacity": provider["available_group_capacity"],
                }
            )
    arithmetic_feasible = assignment is not None
    return {
        "scenario_id": scenario["scenario_id"],
        "arithmetic_feasible": arithmetic_feasible,
        "expected_arithmetic_feasible": scenario["expected_arithmetic_feasible"],
        "result_matches_frozen_expectation": (
            arithmetic_feasible == scenario["expected_arithmetic_feasible"]
        ),
        "scientifically_eligible": False,
        "reason_not_eligible": scenario["reason_not_eligible"],
        "eligible_provider_count": len(providers),
        "eligible_available_group_capacity": sum(
            provider["available_group_capacity"] for provider in providers
        ),
        "capacity_witness": witness,
        "available_capacity_by_partition": capacity_by_partition,
        "exact_member_selection_frozen": False,
    }


def build_report(
    plan: dict[str, Any],
    plan_path: Path = PLAN_PATH,
    implementation_path: Path = Path(__file__),
) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    results = [solve_scenario(plan, scenario) for scenario in plan["scenarios"]]
    if not all(result["result_matches_frozen_expectation"] for result in results):
        mismatches = [
            result["scenario_id"]
            for result in results
            if not result["result_matches_frozen_expectation"]
        ]
        raise ValueError(f"scenario result differs from frozen expectation: {mismatches}")
    by_id = {result["scenario_id"]: result for result in results}
    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "score_blind_additional_provider_capacity_sensitivity_complete_no_member_allocation",
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
            "expanded_pool_clears_count_only_39_each_partition": by_id[
                "expanded_count_only_39_each_partition"
            ]["arithmetic_feasible"],
            "expanded_pool_clears_two_providers_39_each_partition": by_id[
                "expanded_two_providers_39_each_partition"
            ]["arithmetic_feasible"],
            "expanded_pool_clears_final_three_domain_capacity": by_id[
                "expanded_final_three_domain_minimum"
            ]["arithmetic_feasible"],
            "expanded_pool_clears_music_minimum_every_partition": by_id[
                "expanded_music_minimum_every_partition"
            ]["arithmetic_feasible"],
            "expanded_pool_clears_three_domains_every_partition": by_id[
                "expanded_three_domains_every_partition"
            ]["arithmetic_feasible"],
            "expanded_pool_clears_mastered_music_every_partition": by_id[
                "expanded_mastered_music_minimum_every_partition"
            ]["arithmetic_feasible"],
            "expanded_pool_clears_two_mastered_music_providers_in_final": by_id[
                "expanded_final_two_mastered_music_providers"
            ]["arithmetic_feasible"],
            "expanded_pool_clears_reference_sensitivity_120_each_partition": by_id[
                "expanded_reference_sensitivity_120_each_partition"
            ]["arithmetic_feasible"],
            "qualified_reference_group_count": 0,
            "allocated_group_count": 0,
            "exact_member_manifest_frozen": False,
            "provider_allocation_frozen": False,
            "primary_domains_frozen": False,
            "source_successor_selected": False,
            "metric_successor_selected": False,
            "no_reference_work_eligible": False,
            "next_responsible_human_decision": (
                "Choose whether to authorize an exact-member metadata audit of the "
                "expanded candidates, narrow the primary-domain claim, or reject the "
                "current truth-source design; this does not authorize audio access."
            ),
        },
        "claim_boundary": plan["claim_boundary"],
    }


def write_report(report: dict[str, Any], output: Path) -> None:
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def validate_committed_report(
    plan_path: Path = PLAN_PATH, report_path: Path = REPORT_PATH
) -> list[str]:
    errors: list[str] = []
    plan = load_json(plan_path)
    errors.extend(validate_plan(plan))
    if errors:
        return errors
    if not report_path.is_file():
        return ["committed report is missing"]
    expected = build_report(plan, plan_path)
    actual = load_json(report_path)
    if actual != expected:
        errors.append("committed report differs from deterministic regeneration")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.output:
        report = build_report(load_json(args.plan), args.plan)
        write_report(report, args.output)
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
