#!/usr/bin/env python3
"""Apply the frozen grouped gates to codec-projection raw evidence."""

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


SCORE_FIELDS = (
    "r1_cycle_residual_retention",
    "r2_residual_directional_recurrence",
)
EXPECTED_CASES = 2_261
EXPECTED_NEGATIVE_CASES = 1_734
EXPECTED_POSITIVE_CASES = 527
EXPECTED_NEGATIVE_GROUPS = 597
HEX_SHA256 = re.compile(r"[0-9a-f]{64}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def write_new(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"refusing to replace output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True)
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


def wilson_bounds(successes: int, trials: int, z: float) -> tuple[float | None, float | None]:
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


def target_positive(row: dict, selection: dict) -> bool:
    class_name = row.get("class")
    return (
        row.get("expectation") == selection["positive_expectation"]
        and isinstance(class_name, str)
        and (
            class_name == selection["positive_class_exact"]
            or class_name.endswith(selection["positive_class_suffix"])
        )
    )


def domain_family(row: dict, aliases: dict[str, str]) -> str:
    value = row.get("source_domain")
    if not isinstance(value, str) or not value:
        raise ValueError(f"{row.get('case_id')}: source_domain is missing")
    return aliases.get(value, value)


def score_for(row: dict, field: str) -> float | None:
    measurement = row.get("measurement")
    support = measurement.get("support") if isinstance(measurement, dict) else None
    if not isinstance(support, dict) or not isinstance(support.get("supported"), bool):
        raise ValueError(f"{row.get('case_id')}: measurement support is invalid")
    scores = measurement.get("scores")
    if support["supported"] is False:
        if scores is not None:
            raise ValueError(f"{row.get('case_id')}: unsupported case has scores")
        return None
    value = scores.get(field) if isinstance(scores, dict) else None
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{row.get('case_id')}: {field} is invalid")
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{row.get('case_id')}: {field} is out of bounds")
    return value


def summarize_binary(units: dict[str, dict], z: float) -> dict:
    supported = [unit for unit in units.values() if unit["supported"]]
    predicted = [unit for unit in supported if unit["predicted"]]
    lower, upper = wilson_bounds(len(predicted), len(supported), z)
    return {
        "total_count": len(units),
        "supported_count": len(supported),
        "support_coverage": ratio(len(supported), len(units)),
        "predicted_count": len(predicted),
        "predicted_rate": ratio(len(predicted), len(supported)),
        "one_sided_95_wilson_lower": lower,
        "one_sided_95_wilson_upper": upper,
    }


def case_outcomes(rows: list[dict], field: str, threshold: float, selection: dict) -> tuple[dict, dict]:
    negatives: dict[str, dict] = {}
    positives: dict[str, dict] = {}
    for row in rows:
        score = score_for(row, field)
        outcome = {
            "supported": score is not None,
            "predicted": score is not None and score >= threshold,
            "score": score,
        }
        if row.get("expectation") == selection["negative_expectation"]:
            negatives[row["case_id"]] = outcome
        elif target_positive(row, selection):
            positives[row["case_id"]] = outcome
    return negatives, positives


def group_outcomes(
    rows: list[dict], field: str, threshold: float, selection: dict
) -> tuple[dict[str, dict], dict[str, dict]]:
    negative_rows: dict[str, list[dict]] = defaultdict(list)
    positive_rows: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("expectation") == selection["negative_expectation"]:
            negative_rows[row["source_group"]].append(row)
        elif target_positive(row, selection):
            positive_rows[row["source_group"]].append(row)
    negatives = {}
    for source_group, grouped_rows in negative_rows.items():
        scores = [score_for(row, field) for row in grouped_rows]
        supported = [score for score in scores if score is not None]
        negatives[source_group] = {
            "supported": bool(supported),
            "predicted": any(score >= threshold for score in supported),
            "score": max(supported) if supported else None,
        }
    positives = {}
    for source_group, grouped_rows in positive_rows.items():
        scores = [score_for(row, field) for row in grouped_rows]
        supported = [score for score in scores if score is not None]
        group_score = statistics.median(supported) if supported else None
        positives[source_group] = {
            "supported": group_score is not None,
            "predicted": group_score is not None and group_score >= threshold,
            "score": group_score,
        }
    return negatives, positives


