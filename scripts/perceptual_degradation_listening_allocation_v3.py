#!/usr/bin/env python3
"""Allocate score-blind v2 listening manifests with prefix balance."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, TypeVar


SCRIPT_DIR = Path(__file__).resolve().parent
V2_PATH = SCRIPT_DIR / "perceptual_degradation_listening_allocation_v2.py"
SPEC = importlib.util.spec_from_file_location("listening_allocation_v2", V2_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load v2 listening allocator")
V2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V2)

POLICY_ID = "prefix-balanced-score-blind-v3"
MAX_SUBTLE_TRIALS = V2.V1.MAX_SUBTLE_TRIALS
MAX_MUSHRA_TRIALS = V2.V1.MAX_MUSHRA_TRIALS
T = TypeVar("T")


def _digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def _ordered(values: list[str], *seed_parts: str) -> list[str]:
    return sorted(values, key=lambda value: _digest(*seed_parts, value))


def _rotated(values: list[T], offset: int) -> list[T]:
    if not values:
        return []
    normalized = offset % len(values)
    return values[normalized:] + values[:normalized]


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    return V2.validate_manifest(manifest)


def _validate_limits(
    manifest: dict[str, Any],
    subtle_trial_limit: int,
    mushra_trial_limit: int,
) -> list[str]:
    errors: list[str] = []
    limits = {
        "subtle": (subtle_trial_limit, MAX_SUBTLE_TRIALS),
        "mushra": (mushra_trial_limit, MAX_MUSHRA_TRIALS),
    }
    trial_counts = {
        method: sum(
            trial.get("method") == method
            for trial in manifest.get("trials", [])
        )
        for method in limits
    }
    for method, (limit, maximum) in limits.items():
        if isinstance(limit, bool) or not isinstance(limit, int):
            errors.append(f"{method} trial limit must be an integer")
            continue
        if limit < 0 or limit > maximum:
            errors.append(f"{method} trial limit must be between 0 and {maximum}")
        elif limit > trial_counts[method]:
            errors.append(f"{method} trial limit exceeds available trials")
        elif limit > 0 and trial_counts[method] % limit != 0:
            errors.append(f"{method} trial count must be divisible by its limit")
    if subtle_trial_limit == 0 and mushra_trial_limit == 0:
        errors.append("at least one trial method must be enabled")
    return errors


def _prepare(
    manifest: dict[str, Any],
    allocation_seed: str,
    subtle_trial_limit: int,
    mushra_trial_limit: int,
) -> dict[str, Any]:
    errors = validate_manifest(manifest)
    errors.extend(
        _validate_limits(manifest, subtle_trial_limit, mushra_trial_limit)
    )
    if errors:
        raise ValueError("; ".join(errors))
    if not isinstance(allocation_seed, str) or not allocation_seed:
        raise ValueError("allocation seed must be a non-empty string")

    trials_by_id = {trial["trial_id"]: trial for trial in manifest["trials"]}
    trial_order: dict[str, list[str]] = {}
    candidate_order: dict[str, list[str]] = {}
    candidate_phase: dict[str, int] = {}
    for method in ("subtle", "mushra"):
        trial_order[method] = _ordered(
            [
                trial["trial_id"]
                for trial in manifest["trials"]
                if trial["method"] == method
            ],
            allocation_seed,
            method,
            "trial-slot-order-v3",
        )
        for trial_id in trial_order[method]:
            candidate_order[trial_id] = _ordered(
                list(trials_by_id[trial_id]["candidate_ids"]),
                allocation_seed,
                trial_id,
                "candidate-order-v3",
            )
            candidate_phase[trial_id] = int(
                _digest(
                    allocation_seed,
                    trial_id,
                    "candidate-position-phase-v3",
                )[:8],
                16,
            )
    return {
        "manifest_id": manifest["manifest_id"],
        "trials_by_id": trials_by_id,
        "trial_order": trial_order,
        "candidate_order": candidate_order,
        "candidate_phase": candidate_phase,
        "trial_limits": {
            "subtle": subtle_trial_limit,
            "mushra": mushra_trial_limit,
        },
    }


def _allocate_prepared(
    prepared: dict[str, Any],
    participant_key: str,
    allocation_seed: str,
    allocation_index: int,
) -> dict[str, Any]:
    if not isinstance(participant_key, str) or not participant_key:
        raise ValueError("participant key must be a non-empty string")
    if (
        isinstance(allocation_index, bool)
        or not isinstance(allocation_index, int)
        or allocation_index < 0
    ):
        raise ValueError("allocation index must be a non-negative integer")

    limits = prepared["trial_limits"]
    assignment_id = "assignment-" + _digest(
        POLICY_ID,
        allocation_seed,
        participant_key,
        str(allocation_index),
        str(limits["subtle"]),
        str(limits["mushra"]),
    )[:24]
    blocks: list[dict[str, Any]] = []
    for method in ("subtle", "mushra"):
        limit = limits[method]
        if limit == 0:
            continue
        order = prepared["trial_order"][method]
        trial_count = len(order)
        block_trials: list[dict[str, Any]] = []
        for local_slot in range(limit):
            global_slot = allocation_index * limit + local_slot
            order_index = global_slot % trial_count
            exposure_ordinal = global_slot // trial_count
            trial_id = order[order_index]
            trial = prepared["trials_by_id"][trial_id]
            candidates = _rotated(
                prepared["candidate_order"][trial_id],
                prepared["candidate_phase"][trial_id] + exposure_ordinal,
            )
            block_trials.append(
                {
                    "trial_id": trial_id,
                    "method": method,
                    "visible_reference_id": trial["visible_reference_id"],
                    "candidate_positions": [
                        {"position": index + 1, "stimulus_id": stimulus_id}
                        for index, stimulus_id in enumerate(candidates)
                    ],
                }
            )
        participants_per_trial_exposure_cycle = trial_count // limit
        trial_block_position_cycle = (
            allocation_index // participants_per_trial_exposure_cycle
        )
        blocks.append(
            {
                "method": method,
                "trial_limit": limit,
                "trials": _rotated(block_trials, trial_block_position_cycle),
            }
        )
    return {
        "schema_version": 3,
        "manifest_schema_version": 2,
        "state": "synthetic_or_unauthorized_assignment_only",
        "allocation_policy_id": POLICY_ID,
        "manifest_id": prepared["manifest_id"],
        "assignment_id": assignment_id,
        "allocation_index": allocation_index,
        "trial_limits": dict(limits),
        "contiguous_post_eligibility_indexing_required": True,
        "operational_policy_selected": False,
        "human_collection_authorized": False,
        "participant_key_included": False,
        "condition_recipes_included": False,
        "metric_scores_included": False,
        "responses_included": False,
        "blocks": blocks,
    }


def allocate(
    manifest: dict[str, Any],
    participant_key: str,
    allocation_seed: str,
    allocation_index: int,
    *,
    subtle_trial_limit: int,
    mushra_trial_limit: int,
) -> dict[str, Any]:
    prepared = _prepare(
        manifest,
        allocation_seed,
        subtle_trial_limit,
        mushra_trial_limit,
    )
    return _allocate_prepared(
        prepared,
        participant_key,
        allocation_seed,
        allocation_index,
    )


def _empty_balance_state(prepared: dict[str, Any]) -> dict[str, Any]:
    exposures = {
        trial_id: 0
        for method in ("subtle", "mushra")
        for trial_id in prepared["trial_order"][method]
    }
    candidate_positions = {
        trial_id: {
            stimulus_id: [0] * len(prepared["candidate_order"][trial_id])
            for stimulus_id in prepared["candidate_order"][trial_id]
        }
        for trial_id in exposures
    }
    trial_block_positions = {
        trial_id: [0] * prepared["trial_limits"][method]
        for method in ("subtle", "mushra")
        for trial_id in prepared["trial_order"][method]
    }
    return {
        "exposures": exposures,
        "candidate_positions": candidate_positions,
        "trial_block_positions": trial_block_positions,
    }


def _update_balance_state(
    state: dict[str, Any], assignment: dict[str, Any]
) -> None:
    for block in assignment["blocks"]:
        for block_position, trial in enumerate(block["trials"]):
            state["exposures"][trial["trial_id"]] += 1
            state["trial_block_positions"][trial["trial_id"]][block_position] += 1
            for item in trial["candidate_positions"]:
                state["candidate_positions"][trial["trial_id"]][
                    item["stimulus_id"]
                ][
                    item["position"] - 1
                ] += 1


def _balance_summary(
    prepared: dict[str, Any], state: dict[str, Any], participant_count: int
) -> dict[str, Any]:
    by_method: dict[str, Any] = {}
    for method in ("subtle", "mushra"):
        trial_ids = prepared["trial_order"][method]
        values = [state["exposures"][trial_id] for trial_id in trial_ids]
        trial_block_position_ranges = [
            max(state["trial_block_positions"][trial_id], default=0)
            - min(state["trial_block_positions"][trial_id], default=0)
            for trial_id in trial_ids
        ]
        candidate_position_ranges = [
            max(state["candidate_positions"][trial_id][stimulus_id])
            - min(state["candidate_positions"][trial_id][stimulus_id])
            for trial_id in trial_ids
            for stimulus_id in prepared["candidate_order"][trial_id]
        ]
        by_method[method] = {
            "trial_limit": prepared["trial_limits"][method],
            "trial_exposure_min": min(values, default=0),
            "trial_exposure_max": max(values, default=0),
            "trial_exposure_range": (
                max(values, default=0) - min(values, default=0)
            ),
            "trial_block_position_maximum_range": max(
                trial_block_position_ranges, default=0
            ),
            "candidate_position_maximum_range": max(
                candidate_position_ranges, default=0
            ),
        }
    return {
        "participant_count": participant_count,
        "methods": by_method,
        "trial_exposure_maximum_range": max(
            value["trial_exposure_range"] for value in by_method.values()
        ),
        "trial_block_position_maximum_range": max(
            value["trial_block_position_maximum_range"]
            for value in by_method.values()
        ),
        "candidate_position_maximum_range": max(
            value["candidate_position_maximum_range"]
            for value in by_method.values()
        ),
        "balance_gate_passed": all(
            value["trial_exposure_range"] <= 1
            and value["trial_block_position_maximum_range"] <= 1
            and value["candidate_position_maximum_range"] <= 1
            for value in by_method.values()
        ),
        "responses_included": False,
    }


def audit_prefixes(
    manifest: dict[str, Any],
    maximum_participant_count: int,
    checkpoints: list[int],
    allocation_seed: str,
    *,
    subtle_trial_limit: int,
    mushra_trial_limit: int,
) -> dict[str, Any]:
    if (
        isinstance(maximum_participant_count, bool)
        or not isinstance(maximum_participant_count, int)
        or maximum_participant_count <= 0
    ):
        raise ValueError("maximum participant count must be a positive integer")
    if (
        not checkpoints
        or any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value <= 0
            or value > maximum_participant_count
            for value in checkpoints
        )
    ):
        raise ValueError("checkpoints must fall within the audited prefix")
    prepared = _prepare(
        manifest,
        allocation_seed,
        subtle_trial_limit,
        mushra_trial_limit,
    )
    checkpoint_set = set(checkpoints)
    if len(checkpoint_set) != len(checkpoints):
        raise ValueError("checkpoints must be unique")

    state = _empty_balance_state(prepared)
    checkpoint_summaries: dict[str, Any] = {}
    all_prefixes_passed = True
    maximum_trial_exposure_range = 0
    maximum_trial_block_position_range = 0
    maximum_candidate_position_range = 0
    for allocation_index in range(maximum_participant_count):
        assignment = _allocate_prepared(
            prepared,
            f"symbolic-participant-{allocation_index:06d}",
            allocation_seed,
            allocation_index,
        )
        _update_balance_state(state, assignment)
        participant_count = allocation_index + 1
        summary = _balance_summary(prepared, state, participant_count)
        all_prefixes_passed = all_prefixes_passed and summary["balance_gate_passed"]
        maximum_trial_exposure_range = max(
            maximum_trial_exposure_range,
            summary["trial_exposure_maximum_range"],
        )
        maximum_trial_block_position_range = max(
            maximum_trial_block_position_range,
            summary["trial_block_position_maximum_range"],
        )
        maximum_candidate_position_range = max(
            maximum_candidate_position_range,
            summary["candidate_position_maximum_range"],
        )
        if participant_count in checkpoint_set:
            checkpoint_summaries[str(participant_count)] = summary

    return {
        "schema_version": 1,
        "state": "score_blind_prefix_balance_audit_no_responses",
        "allocation_policy_id": POLICY_ID,
        "maximum_participant_count": maximum_participant_count,
        "prefixes_audited": maximum_participant_count,
        "trial_limits": dict(prepared["trial_limits"]),
        "maximum_trial_exposure_range_across_all_prefixes": (
            maximum_trial_exposure_range
        ),
        "maximum_trial_block_position_range_across_all_prefixes": (
            maximum_trial_block_position_range
        ),
        "maximum_candidate_position_range_across_all_prefixes": (
            maximum_candidate_position_range
        ),
        "all_prefixes_balance_gate_passed": all_prefixes_passed,
        "checkpoint_summaries": checkpoint_summaries,
        "responses_included": False,
    }


def audit_balance(
    manifest: dict[str, Any],
    participant_count: int,
    allocation_seed: str,
    *,
    subtle_trial_limit: int,
    mushra_trial_limit: int,
) -> dict[str, Any]:
    audit = audit_prefixes(
        manifest,
        participant_count,
        [participant_count],
        allocation_seed,
        subtle_trial_limit=subtle_trial_limit,
        mushra_trial_limit=mushra_trial_limit,
    )
    return audit["checkpoint_summaries"][str(participant_count)]


def serialize_assignment(result: dict[str, Any], output_format: str) -> str:
    return V2.serialize_assignment(result, output_format)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--participant-key", required=True)
    parser.add_argument("--allocation-index", type=int, required=True)
    parser.add_argument("--allocation-seed", required=True)
    parser.add_argument("--subtle-trial-limit", type=int, required=True)
    parser.add_argument("--mushra-trial-limit", type=int, required=True)
    parser.add_argument("--format", choices=("json", "javascript"), default="json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = allocate(
        manifest,
        args.participant_key,
        args.allocation_seed,
        args.allocation_index,
        subtle_trial_limit=args.subtle_trial_limit,
        mushra_trial_limit=args.mushra_trial_limit,
    )
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit(f"refusing to replace output: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialize_assignment(result, args.format), encoding="utf-8")
    print(
        json.dumps(
            {
                "allocation_policy_id": result["allocation_policy_id"],
                "assignment_id": result["assignment_id"],
                "status": result["state"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
