#!/usr/bin/env python3
"""Reproduce a development-only OOF CNN and stable-rule union."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import statistics
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPLAINABLE_PATH = (
    ROOT / "scripts/analyze-audio-integrity-explainable-policy.py"
)


def load_explainable():
    spec = importlib.util.spec_from_file_location(
        "audio_integrity_explainable_policy",
        EXPLAINABLE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {EXPLAINABLE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXPLAINABLE = load_explainable()


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
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace ensemble report: {path}")
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


def auc(positives: list[float], negatives: list[float]) -> float:
    return sum(
        1.0 if positive > negative else 0.5 if positive == negative else 0.0
        for positive in positives
        for negative in negatives
    ) / (len(positives) * len(negatives))


def validate_candidate_evidence(
    stable: dict,
    candidate_paths: list[Path],
) -> None:
    expected = sorted(
        item.get("report_sha256")
        for item in stable.get("candidate_evidence", [])
    )
    observed = sorted(sha256_file(path) for path in candidate_paths)
    if not expected or expected != observed:
        raise SystemExit(
            "stable-rule report does not commit to the supplied candidates"
        )


def cnn_rows(reports: list[dict], candidate_rows: list[dict]) -> list[dict]:
    expected = {row["case_id"]: row for row in candidate_rows}
    report_rows = [
        {row["case_id"]: row for row in report.get("results", [])}
        for report in reports
    ]
    if any(set(rows) != set(expected) for rows in report_rows):
        raise SystemExit("CNN and candidate reports contain different cases")

    commitment_fields = (
        "manifest_signature",
        "fingerprint_signature",
        "feature_cache_sha256",
        "fold_seed",
        "early_stop_seed",
        "fold_count",
    )
    for field in commitment_fields:
        values = {json.dumps(report.get(field), sort_keys=True) for report in reports}
        if len(values) != 1:
            raise SystemExit(f"CNN reports disagree on {field}")

    output = []
    for case_id, candidate in sorted(expected.items()):
        source_rows = [rows[case_id] for rows in report_rows]
        identity = {
            (
                row["source_group"],
                row.get("partition_group", row["source_group"]),
                row["class"],
                row["expectation"],
                row["fold"],
            )
            for row in source_rows
        }
        expected_identity = (
            candidate["source_group"],
            candidate["partition_group"],
            candidate["class"],
            candidate["expectation"],
        )
        if len(identity) != 1 or next(iter(identity))[:4] != expected_identity:
            raise SystemExit(f"{case_id}: CNN and candidate identity differs")
        values = [row["lossy_probability_mean"] for row in source_rows]
        if any(not isinstance(value, (int, float)) for value in values):
            raise SystemExit(f"{case_id}: CNN score is not numeric")
        output.append(
            {
                "case_id": case_id,
                "source_group": candidate["source_group"],
                "partition_group": candidate["partition_group"],
                "class": candidate["class"],
                "expectation": candidate["expectation"],
                "cnn_fold": source_rows[0]["fold"],
                "cnn_seed_scores": values,
                "cnn_ensemble_score": statistics.fmean(values),
            }
        )
    return output


def nested_rule_selection(stable: dict, rows: list[dict]) -> set[str]:
    method = stable.get("method", {})
    fold_count = method.get("fold_count")
    fold_seed = method.get("fold_seed")
    if not isinstance(fold_count, int) or fold_count < 2:
        raise SystemExit("stable-rule report has an invalid fold count")
    if not isinstance(fold_seed, int):
        raise SystemExit("stable-rule report has an invalid fold seed")

    groups = sorted({row["partition_group"] for row in rows})
    shuffled = groups.copy()
    random.Random(fold_seed).shuffle(shuffled)
    group_fold = {
        group: index % fold_count + 1
        for index, group in enumerate(shuffled)
    }

    selected: set[str] = set()
    expected_folds = set(range(1, fold_count + 1))
    templates = stable.get("selected_templates", [])
    if not templates:
        raise SystemExit("stable-rule report selected no templates")
    for template in templates:
        folds = template.get("folds", [])
        if {item.get("fold") for item in folds} != expected_folds:
            raise SystemExit("stable-rule template does not cover every fold")
        template_selected: set[str] = set()
        for item in folds:
            fold = item["fold"]
            validation = [
                row
                for row in rows
                if group_fold[row["partition_group"]] == fold
            ]
            fold_selected = EXPLAINABLE.select(
                validation,
                item["fitted_policy"],
            )
            if EXPLAINABLE.summary(validation, fold_selected) != (
                item["validation"]
            ):
                raise SystemExit(
                    f"stable-rule validation differs in fold {fold}"
                )
            template_selected.update(fold_selected)
        if EXPLAINABLE.summary(rows, template_selected) != (
            template["oof_summary"]
        ):
            raise SystemExit("stable-rule template OOF summary differs")
        selected.update(template_selected)
    if EXPLAINABLE.summary(rows, selected) != stable.get(
        "nested_grouped_evaluation"
    ):
        raise SystemExit("stable-rule nested evaluation differs")
    return selected


def selection_summary(rows: list[dict], selected: set[str]) -> dict:
    summary = EXPLAINABLE.summary(rows, selected)
    summary["recall"] = (
        summary["detected_positive_count"]
        / summary["controlled_positive_count"]
    )
    summary["selected_case_ids"] = sorted(selected)
    return summary


def command(args: argparse.Namespace) -> int:
    candidate_paths = [
        path.expanduser().resolve() for path in args.candidate
    ]
    stable_path = args.stable_rule_report.expanduser().resolve()
    cnn_paths = [
        path.expanduser().resolve() for path in args.cnn_report
    ]
    if len(cnn_paths) < 2:
        raise SystemExit("at least two CNN reports are required")
    stable = load_json(stable_path)
    validate_candidate_evidence(stable, candidate_paths)
    candidates = EXPLAINABLE.candidate_rows(candidate_paths)
    reports = [load_json(path) for path in cnn_paths]
    combined = cnn_rows(reports, candidates)

    negatives = [
        row["cnn_ensemble_score"]
        for row in combined
        if row["expectation"] == "negative"
    ]
    positives = [
        row["cnn_ensemble_score"]
        for row in combined
        if row["expectation"] == "controlled_positive"
    ]
    if not negatives or not positives:
        raise SystemExit("ensemble analysis requires both classes")
    boundary = max(negatives)
    cnn_selected = {
        row["case_id"]
        for row in combined
        if row["cnn_ensemble_score"] > boundary
    }
    rule_selected = nested_rule_selection(stable, candidates)
    union_selected = cnn_selected | rule_selected

    candidate_by_id = {row["case_id"]: row for row in candidates}
    result_rows = []
    for row in combined:
        case_id = row["case_id"]
        result_rows.append(
            {
                **row,
                "cnn_selected": case_id in cnn_selected,
                "stable_rule_selected": case_id in rule_selected,
                "union_selected": case_id in union_selected,
            }
        )

    by_class = {}
    for class_name in sorted({row["class"] for row in candidates}):
        class_ids = {
            row["case_id"]
            for row in candidates
            if row["class"] == class_name
        }
        by_class[class_name] = {
            "cases": len(class_ids),
            "cnn_selected": len(class_ids & cnn_selected),
            "stable_rule_selected": len(class_ids & rule_selected),
            "union_selected": len(class_ids & union_selected),
        }

    report = {
        "schema_version": 1,
        "disposition": {
            "state": "research_development_only",
            "ensemble_size_selected_after_observing_development_results": True,
            "boundary_calibrated_on_development_negatives": True,
            "stable_rules_selected_on_development_folds": True,
            "release_evidence": False,
            "held_out_release_evaluation_opened": False,
            "public_verdict_enabled": False,
            "reason": (
                "This reproduces an out-of-fold development candidate. It "
                "must be frozen and pass a new disjoint Tier A gate before "
                "any product use."
            ),
        },
        "method": {
            "cnn": "arithmetic mean of per-seed OOF case probabilities",
            "cnn_boundary": "strictly greater than maximum negative score",
            "stable_rules": "union of nested grouped-fold selections",
            "combination": "CNN OR stable rules",
        },
        "case_count": len(candidates),
        "source_group_count": len(
            {row["source_group"] for row in candidates}
        ),
        "partition_group_count": len(
            {row["partition_group"] for row in candidates}
        ),
        "cnn_seed_count": len(reports),
        "cnn_seeds": [report.get("seed") for report in reports],
        "cnn_case_level_auc": auc(positives, negatives),
        "cnn_zero_false_positive_boundary": boundary,
        "cnn_summary": selection_summary(candidates, cnn_selected),
        "stable_rule_summary": selection_summary(
            candidates,
            rule_selected,
        ),
        "union_summary": selection_summary(candidates, union_selected),
        "by_class": by_class,
        "evidence": {
            "candidate_reports": [
                {
                    "path": str(path),
                    "sha256": sha256_file(path),
                }
                for path in candidate_paths
            ],
            "stable_rule_report": {
                "path": str(stable_path),
                "sha256": sha256_file(stable_path),
            },
            "cnn_reports": [
                {
                    "path": str(path),
                    "sha256": sha256_file(path),
                    "seed": report.get("seed"),
                    "trainer_source_sha256": report.get(
                        "trainer_source_sha256"
                    ),
                    "feature_cache_sha256": report.get(
                        "feature_cache_sha256"
                    ),
                }
                for path, report in zip(cnn_paths, reports)
            ],
            "analysis_script_sha256": sha256_file(
                Path(__file__).resolve()
            ),
            "explainable_library_sha256": sha256_file(
                EXPLAINABLE_PATH
            ),
        },
        "results": result_rows,
    }
    if set(candidate_by_id) != {row["case_id"] for row in result_rows}:
        raise RuntimeError("ensemble result case set differs")
    write_atomic(args.output, report)
    print(f"wrote development ensemble report to {args.output}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--candidate",
        type=Path,
        action="append",
        required=True,
    )
    result.add_argument("--stable-rule-report", type=Path, required=True)
    result.add_argument(
        "--cnn-report",
        type=Path,
        action="append",
        required=True,
    )
    result.add_argument("--output", type=Path, required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
