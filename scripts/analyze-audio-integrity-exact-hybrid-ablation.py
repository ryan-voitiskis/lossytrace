#!/usr/bin/env python3
"""Evaluate fixed exact-hybrid ablations with leave-one-domain-out folds."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import tempfile
from collections import defaultdict
from pathlib import Path


EDGE_DROP_EXCLUSIVE = 3.0
EDGE_PERSISTENCE_INCLUSIVE = 0.0015
MIN_SUPPORT_COVERAGE = 0.75
MIN_OVERALL_RECALL = 0.90
MIN_OVERALL_RECALL_LOWER = 0.85
MIN_DOMAIN_RECALL = 0.85
MAX_NEGATIVE_ALERT_UPPER = 0.025
MIN_DOMAIN_GROUPS = 10
ONE_SIDED_95_Z = 1.6448536269514722
TARGET_CLASS_SUFFIXES = ("mp3_128", "_mp3_128_to_flac16")
DOMAIN_FAMILY_ALIASES = {
    "public_tier_a_originals": "public_tier_a",
    "public_tier_a_controlled": "public_tier_a",
}
SCORE_FIELDS = {
    "a0_archived_replay": "a0_replay_selected_small_fraction_1e4",
    "a1_subband_relative": "a1_phase_zero_subband_relative_small_fraction_1e2",
    "a2_time_median": "a2_phase_zero_time_median_small_fraction_1e2",
    "a3_phase_stable": "a3_phase_stable_small_fraction_1e2",
    "a4_content_guarded": "a4_content_guarded_small_fraction_1e2",
}


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
        json.dump(value, output, indent=2, sort_keys=True)
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


def wilson_bounds(successes: int, trials: int) -> tuple[float | None, float | None]:
    if trials == 0:
        return None, None
    proportion = successes / trials
    z2 = ONE_SIDED_95_Z**2
    denominator = 1 + z2 / trials
    center = (proportion + z2 / (2 * trials)) / denominator
    spread = (
        ONE_SIDED_95_Z
        * math.sqrt(
            proportion * (1 - proportion) / trials + z2 / (4 * trials**2)
        )
        / denominator
    )
    return max(0.0, center - spread), min(1.0, center + spread)


def target_positive(row: dict) -> bool:
    class_name = row.get("class")
    return (
        row.get("expectation") == "controlled_positive"
        and isinstance(class_name, str)
        and (class_name == TARGET_CLASS_SUFFIXES[0] or class_name.endswith(TARGET_CLASS_SUFFIXES[1]))
    )


def source_domain_family(row: dict) -> str:
    source_domain = row.get("source_domain")
    if not isinstance(source_domain, str) or not source_domain:
        raise ValueError(f"{row.get('case_id')}: source_domain is missing")
    return DOMAIN_FAMILY_ALIASES.get(source_domain, source_domain)


def score_for(row: dict, field: str) -> float | None:
    probe = row.get("probe")
    aggregate = probe.get("aggregate") if isinstance(probe, dict) else None
    value = aggregate.get(field) if isinstance(aggregate, dict) else None
    if value is None:
        return None
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{row.get('case_id')}: invalid {field}")
    return float(value)


def edge_passed(row: dict) -> bool:
    edge = row.get("baseline_edge")
    drop = edge.get("spectral_edge_drop_db") if isinstance(edge, dict) else None
    persistence = (
        edge.get("spectral_edge_persistence") if isinstance(edge, dict) else None
    )
    return (
        isinstance(drop, (int, float))
        and math.isfinite(drop)
        and isinstance(persistence, (int, float))
        and math.isfinite(persistence)
        and drop > EDGE_DROP_EXCLUSIVE
        and persistence >= EDGE_PERSISTENCE_INCLUSIVE
    )


def eligible_negative(row: dict) -> bool:
    tier = row.get("provenance_tier")
    return row.get("expectation") == "negative" and isinstance(tier, str) and (
        tier.startswith("tier_a") or tier.startswith("tier_b")
    )


def group_outcomes(
    rows: list[dict], field: str, threshold: float, expectation: str
) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if expectation == "negative" and not eligible_negative(row):
            continue
        if expectation == "controlled_positive" and not target_positive(row):
            continue
        grouped[row["source_group"]].append(row)
    output = {}
    for source_group, group_rows in grouped.items():
        scored = [(row, score_for(row, field)) for row in group_rows]
        supported = [(row, score) for row, score in scored if score is not None]
        predicted = any(
            edge_passed(row) and score >= threshold for row, score in supported
        )
        output[source_group] = {
            "supported": bool(supported),
            "predicted": predicted,
            "case_count": len(group_rows),
        }
    return output


def summarize_groups(groups: dict[str, dict]) -> dict:
    supported = [group for group in groups.values() if group["supported"]]
    predicted = [group for group in supported if group["predicted"]]
    lower, upper = wilson_bounds(len(predicted), len(supported))
    return {
        "total_source_group_count": len(groups),
        "supported_source_group_count": len(supported),
        "support_coverage": ratio(len(supported), len(groups)),
        "predicted_source_group_count": len(predicted),
        "predicted_rate": ratio(len(predicted), len(supported)),
        "one_sided_95_wilson_lower": lower,
        "one_sided_95_wilson_upper": upper,
    }


def summarize_cases(
    rows: list[dict], field: str, threshold: float, expectation: str
) -> dict:
    selected = []
    for row in rows:
        if expectation == "negative" and not eligible_negative(row):
            continue
        if expectation == "controlled_positive" and not target_positive(row):
            continue
        selected.append(row)
    scored = [(row, score_for(row, field)) for row in selected]
    supported = [(row, score) for row, score in scored if score is not None]
    predicted = [
        row
        for row, score in supported
        if edge_passed(row) and score >= threshold
    ]
    return {
        "total_case_count": len(selected),
        "supported_case_count": len(supported),
        "support_coverage": ratio(len(supported), len(selected)),
        "predicted_case_count": len(predicted),
        "predicted_rate": ratio(len(predicted), len(supported)),
    }


def evaluate_row(rows: list[dict], field: str) -> dict:
    group_domains: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        group_domains[row["source_group"]].add(source_domain_family(row))
    crossing = sorted(
        source_group
        for source_group, domain_families in group_domains.items()
        if len(domain_families) != 1
    )
    if crossing:
        raise ValueError(
            f"source group crosses canonical domain families: {crossing[0]}"
        )
    domains = sorted({source_domain_family(row) for row in rows})
    folds = []
    pooled_negative_groups: dict[str, dict] = {}
    pooled_positive_groups: dict[str, dict] = {}
    pooled_negative_cases = {
        "total_case_count": 0,
        "supported_case_count": 0,
        "predicted_case_count": 0,
    }
    pooled_positive_cases = {
        "total_case_count": 0,
        "supported_case_count": 0,
        "predicted_case_count": 0,
    }
    negative_classes: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total_case_count": 0, "supported_case_count": 0, "predicted_case_count": 0}
    )
    for held_domain in domains:
        training = [
            row for row in rows if source_domain_family(row) != held_domain
        ]
        threshold_candidates = [
            score
            for row in training
            if eligible_negative(row) and edge_passed(row)
            for score in [score_for(row, field)]
            if score is not None
        ]
        if not threshold_candidates:
            folds.append(
                {
                    "held_out_source_domain": held_domain,
                    "valid": False,
                    "reason": "no supported edge-gated Tier A/B training negative",
                }
            )
            continue
        training_maximum = max(threshold_candidates)
        threshold = math.nextafter(training_maximum, math.inf)
        held = [row for row in rows if source_domain_family(row) == held_domain]
        negatives = group_outcomes(held, field, threshold, "negative")
        positives = group_outcomes(held, field, threshold, "controlled_positive")
        negative_cases = summarize_cases(held, field, threshold, "negative")
        positive_cases = summarize_cases(
            held, field, threshold, "controlled_positive"
        )
        for pooled, summary in (
            (pooled_negative_cases, negative_cases),
            (pooled_positive_cases, positive_cases),
        ):
            for count_field in (
                "total_case_count",
                "supported_case_count",
                "predicted_case_count",
            ):
                pooled[count_field] += summary[count_field]
        for row in held:
            if not eligible_negative(row):
                continue
            summary = negative_classes[row["class"]]
            summary["total_case_count"] += 1
            score = score_for(row, field)
            if score is not None:
                summary["supported_case_count"] += 1
                if edge_passed(row) and score >= threshold:
                    summary["predicted_case_count"] += 1
        overlap = pooled_negative_groups.keys() & negatives.keys()
        if overlap:
            raise ValueError(f"source group crosses source domains: {min(overlap)}")
        pooled_negative_groups.update(negatives)
        pooled_positive_groups.update(positives)
        negative_summary = summarize_groups(negatives)
        positive_summary = summarize_groups(positives)
        folds.append(
            {
                "held_out_source_domain": held_domain,
                "valid": True,
                "training_edge_gated_negative_case_count": len(threshold_candidates),
                "training_maximum_negative_score": training_maximum,
                "threshold_inclusive": threshold,
                "negative_cases": negative_cases,
                "negative_groups": negative_summary,
                "target_positive_cases": positive_cases,
                "target_positive_groups": positive_summary,
            }
        )
    valid_folds = [fold for fold in folds if fold["valid"]]
    negative = summarize_groups(pooled_negative_groups)
    positive = summarize_groups(pooled_positive_groups)
    for pooled in (pooled_negative_cases, pooled_positive_cases):
        pooled["support_coverage"] = ratio(
            pooled["supported_case_count"], pooled["total_case_count"]
        )
        pooled["predicted_rate"] = ratio(
            pooled["predicted_case_count"], pooled["supported_case_count"]
        )
    domain_gates = []
    for fold in valid_folds:
        summary = fold["target_positive_groups"]
        enough = summary["total_source_group_count"] >= MIN_DOMAIN_GROUPS
        domain_gates.append(
            {
                "source_domain": fold["held_out_source_domain"],
                "minimum_group_rule_applies": enough,
                "support_passed": not enough
                or (
                    summary["support_coverage"] is not None
                    and summary["support_coverage"] >= MIN_SUPPORT_COVERAGE
                ),
                "recall_passed": not enough
                or (
                    summary["predicted_rate"] is not None
                    and summary["predicted_rate"] >= MIN_DOMAIN_RECALL
                ),
            }
        )
    false_positive_passed = (
        pooled_negative_cases["predicted_case_count"] == 0
        and negative["predicted_source_group_count"] == 0
        and negative["one_sided_95_wilson_upper"] is not None
        and negative["one_sided_95_wilson_upper"] <= MAX_NEGATIVE_ALERT_UPPER
    )
    support_passed = (
        positive["support_coverage"] is not None
        and positive["support_coverage"] >= MIN_SUPPORT_COVERAGE
        and all(gate["support_passed"] for gate in domain_gates)
    )
    recall_passed = (
        positive["predicted_rate"] is not None
        and positive["predicted_rate"] >= MIN_OVERALL_RECALL
        and positive["one_sided_95_wilson_lower"] is not None
        and positive["one_sided_95_wilson_lower"] >= MIN_OVERALL_RECALL_LOWER
        and all(gate["recall_passed"] for gate in domain_gates)
    )
    return {
        "score_field": field,
        "threshold_direction": "higher_or_equal_is_more_mp3_like",
        "folds": folds,
        "pooled_out_of_fold": {
            "negative_cases": pooled_negative_cases,
            "negative_groups": negative,
            "negative_cases_by_class": dict(sorted(negative_classes.items())),
            "target_positive_cases": pooled_positive_cases,
            "target_positive_groups": positive,
        },
        "domain_gates": domain_gates,
        "gates": {
            "all_folds_valid": len(valid_folds) == len(domains),
            "false_positive_control_passed": false_positive_passed,
            "support_coverage_passed": support_passed,
            "recall_passed": recall_passed,
            "passed": len(valid_folds) == len(domains)
            and false_positive_passed
            and support_passed
            and recall_passed,
        },
    }


def validate_replay(replay: dict, ablation_report_sha256: str) -> None:
    replay_result = replay.get("replay")
    replay_inputs = replay.get("inputs")
    if (
        replay.get("schema_version") != 1
        or replay.get("feature_version") != 0
        or replay.get("public_verdict_enabled") is not False
        or not isinstance(replay_result, dict)
        or replay_result.get("passed") is not True
        or replay_result.get("mismatch_case_count") != 0
        or not isinstance(replay_inputs, dict)
        or replay_inputs.get("ablation_report_sha256") != ablation_report_sha256
    ):
        raise ValueError("exact-hybrid replay gate did not pass for this ablation report")


def analyze(
    manifest: dict, baseline: dict, ablation: dict, replay: dict, hashes: dict
) -> dict:
    if (
        manifest.get("schema_version") != 1
        or manifest.get("evidence_partition") != "observed_development"
        or manifest.get("holdout_scores_opened") is not False
    ):
        raise ValueError("manifest gate state differs")
    baseline_gate = baseline.get("gate_disposition")
    if (
        baseline.get("schema_version") != 1
        or baseline.get("feature_version") != 0
        or not isinstance(baseline_gate, dict)
        or baseline_gate.get("likely_lossy_derived_enabled") is not False
    ):
        raise ValueError("baseline gate state differs")
    if (
        ablation.get("schema_version") != 1
        or ablation.get("feature_version") != 0
        or ablation.get("future_codec_only_opened") is not False
        or ablation.get("release_heldout_opened") is not False
        or ablation.get("public_verdict_enabled") is not False
    ):
        raise ValueError("ablation gate state differs")
    validate_replay(replay, hashes["ablation_report_sha256"])
    rows = ablation.get("results")
    if not isinstance(rows, list) or not rows:
        raise ValueError("ablation results must be a non-empty array")
    case_ids = [row.get("case_id") for row in rows]
    if len(set(case_ids)) != len(case_ids) or any(not case_id for case_id in case_ids):
        raise ValueError("ablation case IDs must be present and unique")
    expected = {
        case["case_id"]
        for case in manifest.get("cases", [])
        if case.get("expectation") == "negative"
        or (
            case.get("expectation") == "controlled_positive"
            and isinstance(case.get("class"), str)
            and (
                case["class"] == TARGET_CLASS_SUFFIXES[0]
                or case["class"].endswith(TARGET_CLASS_SUFFIXES[1])
            )
        )
    }
    if set(case_ids) != expected:
        raise ValueError("ablation selection differs from the preregistration")
    for row in rows:
        if row.get("probe", {}).get("public_verdict_enabled") is not False:
            raise ValueError(f"{row.get('case_id')}: probe verdict state differs")
    elapsed = []
    for row in rows:
        value = row["probe"].get("elapsed_ms")
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{row.get('case_id')}: probe elapsed_ms is invalid")
        elapsed.append(float(value))
    evaluations = {
        name: evaluate_row(rows, field) for name, field in SCORE_FIELDS.items()
    }
    return {
        "schema_version": 1,
        "state": "observed_development_exact_hybrid_ablation_evaluation",
        "feature_version": 0,
        "independent_validation": False,
        "future_codec_only_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "inputs": hashes,
        "criteria": {
            "edge_drop_db_exclusive": EDGE_DROP_EXCLUSIVE,
            "edge_persistence_inclusive": EDGE_PERSISTENCE_INCLUSIVE,
            "minimum_support_coverage": MIN_SUPPORT_COVERAGE,
            "minimum_overall_recall": MIN_OVERALL_RECALL,
            "minimum_overall_one_sided_95_wilson_lower": MIN_OVERALL_RECALL_LOWER,
            "minimum_domain_recall": MIN_DOMAIN_RECALL,
            "maximum_negative_one_sided_95_wilson_upper": MAX_NEGATIVE_ALERT_UPPER,
            "minimum_domain_target_source_groups": MIN_DOMAIN_GROUPS,
        },
        "inventory": {
            "case_count": len(rows),
            "source_group_count": len({row["source_group"] for row in rows}),
            "source_domain_family_count": len(
                {source_domain_family(row) for row in rows}
            ),
            "negative_case_count": sum(eligible_negative(row) for row in rows),
            "target_positive_case_count": sum(target_positive(row) for row in rows),
        },
        "research_probe_runtime": {
            "case_count": len(elapsed),
            "median_elapsed_ms": statistics.median(elapsed),
            "p95_elapsed_ms": quantile(elapsed, 0.95),
            "interpretation": (
                "Eight-phase standalone research measurement only; this is not "
                "the frozen in-process runtime-overhead gate."
            ),
        },
        "ablations": evaluations,
        "surviving_rows": [
            name for name, evaluation in evaluations.items() if evaluation["gates"]["passed"]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--baseline-report", type=Path, required=True)
    parser.add_argument("--ablation-report", type=Path, required=True)
    parser.add_argument("--replay-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = args.manifest.expanduser().resolve()
        baseline = args.baseline_report.expanduser().resolve()
        ablation = args.ablation_report.expanduser().resolve()
        replay = args.replay_report.expanduser().resolve()
        output = args.output.expanduser().resolve()
        value = analyze(
            load_object(manifest),
            load_object(baseline),
            load_object(ablation),
            load_object(replay),
            {
                "manifest_sha256": sha256_file(manifest),
                "baseline_report_sha256": sha256_file(baseline),
                "ablation_report_sha256": sha256_file(ablation),
                "replay_report_sha256": sha256_file(replay),
            },
        )
        write_new(output, value)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(
        f"wrote path-free ablation evaluation with "
        f"{len(value['surviving_rows'])} surviving rows to {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
