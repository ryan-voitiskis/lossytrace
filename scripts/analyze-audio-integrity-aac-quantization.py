#!/usr/bin/env python3
"""Run source-grouped analysis of AAC quantization research scores."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

FEATURES = (
    "score",
    "median",
    "p95",
    "mad",
    "peak_excess_median",
    "peak_excess_p95",
    "peak_mad_z",
    "prominence",
    "alert_fraction",
    "tie_count",
)
OUTER_FOLD_COUNT = 5
GUARD_QUANTILE_STEPS = 20
MINIMUM_ELIGIBLE_NEGATIVE_GROUPS = 20


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_atomic(path: Path, value: dict) -> None:
    path = path.expanduser().resolve()
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace analysis: {path}")
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


def feature_values(row: dict) -> dict[str, float]:
    score = float(row["aac_quantization_probability"])
    median = float(row["offset_probability_median"])
    p95 = float(row["offset_probability_p95"])
    peak_mad_z = row["offset_peak_mad_z"]
    return {
        "score": score,
        "median": median,
        "p95": p95,
        "mad": float(row["offset_probability_mad"]),
        "peak_excess_median": score - median,
        "peak_excess_p95": score - p95,
        "peak_mad_z": float(peak_mad_z or 0.0),
        "prominence": float(
            row["offset_peak_prominence_outside_radius_8"]
        ),
        "alert_fraction": float(row["offset_fixed_alert_fraction"]),
        "tie_count": float(row["offset_peak_tie_count"]),
    }


def outer_fold(source_group: str) -> int:
    digest = hashlib.sha256(source_group.encode()).digest()
    return int.from_bytes(digest[:8], "big") % OUTER_FOLD_COUNT


def prediction(row: dict, rule: dict) -> bool:
    features = row["features"]
    guard = rule["guard"]
    if (
        guard is not None
        and rule["guard_sign"] * features[guard]
        < rule["guard_threshold"]
    ):
        return False
    return (
        rule["primary_sign"] * features[rule["primary"]]
        > rule["primary_boundary_exclusive"]
    )


def quantile_thresholds(rows: list[dict], feature: str, sign: int) -> list[float]:
    ordered = sorted(sign * row["features"][feature] for row in rows)
    return sorted(
        {
            ordered[
                round(
                    (len(ordered) - 1)
                    * step
                    / GUARD_QUANTILE_STEPS
                )
            ]
            for step in range(GUARD_QUANTILE_STEPS + 1)
        }
    )


def fit_rule(rows: list[dict]) -> tuple[dict, dict]:
    negatives = [
        row for row in rows if row["expectation"] == "negative"
    ]
    positives = [
        row
        for row in rows
        if row["expectation"] == "controlled_positive"
    ]
    if not negatives or not positives:
        raise ValueError("rule fitting requires both classes")
    best: tuple | None = None
    for primary in FEATURES:
        for primary_sign in (1, -1):
            for guard in (None, *FEATURES):
                guard_signs = (1,) if guard is None else (1, -1)
                for guard_sign in guard_signs:
                    thresholds = (
                        [None]
                        if guard is None
                        else quantile_thresholds(
                            rows,
                            guard,
                            guard_sign,
                        )
                    )
                    for guard_threshold in thresholds:
                        eligible_negatives = [
                            row
                            for row in negatives
                            if guard is None
                            or guard_sign * row["features"][guard]
                            >= guard_threshold
                        ]
                        eligible_groups = len(
                            {
                                row["source_group"]
                                for row in eligible_negatives
                            }
                        )
                        if (
                            eligible_groups
                            < MINIMUM_ELIGIBLE_NEGATIVE_GROUPS
                        ):
                            continue
                        boundary = max(
                            primary_sign
                            * row["features"][primary]
                            for row in eligible_negatives
                        )
                        rule = {
                            "primary": primary,
                            "primary_sign": primary_sign,
                            "primary_boundary_exclusive": boundary,
                            "guard": guard,
                            "guard_sign": (
                                guard_sign if guard is not None else None
                            ),
                            "guard_threshold": guard_threshold,
                            "eligible_negative_source_group_count": (
                                eligible_groups
                            ),
                        }
                        true_positives = sum(
                            prediction(row, rule) for row in positives
                        )
                        selection_key = (
                            -true_positives,
                            -eligible_groups,
                            primary,
                            -primary_sign,
                            guard or "",
                            -(guard_sign if guard is not None else 0),
                            (
                                guard_threshold
                                if guard_threshold is not None
                                else 0.0
                            ),
                        )
                        candidate = (
                            selection_key,
                            rule,
                            true_positives,
                        )
                        if best is None or candidate[0] < best[0]:
                            best = candidate
    if best is None:
        raise ValueError("no rule met negative-group support")
    _key, rule, true_positives = best
    return rule, {
        "true_positives": true_positives,
        "positive_count": len(positives),
        "false_positives": sum(
            prediction(row, rule) for row in negatives
        ),
        "negative_count": len(negatives),
    }


def confusion(rows: list[dict], predicted: list[bool]) -> dict:
    true_positives = sum(
        is_positive
        and row["expectation"] == "controlled_positive"
        for row, is_positive in zip(rows, predicted, strict=True)
    )
    false_negatives = sum(
        not is_positive
        and row["expectation"] == "controlled_positive"
        for row, is_positive in zip(rows, predicted, strict=True)
    )
    false_positives = sum(
        is_positive and row["expectation"] == "negative"
        for row, is_positive in zip(rows, predicted, strict=True)
    )
    true_negatives = sum(
        not is_positive and row["expectation"] == "negative"
        for row, is_positive in zip(rows, predicted, strict=True)
    )
    positive_count = true_positives + false_negatives
    negative_count = false_positives + true_negatives
    return {
        "true_positives": true_positives,
        "false_negatives": false_negatives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "recall": (
            true_positives / positive_count if positive_count else None
        ),
        "false_positive_rate": (
            false_positives / negative_count if negative_count else None
        ),
    }


def strict_scalar(rows: list[dict], feature: str) -> dict:
    boundary = max(
        row["features"][feature]
        for row in rows
        if row["expectation"] == "negative"
    )
    predicted = [
        row["features"][feature] > boundary for row in rows
    ]
    return {
        "feature": feature,
        "boundary_exclusive": boundary,
        **confusion(rows, predicted),
    }


def class_summary(rows: list[dict], predicted: list[bool]) -> dict:
    values: dict[str, dict] = defaultdict(
        lambda: {"case_count": 0, "predicted_positive_count": 0}
    )
    for row, is_positive in zip(rows, predicted, strict=True):
        values[row["class"]]["case_count"] += 1
        values[row["class"]]["predicted_positive_count"] += int(
            is_positive
        )
    return dict(sorted(values.items()))


def grouped_analysis(rows: list[dict]) -> dict:
    predictions: dict[str, bool] = {}
    folds = []
    for fold in range(OUTER_FOLD_COUNT):
        training = [
            row
            for row in rows
            if outer_fold(row["source_group"]) != fold
        ]
        validation = [
            row
            for row in rows
            if outer_fold(row["source_group"]) == fold
        ]
        rule, training_result = fit_rule(training)
        validation_predictions = [
            prediction(row, rule) for row in validation
        ]
        for row, is_positive in zip(
            validation,
            validation_predictions,
            strict=True,
        ):
            if row["case_id"] in predictions:
                raise RuntimeError("case received duplicate OOF prediction")
            predictions[row["case_id"]] = is_positive
        folds.append(
            {
                "fold": fold,
                "training_source_group_count": len(
                    {row["source_group"] for row in training}
                ),
                "validation_source_group_count": len(
                    {row["source_group"] for row in validation}
                ),
                "rule": rule,
                "training": training_result,
                "validation": confusion(
                    validation,
                    validation_predictions,
                ),
            }
        )
    if set(predictions) != {row["case_id"] for row in rows}:
        raise RuntimeError("OOF predictions do not cover every scored case")
    ordered_predictions = [
        predictions[row["case_id"]] for row in rows
    ]
    result = confusion(rows, ordered_predictions)
    gate_passed = (
        result["false_positives"] == 0
        and result["recall"] is not None
        and result["recall"] >= 0.90
    )
    return {
        "outer_fold_count": OUTER_FOLD_COUNT,
        "fold_assignment": "sha256_source_group_mod_5",
        "minimum_eligible_negative_source_groups": (
            MINIMUM_ELIGIBLE_NEGATIVE_GROUPS
        ),
        "guard_threshold_grid": "observed 0%, 5%, ..., 100% quantiles",
        "folds": folds,
        "combined_out_of_fold": {
            **result,
            "by_class": class_summary(
                rows,
                ordered_predictions,
            ),
        },
        "gate": {
            "maximum_false_positives": 0,
            "minimum_recall": 0.90,
            "passed": gate_passed,
        },
        "case_predictions": [
            {
                "case_id": row["case_id"],
                "source_group": row["source_group"],
                "expectation": row["expectation"],
                "predicted_positive": predictions[row["case_id"]],
            }
            for row in rows
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    input_sha256 = sha256_file(input_path)
    if input_sha256 != args.expected_input_sha256:
        raise SystemExit("input report SHA-256 differs from commitment")
    source = load_json(input_path)
    if (
        source.get("state") != "development_research_only"
        or source.get("public_verdict_enabled") is not False
        or source.get("heldout_opened") is not False
        or source.get("method_id")
        != "derrien-aac-quantization-v1-research"
    ):
        raise SystemExit("input is not sealed development research evidence")
    cases = source.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemExit("input contains no cases")
    rows = []
    unsupported = []
    for case in cases:
        if case.get("state") != "scored":
            unsupported.append(
                {
                    "case_id": case["case_id"],
                    "class": case["class"],
                    "state": case["state"],
                }
            )
            continue
        row = {
            "case_id": case["case_id"],
            "class": case["class"],
            "expectation": case["expectation"],
            "source_group": case["source_group"],
            "features": feature_values(case),
        }
        rows.append(row)
    if len({row["case_id"] for row in rows}) != len(rows):
        raise SystemExit("scored cases contain duplicate IDs")
    if len({row["source_group"] for row in rows}) < 25:
        raise SystemExit("too few source groups for grouped analysis")

    scalar_results = [
        strict_scalar(rows, feature) for feature in FEATURES
    ]
    full_rule, full_training = fit_rule(rows)
    grouped = grouped_analysis(rows)
    disposition = (
        "passed_development_grouped_gate"
        if grouped["gate"]["passed"]
        else "failed_development_grouped_gate"
    )
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": "development_research_only",
        "disposition": disposition,
        "public_verdict_enabled": False,
        "heldout_opened": False,
        "input": {
            "path": str(input_path),
            "sha256": input_sha256,
            "case_count": len(cases),
            "scored_case_count": len(rows),
            "unsupported_case_count": len(unsupported),
        },
        "feature_definitions": list(FEATURES),
        "strict_single_scalar_results": scalar_results,
        "full_development_post_selected_one_guard": {
            "warning": (
                "Optimistic post-selection on all development labels; "
                "not a release estimate."
            ),
            "rule": full_rule,
            "training": full_training,
        },
        "source_grouped_one_guard": grouped,
        "unsupported_cases": unsupported,
    }
    write_atomic(args.output, report)
    oof = grouped["combined_out_of_fold"]
    print(
        f"wrote grouped analysis to {args.output}; "
        f"OOF FP={oof['false_positives']}/{oof['negative_count']} "
        f"TP={oof['true_positives']}/{oof['positive_count']} "
        f"disposition={disposition}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