def domain_distribution(rows: list[dict], field: str, selection: dict, aliases: dict[str, str]) -> list[dict]:
    output = []
    domains = sorted({domain_family(row, aliases) for row in rows})
    for domain in domains:
        domain_rows = [row for row in rows if domain_family(row, aliases) == domain]
        for population in ("negative", "target_positive"):
            if population == "negative":
                scoped = [
                    row
                    for row in domain_rows
                    if row.get("expectation") == selection["negative_expectation"]
                ]
            else:
                scoped = [row for row in domain_rows if target_positive(row, selection)]
            scores = [score_for(row, field) for row in scoped]
            supported = [score for score in scores if score is not None]
            output.append(
                {
                    "source_domain": domain,
                    "population": population,
                    "case_count": len(scoped),
                    "supported_case_count": len(supported),
                    "support_coverage": ratio(len(supported), len(scoped)),
                    "score_minimum": min(supported) if supported else None,
                    "score_q25": quantile(supported, 0.25),
                    "score_median": quantile(supported, 0.5),
                    "score_q75": quantile(supported, 0.75),
                    "score_maximum": max(supported) if supported else None,
                }
            )
    return output


def evaluate_representation(rows: list[dict], field: str, config: dict) -> tuple[dict, dict]:
    selection = config["selection"]
    criteria = config["evaluation"]
    aliases = criteria["domain_family_aliases"]
    z = float(criteria["one_sided_95_z"])
    domains = sorted({domain_family(row, aliases) for row in rows})
    group_domains: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        group_domains[row["source_group"]].add(domain_family(row, aliases))
    crossing = [group for group, values in group_domains.items() if len(values) != 1]
    if crossing:
        raise ValueError(f"source group crosses domain families: {crossing[0]}")

    pooled_negative_cases: dict[str, dict] = {}
    pooled_positive_cases: dict[str, dict] = {}
    pooled_negative_groups: dict[str, dict] = {}
    pooled_positive_groups: dict[str, dict] = {}
    folds = []
    for held_domain in domains:
        training_negatives = [
            row
            for row in rows
            if domain_family(row, aliases) != held_domain
            and row.get("expectation") == selection["negative_expectation"]
        ]
        candidates = [score_for(row, field) for row in training_negatives]
        supported_candidates = [score for score in candidates if score is not None]
        if not supported_candidates:
            folds.append(
                {
                    "held_out_source_domain": held_domain,
                    "valid": False,
                    "reason": "no_supported_training_negative",
                }
            )
            continue
        maximum = max(supported_candidates)
        threshold = math.nextafter(maximum, math.inf)
        held = [row for row in rows if domain_family(row, aliases) == held_domain]
        negative_cases, positive_cases = case_outcomes(held, field, threshold, selection)
        negative_groups, positive_groups = group_outcomes(held, field, threshold, selection)
        for label, pooled, observed in (
            ("negative case", pooled_negative_cases, negative_cases),
            ("positive case", pooled_positive_cases, positive_cases),
            ("negative group", pooled_negative_groups, negative_groups),
            ("positive group", pooled_positive_groups, positive_groups),
        ):
            overlap = pooled.keys() & observed.keys()
            if overlap:
                raise ValueError(f"{label} crosses held-out domains: {min(overlap)}")
            pooled.update(observed)
        folds.append(
            {
                "held_out_source_domain": held_domain,
                "valid": True,
                "training_supported_negative_case_count": len(supported_candidates),
                "training_maximum_negative_score": maximum,
                "threshold_inclusive": threshold,
                "negative_cases": summarize_binary(negative_cases, z),
                "negative_groups": summarize_binary(negative_groups, z),
                "target_positive_cases": summarize_binary(positive_cases, z),
                "target_positive_groups": summarize_binary(positive_groups, z),
            }
        )
    valid_folds = [fold for fold in folds if fold["valid"]]
    negative_cases = summarize_binary(pooled_negative_cases, z)
    positive_cases = summarize_binary(pooled_positive_cases, z)
    negative_groups = summarize_binary(pooled_negative_groups, z)
    positive_groups = summarize_binary(pooled_positive_groups, z)
    domain_gates = []
    for fold in valid_folds:
        positives = fold["target_positive_groups"]
        rule_applies = (
            positives["total_count"]
            >= criteria["minimum_domain_target_source_groups"]
        )
        domain_gates.append(
            {
                "source_domain": fold["held_out_source_domain"],
                "minimum_group_rule_applies": rule_applies,
                "support_passed": not rule_applies
                or (
                    positives["support_coverage"] is not None
                    and positives["support_coverage"]
                    >= criteria["minimum_positive_group_support"]
                ),
                "recall_passed": not rule_applies
                or (
                    positives["predicted_rate"] is not None
                    and positives["predicted_rate"]
                    >= criteria["minimum_domain_recall"]
                ),
            }
        )
    all_folds_valid = len(valid_folds) == len(domains)
    false_positive_passed = (
        negative_cases["predicted_count"] == 0
        and negative_groups["predicted_count"] == 0
        and negative_groups["one_sided_95_wilson_upper"] is not None
        and negative_groups["one_sided_95_wilson_upper"]
        <= criteria["maximum_negative_one_sided_95_wilson_upper"]
    )
    support_passed = (
        positive_groups["support_coverage"] is not None
        and positive_groups["support_coverage"]
        >= criteria["minimum_positive_group_support"]
        and all(gate["support_passed"] for gate in domain_gates)
    )
    recall_passed = (
        positive_groups["predicted_rate"] is not None
        and positive_groups["predicted_rate"] >= criteria["minimum_overall_recall"]
        and positive_groups["one_sided_95_wilson_lower"] is not None
        and positive_groups["one_sided_95_wilson_lower"]
        >= criteria["minimum_overall_one_sided_95_wilson_lower"]
        and all(gate["recall_passed"] for gate in domain_gates)
    )
    gates = {
        "all_folds_valid": all_folds_valid,
        "false_positive_control_passed": false_positive_passed,
        "support_coverage_passed": support_passed,
        "recall_passed": recall_passed,
        "passed": all_folds_valid
        and false_positive_passed
        and support_passed
        and recall_passed,
    }
    public = {
        "score_field": field,
        "threshold_direction": criteria["threshold_direction"],
        "folds": folds,
        "pooled_out_of_fold": {
            "negative_cases": negative_cases,
            "negative_groups": negative_groups,
            "target_positive_cases": positive_cases,
            "target_positive_groups": positive_groups,
        },
        "domain_distributions": domain_distribution(rows, field, selection, aliases),
        "domain_gates": domain_gates,
        "gates": gates,
    }
    internal = {
        "negative_cases": pooled_negative_cases,
        "positive_cases": pooled_positive_cases,
        "negative_groups": pooled_negative_groups,
        "positive_groups": pooled_positive_groups,
    }
    return public, internal


