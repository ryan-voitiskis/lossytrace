#!/usr/bin/env python3
"""Synthetic channel-geometry audit; no gain correction or perceptual scoring."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import shutil
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/channel-normalization-boundary-plan.json"
PLAN_SHA = "5dccbdc651cac34bbacdbbc5b47b96e6a507d929dcc2153c31893387e9d1a556"
BINDINGS = {
    "research_contract": "docs/research/perceptual-degradation-contract-20260803.md",
    "strategic_review": "docs/research/perceptual-degradation-strategic-review-20260905.md",
    "mono_alignment": "scripts/perceptual_degradation_alignment.py",
    "channel_alignment": "scripts/perceptual_degradation_alignment_v2.py",
    "alignment_freeze": "benchmarks/perceptual-degradation-v1/alignment-topology-freeze.json",
    "score_free_oracle": "scripts/perceptual_degradation_oracle.py",
    "temporal_measure_report": "research/toolchains/evidence/perceptual-degradation-temporal-energy-measure-synthetic-20260907-001.json",
}
FAMILIES = ("orthogonal_equal_energy", "correlated_unequal_energy")


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reserve() -> None:
    if shutil.disk_usage(ROOT).free < 15 * 1024**3:
        raise ValueError("15 GiB free-space reserve not preserved")


def load_plan() -> dict[str, Any]:
    if sha(PLAN) != PLAN_SHA:
        raise ValueError("plan bytes differ")
    plan = json.loads(PLAN.read_text())
    if set(plan["bindings"]) != set(BINDINGS):
        raise ValueError("binding inventory differs")
    for key, relative in BINDINGS.items():
        if plan["bindings"][key] != {"path": relative, "sha256": sha(ROOT / relative)}:
            raise ValueError("predecessor binding differs")
    return plan


def modules():
    load_plan()
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    loaded = []
    for key in ("mono_alignment", "channel_alignment", "score_free_oracle"):
        path = ROOT / BINDINGS[key]
        module = importlib.import_module(path.stem)
        if Path(module.__file__).resolve() != path.resolve():
            raise ValueError("loaded predecessor location differs")
        loaded.append(module)
    return loaded[1], loaded[2]


def exact(value: int | Fraction | None) -> str | None:
    if value is None:
        return None
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def formatted(value: Any) -> Any:
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("nonfinite alignment summary")
        result = f"{value:.9f}"
        return "0.000000000" if result == "-0.000000000" else result
    if isinstance(value, dict):
        return {key: formatted(item) for key, item in value.items()}
    if isinstance(value, list):
        return [formatted(item) for item in value]
    return value


def validate_channels(channels: list[list[int]]) -> None:
    if not isinstance(channels, list) or len(channels) != 2 or not all(isinstance(channel, list) for channel in channels):
        raise ValueError("explicit stereo integer arrays required")
    if not channels[0] or len(channels[0]) != len(channels[1]):
        raise ValueError("nonempty equal channel lengths required")
    if any(type(value) is not int or not -(2**23) <= value < 2**23 for channel in channels for value in channel):
        raise ValueError("signed 24-bit integer samples required")


def fixture(family: str) -> list[list[int]]:
    if family not in FAMILIES:
        raise ValueError("undeclared reference family")
    reserve()
    u, v = [], []
    state = 0x35A719C3
    for index in range(6000):
        pair = []
        for _ in range(2):
            state = (1664525 * state + 1013904223) % 2**32
            pair.append((((state >> 16) % 1024) - 512) * 32 * (1 + (index // 137) % 5))
        a, b = pair
        u.extend((a, b))
        v.extend((-b, a))
    right = v if family == FAMILIES[0] else [(3 * a + b) // 4 for a, b in zip(u, v, strict=True)]
    result = [u, right]
    validate_channels(result)
    return result


def matrix(plan: dict[str, Any], name: str) -> list[list[Fraction]]:
    declared = plan["experiment"]["test_matrices_y_equals_A_x"]
    if name not in declared:
        raise ValueError("undeclared channel matrix")
    return [[Fraction(value) for value in row] for row in declared[name]]


def transform(reference: list[list[int]], coefficients: list[list[Fraction]]) -> list[list[int]]:
    validate_channels(reference)
    if not isinstance(coefficients, list) or len(coefficients) != 2 or any(not isinstance(row, list) or len(row) != 2 for row in coefficients):
        raise ValueError("two-by-two rational matrix required")
    if any(type(value) not in (int, Fraction) for row in coefficients for value in row):
        raise ValueError("exact rational matrix required")
    reserve()
    output = []
    for row in coefficients:
        channel = []
        for left, right in zip(*reference, strict=True):
            value = Fraction(row[0]) * left + Fraction(row[1]) * right
            if value.denominator != 1:
                raise ValueError("matrix does not preserve integer sample cells")
            channel.append(value.numerator)
        output.append(channel)
    validate_channels(output)
    return output


def gram(channels: list[list[int]]) -> list[list[int]]:
    return [[sum(a * b for a, b in zip(left, right, strict=True)) for right in channels] for left in channels]


def geometry(value: list[list[int | Fraction]]) -> dict[str, Any]:
    total = value[0][0] + value[1][1]
    if not total:
        return {"left_energy_share": None, "right_energy_share": None, "cross_product_over_total_energy": None,
                "mid_energy_share": None, "side_energy_share": None}
    return {"left_energy_share": exact(Fraction(value[0][0], total)),
            "right_energy_share": exact(Fraction(value[1][1], total)),
            "cross_product_over_total_energy": exact(Fraction(value[0][1], total)),
            "mid_energy_share": exact(Fraction(total + 2 * value[0][1], 2 * total)),
            "side_energy_share": exact(Fraction(total - 2 * value[0][1], 2 * total))}


def projections(reference: list[list[int]], test: list[list[int]], coefficients: list[list[Fraction]]) -> dict[str, Any]:
    validate_channels(reference)
    validate_channels(test)
    if len(reference[0]) != len(test[0]):
        raise ValueError("paired timebase lengths differ")
    r, t = gram(reference), gram(test)
    if any(r[index][index] <= 0 for index in range(2)):
        raise ValueError("reference channel has no energy")
    total = r[0][0] + r[1][1]
    crosses = [sum(a * b for a, b in zip(x, y, strict=True)) for x, y in zip(reference, test, strict=True)]
    common = Fraction(sum(crosses), total)
    separate = [Fraction(crosses[index], r[index][index]) for index in range(2)]
    direct = {}
    for name, gains in (("unaltered", [Fraction(1)] * 2), ("common_signed_gain", [common] * 2), ("independent_signed_gains", separate)):
        residual = sum((Fraction(y) - gain * x) ** 2 for x_values, y_values, gain in zip(reference, test, gains, strict=True) for x, y in zip(x_values, y_values, strict=True))
        direct[name] = Fraction(residual, total)
    predicted_t = [[sum(coefficients[i][k] * r[k][l] * coefficients[j][l] for k in range(2) for l in range(2)) for j in range(2)] for i in range(2)]
    predicted_crosses = [sum(r[i][j] * coefficients[i][j] for j in range(2)) for i in range(2)]
    test_total = predicted_t[0][0] + predicted_t[1][1]
    predicted = {"unaltered": Fraction(test_total + total - 2 * sum(predicted_crosses), total),
                 "common_signed_gain": Fraction(test_total - Fraction(sum(predicted_crosses) ** 2, total), total),
                 "independent_signed_gains": Fraction(test_total - sum(Fraction(predicted_crosses[i] ** 2, r[i][i]) for i in range(2)), total)}
    if t != predicted_t or crosses != predicted_crosses or direct != predicted:
        raise ValueError("matrix/Gram identity disagrees with direct sample calculation")
    return {"common_signed_gain": exact(common), "independent_signed_gains": [exact(value) for value in separate],
            "reference_normalized_squared_residuals": {name: exact(value) for name, value in direct.items()},
            "reference_channel_geometry": geometry(r), "test_channel_geometry": geometry(t),
            "matrix_gram_and_pointwise_calculations_identical": True,
            "zero_fitted_gain_is_not_inverted": common == 0 or any(value == 0 for value in separate)}


def oracle_projection(oracle, alignment: dict[str, Any]) -> dict[str, Any]:
    try:
        result = oracle.assemble_score_free(alignment)
    except ValueError as error:
        return {"assembly": "rejected", "validation_error": str(error), "perceptual_claim": False}
    return {"assembly": "accepted", "result_state": result["result_state"], "support": result["support"],
            "outcomes": result["outcomes"], "perceptual_claim": False}


def build_report() -> dict[str, Any]:
    plan = load_plan()
    aligner, oracle = modules()
    cases = []
    for family in FAMILIES:
        reference = fixture(family)
        for name in plan["experiment"]["test_matrices_y_equals_A_x"]:
            reserve()
            coefficients = matrix(plan, name)
            test = transform(reference, coefficients)
            exact_result = projections(reference, test, coefficients)
            ref_float = [[value / 2**20 for value in channel] for channel in reference]
            test_float = [[value / 2**20 for value in channel] for channel in test]
            before = ([channel[:] for channel in ref_float], [channel[:] for channel in test_float])
            alignment = aligner.align_channels(reference_channels=ref_float, test_channels=test_float,
                                               reference_channel_map=["L", "R"], test_channel_map=["L", "R"],
                                               sample_rate_hz=2000, recipe_identity=f"{plan['plan_id']}:{family}:{name}",
                                               minimum_active_seconds=4, maximum_delay_seconds=2)
            if before != (ref_float, test_float):
                raise ValueError("alignment changed its input samples")
            cases.append({"reference_family": family, "matrix_id": name, "exact_known_zero_lag_projection": exact_result,
                          "original_alignment": {"status": alignment["status"], "support": alignment["support"],
                                                 "alignment": formatted(alignment["alignment"])},
                          "original_oracle_assembly": oracle_projection(oracle, alignment),
                          "alignment_inputs_unchanged": True})
    return {"schema_version": 1, "report_id": plan["plan_id"], "state": "synthetic_channel_normalization_boundary_complete",
            "plan_sha256": sha(PLAN), "implementation_sha256": sha(Path(__file__)), "bindings": plan["bindings"],
            "selected_boundary": plan["selected_boundary"], "claim_boundary": plan["claim_boundary"],
            "case_count": len(cases), "matrix_gram_crosschecks_passed": len(cases), "cases": cases,
            "next_requirement": plan["next_requirement"], "real_audio_accessed": False,
            "gain_or_polarity_corrected_audio_produced": False, "perceptual_metric_or_human_execution": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.parse_args()
    print(canonical(build_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
