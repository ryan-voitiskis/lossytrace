#!/usr/bin/env python3
"""Combine verified measurement shards into one raw private benchmark report."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import tempfile
from pathlib import Path


def load_object(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise ValueError(f"refusing to replace existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def quantile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = proportion * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def combine(full_manifest: dict, shards: list[tuple[Path, dict, Path, dict]]) -> dict:
    expected = {case["case_id"] for case in full_manifest.get("cases", [])}
    if len(expected) != len(full_manifest.get("cases", [])):
        raise ValueError("full manifest case IDs must be unique")
    all_results = []
    seen: set[str] = set()
    runner_hashes = set()
    harness_hashes = set()
    evidence = []
    for manifest_path, manifest, report_path, report in shards:
        if report.get("corpus_id") != manifest.get("corpus_id"):
            raise ValueError(f"{report_path}: corpus_id differs")
        if report.get("schema_version") != 1 or report.get("feature_version") != 0:
            raise ValueError(f"{report_path}: schema or feature version differs")
        gate = report.get("gate_disposition")
        if not isinstance(gate, dict) or gate.get("likely_lossy_derived_enabled") is not False:
            raise ValueError(f"{report_path}: public verdict is not disabled")
        shard_expected = {case["case_id"] for case in manifest.get("cases", [])}
        rows = report.get("results")
        if not isinstance(rows, list):
            raise ValueError(f"{report_path}: results must be an array")
        shard_actual = {row["case_id"] for row in rows}
        if shard_expected != shard_actual or len(rows) != len(shard_actual):
            raise ValueError(f"{report_path}: cases differ from shard manifest")
        overlap = seen & shard_actual
        if overlap:
            raise ValueError(f"case occurs in more than one shard: {min(overlap)}")
        if any(
            not isinstance(row.get("runner"), dict)
            or row["runner"].get("research_transform_grid_enabled") is not False
            or row["runner"].get("research_transform_grid_profile") is not None
            or row["runner"].get("transform_grid_probe") is not None
            for row in rows
        ):
            raise ValueError(f"{report_path}: legacy transform-grid probe was enabled")
        seen.update(shard_actual)
        all_results.extend(rows)
        runner_hashes.add(report.get("runner_sha256"))
        harness_hashes.add(report.get("harness_sha256"))
        evidence.append(
            {
                "manifest_sha256": sha256_file(manifest_path),
                "report_sha256": sha256_file(report_path),
                "case_count": len(rows),
            }
        )
    if seen != expected:
        raise ValueError("combined shard cases differ from the full manifest")
    if len(runner_hashes) != 1 or len(harness_hashes) != 1:
        raise ValueError("shards used different runner or harness builds")
    overhead = [row["runner"]["runtime_overhead_percent"] for row in all_results]
    return {
        "schema_version": 1,
        "corpus_id": full_manifest["corpus_id"],
        "corpus_version": full_manifest["corpus_version"],
        "feature_version": 0,
        "runner_sha256": next(iter(runner_hashes)),
        "harness_sha256": next(iter(harness_hashes)),
        "analysis_max_seconds": full_manifest["analysis_max_seconds"],
        "repetitions": full_manifest["repetitions"],
        "gate_disposition": {
            "state": "not_evaluated",
            "likely_lossy_derived_enabled": False,
            "reason": "Measurements are uncalibrated observed evidence; no held-out release evaluation was opened.",
        },
        "runtime": {
            "cases": len(overhead),
            "jobs_per_shard": 1,
            "overhead_median_percent": statistics.median(overhead),
            "overhead_p95_percent": quantile(overhead, 0.95),
        },
        "shard_evidence_schema_version": 1,
        "shards": evidence,
        "results": sorted(all_results, key=lambda row: row["case_id"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--shard-directory", type=Path, required=True)
    parser.add_argument("--report-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest_path = args.manifest.expanduser().resolve()
        shard_directory = args.shard_directory.expanduser().resolve()
        report_directory = args.report_directory.expanduser().resolve()
        shard_paths = sorted(shard_directory.glob("manifest-*.json"))
        shards = []
        for shard_path in shard_paths:
            report_path = report_directory / shard_path.name.replace(
                "manifest-", "report-"
            )
            shards.append(
                (
                    shard_path,
                    load_object(shard_path),
                    report_path,
                    load_object(report_path),
                )
            )
        if not shards:
            raise ValueError("no shard manifests found")
        value = combine(load_object(manifest_path), shards)
        write_new(args.output.expanduser().resolve(), value)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(f"combined {len(shards)} shards and {len(value['results'])} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
