#!/usr/bin/env python3
"""Create a path-free paired aggregate for the two v2 CRNN conditions."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import analyze_audio_integrity_v2_fixed_baselines as fixed_analysis
import audio_integrity_v2_baseline_common as common
import train_audio_integrity_v2_crnn_baseline as trainer


def validate_raw(
    raw: dict[str, Any], condition: str, cases: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    if (
        raw.get("schema_version") != 1
        or raw.get("plan_id") != common.PLAN_ID
        or raw.get("state") != "mechanism_development_crnn_private_result"
        or raw.get("condition") != condition
        or raw.get("evidence_partition") != common.MECHANISM_PARTITION
        or raw.get("independent_validation") is not False
        or raw.get("encoder_transfer_scores_opened") is not False
        or raw.get("external_transfer_scores_opened") is not False
        or raw.get("public_verdict_enabled") is not False
        or raw.get("thresholds_retuned") is not False
        or raw.get("model_definition_sha256") != trainer.MODEL_DEFINITION_SHA256
    ):
        raise ValueError(f"private CRNN report state differs: {condition}")
    rows = raw.get("case_scores", [])
    by_id = {row.get("case_id"): row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != {row["case_id"] for row in cases}:
        raise ValueError(f"private CRNN result cases differ: {condition}")
    for case in cases:
        row = by_id[case["case_id"]]
        if (
            row.get("analysis_pcm_sha256") != case["_analysis_pcm_sha256"]
            or row.get("audio_sha256") != case["audio_sha256"]
            or row.get("expectation") != case["expectation"]
            or row.get("source_domain") != case["source_domain"]
            or not isinstance(row.get("window_count"), int)
            or row["window_count"] <= 0
            or not isinstance(row.get("score"), (int, float))
            or not 0.0 <= row["score"] <= 1.0
        ):
            raise ValueError(f"private CRNN case differs: {case['case_id']}")
    return by_id


def condition_aggregate(
    condition: str,
    raw: dict[str, Any],
    cases: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    pcm_scores: dict[str, float] = {}
    for case in cases:
        score = float(by_id[case["case_id"]]["score"])
        pcm = case["_analysis_pcm_sha256"]
        previous = pcm_scores.setdefault(pcm, score)
        if previous != score:
            raise ValueError(f"CRNN score differs for identical PCM: {condition}")
    predictions = {pcm: score >= 0.5 for pcm, score in pcm_scores.items()}
    case_rows = [(case, predictions[case["_analysis_pcm_sha256"]]) for case in cases]
    unique_cases = common.representatives_by_pcm(cases)
    unique_rows = [
        (case, predictions[case["_analysis_pcm_sha256"]]) for case in unique_cases
    ]
    unique_values = [pcm_scores[row["_analysis_pcm_sha256"]] for row in unique_cases]
    unique_labels = [trainer.LABELS[row["expectation"]] for row in unique_cases]
    case_values = [pcm_scores[row["_analysis_pcm_sha256"]] for row in cases]
    case_labels = [trainer.LABELS[row["expectation"]] for row in cases]

    negative_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    positive_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        target = (
            positive_groups
            if case["expectation"] == "controlled_positive"
            else negative_groups
        )
        target[case["source_group"]].append(case)
    negative_alerts = sum(
        any(predictions[row["_analysis_pcm_sha256"]] for row in rows)
        for rows in negative_groups.values()
    )
    positive_detections = sum(
        any(predictions[row["_analysis_pcm_sha256"]] for row in rows)
        for rows in positive_groups.values()
    )
    public_folds = {}
    for fold in raw.get("folds", []):
        domain = fold.get("outer_domain")
        best_epoch = fold.get("best_epoch")
        epochs = fold.get("epochs", [])
        selected = next(
            (row for row in epochs if row.get("epoch") == best_epoch), None
        )
        if (
            domain not in common.EXPECTED_DOMAINS
            or selected is None
            or not isinstance(fold.get("checkpoint_sha256"), str)
        ):
            raise ValueError(f"CRNN fold record differs: {condition}")
        public_folds[domain] = {
            "training_unique_pcm_count": fold["training_unique_pcm_count"],
            "validation_unique_pcm_count": fold["validation_unique_pcm_count"],
            "outer_unique_pcm_count": fold["outer_unique_pcm_count"],
            "outer_artifact_count": fold["outer_artifact_count"],
            "training_label_counts": fold["training_label_counts"],
            "validation_label_counts": fold["validation_label_counts"],
            "parameter_count": fold["parameter_count"],
            "best_epoch": best_epoch,
            "epochs_completed": len(epochs),
            "best_inner_validation": selected["validation"],
            "checkpoint_sha256": fold["checkpoint_sha256"],
        }
    if set(public_folds) != common.EXPECTED_DOMAINS:
        raise ValueError(f"CRNN outer-fold set differs: {condition}")

    return {
        "condition": condition,
        "fixed_boundary": 0.5,
        "thresholds_retuned": False,
        "factorial_case_level": {
            **fixed_analysis.confusion(case_rows),
            "auc": trainer.auc(case_values, case_labels),
            "log_loss": trainer.log_loss(case_values, case_labels),
        },
        "unique_analysis_pcm_level": {
            **fixed_analysis.confusion(unique_rows),
            "auc": trainer.auc(unique_values, unique_labels),
            "log_loss": trainer.log_loss(unique_values, unique_labels),
        },
        "source_group_level": {
            "negative_source_group_count": len(negative_groups),
            "negative_source_group_alert_count": negative_alerts,
            "negative_source_group_alert_rate": negative_alerts
            / len(negative_groups),
            "controlled_positive_source_group_count": len(positive_groups),
            "controlled_positive_source_group_detection_count": positive_detections,
            "controlled_positive_source_group_detection_rate": positive_detections
            / len(positive_groups),
        },
        "by_source_domain": fixed_analysis.grouped_confusion(
            cases, predictions, lambda row: row["source_domain"]
        ),
        "negative_by_history_class": fixed_analysis.grouped_confusion(
            [row for row in cases if row["expectation"] == "negative"],
            predictions,
            fixed_analysis.negative_class,
        ),
        "positive_by_codec_family": fixed_analysis.grouped_confusion(
            [row for row in cases if row["expectation"] == "controlled_positive"],
            predictions,
            lambda row: row["codec_family"],
        ),
        "paired_positive_minus_matched_reference": common.paired_effects(
            cases, pcm_scores
        ),
        "outer_fold_training": public_folds,
        "disposition": "paper_aligned_replication_baseline_only_not_a_candidate",
        "_pcm_scores": pcm_scores,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--constructor-manifest", required=True, type=Path)
    parser.add_argument("--naive-report", required=True, type=Path)
    parser.add_argument("--masked-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    plan_path = args.plan.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    constructor_path = args.constructor_manifest.expanduser().resolve()
    naive_path = args.naive_report.expanduser().resolve()
    masked_path = args.masked_report.expanduser().resolve()
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
            (analyzer_path, "crnn_analyzer_sha256", "CRNN analyzer"),
            (
                Path(common.__file__).resolve(),
                "common_module_sha256",
                "baseline common module",
            ),
            (
                Path(trainer.__file__).resolve(),
                "crnn_runner_sha256",
                "CRNN runner",
            ),
            (
                Path(fixed_analysis.__file__).resolve(),
                "fixed_baseline_analyzer_sha256",
                "fixed baseline analyzer",
            ),
        ):
            if not path.is_file() or common.sha256_file(path) != bindings.get(key):
                raise ValueError(f"{label} binding differs")
        cases = common.load_development_cases(
            common.load_object(manifest_path), common.load_object(constructor_path)
        )
        raw_reports = {
            "naive": common.load_object(naive_path),
            "random_high_frequency_mask": common.load_object(masked_path),
        }
        paths = {
            "naive": naive_path,
            "random_high_frequency_mask": masked_path,
        }
        aggregates = {}
        for condition in ("naive", "random_high_frequency_mask"):
            by_id = validate_raw(raw_reports[condition], condition, cases)
            aggregates[condition] = condition_aggregate(
                condition, raw_reports[condition], cases, by_id
            )
        naive_scores = aggregates["naive"].pop("_pcm_scores")
        masked_scores = aggregates["random_high_frequency_mask"].pop("_pcm_scores")
        score_differences = [
            masked_scores[pcm] - naive_scores[pcm] for pcm in sorted(naive_scores)
        ]
        if set(naive_scores) != set(masked_scores):
            raise ValueError("CRNN condition PCM populations differ")
        output = {
            "schema_version": 1,
            "plan_id": common.PLAN_ID,
            "state": "mechanism_development_crnn_path_free_evidence",
            "evidence_partition": common.MECHANISM_PARTITION,
            "independent_validation": False,
            "feature_version": 0,
            "encoder_transfer_scores_opened": False,
            "external_transfer_scores_opened": False,
            "public_verdict_enabled": False,
            "inputs": {
                "plan_sha256": common.sha256_file(plan_path),
                "private_analysis_manifest_sha256": common.sha256_file(manifest_path),
                "naive_private_report_sha256": common.sha256_file(paths["naive"]),
                "masked_private_report_sha256": common.sha256_file(
                    paths["random_high_frequency_mask"]
                ),
                "analyzer_sha256": common.sha256_file(analyzer_path),
            },
            "inventory": {
                "factorial_case_count": len(cases),
                "unique_analysis_pcm_count": len(common.representatives_by_pcm(cases)),
                "source_group_count": len({row["source_group"] for row in cases}),
                "source_domain_count": len(common.EXPECTED_DOMAINS),
                "outer_fold_count_per_condition": len(common.EXPECTED_DOMAINS),
            },
            "reproduction_boundary": {
                "exact_reproduction": False,
                "reason": (
                    "The paper specifies the high-level architecture and mask but "
                    "does not publish reference code, weights, convolution channels, "
                    "spectrogram hop defaults, optimizer, or training schedule."
                ),
                "evaluation_stricter_than_paper": (
                    "complete source-domain outer folds with grouped inner validation"
                ),
            },
            "conditions": aggregates,
            "masked_minus_naive_unique_pcm_score": common.numeric_summary(
                score_differences
            ),
            "interpretation": {
                "conditional_development_evidence_only": True,
                "softmax_is_not_calibrated_history_probability": True,
                "condition_comparison_is_not_independent_validation": True,
                "baseline_can_be_promoted": False,
            },
        }
        common.assert_public_path_free(output)
        common.write_new(args.output.expanduser().resolve(), output)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print("wrote path-free naive-versus-masked CRNN development aggregate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
