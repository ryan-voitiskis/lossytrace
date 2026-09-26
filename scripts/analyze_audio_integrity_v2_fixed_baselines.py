#!/usr/bin/env python3
"""Create path-free v2 fixed-baseline aggregates from private raw results."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import audio_integrity_v2_baseline_common as common
import run_audio_integrity_v2_fixed_baselines as runner


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


def wilson_interval(successes: int, total: int) -> list[float] | None:
    if total <= 0 or not 0 <= successes <= total:
        return None
    z = 1.959963984540054
    proportion = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    centre = proportion + z2 / (2.0 * total)
    spread = z * math.sqrt(
        proportion * (1.0 - proportion) / total + z2 / (4.0 * total * total)
    )
    return [(centre - spread) / denominator, (centre + spread) / denominator]


def negative_class(case: dict[str, Any]) -> str:
    transforms = case.get("post_transform_ids", [])
    return transforms[0] if transforms else "pcm_reference"


def confusion(rows: list[tuple[dict[str, Any], bool]]) -> dict[str, Any]:
    positives = sum(case["expectation"] == "controlled_positive" for case, _ in rows)
    negatives = len(rows) - positives
    tp = sum(
        prediction and case["expectation"] == "controlled_positive"
        for case, prediction in rows
    )
    fp = sum(
        prediction and case["expectation"] == "negative"
        for case, prediction in rows
    )
    tn = negatives - fp
    fn = positives - tp
    recall = tp / positives if positives else None
    specificity = tn / negatives if negatives else None
    precision = tp / (tp + fp) if tp + fp else None
    return {
        "case_count": len(rows),
        "controlled_positive_count": positives,
        "negative_count": negatives,
        "true_positive_count": tp,
        "false_negative_count": fn,
        "true_negative_count": tn,
        "false_positive_count": fp,
        "recall": recall,
        "recall_two_sided_95_percent_wilson": wilson_interval(tp, positives),
        "specificity": specificity,
        "specificity_two_sided_95_percent_wilson": wilson_interval(tn, negatives),
        "false_positive_rate": fp / negatives if negatives else None,
        "selected_population_precision": precision,
        "selected_population_accuracy": (tp + tn) / len(rows) if rows else None,
        "balanced_accuracy": (recall + specificity) / 2.0
        if recall is not None and specificity is not None
        else None,
    }


def grouped_confusion(
    cases: list[dict[str, Any]],
    predictions: dict[str, bool],
    field: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    grouped: dict[str, list[tuple[dict[str, Any], bool]]] = defaultdict(list)
    for case in cases:
        grouped[field(case)].append(
            (case, predictions[case["_analysis_pcm_sha256"]])
        )
    return {name: confusion(rows) for name, rows in sorted(grouped.items())}


def cannam_aggregate(
    cases: list[dict[str, Any]], raw_by_id: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    pcm_results: dict[str, dict[str, Any]] = {}
    for case in cases:
        raw = raw_by_id[case["case_id"]]
        result = runner.validate_result(runner.CANNAM_BASELINE, raw["result"])
        pcm_sha256 = case["_analysis_pcm_sha256"]
        previous = pcm_results.setdefault(pcm_sha256, result)
        if previous != result:
            raise ValueError("Cannam result differs for identical analysis PCM")
    predictions = {
        pcm: result["fixed_binary_label"] for pcm, result in pcm_results.items()
    }
    scores = {
        pcm: result["positive_window_fraction"] for pcm, result in pcm_results.items()
    }
    case_rows = [(case, predictions[case["_analysis_pcm_sha256"]]) for case in cases]
    unique_cases = common.representatives_by_pcm(cases)
    unique_rows = [
        (case, predictions[case["_analysis_pcm_sha256"]]) for case in unique_cases
    ]

    negative_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    positive_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        if case["expectation"] == "negative":
            negative_groups[case["source_group"]].append(case)
        else:
            positive_groups[case["source_group"]].append(case)
    negative_alerts = sum(
        any(predictions[row["_analysis_pcm_sha256"]] for row in rows)
        for rows in negative_groups.values()
    )
    positive_detections = sum(
        any(predictions[row["_analysis_pcm_sha256"]] for row in rows)
        for rows in positive_groups.values()
    )
    group_metrics = {
        "negative_source_group_count": len(negative_groups),
        "negative_source_group_alert_count": negative_alerts,
        "negative_source_group_alert_rate": negative_alerts / len(negative_groups),
        "negative_source_group_alert_two_sided_95_percent_wilson": wilson_interval(
            negative_alerts, len(negative_groups)
        ),
        "controlled_positive_source_group_count": len(positive_groups),
        "controlled_positive_source_group_detection_count": positive_detections,
        "controlled_positive_source_group_detection_rate": positive_detections
        / len(positive_groups),
    }
    return {
        "method": {
            "plugin_key": runner.PLUGIN_KEY,
            "window_threshold": runner.WINDOW_THRESHOLD,
            "file_positive_fraction_threshold": runner.FILE_THRESHOLD,
            "thresholds_retuned": False,
            "score_interpretation": "positive-window fraction, not probability",
        },
        "factorial_case_level": confusion(case_rows),
        "unique_analysis_pcm_level": confusion(unique_rows),
        "source_group_level": group_metrics,
        "by_source_domain": grouped_confusion(
            cases, predictions, lambda row: row["source_domain"]
        ),
        "negative_by_history_class": grouped_confusion(
            [row for row in cases if row["expectation"] == "negative"],
            predictions,
            negative_class,
        ),
        "positive_by_codec_family": grouped_confusion(
            [row for row in cases if row["expectation"] == "controlled_positive"],
            predictions,
            lambda row: row["codec_family"],
        ),
        "positive_by_encoder_lineage": grouped_confusion(
            [row for row in cases if row["expectation"] == "controlled_positive"],
            predictions,
            lambda row: row["encoder_lineage_id"],
        ),
        "paired_positive_minus_matched_reference": common.paired_effects(
            cases, scores
        ),
        "disposition": "fixed_reference_baseline_only_not_a_candidate",
    }


def feature_summary(
    cases: list[dict[str, Any]],
    pcm_features: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    unique_cases: dict[str, dict[str, Any]] = {}
    for case in cases:
        unique_cases.setdefault(case["_analysis_pcm_sha256"], case)
    result: dict[str, Any] = {}
    for field in FEATURE_FIELDS:
        values = [
            float(pcm_features[row["_analysis_pcm_sha256"]][field])
            for row in unique_cases.values()
            if pcm_features[row["_analysis_pcm_sha256"]].get(field) is not None
        ]
        result[field] = common.numeric_summary(values)
    return result


def grouped_feature_summary(
    cases: list[dict[str, Any]],
    pcm_features: dict[str, dict[str, Any]],
    field: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        grouped[field(case)].append(case)
    return {
        name: feature_summary(rows, pcm_features)
        for name, rows in sorted(grouped.items())
    }


def feature_v0_aggregate(
    cases: list[dict[str, Any]], raw_by_id: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    pcm_features: dict[str, dict[str, Any]] = {}
    for case in cases:
        raw = raw_by_id[case["case_id"]]
        result = runner.validate_result(runner.FEATURE_BASELINE, raw["result"])
        features = result["features"]
        pcm_sha256 = case["_analysis_pcm_sha256"]
        previous = pcm_features.setdefault(pcm_sha256, features)
        if previous != features:
            raise ValueError("feature-v0 result differs for identical analysis PCM")
    paired = {}
    for field in FEATURE_FIELDS:
        scores = {
            pcm: float(features[field])
            for pcm, features in pcm_features.items()
            if features.get(field) is not None
        }
        paired[field] = common.paired_effects(cases, scores)
    return {
        "method": {
            "feature_version": 0,
            "classifier_enabled": False,
            "threshold_available": False,
            "calibration_available": False,
        },
        "unique_analysis_pcm_overall": feature_summary(cases, pcm_features),
        "by_expectation": grouped_feature_summary(
            cases, pcm_features, lambda row: row["expectation"]
        ),
        "by_source_domain": grouped_feature_summary(
            cases, pcm_features, lambda row: row["source_domain"]
        ),
        "negative_by_history_class": grouped_feature_summary(
            [row for row in cases if row["expectation"] == "negative"],
            pcm_features,
            negative_class,
        ),
        "positive_by_codec_family": grouped_feature_summary(
            [row for row in cases if row["expectation"] == "controlled_positive"],
            pcm_features,
            lambda row: row["codec_family"],
        ),
        "paired_positive_minus_matched_reference": paired,
        "disposition": "descriptive_measurements_only_no_classifier_or_candidate",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--constructor-manifest", required=True, type=Path)
    parser.add_argument("--raw-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    plan_path = args.plan.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    constructor_path = args.constructor_manifest.expanduser().resolve()
    raw_path = args.raw_report.expanduser().resolve()
    analyzer_path = Path(__file__).resolve()
    try:
        plan = common.load_object(plan_path)
        if (
            plan.get("plan_id") != common.PLAN_ID
            or plan.get("state")
            != "mechanism_development_baselines_frozen_before_waveform_decode"
            or plan.get("authorized_evidence_partition")
            != common.MECHANISM_PARTITION
            or plan.get("encoder_transfer_scores_opened") is not False
            or plan.get("external_transfer_scores_opened") is not False
            or plan.get("public_verdict_enabled") is not False
        ):
            raise ValueError("development-baseline plan state differs")
        bindings = plan.get("bindings", {})
        for path, key, label in (
            (manifest_path, "private_analysis_manifest_sha256", "analysis manifest"),
            (
                constructor_path,
                "private_constructor_manifest_sha256",
                "constructor manifest",
            ),
            (analyzer_path, "fixed_baseline_analyzer_sha256", "baseline analyzer"),
            (
                Path(common.__file__).resolve(),
                "common_module_sha256",
                "baseline common module",
            ),
            (
                Path(runner.__file__).resolve(),
                "fixed_baseline_runner_sha256",
                "fixed baseline runner",
            ),
        ):
            if not path.is_file() or common.sha256_file(path) != bindings.get(key):
                raise ValueError(f"{label} binding differs")
        raw = common.load_object(raw_path)
        if (
            raw.get("schema_version") != 1
            or raw.get("plan_id") != common.PLAN_ID
            or raw.get("state")
            != "mechanism_development_fixed_baseline_private_result"
            or raw.get("evidence_partition") != common.MECHANISM_PARTITION
            or raw.get("encoder_transfer_scores_opened") is not False
            or raw.get("external_transfer_scores_opened") is not False
            or raw.get("public_verdict_enabled") is not False
            or raw.get("thresholds_retuned") is not False
        ):
            raise ValueError("private fixed-baseline report state differs")
        cases = common.load_development_cases(
            common.load_object(manifest_path), common.load_object(constructor_path)
        )
        raw_rows = raw.get("case_results", [])
        raw_by_id = {row.get("case_id"): row for row in raw_rows}
        if set(raw_by_id) != {row["case_id"] for row in cases} or len(raw_by_id) != len(
            raw_rows
        ):
            raise ValueError("private baseline result cases differ")
        baseline = raw.get("baseline")
        if baseline == runner.CANNAM_BASELINE:
            aggregate = cannam_aggregate(cases, raw_by_id)
        elif baseline == runner.FEATURE_BASELINE:
            aggregate = feature_v0_aggregate(cases, raw_by_id)
        else:
            raise ValueError("private baseline identity differs")
        output = {
            "schema_version": 1,
            "plan_id": common.PLAN_ID,
            "state": "mechanism_development_fixed_baseline_path_free_evidence",
            "baseline": baseline,
            "evidence_partition": common.MECHANISM_PARTITION,
            "independent_validation": False,
            "feature_version": 0,
            "encoder_transfer_scores_opened": False,
            "external_transfer_scores_opened": False,
            "public_verdict_enabled": False,
            "inputs": {
                "plan_sha256": common.sha256_file(plan_path),
                "private_analysis_manifest_sha256": common.sha256_file(manifest_path),
                "private_raw_report_sha256": common.sha256_file(raw_path),
                "analyzer_sha256": common.sha256_file(analyzer_path),
            },
            "inventory": {
                "factorial_case_count": len(cases),
                "unique_analysis_pcm_count": len(common.representatives_by_pcm(cases)),
                "source_group_count": len({row["source_group"] for row in cases}),
                "source_domain_count": len({row["source_domain"] for row in cases}),
            },
            "wrapper_invariance": raw["wrapper_invariance"],
            "analysis": aggregate,
            "interpretation": {
                "conditional_development_evidence_only": True,
                "accuracy_is_not_universal_history_identifiability": True,
                "baseline_can_be_promoted": False,
            },
        }
        common.assert_public_path_free(output)
        common.write_new(args.output.expanduser().resolve(), output)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(f"wrote path-free {baseline} mechanism-development aggregate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
