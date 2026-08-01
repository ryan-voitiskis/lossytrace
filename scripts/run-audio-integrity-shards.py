#!/usr/bin/env python3
"""Run deterministic benchmark shards with fail-closed resume validation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HARNESS = ROOT / "scripts/benchmark-audio-integrity.py"
DEFAULT_BINARY = ROOT / "target/release/examples/audio_integrity_benchmark"


def load_object(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def validate_report(manifest: dict, report: dict) -> None:
    if report.get("schema_version") != 1 or report.get("feature_version") != 0:
        raise ValueError("report must use schema 1 and feature version 0")
    if report.get("corpus_id") != manifest.get("corpus_id"):
        raise ValueError("report corpus_id differs from its shard manifest")
    gate = report.get("gate_disposition")
    if not isinstance(gate, dict) or gate.get("likely_lossy_derived_enabled") is not False:
        raise ValueError("report must keep the public verdict disabled")
    expected = {case["case_id"] for case in manifest.get("cases", [])}
    actual = {row["case_id"] for row in report.get("results", [])}
    if len(expected) != len(manifest.get("cases", [])) or expected != actual:
        raise ValueError("report cases differ from its shard manifest")
    if any(
        not isinstance(row.get("runner"), dict)
        or row["runner"].get("research_transform_grid_enabled") is not False
        or row["runner"].get("research_transform_grid_profile") is not None
        or row["runner"].get("transform_grid_probe") is not None
        for row in report.get("results", [])
    ):
        raise ValueError("baseline report must disable the legacy transform-grid probe")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard-directory", type=Path, required=True)
    parser.add_argument("--report-directory", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--harness", type=Path, default=DEFAULT_HARNESS)
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--jobs", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.jobs <= 8:
        raise SystemExit("--jobs must be in 1..=8")
    shard_directory = args.shard_directory.expanduser().resolve()
    report_directory = args.report_directory.expanduser().resolve()
    audio_root = args.audio_root.expanduser().resolve()
    harness = args.harness.expanduser().resolve()
    binary = args.binary.expanduser().resolve()
    manifests = sorted(shard_directory.glob("manifest-*.json"))
    if not manifests:
        raise SystemExit(f"no shard manifests found in {shard_directory}")
    if not audio_root.is_dir() or not harness.is_file() or not binary.is_file():
        raise SystemExit("audio root, harness, and binary must exist")
    report_directory.mkdir(parents=True, exist_ok=True)

    for index, manifest_path in enumerate(manifests, 1):
        report_path = report_directory / manifest_path.name.replace(
            "manifest-", "report-"
        )
        try:
            manifest = load_object(manifest_path)
            if report_path.exists():
                validate_report(manifest, load_object(report_path))
                print(f"[{index:03d}/{len(manifests):03d}] verified existing {report_path.name}")
                continue
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise SystemExit(f"cannot resume {manifest_path.name}: {error}") from error
        print(f"[{index:03d}/{len(manifests):03d}] running {manifest_path.name}")
        completed = subprocess.run(
            [
                sys.executable,
                str(harness),
                "--manifest",
                str(manifest_path),
                "run",
                "--audio-root",
                str(audio_root),
                "--jobs",
                str(args.jobs),
                "--no-build",
                "--binary",
                str(binary),
                "--output",
                str(report_path),
            ],
            cwd=ROOT,
            env={**os.environ, "LOSSYTRACE_RESEARCH_SKIP_TRANSFORM_GRID": "1"},
            check=False,
        )
        if completed.returncode:
            return completed.returncode
        try:
            validate_report(manifest, load_object(report_path))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise SystemExit(f"new report failed validation: {error}") from error
    print(f"verified all {len(manifests)} shard reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
