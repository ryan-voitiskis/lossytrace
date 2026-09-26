#!/usr/bin/env python3
"""Aggregate lossy-original versus lossless-wrapper measurement equivalence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from collections import defaultdict
from pathlib import Path


FEATURE_FIELDS = (
    "median_active_bin_fraction",
    "spectral_edge_hz",
    "spectral_edge_drop_db",
    "spectral_edge_persistence",
    "spectral_edge_spread_hz",
    "spectral_hole_ratio",
    "isolated_hole_ratio",
    "band_rupture_score",
    "transform_alignment_score",
    "transform_alignment_small_coefficient_fraction",
)
ORIGINAL_ROLE = "lossy_original"
WRAPPER_ROLES = ("lossless_flac16", "lossless_wav16", "lossless_aiff16")


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


def quantile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = proportion * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize_differences(values: list[float], null_mismatches: int, pairs: int) -> dict:
    return {
        "pair_count": pairs,
        "numeric_pair_count": len(values),
        "null_mismatch_count": null_mismatches,
        "median_absolute_difference": quantile(values, 0.5),
        "p95_absolute_difference": quantile(values, 0.95),
        "p99_absolute_difference": quantile(values, 0.99),
        "maximum_absolute_difference": max(values) if values else None,
    }


def comparison_contract(manifest: dict, codec: str) -> dict:
    all_contracts = manifest.get("lossy_original_analysis")
    contract = all_contracts.get(codec) if isinstance(all_contracts, dict) else None
    if not isinstance(contract, dict) or not isinstance(contract.get("included"), bool):
        raise ValueError(f"{codec}: lossy-original analysis contract is missing")
    included = contract["included"]
    reason = contract.get("omission_reason")
    if (included and reason is not None) or (
        not included and (not isinstance(reason, str) or not reason)
    ):
        raise ValueError(f"{codec}: lossy-original omission contract differs")
    reference_role = ORIGINAL_ROLE if included else WRAPPER_ROLES[0]
    comparison_roles = (
        WRAPPER_ROLES
        if included
        else tuple(role for role in WRAPPER_ROLES if role != reference_role)
    )
    expected_roles = {*WRAPPER_ROLES}
    if included:
        expected_roles.add(ORIGINAL_ROLE)
    return {
        "lossy_original_analyzed": included,
        "lossy_original_omission_reason": reason,
        "expected_roles": expected_roles,
        "reference_role": reference_role,
        "comparison_roles": comparison_roles,
    }


def analyze(manifest: dict, report: dict, hashes: dict) -> dict:
    if (
        manifest.get("schema_version") != 1
        or manifest.get("evidence_partition") != "observed_development"
        or manifest.get("holdout_scores_opened") is not False
    ):
        raise ValueError("equivalence manifest gate state differs")
    gate = report.get("gate_disposition")
    if (
        report.get("schema_version") != 1
        or report.get("feature_version") != 0
        or not isinstance(gate, dict)
        or gate.get("likely_lossy_derived_enabled") is not False
    ):
        raise ValueError("equivalence report gate state differs")
    cases = manifest.get("cases")
    results = report.get("results")
    if not isinstance(cases, list) or not isinstance(results, list):
        raise ValueError("manifest cases and results must be arrays")
    cases_by_id = {case["case_id"]: case for case in cases}
    results_by_id = {row["case_id"]: row for row in results}
    if (
        len(cases_by_id) != len(cases)
        or len(results_by_id) != len(results)
        or cases_by_id.keys() != results_by_id.keys()
    ):
        raise ValueError("manifest and report case inventories differ")
    grouped: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for case_id, case in cases_by_id.items():
        codec = case.get("codec_family")
        role = case.get("container_role")
        source_group = case.get("source_group")
        if not all(isinstance(value, str) and value for value in (codec, role, source_group)):
            raise ValueError(f"{case_id}: equivalence metadata is missing")
        key = (source_group, codec)
        if role in grouped[key]:
            raise ValueError(f"{case_id}: duplicate container role")
        row = results_by_id[case_id]
        runner = row.get("runner")
        if (
            not isinstance(runner, dict)
            or runner.get("research_transform_grid_enabled") is not False
            or runner.get("research_transform_grid_profile") is not None
            or runner.get("transform_grid_probe") is not None
        ):
            raise ValueError(f"{case_id}: legacy transform-grid probe was enabled")
        features = runner.get("compression_trace") if isinstance(runner, dict) else None
        if not isinstance(features, dict):
            raise ValueError(f"{case_id}: compression trace is missing")
        grouped[key][role] = features

    by_codec_values: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    by_codec_nulls: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_codec_pairs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    exact_wrapper_groups: dict[str, int] = defaultdict(int)
    exact_original_wrapper_groups: dict[str, int] = defaultdict(int)
    total_groups: dict[str, int] = defaultdict(int)
    container_pair_counts: dict[str, int] = defaultdict(int)
    contracts = {}
    for (_, codec), roles in grouped.items():
        contract = comparison_contract(manifest, codec)
        contracts[codec] = contract
        if set(roles) != contract["expected_roles"]:
            raise ValueError(f"{codec}: container-role inventory differs")
        total_groups[codec] += 1
        wrapper_features = [roles[role] for role in WRAPPER_ROLES]
        if all(features == wrapper_features[0] for features in wrapper_features[1:]):
            exact_wrapper_groups[codec] += 1
        if contract["lossy_original_analyzed"] and all(
            roles[ORIGINAL_ROLE] == features for features in wrapper_features
        ):
            exact_original_wrapper_groups[codec] += 1
        reference = roles[contract["reference_role"]]
        for role in contract["comparison_roles"]:
            wrapper = roles[role]
            container_pair_counts[codec] += 1
            for field in FEATURE_FIELDS:
                by_codec_pairs[codec][field] += 1
                left = reference.get(field)
                right = wrapper.get(field)
                if left is None or right is None:
                    if left is not right:
                        by_codec_nulls[codec][field] += 1
                    continue
                if (
                    not isinstance(left, (int, float))
                    or not math.isfinite(left)
                    or not isinstance(right, (int, float))
                    or not math.isfinite(right)
                ):
                    raise ValueError(f"{codec}/{field}: non-finite feature")
                by_codec_values[codec][field].append(abs(float(left) - float(right)))

    by_codec = {}
    for codec in sorted(total_groups):
        by_codec[codec] = {
            "source_group_count": total_groups[codec],
            "lossy_original_analyzed": contracts[codec]["lossy_original_analyzed"],
            "lossy_original_omission_reason": contracts[codec][
                "lossy_original_omission_reason"
            ],
            "comparison_reference_role": contracts[codec]["reference_role"],
            "comparison_pair_count": container_pair_counts[codec],
            "lossless_wrapper_feature_exact_match_group_count": exact_wrapper_groups[
                codec
            ],
            "lossy_original_to_all_wrappers_feature_exact_match_group_count": (
                exact_original_wrapper_groups[codec]
                if contracts[codec]["lossy_original_analyzed"]
                else None
            ),
            "features": {
                field: summarize_differences(
                    by_codec_values[codec][field],
                    by_codec_nulls[codec][field],
                    by_codec_pairs[codec][field],
                )
                for field in FEATURE_FIELDS
            },
        }
    return {
        "schema_version": 1,
        "state": "observed_development_container_equivalence",
        "feature_version": 0,
        "independent_validation": False,
        "holdout_scores_opened": False,
        "public_verdict_enabled": False,
        "inputs": hashes,
        "inventory": {
            "case_count": len(cases),
            "source_group_count": len({case["source_group"] for case in cases}),
            "codec_family_count": len(total_groups),
            "comparison_pair_count": sum(container_pair_counts.values()),
        },
        "container_only_wrapper_equivalence": {
            "all_source_groups_feature_exact_match": all(
                exact_wrapper_groups[codec] == total_groups[codec]
                for codec in total_groups
            ),
            "exact_match_source_group_count": sum(exact_wrapper_groups.values()),
            "total_source_group_count": sum(total_groups.values()),
        },
        "by_codec_family": by_codec,
        "interpretation": {
            "classification_metrics_available": False,
            "calibration_metrics_available": False,
            "reason": (
                "Supported lossy originals are compared with their PCM wrappers. "
                "When the current decoder does not support an original codec, its "
                "lossless wrappers are compared with one another and the omission "
                "is explicit. No score threshold or provenance verdict is fitted."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = args.manifest.expanduser().resolve()
        report = args.report.expanduser().resolve()
        value = analyze(
            load_object(manifest),
            load_object(report),
            {
                "manifest_sha256": sha256_file(manifest),
                "raw_report_sha256": sha256_file(report),
            },
        )
        write_new(args.output.expanduser().resolve(), value)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(
        f"wrote path-free container equivalence for "
        f"{value['inventory']['comparison_pair_count']} pairs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
