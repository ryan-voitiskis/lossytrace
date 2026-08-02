#!/usr/bin/env python3
"""Validate the public-decoder lossless-wrapper equivalence result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_REPORT_SHA256 = (
    "e18ebce9101a59321fe7fcf509222b78d2218476653a091396e596de72520683"
)
EXPECTED_PLAN_SHA256 = (
    "581c76772d93019fba4d12f01dd04f95fdd5f8d51163bcd3dc45519f36f4f30b"
)
EXPECTED_BINARY_SHA256 = (
    "af8bd1389f55325a01ad7ebd48d2ad050a3f8028dccd6ee69262548028d54cb4"
)


def load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(
    report: dict[str, Any],
    plan: dict[str, Any],
    binding: dict[str, Any],
    manifest: dict[str, Any],
    report_path: Path,
    repository_root: Path,
) -> list[str]:
    errors: list[str] = []
    expected_state = {
        "schema_version": 1,
        "probe_id": "lossytrace-v2-public-decoder-equivalence-probe-20260802-001",
        "state": "public_decoder_synthetic_wrapper_equivalence_evidence_only",
        "benchmark_audio_generated": False,
        "source_groups_assigned": False,
        "scores_opened": False,
        "selection_authorized": False,
        "public_verdict_enabled": False,
        "paths_redacted": True,
    }
    for field, expected in expected_state.items():
        if report.get(field) != expected:
            errors.append(f"report {field} differs")
    if sha256_file(report_path) != EXPECTED_REPORT_SHA256:
        errors.append("committed report hash differs")
    if (
        sha256_file(
            repository_root
            / "benchmarks/audio-integrity-v2/public-decoder-equivalence-plan.json"
        )
        != EXPECTED_PLAN_SHA256
        or report.get("plan_binding")
        != {"plan_id": plan.get("plan_id"), "sha256": EXPECTED_PLAN_SHA256}
    ):
        errors.append("plan binding differs")
    if report.get("binary_binding") != {
        "binding_id": binding.get("binding_id"),
        "sha256": EXPECTED_BINARY_SHA256,
    } or binding.get("binary", {}).get("sha256") != EXPECTED_BINARY_SHA256:
        errors.append("public binary binding differs")
    if report.get("toolchain_manifest_binding") != {
        "toolchain_freeze_id": manifest.get("toolchain_freeze_id")
    }:
        errors.append("toolchain manifest binding differs")
    probe_path = repository_root / "scripts/probe-audio-integrity-v2-public-decoder.py"
    base_path = repository_root / "scripts/probe-audio-integrity-v2-toolchains.py"
    if (
        binding.get("probe_script_sha256") != sha256_file(probe_path)
        or binding.get("base_probe_script_sha256") != sha256_file(base_path)
    ):
        errors.append("probe implementation binding differs")

    input_ids = {
        "synthetic-44100-mono",
        "synthetic-44100-stereo",
        "synthetic-48000-mono",
        "synthetic-48000-stereo",
    }
    wrapper_ids = {"flac16", "wav16", "aiff16"}
    paths = report.get("wrapper_paths", [])
    if (
        len(paths) != 12
        or {(row.get("input_id"), row.get("wrapper_id")) for row in paths}
        != {(input_id, wrapper_id) for input_id in input_ids for wrapper_id in wrapper_ids}
        or any(
            row.get("analysis_decoded_pcm_exactly_matches_input") is not True
            or row.get("public_report_deterministic_across_two_runs") is not True
            for row in paths
        )
    ):
        errors.append("wrapper path evidence differs")
    for input_id in input_ids:
        rows = [row for row in paths if row.get("input_id") == input_id]
        if (
            len({row.get("analysis_decoded_pcm_sha256") for row in rows}) != 1
            or len({row.get("public_projection_sha256") for row in rows}) != 1
        ):
            errors.append(f"wrapper triplet hashes differ for {input_id}")

    triplets = report.get("triplets", [])
    if (
        len(triplets) != 4
        or {row.get("input_id") for row in triplets} != input_ids
        or any(
            row.get("wrapper_count") != 3
            or row.get("exact_public_projection_equivalent") is not True
            for row in triplets
        )
    ):
        errors.append("triplet summary differs")
    if report.get("summary") != {
        "wrapper_path_count": 12,
        "triplet_count": 4,
        "all_analysis_decoded_pcm_exact": True,
        "all_public_reports_deterministic": True,
        "all_public_wrapper_projections_exact": True,
    }:
        errors.append("aggregate summary differs")

    serialized = json.dumps(report, sort_keys=True)
    if any(token in serialized for token in ("/Users/", "/Volumes/", "\\Users\\")):
        errors.append("report contains a private path")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument(
        "--plan",
        default=Path("benchmarks/audio-integrity-v2/public-decoder-equivalence-plan.json"),
        type=Path,
    )
    parser.add_argument(
        "--binding",
        default=Path("benchmarks/audio-integrity-v2/public-decoder-binary-binding.json"),
        type=Path,
    )
    parser.add_argument(
        "--toolchain-manifest",
        default=Path("benchmarks/audio-integrity-v2/toolchain-bindings.json"),
        type=Path,
    )
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    report_path = args.report.expanduser().resolve()
    errors = validate(
        load_object(report_path),
        load_object(args.plan.expanduser().resolve()),
        load_object(args.binding.expanduser().resolve()),
        load_object(args.toolchain_manifest.expanduser().resolve()),
        report_path,
        repository_root,
    )
    if errors:
        print("public decoder result validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("public decoder result valid: exact wrapper projections, verdict-free")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
