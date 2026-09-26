#!/usr/bin/env python3
"""Stress v3 listening assignments with score-blind synthetic missingness."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "listening-missingness-stress-plan.json"
)
PLAN_ID = "perceptual-degradation-listening-missingness-stress-20260814-001"
REPORT_ID = PLAN_ID


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ALLOCATOR = _load_module(
    "listening_allocation_v3_for_missingness",
    ROOT / "scripts/perceptual_degradation_listening_allocation_v3.py",
)
RESOURCE = _load_module(
    "listening_resource_frontier_for_missingness",
    ROOT / "scripts/perceptual_degradation_listening_resource_frontier.py",
)


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
        "score_blind_synthetic_missingness_stress_no_operational_policy"
    ):
        errors.append("plan state differs")
    expected_bindings = {
        "allocator_v3",
        "allocator_v3_audit_plan",
        "allocator_v3_audit_report",
        "feasibility_plan",
        "feasibility_report",
        "symbolic_manifest_builder",
        "resource_frontier_plan",
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
    if authorization.get("synthetic_symbolic_missingness_replay_authorized") is not True:
        errors.append("synthetic missingness replay must be authorized")
    for key, value in authorization.items():
        if key != "synthetic_symbolic_missingness_replay_authorized" and value is not False:
            errors.append(f"authorization boundary must remain false: {key}")

    stress = plan.get("stress_contract", {})
    expected_stress = {
        "usable_trial_rate": 0.90,
        "mcar_replicates": 256,
        "minimum_judgments_per_source": 8,
        "source_correlated_missing_group_count": 12,
        "outcome_values_generated": False,
        "outcome_values_read": False,
        "completion_masks_use_only_seed_assignment_trial_source_and_position": True,
        "mcar_is_assumption_not_verified_mechanism": True,
        "power_recalculation_required_for_structured_missingness": True,
        "missing_response_imputation_selected": False,
        "inverse_probability_weighting_selected": False,
        "replacement_assignment_selected": False,
        "exclusion_policy_selected": False,
    }
    if stress != expected_stress:
        errors.append("stress contract differs")

    expected_scenarios = (
        ("complete-issued-prefix", "complete", None, None, None, None),
        (
            "contiguous-session-prefix-90",
            "contiguous_session_prefix",
            0.90,
            None,
            None,
            None,
        ),
        ("hash-mcar-session-90", "hash_mcar_session", 0.90, 256, None, None),
        ("hash-mcar-trial-90", "hash_mcar_trial", 0.90, 256, None, None),
        (
            "exposure-phase-every-tenth",
            "exposure_phase",
            None,
            None,
            10,
            0,
        ),
        (
            "source-correlated-10-percent",
            "source_correlated",
            None,
            None,
            None,
            12,
        ),
    )
    observed_scenarios = tuple(
        (
            row.get("scenario_id"),
            row.get("kind"),
            row.get("retention_rate"),
            row.get("replicates"),
            row.get("modulus"),
            row.get("excluded_remainder", row.get("excluded_source_group_count")),
        )
        for row in plan.get("scenarios", [])
    )
    if observed_scenarios != expected_scenarios:
        errors.append("scenario inventory differs")
    expected_options = (
        ("sources120-subtle3-mushra3", 3, 3, 765),
        ("sources120-subtle5-mushra5", 5, 5, 496),
        ("sources120-subtle8-mushra6", 8, 6, 345),
        ("sources120-subtle15-mushra6", 15, 6, 227),
    )
    observed_options = tuple(
        (
            row.get("option_id"),
            row.get("subtle_trial_limit"),
            row.get("mushra_trial_limit"),
            row.get("eligible_prefix"),
        )
        for row in plan.get("frontier_options", [])
    )
    if observed_options != expected_options:
        errors.append("frontier options differ")
    for key, value in plan.get("claim_boundary", {}).items():
        if value is not False:
            errors.append(f"claim boundary must remain false: {key}")
    return errors


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def _make_schedule(
    manifest: dict[str, Any],
    allocation_seed: str,
    participant_count: int,
    subtle_trial_limit: int,
    mushra_trial_limit: int,
) -> list[dict[str, Any]]:
    stimulus_source = {
        item["stimulus_id"]: item["source_group_id"]
        for item in manifest["stimuli"]
    }
    issued_exposure_ordinal: dict[tuple[str, str], int] = {}
    rows: list[dict[str, Any]] = []
    for allocation_index in range(participant_count):
        assignment = ALLOCATOR.allocate(
            manifest,
            f"symbolic-participant-{allocation_index:06d}",
            allocation_seed,
            allocation_index,
            subtle_trial_limit=subtle_trial_limit,
            mushra_trial_limit=mushra_trial_limit,
        )
        for block in assignment["blocks"]:
            for block_position, trial in enumerate(block["trials"]):
                key = (block["method"], trial["trial_id"])
                exposure_ordinal = issued_exposure_ordinal.get(key, 0)
                issued_exposure_ordinal[key] = exposure_ordinal + 1
                rows.append(
                    {
                        "allocation_index": allocation_index,
                        "method": block["method"],
                        "trial_id": trial["trial_id"],
                        "source_group_id": stimulus_source[
                            trial["visible_reference_id"]
                        ],
                        "block_position": block_position,
                        "issued_exposure_ordinal": exposure_ordinal,
                        "candidate_positions": trial["candidate_positions"],
                    }
                )
    return rows


def _hash_keep(rate: float, *parts: str) -> bool:
    threshold = math.floor(rate * (1 << 64))
    value = int.from_bytes(
        hashlib.sha256("\0".join(parts).encode()).digest()[:8], "big"
    )
    return value < threshold


def _balance_summary(
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    keep: Callable[[dict[str, Any]], bool],
    trial_limits: dict[str, int],
    minimum_judgments: int,
) -> dict[str, Any]:
    trials = {trial["trial_id"]: trial for trial in manifest["trials"]}
    stimulus_source = {
        item["stimulus_id"]: item["source_group_id"]
        for item in manifest["stimuli"]
    }
    retained = [row for row in rows if keep(row)]
    scheduled_sessions = {row["allocation_index"] for row in rows}
    retained_sessions = {row["allocation_index"] for row in retained}
    methods: dict[str, Any] = {}
    for method in ("subtle", "mushra"):
        method_trial_ids = [
            trial_id
            for trial_id, trial in trials.items()
            if trial["method"] == method
        ]
        exposure = {trial_id: 0 for trial_id in method_trial_ids}
        block_positions = {
            trial_id: [0] * trial_limits[method]
            for trial_id in method_trial_ids
        }
        candidate_positions = {
            trial_id: {
                candidate_id: [0] * len(trials[trial_id]["candidate_ids"])
                for candidate_id in trials[trial_id]["candidate_ids"]
            }
            for trial_id in method_trial_ids
        }
        scheduled_count = sum(row["method"] == method for row in rows)
        retained_count = 0
        for row in retained:
            if row["method"] != method:
                continue
            retained_count += 1
            trial_id = row["trial_id"]
            exposure[trial_id] += 1
            block_positions[trial_id][row["block_position"]] += 1
            for item in row["candidate_positions"]:
                candidate_positions[trial_id][item["stimulus_id"]][
                    item["position"] - 1
                ] += 1
        exposure_values = list(exposure.values())
        block_ranges = [
            max(values, default=0) - min(values, default=0)
            for values in block_positions.values()
        ]
        candidate_ranges = [
            max(values, default=0) - min(values, default=0)
            for by_candidate in candidate_positions.values()
            for values in by_candidate.values()
        ]
        retained_source_groups = {
            stimulus_source[trials[trial_id]["visible_reference_id"]]
            for trial_id, count in exposure.items()
            if count > 0
        }
        methods[method] = {
            "scheduled_trials": scheduled_count,
            "retained_trials": retained_count,
            "retained_trial_rate": round(
                retained_count / scheduled_count if scheduled_count else 0.0,
                10,
            ),
            "trial_exposure_min": min(exposure_values, default=0),
            "trial_exposure_max": max(exposure_values, default=0),
            "trial_exposure_range": (
                max(exposure_values, default=0)
                - min(exposure_values, default=0)
            ),
            "trial_block_position_maximum_range": max(block_ranges, default=0),
            "candidate_position_maximum_range": max(
                candidate_ranges, default=0
            ),
            "source_groups_retained": len(retained_source_groups),
            "source_groups_with_zero_judgments": sum(
                value == 0 for value in exposure_values
            ),
            "source_groups_below_minimum_judgments": sum(
                value < minimum_judgments for value in exposure_values
            ),
            "minimum_judgment_support_gate_passed": all(
                value >= minimum_judgments for value in exposure_values
            ),
            "strict_retained_balance_gate_passed": (
                max(exposure_values, default=0)
                - min(exposure_values, default=0)
                <= 1
                and max(block_ranges, default=0) <= 1
                and max(candidate_ranges, default=0) <= 1
            ),
        }
    return {
        "scheduled_session_slots": len(scheduled_sessions),
        "session_slots_with_any_retained_trial": len(retained_sessions),
        "scheduled_trials": len(rows),
        "retained_trials": len(retained),
        "retained_trial_rate": round(
            len(retained) / len(rows) if rows else 0.0, 10
        ),
        "methods": methods,
        "all_methods_strict_retained_balance_gate_passed": all(
            value["strict_retained_balance_gate_passed"]
            for value in methods.values()
        ),
        "all_methods_minimum_judgment_support_gate_passed": all(
            value["minimum_judgment_support_gate_passed"]
            for value in methods.values()
        ),
        "outcomes_included": False,
    }


def _distribution(values: list[float | int]) -> dict[str, float | int]:
    ordered = sorted(values)

    def percentile(fraction: float) -> float | int:
        index = max(0, math.ceil(fraction * len(ordered)) - 1)
        return ordered[index]

    return {
        "min": ordered[0],
        "p05": percentile(0.05),
        "median": percentile(0.50),
        "p95": percentile(0.95),
        "max": ordered[-1],
    }


def _replicate_aggregate(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = (
        "retained_trial_rate",
        "trial_exposure_min",
        "trial_exposure_range",
        "trial_block_position_maximum_range",
        "candidate_position_maximum_range",
        "source_groups_retained",
        "source_groups_with_zero_judgments",
        "source_groups_below_minimum_judgments",
    )
    methods = {}
    for method in ("subtle", "mushra"):
        methods[method] = {
            metric: _distribution(
                [summary["methods"][method][metric] for summary in summaries]
            )
            for metric in metric_names
        }
    worst_index = max(
        range(len(summaries)),
        key=lambda index: (
            max(
                summaries[index]["methods"][method][
                    "source_groups_below_minimum_judgments"
                ]
                for method in ("subtle", "mushra")
            ),
            max(
                summaries[index]["methods"][method]["trial_exposure_range"]
                for method in ("subtle", "mushra")
            ),
            max(
                summaries[index]["methods"][method][
                    "candidate_position_maximum_range"
                ]
                for method in ("subtle", "mushra")
            ),
        ),
    )
    return {
        "replicate_count": len(summaries),
        "replicate_summaries_sha256": canonical_sha256(summaries),
        "strict_retained_balance_gate_pass_count": sum(
            summary["all_methods_strict_retained_balance_gate_passed"]
            for summary in summaries
        ),
        "minimum_judgment_support_gate_pass_count": sum(
            summary["all_methods_minimum_judgment_support_gate_passed"]
            for summary in summaries
        ),
        "methods": methods,
        "worst_replicate_index": worst_index,
        "worst_replicate_summary": summaries[worst_index],
        "outcomes_included": False,
    }


def _scenario_result(
    scenario: dict[str, Any],
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    seed: str,
    trial_limits: dict[str, int],
    minimum_judgments: int,
    mcar_replicates: int,
    source_group_ids: list[str],
) -> dict[str, Any]:
    scenario_id = scenario["scenario_id"]
    kind = scenario["kind"]
    if kind == "complete":
        summary = _balance_summary(
            manifest, rows, lambda _: True, trial_limits, minimum_judgments
        )
        return {"scenario_id": scenario_id, "kind": kind, "summary": summary}
    if kind == "contiguous_session_prefix":
        participant_count = max(row["allocation_index"] for row in rows) + 1
        retained_count = math.floor(participant_count * scenario["retention_rate"])
        summary = _balance_summary(
            manifest,
            rows,
            lambda row: row["allocation_index"] < retained_count,
            trial_limits,
            minimum_judgments,
        )
        return {
            "scenario_id": scenario_id,
            "kind": kind,
            "retained_contiguous_session_slots": retained_count,
            "summary": summary,
        }
    if kind in {"hash_mcar_session", "hash_mcar_trial"}:
        summaries = []
        for replicate in range(mcar_replicates):
            if kind == "hash_mcar_session":
                keep = lambda row, replicate=replicate: _hash_keep(
                    scenario["retention_rate"],
                    seed,
                    scenario_id,
                    str(replicate),
                    str(row["allocation_index"]),
                )
            else:
                keep = lambda row, replicate=replicate: _hash_keep(
                    scenario["retention_rate"],
                    seed,
                    scenario_id,
                    str(replicate),
                    str(row["allocation_index"]),
                    row["method"],
                    row["trial_id"],
                )
            summaries.append(
                _balance_summary(
                    manifest, rows, keep, trial_limits, minimum_judgments
                )
            )
        return {
            "scenario_id": scenario_id,
            "kind": kind,
            "aggregate": _replicate_aggregate(summaries),
        }
    if kind == "exposure_phase":
        summary = _balance_summary(
            manifest,
            rows,
            lambda row: row["issued_exposure_ordinal"] % scenario["modulus"]
            != scenario["excluded_remainder"],
            trial_limits,
            minimum_judgments,
        )
        return {"scenario_id": scenario_id, "kind": kind, "summary": summary}
    if kind == "source_correlated":
        excluded = set(
            sorted(
                source_group_ids,
                key=lambda value: hashlib.sha256(
                    "\0".join((seed, scenario_id, value)).encode()
                ).hexdigest(),
            )[: scenario["excluded_source_group_count"]]
        )
        summary = _balance_summary(
            manifest,
            rows,
            lambda row: row["source_group_id"] not in excluded,
            trial_limits,
            minimum_judgments,
        )
        return {
            "scenario_id": scenario_id,
            "kind": kind,
            "excluded_source_group_count": len(excluded),
            "excluded_source_group_set_sha256": canonical_sha256(sorted(excluded)),
            "summary": summary,
        }
    raise ValueError(f"unsupported scenario kind: {kind}")


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    resource_plan = load_json(_bound(plan, "resource_frontier_plan"))
    manifest = RESOURCE.make_symbolic_manifest(resource_plan)
    manifest_errors = ALLOCATOR.validate_manifest(manifest)
    if manifest_errors:
        raise ValueError("; ".join(manifest_errors))
    allocator_audit = load_json(_bound(plan, "allocator_v3_audit_report"))
    if not allocator_audit["decision"][
        "v3_all_audited_contiguous_prefixes_passed"
    ]:
        raise ValueError("v3 issued schedule did not pass its bound audit")
    feasibility = load_json(_bound(plan, "feasibility_plan"))
    stress = plan["stress_contract"]
    if (
        feasibility["score_blind_stress_assumptions"][
            "usable_trial_rate_after_missingness"
        ]
        != stress["usable_trial_rate"]
        or feasibility["frontier_grid"]["minimum_effective_judgments_per_source"]
        != stress["minimum_judgments_per_source"]
    ):
        raise ValueError("missingness stress assumptions differ from feasibility plan")

    seed = resource_plan["symbolic_fixture"]["allocation_seed"]
    source_group_ids = sorted(
        {item["source_group_id"] for item in manifest["stimuli"]}
    )
    options = []
    for option in plan["frontier_options"]:
        trial_limits = {
            "subtle": option["subtle_trial_limit"],
            "mushra": option["mushra_trial_limit"],
        }
        rows = _make_schedule(
            manifest,
            seed,
            option["eligible_prefix"],
            option["subtle_trial_limit"],
            option["mushra_trial_limit"],
        )
        scenario_results = [
            _scenario_result(
                scenario,
                manifest,
                rows,
                seed,
                trial_limits,
                stress["minimum_judgments_per_source"],
                stress["mcar_replicates"],
                source_group_ids,
            )
            for scenario in plan["scenarios"]
        ]
        options.append(
            {
                "option_id": option["option_id"],
                "eligible_prefix": option["eligible_prefix"],
                "trial_limits": trial_limits,
                "issued_schedule_sha256": canonical_sha256(rows),
                "scenario_results": scenario_results,
            }
        )

    def scenario(option: dict[str, Any], scenario_id: str) -> dict[str, Any]:
        return next(
            item
            for item in option["scenario_results"]
            if item["scenario_id"] == scenario_id
        )

    complete_pass = all(
        scenario(option, "complete-issued-prefix")["summary"][
            "all_methods_strict_retained_balance_gate_passed"
        ]
        for option in options
    )
    contiguous_pass = all(
        scenario(option, "contiguous-session-prefix-90")["summary"][
            "all_methods_strict_retained_balance_gate_passed"
        ]
        for option in options
    )
    mcar_all_replicates_pass = all(
        scenario(option, scenario_id)["aggregate"][
            "strict_retained_balance_gate_pass_count"
        ]
        == stress["mcar_replicates"]
        for option in options
        for scenario_id in ("hash-mcar-session-90", "hash-mcar-trial-90")
    )
    structured_all_pass = all(
        scenario(option, scenario_id)["summary"][
            "all_methods_strict_retained_balance_gate_passed"
        ]
        for option in options
        for scenario_id in (
            "exposure-phase-every-tenth",
            "source-correlated-10-percent",
        )
    )
    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "score_blind_synthetic_missingness_stress_complete",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "allocator_v3_sha256": sha256_file(_bound(plan, "allocator_v3")),
        "symbolic_manifest_sha256": RESOURCE.canonical_sha256(manifest),
        "audio_accessed": False,
        "audio_generated": False,
        "listener_identities_accessed": False,
        "outcome_values_generated": False,
        "outcome_values_read": False,
        "human_collection_performed": False,
        "options": options,
        "decision": {
            "v3_complete_issued_prefixes_pass": complete_pass,
            "contiguous_90_percent_session_prefixes_pass_balance": (
                contiguous_pass
            ),
            "all_mcar_replicates_preserve_strict_balance": (
                mcar_all_replicates_pass
            ),
            "all_structured_stresses_preserve_strict_balance": (
                structured_all_pass
            ),
            "scalar_90_percent_usable_rate_proves_retained_balance": False,
            "scalar_90_percent_usable_rate_proves_source_support": False,
            "mcar_mechanism_empirically_established": False,
            "v3_issued_schedule_repair_remains_valid": True,
            "post_assignment_missingness_policy_ready": False,
            "power_recalculation_required_for_structured_missingness": True,
            "missing_response_imputation_selected": False,
            "inverse_probability_weighting_selected": False,
            "replacement_assignment_selected": False,
            "exclusion_policy_selected": False,
            "allocation_policy_selected": False,
            "operational_design_selected": False,
            "listener_count_frozen": False,
            "human_collection_authorized": False,
            "recruitment_authorized": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "reason": (
                "V3 balances every complete contiguous issued prefix, and a "
                "contiguous 90% prefix retains that property. Non-contiguous "
                "session or trial loss does not preserve the strict schedule "
                "invariant deterministically, while exposure-phase and source-"
                "correlated loss show that a scalar 90% usable-rate assumption "
                "cannot prove candidate-position balance or source support."
            ),
            "next_responsible_human_decision": (
                "Decide whether the unresolved resource scale warrants a "
                "separately frozen score-blind support, missingness and "
                "exclusion policy before any operational allocation state or "
                "collection is authorized."
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
