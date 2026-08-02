#!/usr/bin/env python3
"""Create a path-free, fixed-rule failure atlas for the Cannam detector."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import tempfile
from collections import defaultdict
from pathlib import Path


EXPECTED_REVISION = "7a70bd8d15e68b0b1942a9d3deac6ad4d8293b8b"
EXPECTED_SDK_REVISION = "44c2487763eb248a933e9eff9169cfadee375009"
EXPECTED_PLUGIN_KEY = "vamp-lossy-encoding-detector:lossydetector:cf"
EXPECTED_MANIFEST_SHA256 = (
    "e19b5b408fedf348fa9b6499d5cdd1b6b734d84b19b895d5b0a528f0c4423b7a"
)
EXPECTED_P1 = {
    "case_count": 5_280,
    "source_group_count": 597,
    "negative_case_count": 1_734,
    "controlled_positive_case_count": 3_546,
}
EXPECTED_P2 = {
    "case_count": 2_261,
    "negative_case_count": 1_734,
    "controlled_positive_case_count": 527,
}
MP3_128_EXACT_CLASS = "mp3_128"
MP3_128_CLASS_SUFFIX = "_mp3_128_to_flac16"
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
TWO_SIDED_95_Z = 1.959963984540054
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


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def quantile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = proportion * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def wilson_bounds(
    successes: int, trials: int, z: float = TWO_SIDED_95_Z
) -> tuple[float | None, float | None]:
    if trials == 0:
        return None, None
    proportion = successes / trials
    z_squared = z * z
    denominator = 1.0 + z_squared / trials
    center = (proportion + z_squared / (2.0 * trials)) / denominator
    spread = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / trials
            + z_squared / (4.0 * trials * trials)
        )
        / denominator
    )
    return max(0.0, center - spread), min(1.0, center + spread)


def binomial_summary(successes: int, trials: int) -> dict:
    lower, upper = wilson_bounds(successes, trials)
    return {
        "successes": successes,
        "trials": trials,
        "rate": ratio(successes, trials),
        "two_sided_95_wilson_lower": lower,
        "two_sided_95_wilson_upper": upper,
    }


def score_summary(rows: list[dict]) -> dict:
    values = [row["score"] for row in rows]
    return {
        "count": len(values),
        "mean": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "p05": quantile(values, 0.05),
        "p90": quantile(values, 0.90),
        "p95": quantile(values, 0.95),
        "minimum": min(values) if values else None,
        "maximum": max(values) if values else None,
    }


def mp3_128_positive(row: dict) -> bool:
    class_name = row.get("class")
    return (
        row.get("expectation") == "controlled_positive"
        and isinstance(class_name, str)
        and (
            class_name == MP3_128_EXACT_CLASS
            or class_name.endswith(MP3_128_CLASS_SUFFIX)
        )
    )


def binary_metrics(rows: list[dict]) -> dict:
    true_positive = sum(
        row["expectation"] == "controlled_positive" and row["predicted"]
        for row in rows
    )
    false_negative = sum(
        row["expectation"] == "controlled_positive" and not row["predicted"]
        for row in rows
    )
    true_negative = sum(
        row["expectation"] == "negative" and not row["predicted"] for row in rows
    )
    false_positive = sum(
        row["expectation"] == "negative" and row["predicted"] for row in rows
    )
    positive = true_positive + false_negative
    negative = true_negative + false_positive
    predicted_positive = true_positive + false_positive
    recall = binomial_summary(true_positive, positive)
    specificity = binomial_summary(true_negative, negative)
    false_positive_rate = binomial_summary(false_positive, negative)
    precision = binomial_summary(true_positive, predicted_positive)
    accuracy = binomial_summary(true_positive + true_negative, len(rows))
    recall_rate = recall["rate"]
    specificity_rate = specificity["rate"]
    precision_rate = precision["rate"]
    f1 = (
        2.0 * precision_rate * recall_rate / (precision_rate + recall_rate)
        if precision_rate is not None
        and recall_rate is not None
        and precision_rate + recall_rate > 0
        else None
    )
    return {
        "confusion": {
            "true_positive": true_positive,
            "false_negative": false_negative,
            "true_negative": true_negative,
            "false_positive": false_positive,
        },
        "recall": recall,
        "specificity": specificity,
        "false_positive_rate": false_positive_rate,
        "precision_selected_population": precision,
        "accuracy_selected_population": accuracy,
        "balanced_accuracy": (
            (recall_rate + specificity_rate) / 2.0
            if recall_rate is not None and specificity_rate is not None
            else None
        ),
        "f1_selected_population": f1,
    }


def negative_group_summary(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["expectation"] == "negative":
            grouped[row["source_group"]].append(row)
    alerts = sum(any(row["predicted"] for row in values) for values in grouped.values())
    return {
        "definition": "group alerts when any negative case is positive",
        "alerts": binomial_summary(alerts, len(grouped)),
    }


def positive_group_summary(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["expectation"] == "controlled_positive":
            grouped[row["source_group"]].append(row)
    detected = sum(any(row["predicted"] for row in values) for values in grouped.values())
    return {
        "definition": "group detected when any controlled-positive variant is positive",
        "detected": binomial_summary(detected, len(grouped)),
    }


def expectation_slice(rows: list[dict]) -> dict:
    expectation = rows[0]["expectation"] if rows else None
    predicted = sum(row["predicted"] for row in rows)
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["source_group"]].append(row)
    group_predicted = sum(
        any(row["predicted"] for row in values) for values in groups.values()
    )
    key = "alerts" if expectation == "negative" else "detected"
    return {
        "expectation": expectation,
        "case_count": len(rows),
        "source_group_count": len(groups),
        f"case_{key}": binomial_summary(predicted, len(rows)),
        f"source_group_{key}": binomial_summary(group_predicted, len(groups)),
        "positive_window_fraction": score_summary(rows),
    }


def slices(rows: list[dict], field: str) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        value = row.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"missing public slice field {field}")
        grouped[value].append(row)
    output = {}
    for name, values in sorted(grouped.items()):
        expectations = {row["expectation"] for row in values}
        if len(expectations) == 1:
            output[name] = expectation_slice(values)
        else:
            output[name] = {
                "case_count": len(values),
                "source_group_count": len(
                    {row["source_group"] for row in values}
                ),
                "binary_metrics": binary_metrics(values),
                "negative_groups": negative_group_summary(values),
                "controlled_positive_groups": positive_group_summary(values),
                "by_expectation": {
                    expectation: expectation_slice(
                        [row for row in values if row["expectation"] == expectation]
                    )
                    for expectation in sorted(expectations)
                },
            }
    return output


def calibration_diagnostic(rows: list[dict], bin_count: int = 10) -> dict:
    brier = statistics.fmean(
        (row["score"] - (1.0 if row["expectation"] == "controlled_positive" else 0.0))
        ** 2
        for row in rows
    )
    bins = []
    weighted_gap = 0.0
    for index in range(bin_count):
        lower = index / bin_count
        upper = (index + 1) / bin_count
        values = [
            row
            for row in rows
            if lower <= row["score"] <= upper
            and (index == bin_count - 1 or row["score"] < upper)
        ]
        if not values:
            bins.append(
                {
                    "lower_inclusive": lower,
                    "upper_inclusive_only_for_last_bin": upper,
                    "count": 0,
                    "mean_score": None,
                    "empirical_positive_rate": None,
                }
            )
            continue
        mean_score = statistics.fmean(row["score"] for row in values)
        empirical = statistics.fmean(
            row["expectation"] == "controlled_positive" for row in values
        )
        weighted_gap += len(values) / len(rows) * abs(mean_score - empirical)
        bins.append(
            {
                "lower_inclusive": lower,
                "upper_inclusive_only_for_last_bin": upper,
                "count": len(values),
                "mean_score": mean_score,
                "empirical_positive_rate": empirical,
            }
        )
    return {
        "score_is_probability": False,
        "population_transport_calibration_established": False,
        "brier_score_selected_population": brier,
        "expected_calibration_error_selected_population": weighted_gap,
        "reliability_bins": bins,
    }


def population_summary(rows: list[dict]) -> dict:
    return {
        "inventory": {
            "case_count": len(rows),
            "source_group_count": len({row["source_group"] for row in rows}),
            "negative_case_count": sum(
                row["expectation"] == "negative" for row in rows
            ),
            "controlled_positive_case_count": sum(
                row["expectation"] == "controlled_positive" for row in rows
            ),
        },
        "case_level": binary_metrics(rows),
        "negative_source_groups": negative_group_summary(rows),
        "controlled_positive_source_groups": positive_group_summary(rows),
        "score_by_expectation": {
            expectation: score_summary(
                [row for row in rows if row["expectation"] == expectation]
            )
            for expectation in ("negative", "controlled_positive")
        },
        "by_source_domain": slices(rows, "source_domain"),
        "by_class": slices(rows, "class"),
        "calibration_diagnostic": calibration_diagnostic(rows),
    }


def validate_and_join(
    manifest: dict, report: dict, *, strict_inventory: bool
) -> tuple[list[dict], dict]:
    if (
        manifest.get("schema_version") != 1
        or manifest.get("evidence_partition") != "observed_development"
        or manifest.get("holdout_scores_opened") is not False
    ):
        raise ValueError("manifest is not the consumed observed-development population")
    if report.get("schema_version") != 2:
        raise ValueError("detector report schema_version must be 2")
    if (
        report.get("evidence_partition") != "observed_development"
        or report.get("holdout_scores_opened") is not False
        or report.get("thresholds_retuned") is not False
    ):
        raise ValueError("detector report evidence boundary differs")
    decision = report.get("decision_rule")
    if not isinstance(decision, dict) or (
        decision.get("window_threshold") != 0.5
        or decision.get("file_positive_fraction_threshold") != 0.25
    ):
        raise ValueError("detector report decision rule differs")
    detector = report.get("detector")
    if not isinstance(detector, dict) or (
        detector.get("revision") != EXPECTED_REVISION
        or detector.get("plugin_sdk_revision") != EXPECTED_SDK_REVISION
        or detector.get("plugin_key") != EXPECTED_PLUGIN_KEY
    ):
        raise ValueError("detector identity differs from the frozen baseline")
    for field in ("host_sha256", "plugin_binary_sha256"):
        if not isinstance(detector.get(field), str) or not HEX_SHA256.fullmatch(
            detector[field]
        ):
            raise ValueError(f"detector {field} is invalid")
    if (
        not isinstance(detector.get("host_version"), str)
        or not detector["host_version"]
        or detector.get("source_tracked_clean") is not True
        or detector.get("plugin_sdk_tracked_clean") is not True
    ):
        raise ValueError("detector build provenance differs")

    manifest_cases = manifest.get("cases")
    report_results = report.get("results")
    if not isinstance(manifest_cases, list) or not isinstance(report_results, list):
        raise ValueError("manifest cases and detector results must be arrays")
    metadata = {
        case.get("case_id"): case for case in manifest_cases if isinstance(case, dict)
    }
    results = {
        row.get("case_id"): row for row in report_results if isinstance(row, dict)
    }
    if (
        len(metadata) != len(manifest_cases)
        or len(results) != len(report_results)
        or metadata.keys() != results.keys()
        or any(not isinstance(case_id, str) or not case_id for case_id in metadata)
    ):
        raise ValueError("manifest and report case inventories differ")

    rows = []
    audio_inventory = []
    for case_id in sorted(metadata):
        case = metadata[case_id]
        result = results[case_id]
        for field in (
            "source_group",
            "source_domain",
            "class",
            "expectation",
            "provenance_tier",
        ):
            if result.get(field) != case.get(field):
                raise ValueError(f"{case_id}: detector metadata differs on {field}")
        audio_sha256 = result.get("audio_sha256")
        if not isinstance(audio_sha256, str) or not HEX_SHA256.fullmatch(audio_sha256):
            raise ValueError(f"{case_id}: audio_sha256 is invalid")
        window_count = result.get("window_count")
        score = result.get("positive_window_fraction")
        predicted = result.get("detector_binary_label")
        if (
            not isinstance(window_count, int)
            or window_count <= 0
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or not 0.0 <= score <= 1.0
            or not isinstance(predicted, bool)
            or predicted != (score >= 0.25)
        ):
            raise ValueError(f"{case_id}: fixed detector result is invalid")
        rows.append(
            {
                "source_group": case["source_group"],
                "source_domain": case["source_domain"],
                "class": case["class"],
                "expectation": case["expectation"],
                "provenance_tier": case["provenance_tier"],
                "score": float(score),
                "predicted": predicted,
            }
        )
        audio_inventory.append((case_id, audio_sha256))

    p1_inventory = population_summary(rows)["inventory"]
    p2 = [
        row
        for row in rows
        if row["expectation"] == "negative" or mp3_128_positive(row)
    ]
    p2_inventory = population_summary(p2)["inventory"]
    if strict_inventory:
        if p1_inventory != EXPECTED_P1:
            raise ValueError(f"P1 inventory differs: {p1_inventory}")
        for field, expected in EXPECTED_P2.items():
            if p2_inventory.get(field) != expected:
                raise ValueError(f"P2 inventory differs on {field}")

    inventory_payload = json.dumps(
        audio_inventory, ensure_ascii=False, separators=(",", ":")
    ).encode()
    return rows, {
        "audio_inventory_sha256": hashlib.sha256(inventory_payload).hexdigest(),
        "p2_rows": p2,
    }


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


def analyze(
    manifest: dict,
    report: dict,
    input_hashes: dict,
    *,
    strict_inventory: bool = True,
) -> dict:
    rows, validated = validate_and_join(
        manifest, report, strict_inventory=strict_inventory
    )
    p2_rows = validated.pop("p2_rows")
    detector = report["detector"]
    value = {
        "schema_version": 1,
        "state": "cannam_fixed_rule_failure_atlas_v1",
        "feature_version": 0,
        "evidence_partition": "observed_development",
        "independent_validation": False,
        "holdout_scores_opened": False,
        "thresholds_retuned": False,
        "public_verdict_enabled": False,
        "warning": (
            "Consumed development evidence only. Positive-window fraction is "
            "not a probability and no result authorizes a codec-history, "
            "authenticity, or provenance verdict."
        ),
        "detector": {
            "name": detector.get("name"),
            "repository": detector.get("repository"),
            "revision": detector["revision"],
            "plugin_sdk_revision": detector["plugin_sdk_revision"],
            "plugin_key": detector["plugin_key"],
            "host_sha256": detector["host_sha256"],
            "host_version": detector["host_version"],
            "plugin_binary_sha256": detector["plugin_binary_sha256"],
            "source_tracked_clean": True,
            "plugin_sdk_tracked_clean": True,
            "decision_rule": report["decision_rule"],
        },
        "inputs": {**input_hashes, **validated},
        "populations": {
            "p1_general_consumed": population_summary(rows),
            "p2_mp3_128_comparison": population_summary(p2_rows),
        },
        "interpretation": {
            "candidate_selection_authorized": False,
            "threshold_change_authorized": False,
            "support_filter_from_failures_authorized": False,
            "next_use": (
                "Preserve baseline failure classes in the factorial benchmark; "
                "do not tune or derive a detector from this replay."
            ),
        },
    }
    assert_path_free(value)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.expanduser().resolve()
    report_path = args.report.expanduser().resolve()
    preregistration_path = args.preregistration.expanduser().resolve()
    analyzer_path = Path(__file__).resolve()
    try:
        for path in (
            manifest_path,
            report_path,
            preregistration_path,
            analyzer_path,
        ):
            if not path.is_file():
                raise ValueError(f"required file is missing: {path}")
        manifest_hash = sha256_file(manifest_path)
        if manifest_hash != EXPECTED_MANIFEST_SHA256:
            raise ValueError("observed manifest SHA-256 differs from preregistration")
        value = analyze(
            load_object(manifest_path),
            load_object(report_path),
            {
                "manifest_sha256": manifest_hash,
                "raw_report_sha256": sha256_file(report_path),
                "preregistration_sha256": sha256_file(preregistration_path),
                "analyzer_sha256": sha256_file(analyzer_path),
            },
        )
        write_new(args.output.expanduser().resolve(), value)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    p1 = value["populations"]["p1_general_consumed"]["case_level"]
    print(
        "wrote fixed-rule atlas: "
        f"{p1['confusion']['true_positive']} true positives, "
        f"{p1['confusion']['false_positive']} false positives"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
