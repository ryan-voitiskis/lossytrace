#!/usr/bin/env python3
"""Silent synthetic UI integration; no live-response or audio input surface."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/paired-rating-ui-plan.json"
PLAN_ID = "paired-rating-ui-20260905-001"
PREFIX = "globalThis.LOSSYTRACE_PAIRED_FIXTURES = Object.freeze(\n"
SUFFIX = "\n);\n"
BINDING_PATHS = {
    "paired_plan": "benchmarks/perceptual-degradation-v1/paired-rating-protocol-plan.json",
    "paired_implementation": "scripts/perceptual_degradation_paired_rating.py",
    "html": "research/listening-paired-ui/index.html",
    "style": "research/listening-paired-ui/style.css",
    "state_machine": "research/listening-paired-ui/state.js",
    "application": "research/listening-paired-ui/app.js",
    "public_fixture": "research/listening-paired-ui/fixture.js",
}
ACCESS = {
    "synthetic_execution_only": True,
    "silent_browser_ui_test_authorized": True,
    "audio_access_authorized": False,
    "playback_authorized": False,
    "human_collection_authorized": False,
    "observed_response_input_authorized": False,
    "response_persistence_authorized": False,
    "external_network_submission_authorized": False,
    "metric_execution_authorized": False,
    "no_reference_training_authorized": False,
    "public_verdict_enabled": False,
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_plan() -> dict[str, Any]:
    plan = json.loads(PLAN.read_text())
    if type(plan) is not dict or type(plan.get("schema_version")) is not int or plan["schema_version"] != 1 or plan.get("plan_id") != PLAN_ID or plan.get("state") != "silent_synthetic_ui_integration_only":
        raise ValueError("UI plan identity differs")
    if canonical_bytes(plan.get("access_boundary")) != canonical_bytes(ACCESS):
        raise ValueError("UI access boundary differs")
    bindings = plan.get("bindings")
    if type(bindings) is not dict or set(bindings) != set(BINDING_PATHS):
        raise ValueError("UI binding inventory differs")
    for name, relative in BINDING_PATHS.items():
        expected = {"path": relative, "sha256": _sha(ROOT / relative)}
        if bindings[name] != expected:
            raise ValueError("UI binding differs")
    return plan


def paired_module():
    spec = importlib.util.spec_from_file_location("paired_ui_predecessor", ROOT / BINDING_PATHS["paired_implementation"])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_plan()
    return module


def assignments() -> list[dict[str, Any]]:
    paired = paired_module()
    return [paired.synthetic_assignment("symmetric-error", 0, source) for source in (0, 1)]


def fixture_source() -> str:
    paired = paired_module()
    return PREFIX + json.dumps([paired.presentation_assignment(item) for item in assignments()], indent=2, sort_keys=True) + SUFFIX


def validate_fixture() -> None:
    if (ROOT / BINDING_PATHS["public_fixture"]).read_text() != fixture_source():
        raise ValueError("UI fixture differs from exact generated assignments")


def project_synthetic_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """An in-memory test adapter, not an observed-data collection endpoint."""
    load_plan()
    validate_fixture()
    paired = paired_module()
    allowed = {item["assignment_id"]: item for item in assignments()}
    if type(records) is not list or not 1 <= len(records) <= len(allowed):
        raise ValueError("invalid synthetic record count")
    seen, result = set(), []
    for record in records:
        paired._fields(record, {"schema_version", "state", "fixture_only", "human_collection_authorized", "presentation", "events", "final_grade_ticks_by_position"})
        if type(record["schema_version"]) is not int or record["schema_version"] != 1 or record["state"] != "synthetic_paired_ui_events_only" or record["fixture_only"] is not True or record["human_collection_authorized"] is not False:
            raise ValueError("only synthetic UI events are accepted")
        presentation = record["presentation"]
        if type(presentation) is not dict or type(presentation.get("assignment_id")) is not str:
            raise ValueError("invalid presentation")
        identifier = presentation["assignment_id"]
        if identifier not in allowed or identifier in seen:
            raise ValueError("unknown or duplicate UI assignment")
        assignment = allowed[identifier]
        if canonical_bytes(presentation) != canonical_bytes(paired.presentation_assignment(assignment)):
            raise ValueError("UI presentation is not assignment-bound")
        seen.add(identifier)
        response = paired.reduce_events(presentation, record["events"])
        final = record["final_grade_ticks_by_position"]
        paired._fields(final, {"A", "B"})
        for position, value in final.items():
            if value is not None and (type(value) is not int or not 10 <= value <= 50 or value != response["grade_ticks_by_position"][position]):
                raise ValueError("final grade is invalid or absent from the accepted event history")
        if response["trial_status"] == "submitted" and any(value is None for value in final.values()):
            raise ValueError("submitted UI pair has a blank final grade")
        target = paired.resolve_response(assignment, response)
        condition = assignment["condition_position"]
        hidden = next(p for p in ("A", "B") if p != condition)
        # Incomplete traces can contain an earlier valid grade later cleared in
        # the UI. Preserve that history, but expose only the final accepted fields.
        target["condition_grade_ticks"] = final[condition]
        target["hidden_reference_grade_ticks"] = final[hidden]
        result.append(target)
    return result


def javascript_replay(event_streams: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    node = shutil.which("node")
    if node is None:
        raise ValueError("Node.js is required for JavaScript/Python parity checks")
    program = """
