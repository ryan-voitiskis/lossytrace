#!/usr/bin/env python3
"""Evaluate explainable-only two-family policies on development measurements."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
import tempfile
from collections import Counter
from pathlib import Path

NEGATIVE_PASS_RATES = (0.0, 0.01, 0.025, 0.05, 0.10, 0.20)


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def candidate_rows(paths: list[Path]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for path in paths:
        for row in load_json(path).get("results", []):
            previous = by_id.setdefault(row["case_id"], row)
            if previous != row:
                raise SystemExit(f"conflicting candidate row: {row['case_id']}")
    if not by_id:
        raise SystemExit("candidate reports contain no result rows")
    rows = []
    for case_id, row in sorted(by_id.items()):
        features = {}
        runner = row["runner"]
        for namespace in (
            "compression_trace",
            "stereo_trace",
            "transform_grid_probe",
        ):
            features.update(flatten_numeric(runner.get(namespace), namespace))
        rows.append(
            {
                "case_id": case_id,
                "source_group": row["source_group"],
                "partition_group": row.get(
                    "partition_group",
                    row["source_group"],
                ),
                "class": row["class"],
                "expectation": row["expectation"],
                "features": features,
            }
        )
    return rows


def feature_passes(value: float, threshold: float, direction: str) -> bool:
    return value > threshold if direction == "higher" else value < threshold


def threshold_for_rate(
    values: list[float],
    direction: str,
    rate: float,
) -> float:
    ordered = sorted(values)
    if rate == 0:
        return max(ordered) if direction == "higher" else min(ordered)
    count = max(1, math.floor(rate * len(ordered)))
    if direction == "higher":
        boundary = ordered[-count]
        return math.nextafter(boundary, -math.inf)
    boundary = ordered[count - 1]
    return math.nextafter(boundary, math.inf)


def feature_candidates(
    rows: list[dict],
    maximum_negative_pass_rate: float,
) -> dict[str, list[dict]]:
    negatives = {
        row["case_id"]
        for row in rows
        if row["expectation"] == "negative"
    }
    positives = {
        row["case_id"]
        for row in rows
        if row["expectation"] == "controlled_positive"
    }
    feature_names = sorted(
        {
            name
            for row in rows
            for name in row["features"]
            if feature_family(name) is not None
        }
    )
    by_family: dict[str, list[dict]] = {}
    for feature in feature_names:
        family = feature_family(feature)
        measured_negatives = [
            row["features"][feature]
            for row in rows
            if row["case_id"] in negatives and feature in row["features"]
        ]
        if not measured_negatives:
            continue
        for direction in ("higher", "lower"):
            seen_thresholds = set()
            for rate in NEGATIVE_PASS_RATES:
                if rate > maximum_negative_pass_rate:
                    continue
                threshold = threshold_for_rate(
                    measured_negatives,
                    direction,
                    rate,
                )
                if threshold in seen_thresholds:
                    continue
                seen_thresholds.add(threshold)
                selected = {
                    row["case_id"]
                    for row in rows
                    if feature in row["features"]
                    and feature_passes(
                        row["features"][feature],
                        threshold,
                        direction,
                    )
                }
                selected_positives = selected & positives
                if not selected_positives:
                    continue
                by_family.setdefault(family, []).append(
                    {
                        "feature": feature,
                        "family": family,
                        "direction": direction,
                        "threshold": threshold,
                        "requested_maximum_negative_rate": rate,
                        "selected_negative_ids": selected & negatives,
                        "selected_positive_ids": selected_positives,
                    }
                )
    return by_family


def public_candidate(candidate: dict) -> dict:
    return {
        key: value
        for key, value in candidate.items()
        if not key.endswith("_ids")
    }


def zero_false_positive_two_family_rules(
    rows: list[dict],
    maximum_negative_pass_rate: float,
) -> list[dict]:
    candidates = feature_candidates(rows, maximum_negative_pass_rate)
    rules = []
    for first_family, second_family in itertools.combinations(
        sorted(candidates),
        2,
    ):
        for first in candidates[first_family]:
            for second in candidates[second_family]:
                false_positives = (
                    first["selected_negative_ids"]
                    & second["selected_negative_ids"]
                )
                if false_positives:
                    continue
                detected = (
                    first["selected_positive_ids"]
                    & second["selected_positive_ids"]
                )
                if not detected:
                    continue
                candidate = {
                    "families": [first_family, second_family],
                    "first": first,
                    "second": second,
                    "detected_positive_ids": detected,
                }
                rules.append(candidate)
    return rules


def rule_key(rule: dict, detected_count: int) -> tuple:
    first = rule["first"]
    second = rule["second"]
    return (
        detected_count,
        len(rule["detected_positive_ids"]),
        -len(first["selected_negative_ids"])
        - len(second["selected_negative_ids"]),
        rule["families"][0],
        rule["families"][1],
        first["feature"],
        second["feature"],
        first["direction"],
        second["direction"],
        first["threshold"],
        second["threshold"],
    )


def best_two_family_policy(
    rows: list[dict],
    maximum_negative_pass_rate: float,
) -> dict | None:
    rules = zero_false_positive_two_family_rules(
        rows,
        maximum_negative_pass_rate,
    )
    if not rules:
        return None
    return max(
        rules,
        key=lambda rule: rule_key(
            rule,
            len(rule["detected_positive_ids"]),
        ),
    )


def best_rule_set_policy(
    rows: list[dict],
    maximum_negative_pass_rate: float,
    maximum_rules: int,
) -> dict | None:
    if maximum_rules == 1:
        return best_two_family_policy(rows, maximum_negative_pass_rate)
    available = zero_false_positive_two_family_rules(
        rows,
        maximum_negative_pass_rate,
    )
    selected_rules = []
    detected: set[str] = set()
    while available and len(selected_rules) < maximum_rules:
        best = max(
            available,
            key=lambda rule: rule_key(
                rule,
                len(rule["detected_positive_ids"] - detected),
            ),
        )
        newly_detected = best["detected_positive_ids"] - detected
        if not newly_detected:
            break
        selected_rules.append(best)
        detected.update(best["detected_positive_ids"])
        available.remove(best)
    if not selected_rules:
        return None
    return {
        "rules": selected_rules,
        "detected_positive_ids": detected,
    }


def select(rows: list[dict], policy: dict) -> set[str]:
    if "rules" in policy:
        return set().union(*(select(rows, rule) for rule in policy["rules"]))
    selected = set()
    first = policy["first"]
    second = policy["second"]
    for row in rows:
        if (
            first["feature"] in row["features"]
            and second["feature"] in row["features"]
            and feature_passes(
                row["features"][first["feature"]],
                first["threshold"],
                first["direction"],
            )
            and feature_passes(
                row["features"][second["feature"]],
                second["threshold"],
                second["direction"],
            )
        ):
            selected.add(row["case_id"])
    return selected


def summary(rows: list[dict], selected: set[str]) -> dict:
    false_positives = [
        row
        for row in rows
        if row["case_id"] in selected and row["expectation"] == "negative"
    ]
    detected = [
        row
        for row in rows
        if row["case_id"] in selected
        and row["expectation"] == "controlled_positive"
    ]
    return {
        "negative_count": sum(
            row["expectation"] == "negative" for row in rows
        ),
        "false_positive_count": len(false_positives),
        "false_positive_classes": dict(
            sorted(Counter(row["class"] for row in false_positives).items())
        ),
        "controlled_positive_count": sum(
            row["expectation"] == "controlled_positive" for row in rows
        ),
        "detected_positive_count": len(detected),
        "detected_by_class": dict(
            sorted(Counter(row["class"] for row in detected).items())
        ),
    }


def policy_report(policy: dict) -> dict:
    if "rules" in policy:
        return {
            "rule_count": len(policy["rules"]),
            "rules": [
                policy_report(rule)
                for rule in policy["rules"]
            ],
            "training_detected_positive_count": len(
                policy["detected_positive_ids"]
            ),
        }
    return {
        "families": policy["families"],
        "first": public_candidate(policy["first"]),
        "second": public_candidate(policy["second"]),
        "training_detected_positive_count": len(
            policy["detected_positive_ids"]
        ),
    }


def command(args: argparse.Namespace) -> int:
    if not 0 <= args.maximum_negative_pass_rate <= max(NEGATIVE_PASS_RATES):
        raise SystemExit(
            "--maximum-negative-pass-rate must be between 0 and 0.20"
        )
    if not 1 <= args.maximum_rules <= 8:
        raise SystemExit("--maximum-rules must be in 1..=8")
    candidate_paths = [
        path.expanduser().resolve() for path in args.candidate
    ]
    candidate_evidence = []
    for path in candidate_paths:
        candidate = load_json(path)
        runner_sha256 = candidate.get("runner_sha256")
        harness_sha256 = candidate.get("harness_sha256")
        if (
            not isinstance(runner_sha256, str)
            or len(runner_sha256) != 64
            or not isinstance(harness_sha256, str)
            or len(harness_sha256) != 64
        ):
            if not args.allow_legacy_uncommitted_candidates:
                raise SystemExit(
                    f"{path}: candidate lacks runner and harness commitments"
                )
            runner_sha256 = None
            harness_sha256 = None
        candidate_evidence.append(
            {
                "report_sha256": sha256_file(path),
                "runner_sha256": runner_sha256,
                "harness_sha256": harness_sha256,
                "commitment_state": (
                    "committed"
                    if runner_sha256 is not None
                    else "legacy_uncommitted"
                ),
                "feature_version": candidate.get("feature_version"),
                "case_count": len(candidate.get("results", [])),
            }
        )
    rows = candidate_rows(candidate_paths)
    groups = sorted({row["partition_group"] for row in rows})
    if len(groups) < args.folds:
        raise SystemExit("fewer partition groups than folds")
    shuffled = groups.copy()
    random.Random(args.fold_seed).shuffle(shuffled)
    group_fold = {
        group: index % args.folds + 1 for index, group in enumerate(shuffled)
    }

    full_policy = best_rule_set_policy(
        rows,
        args.maximum_negative_pass_rate,
        args.maximum_rules,
    )
    if full_policy is None:
        raise SystemExit("no zero-training-false-positive two-family policy found")
    folds = []
    for fold in range(1, args.folds + 1):
        training = [
            row for row in rows if group_fold[row["partition_group"]] != fold
        ]
        validation = [
            row for row in rows if group_fold[row["partition_group"]] == fold
        ]
        policy = best_rule_set_policy(
            training,
            args.maximum_negative_pass_rate,
            args.maximum_rules,
        )
        if policy is None:
            folds.append(
                {
                    "fold": fold,
                    "policy_found": False,
                    "validation": summary(validation, set()),
                }
            )
            continue
        folds.append(
            {
                "fold": fold,
                "policy_found": True,
                "frozen_training_policy": policy_report(policy),
                "validation": summary(validation, select(validation, policy)),
            }
        )

    nested = {
        "fold_count": len(folds),
        "negative_count": sum(fold["validation"]["negative_count"] for fold in folds),
        "false_positive_count": sum(
            fold["validation"]["false_positive_count"] for fold in folds
        ),
        "false_positive_classes": dict(
            sorted(
                sum(
                    (
                        Counter(fold["validation"]["false_positive_classes"])
                        for fold in folds
                    ),
                    Counter(),
                ).items()
            )
        ),
        "controlled_positive_count": sum(
            fold["validation"]["controlled_positive_count"] for fold in folds
        ),
        "detected_positive_count": sum(
            fold["validation"]["detected_positive_count"] for fold in folds
        ),
        "detected_by_class": dict(
            sorted(
                sum(
                    (
                        Counter(fold["validation"]["detected_by_class"])
                        for fold in folds
                    ),
                    Counter(),
                ).items()
            )
        ),
    }
    external_evaluation = None
    if args.evaluation_candidate:
        evaluation_paths = [
            path.expanduser().resolve()
            for path in args.evaluation_candidate
        ]
        evaluation_evidence = []
        for path in evaluation_paths:
            candidate = load_json(path)
            runner_sha256 = candidate.get("runner_sha256")
            harness_sha256 = candidate.get("harness_sha256")
            if (
                not isinstance(runner_sha256, str)
                or len(runner_sha256) != 64
                or not isinstance(harness_sha256, str)
                or len(harness_sha256) != 64
            ):
                raise SystemExit(
                    f"{path}: evaluation candidate lacks runner and harness "
                    "commitments"
                )
            evaluation_evidence.append(
                {
                    "report_sha256": sha256_file(path),
                    "runner_sha256": runner_sha256,
                    "harness_sha256": harness_sha256,
                    "feature_version": candidate.get("feature_version"),
                    "case_count": len(candidate.get("results", [])),
                }
            )
        evaluation_rows = candidate_rows(evaluation_paths)
        training_case_ids = {row["case_id"] for row in rows}
        evaluation_case_ids = {row["case_id"] for row in evaluation_rows}
        overlapping_case_ids = sorted(
            training_case_ids & evaluation_case_ids
        )
        if overlapping_case_ids:
            raise SystemExit(
                "training and external evaluation contain overlapping cases: "
                + ", ".join(overlapping_case_ids)
            )
        training_groups = {row["source_group"] for row in rows}
        evaluation_groups = {
            row["source_group"] for row in evaluation_rows
        }
        overlapping_groups = sorted(training_groups & evaluation_groups)
        if overlapping_groups:
            raise SystemExit(
                "training and external evaluation contain overlapping source "
                "groups: "
                + ", ".join(overlapping_groups)
            )
        training_partitions = {
            row["partition_group"] for row in rows
        }
        evaluation_partitions = {
            row["partition_group"] for row in evaluation_rows
        }
        overlapping_partitions = sorted(
            training_partitions & evaluation_partitions
        )
        if overlapping_partitions:
            raise SystemExit(
                "training and external evaluation contain overlapping "
                "partition groups: "
                + ", ".join(overlapping_partitions)
            )
        externally_selected = select(evaluation_rows, full_policy)
        external_evaluation = {
            "state": "disjoint_development_evaluation",
            "thresholds_refit": False,
            "source_groups_disjoint": True,
            "partition_groups_disjoint": True,
            "candidate_evidence": evaluation_evidence,
            "case_count": len(evaluation_rows),
            "source_group_count": len(evaluation_groups),
            "partition_group_count": len(evaluation_partitions),
            "summary": summary(evaluation_rows, externally_selected),
            "selected_case_ids": sorted(externally_selected),
        }
    report = {
            "schema_version": 1,
            "disposition": {
                "state": "development_only",
                "held_out_opened": False,
                "public_verdict_enabled": False,
                "reason": (
                    "Feature pairs and thresholds were selected on "
                    "development data and have not passed the Tier A gate."
                ),
            },
            "method": {
                "policy": (
                    "OR of zero-training-false-positive rules; two "
                    "explainable feature families must both pass each rule"
                    if args.maximum_rules > 1
                    else "two explainable feature families must both pass"
                ),
                "maximum_rules": args.maximum_rules,
                "negative_pass_rates_explored": NEGATIVE_PASS_RATES,
                "maximum_negative_pass_rate": (
                    args.maximum_negative_pass_rate
                ),
                "fold_count": args.folds,
                "fold_seed": args.fold_seed,
                "thresholds_refit_inside_each_training_fold": True,
            },
            "case_count": len(rows),
            "partition_group_count": len(groups),
            "source_group_count": len(
                {row["source_group"] for row in rows}
            ),
            "candidate_evidence": candidate_evidence,
            "full_development_policy": policy_report(full_policy),
            "full_development_evaluation": summary(
                rows,
                select(rows, full_policy),
            ),
            "nested_grouped_evaluation": nested,
            "folds": folds,
        }
    if external_evaluation is not None:
        report["external_evaluation"] = external_evaluation
    write_atomic(args.output, report)
    print(f"wrote explainable-only development report to {args.output}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--candidate", type=Path, action="append", required=True)
    result.add_argument(
        "--evaluation-candidate",
        type=Path,
        action="append",
        help=(
            "apply the full development policy without refitting to a "
            "source-group-disjoint development candidate"
        ),
    )
    result.add_argument("--folds", type=int, default=5)
    result.add_argument("--fold-seed", type=int, default=20260730)
    result.add_argument(
        "--maximum-negative-pass-rate",
        type=float,
        default=0.20,
    )
    result.add_argument(
        "--maximum-rules",
        type=int,
        default=1,
        help=(
            "research-only maximum number of zero-training-false-positive "
            "two-family rules to combine with OR"
        ),
    )
    result.add_argument(
        "--allow-legacy-uncommitted-candidates",
        action="store_true",
        help=(
            "research only: read old candidate reports that predate runner "
            "and harness commitments; freeze will reject the resulting report"
        ),
    )
    result.add_argument("--output", type=Path, required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
