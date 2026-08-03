#!/usr/bin/env python3
"""Validate a score-blind listening manifest and make concealed assignments."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


MAX_SUBTLE_TRIALS = 15
MAX_MUSHRA_TRIALS = 6
MAX_MUSHRA_CANDIDATES = 11


def _digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def _ordered(values: list[str], *seed_parts: str) -> list[str]:
    return sorted(values, key=lambda value: _digest(*seed_parts, value))


def _rotated(values: list[str], offset: int) -> list[str]:
    if not values:
        return []
    normalized = offset % len(values)
    return values[normalized:] + values[:normalized]


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors = []
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if manifest.get("state") != "score_blind_preparation":
        errors.append("manifest must remain in score-blind preparation")
    if manifest.get("human_collection_authorized") is not False:
        errors.append("human collection must remain unauthorized")
    if manifest.get("condition_recipes_visible_to_listener") is not False:
        errors.append("condition recipes must remain concealed")

    stimuli = manifest.get("stimuli", [])
    by_id = {item.get("stimulus_id"): item for item in stimuli}
    if None in by_id or len(by_id) != len(stimuli):
        errors.append("stimulus IDs must be present and unique")
    for item in stimuli:
        stimulus_id = item.get("stimulus_id", "<missing>")
        if item.get("channel_count") == 1 and item.get("channel_map") != "M":
            errors.append(f"{stimulus_id}: mono channel map must be M")
        if item.get("channel_count") == 2 and item.get("channel_map") != "L_R":
            errors.append(f"{stimulus_id}: stereo channel map must be L_R")
        if item.get("active_seconds", 0) > item.get("duration_seconds", 0):
            errors.append(f"{stimulus_id}: active duration exceeds duration")
        controlled = item.get("controlled_codec_intervention")
        condition_class = item.get("condition_class")
        if controlled is True and condition_class not in {
            "controlled_codec",
            "transparent_codec",
        }:
            errors.append(f"{stimulus_id}: controlled codec flag conflicts")
        if condition_class in {"controlled_codec", "transparent_codec"} and controlled is not True:
            errors.append(f"{stimulus_id}: codec class requires controlled intervention")

    trials = manifest.get("trials", [])
    trial_ids = [item.get("trial_id") for item in trials]
    if None in trial_ids or len(set(trial_ids)) != len(trial_ids):
        errors.append("trial IDs must be present and unique")
    for trial in trials:
        trial_id = trial.get("trial_id", "<missing>")
        reference = by_id.get(trial.get("visible_reference_id"))
        candidates = [by_id.get(value) for value in trial.get("candidate_ids", [])]
        if reference is None or any(item is None for item in candidates):
            errors.append(f"{trial_id}: trial refers to an unknown stimulus")
            continue
        all_items = [reference, *candidates]
        source_groups = {item["source_group_id"] for item in all_items}
        partitions = {item["partition"] for item in all_items}
        if len(source_groups) != 1:
            errors.append(f"{trial_id}: stimuli cross source groups")
        if partitions != {trial.get("partition")}:
            errors.append(f"{trial_id}: stimuli cross partitions")
        if reference.get("role") != "reference":
            errors.append(f"{trial_id}: visible reference role differs")
        roles = [item["role"] for item in candidates]
        if roles.count("hidden_reference") != 1:
            errors.append(f"{trial_id}: exactly one hidden reference is required")
        method = trial.get("method")
        if method == "subtle":
            if len(candidates) != 2 or roles.count("condition") != 1:
                errors.append(f"{trial_id}: subtle trial requires hidden reference and condition")
            if any(item.get("active_seconds", 0) < 4 for item in all_items):
                errors.append(f"{trial_id}: subtle active duration is below 4 seconds")
        elif method == "mushra":
            if len(candidates) > MAX_MUSHRA_CANDIDATES:
                errors.append(f"{trial_id}: too many MUSHRA candidates")
            if roles.count("anchor_low") != 1 or roles.count("anchor_mid") != 1:
                errors.append(f"{trial_id}: MUSHRA requires low and mid anchors")
            if any(item.get("active_seconds", 0) < 8 for item in all_items):
                errors.append(f"{trial_id}: MUSHRA active duration is below 8 seconds")
        else:
            errors.append(f"{trial_id}: unknown listening method")
    return errors


def allocate(
    manifest: dict[str, Any],
    participant_key: str,
    allocation_seed: str,
    allocation_index: int = 0,
) -> dict[str, Any]:
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    if not participant_key or not allocation_seed:
        raise ValueError("participant key and allocation seed must be non-empty")
    if allocation_index < 0:
        raise ValueError("allocation index must be non-negative")
    assignment_id = "assignment-" + _digest(
        allocation_seed, participant_key, str(allocation_index)
    )[:24]
    by_method: dict[str, list[dict[str, Any]]] = {"subtle": [], "mushra": []}
    for trial in manifest["trials"]:
        candidate_base = _ordered(
            list(trial["candidate_ids"]),
            allocation_seed,
            trial["trial_id"],
            "candidate-order",
        )
        candidate_offset = allocation_index + int(
            _digest(allocation_seed, trial["trial_id"], "position-phase")[:8], 16
        )
        candidates = _rotated(candidate_base, candidate_offset)
        by_method[trial["method"]].append(
            {
                "trial_id": trial["trial_id"],
                "method": trial["method"],
                "visible_reference_id": trial["visible_reference_id"],
                "candidate_positions": [
                    {"position": index + 1, "stimulus_id": stimulus_id}
                    for index, stimulus_id in enumerate(candidates)
                ],
            }
        )
    limits = {"subtle": MAX_SUBTLE_TRIALS, "mushra": MAX_MUSHRA_TRIALS}
    blocks = []
    for method in ("subtle", "mushra"):
        base_ids = _ordered(
            [item["trial_id"] for item in by_method[method]],
            allocation_seed,
            method,
            "trial-order",
        )
        ordered_ids = _rotated(base_ids, allocation_index)[: limits[method]]
        by_trial = {item["trial_id"]: item for item in by_method[method]}
        if ordered_ids:
            blocks.append(
                {
                    "method": method,
                    "trials": [by_trial[trial_id] for trial_id in ordered_ids],
                }
            )
    return {
        "schema_version": 1,
        "state": "synthetic_or_unauthorized_assignment_only",
        "manifest_id": manifest["manifest_id"],
        "assignment_id": assignment_id,
        "allocation_index": allocation_index,
        "participant_key_included": False,
        "condition_recipes_included": False,
        "metric_scores_included": False,
        "responses_included": False,
        "blocks": blocks,
    }


def audit_balance(
    manifest: dict[str, Any], participant_count: int, allocation_seed: str
) -> dict[str, Any]:
    if participant_count <= 0:
        raise ValueError("participant count must be positive")
    trial_exposures: dict[str, int] = {}
    position_counts: dict[str, dict[str, int]] = {}
    for allocation_index in range(participant_count):
        result = allocate(
            manifest,
            f"synthetic-participant-{allocation_index:06d}",
            allocation_seed,
            allocation_index,
        )
        for block in result["blocks"]:
            for trial in block["trials"]:
                trial_id = trial["trial_id"]
                trial_exposures[trial_id] = trial_exposures.get(trial_id, 0) + 1
                for positioned in trial["candidate_positions"]:
                    stimulus_id = positioned["stimulus_id"]
                    key = f"position_{positioned['position']}"
                    counts = position_counts.setdefault(stimulus_id, {})
                    counts[key] = counts.get(key, 0) + 1
    exposure_values = list(trial_exposures.values())
    return {
        "schema_version": 1,
        "state": "synthetic_balance_audit_no_responses",
        "participant_count": participant_count,
        "trial_exposure_min": min(exposure_values),
        "trial_exposure_max": max(exposure_values),
        "trial_exposure_range": max(exposure_values) - min(exposure_values),
        "trial_exposures": dict(sorted(trial_exposures.items())),
        "candidate_position_counts": {
            key: dict(sorted(value.items()))
            for key, value in sorted(position_counts.items())
        },
        "responses_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--participant-key", required=True)
    parser.add_argument("--allocation-index", type=int, required=True)
    parser.add_argument("--allocation-seed", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = allocate(
        manifest,
        args.participant_key,
        args.allocation_seed,
        args.allocation_index,
    )
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit(f"refusing to replace output: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"assignment_id": result["assignment_id"], "status": result["state"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
