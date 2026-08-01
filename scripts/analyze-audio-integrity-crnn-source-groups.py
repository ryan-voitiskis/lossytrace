#!/usr/bin/env python3
"""Summarize source-group shortcut behavior in a CRNN holdout report."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def write_atomic(path: Path, value: dict[str, Any]) -> None:
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


def group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    alerted = [row for row in rows if row["predicted_positive"]]
    negative_alerts = [
        row for row in alerted if row["expectation"] == "negative"
    ]
    positive_alerts = [
        row for row in alerted if row["expectation"] == "controlled_positive"
    ]
    return {
        "source_group": rows[0]["source_group"],
        "domain": rows[0]["domain"],
        "case_count": len(rows),
        "alert_count": len(alerted),
        "negative_alert_count": len(negative_alerts),
        "controlled_positive_alert_count": len(positive_alerts),
        "all_cases_alerted": len(alerted) == len(rows),
        "any_negative_alerted": bool(negative_alerts),
        "positive_only_alert": bool(alerted) and not negative_alerts,
        "minimum_score": min(row["score"] for row in rows),
        "maximum_score": max(row["score"] for row in rows),
    }


def analyze(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("heldout_opened") is not False:
        raise SystemExit("input is not an unopened development report")
    if report.get("public_verdict_enabled") is not False:
        raise SystemExit("input unexpectedly enables a public verdict")
    allowed_dispositions = {
        "failed_development_source_domain_gate",
        "failed_development_transfer_gate",
        "development_transfer_gate_passed_requires_independent_review",
    }
    if report.get("disposition") not in allowed_dispositions:
        raise SystemExit("input does not contain an allowed development disposition")
    rows = report.get("case_predictions")
    prediction_set = "case_predictions"
    if rows is None:
        transfer = report.get("transfer")
        if isinstance(transfer, dict):
            rows = transfer.get("case_predictions")
            prediction_set = "transfer.case_predictions"
    if not isinstance(rows, list) or not rows:
        raise SystemExit("input has no case predictions")
    required = {
        "case_id",
        "source_group",
        "domain",
        "expectation",
        "predicted_positive",
        "score",
    }
    case_ids: set[str] = set()
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict) or not required <= set(row):
            raise SystemExit("case prediction has an invalid shape")
        case_id = row["case_id"]
        if case_id in case_ids:
            raise SystemExit(f"duplicate case prediction: {case_id}")
        case_ids.add(case_id)
        if row["expectation"] not in {"negative", "controlled_positive"}:
            raise SystemExit(f"{case_id}: invalid expectation")
        if not isinstance(row["predicted_positive"], bool):
            raise SystemExit(f"{case_id}: prediction must be boolean")
        by_group[(row["domain"], row["source_group"])].append(row)

    groups = [
        group_summary(by_group[key])
        for key in sorted(by_group)
    ]
    domains = []
    for domain in sorted({group["domain"] for group in groups}):
        selected = [group for group in groups if group["domain"] == domain]
        domains.append(
            {
                "domain": domain,
                "source_group_count": len(selected),
                "any_alert_source_group_count": sum(
                    group["alert_count"] > 0 for group in selected
                ),
                "negative_alert_source_group_count": sum(
                    group["any_negative_alerted"] for group in selected
                ),
                "all_cases_alert_source_group_count": sum(
                    group["all_cases_alerted"] for group in selected
                ),
                "positive_only_alert_source_group_count": sum(
                    group["positive_only_alert"] for group in selected
                ),
            }
        )

    alerted_groups = [group for group in groups if group["alert_count"] > 0]
    negative_alert_groups = [
        group for group in groups if group["any_negative_alerted"]
    ]
    all_alert_groups = [group for group in groups if group["all_cases_alerted"]]
    positive_only_groups = [
        group for group in groups if group["positive_only_alert"]
    ]
    specificity_passed = not negative_alert_groups
    if specificity_passed:
        finding = (
            "No source group contains an alerted PCM negative. Alerts, if any, "
            "are confined to controlled-positive variants within each group."
        )
        disposition = "passed_source_group_specificity_check"
    else:
        finding = (
            "At least one alerted source group also alerts a PCM negative. The "
            "scores do not support a codec-history interpretation for those "
            "groups."
        )
        disposition = "failed_source_group_specificity_check"
    return {
        "schema_version": 1,
        "state": "development_research_only",
        "heldout_opened": False,
        "public_verdict_enabled": False,
        "input_disposition": report["disposition"],
        "input_prediction_set": prediction_set,
        "case_count": len(rows),
        "source_group_count": len(groups),
        "summary": {
            "any_alert_source_group_count": len(alerted_groups),
            "negative_alert_source_group_count": len(negative_alert_groups),
            "all_cases_alert_source_group_count": len(all_alert_groups),
            "positive_only_alert_source_group_count": len(positive_only_groups),
        },
        "domains": domains,
        "alerted_source_groups": alerted_groups,
        "finding": finding,
        "disposition": disposition,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite output: {args.output}")
    result = analyze(load_json(args.report))
    result["input"] = {
        "name": args.report.name,
        "sha256": sha256_file(args.report),
    }
    write_atomic(args.output, result)
    print(
        f"wrote {args.output}; disposition={result['disposition']} "
        f"negative-alert-groups="
        f"{result['summary']['negative_alert_source_group_count']}"
    )


if __name__ == "__main__":
    main()
