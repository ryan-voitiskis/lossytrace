#!/usr/bin/env python3
"""Compare two synthetic-only ViSQOL replay observations without perceptual claims."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _maximum_delta(first: list[float], second: list[float]) -> float:
    if len(first) != len(second):
        return math.inf
    return max((abs(left - right) for left, right in zip(first, second)), default=0.0)


def compare(
    first: dict[str, Any],
    second: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    policy = plan["cross_environment_comparison"]
    expected_cases = {case["case_id"] for case in plan["synthetic_cases"]}
    first_results = {item["case_id"]: item for item in first["results"]}
    second_results = {item["case_id"]: item for item in second["results"]}
    if set(first_results) != expected_cases or set(second_results) != expected_cases:
        raise ValueError("cross-environment case set differs")
    for replay in (first, second):
        if replay.get("metric_family") != "visqol_audio_v3_3_3":
            raise ValueError("cross-environment metric family differs")
        if replay.get("fixture_set_id") != plan["fixture_set_id"]:
            raise ValueError("cross-environment fixture set differs")
        if replay.get("synthetic_scores_are_human_truth") is not False:
            raise ValueError("synthetic score cannot be human truth")
        if replay.get("threshold_selected") is not False:
            raise ValueError("synthetic replay cannot select a threshold")

    comparison_results = []
    overall_pass = True
    for case_id in sorted(expected_cases):
        left = first_results[case_id]
        right = second_results[case_id]
        deltas = {
            "mos_lqo": abs(left["mos_lqo"] - right["mos_lqo"]),
            "similarity": abs(left["similarity"] - right["similarity"]),
            "band_similarity": _maximum_delta(
                left["band_similarity"], right["band_similarity"]
            ),
            "patch_similarity": _maximum_delta(
                left["patch_similarity"], right["patch_similarity"]
            ),
        }
        tolerance_pass = all(
            deltas[key] <= policy[f"{key}_absolute_tolerance"] for key in deltas
        )
        shape_pass = (
            left["patch_count"] == right["patch_count"]
            and len(left["band_similarity"]) == len(right["band_similarity"])
            and len(left["patch_similarity"]) == len(right["patch_similarity"])
        )
        case_pass = tolerance_pass and shape_pass
        overall_pass = overall_pass and case_pass
        comparison_results.append(
            {
                "case_id": case_id,
                "absolute_deltas": deltas,
                "shape_identical": shape_pass,
                "within_frozen_tolerance": tolerance_pass,
                "comparison_pass": case_pass,
            }
        )

    return {
        "schema_version": 1,
        "record_kind": "visqol_synthetic_cross_environment_comparison",
        "state": "cross_environment_comparison_complete",
        "metric_family": "visqol_audio_v3_3_3",
        "fixture_set_id": plan["fixture_set_id"],
        "first_environment": {
            "environment_id": policy["first_environment_id"],
            "binary_sha256": first["binary_sha256"],
        },
        "second_environment": {
            "environment_id": policy["second_environment_id"],
            "binary_sha256": second["binary_sha256"],
        },
        "frozen_absolute_tolerances": {
            key: policy[key]
            for key in (
                "mos_lqo_absolute_tolerance",
                "similarity_absolute_tolerance",
                "band_similarity_absolute_tolerance",
                "patch_similarity_absolute_tolerance",
            )
        },
        "results": comparison_results,
        "score_determinism_pass": overall_pass,
        "comparison_complete": True,
        "synthetic_scores_are_human_truth": False,
        "audibility_or_materiality_threshold_selected": False,
        "human_listening_scores_opened": False,
        "retained_audio_accessed": False,
        "retained_metric_scores_opened": False,
        "public_or_provider_audio_accessed": False,
        "sealed_labels_opened": False,
        "existing_280_case_future_subset_opened": False,
        "public_verdict_enabled": False,
        "paths_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    first = json.loads(args.first.read_text(encoding="utf-8"))
    second = json.loads(args.second.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    expected_first_sha256 = plan["cross_environment_comparison"][
        "first_replay_sha256"
    ]
    if sha256_file(args.first) != expected_first_sha256:
        raise ValueError("first-environment replay hash differs")
    report = compare(first, second, plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
