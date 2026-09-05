#!/usr/bin/env python3
"""Synthetic-only paired-rating reducer, role linkage and signed-target replay."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/paired-rating-protocol-plan.json"
PLAN_ID = "paired-rating-protocol-20260905-001"
POSITIONS = ("A", "B")
BINDING_PATHS = {
    "predecessor_protocol": "docs/research/perceptual-degradation-listening-protocol-20260803.md",
    "predecessor_player": "research/listening-player/player.js",
    "predecessor_response_schema": "benchmarks/perceptual-degradation-v1/listening-response-envelope.schema.json",
    "predecessor_analysis_plan": "benchmarks/perceptual-degradation-v1/listening-analysis-plan.json",
    "predecessor_analysis": "scripts/perceptual_degradation_listening_analysis.py",
    "target_semantics_plan": "benchmarks/perceptual-degradation-v1/perceptual-target-semantics-plan.json",
    "successor_protocol": "docs/research/perceptual-degradation-paired-rating-protocol-20260905.md",
}
ACCESS = {
    "synthetic_execution_only": True,
    "observed_response_input_authorized": False,
    "audio_access_authorized": False,
    "playback_authorized": False,
    "human_collection_authorized": False,
    "metric_execution_authorized": False,
    "sealed_evidence_access_authorized": False,
    "no_reference_training_authorized": False,
    "public_verdict_enabled": False,
}
CONTRACT = {
    "grade_ticks_range": [10, 50],
    "paired_sdg_range": [-4, 4],
    "paired_sdg_definition": "condition_minus_hidden_reference_grade",
    "forced_choice_before_both_ratings": True,
    "correct_choice_only_filter_allowed": False,
    "positive_difference_clipping_allowed": False,
    "missing_grade_imputation_allowed": False,
    "legacy_numeric_gates_transferred": False,
    "legacy_single_grade_migration_allowed": False,
}
SCENARIOS = ("equal-top", "symmetric-error", "choice-correlated", "common-offset", "positive-difference")


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fields(value: Any, keys: set[str]) -> None:
    if type(value) is not dict or set(value) != keys:
        raise ValueError("unexpected object fields")


def load_plan() -> dict[str, Any]:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if type(plan) is not dict or type(plan.get("schema_version")) is not int or plan["schema_version"] != 1:
        raise ValueError("paired plan identity differs")
    if plan.get("plan_id") != PLAN_ID or plan.get("state") != "synthetic_paired_rating_successor_only":
        raise ValueError("paired plan identity differs")
    # Canonical JSON distinguishes booleans from integers, unlike Python equality.
    if canonical_bytes(plan.get("access_boundary")) != canonical_bytes(ACCESS):
        raise ValueError("paired access boundary differs")
    if canonical_bytes(plan.get("rating_contract")) != canonical_bytes(CONTRACT):
        raise ValueError("paired target contract differs")
    bindings = plan.get("bindings")
    _fields(bindings, set(BINDING_PATHS))
    for name, relative in BINDING_PATHS.items():
        _fields(bindings[name], {"path", "sha256"})
        if bindings[name]["path"] != relative or bindings[name]["sha256"] != _sha(ROOT / relative):
            raise ValueError("paired predecessor binding differs")
    return plan


def synthetic_assignment(scenario: str, listener: int, source: int) -> dict[str, Any]:
    """Generate role linkage separately from the participant-facing assignment."""
    if scenario not in SCENARIOS or type(listener) is not int or type(source) is not int or not (0 <= listener < 24 and 0 <= source < 12):
        raise ValueError("only declared synthetic assignments are supported")
    token = hashlib.sha256(f"{PLAN_ID}/{scenario}/{listener}/{source}".encode()).hexdigest()[:24]
    position = POSITIONS[(listener + source) % 2]
    return {
        "state": "generated_synthetic_assignment_only",
        "fixture_only": True,
        "scenario": scenario,
        "listener_index": listener,
        "source_index": source,
        "assignment_id": "assignment-" + token,
        "trial_id": "trial-" + token,
        "participant_id": f"participant-synthetic-{listener:02d}",
        "source_group_id": f"source-synthetic-{source:02d}",
        "analysis_group_id": "group-" + scenario,
        "partition": "development",
        "candidate_ids": {p: "stimulus-" + token + p.lower() for p in POSITIONS},
        "condition_position": position,
    }


def _validate_assignment(assignment: Any) -> None:
    if type(assignment) is not dict:
        raise ValueError("invalid synthetic assignment")
    expected = synthetic_assignment(assignment.get("scenario"), assignment.get("listener_index"), assignment.get("source_index"))
    if canonical_bytes(assignment) != canonical_bytes(expected):
        raise ValueError("synthetic assignment binding differs")


def presentation_assignment(assignment: dict[str, Any]) -> dict[str, Any]:
    _validate_assignment(assignment)
    return {key: copy.deepcopy(assignment[key]) for key in ("state", "fixture_only", "assignment_id", "trial_id", "candidate_ids")}


def _position(value: Any) -> str:
    if type(value) is not str or value not in POSITIONS:
        raise ValueError("unknown candidate position")
    return value


def reduce_events(presentation: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """No audio/UI side effects. Event sequence is not proof of human participation."""
    _fields(presentation, {"state", "fixture_only", "assignment_id", "trial_id", "candidate_ids"})
    if presentation["state"] != "generated_synthetic_assignment_only" or presentation["fixture_only"] is not True:
        raise ValueError("only synthetic presentation is accepted")
    _fields(presentation["candidate_ids"], set(POSITIONS))
    if type(events) is not list or len(events) > 100:
        raise ValueError("invalid event stream")
    choice = None
    grades: dict[str, int | None] = {p: None for p in POSITIONS}
    submitted = False
    for sequence, event in enumerate(events):
        if submitted or type(event) is not dict or type(event.get("sequence")) is not int or event["sequence"] != sequence:
            raise ValueError("event sequence differs or trial already submitted")
        kind = event.get("kind")
        if kind == "lock_choice":
            _fields(event, {"sequence", "kind", "position"})
            if choice is not None:
                raise ValueError("forced choice is already locked")
            choice = _position(event["position"])
        elif kind == "grade":
            _fields(event, {"sequence", "kind", "position", "grade_ticks"})
            if choice is None:
                raise ValueError("forced choice must precede grades")
            position = _position(event["position"])
            value = event["grade_ticks"]
            if type(value) is not int or not 10 <= value <= 50:
                raise ValueError("grade must be integer ticks from 10 to 50")
            grades[position] = value
        elif kind == "submit":
            _fields(event, {"sequence", "kind"})
            if choice is None or any(value is None for value in grades.values()):
                raise ValueError("both explicit grades are required for submission")
            submitted = True
        else:
            raise ValueError("unknown event kind")
    return {
        "state": "synthetic_paired_response_only",
        "fixture_only": True,
        "assignment_id": presentation["assignment_id"],
        "trial_id": presentation["trial_id"],
        "presentation_sha256": hashlib.sha256(canonical_bytes(presentation)).hexdigest(),
        "trial_status": "submitted" if submitted else "incomplete",
        "forced_choice_position": choice,
        "grade_ticks_by_position": grades,
    }


def resolve_response(assignment: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """Condition identity comes from the exact generated assignment, never choice."""
    _validate_assignment(assignment)
    _fields(response, {"state", "fixture_only", "assignment_id", "trial_id", "presentation_sha256", "trial_status", "forced_choice_position", "grade_ticks_by_position"})
    if response["state"] != "synthetic_paired_response_only" or response["fixture_only"] is not True:
        raise ValueError("observed responses are not accepted")
    if any(response[key] != assignment[key] for key in ("assignment_id", "trial_id")):
        raise ValueError("response belongs to another assignment")
    expected_presentation = hashlib.sha256(canonical_bytes(presentation_assignment(assignment))).hexdigest()
    if response["presentation_sha256"] != expected_presentation:
        raise ValueError("response presentation binding differs")
    if response["trial_status"] not in ("submitted", "incomplete"):
        raise ValueError("unknown trial status")
    choice = response["forced_choice_position"]
    if choice is not None:
        _position(choice)
    grades = response["grade_ticks_by_position"]
    _fields(grades, set(POSITIONS))
    for value in grades.values():
        if value is not None and (type(value) is not int or not 10 <= value <= 50):
            raise ValueError("invalid grade ticks")
    if choice is None and any(value is not None for value in grades.values()):
        raise ValueError("grades without locked choice")
    complete = response["trial_status"] == "submitted"
    if complete and (choice is None or any(value is None for value in grades.values())):
        raise ValueError("submitted pair is incomplete")
    condition = assignment["condition_position"]
    hidden = next(p for p in POSITIONS if p != condition)
    return {
        **{key: assignment[key] for key in ("participant_id", "source_group_id", "analysis_group_id", "partition")},
        "condition_stimulus_id": assignment["candidate_ids"][condition],
        "hidden_reference_stimulus_id": assignment["candidate_ids"][hidden],
        "forced_choice_correct": None if choice is None else choice == condition,
        "condition_grade_ticks": grades[condition],
        "hidden_reference_grade_ticks": grades[hidden],
        "paired_sdg": (grades[condition] - grades[hidden]) / 10 if complete else None,
        "complete_pair_analysis_eligible": complete,
        "scientific_truth_eligible": False,
    }


def synthetic_events(assignment: dict[str, Any]) -> list[dict[str, Any]]:
    _validate_assignment(assignment)
    scenario = assignment["scenario"]
    condition = assignment["condition_position"]
    hidden = next(p for p in POSITIONS if p != condition)
    # Balanced error pattern independent of the alternating candidate positions.
    even = (assignment["listener_index"] // 2 + assignment["source_index"] // 2) % 2 == 0
    values = {
        "equal-top": (50, 50, even),
        "symmetric-error": (44, 50, True) if even else (50, 44, False),
        "choice-correlated": (30, 50, True) if even else (50, 40, False),
        "common-offset": (30, 40, even),
        "positive-difference": (50, 10, False),
    }
    condition_grade, hidden_grade, correct = values[scenario]
    grades = {condition: condition_grade, hidden: hidden_grade}
    return [
        {"sequence": 0, "kind": "lock_choice", "position": condition if correct else hidden},
        {"sequence": 1, "kind": "grade", "position": "A", "grade_ticks": grades["A"]},
        {"sequence": 2, "kind": "grade", "position": "B", "grade_ticks": grades["B"]},
        {"sequence": 3, "kind": "submit"},
    ]


def build_synthetic_report() -> dict[str, Any]:
    plan = load_plan()
    spec = importlib.util.spec_from_file_location("paired_numerical_solver", ROOT / BINDING_PATHS["predecessor_analysis"])
    assert spec and spec.loader
    solver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(solver)
    scenarios = []
    for scenario in SCENARIOS:
        rows, selected_offsets = [], []
        for listener in range(24):
            for source in range(12):
                assignment = synthetic_assignment(scenario, listener, source)
                response = reduce_events(presentation_assignment(assignment), synthetic_events(assignment))
                rows.append(resolve_response(assignment, response))
                selected_offsets.append((response["grade_ticks_by_position"][response["forced_choice_position"]] - 50) / 10)
        fitted = solver._fit_gaussian(rows, lambda row: row["paired_sdg"], "sdg")
        correct = [row["paired_sdg"] for row in rows if row["forced_choice_correct"]]
        scenarios.append({
            "synthetic_scenario": scenario,
            "listeners": fitted["listeners"],
            "sources": fitted["sources"],
            "complete_pairs": len(rows),
            "incorrect_choices_retained": sum(not row["forced_choice_correct"] for row in rows),
            "positive_differences_retained": sum(row["paired_sdg"] > 0 for row in rows),
            "signed_paired_mean": round(sum(row["paired_sdg"] for row in rows) / len(rows), 10),
            "signed_crossed_effects_estimate": round(fitted["estimate"], 10),
            "counterfactual_selected_grade_offset_mean": round(sum(selected_offsets) / len(rows), 10),
            "counterfactual_correct_only_mean": round(sum(correct) / len(correct), 10) if correct else None,
            "counterfactual_nonpositive_clipped_mean": round(sum(min(0, row["paired_sdg"]) for row in rows) / len(rows), 10),
        })
    return {
        "schema_version": 1,
        "report_id": PLAN_ID,
        "state": "synthetic_paired_rating_replay_not_scientific_validation",
        "plan_sha256": _sha(PLAN),
        "implementation_sha256": _sha(Path(__file__)),
        "bindings": plan["bindings"],
        "access_boundary": ACCESS,
        "scenarios": scenarios,
        "model_scope": "numerical_solver_integration_only_variance_and_intervals_not_validated_for_paired_target",
        "counterfactuals_are_analysis_witnesses_not_accepted_estimators": True,
        "legacy_thresholds_applied": False,
        "human_responses_observed": False,
        "scientific_gate_evaluated": False,
        "live_player_implemented": False,
        "objective_complete": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.parse_args()
    print(canonical_bytes(build_synthetic_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