const core = require(process.argv[1]);
const cases = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(cases.map(events => {
  try { return {accepted: true, response: core.reduce(events)}; }
  catch { return {accepted: false}; }
})));
"""
    process = subprocess.run([node, "-e", program, str(ROOT / BINDING_PATHS["state_machine"])], input=json.dumps(event_streams, allow_nan=False), text=True, capture_output=True, check=True, timeout=30)
    return json.loads(process.stdout)


def synthetic_records() -> list[dict[str, Any]]:
    paired = paired_module()
    records = []
    for assignment, choice in zip(assignments(), ("B", "A"), strict=True):
        records.append({
            "schema_version": 1,
            "state": "synthetic_paired_ui_events_only",
            "fixture_only": True,
            "human_collection_authorized": False,
            "presentation": paired.presentation_assignment(assignment),
            "events": [
                {"sequence": 0, "kind": "lock_choice", "position": choice},
                {"sequence": 1, "kind": "grade", "position": "A", "grade_ticks": 50},
                {"sequence": 2, "kind": "grade", "position": "B", "grade_ticks": 44},
                {"sequence": 3, "kind": "submit"},
            ],
            "final_grade_ticks_by_position": {"A": 50, "B": 44},
        })
    return records


def build_synthetic_report() -> dict[str, Any]:
    plan = load_plan()
    records = synthetic_records()
    rows = project_synthetic_records(records)
    paired = paired_module()
    javascript = javascript_replay([record["events"] for record in records])
    for record, js in zip(records, javascript, strict=True):
        python = paired.reduce_events(record["presentation"], record["events"])
        expected = {key: python[key] for key in ("forced_choice_position", "grade_ticks_by_position", "trial_status")}
        if not js["accepted"] or js["response"] != expected:
            raise ValueError("JavaScript and Python event semantics differ")
    return {
        "schema_version": 1,
        "report_id": PLAN_ID,
        "state": "silent_ui_synthetic_parity_replay_not_browser_or_listening_qualification",
        "plan_sha256": _sha(PLAN),
        "implementation_sha256": _sha(Path(__file__)),
        "bindings": plan["bindings"],
        "access_boundary": ACCESS,
        "synthetic_trials": len(rows),
        "incorrect_choices_retained": sum(row["forced_choice_correct"] is False for row in rows),
        "signed_pair_differences": [row["paired_sdg"] for row in rows],
        "signed_mean": sum(row["paired_sdg"] for row in rows) / len(rows),
        "javascript_python_parity_passed": True,
        "browser_behavior_verified_by_this_replay": False,
        "human_responses_observed": False,
        "perceptual_truth_eligible": False,
        "playback_qualified": False,
        "objective_complete": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", required=True, action="store_true")
    parser.parse_args()
    print(canonical_bytes(build_synthetic_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
