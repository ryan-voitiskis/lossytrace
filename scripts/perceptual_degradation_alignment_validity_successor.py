#!/usr/bin/env python3
"""Bound synthetic regression of explicit alignment-correlation validity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import perceptual_degradation_alignment_v3 as successor
import perceptual_degradation_channel_normalization_boundary as fixtures
import perceptual_degradation_oracle as oracle


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/alignment-validity-successor-plan.json"
PLAN_SHA = "717e03b6c9e45c1ce57c3298b6a921576a771f96ee7d1fd07405b8e5c19a8a29"
BINDINGS = {
    "mono_alignment": "scripts/perceptual_degradation_alignment.py",
    "channel_alignment": "scripts/perceptual_degradation_alignment_v2.py",
    "topology_freeze": "benchmarks/perceptual-degradation-v1/alignment-topology-freeze.json",
    "score_free_oracle": "scripts/perceptual_degradation_oracle.py",
    "channel_fixture_implementation": "scripts/perceptual_degradation_channel_normalization_boundary.py",
    "channel_boundary_report": "research/toolchains/evidence/perceptual-degradation-channel-normalization-boundary-synthetic-20260907-001.json",
}


def load_plan() -> dict[str, Any]:
    if fixtures.sha(PLAN) != PLAN_SHA:
        raise ValueError("successor plan bytes differ")
    plan = json.loads(PLAN.read_text())
    if set(plan["bindings"]) != set(BINDINGS):
        raise ValueError("successor binding inventory differs")
    for key, relative in BINDINGS.items():
        if plan["bindings"][key] != {"path": relative, "sha256": fixtures.sha(ROOT / relative)}:
            raise ValueError("successor predecessor binding differs")
    for module in (successor, fixtures, oracle, successor.legacy, successor.topology):
        if Path(module.__file__).resolve() != (ROOT / "scripts" / f"{module.__name__}.py").resolve():
            raise ValueError("loaded implementation location differs")
    fixtures.load_plan()
    return plan


def align(reference: list[list[float]], test: list[list[float]], identity: str) -> dict[str, Any]:
    fixtures.reserve()
    before = ([channel[:] for channel in reference], [channel[:] for channel in test])
    channel_map = ["M"] if len(reference) == 1 else ["L", "R"]
    result = successor.align_channels(reference_channels=reference, test_channels=test,
                                      reference_channel_map=channel_map, test_channel_map=channel_map,
                                      sample_rate_hz=2000, recipe_identity=identity)
    if before != (reference, test):
        raise ValueError("successor changed input samples")
    return result


def projection(result: dict[str, Any]) -> dict[str, Any]:
    try:
        oracle.assemble_score_free(result)
    except ValueError as error:
        rejection = str(error)
    else:
        raise ValueError("legacy oracle unexpectedly accepted successor")
    return fixtures.formatted({
        "status": result["status"], "reasons": result["support"]["reasons"],
        "summary": result["alignment"]["summary"],
        "channels": [{"channel": channel["channel"], "status": channel["status"], "reasons": channel["reasons"],
                      "correlation": channel["diagnostics"]["correlation"], "gain": channel["diagnostics"]["gain"],
                      "drift": channel["diagnostics"]["drift"], "structural": channel["diagnostics"]["structural"]}
                     for channel in result["alignment"]["channels"]],
        "legacy_oracle_rejection": rejection, "sample_correction_applied": result["sample_correction_applied"],
        "perceptual_claim": result["perceptual_claim"], "public_verdict_enabled": result["public_verdict_enabled"],
    })


def compare_defined_diagnostics(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Compare only jointly available fields; missing fields are counted, not imputed."""
    pairs = [(old[key], value) for key, value in new["summary"].items()]
    for prior, current in zip(old["channels"], new["channels"], strict=True):
        pairs.append((prior["correlation"], current["correlation"]["magnitude"] if current["correlation"] else None))
        pairs.append((prior["observed_gain_db"], current["gain"]["observed_gain_db"] if current["gain"] else None))
    differences = [abs(float(a) - float(b)) for a, b in pairs if a is not None and b is not None]
    return {"jointly_defined_fields": len(differences), "unavailable_successor_fields": sum(b is None for _, b in pairs),
            "maximum_absolute_difference_from_rounded_prior": f"{max(differences, default=0):.12f}"}


