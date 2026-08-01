#!/usr/bin/env python3
"""Evaluate development-only learned-plus-explainable forensic conjunctions."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import tempfile
from collections import defaultdict
from pathlib import Path


def load_json(path: Path) -> dict:
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


def case_rows(paths: list[Path]) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for path in paths:
        for row in load_json(path).get("results", []):
            case_id = row["case_id"]
            previous = rows.setdefault(case_id, row)
            if previous != row:
                raise SystemExit(f"conflicting benchmark row: {case_id}")
    if not rows:
        raise SystemExit("benchmark reports contain no result rows")
    return rows


def model_rows(
    paths: list[Path],
) -> tuple[
    dict[str, list[float]],
    dict[str, int],
    dict[str, str],
    list[dict],
]:
    scores: dict[str, list[float]] = defaultdict(list)
    folds: dict[str, int] = {}
    partitions: dict[str, str] = {}
    reports = []
    expected_cases: set[str] | None = None
    for path in paths:
        report = load_json(path)
        rows = report.get("results", [])
        case_ids = {row["case_id"] for row in rows}
        if expected_cases is None:
            expected_cases = case_ids
        elif case_ids != expected_cases:
            raise SystemExit(f"{path}: model reports score different cases")
        for row in rows:
            scores[row["case_id"]].append(row["lossy_probability_mean"])
            previous_fold = folds.setdefault(row["case_id"], row["fold"])
            if previous_fold != row["fold"]:
                raise SystemExit(
                    f"{path}: model reports use different folds for "
                    f"{row['case_id']}"
                )
            partition_group = row.get(
                "partition_group",
                row["source_group"],
            )
            previous_partition = partitions.setdefault(
                row["case_id"],
                partition_group,
            )
            if previous_partition != partition_group:
                raise SystemExit(
                    f"{path}: model reports use different partition groups "
                    f"for {row['case_id']}"
                )
        reports.append(
            {
                "path": str(path),
                "schema_version": report.get("schema_version"),
                "manifest_signature": report.get("manifest_signature"),
                "seed": report.get("seed"),
                "fold_seed": report.get("fold_seed"),
                "case_level_auc": report.get("metrics", {}).get("case_level_auc"),
                "zero_false_positive_boundary": report.get("metrics", {}).get(
                    "zero_false_positive_boundary"
                ),
            }
        )
    if not scores:
        raise SystemExit("model reports contain no result rows")
    return scores, folds, partitions, reports


def flatten_numeric(value: object, prefix: str = "") -> dict[str, float]:
    result: dict[str, float] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            name = f"{prefix}.{key}" if prefix else key
            result.update(flatten_numeric(child, name))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        if math.isfinite(numeric):
            result[prefix] = numeric
    return result


def feature_family(name: str) -> str | None:
    if name.startswith("transform_grid_probe."):
        leaf = name.rsplit(".", 1)[-1]
        if (
            "contrast" in leaf
            or "gap_depletion" in leaf
            or leaf.startswith("phase_")
            or leaf in {"histogram_gap_fraction", "small_coefficient_fraction"}
        ):
            return "transform_grid"
        return None
    if name.startswith("stereo_trace."):
        leaf = name.removeprefix("stereo_trace.")
        if leaf in {
            "high_band_coherence",
            "high_band_coherence_lift",
            "high_band_side_ratio",
            "high_band_side_suppression",
            "strongest_coherence_step",
            "strongest_side_ratio_step",
        }:
            return "stereo"
        return None
    if not name.startswith("compression_trace."):
        return None
    leaf = name.removeprefix("compression_trace.")
    if leaf.startswith("spectral_edge_"):
        return "spectral_edge"
    if "hole" in leaf:
        return "spectral_holes"
    if "rupture" in leaf:
        return "band_rupture"
    if leaf in {
        "transform_alignment_score",
        "transform_alignment_small_coefficient_fraction",
    }:
        return "transform_alignment"
    return None


def auc(positives: list[float], negatives: list[float]) -> float:
    return sum(
        1.0 if positive > negative else 0.5 if positive == negative else 0.0
        for positive in positives
        for negative in negatives
    ) / (len(positives) * len(negatives))


def model_summary(rows: list[dict], score_name: str) -> dict:
    positives = [
        row[score_name]
        for row in rows
        if row["expectation"] == "controlled_positive"
    ]
    negatives = [
        row[score_name] for row in rows if row["expectation"] == "negative"
    ]
    boundary = max(negatives)
    return {
        "case_level_auc": auc(positives, negatives),
        "zero_false_positive_boundary": boundary,
        "controlled_positive_count": len(positives),
        "controlled_positives_above_boundary": sum(
            value > boundary for value in positives
        ),
        "negative_count": len(negatives),
    }


def feature_passes(value: float, threshold: float, direction: str) -> bool:
    if direction == "higher":
        return value > threshold
    return value < threshold


def best_conjunction(
    rows: list[dict],
    feature_name: str,
    direction: str,
    *,
    model_floor: float | None,
    max_feature_negative_rate: float,
) -> dict | None:
    measured = [row for row in rows if feature_name in row["features"]]
    positives = [
        row for row in measured if row["expectation"] == "controlled_positive"
    ]
    negatives = [row for row in measured if row["expectation"] == "negative"]
    if not positives or not negatives:
        return None
    values = sorted({row["features"][feature_name] for row in measured})
    thresholds = values
    standalone_model_boundary = max(
        row["model_ensemble_score"] for row in negatives
    )
    best: dict | None = None
    for feature_threshold in thresholds:
        passing_negatives = [
            row
            for row in negatives
            if feature_passes(
                row["features"][feature_name],
                feature_threshold,
                direction,
            )
        ]
        if not passing_negatives or len(passing_negatives) == len(negatives):
            continue
        if len(passing_negatives) / len(negatives) > max_feature_negative_rate:
            continue
        model_threshold = max(
            row["model_ensemble_score"] for row in passing_negatives
        )
        if model_floor is not None:
            model_threshold = max(model_threshold, model_floor)
        elif model_threshold >= standalone_model_boundary:
            continue
        passing_positives = [
            row
            for row in positives
            if feature_passes(
                row["features"][feature_name],
                feature_threshold,
                direction,
            )
        ]
        detected = [
            row
            for row in passing_positives
            if row["model_ensemble_score"] > model_threshold
        ]
        if not detected:
            continue
        class_counts: dict[str, int] = defaultdict(int)
        for row in detected:
            class_counts[row["class"]] += 1
        candidate = {
            "feature": feature_name,
            "feature_family": feature_family(feature_name),
            "feature_direction": direction,
            "feature_threshold": feature_threshold,
            "model_threshold": model_threshold,
            "measured_positive_count": len(positives),
            "measured_negative_count": len(negatives),
            "feature_passing_positive_count": len(passing_positives),
            "feature_passing_negative_count": len(passing_negatives),
            "feature_passing_negative_rate": (
                len(passing_negatives) / len(negatives)
            ),
            "detected_positive_count": len(detected),
            "detected_by_class": dict(sorted(class_counts.items())),
            "false_positive_count": 0,
        }
        if best is None or (
            candidate["detected_positive_count"],
            candidate["measured_negative_count"],
        ) > (
            best["detected_positive_count"],
            best["measured_negative_count"],
        ):
            best = candidate
    return best


def select_conjunction(rows: list[dict], candidate: dict) -> list[dict]:
    return [
        row
        for row in rows
        if candidate["feature"] in row["features"]
        and feature_passes(
            row["features"][candidate["feature"]],
            candidate["feature_threshold"],
            candidate["feature_direction"],
        )
        and row["model_ensemble_score"] > candidate["model_threshold"]
    ]


def evaluate_selection(rows: list[dict], selected: list[dict]) -> dict:
    false_positives = [
        row for row in selected if row["expectation"] == "negative"
    ]
    detected = [
        row
        for row in selected
        if row["expectation"] == "controlled_positive"
    ]
    class_counts: dict[str, int] = defaultdict(int)
    for row in detected:
        class_counts[row["class"]] += 1
    return {
        "negative_count": sum(
            row["expectation"] == "negative" for row in rows
        ),
        "false_positive_count": len(false_positives),
        "false_positive_case_ids": sorted(
            row["case_id"] for row in false_positives
        ),
        "false_positive_classes": dict(
            sorted(
                (
                    class_name,
                    sum(row["class"] == class_name for row in false_positives),
                )
                for class_name in {row["class"] for row in false_positives}
            )
        ),
        "controlled_positive_count": sum(
            row["expectation"] == "controlled_positive" for row in rows
        ),
        "detected_positive_count": len(detected),
        "detected_by_class": dict(sorted(class_counts.items())),
    }


def evaluate_conjunction(rows: list[dict], candidate: dict) -> dict:
    return evaluate_selection(rows, select_conjunction(rows, candidate))


def select_by_family_count(
    rows: list[dict],
    candidates: dict[str, dict],
    minimum_families: int,
) -> list[dict]:
    families_by_case: dict[str, set[str]] = defaultdict(set)
    row_by_case = {row["case_id"]: row for row in rows}
    for family, candidate in candidates.items():
        for row in select_conjunction(rows, candidate):
            families_by_case[row["case_id"]].add(family)
    return [
        row_by_case[case_id]
        for case_id, families in families_by_case.items()
        if len(families) >= minimum_families
    ]


def nested_policy_evaluation(
    rows: list[dict],
    feature_names: list[str],
    *,
    model_floor: float | None,
    max_feature_negative_rate: float,
    minimum_explainable_families: int,
) -> dict:
    fold_results = []
    for fold in sorted({row["fold"] for row in rows}):
        training = [row for row in rows if row["fold"] != fold]
        validation = [row for row in rows if row["fold"] == fold]
        candidates = []
        for feature_name in feature_names:
            for direction in ("higher", "lower"):
                candidate = best_conjunction(
                    training,
                    feature_name,
                    direction,
                    model_floor=model_floor,
                    max_feature_negative_rate=max_feature_negative_rate,
                )
                if candidate is not None:
                    candidates.append(candidate)
        candidates.sort(
            key=lambda item: (
                -item["detected_positive_count"],
                item["feature"],
                item["feature_direction"],
            )
        )
        best_by_family = {}
        for candidate in candidates:
            best_by_family.setdefault(candidate["feature_family"], candidate)
        by_family = {
            family: {
                "frozen_training_candidate": candidate,
                "validation": evaluate_conjunction(
                    validation,
                    candidate,
                ),
            }
            for family, candidate in sorted(best_by_family.items())
        }
        fold_results.append(
            {
                "fold": fold,
                "training_source_group_count": len(
                    {row["source_group"] for row in training}
                ),
                "training_partition_group_count": len(
                    {row["partition_group"] for row in training}
                ),
                "validation_source_group_count": len(
                    {row["source_group"] for row in validation}
                ),
                "validation_partition_group_count": len(
                    {row["partition_group"] for row in validation}
                ),
                "by_family": by_family,
                "any_explainable_family_validation": evaluate_selection(
                    validation,
                    select_by_family_count(
                        validation,
                        best_by_family,
                        minimum_explainable_families,
                    ),
                ),
            }
        )

    families = [
        *sorted(
        {
            family
            for fold_result in fold_results
            for family in fold_result["by_family"]
        }),
        "any_explainable_family",
    ]
    aggregated = {}
    for family in families:
        if family == "any_explainable_family":
            validations = [
                fold_result["any_explainable_family_validation"]
                for fold_result in fold_results
            ]
        else:
            validations = [
                fold_result["by_family"][family]["validation"]
                for fold_result in fold_results
                if family in fold_result["by_family"]
            ]
        false_positive_classes: dict[str, int] = defaultdict(int)
        detected_by_class: dict[str, int] = defaultdict(int)
        for validation in validations:
            for class_name, count in validation["false_positive_classes"].items():
                false_positive_classes[class_name] += count
            for class_name, count in validation["detected_by_class"].items():
                detected_by_class[class_name] += count
        aggregated[family] = {
            "fold_count": len(validations),
            "negative_count": sum(
                value["negative_count"] for value in validations
            ),
            "false_positive_count": sum(
                value["false_positive_count"] for value in validations
            ),
            "false_positive_classes": dict(sorted(false_positive_classes.items())),
            "controlled_positive_count": sum(
                value["controlled_positive_count"] for value in validations
            ),
            "detected_positive_count": sum(
                value["detected_positive_count"] for value in validations
            ),
            "detected_by_class": dict(sorted(detected_by_class.items())),
        }
    return {
        "method": (
            "For each fold, select a zero-training-false-positive feature and "
            "threshold conjunction on the other four partition-group folds, "
            "then evaluate it without adjustment on the untouched partition "
            "fold."
        ),
        "aggregated_by_family": aggregated,
        "folds": fold_results,
    }


def command(args: argparse.Namespace) -> int:
    if args.model_floor is not None and not 0.0 <= args.model_floor <= 1.0:
        raise SystemExit("--model-floor must be between 0 and 1")
    if not 0.0 < args.max_feature_negative_rate < 1.0:
        raise SystemExit("--max-feature-negative-rate must be between 0 and 1")
    if args.minimum_explainable_families < 1:
        raise SystemExit("--minimum-explainable-families must be at least 1")
    benchmarks = case_rows(args.candidate)
    (
        model_scores,
        model_folds,
        model_partitions,
        model_reports,
    ) = model_rows(args.model_report)
    if set(benchmarks) != set(model_scores):
        only_benchmark = sorted(set(benchmarks) - set(model_scores))
        only_model = sorted(set(model_scores) - set(benchmarks))
        raise SystemExit(
            "benchmark/model case mismatch: "
            f"benchmark_only={only_benchmark[:5]} model_only={only_model[:5]}"
        )

    rows = []
    for case_id in sorted(benchmarks):
        benchmark = benchmarks[case_id]
        runner = benchmark.get("runner", {})
        scores = model_scores[case_id]
        partition_group = benchmark.get(
            "partition_group",
            benchmark["source_group"],
        )
        if model_partitions[case_id] != partition_group:
            raise SystemExit(
                f"{case_id}: benchmark and model partition groups differ"
            )
        features = {}
        for family in (
            "compression_trace",
            "stereo_trace",
            "transform_grid_probe",
        ):
            features.update(flatten_numeric(runner.get(family), family))
        rows.append(
            {
                "case_id": case_id,
                "source_group": benchmark["source_group"],
                "partition_group": partition_group,
                "class": benchmark["class"],
                "expectation": benchmark["expectation"],
                "fold": model_folds[case_id],
                "model_scores": scores,
                "model_ensemble_score": statistics.fmean(scores),
                "features": features,
            }
        )

    feature_names = sorted(
        {
            name
            for row in rows
            for name in row["features"]
            if feature_family(name) is not None
        }
    )
    candidates = []
    for feature_name in feature_names:
        for direction in ("higher", "lower"):
            candidate = best_conjunction(
                rows,
                feature_name,
                direction,
                model_floor=args.model_floor,
                max_feature_negative_rate=args.max_feature_negative_rate,
            )
            if candidate is not None:
                candidates.append(candidate)
    candidates.sort(
        key=lambda item: (
            -item["detected_positive_count"],
            item["feature_family"],
            item["feature"],
            item["feature_direction"],
        )
    )
    best_by_family = {}
    for candidate in candidates:
        family = candidate["feature_family"]
        best_by_family.setdefault(family, candidate)

    write_atomic(
        args.output,
        {
            "schema_version": 1,
            "disposition": {
                "state": "development_only",
                "held_out_opened": False,
                "public_verdict_enabled": False,
                "reason": (
                    "Thresholds were explored on Tier B development data and "
                    "have not passed the frozen Tier A held-out release gate."
                ),
            },
            "model_reports": model_reports,
            "model_ensemble": model_summary(rows, "model_ensemble_score"),
            "conjunction_constraints": {
                "model_floor": args.model_floor,
                "maximum_feature_passing_negative_rate": (
                    args.max_feature_negative_rate
                ),
                "minimum_explainable_family_count": (
                    args.minimum_explainable_families
                ),
            },
            "case_count": len(rows),
            "source_group_count": len(
                {row["source_group"] for row in rows}
            ),
            "partition_group_count": len(
                {row["partition_group"] for row in rows}
            ),
            "best_zero_false_positive_conjunction_by_family": best_by_family,
            "combined_any_explainable_family": evaluate_selection(
                rows,
                select_by_family_count(
                    rows,
                    best_by_family,
                    args.minimum_explainable_families,
                ),
            ),
            "nested_grouped_policy_evaluation": nested_policy_evaluation(
                rows,
                feature_names,
                model_floor=args.model_floor,
                max_feature_negative_rate=args.max_feature_negative_rate,
                minimum_explainable_families=args.minimum_explainable_families,
            ),
            "all_zero_false_positive_conjunctions": candidates,
        },
    )
    print(f"wrote forensic development report to {args.output}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--candidate", type=Path, action="append", required=True)
    result.add_argument("--model-report", type=Path, action="append", required=True)
    result.add_argument("--model-floor", type=float)
    result.add_argument("--max-feature-negative-rate", type=float, default=1.0)
    result.add_argument("--minimum-explainable-families", type=int, default=1)
    result.add_argument("--output", type=Path, required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