def pearson(first: list[float], second: list[float]) -> float | None:
    if len(first) != len(second):
        raise ValueError("correlation vectors differ in length")
    if len(first) < 2:
        return None
    first_mean = statistics.fmean(first)
    second_mean = statistics.fmean(second)
    numerator = sum(
        (left - first_mean) * (right - second_mean)
        for left, right in zip(first, second, strict=True)
    )
    first_power = sum((value - first_mean) ** 2 for value in first)
    second_power = sum((value - second_mean) ** 2 for value in second)
    denominator = math.sqrt(first_power * second_power)
    return numerator / denominator if denominator else None


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average = (start + 1 + end) / 2.0
        for position in range(start, end):
            ranks[order[position]] = average
        start = end
    return ranks


def correlations(rows: list[dict]) -> dict:
    case_pairs = []
    for row in sorted(rows, key=lambda value: value["case_id"]):
        first = score_for(row, SCORE_FIELDS[0])
        second = score_for(row, SCORE_FIELDS[1])
        if first is not None and second is not None:
            case_pairs.append((first, second))
    group_populations: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        population = "negative" if row.get("expectation") == "negative" else "target_positive"
        group_populations[(population, row["source_group"])].append(row)
    group_pairs = []
    for (population, _), grouped_rows in sorted(group_populations.items()):
        first = [score_for(row, SCORE_FIELDS[0]) for row in grouped_rows]
        second = [score_for(row, SCORE_FIELDS[1]) for row in grouped_rows]
        first_supported = [value for value in first if value is not None]
        second_supported = [value for value in second if value is not None]
        if not first_supported or not second_supported:
            continue
        aggregate = max if population == "negative" else statistics.median
        group_pairs.append((aggregate(first_supported), aggregate(second_supported)))

    def summarize(pairs: list[tuple[float, float]]) -> dict:
        first = [pair[0] for pair in pairs]
        second = [pair[1] for pair in pairs]
        return {
            "paired_count": len(pairs),
            "pearson": pearson(first, second),
            "spearman": pearson(average_ranks(first), average_ranks(second)),
        }

    return {
        "cases": summarize(case_pairs),
        "groups": {
            **summarize(group_pairs),
            "aggregation": "negative_maximum_or_target_positive_median",
        },
    }


