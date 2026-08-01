#!/usr/bin/env python3
"""Apply a frozen explainable rule policy without fitting new thresholds."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from collections import Counter
from pathlib import Path


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


def write_new_atomic(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace evaluation report: {path}")
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


def validate_condition(condition: dict, label: str) -> None:
    for field in ("feature", "family", "direction", "threshold"):
        if field not in condition:
            raise SystemExit(f"{label}: condition has no {field}")
    if condition["direction"] not in {"higher", "lower"}:
        raise SystemExit(f"{label}: condition direction is unsupported")
    threshold = condition["threshold"]
    if (
        not isinstance(threshold, (int, float))
        or isinstance(threshold, bool)
        or not math.isfinite(float(threshold))
    ):
        raise SystemExit(f"{label}: condition threshold is invalid")


def validate_policy(policy: dict) -> list[dict]:
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        raise SystemExit("frozen policy contains no rules")
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise SystemExit(f"rule {index + 1} is not an object")
        validate_condition(rule.get("first", {}), f"rule {index + 1} first")
        validate_condition(
            rule.get("second", {}),
            f"rule {index + 1} second",
        )
    return rules


def row_features(row: dict) -> dict[str, float]:
    runner = row.get("runner")
    if not isinstance(runner, dict):
        raise SystemExit(f"{row.get('case_id')}: runner is missing")
    features = {}
    for namespace in (
        "compression_trace",
        "stereo_trace",
        "transform_grid_probe",
    ):
        features.update(
            flatten_numeric(runner.get(namespace), namespace)
        )
    return features


def evaluate_rule(
    features: dict[str, float],
    rule: dict,
) -> tuple[bool, list[str]]:
    missing = []
    passed = True
    for condition in (rule["first"], rule["second"]):
        feature = condition["feature"]
        if feature not in features:
            missing.append(feature)
            passed = False
            continue
        if not feature_passes(
            features[feature],
            float(condition["threshold"]),
            condition["direction"],
        ):
            passed = False
    return passed, missing


def summarize(rows: list[dict], selected_ids: set[str]) -> dict:
    negatives = [
        row for row in rows if row["expectation"] == "negative"
    ]
    positives = [
        row
        for row in rows
        if row["expectation"] == "controlled_positive"
    ]
    false_positives = [
        row for row in negatives if row["case_id"] in selected_ids
    ]
    detected = [
        row for row in positives if row["case_id"] in selected_ids
    ]
    by_class = {}
    for class_name in sorted({row["class"] for row in rows}):
        class_rows = [
            row for row in rows if row["class"] == class_name
        ]
        selected = sum(
            row["case_id"] in selected_ids for row in class_rows
        )
        by_class[class_name] = {
            "cases": len(class_rows),
            "selected": selected,
            "rate": selected / len(class_rows),
        }
    return {
        "negative_count": len(negatives),
        "false_positive_count": len(false_positives),
        "false_positive_case_ids": sorted(
            row["case_id"] for row in false_positives
        ),
        "controlled_positive_count": len(positives),
        "detected_positive_count": len(detected),
        "recall": len(detected) / len(positives) if positives else None,
        "by_class": by_class,
    }


def command(args: argparse.Namespace) -> int:
    candidate_path = args.candidate.expanduser().resolve()
    policy_path = args.frozen_policy_report.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    for label, path in (
        ("candidate report", candidate_path),
        ("frozen policy report", policy_path),
    ):
        if path.is_symlink() or not path.is_file():
            raise SystemExit(f"{label} is not a regular file: {path}")
    candidate = load_json(candidate_path)
    policy_report = load_json(policy_path)
    policy = policy_report.get("full_development_policy")
    if not isinstance(policy, dict):
        raise SystemExit(
            "frozen report contains no full_development_policy"
        )
    rules = validate_policy(policy)
    rows = candidate.get("results")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("candidate report contains no result rows")
    case_ids = [row.get("case_id") for row in rows]
    if any(not isinstance(case_id, str) or not case_id for case_id in case_ids):
        raise SystemExit("candidate report contains an invalid case ID")
    if len(case_ids) != len(set(case_ids)):
        raise SystemExit("candidate report contains duplicate case IDs")
    if candidate.get("feature_version") != 0:
        raise SystemExit("candidate feature version is not prototype version 0")

    selected_by_rule: list[set[str]] = [set() for _ in rules]
    missing_by_rule: list[Counter[str]] = [
        Counter() for _ in rules
    ]
    evaluated = []
    for row in sorted(rows, key=lambda item: item["case_id"]):
        if row.get("expectation") not in {
            "negative",
            "controlled_positive",
        }:
            raise SystemExit(
                f"{row['case_id']}: unsupported expectation"
            )
        features = row_features(row)
        passing_rules = []
        for index, rule in enumerate(rules):
            passed, missing = evaluate_rule(features, rule)
            missing_by_rule[index].update(missing)
            if passed:
                passing_rules.append(index + 1)
                selected_by_rule[index].add(row["case_id"])
        evaluated.append(
            {
                "case_id": row["case_id"],
                "source_group": row["source_group"],
                "partition_group": row.get(
                    "partition_group",
                    row["source_group"],
                ),
                "class": row["class"],
                "expectation": row["expectation"],
                "passing_rule_numbers": passing_rules,
                "selected": bool(passing_rules),
            }
        )
    union = set().union(*selected_by_rule)
    report = {
        "schema_version": 1,
        "disposition": {
            "state": "external_development_evaluation",
            "thresholds_retuned": False,
            "rules_reselected": False,
            "release_evidence": False,
            "public_verdict_enabled": False,
            "reason": (
                "This applies a previously frozen development rule policy to "
                "a labeled Tier B hard-negative corpus. It is neither an "
                "untouched Tier A release set nor evidence for public enablement."
            ),
        },
        "source_candidate": {
            "path": str(candidate_path),
            "sha256": sha256_file(candidate_path),
            "corpus_id": candidate.get("corpus_id"),
            "case_count": len(rows),
            "runner_sha256": candidate.get("runner_sha256"),
            "harness_sha256": candidate.get("harness_sha256"),
            "feature_version": candidate.get("feature_version"),
        },
        "source_frozen_policy": {
            "path": str(policy_path),
            "sha256": sha256_file(policy_path),
            "rule_count": len(rules),
            "rules": rules,
        },
        "combined_frozen_policy": summarize(evaluated, union),
        "by_rule": [
            {
                "rule_number": index + 1,
                "rule": rule,
                "missing_feature_counts": dict(
                    sorted(missing_by_rule[index].items())
                ),
                "evaluation": summarize(
                    evaluated,
                    selected_by_rule[index],
                ),
            }
            for index, rule in enumerate(rules)
        ],
        "results": evaluated,
    }
    write_new_atomic(output_path, report)
    print(f"wrote frozen rule evaluation to {output_path}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--candidate", type=Path, required=True)
    result.add_argument("--frozen-policy-report", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
