#!/usr/bin/env python3
"""Combine private frozen-policy evaluations without retuning their thresholds."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
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


def command(args: argparse.Namespace) -> int:
    if len(args.evaluation) < 2:
        raise SystemExit("at least two policy evaluations are required")
    reports = [load_json(path) for path in args.evaluation]
    rows_by_report = [
        {row["case_id"]: row for row in report.get("results", [])}
        for report in reports
    ]
    expected_ids = set(rows_by_report[0])
    if not expected_ids:
        raise SystemExit("policy evaluations contain no result rows")
    if any(set(rows) != expected_ids for rows in rows_by_report[1:]):
        raise SystemExit("policy evaluations contain different cases")

    rows = []
    for case_id in sorted(expected_ids):
        source_rows = [report_rows[case_id] for report_rows in rows_by_report]
        identity = {
            (
                row["source_group"],
                row["class"],
                row["expectation"],
            )
            for row in source_rows
        }
        if len(identity) != 1:
            raise SystemExit(f"{case_id}: case identity differs between reports")
        selected_by_policy = [row["selected"] for row in source_rows]
        selected = (
            all(selected_by_policy)
            if args.mode == "all"
            else any(selected_by_policy)
        )
        first = source_rows[0]
        rows.append(
            {
                "case_id": case_id,
                "source_group": first["source_group"],
                "class": first["class"],
                "expectation": first["expectation"],
                "selected_by_policy": selected_by_policy,
                "selected": selected,
            }
        )

    false_positives = [
        row
        for row in rows
        if row["selected"] and row["expectation"] == "negative"
    ]
    detected = [
        row
        for row in rows
        if row["selected"] and row["expectation"] == "controlled_positive"
    ]
    positive_classes = Counter(row["class"] for row in detected)
    total_classes = Counter(
        row["class"]
        for row in rows
        if row["expectation"] == "controlled_positive"
    )
    write_atomic(
        args.output,
        {
            "schema_version": 1,
            "disposition": {
                "state": "development_candidate",
                "combination_selected_after_observing_this_corpus": True,
                "held_out_source_groups": False,
                "public_verdict_enabled": False,
                "reason": (
                    "The constituent thresholds were frozen, but this "
                    "cross-policy combination rule was selected after the "
                    "settings-holdout results and needs a new untouched gate."
                ),
            },
            "mode": args.mode,
            "source_evaluations": [str(path) for path in args.evaluation],
            "policy_count": len(reports),
            "negative_count": sum(
                row["expectation"] == "negative" for row in rows
            ),
            "false_positive_count": len(false_positives),
            "false_positive_case_ids": sorted(
                row["case_id"] for row in false_positives
            ),
            "controlled_positive_count": sum(total_classes.values()),
            "detected_positive_count": len(detected),
            "detected_by_class": {
                class_name: {
                    "detected": positive_classes[class_name],
                    "total": total,
                }
                for class_name, total in sorted(total_classes.items())
            },
            "results": rows,
        },
    )
    print(f"wrote combined policy evaluation to {args.output}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--evaluation",
        type=Path,
        action="append",
        required=True,
    )
    result.add_argument("--mode", choices=("all", "any"), default="all")
    result.add_argument("--output", type=Path, required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
