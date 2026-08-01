#!/usr/bin/env python3
"""Summarize an audio-integrity development candidate without making policy."""

from __future__ import annotations

import argparse
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
CONTROL_CLASSES = (
    "gain_only_pcm",
    "trim_only_pcm",
    "dither_16_pcm",
    "lowpass_only_pcm",
    "sharp_lowpass_only_pcm",
)
FAMILY_FIELDS = {
    "edge": ("spectral_edge_drop_db", "spectral_edge_persistence"),
    "holes": ("spectral_hole_ratio", "isolated_hole_ratio"),
    "rupture": ("band_rupture_score",),
    "transform_alignment": (
        "transform_alignment_score",
        "transform_alignment_small_coefficient_fraction",
    ),
}


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
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


def summary(values: list[float]) -> dict:
    return {
        "count": len(values),
        "median": statistics.median(values) if values else None,
        "p05": quantile(values, 0.05),
        "p95": quantile(values, 0.95),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def feature(row: dict, field: str) -> float | None:
    return row["runner"]["compression_trace"].get(field)


def auc_higher(positives: list[float], negatives: list[float]) -> float | None:
    if not positives or not negatives:
        return None
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            if positive > negative:
                wins += 1
            elif positive == negative:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> dict:
    if total == 0:
        return {"low": None, "high": None}
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return {"low": center - radius, "high": center + radius}


def zero_false_positive(
    positives: list[float], negatives: list[float]
) -> dict:
    if not positives or not negatives:
        return {
            "direction": None,
            "threshold": None,
            "detected": 0,
            "measured": len(positives),
            "rate": None,
        }
    higher_threshold = max(negatives)
    higher_detected = sum(value > higher_threshold for value in positives)
    lower_threshold = min(negatives)
    lower_detected = sum(value < lower_threshold for value in positives)
    if higher_detected >= lower_detected:
        direction = "higher"
        threshold = higher_threshold
        detected = higher_detected
    else:
        direction = "lower"
        threshold = lower_threshold
        detected = lower_detected
    return {
        "direction": direction,
        "threshold": threshold,
        "detected": detected,
        "measured": len(positives),
        "rate": detected / len(positives),
        "rate_95_percent_ci": wilson(detected, len(positives)),
    }


def threshold_candidates(rows: list[dict], field: str) -> list[float]:
    values = [
        value
        for row in rows
        if (value := feature(row, field)) is not None
    ]
    candidates = {
        quantile(values, index / 40)
        for index in range(41)
        if values
    }
    return sorted(value for value in candidates if value is not None)


def fires(
    row: dict, field: str, threshold: float, direction: str
) -> bool:
    value = feature(row, field)
    if value is None:
        return False
    if direction == "higher":
        return value > threshold
    if direction == "lower":
        return value < threshold
    raise ValueError(f"unknown threshold direction: {direction}")


def search_conjunction(
    rows: list[dict],
    negatives: list[dict],
    positives: list[dict],
    first_field: str,
    second_field: str,
) -> dict:
    best: dict | None = None
    first_negative_values = [
        value
        for row in negatives
        if (value := feature(row, first_field)) is not None
    ]
    second_negative_values = [
        value
        for row in negatives
        if (value := feature(row, second_field)) is not None
    ]
    quantiles = {
        "higher": 0.95,
        "lower": 0.05,
    }
    for first_direction, first_quantile in quantiles.items():
        first_boundary = quantile(first_negative_values, first_quantile)
        first_candidates = [
            value
            for value in threshold_candidates(rows, first_field)
            if first_boundary is not None
            and (
                value >= first_boundary
                if first_direction == "higher"
                else value <= first_boundary
            )
        ]
        for second_direction, second_quantile in quantiles.items():
            second_boundary = quantile(
                second_negative_values, second_quantile
            )
            second_candidates = [
                value
                for value in threshold_candidates(rows, second_field)
                if second_boundary is not None
                and (
                    value >= second_boundary
                    if second_direction == "higher"
                    else value <= second_boundary
                )
            ]
            for first_threshold in first_candidates:
                for second_threshold in second_candidates:
                    false_positives = sum(
                        fires(
                            row,
                            first_field,
                            first_threshold,
                            first_direction,
                        )
                        and fires(
                            row,
                            second_field,
                            second_threshold,
                            second_direction,
                        )
                        for row in negatives
                    )
                    if false_positives:
                        continue
                    detected_rows = [
                        row
                        for row in positives
                        if fires(
                            row,
                            first_field,
                            first_threshold,
                            first_direction,
                        )
                        and fires(
                            row,
                            second_field,
                            second_threshold,
                            second_direction,
                        )
                    ]
                    by_class: dict[str, int] = defaultdict(int)
                    for row in detected_rows:
                        by_class[row["class"]] += 1
                    candidate = {
                        "first_field": first_field,
                        "first_direction": first_direction,
                        "first_threshold_exclusive": first_threshold,
                        "first_development_negative_boundary": first_boundary,
                        "second_field": second_field,
                        "second_direction": second_direction,
                        "second_threshold_exclusive": second_threshold,
                        "second_development_negative_boundary": (
                            second_boundary
                        ),
                        "development_false_positives": 0,
                        "detected": len(detected_rows),
                        "total_positives": len(positives),
                        "rate": len(detected_rows) / len(positives),
                        "detected_by_class": dict(sorted(by_class.items())),
                    }
                    if best is None or (
                        candidate["detected"],
                        len(candidate["detected_by_class"]),
                    ) > (
                        best["detected"],
                        len(best["detected_by_class"]),
                    ):
                        best = candidate
    return best or {
        "first_field": first_field,
        "second_field": second_field,
        "development_false_positives": 0,
        "detected": 0,
        "total_positives": len(positives),
        "rate": 0,
        "detected_by_class": {},
    }


def analyze(candidate: dict) -> dict:
    rows = candidate["results"]
    by_class: dict[str, list[dict]] = defaultdict(list)
    by_source: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        by_class[row["class"]].append(row)
        by_source[row["source_group"]][row["class"]] = row

    negatives = [row for row in rows if row["expectation"] == "negative"]
    positives = [
        row for row in rows if row["expectation"] == "controlled_positive"
    ]
    positive_classes = sorted({row["class"] for row in positives})

    class_analysis: dict[str, dict] = {}
    for class_name in positive_classes:
        class_rows = by_class[class_name]
        fields: dict[str, dict] = {}
        for field in FEATURE_FIELDS:
            positive_values = [
                value
                for row in class_rows
                if (value := feature(row, field)) is not None
            ]
            negative_values = [
                value
                for row in negatives
                if (value := feature(row, field)) is not None
            ]
            auc = auc_higher(positive_values, negative_values)
            deltas = []
            for row in class_rows:
                baseline = by_source[row["source_group"]].get(
                    "untouched_lossless"
                )
                value = feature(row, field)
                baseline_value = feature(baseline, field) if baseline else None
                if value is not None and baseline_value is not None:
                    deltas.append(value - baseline_value)
            fields[field] = {
                "raw": summary(positive_values),
                "paired_delta_from_untouched": summary(deltas),
                "auc_higher_vs_all_development_negatives": auc,
                "auc_best_direction_vs_all_development_negatives": (
                    max(auc, 1 - auc) if auc is not None else None
                ),
                "zero_false_positive_single_feature": zero_false_positive(
                    positive_values, negative_values
                ),
            }
        class_analysis[class_name] = {
            "cases": len(class_rows),
            "features": fields,
        }

    control_invariance: dict[str, dict] = {}
    for class_name in CONTROL_CLASSES:
        fields = {}
        for field in FEATURE_FIELDS:
            absolute_deltas = []
            for row in by_class[class_name]:
                baseline = by_source[row["source_group"]].get(
                    "untouched_lossless"
                )
                value = feature(row, field)
                baseline_value = feature(baseline, field) if baseline else None
                if value is not None and baseline_value is not None:
                    absolute_deltas.append(abs(value - baseline_value))
            fields[field] = summary(absolute_deltas)
        control_invariance[class_name] = fields

    conjunctions = []
    family_names = tuple(FAMILY_FIELDS)
    for first_index, first_family in enumerate(family_names):
        for second_family in family_names[first_index + 1 :]:
            for first_field in FAMILY_FIELDS[first_family]:
                for second_field in FAMILY_FIELDS[second_family]:
                    result = search_conjunction(
                        rows,
                        negatives,
                        positives,
                        first_field,
                        second_field,
                    )
                    result["first_family"] = first_family
                    result["second_family"] = second_family
                    conjunctions.append(result)
    conjunctions.sort(
        key=lambda value: (
            value["detected"],
            len(value["detected_by_class"]),
        ),
        reverse=True,
    )

    return {
        "schema_version": 1,
        "source_candidate": {
            "corpus_id": candidate["corpus_id"],
            "feature_version": candidate["feature_version"],
            "analysis_max_seconds": candidate["analysis_max_seconds"],
            "repetitions": candidate["repetitions"],
            "result_count": len(rows),
        },
        "disposition": {
            "state": "development_only",
            "likely_lossy_derived_enabled": False,
            "reason": (
                "Thresholds are exploratory and selected on Tier B "
                "development audio; no independent Tier A held-out gate ran."
            ),
        },
        "counts": {
            "source_groups": len(by_source),
            "development_negatives": len(negatives),
            "controlled_positives": len(positives),
        },
        "class_analysis": class_analysis,
        "control_invariance": control_invariance,
        "exploratory_zero_false_positive_two_family_conjunctions": conjunctions,
        "runtime": candidate["runtime"],
        "limitations": [
            "Tier B trusted-commercial development sources, not Tier A "
            "confirmed pristine PCM masters.",
            "Ninety-second analysis windows rather than the preserved "
            "full-track release manifest.",
            "No independent held-out labels or release evaluation.",
            "Runtime uses one repetition under bounded concurrency and is not "
            "eligible for the release overhead gate.",
            "Thresholds were selected on the development rows and are "
            "descriptive, not a policy.",
        ],
    }


def merge_candidates(candidates: list[dict]) -> dict:
    first = candidates[0]
    feature_versions = {candidate["feature_version"] for candidate in candidates}
    analysis_windows = {
        candidate["analysis_max_seconds"] for candidate in candidates
    }
    if len(feature_versions) != 1:
        raise SystemExit("candidate feature versions differ")
    if len(analysis_windows) != 1:
        raise SystemExit("candidate analysis windows differ")
    results = []
    seen_case_ids: set[str] = set()
    for candidate in candidates:
        for row in candidate["results"]:
            if row["case_id"] in seen_case_ids:
                raise SystemExit(f"duplicate case_id: {row['case_id']}")
            seen_case_ids.add(row["case_id"])
            results.append(row)
    return {
        "corpus_id": "+".join(
            candidate["corpus_id"] for candidate in candidates
        ),
        "feature_version": first["feature_version"],
        "analysis_max_seconds": first["analysis_max_seconds"],
        "repetitions": min(
            candidate["repetitions"] for candidate in candidates
        ),
        "results": results,
        "runtime": {
            "gate_evaluable": all(
                candidate["repetitions"] >= 3
                and candidate["runtime"].get("jobs", 1) == 1
                for candidate in candidates
            ),
            "component_runs": [
                {
                    "corpus_id": candidate["corpus_id"],
                    "runtime": candidate["runtime"],
                }
                for candidate in candidates
            ]
        },
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument(
        "--candidate", type=Path, action="append", required=True
    )
    root.add_argument("--output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    report = analyze(merge_candidates([load(path) for path in args.candidate]))
    write_atomic(args.output, report)
    print(
        f"analyzed {report['source_candidate']['result_count']} results; "
        f"wrote {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
