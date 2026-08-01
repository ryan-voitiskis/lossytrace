#!/usr/bin/env python3
"""Apply a frozen development policy to an untouched settings-holdout corpus."""

from __future__ import annotations

import argparse
import json
import math
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


def feature_passes(value: float, threshold: float, direction: str) -> bool:
    if direction == "higher":
        return value > threshold
    if direction == "lower":
        return value < threshold
    raise SystemExit(f"unsupported feature direction: {direction}")


def rows_by_id(report: dict, label: str) -> dict[str, dict]:
    rows = {row["case_id"]: row for row in report.get("results", [])}
    if not rows:
        raise SystemExit(f"{label} contains no result rows")
    if len(rows) != len(report["results"]):
        raise SystemExit(f"{label} contains duplicate case IDs")
    return rows


def summarize(rows: list[dict], selected_ids: set[str]) -> dict:
    false_positives = [
        row
        for row in rows
        if row["case_id"] in selected_ids
        and row["expectation"] == "negative"
    ]
    positives = [
        row
        for row in rows
        if row["case_id"] in selected_ids
        and row["expectation"] == "controlled_positive"
    ]
    by_class: dict[str, dict] = {}
    for class_name in sorted({row["class"] for row in rows}):
        class_rows = [row for row in rows if row["class"] == class_name]
        selected = sum(row["case_id"] in selected_ids for row in class_rows)
        by_class[class_name] = {
            "cases": len(class_rows),
            "selected": selected,
            "rate": selected / len(class_rows),
        }
    return {
        "negative_count": sum(
            row["expectation"] == "negative" for row in rows
        ),
        "false_positive_count": len(false_positives),
        "false_positive_case_ids": sorted(
            row["case_id"] for row in false_positives
        ),
        "controlled_positive_count": sum(
            row["expectation"] == "controlled_positive" for row in rows
        ),
        "detected_positive_count": len(positives),
        "by_class": by_class,
    }


def command(args: argparse.Namespace) -> int:
    candidate_report = load_json(args.candidate)
    score_report = load_json(args.model_score_report)
    policy_report = load_json(args.frozen_policy_report)
    candidates = rows_by_id(candidate_report, "candidate report")
    scores = rows_by_id(score_report, "model score report")
    if set(candidates) != set(scores):
        raise SystemExit("candidate and model score reports contain different cases")

    policy_folds = {
        fold["fold"]: fold
        for fold in policy_report["nested_grouped_policy_evaluation"]["folds"]
    }
    minimum_families = policy_report["conjunction_constraints"].get(
        "minimum_explainable_family_count",
        1,
    )
    selected_by_family: dict[str, set[str]] = defaultdict(set)
    measured_by_family: dict[str, int] = defaultdict(int)
    evaluated_rows = []
    for case_id in sorted(candidates):
        candidate = candidates[case_id]
        score = scores[case_id]
        if candidate["source_group"] != score["source_group"]:
            raise SystemExit(f"{case_id}: source group differs between reports")
        fold = score["fold"]
        if fold not in policy_folds:
            raise SystemExit(f"{case_id}: no frozen policy for fold {fold}")
        runner = candidate["runner"]
        features = {}
        for family_name in (
            "compression_trace",
            "stereo_trace",
            "transform_grid_probe",
        ):
            features.update(flatten_numeric(runner.get(family_name), family_name))

        passing_families = []
        for family, frozen in policy_folds[fold]["by_family"].items():
            conjunction = frozen["frozen_training_candidate"]
            feature = conjunction["feature"]
            if feature not in features:
                continue
            measured_by_family[family] += 1
            if (
                score["lossy_probability_mean"]
                > conjunction["model_threshold"]
                and feature_passes(
                    features[feature],
                    conjunction["feature_threshold"],
                    conjunction["feature_direction"],
                )
            ):
                passing_families.append(family)
                selected_by_family[family].add(case_id)
        evaluated_rows.append(
            {
                "case_id": case_id,
                "source_group": candidate["source_group"],
                "class": candidate["class"],
                "expectation": candidate["expectation"],
                "fold": fold,
                "model_score": score["lossy_probability_mean"],
                "passing_explainable_families": sorted(passing_families),
                "selected": len(passing_families) >= minimum_families,
            }
        )

    selected_ids = {
        row["case_id"] for row in evaluated_rows if row["selected"]
    }
    policy_families = sorted(
        {
            family
            for fold in policy_folds.values()
            for family in fold["by_family"]
        }
    )
    fully_unavailable_families = [
        family
        for family in policy_families
        if measured_by_family[family] == 0
    ]
    partially_unavailable_families = [
        family
        for family in policy_families
        if 0 < measured_by_family[family] < len(evaluated_rows)
    ]
    write_atomic(
        args.output,
        {
            "schema_version": 1,
            "disposition": {
                "state": "development_settings_holdout",
                "source_groups_held_out": False,
                "codec_settings_held_out": True,
                "models_retrained": False,
                "thresholds_retuned": False,
                "public_verdict_enabled": False,
                "reason": (
                    "This applies previously frozen fold policies to unseen "
                    "codec settings on reused Tier B source groups."
                ),
            },
            "source_candidate": {
                "corpus_id": candidate_report.get("corpus_id"),
                "result_count": len(candidates),
                "feature_version": candidate_report.get("feature_version"),
                "exact_transform_grid_available": (
                    measured_by_family["transform_grid"] > 0
                ),
            },
            "source_model_score": {
                "manifest_signature": score_report.get("manifest_signature"),
                "model_set_count": len(score_report.get("model_sets", [])),
            },
            "source_frozen_policy": {
                "minimum_explainable_family_count": minimum_families,
                "measured_case_count_by_family": dict(
                    sorted(measured_by_family.items())
                ),
                "fully_unavailable_explainable_families": (
                    fully_unavailable_families
                ),
                "partially_unavailable_explainable_families": (
                    partially_unavailable_families
                ),
            },
            "combined_frozen_policy": summarize(
                evaluated_rows,
                selected_ids,
            ),
            "by_explainable_family": {
                family: summarize(evaluated_rows, case_ids)
                for family, case_ids in sorted(selected_by_family.items())
            },
            "results": evaluated_rows,
        },
    )
    print(f"wrote frozen-policy holdout evaluation to {args.output}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--candidate", type=Path, required=True)
    result.add_argument("--model-score-report", type=Path, required=True)
    result.add_argument("--frozen-policy-report", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