def overlap_counts(first: dict[str, dict], second: dict[str, dict], failure: str) -> dict:
    keys = first.keys() & second.keys()

    def failed(value: dict) -> bool:
        if failure == "negative_alert":
            return value["supported"] and value["predicted"]
        if failure == "positive_miss":
            return value["supported"] and not value["predicted"]
        if failure == "unsupported":
            return not value["supported"]
        raise ValueError(f"unknown overlap failure: {failure}")

    first_failed = {key for key in keys if failed(first[key])}
    second_failed = {key for key in keys if failed(second[key])}
    return {
        "paired_count": len(keys),
        "both": len(first_failed & second_failed),
        "r1_only": len(first_failed - second_failed),
        "r2_only": len(second_failed - first_failed),
        "neither": len(keys - first_failed - second_failed),
    }


def failure_overlap(internal: dict[str, dict]) -> dict:
    first = internal[SCORE_FIELDS[0]]
    second = internal[SCORE_FIELDS[1]]
    return {
        "negative_case_alerts": overlap_counts(
            first["negative_cases"], second["negative_cases"], "negative_alert"
        ),
        "negative_group_alerts": overlap_counts(
            first["negative_groups"], second["negative_groups"], "negative_alert"
        ),
        "target_positive_case_misses": overlap_counts(
            first["positive_cases"], second["positive_cases"], "positive_miss"
        ),
        "target_positive_group_misses": overlap_counts(
            first["positive_groups"], second["positive_groups"], "positive_miss"
        ),
        "negative_group_unsupported": overlap_counts(
            first["negative_groups"], second["negative_groups"], "unsupported"
        ),
        "target_positive_group_unsupported": overlap_counts(
            first["positive_groups"], second["positive_groups"], "unsupported"
        ),
    }


def validate_rows(raw: dict, config: dict) -> list[dict]:
    if (
        raw.get("schema_version") != 1
        or raw.get("state") != "codec_projection_observed_raw_v1"
        or raw.get("feature_version") != 0
        or raw.get("future_codec_only_opened") is not False
        or raw.get("release_heldout_opened") is not False
        or raw.get("public_verdict_enabled") is not False
    ):
        raise ValueError("raw report gate state differs")
    selection_summary = raw.get("selection")
    if (
        not isinstance(selection_summary, dict)
        or selection_summary.get("case_count") != EXPECTED_CASES
        or selection_summary.get("negative_case_count") != EXPECTED_NEGATIVE_CASES
        or selection_summary.get("target_positive_case_count")
        != EXPECTED_POSITIVE_CASES
        or selection_summary.get("negative_source_group_count")
        != EXPECTED_NEGATIVE_GROUPS
    ):
        raise ValueError("raw report selection summary differs")
    rows = raw.get("results")
    if not isinstance(rows, list) or len(rows) != EXPECTED_CASES:
        raise ValueError("raw report case inventory differs")
    ids = [row.get("case_id") for row in rows if isinstance(row, dict)]
    if len(ids) != len(rows) or len(set(ids)) != len(ids) or any(not value for value in ids):
        raise ValueError("raw report case IDs are missing or duplicated")
    selection = config["selection"]
    negatives = [row for row in rows if row.get("expectation") == "negative"]
    positives = [row for row in rows if target_positive(row, selection)]
    if len(negatives) != EXPECTED_NEGATIVE_CASES or len(positives) != EXPECTED_POSITIVE_CASES:
        raise ValueError("raw report selected populations differ")
    if len({row["source_group"] for row in negatives}) != EXPECTED_NEGATIVE_GROUPS:
        raise ValueError("raw report negative source-group inventory differs")
    for row in rows:
        if any(
            not isinstance(row.get(field), str) or not row[field]
            for field in (
                "case_id",
                "audio_sha256",
                "source_group",
                "partition_group",
                "source_domain",
                "class",
                "expectation",
                "provenance_tier",
            )
        ) or not HEX_SHA256.fullmatch(row["audio_sha256"]):
            raise ValueError(f"{row.get('case_id')}: raw row metadata differs")
        measurement = row.get("measurement")
        if (
            not isinstance(measurement, dict)
            or measurement.get("schema_version") != 1
            or measurement.get("state") != "codec_projection_raw_case_v1"
            or measurement.get("feature_version") != 0
            or measurement.get("case_id") != row["case_id"]
            or measurement.get("public_verdict_enabled") is not False
            or measurement.get("algorithm") != config["algorithm"]
        ):
            raise ValueError(f"{row['case_id']}: measurement binding differs")
        for field in SCORE_FIELDS:
            score_for(row, field)
    return rows


