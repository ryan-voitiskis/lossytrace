#!/usr/bin/env python3
"""Compose and verify the retained 104-case Cannam pilot replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import tempfile
from collections import Counter
from pathlib import Path


EXPECTED_REVISION = "7a70bd8d15e68b0b1942a9d3deac6ad4d8293b8b"
EXPECTED_SDK_REVISION = "44c2487763eb248a933e9eff9169cfadee375009"
EXPECTED_PLUGIN_KEY = "vamp-lossy-encoding-detector:lossydetector:cf"
EXPECTED_HISTORICAL_CASES = 112
EXPECTED_RETAINED_CASES = 104
EXPECTED_MISSING_CASES = 8
EXPECTED_MISSING_CLASS = "sharp_lowpass_only_pcm"
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_KEYS = {
    "audio_sha256",
    "case_id",
    "partition_group",
    "relative_path",
    "source_group",
}


def load_object(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_new(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"refusing to replace output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(
            value,
            output,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def detector_identity(report: dict, *, require_schema_two: bool) -> dict:
    expected_schema = 2 if require_schema_two else 1
    if report.get("schema_version") != expected_schema:
        raise ValueError(f"detector report schema must be {expected_schema}")
    detector = report.get("detector")
    if not isinstance(detector, dict) or (
        detector.get("revision") != EXPECTED_REVISION
        or detector.get("plugin_key") != EXPECTED_PLUGIN_KEY
    ):
        raise ValueError("detector report identity differs")
    host_hash = detector.get("host_sha256")
    if not isinstance(host_hash, str) or not HEX_SHA256.fullmatch(host_hash):
        raise ValueError("detector report host hash is invalid")
    if require_schema_two and (
        detector.get("plugin_sdk_revision") != EXPECTED_SDK_REVISION
        or not isinstance(detector.get("plugin_binary_sha256"), str)
        or not HEX_SHA256.fullmatch(detector["plugin_binary_sha256"])
        or detector.get("source_tracked_clean") is not True
        or detector.get("plugin_sdk_tracked_clean") is not True
    ):
        raise ValueError("detector replay build provenance differs")
    return detector


def indexed_rows(report: dict) -> dict[str, dict]:
    values = report.get("results")
    if not isinstance(values, list):
        raise ValueError("detector results must be an array")
    output = {}
    for index, value in enumerate(values, 1):
        if not isinstance(value, dict):
            raise ValueError(f"detector result {index} must be an object")
        case_id = value.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in output:
            raise ValueError("detector case IDs are missing or duplicated")
        output[case_id] = value
    return output


def compose_manifest(full_manifest: dict, historical_report: dict) -> dict:
    if (
        full_manifest.get("schema_version") != 1
        or full_manifest.get("evidence_partition") != "observed_development"
        or full_manifest.get("holdout_scores_opened") is not False
    ):
        raise ValueError("full manifest evidence boundary differs")
    detector_identity(historical_report, require_schema_two=False)
    historical_rows = indexed_rows(historical_report)
    if len(historical_rows) != EXPECTED_HISTORICAL_CASES:
        raise ValueError("historical pilot case count differs")
    full_cases = full_manifest.get("cases")
    if not isinstance(full_cases, list):
        raise ValueError("full manifest cases must be an array")
    indexed_cases = {
        case.get("case_id"): case for case in full_cases if isinstance(case, dict)
    }
    if len(indexed_cases) != len(full_cases):
        raise ValueError("full manifest case IDs are missing or duplicated")
    shared_ids = historical_rows.keys() & indexed_cases.keys()
    missing_ids = historical_rows.keys() - indexed_cases.keys()
    if (
        len(shared_ids) != EXPECTED_RETAINED_CASES
        or len(missing_ids) != EXPECTED_MISSING_CASES
    ):
        raise ValueError("retained pilot overlap differs")
    missing_classes = Counter(historical_rows[case_id].get("class") for case_id in missing_ids)
    if missing_classes != {EXPECTED_MISSING_CLASS: EXPECTED_MISSING_CASES}:
        raise ValueError("missing pilot class inventory differs")
    selected = [indexed_cases[case_id] for case_id in sorted(shared_ids)]
    if len({case["source_group"] for case in selected}) != 8:
        raise ValueError("retained pilot source-group count differs")
    return {
        "schema_version": 1,
        "corpus_id": "audio-integrity-cannam-retained-pilot-replay-20260802-001",
        "corpus_version": 1,
        "evidence_partition": "observed_development",
        "holdout_scores_opened": False,
        "analysis_max_seconds": 0,
        "repetitions": 1,
        "source_manifest_sha256": None,
        "historical_report_sha256": None,
        "historical_case_count": EXPECTED_HISTORICAL_CASES,
        "retained_case_count": EXPECTED_RETAINED_CASES,
        "unretained_case_count": EXPECTED_MISSING_CASES,
        "unretained_class_counts": {
            EXPECTED_MISSING_CLASS: EXPECTED_MISSING_CASES
        },
        "cases": selected,
    }


def quantile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = proportion * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def delta_summary(values: list[float]) -> dict:
    return {
        "count": len(values),
        "mean": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "p95": quantile(values, 0.95),
        "maximum": max(values) if values else None,
    }


def valid_score(row: dict) -> float:
    value = row.get("positive_window_fraction")
    if (
        not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0.0 <= value <= 1.0
        or not isinstance(row.get("detector_binary_label"), bool)
        or row["detector_binary_label"] != (value >= 0.25)
        or not isinstance(row.get("window_count"), int)
        or row["window_count"] <= 0
    ):
        raise ValueError("pilot row score or fixed decision is invalid")
    return float(value)


def compare(
    manifest: dict,
    historical_report: dict,
    replay_report: dict,
    input_hashes: dict,
) -> dict:
    if (
        manifest.get("evidence_partition") != "observed_development"
        or manifest.get("holdout_scores_opened") is not False
        or manifest.get("retained_case_count") != EXPECTED_RETAINED_CASES
        or manifest.get("unretained_class_counts")
        != {EXPECTED_MISSING_CLASS: EXPECTED_MISSING_CASES}
    ):
        raise ValueError("pilot replay manifest boundary differs")
    historical_detector = detector_identity(
        historical_report, require_schema_two=False
    )
    replay_detector = detector_identity(replay_report, require_schema_two=True)
    if (
        replay_report.get("evidence_partition") != "observed_development"
        or replay_report.get("holdout_scores_opened") is not False
        or replay_report.get("thresholds_retuned") is not False
        or replay_report.get("manifest_sha256") != input_hashes["manifest_sha256"]
    ):
        raise ValueError("pilot replay report boundary differs")
    decision = replay_report.get("decision_rule")
    if not isinstance(decision, dict) or (
        decision.get("window_threshold") != 0.5
        or decision.get("file_positive_fraction_threshold") != 0.25
    ):
        raise ValueError("pilot replay fixed decision rule differs")
    historical = indexed_rows(historical_report)
    replay = indexed_rows(replay_report)
    manifest_ids = {
        case.get("case_id")
        for case in manifest.get("cases", [])
        if isinstance(case, dict)
    }
    if len(manifest_ids) != EXPECTED_RETAINED_CASES or replay.keys() != manifest_ids:
        raise ValueError("pilot replay case inventory differs")
    if not manifest_ids <= historical.keys():
        raise ValueError("pilot replay contains a non-historical case")

    decision_mismatches = 0
    window_count_mismatches = 0
    absolute_score_deltas = []
    by_expectation = {}
    for expectation in ("negative", "controlled_positive"):
        ids = sorted(
            case_id
            for case_id in manifest_ids
            if historical[case_id].get("expectation") == expectation
        )
        historical_alerts = 0
        replay_alerts = 0
        for case_id in ids:
            before = historical[case_id]
            after = replay[case_id]
            for field in (
                "source_group",
                "class",
                "expectation",
                "provenance_tier",
            ):
                if before.get(field) != after.get(field):
                    raise ValueError(f"pilot replay metadata differs on {field}")
            before_score = valid_score(before)
            after_score = valid_score(after)
            absolute_score_deltas.append(abs(after_score - before_score))
            historical_alerts += before["detector_binary_label"]
            replay_alerts += after["detector_binary_label"]
            decision_mismatches += (
                before["detector_binary_label"] != after["detector_binary_label"]
            )
            window_count_mismatches += before["window_count"] != after["window_count"]
        by_expectation[expectation] = {
            "case_count": len(ids),
            "historical_positive_decisions": historical_alerts,
            "replay_positive_decisions": replay_alerts,
        }

    value = {
        "schema_version": 1,
        "state": "cannam_retained_pilot_replay_verification_v1",
        "independent_validation": False,
        "holdout_scores_opened": False,
        "thresholds_retuned": False,
        "public_verdict_enabled": False,
        "inputs": input_hashes,
        "detector": {
            "revision": EXPECTED_REVISION,
            "plugin_key": EXPECTED_PLUGIN_KEY,
            "historical_host_sha256": historical_detector["host_sha256"],
            "replay_host_sha256": replay_detector["host_sha256"],
            "replay_plugin_binary_sha256": replay_detector[
                "plugin_binary_sha256"
            ],
        },
        "inventory": {
            "historical_case_count": EXPECTED_HISTORICAL_CASES,
            "retained_replay_case_count": EXPECTED_RETAINED_CASES,
            "unretained_case_count": EXPECTED_MISSING_CASES,
            "unretained_class_counts": {
                EXPECTED_MISSING_CLASS: EXPECTED_MISSING_CASES
            },
        },
        "comparison": {
            "fixed_decision_mismatch_count": decision_mismatches,
            "window_count_mismatch_count": window_count_mismatches,
            "positive_window_fraction_absolute_delta": delta_summary(
                absolute_score_deltas
            ),
            "by_expectation": by_expectation,
        },
        "regression_passed": decision_mismatches == 0,
        "limitation": (
            "This is a decision regression on 104 retained lossless-wrapper "
            "equivalents using a newly bound host/plugin build, not an exact "
            "112-file binary replay. Eight historical private-source sharp-"
            "low-pass inputs were not retained."
        ),
    }
    assert_path_free(value)
    return value


def assert_path_free(value: object, key: str | None = None) -> None:
    if key in FORBIDDEN_KEYS:
        raise ValueError(f"aggregate contains private key: {key}")
    if isinstance(value, dict):
        for child_key, child in value.items():
            assert_path_free(child, child_key)
    elif isinstance(value, list):
        for child in value:
            assert_path_free(child, key)
    elif isinstance(value, str) and (
        value.startswith("/") or value.startswith("file:")
    ):
        raise ValueError("aggregate contains an absolute path")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    compose = subparsers.add_parser("compose")
    compose.add_argument("--full-manifest", type=Path, required=True)
    compose.add_argument("--historical-report", type=Path, required=True)
    compose.add_argument("--output", type=Path, required=True)
    verify = subparsers.add_parser("compare")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--historical-report", type=Path, required=True)
    verify.add_argument("--replay-report", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "compose":
            full_manifest = args.full_manifest.expanduser().resolve()
            historical_report = args.historical_report.expanduser().resolve()
            value = compose_manifest(
                load_object(full_manifest), load_object(historical_report)
            )
            value["source_manifest_sha256"] = sha256_file(full_manifest)
            value["historical_report_sha256"] = sha256_file(historical_report)
        else:
            manifest = args.manifest.expanduser().resolve()
            historical_report = args.historical_report.expanduser().resolve()
            replay_report = args.replay_report.expanduser().resolve()
            value = compare(
                load_object(manifest),
                load_object(historical_report),
                load_object(replay_report),
                {
                    "manifest_sha256": sha256_file(manifest),
                    "historical_report_sha256": sha256_file(historical_report),
                    "replay_report_sha256": sha256_file(replay_report),
                    "verifier_sha256": sha256_file(Path(__file__).resolve()),
                },
            )
        write_new(args.output.expanduser().resolve(), value)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    if args.command == "compare" and not value["regression_passed"]:
        raise SystemExit("pilot replay fixed decisions differ; stop before P1")
    print(
        f"{args.command} complete: {value.get('retained_case_count', value.get('inventory', {}).get('retained_replay_case_count'))} retained cases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
