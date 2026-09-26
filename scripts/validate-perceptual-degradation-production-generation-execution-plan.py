#!/usr/bin/env python3
"""Validate synthetic-only production/generation execution authority."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXECUTION_PLAN = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/production-generation-execution-plan.json"
)
REQUIRED_BINDINGS = {
    "recipe_plan",
    "recipe_plan_validator",
    "recipe_plan_validator_tests",
    "preregistration",
    "implementation",
    "implementation_tests",
    "execution_plan_validator",
    "execution_plan_validator_tests",
}
AUTHORITY = {
    "synthetic_execution_authorized": True,
    "actual_source_audio_authorized": False,
    "provider_audio_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "human_collection_authorized": False,
    "sealed_evidence_access_authorized": False,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    return value


def validate(execution: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if execution.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if execution.get("state") != (
        "synthetic_execution_authorized_actual_audio_forbidden"
    ):
        errors.append("execution authority state differs")
    if execution.get("authority") != AUTHORITY:
        errors.append("execution authority differs")

    bindings = execution.get("bindings", {})
    if set(bindings) != REQUIRED_BINDINGS:
        errors.append("execution binding set differs")
    for binding_id, binding in bindings.items():
        relative = binding.get("path", "")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            errors.append(f"invalid repository-relative binding: {binding_id}")
            continue
        path = root / relative
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"binding hash differs: {binding_id}")

    recipe_binding = bindings.get("recipe_plan", {})
    recipe_path = root / recipe_binding.get("path", "missing")
    recipe = load_json(recipe_path) if recipe_path.is_file() else {}
    expected_cases = {
        item.get("recipe_id")
        for section in ("production_control_recipes", "codec_generation_recipes")
        for item in recipe.get(section, [])
    }
    cases = execution.get("synthetic_cases", [])
    if len(cases) != 12 or len(cases) != len(set(cases)):
        errors.append("exactly 12 unique synthetic cases are required")
    if set(cases) != expected_cases:
        errors.append("synthetic case set differs from recipe plan")

    replay = execution.get("replay_protocol", {})
    expected_replay = {
        "fresh_temporary_directories": True,
        "replay_count": 2,
        "byte_identical_reports_required": True,
        "path_free_reports_required": True,
        "timing_fields_forbidden": True,
        "retain_generated_audio": False,
        "minimum_free_disk_gib": 15,
    }
    if replay != expected_replay:
        errors.append("replay protocol differs")

    outcome = execution.get("outcome_boundary", {})
    for field in (
        "perceptual_truth_included",
        "metric_scores_included",
        "listener_responses_included",
        "codec_quality_ranking_included",
    ):
        if outcome.get(field) is not False:
            errors.append(f"outcome boundary differs: {field}")

    decision = execution.get("decision", {})
    if decision.get("implementation_hash_frozen") is not True:
        errors.append("implementation hash is not frozen")
    for field in (
        "synthetic_execution_observed",
        "actual_audio_accessed",
        "stimuli_generated",
        "perceptual_metric_executed",
        "listener_response_collected",
    ):
        if decision.get(field) is not False:
            errors.append(f"premature execution completion: {field}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=DEFAULT_EXECUTION_PLAN)
    args = parser.parse_args()
    errors = validate(load_json(args.plan))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated {args.plan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
