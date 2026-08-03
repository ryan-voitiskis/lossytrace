#!/usr/bin/env python3
"""Create a path-free paired atlas for retained v2 explainable controls."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import audio_integrity_v2_baseline_common as common
import run_audio_integrity_v2_explainable_controls as runner


MINIMUM_DIRECTION_RATE = 0.90
MINIMUM_DIRECTION_WILSON_LOWER = 0.85
MINIMUM_DOMAIN_DIRECTION_RATE_EXCLUSIVE = 0.50


def scoped_pcm_representatives(
    cases: list[dict[str, Any]], *, enforce_frozen_inventory: bool = False
) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in cases:
        key = row["_analysis_pcm_sha256"]
        previous = selected.get(key)
        if previous is None or row["case_id"] < previous["case_id"]:
            selected[key] = row
    output = sorted(selected.values(), key=lambda row: row["case_id"])
    if enforce_frozen_inventory and len(output) != runner.EXPECTED_UNIQUE_PCM_COUNT:
        raise ValueError("scoped unique-PCM inventory differs")
    return output


def negative_history_class(row: dict[str, Any]) -> str:
    transforms = row.get("post_transform_ids", [])
    return transforms[0] if transforms else row.get("history_class", "pcm_reference")


def support_summary(
    cases: list[dict[str, Any]], scores: dict[str, float]
) -> dict[str, Any]:
    unique = scoped_pcm_representatives(cases)
    groups: dict[str, set[str]] = defaultdict(set)
    for row in cases:
        groups[row["source_group"]].add(row["_analysis_pcm_sha256"])
    supported_groups = sum(any(pcm in scores for pcm in pcms) for pcms in groups.values())
    return {
        "factorial_case_count": len(cases),
        "supported_factorial_case_count": sum(
            row["_analysis_pcm_sha256"] in scores for row in cases
        ),
        "factorial_case_support_rate": sum(
            row["_analysis_pcm_sha256"] in scores for row in cases
        )
        / len(cases)
        if cases
        else None,
        "unique_analysis_pcm_count": len(unique),
        "supported_unique_analysis_pcm_count": sum(
            row["_analysis_pcm_sha256"] in scores for row in unique
        ),
        "unique_analysis_pcm_support_rate": sum(
            row["_analysis_pcm_sha256"] in scores for row in unique
        )
        / len(unique)
        if unique
        else None,
        "source_group_count": len(groups),
        "supported_source_group_count": supported_groups,
        "source_group_support_rate": supported_groups / len(groups) if groups else None,
    }


def grouped_support(
    cases: list[dict[str, Any]],
    scores: dict[str, float],
    field: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in cases:
        grouped[field(row)].append(row)
    return {
        name: support_summary(rows, scores) for name, rows in sorted(grouped.items())
    }


def score_summary(cases: list[dict[str, Any]], scores: dict[str, float]) -> dict[str, Any]:
    values = [
        scores[row["_analysis_pcm_sha256"]]
        for row in scoped_pcm_representatives(cases)
        if row["_analysis_pcm_sha256"] in scores
    ]
    return common.numeric_summary(values)


def grouped_scores(
    cases: list[dict[str, Any]],
    scores: dict[str, float],
    field: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in cases:
        grouped[field(row)].append(row)
    return {
        name: score_summary(rows, scores) for name, rows in sorted(grouped.items())
    }


def average_ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(indexed):
        end = index + 1
        while end < len(indexed) and indexed[end][1] == indexed[index][1]:
            end += 1
        average = (index + 1 + end) / 2.0
        for original, _ in indexed[index:end]:
            ranks[original] = average
        index = end
    return ranks


def pearson(first: list[float], second: list[float]) -> float | None:
    if len(first) != len(second) or len(first) < 2:
        return None
    first_mean = statistics.fmean(first)
    second_mean = statistics.fmean(second)
    numerator = sum(
        (left - first_mean) * (right - second_mean)
        for left, right in zip(first, second, strict=True)
    )
    left_scale = math.sqrt(sum((value - first_mean) ** 2 for value in first))
    right_scale = math.sqrt(sum((value - second_mean) ** 2 for value in second))
    if left_scale == 0.0 or right_scale == 0.0:
        return None
    return numerator / (left_scale * right_scale)


def correlation(first: list[float], second: list[float]) -> dict[str, Any]:
    return {
        "paired_value_count": len(first),
        "pearson": pearson(first, second),
        "spearman": pearson(average_ranks(first), average_ranks(second)),
    }


def score_correlations(score_maps: dict[str, dict[str, float]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for first_name, second_name in itertools.combinations(sorted(score_maps), 2):
        shared = sorted(set(score_maps[first_name]) & set(score_maps[second_name]))
        output[f"{first_name}_versus_{second_name}"] = correlation(
            [score_maps[first_name][key] for key in shared],
            [score_maps[second_name][key] for key in shared],
        )
    return output


def paired_group_deltas(
    cases: list[dict[str, Any]], scores: dict[str, float]
) -> dict[str, float]:
    by_id = {row["case_id"]: row for row in cases}
    unique_pairs: dict[tuple[str, str], tuple[str, float, tuple[Any, ...]]] = {}
    for row in cases:
        if row["expectation"] != "controlled_positive":
            continue
        reference = by_id[row["reference_case_id"]]
        positive_pcm = row["_analysis_pcm_sha256"]
        reference_pcm = reference["_analysis_pcm_sha256"]
        if positive_pcm not in scores or reference_pcm not in scores:
            continue
        key = (positive_pcm, reference_pcm)
        post_transform = (
            row["post_transform_ids"][0]
            if row.get("post_transform_ids")
            else "identity"
        )
        attribution = (
            post_transform != "identity",
            post_transform,
            row["encoder_lineage_id"],
            row["encoder_setting_id"],
        )
        value = (
            row["source_group"],
            scores[positive_pcm] - scores[reference_pcm],
            attribution,
        )
        previous = unique_pairs.get(key)
        if previous is None or attribution < previous[2]:
            unique_pairs[key] = value
    grouped: dict[str, list[float]] = defaultdict(list)
    for source_group, delta, _ in unique_pairs.values():
        grouped[source_group].append(delta)
    return {group: statistics.median(values) for group, values in grouped.items()}


def paired_correlations(
    cases: list[dict[str, Any]], score_maps: dict[str, dict[str, float]]
) -> dict[str, Any]:
    deltas = {name: paired_group_deltas(cases, scores) for name, scores in score_maps.items()}
    return score_correlations(deltas)


def representation_result(
    *,
    name: str,
    control: str,
    cases: list[dict[str, Any]],
    scores: dict[str, float],
) -> dict[str, Any]:
    paired = common.paired_effects(cases, scores)
    overall = paired["overall"]
    domain_rows = paired["by_source_domain"]
    domain_checks = {
        domain: {
            "positive_direction_rate": row["positive_direction_rate"],
            "strictly_above_one_half": row["positive_direction_rate"] is not None
            and row["positive_direction_rate"]
            > MINIMUM_DOMAIN_DIRECTION_RATE_EXCLUSIVE,
        }
        for domain, row in domain_rows.items()
    }
    direction_passed = (
        overall["positive_direction_rate"] is not None
        and overall["positive_direction_rate"] >= MINIMUM_DIRECTION_RATE
    )
    lower_passed = (
        overall["one_sided_95_percent_wilson_lower"] is not None
        and overall["one_sided_95_percent_wilson_lower"]
        >= MINIMUM_DIRECTION_WILSON_LOWER
    )
    domains_passed = bool(domain_checks) and all(
        row["strictly_above_one_half"] for row in domain_checks.values()
    )
    return {
        "control": control,
        "representation": name,
        "score_direction": "higher_is_more_consistent_with_prior_mp3_history",
        "threshold_available": False,
        "classification_metrics_available": False,
        "support": {
            "overall": support_summary(cases, scores),
            "by_expectation": grouped_support(
                cases, scores, lambda row: row["expectation"]
            ),
            "by_source_domain": grouped_support(
                cases, scores, lambda row: row["source_domain"]
            ),
            "negative_by_history_class": grouped_support(
                [row for row in cases if row["expectation"] == "negative"],
                scores,
                negative_history_class,
            ),
        },
        "unique_pcm_score_distribution": {
            "overall": score_summary(cases, scores),
            "by_expectation": grouped_scores(
                cases, scores, lambda row: row["expectation"]
            ),
            "by_source_domain": grouped_scores(
                cases, scores, lambda row: row["source_domain"]
            ),
            "negative_by_history_class": grouped_scores(
                [row for row in cases if row["expectation"] == "negative"],
                scores,
                negative_history_class,
            ),
            "positive_by_encoder_lineage": grouped_scores(
                [
                    row
                    for row in cases
                    if row["expectation"] == "controlled_positive"
                ],
                scores,
                lambda row: row["encoder_lineage_id"],
            ),
            "positive_by_encoder_setting": grouped_scores(
                [
                    row
                    for row in cases
                    if row["expectation"] == "controlled_positive"
                ],
                scores,
                lambda row: row["encoder_setting_id"],
            ),
        },
        "paired_positive_minus_matched_reference": paired,
        "discovery_gate_comparison": {
            "minimum_positive_direction_rate": MINIMUM_DIRECTION_RATE,
            "minimum_one_sided_95_percent_wilson_lower": MINIMUM_DIRECTION_WILSON_LOWER,
            "minimum_domain_direction_rate_exclusive": MINIMUM_DOMAIN_DIRECTION_RATE_EXCLUSIVE,
            "positive_direction_rate_passed": direction_passed,
            "wilson_lower_passed": lower_passed,
            "no_source_domain_reversed": domains_passed,
            "paired_source_group_support_rate": overall["source_group_count"]
            / common.EXPECTED_SOURCE_GROUP_COUNT,
            "all_comparisons_passed": direction_passed
            and lower_passed
            and domains_passed,
            "by_source_domain": domain_checks,
            "can_promote_retained_control": False,
        },
        "disposition": "retained_rejected_explainable_control_only",
    }


def feature_edges_by_pcm(
    feature_report: dict[str, Any], cases: list[dict[str, Any]]
) -> dict[str, bool]:
    by_case = {row.get("case_id"): row for row in feature_report.get("case_results", [])}
    if set(by_case) != {row["case_id"] for row in cases}:
        raise ValueError("feature-v0 inventory differs during edge join")
    output: dict[str, bool] = {}
    for row in cases:
        result = by_case[row["case_id"]].get("result", {})
        features = result.get("features", {}) if isinstance(result, dict) else {}
        drop = features.get("spectral_edge_drop_db")
        persistence = features.get("spectral_edge_persistence")
        passed = (
            isinstance(drop, (int, float))
            and math.isfinite(drop)
            and drop > 3.0
            and isinstance(persistence, (int, float))
            and math.isfinite(persistence)
            and persistence >= 0.0015
        )
        pcm = row["_analysis_pcm_sha256"]
        previous = output.setdefault(pcm, passed)
        if previous != passed:
            raise ValueError("feature-v0 edge state differs for identical PCM")
    return output


def edge_summary(
    cases: list[dict[str, Any]], edge_passed: dict[str, bool]
) -> dict[str, Any]:
    unique = scoped_pcm_representatives(cases)
    passed = sum(edge_passed[row["_analysis_pcm_sha256"]] for row in unique)
    return {
        "unique_analysis_pcm_count": len(unique),
        "edge_corroborated_unique_analysis_pcm_count": passed,
        "edge_corroboration_rate": passed / len(unique) if unique else None,
    }


def validate_private_report(
    *,
    control: str,
    raw: dict[str, Any],
    representatives: list[dict[str, Any]],
    expected_input_hashes: dict[str, str],
) -> dict[str, dict[str, float]]:
    rows = raw.get("artifact_results")
    binding = raw.get("run_binding")
    wrapper = raw.get("wrapper_invariance")
    expected_inventory = {
        "controlled_mp3_positive_case_count": runner.EXPECTED_MP3_POSITIVE_CASE_COUNT,
        "multi_wrapper_pcm_count": runner.EXPECTED_MULTI_WRAPPER_PCM_COUNT,
        "negative_case_count": runner.EXPECTED_NEGATIVE_CASE_COUNT,
        "pcm_wrapper_representative_count": runner.EXPECTED_PCM_WRAPPER_REPRESENTATIVE_COUNT,
        "selected_factorial_case_count": runner.EXPECTED_SELECTED_CASE_COUNT,
        "source_group_count": common.EXPECTED_SOURCE_GROUP_COUNT,
        "unique_analysis_pcm_count": runner.EXPECTED_UNIQUE_PCM_COUNT,
    }
    if (
        raw.get("schema_version") != 1
        or raw.get("adapter_id") != runner.ADAPTER_ID
        or raw.get("state")
        != "mechanism_development_explainable_control_private_result"
        or raw.get("control") != control
        or raw.get("evidence_partition") != common.MECHANISM_PARTITION
        or raw.get("feature_version") != 0
        or raw.get("scores_opened") is not True
        or raw.get("thresholds_fitted") is not False
        or raw.get("independent_validation") is not False
        or raw.get("encoder_transfer_scores_opened") is not False
        or raw.get("external_transfer_scores_opened") is not False
        or raw.get("public_verdict_enabled") is not False
        or raw.get("inventory") != expected_inventory
        or not isinstance(binding, dict)
        or binding.get("adapter_id") != runner.ADAPTER_ID
        or binding.get("control") != control
        or binding.get("scope") != expected_inventory
        or not isinstance(binding.get("implementation_commit_sha1"), str)
        or len(binding["implementation_commit_sha1"]) != 40
        or binding.get("input_hashes") != expected_input_hashes
        or raw.get("run_binding_sha256")
        != common.canonical_sha256(
            b"lossytrace-v2-explainable-control-run-binding-v1\0", binding
        )
        or wrapper
        != {
            "exact_wrapper_invariance_passed": True,
            "multi_wrapper_pcm_count": runner.EXPECTED_MULTI_WRAPPER_PCM_COUNT,
            "pcm_wrapper_representative_count": runner.EXPECTED_PCM_WRAPPER_REPRESENTATIVE_COUNT,
            "unique_analysis_pcm_count": runner.EXPECTED_UNIQUE_PCM_COUNT,
        }
        or not isinstance(rows, list)
    ):
        raise ValueError(f"private {control} report state differs")
    expected = {row["case_id"]: row for row in representatives}
    observed = {row.get("case_id"): row for row in rows if isinstance(row, dict)}
    if len(observed) != len(rows) or set(observed) != set(expected):
        raise ValueError(f"private {control} representative inventory differs")
    fields = runner.EXACT_SCORE_FIELDS if control == runner.EXACT_HYBRID else runner.PROJECTION_SCORE_FIELDS
    pcm_measurements: dict[str, dict[str, Any]] = {}
    for case_id, case in expected.items():
        row = observed[case_id]
        if (
            row.get("audio_sha256") != case["audio_sha256"]
            or row.get("analysis_pcm_sha256") != case["_analysis_pcm_sha256"]
            or row.get("lossless_wrapper_id") != case["lossless_wrapper_id"]
        ):
            raise ValueError(f"private {control} representative binding differs")
        measurement = runner.validate_normalized_measurement(control, row.get("measurement"))
        pcm = case["_analysis_pcm_sha256"]
        previous = pcm_measurements.setdefault(pcm, measurement)
        if previous != measurement:
            raise ValueError(f"private {control} wrapper invariance replay failed")
    return {
        name: {
            pcm: float(measurement["scores"][name])
            for pcm, measurement in pcm_measurements.items()
            if measurement["support"][name]
        }
        for name in fields
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-plan", required=True, type=Path)
    parser.add_argument("--parent-plan", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--constructor-manifest", required=True, type=Path)
    parser.add_argument("--feature-v0-report", required=True, type=Path)
    parser.add_argument("--exact-report", required=True, type=Path)
    parser.add_argument("--projection-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        analyzer_path = Path(__file__).resolve()
        runner_path = Path(runner.__file__).resolve()
        adapter_plan_path = args.adapter_plan.expanduser().resolve()
        parent_plan_path = args.parent_plan.expanduser().resolve()
        manifest_path = args.manifest.expanduser().resolve()
        constructor_path = args.constructor_manifest.expanduser().resolve()
        feature_path = args.feature_v0_report.expanduser().resolve()
        exact_path = args.exact_report.expanduser().resolve()
        projection_path = args.projection_report.expanduser().resolve()
        adapter, expected_input_hashes = runner.validate_plan_and_inputs(
            adapter_plan_path=adapter_plan_path,
            parent_plan_path=parent_plan_path,
            analysis_manifest_path=manifest_path,
            constructor_manifest_path=constructor_path,
            feature_report_path=feature_path,
            runner_path=runner_path,
            analyzer_path=analyzer_path,
        )
        cases = common.load_development_cases(
            common.load_object(manifest_path), common.load_object(constructor_path)
        )
        feature_report = common.load_object(feature_path)
        runner.validate_feature_report(feature_report, cases)
        selected = runner.select_scope(cases)
        representatives = runner.scoped_representatives(selected)
        exact_raw = common.load_object(exact_path)
        projection_raw = common.load_object(projection_path)
        exact_scores = validate_private_report(
            control=runner.EXACT_HYBRID,
            raw=exact_raw,
            representatives=representatives,
            expected_input_hashes=expected_input_hashes,
        )
        projection_scores = validate_private_report(
            control=runner.CODEC_PROJECTION,
            raw=projection_raw,
            representatives=representatives,
            expected_input_hashes=expected_input_hashes,
        )
        if (
            exact_raw["run_binding"]["implementation_commit_sha1"]
            != projection_raw["run_binding"]["implementation_commit_sha1"]
        ):
            raise ValueError("control runs use different implementation commits")
        representations = {
            name: representation_result(
                name=name,
                control=runner.EXACT_HYBRID,
                cases=selected,
                scores=scores,
            )
            for name, scores in exact_scores.items()
        }
        representations.update(
            {
                name: representation_result(
                    name=name,
                    control=runner.CODEC_PROJECTION,
                    cases=selected,
                    scores=scores,
                )
                for name, scores in projection_scores.items()
            }
        )
        edges = feature_edges_by_pcm(feature_report, cases)
        output = {
            "schema_version": 1,
            "adapter_id": runner.ADAPTER_ID,
            "state": "mechanism_development_explainable_control_path_free_evidence",
            "evidence_partition": common.MECHANISM_PARTITION,
            "feature_version": 0,
            "independent_validation": False,
            "encoder_transfer_scores_opened": False,
            "external_transfer_scores_opened": False,
            "public_verdict_enabled": False,
            "inputs": {
                "adapter_plan_sha256": common.sha256_file(adapter_plan_path),
                "parent_plan_sha256": common.sha256_file(parent_plan_path),
                "private_analysis_manifest_sha256": common.sha256_file(manifest_path),
                "private_feature_v0_report_sha256": common.sha256_file(feature_path),
                "private_exact_report_sha256": common.sha256_file(exact_path),
                "private_projection_report_sha256": common.sha256_file(projection_path),
                "runner_sha256": common.sha256_file(runner_path),
                "analyzer_sha256": common.sha256_file(analyzer_path),
            },
            "inventory": {
                "selected_factorial_case_count": len(selected),
                "negative_case_count": sum(
                    row["expectation"] == "negative" for row in selected
                ),
                "controlled_mp3_positive_case_count": sum(
                    row["expectation"] == "controlled_positive" for row in selected
                ),
                "unique_analysis_pcm_count": len(
                    scoped_pcm_representatives(
                        selected, enforce_frozen_inventory=True
                    )
                ),
                "pcm_wrapper_representative_count": len(representatives),
                "source_group_count": len({row["source_group"] for row in selected}),
                "source_domain_count": len({row["source_domain"] for row in selected}),
            },
            "wrapper_invariance": {
                runner.EXACT_HYBRID: exact_raw["wrapper_invariance"],
                runner.CODEC_PROJECTION: projection_raw["wrapper_invariance"],
            },
            "fixed_edge_corroboration_diagnostic": {
                "definition": {
                    "spectral_edge_drop_db_exclusive": 3.0,
                    "spectral_edge_persistence_inclusive": 0.0015,
                    "threshold_refitted": False,
                },
                "overall": edge_summary(selected, edges),
                "by_expectation": {
                    name: edge_summary(rows, edges)
                    for name, rows in sorted(
                        (
                            name,
                            [row for row in selected if row["expectation"] == name],
                        )
                        for name in {row["expectation"] for row in selected}
                    )
                },
            },
            "representations": representations,
            "within_family_correlations": {
                "exact_hybrid_unique_pcm_scores": score_correlations(exact_scores),
                "exact_hybrid_paired_source_group_deltas": paired_correlations(
                    selected, exact_scores
                ),
                "codec_projection_unique_pcm_scores": score_correlations(
                    projection_scores
                ),
                "codec_projection_paired_source_group_deltas": paired_correlations(
                    selected, projection_scores
                ),
            },
            "interpretation": {
                "raw_paired_controls_only": True,
                "thresholds_fitted_on_v2": False,
                "classification_or_calibration_claim_available": False,
                "retained_controls_can_be_promoted": False,
                "accuracy_is_not_universal_history_identifiability": True,
            },
        }
        common.assert_public_path_free(output)
        common.write_new(args.output.expanduser().resolve(), output)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print("wrote path-free v2 explainable-control aggregate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
