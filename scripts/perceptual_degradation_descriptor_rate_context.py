#!/usr/bin/env python3
"""Audit frozen descriptors on shared-grid synthetic signals; never save audio."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
from fractions import Fraction
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/descriptor-rate-context-audit-plan.json"
PLAN_SHA = "6a112bd011fc1216f6f0c02f64853b30d35eeac6c8b35c40659d25167339be37"
BINDINGS = {
    "descriptor_plan": "benchmarks/perceptual-degradation-v1/source-trait-sparse-tonal-descriptor-plan.json",
    "descriptor_engine": "scripts/perceptual_degradation_source_trait_sparse_tonal_descriptor.py",
    "native_rate_runner": "scripts/perceptual_degradation_source_trait_sparse_tonal_exact_member_confirmation.py",
    "capture_specification": "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-clean-capture-acquisition-spec.json",
    "restart_review": "docs/research/perceptual-degradation-strategic-review-20260905.md",
}
RATES = (48000, 96000, 192000)
HARMONICS = {"coherent_full_band": (1, 511), "hash_phase_full_band": (1, 511),
             "hash_phase_lower_band": (1, 255), "single_tone": (32, 32)}
SEED = "lossytrace-descriptor-rate-context-20260905-001"
CONTRAST_FLAGS = ("sparse_non_tonal_contrast", "tonal_non_sparse_contrast", "sparse_tonal_overlap", "abstain")


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


def load_engine():
    load_plan()
    spec = importlib.util.spec_from_file_location("rate_context_descriptor", ROOT / BINDINGS["descriptor_engine"])
    assert spec and spec.loader
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    errors = engine.validate_plan(json.loads((ROOT / BINDINGS["descriptor_plan"]).read_text()))
    if errors:
        raise ValueError("bound descriptor plan is invalid")
    return engine


def exact(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def phase(harmonic: int) -> float:
    digest = hashlib.sha256(f"{SEED}/{harmonic}".encode()).digest()
    return 2 * math.pi * (int.from_bytes(digest[:8], "big") / 2**64)


def master_period(family: str) -> list[int]:
    if type(family) is not str or family not in HARMONICS:
        raise ValueError("unknown declared signal family")
    reserve()
    lo, hi = HARMONICS[family]
    phases = [(k, phase(k) if family.startswith("hash_phase_") else 0.0) for k in range(lo, hi + 1)]
    period = [round(8192 * math.fsum(math.cos(2 * math.pi * k * n / 4096 + offset) for k, offset in phases)) for n in range(4096)]
    if any(not -(2**23) <= value < 2**23 for value in period):
        raise ValueError("synthetic samples exceed signed 24-bit range")
    return period


def kernel(period: list[int], rate: int) -> list[int]:
    if type(rate) is not int or rate not in RATES:
        raise ValueError("undeclared diagnostic sample rate")
    if type(period) is not list or len(period) != 4096 or any(type(value) is not int or not -(2**23) <= value < 2**23 for value in period):
        raise ValueError("invalid common quantized period")
    return period[::192000 // rate] * 6


def rate_geometry(rate: int) -> dict[str, Any]:
    if type(rate) is not int or rate not in RATES:
        raise ValueError("undeclared diagnostic sample rate")
    return {"sample_rate_hz": rate, "fft_window_seconds": exact(Fraction(1024, rate)),
            "hop_seconds": exact(Fraction(512, rate)), "bin_spacing_hz": exact(Fraction(rate, 1024)),
            "highest_included_bin_hz": exact(Fraction(511 * rate, 1024)),
            "capture_permitted_rate": rate in (48000, 96000)}


def shared_grid_checks(kernels: dict[int, list[int]]) -> list[dict[str, Any]]:
    checks = []
    for low, high in ((48000, 96000), (48000, 192000), (96000, 192000)):
        matches = kernels[low] == kernels[high][::high // low]
        if not matches:
            raise ValueError("shared-time sample identity failed")
        checks.append({"lower_rate_hz": low, "higher_rate_hz": high,
                       "shared_sample_count": len(kernels[low]), "all_shared_samples_identical": matches})
    return checks


def rate_changes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base = rows[0]["descriptor"]
    changes = []
    for row in rows[1:]:
        current = row["descriptor"]
        changes.append({
            "compared_rate_hz": row["geometry"]["sample_rate_hz"], "reference_rate_hz": 48000,
            "spectral_tonal_flag_changed": current["spectral_concentration"].get("tonal") != base["spectral_concentration"].get("tonal"),
            "spectral_non_tonal_flag_changed": current["spectral_concentration"].get("non_tonal") != base["spectral_concentration"].get("non_tonal"),
            "contrast_class_changed": any(current[key] != base[key] for key in CONTRAST_FLAGS),
        })
    return changes


def rate_audit(engine) -> dict[str, Any]:
    constructions = []
    padded_rows = []
    for family in HARMONICS:
        period = master_period(family)
        kernels = {rate: kernel(period, rate) for rate in RATES}
        checks = shared_grid_checks(kernels)
        rows = [{"geometry": rate_geometry(rate), "sample_count": len(kernels[rate]), "descriptor": engine.classify(kernels[rate])} for rate in RATES]
        constructions.append({"synthetic_construction": family, "shared_grid_checks": checks,
                              "native_rate_results": rows, "changes_from_48000_hz": rate_changes(rows)})
        if family == "coherent_full_band":
            for rate in (48000, 96000):
                reserve()
                samples = [0] * (15 * rate)
                start = 7 * rate
                samples[start:start + len(kernels[rate])] = kernels[rate]
                padded_rows.append({"geometry": rate_geometry(rate), "sample_count": len(samples),
                                    "duration_and_quiet_geometry_met": True,
                                    "eligible_natural_capture": False, "descriptor": engine.classify(samples)})
                del samples
    return {"kernel_constructions": constructions,
            "padded_coherent_kernel": {"native_rate_results": padded_rows, "changes_from_48000_hz": rate_changes(padded_rows),
                                       "natural_source_or_perceptual_truth": False}}


def context_parameters(rate: int, duration: int, onset: str) -> tuple[int, int, int]:
    if type(rate) is not int or rate not in (48000, 96000) or type(duration) is not int or duration not in (15, 30) or type(onset) is not str or onset not in ("5.950", "6.000"):
        raise ValueError("undeclared context construction")
    return duration * rate, int(Fraction(onset) * rate), int((Fraction(onset) + Fraction(8, 5)) * rate)


def analytic_occupancy(rate: int, duration: int, onset: str) -> dict[str, Any]:
    count, start, end = context_parameters(rate, duration, onset)
    powers = []
    for block in range(10):
        lower, upper = block * count // 10, (block + 1) * count // 10
        overlap = max(0, min(end, upper) - max(start, lower))
        powers.append(Fraction(1000**2 * overlap, upper - lower))
    active = sum(power >= max(powers) / 1000 for power in powers)
    return {"active_block_count": active, "sparse": active <= 2, "non_sparse": active >= 8,
            "relative_block_powers": [exact(power / max(powers)) for power in powers]}


def context_audit(engine) -> dict[str, Any]:
    rows = []
    for rate in (48000, 96000):
        for duration in (15, 30):
            for onset in ("5.950", "6.000"):
                reserve()
                count, start, end = context_parameters(rate, duration, onset)
                samples = [0] * count
                samples[start:end] = [1000] * (end - start)
                observed = engine.time_occupancy(samples)
                del samples
                analytic = analytic_occupancy(rate, duration, onset)
                agrees = all(observed[key] == analytic[key] for key in ("active_block_count", "sparse", "non_sparse"))
                if not agrees:
                    raise ValueError("occupancy disagrees with exact interval-overlap calculation")
                rows.append({"sample_rate_hz": rate, "duration_seconds": duration, "event_start_seconds": onset,
                             "descriptor": observed, "analytic": analytic, "exact_overlap_check_passed": agrees})
    comparisons = []
    for rate in (48000, 96000):
        by_key = {(row["duration_seconds"], row["event_start_seconds"]): row for row in rows if row["sample_rate_hz"] == rate}
        original = by_key[(15, "5.950")]["descriptor"]
        for change, key in (("translate_event_by_50_ms", (15, "6.000")), ("append_15_seconds_of_quiet", (30, "5.950"))):
            modified = by_key[key]["descriptor"]
            comparisons.append({"sample_rate_hz": rate, "change": change,
                                "event_samples_unchanged": True,
                                "before_active_blocks": original["active_block_count"],
                                "after_active_blocks": modified["active_block_count"],
                                "sparse_flag_changed": original["sparse"] != modified["sparse"]})
    return {"occupancy_only_constructions": rows, "comparisons": comparisons,
            "spectral_classification_or_natural_source_truth_claimed": False}


def build_report() -> dict[str, Any]:
    plan, engine = load_plan(), load_engine()
    reserve()
    return {"schema_version": 1, "report_id": plan["plan_id"],
            "state": "synthetic_descriptor_rate_and_context_audit_complete",
            "plan_sha256": sha(PLAN), "implementation_sha256": sha(Path(__file__)),
            "bindings": plan["bindings"], "rate_audit": rate_audit(engine),
            "context_audit": context_audit(engine), "claim_boundary": plan["claim_boundary"],
            "next_requirement": plan["next_requirement"], "generated_audio_retained": False,
            "actual_audio_accessed": False, "statistical_fits_or_perceptual_metrics_executed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.parse_args()
    print(canonical(build_report()).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
