#!/usr/bin/env python3
"""Deterministic grouped evaluation for the full-reference research oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "full-reference-evaluation-plan.json"
)
RESEARCH_PLAN = (
    ROOT / "benchmarks" / "perceptual-degradation-v1" / "research-plan.json"
)
REPLAY = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-full-reference-evaluation-synthetic-20260813-001.json"
)
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = "lossytrace-full-reference-source-group-bootstrap-20260813-001"
MINIMUM_VALID_BOOTSTRAP_FRACTION = 0.99
ECE_BIN_COUNT = 10
MINIMUM_REVERSAL_SOURCE_GROUPS = 8
MINIMUM_PRIMARY_DOMAIN_SOURCE_GROUPS = 8
ONE_SIDED_95_Z = 1.6448536269514722
OPAQUE_ID = re.compile(r"^(?:case|group|partition-group)-[0-9a-f]{64}$")
STRATUM_ID = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
BASELINE_IDS = (
    "visqol_audio_v3_3_3",
    "gstpeaq_proxy_v0_6_1",
    "signal_distance_v1",
)
AXES = ("primary_domain", "codec_stratum", "encoder_stratum", "artifact_stratum")
DIAGNOSTIC_AXES = (*AXES, "bitrate_region", "human_truth_stratum")
GATES = {
    "severity_spearman_lower_ci_overall": 0.75,
    "severity_spearman_lower_ci_each_primary_domain": 0.55,
    "audibility_brier_max": 0.15,
    "audibility_ece_max": 0.10,
    "audibility_auc_lower_ci": 0.75,
    "transparent_material_rate_point_max": 0.05,
    "transparent_material_rate_upper_ci_max": 0.10,
    "material_sensitivity_lower_ci": 0.80,
    "coverage_overall_min": 0.80,
    "coverage_each_primary_domain_min": 0.60,
    "added_value_brier_absolute": 0.02,
    "added_value_severity_correlation_absolute": 0.05,
}


def research_plan_gate_projection(research_plan: dict[str, Any]) -> dict[str, float]:
    gates = research_plan.get("full_reference_gates", {})
    added_value = gates.get("required_added_value", {})
    return {
        "severity_spearman_lower_ci_overall": gates.get(
            "severity_spearman_lower_ci_overall"
        ),
        "severity_spearman_lower_ci_each_primary_domain": gates.get(
            "severity_spearman_lower_ci_each_primary_domain"
        ),
        "audibility_brier_max": gates.get("audibility_brier_max"),
        "audibility_ece_max": gates.get("audibility_ece_max"),
        "audibility_auc_lower_ci": gates.get("audibility_auc_lower_ci"),
        "transparent_material_rate_point_max": gates.get(
            "transparent_material_rate_point_max"
        ),
        "transparent_material_rate_upper_ci_max": gates.get(
            "transparent_material_rate_upper_ci_max"
        ),
        "material_sensitivity_lower_ci": gates.get(
            "material_sensitivity_lower_ci"
        ),
        "coverage_overall_min": gates.get("coverage_overall_min"),
        "coverage_each_primary_domain_min": gates.get(
            "coverage_each_primary_domain_min"
        ),
        "added_value_brier_absolute": added_value.get("brier_absolute"),
        "added_value_severity_correlation_absolute": added_value.get(
            "severity_correlation_absolute"
        ),
    }


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + 1 + end) / 2.0
        for position in range(start, end):
            result[order[position]] = rank
        start = end
    return result


def pearson(first: Sequence[float], second: Sequence[float]) -> float | None:
    if len(first) != len(second) or len(first) < 2:
        return None
    mean_first = statistics.fmean(first)
    mean_second = statistics.fmean(second)
    centered_first = [value - mean_first for value in first]
    centered_second = [value - mean_second for value in second]
    first_energy = math.fsum(value * value for value in centered_first)
    second_energy = math.fsum(value * value for value in centered_second)
    if first_energy <= 0.0 or second_energy <= 0.0:
        return None
    return math.fsum(
        left * right
        for left, right in zip(centered_first, centered_second, strict=True)
    ) / math.sqrt(first_energy * second_energy)


def spearman(first: Sequence[float], second: Sequence[float]) -> float | None:
    if len(first) != len(second):
        return None
    return pearson(average_ranks(first), average_ranks(second))


def brier(labels: Sequence[bool], probabilities: Sequence[float]) -> float | None:
    if len(labels) != len(probabilities) or not labels:
        return None
    return statistics.fmean(
        (probability - float(label)) ** 2
        for label, probability in zip(labels, probabilities, strict=True)
    )


def expected_calibration_error(
    labels: Sequence[bool], probabilities: Sequence[float]
) -> float | None:
    if len(labels) != len(probabilities) or not labels:
        return None
    total = len(labels)
    error = 0.0
    for bin_index in range(ECE_BIN_COUNT):
        lower = bin_index / ECE_BIN_COUNT
        upper = (bin_index + 1) / ECE_BIN_COUNT
        indexes = [
            index
            for index, probability in enumerate(probabilities)
            if lower <= probability < upper
            or (bin_index == ECE_BIN_COUNT - 1 and probability == 1.0)
        ]
        if not indexes:
            continue
        confidence = statistics.fmean(probabilities[index] for index in indexes)
        accuracy = statistics.fmean(float(labels[index]) for index in indexes)
        error += len(indexes) / total * abs(confidence - accuracy)
    return error


def roc_auc(labels: Sequence[bool], probabilities: Sequence[float]) -> float | None:
    if len(labels) != len(probabilities) or not labels:
        return None
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    ranks = average_ranks(probabilities)
    positive_rank_sum = math.fsum(
        rank for rank, label in zip(ranks, labels, strict=True) if label
    )
    return (positive_rank_sum - positives * (positives + 1) / 2) / (
        positives * negatives
    )


def percentile(values: Sequence[float], probability: float) -> float | None:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return None
    if not 0.0 <= probability <= 1.0:
        raise ValueError("percentile probability differs")
    position = probability * (len(finite) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return finite[lower]
    weight = position - lower
    return finite[lower] * (1.0 - weight) + finite[upper] * weight


def _hash_index(seed: str, replicate: int, draw: int, size: int) -> int:
    if size < 1:
        raise ValueError("bootstrap population is empty")
    maximum = 1 << 64
    limit = maximum - maximum % size
    nonce = 0
    while True:
        payload = f"{seed}\0{replicate}\0{draw}\0{nonce}".encode()
        value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
        if value < limit:
            return value % size
        nonce += 1


def _resampled_records(
    by_group: dict[str, list[dict[str, Any]]],
    group_ids: list[str],
    replicate: int,
    seed: str,
) -> list[dict[str, Any]]:
    return [
        record
        for draw in range(len(group_ids))
        for record in by_group[group_ids[_hash_index(seed, replicate, draw, len(group_ids))]]
    ]


def bootstrap_summary(
    records: list[dict[str, Any]],
    metric: Callable[[list[dict[str, Any]]], float | None],
    *,
    replicates: int,
    seed_suffix: str,
) -> dict[str, Any]:
    if replicates < 1:
        raise ValueError("bootstrap replicate count must be positive")
    by_group: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_group.setdefault(record["source_group_id"], []).append(record)
    group_ids = sorted(by_group)
    point = metric(records)
    values = []
    seed = f"{BOOTSTRAP_SEED}\0{seed_suffix}"
    for replicate in range(replicates):
        value = metric(_resampled_records(by_group, group_ids, replicate, seed))
        if value is not None and math.isfinite(value):
            values.append(value)
    result = {
        "point": point,
        "lower_two_sided_95": percentile(values, 0.025),
        "upper_two_sided_95": percentile(values, 0.975),
        "lower_one_sided_95": percentile(values, 0.05),
        "upper_one_sided_95": percentile(values, 0.95),
        "valid_replicates": len(values),
        "requested_replicates": replicates,
        "source_group_count": len(group_ids),
        "partition_group_count": len(
            {record["partition_group_id"] for record in records}
        ),
        "case_count": len(records),
    }
    result["valid_fraction"] = len(values) / replicates
    result["validity_gate_passes"] = (
        result["valid_fraction"] >= MINIMUM_VALID_BOOTSTRAP_FRACTION
    )
    return result


def _supported(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if record["oracle"]["supported"]]


def _severity(records: list[dict[str, Any]], prediction: str = "oracle") -> float | None:
    pairs = [
        (record["human_severity"], record[prediction]["severity"])
        for record in records
        if record[prediction]["severity"] is not None
    ]
    return spearman([pair[0] for pair in pairs], [pair[1] for pair in pairs])


def _brier(records: list[dict[str, Any]], prediction: str = "oracle") -> float | None:
    pairs = [
        (record["human_audible"], record[prediction]["audibility_probability"])
        for record in records
        if record[prediction]["audibility_probability"] is not None
    ]
    return brier([pair[0] for pair in pairs], [pair[1] for pair in pairs])


def _ece(records: list[dict[str, Any]]) -> float | None:
    pairs = [
        (record["human_audible"], record["oracle"]["audibility_probability"])
        for record in records
        if record["oracle"]["audibility_probability"] is not None
    ]
    return expected_calibration_error(
        [pair[0] for pair in pairs], [pair[1] for pair in pairs]
    )


def _auc(records: list[dict[str, Any]]) -> float | None:
    pairs = [
        (record["human_audible"], record["oracle"]["audibility_probability"])
        for record in records
        if record["oracle"]["audibility_probability"] is not None
    ]
    return roc_auc([pair[0] for pair in pairs], [pair[1] for pair in pairs])


def _mean_flag(records: list[dict[str, Any]], key: str) -> float | None:
    if not records:
        return None
    return statistics.fmean(float(record["oracle"][key]) for record in records)


def wilson_bounds(successes: int, trials: int) -> tuple[float | None, float | None]:
    if trials < 1 or successes < 0 or successes > trials:
        return None, None
    probability = successes / trials
    z_squared = ONE_SIDED_95_Z**2
    denominator = 1.0 + z_squared / trials
    center = (probability + z_squared / (2.0 * trials)) / denominator
    radius = (
        ONE_SIDED_95_Z
        * math.sqrt(
            probability * (1.0 - probability) / trials
            + z_squared / (4.0 * trials * trials)
        )
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def _source_group_guard(
    records: list[dict[str, Any]], key: str, *, mode: str
) -> dict[str, Any]:
    by_group: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_group.setdefault(record["source_group_id"], []).append(record)
    if mode == "any_event":
        group_values = [
            any(record["oracle"][key] for record in by_group[group_id])
            for group_id in sorted(by_group)
        ]
        definition = "source_group_has_any_event"
    elif mode == "all_success":
        group_values = [
            all(record["oracle"][key] for record in by_group[group_id])
            for group_id in sorted(by_group)
        ]
        definition = "source_group_has_all_successes"
    else:
        raise ValueError("source-group guard mode differs")
    successes = sum(group_values)
    lower, upper = wilson_bounds(successes, len(group_values))
    return {
        "definition": definition,
        "success_source_group_count": successes,
        "source_group_count": len(group_values),
        "lower_one_sided_95": lower,
        "upper_one_sided_95": upper,
        "method": "wilson_score",
        "z": ONE_SIDED_95_Z,
    }


def _rate_summary(
    records: list[dict[str, Any]],
    key: str,
    *,
    replicates: int,
    seed_suffix: str,
    guard_mode: str,
) -> dict[str, Any]:
    result = bootstrap_summary(
        records,
        lambda values: _mean_flag(values, key),
        replicates=replicates,
        seed_suffix=seed_suffix,
    )
    guard = _source_group_guard(records, key, mode=guard_mode)
    result["source_group_boundary_guard"] = guard
    if guard_mode == "any_event":
        candidates = [
            value
            for value in (result["upper_one_sided_95"], guard["upper_one_sided_95"])
            if value is not None
        ]
        result["gate_upper_one_sided_95"] = max(candidates) if candidates else None
    else:
        candidates = [
            value
            for value in (result["lower_one_sided_95"], guard["lower_one_sided_95"])
            if value is not None
        ]
        result["gate_lower_one_sided_95"] = min(candidates) if candidates else None
    return result


def _coverage(records: list[dict[str, Any]]) -> float:
    return statistics.fmean(float(record["oracle"]["supported"]) for record in records)


def human_truth_stratum(record: dict[str, Any]) -> str:
    if record["human_transparent"]:
        return "transparent"
    if record["human_material"]:
        return "material"
    if record["human_audible"]:
        return "audible_nonmaterial"
    return "indeterminate"


def _diagnostic_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    supported = _supported(records)
    return {
        "case_count": len(records),
        "source_group_count": len({record["source_group_id"] for record in records}),
        "partition_group_count": len(
            {record["partition_group_id"] for record in records}
        ),
        "supported_case_count": len(supported),
        "coverage": _coverage(records),
        "severity_spearman": _severity(supported),
        "audibility_brier": _brier(supported),
        "audibility_ece": _ece(supported),
        "audibility_roc_auc": _auc(supported),
    }


def _validate_probability(value: Any, field: str, errors: list[str]) -> None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or not 0.0 <= value <= 1.0
    ):
        errors.append(f"probability differs: {field}")


def validate_records(records: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(records, list) or not records:
        return ["evaluation records must be a non-empty list"]
    case_ids: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"record differs: {index}")
            continue
        expected_keys = {
            "case_id",
            "source_group_id",
            "partition_group_id",
            "primary_domain",
            "codec_stratum",
            "encoder_stratum",
            "artifact_stratum",
            "bitrate_region",
            "human_severity",
            "human_audible",
            "human_transparent",
            "human_material",
            "oracle",
            *BASELINE_IDS,
        }
        if set(record) != expected_keys:
            errors.append(f"record field set differs: {index}")
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not OPAQUE_ID.fullmatch(case_id):
            errors.append(f"case identity differs: {index}")
        elif case_id in case_ids:
            errors.append(f"duplicate case identity: {index}")
        else:
            case_ids.add(case_id)
        group_id = record.get("source_group_id")
        if not isinstance(group_id, str) or not OPAQUE_ID.fullmatch(group_id):
            errors.append(f"source-group identity differs: {index}")
        partition_group_id = record.get("partition_group_id")
        if not isinstance(partition_group_id, str) or not OPAQUE_ID.fullmatch(
            partition_group_id
        ):
            errors.append(f"partition-group identity differs: {index}")
        for key in AXES:
            value = record.get(key)
            if not isinstance(value, str) or not STRATUM_ID.fullmatch(value):
                errors.append(f"stratum differs: {index}:{key}")
        bitrate_region = record.get("bitrate_region")
        if not isinstance(bitrate_region, str) or not STRATUM_ID.fullmatch(
            bitrate_region
        ):
            errors.append(f"stratum differs: {index}:bitrate_region")
        severity = record.get("human_severity")
        if (
            not isinstance(severity, (int, float))
            or isinstance(severity, bool)
            or not math.isfinite(float(severity))
            or not 0.0 <= severity <= 100.0
        ):
            errors.append(f"human severity differs: {index}")
        for key in ("human_audible", "human_transparent", "human_material"):
            if not isinstance(record.get(key), bool):
                errors.append(f"human label differs: {index}:{key}")
        if record.get("human_transparent") is True and record.get("human_material") is True:
            errors.append(f"transparent and material labels conflict: {index}")
        if record.get("human_material") is True and record.get("human_audible") is not True:
            errors.append(f"material label lacks audibility: {index}")
        if record.get("human_transparent") is True and record.get("human_audible") is True:
            errors.append(f"transparent label conflicts with audibility: {index}")
        for prediction_id in ("oracle", *BASELINE_IDS):
            prediction = record.get(prediction_id)
            if not isinstance(prediction, dict) or set(prediction) != {
                "supported",
                "severity",
                "audibility_probability",
                "materially_degraded",
            }:
                errors.append(f"prediction field set differs: {index}:{prediction_id}")
                continue
            supported = prediction.get("supported")
            if not isinstance(supported, bool):
                errors.append(f"prediction support differs: {index}:{prediction_id}")
                continue
            values = (
                prediction.get("severity"),
                prediction.get("audibility_probability"),
                prediction.get("materially_degraded"),
            )
            if not supported:
                if values != (None, None, None):
                    errors.append(f"unsupported prediction contains values: {index}:{prediction_id}")
                continue
            predicted_severity, probability, material = values
            if (
                not isinstance(predicted_severity, (int, float))
                or isinstance(predicted_severity, bool)
                or not math.isfinite(float(predicted_severity))
                or not 0.0 <= predicted_severity <= 100.0
            ):
                errors.append(f"predicted severity differs: {index}:{prediction_id}")
            _validate_probability(probability, f"{index}:{prediction_id}", errors)
            if not isinstance(material, bool):
                errors.append(f"predicted material label differs: {index}:{prediction_id}")
    serialized = json.dumps(records, sort_keys=True)
    if any(value in serialized for value in ("/Users/", "Application Support", "file://")):
        errors.append("evaluation records contain a private path")
    source_partitions: dict[str, set[str]] = {}
    for record in records:
        if isinstance(record, dict) and isinstance(record.get("source_group_id"), str):
            source_partitions.setdefault(record["source_group_id"], set()).add(
                str(record.get("partition_group_id"))
            )
    if any(len(partitions) != 1 for partitions in source_partitions.values()):
        errors.append("source group crosses partition groups")
    return errors


def _eligible_reversal_strata(
    records: list[dict[str, Any]], axis: str
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for value in sorted({record[axis] for record in records}):
        subset = [record for record in records if record[axis] == value]
        groups = {record["source_group_id"] for record in subset}
        human_values = {record["human_severity"] for record in subset}
        predicted_values = {record["oracle"]["severity"] for record in subset}
        if (
            len(groups) >= MINIMUM_REVERSAL_SOURCE_GROUPS
            and len(human_values) >= 2
            and len(predicted_values) >= 2
        ):
            result[value] = subset
    return result


def evaluate(
    records: list[dict[str, Any]],
    *,
    primary_domains: Sequence[str],
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    errors = validate_records(records)
    if errors:
        raise ValueError("invalid full-reference evaluation records: " + "; ".join(errors))
    if bootstrap_replicates < BOOTSTRAP_REPLICATES:
        raise ValueError("full-reference gate requires at least 10000 bootstrap replicates")
    domains = sorted(set(primary_domains))
    observed_domains = {record["primary_domain"] for record in records}
    if not domains or set(domains) != observed_domains:
        raise ValueError("primary domains differ")
    for domain in domains:
        group_count = len(
            {
                record["source_group_id"]
                for record in records
                if record["primary_domain"] == domain
            }
        )
        if group_count < MINIMUM_PRIMARY_DOMAIN_SOURCE_GROUPS:
            raise ValueError("primary domain has insufficient source groups")

    supported = _supported(records)
    severity_overall = bootstrap_summary(
        supported,
        _severity,
        replicates=bootstrap_replicates,
        seed_suffix="severity-overall",
    )
    severity_by_domain = {}
    coverage_by_domain = {}
    for domain in domains:
        domain_all = [record for record in records if record["primary_domain"] == domain]
        domain_supported = _supported(domain_all)
        severity_by_domain[domain] = bootstrap_summary(
            domain_supported,
            _severity,
            replicates=bootstrap_replicates,
            seed_suffix=f"severity-domain-{domain}",
        )
        coverage_by_domain[domain] = _coverage(domain_all)

    audibility = {
        "brier": bootstrap_summary(
            supported,
            _brier,
            replicates=bootstrap_replicates,
            seed_suffix="audibility-brier",
        ),
        "ece_10_equal_width": bootstrap_summary(
            supported,
            _ece,
            replicates=bootstrap_replicates,
            seed_suffix="audibility-ece",
        ),
        "roc_auc": bootstrap_summary(
            supported,
            _auc,
            replicates=bootstrap_replicates,
            seed_suffix="audibility-auc",
        ),
    }
    transparent = [record for record in supported if record["human_transparent"]]
    material = [record for record in supported if record["human_material"]]
    transparent_rate = _rate_summary(
        transparent,
        "materially_degraded",
        replicates=bootstrap_replicates,
        seed_suffix="transparent-material-rate",
        guard_mode="any_event",
    )
    material_sensitivity = _rate_summary(
        material,
        "materially_degraded",
        replicates=bootstrap_replicates,
        seed_suffix="material-sensitivity",
        guard_mode="all_success",
    )

    reversal = {}
    reversed_strata = []
    for axis in AXES:
        reversal[axis] = {}
        for stratum, subset in _eligible_reversal_strata(supported, axis).items():
            summary = bootstrap_summary(
                subset,
                _severity,
                replicates=bootstrap_replicates,
                seed_suffix=f"reversal-{axis}-{stratum}",
            )
            summary["statistically_supported_reversal"] = (
                summary["validity_gate_passes"]
                and summary["upper_two_sided_95"] is not None
                and summary["upper_two_sided_95"] < 0.0
            )
            if summary["statistically_supported_reversal"]:
                reversed_strata.append(f"{axis}:{stratum}")
            reversal[axis][stratum] = summary

    added_value = {}
    for baseline_id in BASELINE_IDS:
        paired = [
            record
            for record in supported
            if record[baseline_id]["supported"]
        ]
        combined_correlation = _severity(paired, "oracle")
        baseline_correlation = _severity(paired, baseline_id)
        combined_brier = _brier(paired, "oracle")
        baseline_brier = _brier(paired, baseline_id)
        severity_improvement = (
            None
            if combined_correlation is None or baseline_correlation is None
            else combined_correlation - baseline_correlation
        )
        brier_improvement = (
            None
            if combined_brier is None or baseline_brier is None
            else baseline_brier - combined_brier
        )
        passes = (
            brier_improvement is not None
            and brier_improvement >= GATES["added_value_brier_absolute"]
        ) or (
            severity_improvement is not None
            and severity_improvement
            >= GATES["added_value_severity_correlation_absolute"]
        )
        added_value[baseline_id] = {
            "paired_case_count": len(paired),
            "paired_source_group_count": len(
                {record["source_group_id"] for record in paired}
            ),
            "combined_severity_spearman": combined_correlation,
            "baseline_severity_spearman": baseline_correlation,
            "severity_correlation_improvement": severity_improvement,
            "combined_brier": combined_brier,
            "baseline_brier": baseline_brier,
            "brier_improvement": brier_improvement,
            "passes": passes,
        }

    diagnostic_views = {}
    for axis in DIAGNOSTIC_AXES:
        if axis == "human_truth_stratum":
            values = sorted({human_truth_stratum(record) for record in records})
            diagnostic_views[axis] = {
                value: _diagnostic_summary(
                    [record for record in records if human_truth_stratum(record) == value]
                )
                for value in values
            }
        else:
            values = sorted({record[axis] for record in records})
            diagnostic_views[axis] = {
                value: _diagnostic_summary(
                    [record for record in records if record[axis] == value]
                )
                for value in values
            }

    reversal_unevaluable = [
        f"{axis}:{stratum}"
        for axis, strata in reversal.items()
        for stratum, summary in strata.items()
        if not summary["validity_gate_passes"]
    ]
    gate_results = {
        "severity_ordering": (
            severity_overall["validity_gate_passes"]
            and severity_overall["lower_one_sided_95"] is not None
            and severity_overall["lower_one_sided_95"]
            >= GATES["severity_spearman_lower_ci_overall"]
            and all(
                summary["lower_one_sided_95"] is not None
                and summary["validity_gate_passes"]
                and summary["lower_one_sided_95"]
                >= GATES["severity_spearman_lower_ci_each_primary_domain"]
                for summary in severity_by_domain.values()
            )
        ),
        "audibility_calibration": (
            audibility["brier"]["point"] is not None
            and audibility["brier"]["validity_gate_passes"]
            and audibility["brier"]["point"] <= GATES["audibility_brier_max"]
            and audibility["ece_10_equal_width"]["point"] is not None
            and audibility["ece_10_equal_width"]["validity_gate_passes"]
            and audibility["ece_10_equal_width"]["point"]
            <= GATES["audibility_ece_max"]
            and audibility["roc_auc"]["lower_one_sided_95"] is not None
            and audibility["roc_auc"]["validity_gate_passes"]
            and audibility["roc_auc"]["lower_one_sided_95"]
            >= GATES["audibility_auc_lower_ci"]
        ),
        "transparent_safety": (
            transparent_rate["point"] is not None
            and transparent_rate["validity_gate_passes"]
            and transparent_rate["point"]
            <= GATES["transparent_material_rate_point_max"]
            and transparent_rate["gate_upper_one_sided_95"] is not None
            and transparent_rate["gate_upper_one_sided_95"]
            <= GATES["transparent_material_rate_upper_ci_max"]
        ),
        "material_sensitivity": (
            material_sensitivity["validity_gate_passes"]
            and material_sensitivity["gate_lower_one_sided_95"] is not None
            and material_sensitivity["gate_lower_one_sided_95"]
            >= GATES["material_sensitivity_lower_ci"]
        ),
        "coverage": (
            _coverage(records) >= GATES["coverage_overall_min"]
            and all(
                value >= GATES["coverage_each_primary_domain_min"]
                for value in coverage_by_domain.values()
            )
        ),
        "no_subgroup_reversal": not reversed_strata and not reversal_unevaluable,
        "added_value": all(item["passes"] for item in added_value.values()),
    }
    return {
        "schema_version": 1,
        "statistics_id": "full-reference-grouped-statistics-20260813-001",
        "bootstrap": {
            "unit": "source_group",
            "replicates": bootstrap_replicates,
            "seed": BOOTSTRAP_SEED,
            "sampler": "sha256_counter_rejection_uniform_v1",
            "interval": "percentile",
            "two_sided_quantiles": [0.025, 0.975],
            "one_sided_quantiles": [0.05, 0.95],
            "minimum_valid_fraction": MINIMUM_VALID_BOOTSTRAP_FRACTION,
        },
        "severity": {
            "overall_spearman": severity_overall,
            "by_primary_domain": severity_by_domain,
        },
        "audibility": audibility,
        "transparent_material_rate": transparent_rate,
        "material_sensitivity": material_sensitivity,
        "coverage": {
            "overall": _coverage(records),
            "by_primary_domain": coverage_by_domain,
        },
        "subgroup_reversal": {
            "minimum_source_groups": MINIMUM_REVERSAL_SOURCE_GROUPS,
            "axes": reversal,
            "reversed_strata": reversed_strata,
            "unevaluable_strata": reversal_unevaluable,
        },
        "added_value": added_value,
        "diagnostic_views": diagnostic_views,
        "gate_results": {
            **gate_results,
            "all_statistical_gates_pass": all(gate_results.values()),
        },
    }


def synthetic_records() -> list[dict[str, Any]]:
    records = []
    for group_index in range(40):
        domain = "synthetic_music_a" if group_index < 20 else "synthetic_music_b"
        for condition_index, severity in enumerate((5.0, 65.0)):
            audible = condition_index == 1
            material = condition_index == 1
            group_id = "group-" + hashlib.sha256(f"group-{group_index}".encode()).hexdigest()
            case_id = "case-" + hashlib.sha256(
                f"case-{group_index}-{condition_index}".encode()
            ).hexdigest()
            oracle_severity = severity + ((group_index % 3) - 1) * 0.5
            records.append(
                {
                    "case_id": case_id,
                    "source_group_id": group_id,
                    "partition_group_id": "partition-group-"
                    + hashlib.sha256(f"partition-{group_index // 2}".encode()).hexdigest(),
                    "primary_domain": domain,
                    "codec_stratum": f"synthetic_codec_{group_index % 2}",
                    "encoder_stratum": f"synthetic_encoder_{group_index % 2}",
                    "artifact_stratum": f"synthetic_artifact_{group_index % 2}",
                    "bitrate_region": (
                        "transparent_candidate" if not material else "severe"
                    ),
                    "human_severity": severity,
                    "human_audible": audible,
                    "human_transparent": not material,
                    "human_material": material,
                    "oracle": {
                        "supported": True,
                        "severity": oracle_severity,
                        "audibility_probability": 0.05 if not audible else 0.95,
                        "materially_degraded": material,
                    },
                    "visqol_audio_v3_3_3": {
                        "supported": True,
                        "severity": 30.0 + (5.0 if material else 0.0),
                        "audibility_probability": 0.40 if not audible else 0.60,
                        "materially_degraded": material,
                    },
                    "gstpeaq_proxy_v0_6_1": {
                        "supported": True,
                        "severity": 25.0 + (10.0 if material else 0.0),
                        "audibility_probability": 0.35 if not audible else 0.65,
                        "materially_degraded": material,
                    },
                    "signal_distance_v1": {
                        "supported": True,
                        "severity": float((group_index * 17 + condition_index * 7) % 100),
                        "audibility_probability": 0.45 if not audible else 0.55,
                        "materially_degraded": material,
                    },
                }
            )
    return records


def build_synthetic_replay(
    evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    records = synthetic_records()
    if evaluation is None:
        evaluation = evaluate(
            records,
            primary_domains=["synthetic_music_a", "synthetic_music_b"],
        )
    severity = evaluation["severity"]["overall_spearman"]
    audibility = evaluation["audibility"]
    transparent = evaluation["transparent_material_rate"]
    material = evaluation["material_sensitivity"]
    return {
        "schema_version": 1,
        "replay_id": "perceptual-degradation-full-reference-evaluation-synthetic-20260813-001",
        "state": "synthetic_statistics_replayed_no_scientific_gate_evaluated",
        "fixture_only": True,
        "scientific_gate_evaluated": False,
        "synthetic_record_inventory_sha256": hashlib.sha256(
            canonical_bytes(records)
        ).hexdigest(),
        "evaluation_sha256": hashlib.sha256(canonical_bytes(evaluation)).hexdigest(),
        "evaluation_summary": {
            "case_count": severity["case_count"],
            "source_group_count": severity["source_group_count"],
            "partition_group_count": severity["partition_group_count"],
            "bootstrap_replicates": evaluation["bootstrap"]["replicates"],
            "severity_spearman_point": severity["point"],
            "severity_spearman_lower_one_sided_95": severity[
                "lower_one_sided_95"
            ],
            "audibility_brier": audibility["brier"]["point"],
            "audibility_ece": audibility["ece_10_equal_width"]["point"],
            "audibility_auc_lower_one_sided_95": audibility["roc_auc"][
                "lower_one_sided_95"
            ],
            "transparent_material_rate_point": transparent["point"],
            "transparent_material_rate_gate_upper_one_sided_95": transparent[
                "gate_upper_one_sided_95"
            ],
            "material_sensitivity_gate_lower_one_sided_95": material[
                "gate_lower_one_sided_95"
            ],
            "coverage_overall": evaluation["coverage"]["overall"],
            "reversed_strata": evaluation["subgroup_reversal"]["reversed_strata"],
            "unevaluable_strata": evaluation["subgroup_reversal"][
                "unevaluable_strata"
            ],
            "added_value_passes": {
                baseline_id: evaluation["added_value"][baseline_id]["passes"]
                for baseline_id in BASELINE_IDS
            },
            "synthetic_gate_results": evaluation["gate_results"],
        },
        "access_boundary": {
            "synthetic_records_only": True,
            "retained_audio_accessed": False,
            "provider_audio_accessed": False,
            "perceptual_metric_executed": False,
            "human_score_accessed": False,
            "sealed_evidence_opened": False,
            "no_reference_training_performed": False,
            "public_verdict_enabled": False,
        },
        "claim_boundary": {
            "synthetic_gate_pass_is_scientific_evidence": False,
            "full_reference_gate_passed": False,
            "no_reference_work_eligible": False,
        },
        "paths_redacted": True,
    }


def validate_synthetic_replay(replay: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = build_synthetic_replay()
    if replay != expected:
        errors.append("synthetic evaluation replay differs from exact reconstruction")
    if replay.get("state") != "synthetic_statistics_replayed_no_scientific_gate_evaluated":
        errors.append("synthetic replay state differs")
    if replay.get("fixture_only") is not True:
        errors.append("synthetic replay fixture boundary differs")
    if replay.get("scientific_gate_evaluated") is not False:
        errors.append("synthetic replay improperly claims scientific evaluation")
    boundary = replay.get("access_boundary", {})
    if not isinstance(boundary, dict):
        errors.append("synthetic replay access boundary differs")
        boundary = {}
    if boundary.get("synthetic_records_only") is not True:
        errors.append("synthetic-record boundary differs")
    for key in (
        "retained_audio_accessed",
        "provider_audio_accessed",
        "perceptual_metric_executed",
        "human_score_accessed",
        "sealed_evidence_opened",
        "no_reference_training_performed",
        "public_verdict_enabled",
    ):
        if boundary.get(key) is not False:
            errors.append(f"synthetic replay access boundary must remain false: {key}")
    if replay.get("claim_boundary") != {
        "synthetic_gate_pass_is_scientific_evidence": False,
        "full_reference_gate_passed": False,
        "no_reference_work_eligible": False,
    }:
        errors.append("synthetic replay claim boundary differs")
    if replay.get("paths_redacted") is not True:
        errors.append("synthetic replay paths must remain redacted")
    serialized = json.dumps(replay, sort_keys=True)
    if any(value in serialized for value in ("/Users/", "Application Support", "file://")):
        errors.append("synthetic replay contains a private path")
    return errors


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_plan_keys = {
        "schema_version",
        "plan_id",
        "state",
        "purpose",
        "bindings",
        "statistics",
        "numeric_gates",
        "subgroup_policy",
        "diagnostic_policy",
        "population_policy",
        "boundary_rate_policy",
        "input_boundary",
        "synthetic_replay",
        "access_boundary",
        "claim_boundary",
        "authorized_next_step",
    }
    if set(plan) != expected_plan_keys:
        errors.append("plan field set differs")
    if plan.get("schema_version") != 1:
        errors.append("plan schema version differs")
    if plan.get("plan_id") != "full-reference-evaluation-plan-20260813-001":
        errors.append("plan identity differs")
    if plan.get("state") != "score_blind_statistics_frozen_synthetic_replay_complete":
        errors.append("plan state differs")
    expected_bindings = {
        "research_plan",
        "research_contract",
        "score_free_oracle_plan",
        "evaluation_implementation",
        "evaluation_tests",
        "synthetic_replay",
        "evaluation_report",
    }
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        errors.append("plan binding set differs")
    else:
        for binding_id, binding in bindings.items():
            if not isinstance(binding, dict):
                errors.append(f"invalid binding object: {binding_id}")
                continue
            relative = Path(str(binding.get("path", "")))
            if relative.is_absolute() or ".." in relative.parts:
                errors.append(f"invalid repository-relative binding: {binding_id}")
                continue
            path = ROOT / relative
            if not path.is_file():
                errors.append(f"missing bound file: {binding_id}")
            elif sha256_file(path) != binding.get("sha256"):
                errors.append(f"bound file hash differs: {binding_id}")
    if plan.get("statistics") != {
        "bootstrap_unit": "source_group",
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_sampler": "sha256_counter_rejection_uniform_v1",
        "minimum_valid_bootstrap_fraction": MINIMUM_VALID_BOOTSTRAP_FRACTION,
        "interval_method": "percentile",
        "two_sided_quantiles": [0.025, 0.975],
        "one_sided_quantiles": [0.05, 0.95],
        "spearman_ties": "average_rank",
        "roc_auc_ties": "average_rank_mann_whitney",
        "ece_bins": ECE_BIN_COUNT,
        "ece_binning": "equal_width_left_closed_right_open_final_includes_one",
        "minimum_reversal_source_groups": MINIMUM_REVERSAL_SOURCE_GROUPS,
        "minimum_primary_domain_source_groups": MINIMUM_PRIMARY_DOMAIN_SOURCE_GROUPS,
        "boundary_rate_guard": "source_group_wilson_one_sided_95_conservative_max_or_min",
        "boundary_rate_guard_z": ONE_SIDED_95_Z,
        "added_value_gate_uses_pairwise_complete_point_estimates": True,
    }:
        errors.append("statistical freeze differs")
    if plan.get("numeric_gates") != GATES:
        errors.append("numeric gates differ")
    if research_plan_gate_projection(load_json(RESEARCH_PLAN)) != GATES:
        errors.append("implementation gates differ from frozen research plan")
    if load_json(RESEARCH_PLAN).get("full_reference_gates", {}).get(
        "bootstrap_replicates_min"
    ) != BOOTSTRAP_REPLICATES:
        errors.append("bootstrap replicate minimum differs from frozen research plan")
    if plan.get("subgroup_policy") != {
        "axes": list(AXES),
        "statistically_supported_reversal": "two_sided_95_upper_spearman_below_zero",
        "undefined_bootstrap_fraction_above_one_percent_fails_gate": True,
        "multiplicity_adjustment": "none_stop_oriented_conservative_any_reversal_fails",
    }:
        errors.append("subgroup policy differs")
    if plan.get("diagnostic_policy") != {
        "axes": list(DIAGNOSTIC_AXES),
        "human_truth_strata_derived_from_labels": True,
        "reported_statistics": [
            "case_and_group_counts",
            "coverage",
            "severity_spearman",
            "audibility_brier",
            "audibility_ece",
            "audibility_roc_auc",
        ],
        "point_diagnostics_are_gate_inputs": False,
    }:
        errors.append("diagnostic policy differs")
    if plan.get("population_policy") != {
        "severity_and_audibility_use_supported_cases": True,
        "transparent_safety_uses_supported_human_transparent_cases": True,
        "material_sensitivity_uses_supported_human_material_cases": True,
        "coverage_uses_all_eligible_cases": True,
        "unsupported_cases_remain_visible_through_coverage": True,
        "primary_domains_are_declared_before_evaluation": True,
    }:
        errors.append("population policy differs")
    if plan.get("boundary_rate_policy") != {
        "bootstrap_interval_retained": True,
        "transparent_group_event": "any_human_transparent_condition_called_materially_degraded",
        "transparent_gate_upper": "maximum_of_bootstrap_and_source_group_wilson_upper",
        "material_group_success": "all_human_material_conditions_called_materially_degraded",
        "material_gate_lower": "minimum_of_bootstrap_and_source_group_wilson_lower",
        "policy_can_only_tighten_original_numeric_gates": True,
    }:
        errors.append("boundary rate policy differs")
    if plan.get("input_boundary") != {
        "opaque_case_source_and_partition_ids_required": True,
        "bounded_stratum_codes_required": True,
        "source_group_may_not_cross_partition_groups": True,
        "unsupported_predictions_must_have_null_values": True,
        "human_material_requires_human_audible": True,
        "human_transparent_conflicts_with_audible_or_material": True,
        "codec_encoder_and_artifact_strata_are_evaluation_only": True,
        "metadata_is_model_input": False,
    }:
        errors.append("input boundary differs")
    if plan.get("claim_boundary") != {
        "synthetic_gate_pass_is_scientific_evidence": False,
        "determinism_gate_evaluated": False,
        "full_reference_gate_passed": False,
        "no_reference_work_eligible": False,
        "public_cli_changed": False,
        "public_verdict_enabled": False,
    }:
        errors.append("claim boundary differs")
    replay = load_json(REPLAY)
    replay_summary = replay.get("evaluation_summary", {})
    expected_replay = {
        "case_count": replay_summary.get("case_count"),
        "source_group_count": replay_summary.get("source_group_count"),
        "partition_group_count": replay_summary.get("partition_group_count"),
        "primary_domain_count": 2,
        "synthetic_record_inventory_sha256": replay.get(
            "synthetic_record_inventory_sha256"
        ),
        "evaluation_sha256": replay.get("evaluation_sha256"),
        "compact_replay_sha256": sha256_file(REPLAY),
        "byte_identical_replay": True,
        "synthetic_statistical_gates_pass": replay_summary.get(
            "synthetic_gate_results", {}
        ).get("all_statistical_gates_pass"),
        "scientific_gate_evaluated": False,
    }
    if plan.get("synthetic_replay") != expected_replay:
        errors.append("synthetic replay projection differs")
    boundary = plan.get("access_boundary", {})
    if not isinstance(boundary, dict) or set(boundary) != {
        "synthetic_fixture_execution_authorized",
        "retained_audio_access_authorized",
        "provider_audio_access_authorized",
        "perceptual_metric_execution_authorized",
        "human_score_access_authorized",
        "human_collection_authorized",
        "no_reference_training_authorized",
        "sealed_evidence_access_authorized",
        "public_verdict_authorized",
    }:
        errors.append("plan access boundary field set differs")
        boundary = {}
    if boundary.get("synthetic_fixture_execution_authorized") is not True:
        errors.append("synthetic fixture authority differs")
    for key in (
        "retained_audio_access_authorized",
        "provider_audio_access_authorized",
        "perceptual_metric_execution_authorized",
        "human_score_access_authorized",
        "human_collection_authorized",
        "no_reference_training_authorized",
        "sealed_evidence_access_authorized",
        "public_verdict_authorized",
    ):
        if boundary.get(key) is not False:
            errors.append(f"plan access boundary must remain false: {key}")
    if plan.get("authorized_next_step") != (
        "Preserve the frozen statistical semantics. Do not evaluate scientific "
        "gates until separately authorized metric outputs and valid human-calibration "
        "targets exist; do not begin no-reference training unless every prerequisite "
        "full-reference gate passes on eligible evidence."
    ):
        errors.append("authorized next step differs")
    serialized = json.dumps(plan, sort_keys=True)
    if any(value in serialized for value in ("/Users/", "Application Support", "file://")):
        errors.append("plan contains a private path")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    replay_parser = subcommands.add_parser("synthetic-replay")
    replay_parser.add_argument("--output", type=Path)
    validate_replay_parser = subcommands.add_parser("validate-replay")
    validate_replay_parser.add_argument("--input", type=Path, default=REPLAY)
    validate_plan_parser = subcommands.add_parser("validate-plan")
    validate_plan_parser.add_argument("--plan", type=Path, default=PLAN)
    args = parser.parse_args()
    if args.command == "synthetic-replay":
        value = build_synthetic_replay()
        if args.output:
            if args.output.exists():
                raise ValueError("refusing to replace synthetic evaluation replay")
            args.output.write_bytes(canonical_bytes(value))
        else:
            sys.stdout.buffer.write(canonical_bytes(value))
        return 0
    if args.command == "validate-replay":
        errors = validate_synthetic_replay(load_json(args.input))
        status = "full_reference_synthetic_statistics_replay_valid"
    else:
        errors = validate_plan(load_json(args.plan))
        status = "full_reference_statistics_frozen_synthetic_only"
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(json.dumps({
        "status": status,
        "scientific_gate_evaluated": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
