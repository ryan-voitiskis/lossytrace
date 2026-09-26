#!/usr/bin/env python3
"""Audit the v3 score-blind allocator on the symbolic resource frontier."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "listening-allocation-v3-symbolic-audit-plan.json"
)
PLAN_ID = "perceptual-degradation-listening-allocation-v3-symbolic-audit-20260814-001"
REPORT_ID = PLAN_ID


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ALLOCATOR = _load_module(
    "listening_allocation_v3_audit_target",
    ROOT / "scripts/perceptual_degradation_listening_allocation_v3.py",
)
RESOURCE = _load_module(
    "listening_resource_frontier_for_v3_audit",
    ROOT / "scripts/perceptual_degradation_listening_resource_frontier.py",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def validate_plan(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != (
        "score_blind_symbolic_allocator_successor_audit_no_operational_selection"
    ):
        errors.append("plan state differs")
    expected_bindings = {
        "allocator_v1",
        "allocator_v2",
        "allocator_v3",
        "manifest_v2_schema",
        "resource_frontier_plan",
        "resource_frontier_report",
        "symbolic_manifest_builder",
        "listening_protocol",
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

    policy = plan.get("policy_contract", {})
    expected_policy = {
        "allocation_policy_id": ALLOCATOR.POLICY_ID,
        "manifest_schema_version": 2,
        "assignment_schema_version": 3,
        "trial_order_seeded_and_score_blind": True,
        "candidate_order_seeded_and_score_blind": True,
        "candidate_rotation_uses_per_trial_exposure_ordinal": True,
        "trial_block_order_rotates_by_exposure_cycle": True,
        "trial_count_divisible_by_trial_limit_required": True,
        "contiguous_post_eligibility_allocation_indices_required": True,
        "maximum_trial_exposure_range_at_every_contiguous_prefix": 1,
        "maximum_trial_block_position_range_at_every_contiguous_prefix": 1,
        "maximum_candidate_position_range_at_every_contiguous_prefix": 1,
        "missingness_or_post_assignment_exclusion_balance_proven": False,
        "operational_policy_selected": False,
    }
    if policy != expected_policy:
        errors.append("policy contract differs")

    expected_grid = (
        ("sources120-subtle3-mushra3", 3, 3, 765, 840),
        ("sources120-subtle5-mushra5", 5, 5, 496, 600),
        ("sources120-subtle8-mushra6", 8, 6, 345, 360),
        ("sources120-subtle15-mushra6", 15, 6, 227, 240),
    )
    observed_grid = tuple(
        (
            row.get("option_id"),
            row.get("subtle_trial_limit"),
            row.get("mushra_trial_limit"),
            row.get("raw_minimum_eligible_prefix"),
            row.get("cycle_rounded_eligible_prefix"),
        )
        for row in plan.get("audit_grid", [])
    )
    if observed_grid != expected_grid:
        errors.append("audit grid differs")
    for key, value in plan.get("claim_boundary", {}).items():
        if value is not False:
            errors.append(f"claim boundary must remain false: {key}")
    return errors


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    resource_plan = load_json(_bound(plan, "resource_frontier_plan"))
    resource_report = load_json(_bound(plan, "resource_frontier_report"))
    if (
        resource_report["decision"]["qualified_source_group_count"] != 0
        or resource_report["decision"]["allocated_source_group_count"] != 0
    ):
        raise ValueError("resource frontier unexpectedly qualifies source groups")
    manifest = RESOURCE.make_symbolic_manifest(resource_plan)
    manifest_errors = ALLOCATOR.validate_manifest(manifest)
    if manifest_errors:
        raise ValueError("; ".join(manifest_errors))
    seed = resource_plan["symbolic_fixture"]["allocation_seed"]
    resource_rows = {row["option_id"]: row for row in resource_report["frontier"]}

    frontier = []
    for row in plan["audit_grid"]:
        resource_row = resource_rows.get(row["option_id"])
        if resource_row is None:
            raise ValueError(f"resource row missing: {row['option_id']}")
        if (
            resource_row[
                "minimum_eligible_listener_slots_per_stratum_device_partition"
            ]
            != row["raw_minimum_eligible_prefix"]
            or resource_row[
                "cycle_rounded_eligible_listener_slots_per_stratum_device_partition"
            ]
            != row["cycle_rounded_eligible_prefix"]
        ):
            raise ValueError(f"resource prefix differs: {row['option_id']}")
        audit = ALLOCATOR.audit_prefixes(
            manifest,
            row["cycle_rounded_eligible_prefix"],
            [
                row["raw_minimum_eligible_prefix"],
                row["cycle_rounded_eligible_prefix"],
            ],
            seed,
            subtle_trial_limit=row["subtle_trial_limit"],
            mushra_trial_limit=row["mushra_trial_limit"],
        )
        frontier.append(
            {
                "option_id": row["option_id"],
                "subtle_trial_limit": row["subtle_trial_limit"],
                "mushra_trial_limit": row["mushra_trial_limit"],
                "raw_minimum_eligible_prefix": row[
                    "raw_minimum_eligible_prefix"
                ],
                "cycle_rounded_eligible_prefix": row[
                    "cycle_rounded_eligible_prefix"
                ],
                "v2_raw_minimum_prefix_balance_passed": resource_row[
                    "minimum_eligible_prefix_balance_passes"
                ],
                "v2_cycle_rounded_prefix_balance_passed": resource_row[
                    "cycle_rounded_eligible_prefix_balance_passes"
                ],
                "v3_prefix_audit": audit,
                "operational_policy_selected": False,
            }
        )

    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "score_blind_symbolic_allocator_successor_audit_complete",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "allocator_v3_sha256": sha256_file(_bound(plan, "allocator_v3")),
        "symbolic_manifest_sha256": RESOURCE.canonical_sha256(manifest),
        "symbolic_manifest_source_group_count": 120,
        "symbolic_manifest_stimulus_count": len(manifest["stimuli"]),
        "symbolic_manifest_trial_count": len(manifest["trials"]),
        "audio_accessed": False,
        "audio_generated": False,
        "listener_responses_opened": False,
        "human_collection_performed": False,
        "frontier": frontier,
        "decision": {
            "v2_all_raw_prefixes_passed": all(
                row["v2_raw_minimum_prefix_balance_passed"] for row in frontier
            ),
            "v2_all_cycle_rounded_prefixes_passed": all(
                row["v2_cycle_rounded_prefix_balance_passed"]
                for row in frontier
            ),
            "v3_all_audited_contiguous_prefixes_passed": all(
                row["v3_prefix_audit"]["all_prefixes_balance_gate_passed"]
                for row in frontier
            ),
            "v3_maximum_trial_exposure_range_across_all_audits": max(
                row["v3_prefix_audit"][
                    "maximum_trial_exposure_range_across_all_prefixes"
                ]
                for row in frontier
            ),
            "v3_maximum_trial_block_position_range_across_all_audits": max(
                row["v3_prefix_audit"][
                    "maximum_trial_block_position_range_across_all_prefixes"
                ]
                for row in frontier
            ),
            "v3_maximum_candidate_position_range_across_all_audits": max(
                row["v3_prefix_audit"][
                    "maximum_candidate_position_range_across_all_prefixes"
                ]
                for row in frontier
            ),
            "trial_and_candidate_position_scheduling_technically_repaired": True,
            "raw_minimum_prefix_requires_cycle_rounding_for_schedule_balance": False,
            "missingness_or_post_assignment_exclusion_balance_proven": False,
            "concurrent_append_only_allocation_state_implemented": False,
            "restart_recovery_implemented": False,
            "qualified_source_group_count": 0,
            "allocated_source_group_count": 0,
            "allocation_policy_selected": False,
            "operational_design_selected": False,
            "listener_count_frozen": False,
            "human_collection_authorized": False,
            "recruitment_authorized": False,
            "no_reference_work_eligible": False,
            "public_verdict_enabled": False,
            "reason": (
                "The v3 construction keeps trial-exposure, within-block trial-"
                "position and candidate-position ranges at or below one for "
                "every audited contiguous prefix, including all raw power "
                "minimums. This repairs the v2 scheduling defect without "
                "cycle rounding, but it does not select an operational policy "
                "or prove balance after missingness, exclusion, concurrency "
                "or restart."
            ),
            "next_responsible_human_decision": (
                "Decide whether the unresolved listening-resource scale "
                "warrants a separately frozen operational allocation-state "
                "and missingness-policy successor before any collection."
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
