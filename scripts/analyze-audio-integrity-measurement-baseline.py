#!/usr/bin/env python3
"""Create a path-free aggregate baseline from a private measurement report."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import tempfile
from collections import defaultdict
from pathlib import Path


FEATURE_FIELDS = (
    "median_active_bin_fraction",
    "spectral_edge_hz",
    "spectral_edge_drop_db",
    "spectral_edge_persistence",
    "spectral_edge_spread_hz",
    "spectral_hole_ratio",
    "isolated_hole_ratio",
    "band_rupture_score",
    "transform_alignment_score",
    "transform_alignment_small_coefficient_fraction",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


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


def summarize_rows(rows: list[dict]) -> dict:
    source_groups = {row["source_group"] for row in rows}
    high_band_supported = [
        row for row in rows if row["features"].get("spectral_edge_hz") is not None
    ]
    transform_supported = [
        row
        for row in rows
        if row["features"].get("transform_alignment_score") is not None
    ]
    features = {}
    for field in FEATURE_FIELDS:
        values = [
            float(row["features"][field])
            for row in rows
            if row["features"].get(field) is not None
        ]
        features[field] = {
            "measured_cases": len(values),
            "median": statistics.median(values) if values else None,
            "p05": quantile(values, 0.05),
            "p95": quantile(values, 0.95),
        }
    return {
        "case_count": len(rows),
        "source_group_count": len(source_groups),
        "high_band_supported_case_count": len(high_band_supported),
        "high_band_supported_source_group_count": len(
            {row["source_group"] for row in high_band_supported}
        ),
        "transform_supported_case_count": len(transform_supported),
        "transform_supported_source_group_count": len(
            {row["source_group"] for row in transform_supported}
        ),
        "features": features,
    }


def paired_deltas(rows: list[dict]) -> dict:
    by_group: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_group[row["source_group"]].append(row)
    output = {}
    for field in FEATURE_FIELDS:
        deltas = []
        eligible_groups = 0
        for group_rows in by_group.values():
            negative_values = [
                float(row["features"][field])
                for row in group_rows
                if row["expectation"] == "negative"
                and row["features"].get(field) is not None
            ]
            positive_values = [
                float(row["features"][field])
                for row in group_rows
                if row["expectation"] == "controlled_positive"
                and row["features"].get(field) is not None
            ]
            if not negative_values or not positive_values:
                continue
            eligible_groups += 1
            deltas.append(
                statistics.median(positive_values)
                - statistics.median(negative_values)
            )
        output[field] = {
            "eligible_source_group_count": eligible_groups,
            "positive_delta_group_count": sum(delta > 0 for delta in deltas),
            "zero_delta_group_count": sum(delta == 0 for delta in deltas),
            "negative_delta_group_count": sum(delta < 0 for delta in deltas),
            "median_within_group_delta": statistics.median(deltas) if deltas else None,
            "p05_within_group_delta": quantile(deltas, 0.05),
            "p95_within_group_delta": quantile(deltas, 0.95),
        }
    return output


def analyze(manifest: dict, report: dict, manifest_sha256: str, report_sha256: str) -> dict:
    if manifest.get("schema_version") != 1:
        raise ValueError("manifest schema_version must be 1")
    if manifest.get("evidence_partition") != "observed_development":
        raise ValueError("manifest must be explicitly marked observed_development")
    if manifest.get("holdout_scores_opened") is not False:
        raise ValueError("manifest must record that holdout scores remain unopened")
    if report.get("schema_version") != 1 or report.get("feature_version") != 0:
        raise ValueError("raw report must use schema 1 and feature version 0")
    gate = report.get("gate_disposition")
    if not isinstance(gate, dict) or gate.get("likely_lossy_derived_enabled") is not False:
        raise ValueError("raw report must keep the public verdict disabled")

    manifest_cases = manifest.get("cases")
    report_results = report.get("results")
    if not isinstance(manifest_cases, list) or not isinstance(report_results, list):
        raise ValueError("manifest cases and report results must be arrays")
    metadata = {case["case_id"]: case for case in manifest_cases}
    results = {row["case_id"]: row for row in report_results}
    if len(metadata) != len(manifest_cases) or len(results) != len(report_results):
        raise ValueError("case IDs must be unique")
    if metadata.keys() != results.keys():
        raise ValueError("raw report case IDs differ from the manifest")

    rows = []
    for case_id in sorted(metadata):
        case = metadata[case_id]
        result = results[case_id]
        if result.get("source_group") != case.get("source_group"):
            raise ValueError(f"source_group differs for {case_id}")
        if result.get("expectation") != case.get("expectation"):
            raise ValueError(f"expectation differs for {case_id}")
        runner = result.get("runner")
        if (
            not isinstance(runner, dict)
            or runner.get("research_transform_grid_enabled") is not False
            or runner.get("research_transform_grid_profile") is not None
            or runner.get("transform_grid_probe") is not None
        ):
            raise ValueError(f"legacy transform-grid probe enabled for {case_id}")
        features = runner.get("compression_trace") if isinstance(runner, dict) else None
        if not isinstance(features, dict):
            raise ValueError(f"missing compression_trace for {case_id}")
        for field in FEATURE_FIELDS:
            value = features.get(field)
            if value is not None and (
                not isinstance(value, (int, float)) or not math.isfinite(value)
            ):
                raise ValueError(f"invalid {field} for {case_id}")
        rows.append(
            {
                "source_group": case["source_group"],
                "source_domain": case["source_domain"],
                "class": case["class"],
                "expectation": case["expectation"],
                "provenance_tier": case["provenance_tier"],
                "features": features,
            }
        )

    def grouped_summary(field: str) -> dict:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[row[field]].append(row)
        return {
            name: summarize_rows(group_rows)
            for name, group_rows in sorted(grouped.items())
        }

    return {
        "schema_version": 2,
        "state": "experimental_measurement_baseline",
        "feature_version": 0,
        "public_verdict_enabled": False,
        "evidence_partition": "observed_development",
        "independent_validation": False,
        "holdout_scores_opened": False,
        "inputs": {
            "manifest_sha256": manifest_sha256,
            "raw_report_sha256": report_sha256,
            "runner_sha256": report.get("runner_sha256"),
            "harness_sha256": report.get("harness_sha256"),
        },
        "inventory": {
            "case_count": len(rows),
            "source_group_count": len({row["source_group"] for row in rows}),
            "negative_case_count": sum(
                row["expectation"] == "negative" for row in rows
            ),
            "controlled_positive_case_count": sum(
                row["expectation"] == "controlled_positive" for row in rows
            ),
        },
        "runtime": report.get("runtime"),
        "overall": summarize_rows(rows),
        "by_expectation": grouped_summary("expectation"),
        "by_provenance_tier": grouped_summary("provenance_tier"),
        "by_source_domain": grouped_summary("source_domain"),
        "by_class": grouped_summary("class"),
        "within_source_group_positive_minus_negative": paired_deltas(rows),
        "interpretation": {
            "classification_metrics_available": False,
            "calibration_metrics_available": False,
            "reason": (
                "Feature version 0 emits measurements without a frozen score, "
                "policy, confidence, or verdict. This baseline measures support "
                "and separation only."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.expanduser().resolve()
    report_path = args.report.expanduser().resolve()
    try:
        value = analyze(
            load_object(manifest_path),
            load_object(report_path),
            sha256_file(manifest_path),
            sha256_file(report_path),
        )
        write_new(args.output.expanduser().resolve(), value)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(
        f"wrote path-free schema-{value['schema_version']} baseline for "
        f"{value['inventory']['case_count']} cases to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