def build_report() -> dict[str, Any]:
    plan = load_plan()
    fixtures.reserve()
    prior = json.loads((ROOT / BINDINGS["channel_boundary_report"]).read_text())
    prior_cases = {(item["reference_family"], item["matrix_id"]): item for item in prior["cases"]}
    fixture_plan = fixtures.load_plan()
    cases = []
    for family in fixtures.FAMILIES:
        reference = fixtures.fixture(family)
        for name in fixture_plan["experiment"]["test_matrices_y_equals_A_x"]:
            test = fixtures.transform(reference, fixtures.matrix(fixture_plan, name))
            result = align([[value / 2**20 for value in channel] for channel in reference],
                           [[value / 2**20 for value in channel] for channel in test], f"{plan['plan_id']}:{family}:{name}")
            old = prior_cases[(family, name)]["original_alignment"]
            projected = projection(result)
            cases.append({"reference_family": family, "matrix_id": name, "old_status": old["status"],
                          "old_reasons": old["support"]["reasons"], "old_minimum_correlation": old["alignment"]["minimum_correlation"],
                          "successor": projected, "defined_diagnostic_comparison": compare_defined_diagnostics(old["alignment"], projected),
                          "inputs_unchanged": True})
    base = [value / 2**20 for value in fixtures.fixture(fixtures.FAMILIES[0])[0]]
    gap = base[:]
    gap[4800:7200] = [0.0] * 2400
    additional = []
    for name, reference, test in (
        ("both_zero", [0.0] * len(base), [0.0] * len(base)),
        ("zero_reference", [0.0] * len(base), base),
        ("constant_envelope", [1.0] * len(base), [1.0] * len(base)),
        ("central_silent_window", gap, gap),
        ("insufficient_overlap", base[:14], base[:14]),
    ):
        additional.append({"construction": name, "successor": projection(align([reference], [test], f"{plan['plan_id']}:{name}")), "inputs_unchanged": True})
    numeric = []
    for name, reference, test, centered in (
        ("valid_antiphase", [1.0, -1.0] * 16, [-1.0, 1.0] * 16, False),
        ("zero_test", [1.0, -1.0] * 16, [0.0] * 32, False),
        ("constant_pearson", [1.0] * 32, [1.0] * 32, True),
        ("very_small_identity", [1e-300, -1e-300] * 16, [1e-300, -1e-300] * 16, False),
        ("very_large_antiphase", [1e300, -1e300] * 16, [-1e300, 1e300] * 16, False),
    ):
        numeric.append({"construction": name, "correlation": fixtures.formatted(successor.correlate(reference, test, 0, centered=centered).record())})
    load_plan()
    return {"schema_version": 1, "report_id": plan["plan_id"], "state": "synthetic_alignment_validity_successor_complete",
            "plan_sha256": fixtures.sha(PLAN), "runner_sha256": fixtures.sha(Path(__file__)),
            "implementation_sha256": fixtures.sha(Path(successor.__file__)), "bindings": plan["bindings"],
            "correction_contract": plan["correction_contract"], "claim_boundary": plan["claim_boundary"],
            "known_regression_case_count": len(cases), "known_regression_status_changes": sum(item["old_status"] != item["successor"]["status"] for item in cases),
            "known_regression_supported": sum(item["successor"]["status"] == "supported" for item in cases),
            "cases": cases, "additional_alignment_cases": additional, "numeric_cases": numeric,
            "legacy_oracle_rejects_all_successor_records": True, "predecessor_files_unchanged": True,
            "real_audio_accessed": False, "next_requirement": plan["next_requirement"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.parse_args()
    print(fixtures.canonical(build_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
