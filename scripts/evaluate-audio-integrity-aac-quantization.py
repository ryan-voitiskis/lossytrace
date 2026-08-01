#!/usr/bin/env python3
"""Evaluate the research-only AAC quantization probe on sealed public corpora."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

REFERENCE_METHOD_ID = "derrien-aac-quantization-v1-research"
HIGH_PRECISION_METHOD_ID = (
    "derrien-aac-quantization-v2-high-precision-research"
)
SAMPLING_THRESHOLDS = {
    8: 0.031,
    16: 0.019,
    32: 0.0145,
    64: 0.0125,
}


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


def resolve_beneath(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise SystemExit(f"path escapes corpus root: {relative}") from error
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"audio is not a regular non-symlink file: {path}")
    return path


def write_atomic(path: Path, value: dict) -> None:
    path = path.expanduser().resolve()
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace report: {path}")
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


def validate_corpus(
    root: Path,
    *,
    external_transfer: bool = False,
) -> tuple[dict, list[dict], dict]:
    root = root.expanduser().resolve()
    if not root.is_dir() or root.is_symlink():
        raise SystemExit(f"invalid corpus root: {root}")
    manifest_path = root / "manifest.json"
    fingerprints_path = root / "fingerprints.json"
    seal_path = root / "seal.json"
    manifest = load_json(manifest_path)
    fingerprints = load_json(fingerprints_path)
    seal = load_json(seal_path)
    if external_transfer:
        if (
            seal.get("state") != "sealed_external_transfer_corpus"
            or seal.get("split") != "held_out"
            or seal.get("release_heldout_labels_present") is not False
            or seal.get("external_transfer_feature_scores_opened") is not False
            or seal.get("release_gate_eligible") is not False
        ):
            raise SystemExit(
                f"{root}: corpus is not a sealed external-transfer set"
            )
        expected_split = "held_out"
    else:
        if (
            seal.get("state") != "sealed_development_corpus"
            or seal.get("split") != "development"
            or seal.get("held_out_labels_present") is not False
        ):
            raise SystemExit(
                f"{root}: corpus is not sealed development-only data"
            )
        expected_split = "development"
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemExit(f"{manifest_path}: cases must be a non-empty list")
    expected = fingerprints.get("case_sha256")
    if not isinstance(expected, dict):
        raise SystemExit(f"{fingerprints_path}: missing case_sha256")
    case_ids = {case.get("case_id") for case in cases}
    if None in case_ids or len(case_ids) != len(cases):
        raise SystemExit(f"{manifest_path}: duplicate or missing case IDs")
    if set(expected) != case_ids:
        raise SystemExit(f"{root}: fingerprints and manifest case IDs differ")
    for case in cases:
        if (
            case.get("split") != expected_split
            or case.get("expectation")
            not in {"negative", "controlled_positive"}
        ):
            raise SystemExit(
                f"{case.get('case_id')}: unsupported split or expectation"
            )
        audio = resolve_beneath(root, case["relative_path"])
        if sha256_file(audio) != expected[case["case_id"]]:
            raise SystemExit(
                f"{case['case_id']}: current audio fingerprint differs"
            )
    commitment = {
        "root": str(root),
        "corpus_id": manifest.get("corpus_id"),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "fingerprints_path": str(fingerprints_path),
        "fingerprints_sha256": sha256_file(fingerprints_path),
        "seal_path": str(seal_path),
        "seal_sha256": sha256_file(seal_path),
        "case_count": len(cases),
        "analysis_max_seconds": manifest["analysis_max_seconds"],
        "evaluation_kind": (
            "external_transfer"
            if external_transfer
            else "development"
        ),
    }
    return commitment, cases, expected


def filter_cases(
    cases: list[dict],
    *,
    classes: set[str],
    source_groups: set[str],
) -> list[dict]:
    selected = [
        case
        for case in cases
        if (not classes or case["class"] in classes)
        and (
            not source_groups
            or case["source_group"] in source_groups
        )
    ]
    return sorted(selected, key=lambda case: case["case_id"])


def confusion(rows: list[dict], threshold: float) -> dict:
    supported = [row for row in rows if row["state"] == "scored"]
    true_positives = sum(
        row["expectation"] == "controlled_positive"
        and row["aac_quantization_probability"] > threshold
        for row in supported
    )
    false_negatives = sum(
        row["expectation"] == "controlled_positive"
        and row["aac_quantization_probability"] <= threshold
        for row in supported
    )
    false_positives = sum(
        row["expectation"] == "negative"
        and row["aac_quantization_probability"] > threshold
        for row in supported
    )
    true_negatives = sum(
        row["expectation"] == "negative"
        and row["aac_quantization_probability"] <= threshold
        for row in supported
    )
    positive_count = true_positives + false_negatives
    negative_count = false_positives + true_negatives
    return {
        "threshold_exclusive": threshold,
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


def summarize(
    rows: list[dict],
    fixed_reference_threshold: float = SAMPLING_THRESHOLDS[8],
) -> dict:
    scored = [row for row in rows if row["state"] == "scored"]
    negatives = [
        row["aac_quantization_probability"]
        for row in scored
        if row["expectation"] == "negative"
    ]
    strict_boundary = max(negatives) if negatives else None
    by_class: dict[str, dict] = defaultdict(
        lambda: {
            "case_count": 0,
            "scored_count": 0,
            "unsupported_count": 0,
            "fixed_alert_count": 0,
        }
    )
    for row in rows:
        summary = by_class[row["class"]]
        summary["case_count"] += 1
        if row["state"] == "scored":
            summary["scored_count"] += 1
            summary["fixed_alert_count"] += int(
                row["aac_quantization_probability"]
                > fixed_reference_threshold
            )
        else:
            summary["unsupported_count"] += 1
    return {
        "case_count": len(rows),
        "scored_count": len(scored),
        "unsupported_count": len(rows) - len(scored),
        "fixed_reference": confusion(
            rows,
            fixed_reference_threshold,
        ),
        "strict_zero_observed_false_positive": (
            confusion(rows, strict_boundary)
            if strict_boundary is not None
            else None
        ),
        "by_class": dict(sorted(by_class.items())),
    }


def run_probe(
    runner: Path,
    *,
    case: dict,
    audio: Path,
    maximum_seconds: float,
    timeout_seconds: float,
    sampling_count: int,
) -> dict:
    process = subprocess.run(
        [
            str(runner),
            case["case_id"],
            str(audio),
            str(maximum_seconds),
            str(sampling_count),
            str(sampling_count),
        ],
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if process.returncode != 0:
        diagnostic = process.stderr.strip()
        if "unsupported AAC reference sample rate" in diagnostic:
            return {
                "state": "unsupported_sample_rate",
                "diagnostic": diagnostic.removeprefix("error: "),
            }
        raise SystemExit(
            f"{case['case_id']}: runner failed ({process.returncode}): "
            f"{diagnostic[:500]}"
        )
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise SystemExit(
            f"{case['case_id']}: runner output is not JSON"
        ) from error
    expected_method_id = (
        REFERENCE_METHOD_ID
        if sampling_count == 8
        else HIGH_PRECISION_METHOD_ID
    )
    fixed_reference_threshold = SAMPLING_THRESHOLDS[
        sampling_count
    ]
    if (
        result.get("schema_version") != 1
        or result.get("method_id") != expected_method_id
        or result.get("research_only") is not True
        or result.get("case_id") != case["case_id"]
        or result.get("audio_sha256") != sha256_file(audio)
        or result.get("fixed_reference_threshold")
        != fixed_reference_threshold
        or result.get("analyzed_audio_window_count")
        != sampling_count
        or result.get("scale_factor_hypothesis_count")
        != sampling_count
    ):
        raise SystemExit(f"{case['case_id']}: runner contract differs")
    probability = result.get("aac_quantization_probability")
    if (
        not isinstance(probability, (int, float))
        or not 0.0 <= probability <= 1.0
    ):
        raise SystemExit(f"{case['case_id']}: invalid probability")
    return {"state": "scored", **result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument(
        "--corpus-root",
        type=Path,
        action="append",
        required=True,
    )
    parser.add_argument("--include-class", action="append", default=[])
    parser.add_argument(
        "--include-source-group",
        action="append",
        default=[],
    )
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument(
        "--sampling-count",
        type=int,
        choices=sorted(SAMPLING_THRESHOLDS),
        default=8,
    )
    parser.add_argument(
        "--external-transfer-freeze",
        type=Path,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    runner = args.runner.expanduser().resolve()
    if not runner.is_file() or runner.is_symlink():
        raise SystemExit(f"runner is not a regular non-symlink file: {runner}")
    if args.timeout_seconds <= 0:
        raise SystemExit("timeout-seconds must be positive")
    external_transfer = args.external_transfer_freeze is not None
    freeze_commitment = None
    if external_transfer:
        freeze = load_json(args.external_transfer_freeze)
        if (
            freeze.get("state")
            != "frozen_before_external_transfer"
            or freeze.get("candidate_id")
            != "aac-16x16-sample-rate-normalized-support-two-family-v2"
            or freeze.get("release_heldout_opened") is not False
        ):
            raise SystemExit("external-transfer freeze contract differs")
        freeze_commitment = {
            "path": str(args.external_transfer_freeze.resolve()),
            "sha256": sha256_file(args.external_transfer_freeze),
        }

    classes = set(args.include_class)
    source_groups = set(args.include_source_group)
    commitments = []
    selected_cases = []
    for root_argument in args.corpus_root:
        root = root_argument.expanduser().resolve()
        commitment, cases, _fingerprints = validate_corpus(
            root,
            external_transfer=external_transfer,
        )
        commitments.append(commitment)
        for case in filter_cases(
            cases,
            classes=classes,
            source_groups=source_groups,
        ):
            selected_cases.append(
                (
                    root,
                    commitment["analysis_max_seconds"],
                    case,
                )
            )
    selected_cases.sort(key=lambda item: item[2]["case_id"])
    if not selected_cases:
        raise SystemExit("filters selected no cases")
    case_ids = [item[2]["case_id"] for item in selected_cases]
    if len(set(case_ids)) != len(case_ids):
        raise SystemExit("selected corpora contain duplicate case IDs")

    rows = []
    for index, (root, maximum_seconds, case) in enumerate(
        selected_cases,
        1,
    ):
        print(
            f"[{index:03}/{len(selected_cases)}] {case['case_id']}",
            flush=True,
        )
        audio = resolve_beneath(root, case["relative_path"])
        probe = run_probe(
            runner,
            case=case,
            audio=audio,
            maximum_seconds=maximum_seconds,
            timeout_seconds=args.timeout_seconds,
            sampling_count=args.sampling_count,
        )
        rows.append(
            {
                "case_id": case["case_id"],
                "class": case["class"],
                "expectation": case["expectation"],
                "source_group": case["source_group"],
                "partition_group": case.get(
                    "partition_group",
                    case["source_group"],
                ),
                "provenance_tier": case.get("provenance_tier"),
                **probe,
            }
        )

    method_id = (
        REFERENCE_METHOD_ID
        if args.sampling_count == 8
        else HIGH_PRECISION_METHOD_ID
    )
    fixed_reference_threshold = SAMPLING_THRESHOLDS[
        args.sampling_count
    ]
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": (
            "untouched_external_transfer_after_candidate_freeze"
            if external_transfer
            else "development_research_only"
        ),
        "method_id": method_id,
        "sampling": {
            "audio_window_count": args.sampling_count,
            "scale_factor_hypothesis_count": args.sampling_count,
            "published_threshold_exclusive": (
                fixed_reference_threshold
            ),
        },
        "public_verdict_enabled": False,
        "heldout_opened": False,
        "release_heldout_opened": False,
        "external_transfer_opened": external_transfer,
        "external_transfer_freeze": freeze_commitment,
        "evaluator": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "runner": {
            "path": str(runner),
            "sha256": sha256_file(runner),
        },
        "input_commitments": commitments,
        "filters": {
            "classes": sorted(classes),
            "source_groups": sorted(source_groups),
        },
        "summary": summarize(rows, fixed_reference_threshold),
        "cases": rows,
    }
    write_atomic(args.output, report)
    summary = report["summary"]
    fixed = summary["fixed_reference"]
    strict = summary["strict_zero_observed_false_positive"]
    print(
        f"wrote {len(rows)} cases to {args.output}; "
        f"fixed FP={fixed['false_positives']}/{fixed['negative_count']} "
        f"TP={fixed['true_positives']}/{fixed['positive_count']}; "
        f"strict TP={strict['true_positives']}/{strict['positive_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
