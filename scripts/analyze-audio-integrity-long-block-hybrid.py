#!/usr/bin/env python3
"""Evaluate research-only long-block/CNN hybrid rules.

This analyzer is deliberately development-only. It fits zero-observed-false-
positive scalar conjunctions on labelled development data, then requires each
rule template to remain safe and useful in every source-grouped fold. It never
opens held-out labels or emits a product policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import tempfile
from pathlib import Path
from typing import Any, Callable


EXPECTED_PROFILE = "long-block-v16"
EXPECTED_EXPECTATIONS = {"negative", "controlled_positive"}
SCORE_NAMES = ("long", "cnn")
EXCLUDED_FEATURE_PARTS = (
    "baseline_median_ms",
    "baseline_times_ms",
    "prototype_median_ms",
    "prototype_times_ms",
    "runtime_overhead_percent",
    "duration_seconds",
    "frame_count",
    "sample_count",
    "best_phase_samples",
    "audio_block_count",
    "frames_per_phase",
    "sample_rate_hz",
    "channel_count",
    "bits_per_sample",
    "feature_version",
    "schema_version",
    "derived.long_max",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    return value


def write_atomic(path: Path, value: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    if path.exists():
        raise SystemExit(f"refusing to replace existing report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        json.dump(value, temporary, indent=2, sort_keys=True)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def flatten_numeric(
    prefix: str, value: Any, output: dict[str, float]
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            flatten_numeric(child_prefix, child, output)
    elif (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    ):
        output[prefix] = float(value)


def cnn_scores(
    nsynth_oof_path: Path, unseen_path: Path
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    sources = [
        (
            nsynth_oof_path,
            "cnn_ensemble_score",
            "source_grouped_out_of_fold",
        ),
        (unseen_path, "lossy_probability_mean", "unseen_source_scoring"),
    ]
    scores: dict[str, float] = {}
    evidence = []
    for path, score_field, method in sources:
        report = load_json(path)
        results = report.get("results")
        if not isinstance(results, list):
            raise SystemExit(f"{path}: results must be an array")
        for result in results:
            case_id = result.get("case_id")
            score = result.get(score_field)
            if (
                not isinstance(case_id, str)
                or not isinstance(score, (int, float))
                or isinstance(score, bool)
                or not math.isfinite(score)
            ):
                raise SystemExit(
                    f"{path}: invalid {score_field} observation"
                )
            if case_id in scores:
                raise SystemExit(
                    f"CNN score inputs overlap at case ID {case_id}"
                )
            scores[case_id] = float(score)
        evidence.append(
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "score_field": score_field,
                "method": method,
                "case_count": len(results),
            }
        )
    return scores, evidence


def long_score(probe: dict[str, Any], case_id: str) -> float:
    values = []
    for grid_name in (
        "mp3_long_sine",
        "long_vorbis",
        "opus_long_celt",
    ):
        grid = probe.get(grid_name)
        value = (
            grid.get("long_block_phase_consistent_peak_score")
            if isinstance(grid, dict)
            else None
        )
        if isinstance(value, (int, float)) and math.isfinite(value):
            values.append(float(value))
    if len(values) != 3:
        raise SystemExit(
            f"{case_id}: expected all three long-block-v16 grid scores"
        )
    return max(values)


def candidate_rows(
    paths: list[Path], scores: dict[str, float]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    evidence = []
    seen_case_ids: set[str] = set()
    runner_hashes: set[str] = set()
    for path in paths:
        report = load_json(path)
        if report.get("schema_version") != 1:
            raise SystemExit(f"{path}: unsupported candidate schema")
        results = report.get("results")
        if not isinstance(results, list):
            raise SystemExit(f"{path}: results must be an array")
        report_runner_hash = report.get("runner_sha256")
        if not isinstance(report_runner_hash, str):
            raise SystemExit(f"{path}: missing runner SHA-256")
        runner_hashes.add(report_runner_hash)
        for result in results:
            case_id = result.get("case_id")
            expectation = result.get("expectation")
            source_group = result.get("source_group")
            class_name = result.get("class")
            runner = result.get("runner")
            if (
                not isinstance(case_id, str)
                or not isinstance(source_group, str)
                or not isinstance(class_name, str)
                or expectation not in EXPECTED_EXPECTATIONS
                or not isinstance(runner, dict)
            ):
                raise SystemExit(f"{path}: invalid candidate observation")
            if case_id in seen_case_ids:
                raise SystemExit(f"duplicate candidate case ID: {case_id}")
            seen_case_ids.add(case_id)
            if (
                runner.get("research_transform_grid_profile")
                != EXPECTED_PROFILE
            ):
                raise SystemExit(
                    f"{case_id}: expected {EXPECTED_PROFILE} measurements"
                )
            if case_id not in scores:
                raise SystemExit(f"{case_id}: no leakage-safe CNN score")
            features: dict[str, float] = {}
            flatten_numeric("runner", runner, features)
            trace = runner.get("compression_trace")
            if (
                not isinstance(trace, dict)
                or not isinstance(trace.get("active_frame_count"), int)
                or trace["active_frame_count"] <= 0
            ):
                raise SystemExit(f"{case_id}: invalid compression trace")
            features["derived.high_band_ratio"] = (
                trace["high_band_supported_frame_count"]
                / trace["active_frame_count"]
            )
            transform_probe = runner.get("transform_grid_probe")
            if not isinstance(transform_probe, dict):
                raise SystemExit(f"{case_id}: missing transform-grid probe")
            measured_long_score = long_score(transform_probe, case_id)
            features["derived.long_max"] = measured_long_score
            rows.append(
                {
                    "case_id": case_id,
                    "class": class_name,
                    "expectation": expectation,
                    "source_group": source_group,
                    "positive": expectation == "controlled_positive",
                    "features": features,
                    "long": measured_long_score,
                    "cnn": scores[case_id],
                }
            )
        evidence.append(
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "case_count": len(results),
                "runner_sha256": report_runner_hash,
            }
        )
    if len(runner_hashes) != 1:
        raise SystemExit("candidate reports use different runner binaries")
    return rows, evidence


def allowed_features(rows: list[dict[str, Any]]) -> list[str]:
    shared = set.intersection(
        *(set(row["features"]) for row in rows)
    )
    output = []
    for feature in sorted(shared):
        if any(part in feature for part in EXCLUDED_FEATURE_PARTS):
            continue
        values = {row["features"][feature] for row in rows}
        if len(values) > 1:
            output.append(feature)
    return output


def guard_matches(
    row: dict[str, Any],
    feature: str | None,
    direction: str | None,
    threshold: float | None,
) -> bool:
    if feature is None:
        return True
    assert direction in {"greater_than", "less_than"}
    assert threshold is not None
    value = row["features"][feature]
    if direction == "greater_than":
        return value > threshold
    return value < threshold


def selected_ids(
    rule: dict[str, Any], rows: list[dict[str, Any]]
) -> set[str]:
    boundary = rule["score_boundary"]
    if boundary is None:
        boundary = -math.inf
    return {
        row["case_id"]
        for row in rows
        if guard_matches(
            row,
            rule["guard_feature"],
            rule["guard_direction"],
            rule["guard_threshold"],
        )
        and row[rule["score"]] > boundary
    }


def rules_for_template(
    template: tuple[str, str | None, str | None],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    score_name, feature, direction = template
    negatives = [row for row in rows if not row["positive"]]
    positives = [row for row in rows if row["positive"]]
    thresholds: list[float | None]
    if feature is None:
        thresholds = [None]
    else:
        thresholds = sorted(
            {row["features"][feature] for row in negatives}
        )
    output = []
    for threshold in thresholds:
        guarded_negatives = [
            row
            for row in negatives
            if guard_matches(row, feature, direction, threshold)
        ]
        boundary = max(
            (row[score_name] for row in guarded_negatives),
            default=-math.inf,
        )
        rule = {
            "score": score_name,
            "guard_feature": feature,
            "guard_direction": direction,
            "guard_threshold": threshold,
            "score_boundary": (
                boundary if math.isfinite(boundary) else None
            ),
        }
        output.append(rule)
    return output


def fit_template(
    template: tuple[str, str | None, str | None],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    positives = [row for row in rows if row["positive"]]
    best: tuple[int, float, float, dict[str, Any]] | None = None
    for rule in rules_for_template(template, rows):
        selected = selected_ids(rule, positives)
        threshold = rule["guard_threshold"]
        # Prefer more positives, then a rule with guarded negatives, then the
        # lexically smaller threshold for deterministic evidence.
        rank = (
            len(selected),
            float(rule["score_boundary"] is not None),
            -(threshold if threshold is not None else 0.0),
        )
        if best is None or rank > best[:3]:
            best = (*rank, rule)
    assert best is not None
    return best[3]


def greedy_rule_variants(
    candidates: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    maximum_rules: int,
) -> tuple[list[dict[str, Any]], set[str]]:
    positives = [row for row in rows if row["positive"]]
    unique: dict[frozenset[str], dict[str, Any]] = {}
    for rule in candidates:
        selected = frozenset(selected_ids(rule, positives))
        if selected:
            unique.setdefault(selected, rule)
    remaining = set(unique)
    covered: set[str] = set()
    output = []
    while remaining and len(output) < maximum_rules:
        best = max(
            remaining,
            key=lambda selected: (
                len(selected - covered),
                len(selected),
                str(unique[selected]),
            ),
        )
        newly_selected = set(best) - covered
        if not newly_selected:
            break
        rule = dict(unique[best])
        rule["newly_detected_positive_count"] = len(newly_selected)
        rule["total_detected_positive_count"] = len(best)
        output.append(rule)
        covered.update(best)
        remaining.remove(best)
    return output, covered


def templates(features: list[str]) -> list[tuple[str, str | None, str | None]]:
    output = [(score, None, None) for score in SCORE_NAMES]
    for score in SCORE_NAMES:
        for feature in features:
            output.extend(
                [
                    (score, feature, "greater_than"),
                    (score, feature, "less_than"),
                ]
            )
    return output


def summary(
    rows: list[dict[str, Any]], selected: set[str]
) -> dict[str, Any]:
    negatives = [row for row in rows if not row["positive"]]
    positives = [row for row in rows if row["positive"]]
    false_positives = [
        row["case_id"]
        for row in negatives
        if row["case_id"] in selected
    ]
    detected = [
        row for row in positives if row["case_id"] in selected
    ]
    by_class = {}
    for class_name in sorted({row["class"] for row in positives}):
        class_rows = [
            row for row in positives if row["class"] == class_name
        ]
        class_detected = sum(
            row["case_id"] in selected for row in class_rows
        )
        by_class[class_name] = {
            "cases": len(class_rows),
            "detected": class_detected,
            "recall": class_detected / len(class_rows),
        }
    return {
        "negative_count": len(negatives),
        "false_positive_count": len(false_positives),
        "false_positive_case_ids": sorted(false_positives),
        "controlled_positive_count": len(positives),
        "detected_positive_count": len(detected),
        "recall": len(detected) / len(positives),
        "by_class": by_class,
    }


def greedy_rules(
    fitted: dict[tuple[str, str | None, str | None], dict[str, Any]],
    selected_by_template: dict[
        tuple[str, str | None, str | None], set[str]
    ],
    maximum_rules: int,
) -> tuple[list[dict[str, Any]], set[str]]:
    remaining = set(fitted)
    covered: set[str] = set()
    output = []
    while remaining and len(output) < maximum_rules:
        best = max(
            remaining,
            key=lambda template: (
                len(selected_by_template[template] - covered),
                len(selected_by_template[template]),
                str(template),
            ),
        )
        newly_selected = selected_by_template[best] - covered
        if not newly_selected:
            break
        rule = dict(fitted[best])
        rule["newly_detected_positive_count"] = len(newly_selected)
        rule["total_detected_positive_count"] = len(
            selected_by_template[best]
        )
        output.append(rule)
        covered.update(selected_by_template[best])
        remaining.remove(best)
    return output, covered


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    candidate_paths = [
        path.expanduser().resolve() for path in args.candidate
    ]
    nsynth_oof_path = args.nsynth_oof_cnn.expanduser().resolve()
    unseen_path = args.unseen_cnn.expanduser().resolve()
    scores, cnn_evidence = cnn_scores(nsynth_oof_path, unseen_path)
    rows, candidate_evidence = candidate_rows(candidate_paths, scores)
    groups = sorted({row["source_group"] for row in rows})
    if len(groups) < args.folds:
        raise SystemExit("fewer source groups than grouped folds")
    features = allowed_features(rows)
    rule_templates = templates(features)

    full_fitted = {
        template: fit_template(template, rows)
        for template in rule_templates
    }
    full_rules, full_selected = greedy_rule_variants(
        [
            rule
            for template in rule_templates
            for rule in rules_for_template(template, rows)
        ],
        rows,
        args.maximum_rules,
    )

    shuffled_groups = groups.copy()
    random.Random(args.fold_seed).shuffle(shuffled_groups)
    group_fold = {
        group: index % args.folds + 1
        for index, group in enumerate(shuffled_groups)
    }
    stable_templates = set(rule_templates)
    oof_selected_by_template = {
        template: set() for template in rule_templates
    }
    fold_details_by_template = {
        template: [] for template in rule_templates
    }
    fold_summaries = []
    for fold in range(1, args.folds + 1):
        training = [
            row
            for row in rows
            if group_fold[row["source_group"]] != fold
        ]
        validation = [
            row
            for row in rows
            if group_fold[row["source_group"]] == fold
        ]
        safe_templates = set()
        for template in rule_templates:
            fitted_rule = fit_template(template, training)
            selected = selected_ids(fitted_rule, validation)
            validation_summary = summary(validation, selected)
            safe = (
                validation_summary["false_positive_count"] == 0
                and validation_summary["detected_positive_count"]
                >= args.minimum_fold_detected_positives
            )
            if safe:
                safe_templates.add(template)
                oof_selected_by_template[template].update(
                    row["case_id"]
                    for row in validation
                    if row["positive"] and row["case_id"] in selected
                )
            fold_details_by_template[template].append(
                {
                    "fold": fold,
                    "safe_and_useful": safe,
                    "fitted_rule": fitted_rule,
                    "validation": validation_summary,
                }
            )
        stable_templates.intersection_update(safe_templates)
        fold_summaries.append(
            {
                "fold": fold,
                "training_case_count": len(training),
                "validation_case_count": len(validation),
                "validation_source_group_count": len(
                    {
                        row["source_group"]
                        for row in validation
                    }
                ),
                "safe_and_useful_template_count": len(safe_templates),
            }
        )

    stable_fitted = {
        template: full_fitted[template]
        for template in stable_templates
    }
    stable_selected = {
        template: oof_selected_by_template[template]
        for template in stable_templates
    }
    stable_rules, stable_oof_selected = greedy_rules(
        stable_fitted,
        stable_selected,
        args.maximum_rules,
    )
    for rule in stable_rules:
        template = (
            rule["score"],
            rule["guard_feature"],
            rule["guard_direction"],
        )
        rule["folds"] = fold_details_by_template[template]

    grouped_summary = summary(rows, stable_oof_selected)
    passed = (
        grouped_summary["false_positive_count"] == 0
        and grouped_summary["recall"] >= args.minimum_recall
        and bool(stable_rules)
    )
    return {
        "schema_version": 1,
        "method": {
            "candidate_profile": EXPECTED_PROFILE,
            "score_families": list(SCORE_NAMES),
            "rule_shape": (
                "one scalar guard AND one strict score boundary; "
                "greedy OR across rules"
            ),
            "score_boundary_fit": (
                "strictly greater than the maximum guarded training-negative "
                "score"
            ),
            "outer_split": "source_group",
            "folds": args.folds,
            "fold_seed": args.fold_seed,
            "stable_template_requirement": (
                "safe and useful in every outer validation fold"
            ),
            "maximum_rules": args.maximum_rules,
        },
        "evidence": {
            "candidates": candidate_evidence,
            "cnn_scores": cnn_evidence,
            "analysis_script_sha256": sha256_file(
                Path(__file__).resolve()
            ),
        },
        "case_count": len(rows),
        "source_group_count": len(groups),
        "feature_template_count": len(rule_templates),
        "full_development_fit": {
            "rules": full_rules,
            "summary": summary(rows, full_selected),
            "warning": (
                "Thresholds and templates were selected on the same labelled "
                "development rows; this is an optimistic diagnostic only."
            ),
        },
        "source_grouped_evaluation": {
            "folds": fold_summaries,
            "stable_template_count": len(stable_templates),
            "rules": stable_rules,
            "summary": grouped_summary,
        },
        "disposition": {
            "state": (
                "passed_development_grouped_gate"
                if passed
                else "failed_development_grouped_gate"
            ),
            "minimum_recall": args.minimum_recall,
            "heldout_release_evaluation_opened": False,
            "public_verdict_enabled": False,
            "reason": (
                "Grouped development criteria passed; freezing and untouched "
                "held-out evaluation are still required."
                if passed
                else "No stable grouped hybrid policy met the development gate."
            ),
        },
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument(
        "--candidate",
        type=Path,
        action="append",
        required=True,
        help="long-block-v16 benchmark report; repeat for multiple corpora",
    )
    root.add_argument("--nsynth-oof-cnn", type=Path, required=True)
    root.add_argument("--unseen-cnn", type=Path, required=True)
    root.add_argument("--output", type=Path, required=True)
    root.add_argument("--folds", type=int, default=5)
    root.add_argument("--fold-seed", type=int, default=20260760)
    root.add_argument("--maximum-rules", type=int, default=3)
    root.add_argument(
        "--minimum-fold-detected-positives", type=int, default=1
    )
    root.add_argument("--minimum-recall", type=float, default=0.90)
    return root


def main() -> int:
    args = parser().parse_args()
    if not 2 <= args.folds <= 10:
        raise SystemExit("--folds must be in 2..=10")
    if not 1 <= args.maximum_rules <= 8:
        raise SystemExit("--maximum-rules must be in 1..=8")
    if args.minimum_fold_detected_positives < 1:
        raise SystemExit(
            "--minimum-fold-detected-positives must be positive"
        )
    if not 0 < args.minimum_recall <= 1:
        raise SystemExit("--minimum-recall must be in (0, 1]")
    report = analyze(args)
    write_atomic(args.output, report)
    grouped = report["source_grouped_evaluation"]["summary"]
    print(
        f"wrote hybrid report to {args.output}; "
        f"grouped recall={grouped['recall']:.4f}, "
        f"false positives={grouped['false_positive_count']}, "
        f"stable templates="
        f"{report['source_grouped_evaluation']['stable_template_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
