#!/usr/bin/env python3
"""Replay frozen sparse/tonal descriptors on synthetic fixtures only."""

from __future__ import annotations

import argparse
import cmath
import hashlib
import importlib.util
import json
import math
import shutil
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-tonal-descriptor-plan.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-source-trait-sparse-tonal-descriptor-20260818-001.json"
PLAN_ID = "perceptual-degradation-source-trait-sparse-tonal-descriptor-20260818-001"
REPORT_ID = PLAN_ID
FIXTURE_IDS = [
    "sparse-tonal-overlap",
    "sparse-nontonal-contrast",
    "tonal-nonsparse-contrast",
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load bound implementation: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != "score_blind_sparse_tonal_descriptor_and_non_overlap_rules_frozen_before_candidate_access":
        errors.append("plan state differs")
    expected_bindings = {
        "adjudication_relationship_report",
        "identifiability_implementation",
        "identifiability_plan",
        "identifiability_report",
    }
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        errors.append("binding inventory differs")
        bindings = {}
    for binding_id, binding in bindings.items():
        path = Path(str(binding.get("path", "")))
        if path.is_absolute() or ".." in path.parts or not (ROOT / path).is_file():
            errors.append(f"invalid binding: {binding_id}")
        elif sha256_file(ROOT / path) != binding.get("sha256"):
            errors.append(f"binding hash differs: {binding_id}")
    authorization = plan.get("authorization", {})
    for key, value in authorization.items():
        expected = key in {
            "bound_committed_evidence_read_authorized",
            "synthetic_fixture_execution_authorized",
        }
        if value is not expected:
            errors.append(f"authorization differs: {key}")
    contract = plan.get("descriptor_contract", {})
    time = contract.get("time_occupancy", {})
    spectral = contract.get("spectral_concentration", {})
    if time != {
        "active_block_power_ratio_to_maximum": "0.001000000",
        "equal_duration_block_count": 10,
        "non_sparse_minimum_active_block_count": 8,
        "sparse_maximum_active_block_count": 2,
    }:
        errors.append("time-occupancy contract differs")
    if spectral != {
        "active_frame_power_ratio_to_maximum": "0.001000000",
        "fft_frames": 1024,
        "flatness_power_floor_ratio": "0.000000000001",
        "hop_frames": 512,
        "non_tonal_maximum_top_8_bin_power_share": "0.200000000",
        "non_tonal_minimum_median_spectral_flatness": "0.500000000",
        "tonal_maximum_median_spectral_flatness": "0.100000000",
        "tonal_minimum_top_8_bin_power_share": "0.600000000",
        "window": "periodic_hann",
        "zero_and_nyquist_bins_excluded": True,
    }:
        errors.append("spectral-concentration contract differs")
    if plan.get("resources") != {
        "fresh_temporary_directories": True,
        "maximum_workers": 1,
        "minimum_free_disk_gib": 15,
        "replay_count": 2,
        "retain_generated_audio": False,
    }:
        errors.append("resource boundary differs")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def _fft(values: Sequence[complex]) -> list[complex]:
    size = len(values)
    if size == 1:
        return [values[0]]
    if size == 0 or size & (size - 1):
        raise ValueError("FFT size must be a positive power of two")
    even = _fft(values[0::2])
    odd = _fft(values[1::2])
    output = [0j] * size
    for index in range(size // 2):
        factor = cmath.exp(-2j * math.pi * index / size) * odd[index]
        output[index] = even[index] + factor
        output[index + size // 2] = even[index] - factor
    return output


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def time_occupancy(samples: Sequence[int], block_count: int = 10) -> dict[str, Any]:
    if len(samples) < block_count:
        return {"supported": False}
    powers = []
    for block in range(block_count):
        start = block * len(samples) // block_count
        end = (block + 1) * len(samples) // block_count
        powers.append(sum(value * value for value in samples[start:end]) / (end - start))
    maximum = max(powers)
    if maximum == 0:
        return {"supported": False}
    active = sum(power >= maximum * 0.001 for power in powers)
    return {
        "supported": True,
        "active_block_count": active,
        "block_count": block_count,
        "active_fraction": f"{active / block_count:.9f}",
        "sparse": active <= 2,
        "non_sparse": active >= 8,
    }


def spectral_concentration(samples: Sequence[int]) -> dict[str, Any]:
    size = 1024
    hop = 512
    if len(samples) < size:
        return {"supported": False}
    frames = [samples[start : start + size] for start in range(0, len(samples) - size + 1, hop)]
    frame_powers = [sum(value * value for value in frame) / size for frame in frames]
    maximum = max(frame_powers)
    active = [frame for frame, power in zip(frames, frame_powers) if maximum > 0 and power >= maximum * 0.001]
    if len(active) < 3:
        return {"supported": False, "active_frame_count": len(active)}
    flatness: list[float] = []
    concentration: list[float] = []
    window = [0.5 - 0.5 * math.cos(2.0 * math.pi * index / size) for index in range(size)]
    for frame in active:
        spectrum = _fft([complex(value * weight, 0.0) for value, weight in zip(frame, window)])
        powers = [abs(value) ** 2 for value in spectrum[1 : size // 2]]
        total = sum(powers)
        if total == 0:
            continue
        floor = total * 1e-12
        flatness.append(math.exp(sum(math.log(max(value, floor)) for value in powers) / len(powers)) / (total / len(powers)))
        concentration.append(sum(sorted(powers, reverse=True)[:8]) / total)
    if len(flatness) < 3:
        return {"supported": False, "active_frame_count": len(flatness)}
    median_flatness = _median(flatness)
    median_concentration = _median(concentration)
    tonal = median_flatness <= 0.1 and median_concentration >= 0.6
    non_tonal = median_flatness >= 0.5 and median_concentration <= 0.2
    return {
        "supported": True,
        "active_frame_count": len(flatness),
        "median_spectral_flatness": f"{median_flatness:.9f}",
        "median_top_8_bin_power_share": f"{median_concentration:.9f}",
        "tonal": tonal,
        "non_tonal": non_tonal,
    }


def classify(samples: Sequence[int]) -> dict[str, Any]:
    occupancy = time_occupancy(samples)
    spectral = spectral_concentration(samples)
    supported = occupancy.get("supported") is True and spectral.get("supported") is True
    sparse_non_tonal = supported and occupancy["sparse"] and spectral["non_tonal"] and not spectral["tonal"]
    tonal_non_sparse = supported and spectral["tonal"] and occupancy["non_sparse"] and not occupancy["sparse"]
    overlap = supported and occupancy["sparse"] and spectral["tonal"]
    return {
        "time_occupancy": occupancy,
        "spectral_concentration": spectral,
        "sparse_non_tonal_contrast": bool(sparse_non_tonal),
        "tonal_non_sparse_contrast": bool(tonal_non_sparse),
        "sparse_tonal_overlap": bool(overlap),
        "abstain": not supported or not (sparse_non_tonal or tonal_non_sparse or overlap),
    }


def build_payload(plan: dict[str, Any]) -> dict[str, Any]:
    source = _load_module(_bound(plan, "identifiability_implementation"), "identifiability")
    contract = load_json(_bound(plan, "identifiability_plan"))["overlap_and_contrast_fixtures"]
    total_frames = contract["sample_rate_hz"] * contract["duration_seconds"]
    rows = []
    for fixture_id in FIXTURE_IDS:
        samples = source.overlap_fixture_samples(
            fixture_id,
            sample_rate=contract["sample_rate_hz"],
            total_frames=total_frames,
            block_frames=contract["block_frames"],
            tone_hz=contract["tone_hz"],
        )
        rows.append({"fixture_id": fixture_id, "descriptor": classify(samples), "source_member_included": False, "trait_truth_included": False})
    return {"synthetic_fixture_results": rows}


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    if shutil.disk_usage(ROOT).free < plan["resources"]["minimum_free_disk_gib"] * 1024**3:
        raise ValueError("free disk reserve not preserved")
    payloads = []
    for _ in range(2):
        with tempfile.TemporaryDirectory(prefix="lossytrace-sparse-tonal-") as directory:
            path = Path(directory) / "payload.json"
            path.write_bytes(canonical_bytes(build_payload(plan)))
            payloads.append(path.read_bytes())
    if payloads[0] != payloads[1]:
        raise ValueError("fresh synthetic replays differ")
    payload = json.loads(payloads[0])
    by_id = {row["fixture_id"]: row["descriptor"] for row in payload["synthetic_fixture_results"]}
    expected = {
        "sparse-tonal-overlap": "sparse_tonal_overlap",
        "sparse-nontonal-contrast": "sparse_non_tonal_contrast",
        "tonal-nonsparse-contrast": "tonal_non_sparse_contrast",
    }
    for fixture_id, key in expected.items():
        if by_id[fixture_id].get(key) is not True:
            raise ValueError(f"synthetic classification gate failed: {fixture_id}")
    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "sparse_tonal_descriptor_synthetic_replay_complete_candidate_access_still_closed",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "implementation_sha256": sha256_file(Path(__file__)),
        "execution": {
            "fresh_temporary_replay_count": 2,
            "payloads_byte_identical": True,
            "maximum_workers": 1,
            "generated_audio_retained": False,
            "actual_or_retained_audio_accessed": False,
        },
        **payload,
        "decision": {
            "descriptor_and_non_overlap_rules_frozen": True,
            "synthetic_fixture_gate_count": 3,
            "synthetic_fixture_gate_pass_count": 3,
            "exact_member_selection_authorized": False,
            "candidate_audio_access_authorized": False,
            "source_trait_assignment_authorized": False,
            "source_trait_manifest_frozen": False,
            "next_gate": "Perform a bounded metadata-only exact-member selection audit. TinySOL may supply a tonal non-sparse candidate, but its pitched-note metadata does not establish the required sparse non-tonal contrast; identify that route before requesting access to any nominated audio.",
            "public_verdict_enabled": False,
        },
        "claim_boundary": plan["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report(load_json(args.plan), args.plan)
    payload = canonical_json_bytes(report)
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != payload:
            print("ERROR: committed report differs from deterministic replay")
            return 1
        print(f"validated {REPORT_ID}")
        return 0
    args.output.write_bytes(payload)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
