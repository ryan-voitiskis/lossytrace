#!/usr/bin/env python3
"""Select development-only rule templates stable across grouped folds."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPLAINABLE_PATH = (
    ROOT / "scripts/analyze-audio-integrity-explainable-policy.py"
)
DEFAULT_ALLOWED_FAMILIES = (
    "band_rupture",
    "spectral_edge",
    "spectral_holes",
    "transform_alignment",
    "transform_grid",
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_atomic(path: Path, value: dict) -> None:
    if path.exists():
        raise SystemExit(f"refusing to replace stable-rule report: {path}")
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


def template_key(rule: dict) -> tuple:
    first = rule["first"]
    second = rule["second"]
    return (
        first["family"],
        first["feature"],
        first["direction"],
        first["requested_maximum_negative_rate"],
        second["family"],
        second["feature"],
        second["direction"],
        second["requested_maximum_negative_rate"],
    )


def template_description(key: tuple) -> dict:
    return {
        "first": {
            "family": key[0],
            "feature": key[1],
            "direction": key[2],
            "requested_maximum_negative_rate": key[3],
        },
        "second": {
            "family": key[4],
            "feature": key[5],
            "direction": key[6],
            "requested_maximum_negative_rate": key[7],
        },
    }


def candidate_evidence(paths: list[Path]) -> list[dict]:
    evidence = []
    for path in paths:
        candidate = EXPLAINABLE.load_json(path)
        runner_sha256 = candidate.get("runner_sha256")
        harness_sha256 = candidate.get("harness_sha256")
        if (
            not isinstance(runner_sha256, str)
            or len(runner_sha256) != 64
            or not isinstance(harness_sha256, str)
            or len(harness_sha256) != 64
        ):
            raise SystemExit(
                f"{path}: candidate lacks runner and harness commitments"
            )
        evidence.append(
            {
                "report_sha256": sha256_file(path),
                "runner_sha256": runner_sha256,
                "harness_sha256": harness_sha256,
                "feature_version": candidate.get("feature_version"),
                "case_count": len(candidate.get("results", [])),
            }
        )
    return evidence


def rules_by_template(
    rows: list[dict],
    maximum_negative_pass_rate: float,
    allowed_families: set[str],
) -> dict[tuple, dict]:
    rules = EXPLAINABLE.zero_false_positive_two_family_rules(
        rows,
        maximum_negative_pass_rate,
    )
    output = {}
    for rule in rules:
        if not set(rule["families"]).issubset(allowed_families):
            continue
        key = template_key(rule)
        previous = output.setdefault(key, rule)
        if previous != rule:
            raise SystemExit("duplicate rule template has conflicting thresholds")
    return output


def command(args: argparse.Namespace) -> int:
    if not 0 <= args.maximum_negative_pass_rate <= 0.20:
        raise SystemExit(
            "--maximum-negative-pass-rate must be between 0 and 0.20"
        )
    if not 1 <= args.maximum_rules <= 8:
        raise SystemExit("--maximum-rules must be in 1..=8")
    if args.minimum_fold_detected_positives < 1:
        raise SystemExit(
            "--minimum-fold-detected-positives must be positive"
        )
    allowed_families = set(
        args.allowed_family or DEFAULT_ALLOWED_FAMILIES
    )
    unknown_families = allowed_families - set(DEFAULT_ALLOWED_FAMILIES) - {
        "stereo"
    }
    if unknown_families:
        raise SystemExit(
            "unknown allowed families: " + ", ".join(sorted(unknown_families))
        )
    candidate_paths = [
        path.expanduser().resolve() for path in args.candidate
    ]
    evidence = candidate_evidence(candidate_paths)
    rows = EXPLAINABLE.candidate_rows(candidate_paths)
    groups = sorted({row["partition_group"] for row in rows})
    if len(groups) < args.folds:
        raise SystemExit("fewer partition groups than folds")
    shuffled = groups.copy()
    random.Random(args.fold_seed).shuffle(shuffled)
    group_fold = {
        group: index % args.folds + 1
        for index, group in enumerate(shuffled)
    }
    full_rules = rules_by_template(
        rows,
        args.maximum_negative_pass_rate,
        allowed_families,
    )
    fold_rules: dict[int, dict[tuple, dict]] = {}
    fold_validation: dict[int, list[dict]] = {}
    fold_safe_templates: dict[int, dict[tuple, dict]] = {}
    for fold in range(1, args.folds + 1):
        training = [
            row for row in rows if group_fold[row["partition_group"]] != fold
        ]
        validation = [
            row for row in rows if group_fold[row["partition_group"]] == fold
        ]
        fitted = rules_by_template(
            training,
            args.maximum_negative_pass_rate,
            allowed_families,
        )
        safe = {}
        for key, rule in fitted.items():
            selected = EXPLAINABLE.select(validation, rule)
            validation_summary = EXPLAINABLE.summary(validation, selected)
            if (
                validation_summary["false_positive_count"] == 0
                and validation_summary["detected_positive_count"]
                >= args.minimum_fold_detected_positives
            ):
                safe[key] = {
                    "rule": rule,
                    "selected_ids": selected,
                    "summary": validation_summary,
                }
        fold_rules[fold] = fitted
        fold_validation[fold] = validation
        fold_safe_templates[fold] = safe
    stable_keys = set(full_rules)
    for safe in fold_safe_templates.values():
        stable_keys.intersection_update(safe)
    if not stable_keys:
        raise SystemExit(
            "no rule template was safe and useful in every grouped fold"
        )

    template_metrics = {}
    for key in sorted(stable_keys):
        selected_ids = set()
        fold_details = []
        for fold in range(1, args.folds + 1):
            detail = fold_safe_templates[fold][key]
            selected_ids.update(detail["selected_ids"])
            fold_details.append(
                {
                    "fold": fold,
                    "fitted_policy": EXPLAINABLE.policy_report(
                        detail["rule"]
                    ),
                    "validation": detail["summary"],
                }
            )
        oof_summary = EXPLAINABLE.summary(rows, selected_ids)
        if oof_summary["false_positive_count"] != 0:
            raise RuntimeError("stable template OOF safety contract differs")
        template_metrics[key] = {
            "template": template_description(key),
            "oof_selected_ids": selected_ids,
            "oof_summary": oof_summary,
            "folds": fold_details,
            "full_rule": full_rules[key],
        }

    selected_keys = []
    selected_oof_ids: set[str] = set()
    remaining = set(stable_keys)
    while remaining and len(selected_keys) < args.maximum_rules:
        best_key = max(
            remaining,
            key=lambda key: (
                len(
                    template_metrics[key]["oof_selected_ids"]
                    - selected_oof_ids
                ),
                len(template_metrics[key]["oof_selected_ids"]),
                tuple(str(value) for value in key),
            ),
        )
        newly_selected = (
            template_metrics[best_key]["oof_selected_ids"]
            - selected_oof_ids
        )
        if not newly_selected:
            break
        selected_keys.append(best_key)
        selected_oof_ids.update(
            template_metrics[best_key]["oof_selected_ids"]
        )
        remaining.remove(best_key)
    if not selected_keys:
        raise SystemExit("stable rule selection detected no positives")

    selected_full_rules = [
        full_rules[key] for key in selected_keys
    ]
    full_policy = {
        "rules": selected_full_rules,
        "detected_positive_ids": set().union(
            *(
                rule["detected_positive_ids"]
                for rule in selected_full_rules
            )
        ),
    }
    full_selected = EXPLAINABLE.select(rows, full_policy)
    external_evaluation = None
    if args.evaluation_candidate:
        evaluation_paths = [
            path.expanduser().resolve()
            for path in args.evaluation_candidate
        ]
        evaluation_evidence = candidate_evidence(evaluation_paths)
        evaluation_rows = EXPLAINABLE.candidate_rows(evaluation_paths)
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
        training_case_ids = {row["case_id"] for row in rows}
        evaluation_case_ids = {
            row["case_id"] for row in evaluation_rows
        }
        overlapping_cases = sorted(
            training_case_ids & evaluation_case_ids
        )
        if overlapping_cases:
            raise SystemExit(
                "training and external evaluation contain overlapping cases: "
                + ", ".join(overlapping_cases)
            )
        external_selected = EXPLAINABLE.select(
            evaluation_rows,
            full_policy,
        )
        external_evaluation = {
            "state": "disjoint_development_evaluation",
            "thresholds_refit": False,
            "source_groups_disjoint": True,
            "partition_groups_disjoint": True,
            "candidate_evidence": evaluation_evidence,
            "case_count": len(evaluation_rows),
            "source_group_count": len(evaluation_groups),
            "partition_group_count": len(evaluation_partitions),
            "summary": EXPLAINABLE.summary(
                evaluation_rows,
                external_selected,
            ),
            "selected_case_ids": sorted(external_selected),
        }

    report = {
        "schema_version": 1,
        "disposition": {
            "state": "research_development_only",
            "held_out_opened": False,
            "public_verdict_enabled": False,
            "reason": (
                "Rule templates were selected using grouped development "
                "partition-grouped folds; untouched release labels remain "
                "sealed."
            ),
        },
        "method": {
            "policy": (
                "OR of rule templates that were zero-false-positive and "
                "useful in every partition-grouped development fold; each "
                "rule "
                "requires two explainable feature families"
            ),
            "fold_count": args.folds,
            "fold_seed": args.fold_seed,
            "maximum_negative_pass_rate": (
                args.maximum_negative_pass_rate
            ),
            "maximum_rules": args.maximum_rules,
            "minimum_fold_detected_positives": (
                args.minimum_fold_detected_positives
            ),
            "allowed_families": sorted(allowed_families),
            "thresholds_refit_inside_each_fold": True,
            "templates_selected_using_oof_results": True,
        },
        "candidate_evidence": evidence,
        "case_count": len(rows),
        "partition_group_count": len(groups),
        "source_group_count": len(
            {row["source_group"] for row in rows}
        ),
        "stable_template_count": len(stable_keys),
        "selected_template_count": len(selected_keys),
        "selected_templates": [
            {
                "template": template_metrics[key]["template"],
                "oof_summary": template_metrics[key]["oof_summary"],
                "folds": template_metrics[key]["folds"],
            }
            for key in selected_keys
        ],
        "nested_grouped_evaluation": EXPLAINABLE.summary(
            rows,
            selected_oof_ids,
        ),
        "full_development_policy": EXPLAINABLE.policy_report(
            full_policy
        ),
        "full_development_evaluation": EXPLAINABLE.summary(
            rows,
            full_selected,
        ),
        "commitments": {
            "selection_script_sha256": sha256_file(
                Path(__file__).resolve()
            ),
            "explainable_library_sha256": sha256_file(
                EXPLAINABLE_PATH
            ),
        },
    }
    if external_evaluation is not None:
        report["external_evaluation"] = external_evaluation
    write_atomic(args.output, report)
    print(f"wrote stable-rule development report to {args.output}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--candidate", type=Path, action="append", required=True)
    result.add_argument(
        "--evaluation-candidate",
        type=Path,
        action="append",
    )
    result.add_argument("--folds", type=int, default=5)
    result.add_argument("--fold-seed", type=int, default=20260730)
    result.add_argument(
        "--maximum-negative-pass-rate",
        type=float,
        default=0.20,
    )
    result.add_argument("--maximum-rules", type=int, default=2)
    result.add_argument(
        "--minimum-fold-detected-positives",
        type=int,
        default=1,
    )
    result.add_argument("--allowed-family", action="append")
    result.add_argument("--output", type=Path, required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
