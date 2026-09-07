#!/usr/bin/env python3
"""Exact temporal squared-sample energy measures; synthetic development only."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
from bisect import bisect_left
from fractions import Fraction
from itertools import accumulate
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/temporal-energy-measure-plan.json"
PLAN_SHA = "9238c8073d2c1b179387ab8083806eeb3c1ab285b8a0b78253d1ad7946789257"
BINDINGS = {
    "trait_contract": "benchmarks/perceptual-degradation-v1/source-trait-identifiability-plan.json",
    "rate_context_implementation": "scripts/perceptual_degradation_descriptor_rate_context.py",
    "rate_context_report": "research/toolchains/evidence/perceptual-degradation-descriptor-rate-context-synthetic-20260905-001.json",
    "window_support_report": "research/toolchains/evidence/perceptual-degradation-descriptor-window-support-synthetic-20260905-001.json",
    "capture_specification": "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-clean-capture-acquisition-spec.json",
}
QUANTILES = {"q05": Fraction(1, 20), "q25": Fraction(1, 4), "q50": Fraction(1, 2), "q75": Fraction(3, 4), "q95": Fraction(19, 20)}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(value: Fraction | int | None) -> str | None:
    if value is None:
        return None
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


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


def predecessor():
    load_plan()
    spec = importlib.util.spec_from_file_location("temporal_measure_predecessor", ROOT / BINDINGS["rate_context_implementation"])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_plan()
    return module


def validate_rate(rate: int) -> None:
    if type(rate) is not int or rate <= 0:
        raise ValueError("sample rate must be a positive integer")


def validate_amplitude(value: int) -> None:
    if type(value) is not int or not -(2**23) <= value < 2**23:
        raise ValueError("sample must be a signed 24-bit integer")


def assemble(count: int, rate: int, mass: int, quantiles: dict[str, Fraction | None], centroid: Fraction | None,
             first: int | None, last: int | None, nonzero_count: int) -> dict[str, Any]:
    span90 = quantiles["q95"] - quantiles["q05"] if mass else None
    span50 = quantiles["q75"] - quantiles["q25"] if mass else None
    return {"supported": mass > 0, "reason": "positive_squared_sample_mass" if mass else "no_nonzero_sample_energy",
            "sample_count": count, "recording_duration_seconds": exact(Fraction(count, rate)),
            "squared_integer_amplitude_exposure_seconds": exact(Fraction(mass, rate)),
            "quantile_times_seconds": {key: exact(value) for key, value in quantiles.items()},
            "central_90_energy_span_seconds": exact(span90), "central_50_energy_span_seconds": exact(span50),
            "squared_sample_energy_centroid_seconds": exact(centroid),
            "first_nonzero_cell_start_seconds": exact(Fraction(first, rate)) if first is not None else None,
            "last_nonzero_cell_end_seconds": exact(Fraction(last, rate)) if last is not None else None,
            "literal_nonzero_cell_duration_seconds": exact(Fraction(nonzero_count, rate)),
            "recording_relative_central_90_fraction": exact(span90 * rate / count) if mass else None}


def measure_runs(runs: Sequence[tuple[int, int]], rate: int) -> dict[str, Any]:
    validate_rate(rate)
    if not isinstance(runs, (list, tuple)):
        raise ValueError("runs must be an explicit sequence")
    count = mass = moment_twice = nonzero_count = 0
    first = last = None
    for run in runs:
        if not isinstance(run, (list, tuple)) or len(run) != 2:
            raise ValueError("run must contain length and amplitude")
        length, amplitude = run
        if type(length) is not int or length <= 0:
            raise ValueError("run length must be a positive integer")
        validate_amplitude(amplitude)
        power = amplitude * amplitude
        mass += length * power
        moment_twice += power * length * (2 * count + length)
        if power:
            first = count if first is None else first
            last = count + length
            nonzero_count += length
        count += length
    quantiles: dict[str, Fraction | None] = {key: None for key in QUANTILES}
    if mass:
        for key, q in QUANTILES.items():
            target, before, start = q * mass, 0, 0
            for length, amplitude in runs:
                power = amplitude * amplitude
                if power and before + length * power >= target:
                    quantiles[key] = (start + (target - before) / power) / rate
                    break
                before += length * power
                start += length
        if any(value is None for value in quantiles.values()):
            raise ValueError("positive mass lacks a quantile")
    centroid = Fraction(moment_twice, 2 * rate * mass) if mass else None
    return assemble(count, rate, mass, quantiles, centroid, first, last, nonzero_count)


def measure_samples(samples: Sequence[int], rate: int) -> dict[str, Any]:
    validate_rate(rate)
    if not isinstance(samples, (list, tuple)):
        raise ValueError("samples must be an explicit sequence")
    runs: list[tuple[int, int]] = []
    for value in samples:
        validate_amplitude(value)
        if runs and runs[-1][1] == value:
            runs[-1] = (runs[-1][0] + 1, value)
        else:
            runs.append((1, value))
    return measure_runs(runs, rate)


def profiles() -> list[dict[str, Any]]:
    rows = [{"profile_id": f"single-{duration}-{onset}", "duration": duration,
             "intervals": [(Fraction(onset), Fraction(onset) + Fraction(8, 5))], "background": 0,
             "legacy_onset": onset}
            for duration in (15, 30) for onset in ("5.950", "6.000")]
    rows.append({"profile_id": "separated-equal-intervals", "duration": 30,
                 "intervals": [(Fraction(6), Fraction(34, 5)), (Fraction(18), Fraction(94, 5))], "background": 0})
    rows.extend({"profile_id": f"background-{background}-{duration}", "duration": duration,
                 "intervals": [(Fraction(6), Fraction(38, 5))], "background": background}
                for duration in (15, 30) for background in (10, 100))
    return rows


def profile_runs(profile: dict[str, Any], rate: int, gain: int = 1) -> list[tuple[int, int]]:
    validate_rate(rate)
    if type(gain) is not int or gain not in (1, -2) or profile not in profiles():
        raise ValueError("undeclared profile or gain")
    reserve()
    points = [(0, profile["background"] * gain)]
    for start, stop in profile["intervals"]:
        if (start * rate).denominator != 1 or (stop * rate).denominator != 1:
            raise ValueError("profile endpoints are not sample-cell boundaries")
        points.extend([(int(start * rate), 1000 * gain), (int(stop * rate), profile["background"] * gain)])
    points.append((profile["duration"] * rate, 0))
    return [(b[0] - a[0], a[1]) for a, b in zip(points, points[1:]) if b[0] > a[0]]


def physical_view(summary: dict[str, Any], *, include_exposure: bool = True) -> dict[str, Any]:
    omitted = {"sample_count"}
    if not include_exposure:
        omitted.add("squared_integer_amplitude_exposure_seconds")
    return {key: value for key, value in summary.items() if key not in omitted}


def dense_reference(samples: list[int], rate: int) -> dict[str, Any]:
    """Independent sample-cell CDF enumeration; no run integration or adapter."""
    weights = [value**2 for value in samples]
    total = sum(weights)
    quantiles: dict[str, Fraction | None] = {key: None for key in QUANTILES}
    centroid = None
    support = [n for n, weight in enumerate(weights) if weight]
    if total:
        knots = [Fraction(0)] + [Fraction(value, total) for value in accumulate(weights)]
        for key, q in QUANTILES.items():
            right = bisect_left(knots, q)
            cell_fraction = (q - knots[right - 1]) / (knots[right] - knots[right - 1])
            quantiles[key] = (right - 1 + cell_fraction) / rate
        centroid = sum(Fraction(2 * n + 1, 2 * rate) * weight for n, weight in enumerate(weights)) / total
    return assemble(len(samples), rate, total, quantiles, centroid,
                    support[0] if support else None, support[-1] + 1 if support else None, len(support))


def build_report() -> dict[str, Any]:
    plan, previous = load_plan(), predecessor()
    rows, by_id = [], {}
    dense_checks = 0
    for profile in profiles():
        native, gain_checks = [], []
        for rate in (48000, 96000):
            base = measure_runs(profile_runs(profile, rate), rate)
            scaled = measure_runs(profile_runs(profile, rate, -2), rate)
            time_equal = physical_view(base, include_exposure=False) == physical_view(scaled, include_exposure=False)
            exposure_fourfold = Fraction(scaled["squared_integer_amplitude_exposure_seconds"]) == 4 * Fraction(base["squared_integer_amplitude_exposure_seconds"])
            if not time_equal or not exposure_fourfold:
                raise ValueError("signed gain identity failed")
            native.append({"sample_rate_hz": rate, "summary": base})
            gain_checks.append({"sample_rate_hz": rate, "gain": -2, "temporal_and_context_fields_identical": time_equal,
                                "squared_amplitude_exposure_multiplied_by_four": exposure_fourfold})
        if physical_view(native[0]["summary"]) != physical_view(native[1]["summary"]):
            raise ValueError("exact density refinement identity failed")
        for rate in (20, 40):
            for gain in (1, -2):
                reserve()
                runs = profile_runs(profile, rate, gain)
                samples = [value for length, value in runs for _ in range(length)]
                direct = dense_reference(samples, rate)
                if direct != measure_runs(runs, rate) or direct != measure_samples(samples, rate):
                    raise ValueError("independent cell enumeration disagrees")
                expected = measure_runs(profile_runs(profile, 48000, gain), 48000)
                if physical_view(direct) != physical_view(expected):
                    raise ValueError("numerical density analog differs in physical measures")
                dense_checks += 1
        row = {"synthetic_profile_id": profile["profile_id"], "background_amplitude": profile["background"],
               "native_rate_views": native, "signed_gain_checks": gain_checks,
               "exact_density_refinement_identity": True, "independent_dense_checks_passed": 4}
        if "legacy_onset" in profile:
            row["consumed_legacy_analytic_occupancy"] = previous.analytic_occupancy(48000, profile["duration"], profile["legacy_onset"])
        rows.append(row)
        by_id[profile["profile_id"]] = native[0]["summary"]
    base = by_id["single-15-5.950"]
    translated, padded = by_id["single-15-6.000"], by_id["single-30-5.950"]
    translation = all(Fraction(translated["quantile_times_seconds"][key]) - Fraction(base["quantile_times_seconds"][key]) == Fraction(1, 20) for key in QUANTILES)
    padding = all(padded[key] == base[key] for key in ("quantile_times_seconds", "central_90_energy_span_seconds", "central_50_energy_span_seconds", "squared_sample_energy_centroid_seconds", "literal_nonzero_cell_duration_seconds"))
    if not translation or not padding:
        raise ValueError("declared zero-context temporal identities failed")
    comparisons = {"50_ms_translation_quantiles_shift_exactly": translation,
                   "exact_zero_append_preserves_temporal_measures": padding,
                   "zero_append_context_ratio_halves": Fraction(padded["recording_relative_central_90_fraction"]) == Fraction(base["recording_relative_central_90_fraction"]) / 2,
                   "contiguous_vs_separated": {key: {"contiguous": by_id["single-30-6.000"][key], "separated": by_id["separated-equal-intervals"][key]} for key in ("central_90_energy_span_seconds", "literal_nonzero_cell_duration_seconds", "quantile_times_seconds")},
                   "positive_background_append": [{"background_amplitude": value, "before_span_seconds": by_id[f"background-{value}-15"]["central_90_energy_span_seconds"], "after_span_seconds": by_id[f"background-{value}-30"]["central_90_energy_span_seconds"], "exact_zero_padding_invariance_applies": False} for value in (10, 100)]}
    return {"schema_version": 1, "report_id": plan["plan_id"], "state": "continuous_temporal_energy_measure_synthetic_development_complete",
            "plan_sha256": sha(PLAN), "implementation_sha256": sha(Path(__file__)), "bindings": plan["bindings"],
            "technical_measure_definition_selected": True, "claim_boundary": plan["claim_boundary"],
            "next_requirement": plan["next_requirement"], "physical_profiles": rows, "comparisons": comparisons,
            "native_rate_and_signed_gain_summaries_evaluated": 36, "independent_dense_checks_passed": dense_checks,
            "legacy_occupancy_reused_via_bound_analytic_replay": True,
            "actual_audio_accessed": False, "generated_audio_retained": False, "perceptual_or_statistical_fit_executed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.parse_args()
    print(canonical(build_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
