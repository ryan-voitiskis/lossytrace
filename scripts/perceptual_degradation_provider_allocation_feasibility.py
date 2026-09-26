#!/usr/bin/env python3
"""Evaluate score-blind provider-capacity allocation sensitivities."""

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
    / "permissive-provider-allocation-feasibility-plan.json"
)
PLAN_ID = "perceptual-degradation-permissive-provider-allocation-feasibility-20260814-001"
REPORT_ID = "perceptual-degradation-permissive-provider-allocation-feasibility-20260814-001"


class State(NamedTuple):
    totals: tuple[int, ...]
    provider_counts: tuple[int, ...]
    domain_totals: tuple[int, ...]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _resolved_tiers(plan: dict[str, Any], scenario: dict[str, Any]) -> tuple[set[str], set[str]]:
    tiers: set[str] = set()
    provider_aliases: set[str] = set()
    aliases = plan.get("tier_aliases", {})
    for value in scenario.get("allowed_tiers", []):
        if value in aliases:
            provider_aliases.update(aliases[value])
        else:
            tiers.add(value)
    return tiers, provider_aliases


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != "score_blind_aggregate_capacity_sensitivity_no_member_allocation":
        errors.append("plan state differs")

    bound: dict[str, dict[str, Any]] = {}
    for binding_id, binding in plan.get("bindings", {}).items():
        path = root / str(binding.get("path", ""))
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")
        elif path.suffix == ".json":
            bound[binding_id] = load_json(path)

    expected_authorization = {
        "aggregate_metadata_computation_authorized": True,
        "exact_member_selection_authorized": False,
        "new_audio_acquisition_authorized": False,
        "retained_odaq_reference_read_authorized": False,
        "retained_reference_projection_authorized": False,
        "processed_condition_access_authorized": False,
        "listening_score_access_authorized": False,
        "perceptual_metric_execution_authorized": False,
        "human_collection_authorized": False,
        "recruitment_authorized": False,
        "sealed_evidence_access_authorized": False,
        "no_reference_training_authorized": False,
        "public_verdict_enabled": False,
    }
    if plan.get("authorization") != expected_authorization:
        errors.append("authorization boundary differs")

    candidate_plan = bound.get("candidate_plan", {})
    expected_partitions = candidate_plan.get("partition_requirements", {}).get(
        "truth_bearing_partitions"
    )
    if plan.get("partitions") != expected_partitions:
        errors.append("partition order differs from candidate plan")
    minimum = candidate_plan.get("partition_requirements", {}).get(
        "minimum_independent_source_groups_per_partition"
    )
    domain_minimum = bound.get("full_reference_evaluation_plan", {}).get(
        "statistics", {}
    ).get("minimum_primary_domain_source_groups")

    observation_binding = candidate_plan.get("bindings", {}).get(
        "public_metadata_observation", {}
    )
    observation_path = root / str(observation_binding.get("path", ""))
    observation: dict[str, Any] = {}
    if not observation_path.is_file():
        errors.append("nested metadata observation is missing")
    elif sha256_file(observation_path) != observation_binding.get("sha256"):
        errors.append("nested metadata observation hash differs")
    else:
        observation = load_json(observation_path)
    observed = {
        item.get("source_id"): item
        for item in observation.get("observations", [])
    }

    providers = plan.get("providers", [])
    provider_ids = [provider.get("provider_id") for provider in providers]
    if len(provider_ids) != len(set(provider_ids)):
        errors.append("provider IDs must be unique")
    expected_domains = {
        "fsd50k": "mixed",
        "guitarset": "music",
        "lombard_grid": "speech",
        "musicnet": "music",
        "satp": "natural",
        "slakh": "synthetic",
        "sonyc_backgrounds": "natural",
        "tinysol": "music",
        "vctk_clean": "speech",
    }
    if set(provider_ids) != set(expected_domains):
        errors.append("provider sensitivity population differs")
    source_tiers = {
        source_id: tier["tier_id"]
        for tier in candidate_plan.get("candidate_tiers", [])
        for source_id in tier.get("source_ids", [])
    }
    for provider in providers:
        source_id = provider.get("source_id")
        source = observed.get(source_id, {})
        if provider.get("available_group_capacity") != source.get(
            "conservative_available_group_count"
        ):
            errors.append(f"provider capacity differs: {provider.get('provider_id')}")
        if provider.get("provider_id") != source.get("provider_id"):
            errors.append(f"provider identity differs: {provider.get('provider_id')}")
        if provider.get("domain") != expected_domains.get(provider.get("provider_id")):
            errors.append(f"provider domain differs: {provider.get('provider_id')}")
        if provider.get("tier_id") != source_tiers.get(source_id):
            errors.append(f"provider tier differs: {provider.get('provider_id')}")

    expected_policy = {
        "provider_may_be_assigned_to_at_most_one_partition": True,
        "unused_provider_allowed": True,
        "capacity_is_capped_for_state_search_at_each_scenario_threshold": True,
        "full_provider_capacity_is_not_an_exact_member_selection": True,
        "domain_labels_are_conservative_single_labels": True,
        "synthetic_counts_as_music": False,
        "mixed_counts_as_natural": False,
        "pending_provider_can_be_scientifically_eligible": False,
        "capacity_witness_is_operational_allocation": False,
        "deterministic_provider_order": "provider_id_ascending",
        "deterministic_assignment_order": "unused_then_partition_order",
    }
    if plan.get("solver_policy") != expected_policy:
        errors.append("solver policy differs")

    scenario_ids: set[str] = set()
    for scenario in plan.get("scenarios", []):
        scenario_id = scenario.get("scenario_id")
        if not isinstance(scenario_id, str) or scenario_id in scenario_ids:
            errors.append("scenario IDs must be unique strings")
        scenario_ids.add(scenario_id)
        if scenario.get("minimum_groups_each_partition") != minimum:
            errors.append(f"scenario source floor differs: {scenario_id}")
        if scenario.get("scientifically_eligible") is not False:
            errors.append(f"scenario was prematurely made eligible: {scenario_id}")
        for partition, requirements in scenario.get(
            "domain_minimums_by_partition", {}
        ).items():
            if partition not in plan.get("partitions", []):
                errors.append(f"scenario domain partition differs: {scenario_id}")
            for domain, value in requirements.items():
                if domain not in {"music", "speech", "natural"}:
                    errors.append(f"scenario primary domain differs: {scenario_id}")
                if value != domain_minimum:
                    errors.append(f"scenario domain minimum differs: {scenario_id}")
        tiers, aliases = _resolved_tiers(plan, scenario)
        known_tiers = {provider.get("tier_id") for provider in providers}
        if not tiers <= known_tiers:
            errors.append(f"scenario tier differs: {scenario_id}")
        if not aliases <= set(provider_ids):
            errors.append(f"scenario provider alias differs: {scenario_id}")

    for key, value in plan.get("claim_boundary", {}).items():
        if value is not False:
            errors.append(f"claim boundary must remain false: {key}")
    return errors


