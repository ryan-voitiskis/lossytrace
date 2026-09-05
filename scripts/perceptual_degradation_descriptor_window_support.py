#!/usr/bin/env python3
"""Isolate frozen descriptor window support on declared integer synthetic periods."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/descriptor-window-support-audit-plan.json"
PLAN_SHA = "4822a5ddf9b1809f5348cb44acd20de38306b37b75d9b29d389785eb9dac45b8"
BINDINGS = {
    "rate_context_plan": "benchmarks/perceptual-degradation-v1/descriptor-rate-context-audit-plan.json",
    "rate_context_implementation": "scripts/perceptual_degradation_descriptor_rate_context.py",
    "rate_context_report": "research/toolchains/evidence/perceptual-degradation-descriptor-rate-context-synthetic-20260905-001.json",
    "descriptor_engine": "scripts/perceptual_degradation_source_trait_sparse_tonal_descriptor.py",
}
FAMILIES = ("coherent_harmonics", "impulse_train", "quarter_rate_tone")
METHODS = ("legacy_equal_frame_medians", "analyzed_band_energy_admission", "pooled_raw_admitted_spectra")
CLASSES = ("tonal", "non_tonal", "indeterminate", "unsupported")
ANCHORS = (0, 1, 128, 256, 511, 512, 640, 1023)
SIZE, HOP = 1024, 512


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


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


def load_predecessor():
    load_plan()
    spec = importlib.util.spec_from_file_location("window_support_predecessor", ROOT / BINDINGS["rate_context_implementation"])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_plan()
    return module


def period(family: str) -> list[int]:
    if type(family) is not str or family not in FAMILIES:
        raise ValueError("undeclared family")
    reserve()
    if family == "coherent_harmonics":
        return [511 * 8192] + [0 if n % 2 else -8192 for n in range(1, SIZE)]
    if family == "impulse_train":
        return [511 * 8192] + [0] * (SIZE - 1)
    return [1048576, 0, -1048576, 0] * 256


def rotate(values: list[int], origin: int) -> list[int]:
    if type(origin) is not int or not 0 <= origin < SIZE:
        raise ValueError("undeclared frame origin")
    if type(values) is not list or len(values) != SIZE or any(type(v) is not int or not -(2**23) <= v < 2**23 for v in values):
        raise ValueError("invalid integer period")
    return values[origin:] + values[:origin]


def inventory(origin: int, count: int) -> tuple[tuple[int, int], tuple[int, int]]:
    if type(origin) is not int or not 0 <= origin < SIZE or type(count) is not int or count not in (11, 12):
        raise ValueError("undeclared frame inventory")
    return ((origin, (count + 1) // 2), ((origin + HOP) % SIZE, count // 2))


def expected_dft(family: str) -> list[int]:
    if family == "coherent_harmonics":
        return [0 if k in (0, HOP) else 8192 * HOP for k in range(SIZE)]
    if family == "impulse_train":
        return [511 * 8192] * SIZE
    if family == "quarter_rate_tone":
        return [1048576 * HOP if k in (256, 768) else 0 for k in range(SIZE)]
    raise ValueError("undeclared DFT family")


def analytic_check(engine, family: str, values: list[int]) -> dict[str, Any]:
    expected = expected_dft(family)
    actual = engine._fft([complex(value, 0) for value in values])
    relative_error = max(abs(a - b) for a, b in zip(actual, expected, strict=True)) / max(expected)
    if relative_error > 1e-12:
        raise ValueError("closed-form DFT check failed")
    return {"all_1024_bins_checked": True, "relative_error_at_most": "1e-12", "passed": True}


def spectral_values(powers: list[float]) -> tuple[float, float] | None:
    total = sum(powers)
    if total == 0:
        return None
    flatness = math.exp(sum(math.log(max(value, total * 1e-12)) for value in powers) / len(powers)) / (total / len(powers))
    return flatness, sum(sorted(powers, reverse=True)[:8]) / total


def frame_features(engine, values: list[int], window: list[float]) -> dict[str, Any]:
    weighted = [value * weight for value, weight in zip(values, window, strict=True)]
    spectrum = engine._fft([complex(value, 0) for value in weighted])
    powers = [abs(value) ** 2 for value in spectrum[1:HOP]]
    return {"raw_power": sum(value * value for value in values) / SIZE,
            "windowed_power": sum(value * value for value in weighted) / SIZE,
            "powers": powers, "band_energy": sum(powers), "spectral": spectral_values(powers)}


def result(flatness: float | None, concentration: float | None, count: int, fraction: float) -> dict[str, Any]:
    supported = count >= 3 and flatness is not None and concentration is not None
    tonal = supported and flatness <= 0.1 and concentration >= 0.6
    non_tonal = supported and flatness >= 0.5 and concentration <= 0.2
    label = "unsupported" if not supported else "tonal" if tonal else "non_tonal" if non_tonal else "indeterminate"
    return {"supported": supported, "contributing_frame_count": count,
            "spectral_flatness": f"{flatness:.9f}" if supported else None,
            "top_8_bin_power_share": f"{concentration:.9f}" if supported else None,
            "tonal": bool(tonal), "non_tonal": bool(non_tonal), "class": label,
            "retained_analyzed_band_energy_fraction": f"{fraction:.12f}"}


def summarize(engine, features: list[dict[str, Any]], origin: int, count: int) -> dict[str, dict[str, Any]]:
    groups = [(features[index], multiplicity) for index, multiplicity in inventory(origin, count)]
    raw_max = max(frame["raw_power"] for frame, _ in groups)
    admitted = [(frame, n) for frame, n in groups if raw_max > 0 and frame["raw_power"] >= raw_max * 0.001]
    positive = [(frame, n) for frame, n in admitted if frame["band_energy"] > 0]
    band_max = max((frame["band_energy"] for frame, _ in positive), default=0.0)
    all_energy = sum(frame["band_energy"] * n for frame, n in positive)
    output = {}
    for method in METHODS:
        selected = [(frame, n) for frame, n in positive if method != METHODS[1] or frame["band_energy"] >= band_max * 0.001]
        selected_count = sum(n for _, n in selected)
        selected_energy = sum(frame["band_energy"] * n for frame, n in selected)
        if selected_count < 3:
            values = (None, None)
        elif method == METHODS[2]:
            pooled = [sum(frame["powers"][k] * n for frame, n in selected) for k in range(HOP - 1)]
            values = spectral_values(pooled)
            assert values is not None
        else:
            values = tuple(engine._median([frame["spectral"][k] for frame, n in selected for _ in range(n)]) for k in (0, 1))
        output[method] = result(*values, selected_count, selected_energy / all_energy if all_energy else 0.0)
    return output


def compare_legacy(expected: dict[str, Any], actual: dict[str, Any]) -> None:
    view = {"supported": actual["supported"], "active_frame_count": actual["contributing_frame_count"]}
    if actual["supported"]:
        view.update(median_spectral_flatness=actual["spectral_flatness"],
                    median_top_8_bin_power_share=actual["top_8_bin_power_share"],
                    tonal=actual["tonal"], non_tonal=actual["non_tonal"])
    if view != expected:
        raise ValueError("unchanged descriptor cross-check failed")


def runs(labels: list[str]) -> list[dict[str, Any]]:
    if len(labels) != SIZE or any(label not in CLASSES for label in labels):
        raise ValueError("incomplete or invalid origin class inventory")
    encoded = []
    start = 0
    for end in range(1, SIZE + 1):
        if end == SIZE or labels[end] != labels[start]:
            encoded.append({"start_origin_inclusive": start, "end_origin_exclusive": end, "class": labels[start]})
            start = end
    return encoded


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [row["class"] for row in rows]
    counts = Counter(labels)
    output = {"origin_count": len(rows), "class_counts": {key: counts[key] for key in CLASSES},
              "complete_origin_class_runs": runs(labels),
              "different_class_from_origin_zero_count": sum(label != labels[0] for label in labels),
              "contributing_frames_min_max": [min(row["contributing_frame_count"] for row in rows), max(row["contributing_frame_count"] for row in rows)]}
    for key in ("spectral_flatness", "top_8_bin_power_share", "retained_analyzed_band_energy_fraction"):
        values = [row[key] for row in rows if row[key] is not None]
        output[key + "_min_max"] = [min(values, key=float), max(values, key=float)] if values else [None, None]
    return output


def family_audit(engine, family: str) -> dict[str, Any]:
    values = period(family)
    record = values * 8
    analytic = analytic_check(engine, family, values)
    window = [0.5 - 0.5 * math.cos(2 * math.pi * n / SIZE) for n in range(SIZE)]
    features = []
    for origin in range(SIZE):
        rotated = rotate(values, origin)
        if record[origin:origin + SIZE] != rotated:
            raise ValueError("frame identity failed")
        features.append(frame_features(engine, rotated, window))
    if len({row["raw_power"] for row in features}) != 1 or features[0]["raw_power"] <= 0:
        raise ValueError("unwindowed frame energies are not identical and positive")
    by_inventory = {}
    ledgers = []
    crosschecks = 0
    for count in (11, 12):
        rows = []
        for origin in range(SIZE):
            summaries = summarize(engine, features, origin, count)
            if origin in ANCHORS:
                clip = record[origin:origin + SIZE + HOP * (count - 1)]
                if len(clip) != SIZE + HOP * (count - 1):
                    raise ValueError("declared frame inventory exceeds record")
                compare_legacy(engine.spectral_concentration(clip), summaries[METHODS[0]])
                crosschecks += 1
            if family == FAMILIES[0] and origin in (0, 128, 512):
                ledgers.append({"origin_samples": origin, "frame_count": count,
                                "raw_power_identical_across_all_frames": True,
                                "frame_phases": [{"period_origin": index, "multiplicity": n,
                                                  "analyzed_band_energy_relative_to_largest_phase": f"{features[index]['band_energy'] / max(features[i]['band_energy'] for i, _ in inventory(origin, count)):.12e}",
                                                  "post_window_power_over_raw_power": f"{features[index]['windowed_power'] / features[index]['raw_power']:.12e}"}
                                                 for index, n in inventory(origin, count)],
                                "methods": summaries})
            rows.append(summaries)
        by_inventory[count] = rows
    return {"family": family, "closed_form_unwindowed_dft": analytic,
            "unique_rotated_frames_checked": SIZE, "all_raw_frame_powers_identical_positive": True,
            "unchanged_descriptor_crosschecks_passed": crosschecks,
            "inventories": [{"frame_count": count, "methods": {method: aggregate([row[method] for row in by_inventory[count]]) for method in METHODS},
                             "diagnostic_changed_class_from_legacy_counts": {method: sum(row[method]["class"] != row[METHODS[0]]["class"] for row in by_inventory[count]) for method in METHODS[1:]}}
                            for count in (11, 12)],
            "changed_class_between_11_and_12_frames": {method: sum(a[method]["class"] != b[method]["class"] for a, b in zip(by_inventory[11], by_inventory[12], strict=True)) for method in METHODS},
            "coherent_mechanism_ledgers": ledgers}


def build_report() -> dict[str, Any]:
    plan = load_plan()
    predecessor = load_predecessor()
    engine = predecessor.load_engine()
    reserve()
    if period(FAMILIES[0]) != predecessor.master_period("coherent_full_band")[::4]:
        raise ValueError("consumed development period identity differs")
    families = [family_audit(engine, family) for family in FAMILIES]
    return {"schema_version": 1, "report_id": plan["plan_id"],
            "state": "synthetic_descriptor_window_support_mechanism_audit_complete",
            "plan_sha256": sha(PLAN), "implementation_sha256": sha(Path(__file__)),
            "bindings": plan["bindings"], "claim_boundary": plan["claim_boundary"],
            "next_requirement": plan["next_requirement"], "families": families,
            "origin_inventory_family_cases": SIZE * 2 * len(FAMILIES),
            "method_summaries_evaluated": SIZE * 2 * len(FAMILIES) * len(METHODS),
            "unchanged_descriptor_crosschecks_passed": sum(row["unchanged_descriptor_crosschecks_passed"] for row in families),
            "consumed_coherent_development_period_identity_verified": True,
            "independent_scientific_validation_claimed": False,
            "actual_audio_accessed": False, "generated_audio_retained": False,
            "statistical_fits_or_perceptual_metrics_executed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.parse_args()
    print(canonical(build_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