def audio_inventory_sha256(rows: list[dict]) -> str:
    payload = [
        [row["case_id"], row["audio_sha256"]]
        for row in sorted(rows, key=lambda value: value["case_id"])
    ]
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def measurement_commitments(raw: dict, input_hashes: dict) -> dict:
    commitments = raw.get("commitments")
    required_sha256 = (
        "manifest_sha256",
        "baseline_report_sha256",
        "config_sha256",
        "preregistration_sha256",
        "oracle_sha256",
        "harness_sha256",
        "ffmpeg_sha256",
        "lame_cli_sha256",
        "linked_libmp3lame_sha256",
    )
    if not isinstance(commitments, dict) or any(
        not isinstance(commitments.get(field), str)
        or not HEX_SHA256.fullmatch(commitments[field])
        for field in required_sha256
    ):
        raise ValueError("raw measurement commitments differ")
    repository_commit = commitments.get("repository_commit")
    if not isinstance(repository_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", repository_commit
    ):
        raise ValueError("raw repository commitment differs")
    if (
        commitments["config_sha256"] != input_hashes["config_sha256"]
        or commitments["preregistration_sha256"]
        != input_hashes["preregistration_sha256"]
    ):
        raise ValueError("raw report does not bind the analyzed config and preregistration")
    return {field: commitments[field] for field in ("repository_commit", *required_sha256)}


def assert_path_free(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"path", "case_id", "relative_path", "corpus_root"}:
                raise ValueError(f"aggregate contains private key: {key}")
            assert_path_free(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_path_free(nested)
    elif isinstance(value, str):
        if value.startswith("/") or value.startswith("file:"):
            raise ValueError("aggregate contains an absolute path")


def analyze(raw: dict, config: dict, input_hashes: dict) -> dict:
    rows = validate_rows(raw, config)
    bound_measurement = measurement_commitments(raw, input_hashes)
    evaluations = {}
    internal = {}
    for field in SCORE_FIELDS:
        evaluations[field], internal[field] = evaluate_representation(rows, field, config)
    survivors = [field for field in SCORE_FIELDS if evaluations[field]["gates"]["passed"]]
    result = {
        "schema_version": 1,
        "state": "codec_projection_observed_evaluation_v1",
        "feature_version": 0,
        "candidate_frozen": False,
        "independent_validation": False,
        "future_codec_only_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "warning": (
            "Consumed development evidence only. No result authorizes a "
            "lossy-source, authenticity, codec, or provenance verdict."
        ),
        "inputs": {
            "evaluation_artifacts": input_hashes,
            "measurement_commitments": bound_measurement,
            "audio_inventory_sha256": audio_inventory_sha256(rows),
        },
        "criteria": config["evaluation"],
        "inventory": {
            "case_count": len(rows),
            "negative_case_count": EXPECTED_NEGATIVE_CASES,
            "target_positive_case_count": EXPECTED_POSITIVE_CASES,
            "negative_source_group_count": EXPECTED_NEGATIVE_GROUPS,
            "source_domain_family_count": len(
                {
                    domain_family(row, config["evaluation"]["domain_family_aliases"])
                    for row in rows
                }
            ),
        },
        "representations": evaluations,
        "correlations": correlations(rows),
        "failure_overlap": failure_overlap(internal),
        "surviving_representations": survivors,
        "disposition": {
            "direction_status": "observed_screen_passed" if survivors else "rejected",
            "robustness_authorized": bool(survivors),
            "external_transfer_authorized": False,
            "public_integration_authorized": False,
            "reason": (
                "At least one fixed representation passed every observed gate; "
                "only the preregistered robustness stage may proceed."
                if survivors
                else "Neither fixed representation passed every observed gate; stop this direction."
            ),
        },
    }
    assert_path_free(result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-report", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        raw = args.raw_report.expanduser().resolve()
        config_path = args.config.expanduser().resolve()
        preregistration = args.preregistration.expanduser().resolve()
        output = args.output.expanduser().resolve()
        analyzer = Path(__file__).resolve()
        for path in (raw, config_path, preregistration, analyzer):
            if not path.is_file():
                raise ValueError(f"required file is missing: {path}")
        config = load_object(config_path)
        value = analyze(
            load_object(raw),
            config,
            {
                "raw_report_sha256": sha256_file(raw),
                "config_sha256": sha256_file(config_path),
                "preregistration_sha256": sha256_file(preregistration),
                "analyzer_sha256": sha256_file(analyzer),
            },
        )
        write_new(output, value)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(
        f"wrote path-free evaluation with {len(value['surviving_representations'])} "
        f"surviving representations to {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