def _domain_slots(
    partitions: list[str], scenario: dict[str, Any]
) -> tuple[list[tuple[int, str]], tuple[int, ...]]:
    slots: list[tuple[int, str]] = []
    thresholds: list[int] = []
    requirements = scenario.get("domain_minimums_by_partition", {})
    for partition_index, partition in enumerate(partitions):
        for domain in sorted(requirements.get(partition, {})):
            slots.append((partition_index, domain))
            thresholds.append(int(requirements[partition][domain]))
    return slots, tuple(thresholds)


def solve_scenario(plan: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    partitions = list(plan["partitions"])
    tiers, provider_aliases = _resolved_tiers(plan, scenario)
    providers = [
        provider
        for provider in plan["providers"]
        if provider["tier_id"] in tiers or provider["provider_id"] in provider_aliases
    ]
    providers.sort(key=lambda provider: provider["provider_id"])

    minimum_groups = int(scenario["minimum_groups_each_partition"])
    minimum_providers = int(scenario["minimum_providers_each_partition"])
    domain_slots, domain_thresholds = _domain_slots(partitions, scenario)
    initial = State(
        totals=(0,) * len(partitions),
        provider_counts=(0,) * len(partitions),
        domain_totals=(0,) * len(domain_slots),
    )
    states: dict[State, tuple[int | None, ...]] = {initial: ()}

    for provider in providers:
        next_states: dict[State, tuple[int | None, ...]] = {}
        capacity = int(provider["available_group_capacity"])
        for state, assignment in states.items():
            choices: list[int | None] = [None, *range(len(partitions))]
            for partition_index in choices:
                totals = list(state.totals)
                counts = list(state.provider_counts)
                domains = list(state.domain_totals)
                if partition_index is not None:
                    totals[partition_index] = min(
                        minimum_groups, totals[partition_index] + capacity
                    )
                    counts[partition_index] = min(
                        minimum_providers,
                        counts[partition_index] + 1,
                    )
                    for slot_index, (slot_partition, slot_domain) in enumerate(
                        domain_slots
                    ):
                        if (
                            slot_partition == partition_index
                            and slot_domain == provider["domain"]
                        ):
                            domains[slot_index] = min(
                                domain_thresholds[slot_index],
                                domains[slot_index] + capacity,
                            )
                candidate = State(tuple(totals), tuple(counts), tuple(domains))
                if candidate not in next_states:
                    next_states[candidate] = (*assignment, partition_index)
        states = next_states

    target = State(
        totals=(minimum_groups,) * len(partitions),
        provider_counts=(minimum_providers,) * len(partitions),
        domain_totals=domain_thresholds,
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
                    "domain": provider["domain"],
                    "available_group_capacity": provider["available_group_capacity"],
                }
            )
    return {
        "scenario_id": scenario["scenario_id"],
        "arithmetic_feasible": assignment is not None,
        "expected_arithmetic_feasible": scenario["expected_arithmetic_feasible"],
        "result_matches_frozen_expectation": (
            (assignment is not None) == scenario["expected_arithmetic_feasible"]
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


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    results = [solve_scenario(plan, scenario) for scenario in plan["scenarios"]]
    if not all(result["result_matches_frozen_expectation"] for result in results):
        raise ValueError("scenario result differs from frozen expectation")
    by_id = {result["scenario_id"]: result for result in results}
    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "score_blind_aggregate_capacity_sensitivity_complete_no_member_allocation",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "audio_accessed": False,
        "exact_members_selected": False,
        "scores_opened": False,
        "metrics_executed": False,
        "sealed_evidence_opened": False,
        "human_collection_authorized": False,
        "public_verdict_enabled": False,
        "scenario_results": results,
        "decision": {
            "audit_tier_clears_count_only_capacity": by_id["audit_count_only"][
                "arithmetic_feasible"
            ],
            "audit_tier_supports_two_providers_each_partition": by_id[
                "audit_two_providers_each_partition"
            ]["arithmetic_feasible"],
            "audit_tier_supports_final_three_domain_minimum": by_id[
                "audit_final_three_domain_minimum"
            ]["arithmetic_feasible"],
            "musicnet_alone_repairs_final_three_domain_allocation": by_id[
                "add_musicnet_final_three_domain_minimum"
            ]["arithmetic_feasible"],
            "all_pending_providers_make_arithmetic_final_domain_sensitivity_feasible": by_id[
                "add_all_pending_final_three_domain_minimum"
            ]["arithmetic_feasible"],
            "pending_sensitivity_is_scientifically_eligible": False,
            "three_domain_breadth_each_partition_is_feasible": by_id[
                "all_pending_three_domains_each_partition"
            ]["arithmetic_feasible"],
            "exact_member_manifest_frozen": False,
            "provider_allocation_frozen": False,
            "primary_domains_frozen": False,
            "no_reference_work_eligible": False,
            "next_score_blind_requirement": "Obtain or qualify more independent real-music, speech and natural providers, or explicitly narrow the future claim and primary-domain design; exact-member selection remains premature.",
        },
    }


def write_report(report: dict[str, Any], output: Path) -> None:
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = load_json(args.plan)
    report = build_report(plan, args.plan)
    write_report(report, args.output)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
