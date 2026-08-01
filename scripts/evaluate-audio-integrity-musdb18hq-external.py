#!/usr/bin/env python3
"""Evaluate the one-use frozen MUSDB18-HQ external transfer."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path


CANDIDATE_ID = "conservative-two-grid-edge-v28-musdb-transfer-v1"
PROFILE = "conservative-two-grid-v28"
EXPECTED_CASE_COUNT = 1_770
EXPECTED_SOURCE_COUNT = 150
EXPECTED_NEGATIVE_COUNT = 600
MINIMUM_SUPPORTED_RECALL = 0.90
MINIMUM_SUPPORT_COVERAGE = 0.75
MAXIMUM_FALSE_POSITIVES = 0
MAXIMUM_P95_RUNTIME_OVERHEAD_PERCENT = 10.0
SCOPED_CLASSES = {
    "musdb_aac_at_128_to_flac16",
    "musdb_aac_lc_128_to_flac16",
    "musdb_mp3_128_to_flac16",
    "musdb_vorbis_native_q3_to_flac16",
}
DIFFICULT_CLASSES = {
    "musdb_aac_lc_192_to_flac16",
    "musdb_mp3_320_to_flac16",
    "musdb_opus_96_to_flac16",
}
NEGATIVE_CLASSES = {
    "musdb_pcm_reference_wav16",
    "musdb_pcm_sharp_lowpass_16000_flac16",
    "musdb_pcm_lowpass_19000_flac16",
    "musdb_pcm_resample_32000_44100_flac16",
}
AAC_INVARIANT_CLASSES = {
    "musdb_aac_lc_128_to_flac16",
    "musdb_aac_lc_128_gain_minus3db_to_flac16",
    "musdb_aac_lc_128_trim_137_to_flac16",
    "musdb_aac_lc_128_to_wav16",
    "musdb_aac_lc_128_to_aiff24",
}


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(
        "audio_integrity_conservative_policy",
        path,
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import policy module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def write_new_json(path: Path, value: dict) -> None:
    path = path.expanduser().resolve()
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace evaluation: {path}")
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


def wilson_interval(successes: int, total: int) -> dict:
    if total == 0:
        return {"lower": None, "upper": None}
    z = 1.959963984540054
    observed = successes / total
    denominator = 1.0 + z * z / total
    center = (observed + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * math.sqrt(
            observed * (1.0 - observed) / total
            + z * z / (4.0 * total * total)
        )
        / denominator
    )
    return {
        "lower": max(0.0, center - radius),
        "upper": min(1.0, center + radius),
    }


def metrics(rows: list[dict]) -> dict:
    positives = [
        row
        for row in rows
        if row["expectation"] == "controlled_positive"
    ]
    negatives = [
        row for row in rows if row["expectation"] == "negative"
    ]
    supported_positives = [
        row for row in positives if row["signal_supported"]
    ]
    supported_negatives = [
        row for row in negatives if row["signal_supported"]
    ]
    true_positives = [
        row for row in positives if row["predicted_positive"]
    ]
    false_positives = [
        row for row in negatives if row["predicted_positive"]
    ]
    predicted_positives = true_positives + false_positives
    return {
        "case_count": len(rows),
        "positive_count": len(positives),
        "negative_count": len(negatives),
        "supported_positive_count": len(supported_positives),
        "supported_negative_count": len(supported_negatives),
        "true_positive_count": len(true_positives),
        "false_positive_count": len(false_positives),
        "false_positive_case_ids": [
            row["case_id"] for row in false_positives
        ],
        "false_positive_source_group_count": len(
            {row["source_group"] for row in false_positives}
        ),
        "false_positive_source_groups": sorted(
            {row["source_group"] for row in false_positives}
        ),
        "positive_coverage": (
            len(supported_positives) / len(positives)
            if positives
            else None
        ),
        "supported_recall": (
            len(true_positives) / len(supported_positives)
            if supported_positives
            else None
        ),
        "precision_on_stated_evaluation_mix": (
            len(true_positives) / len(predicted_positives)
            if predicted_positives
            else None
        ),
        "all_negative_false_positive_rate": (
            len(false_positives) / len(negatives)
            if negatives
            else None
        ),
        "all_negative_false_positive_rate_wilson_95": wilson_interval(
            len(false_positives),
            len(negatives),
        ),
        "supported_negative_false_positive_rate": (
            len(false_positives) / len(supported_negatives)
            if supported_negatives
            else None
        ),
    }


def grouped_metrics(rows: list[dict], key: str) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row)
    return {
        name: metrics(group)
        for name, group in sorted(grouped.items())
    }


def invariant_audit(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["class"] in AAC_INVARIANT_CLASSES:
            grouped[row["source_group"]].append(row)
    selected = {
        source_group: group
        for source_group, group in grouped.items()
        if {row["class"] for row in group} == AAC_INVARIANT_CLASSES
    }
    if len(selected) != 30:
        raise SystemExit("AAC invariant source-group inventory differs")
    mismatches = []
    for source_group, group in sorted(selected.items()):
        states = {
            (
                row["signal_supported"],
                row["assessment"],
                row["predicted_positive"],
            )
            for row in group
        }
        if len(states) != 1:
            mismatches.append(
                {
                    "source_group": source_group,
                    "states": [
                        {
                            "class": row["class"],
                            "signal_supported": row["signal_supported"],
                            "assessment": row["assessment"],
                            "predicted_positive": row[
                                "predicted_positive"
                            ],
                        }
                        for row in sorted(
                            group,
                            key=lambda value: value["class"],
                        )
                    ],
                }
            )
    return {
        "source_group_count": len(selected),
        "mismatch_source_group_count": len(mismatches),
        "mismatches": mismatches,
    }


def validate_frozen_inputs(
    *,
    precommit_path: Path,
    precommit: dict,
    policy_path: Path,
    measurement_path: Path,
    measurement: dict,
    support_path: Path,
    support_report: dict,
    manifest_path: Path,
    manifest: dict,
    fingerprints_path: Path,
    fingerprints: dict,
    performance_path: Path,
    performance: dict,
) -> None:
    tools = precommit.get("tools", {})
    evidence = precommit.get("evidence", {})
    corpus_plan = precommit.get("corpus_plan", {})
    gate = precommit.get("external_transfer_gate", {})
    plan_path = Path(corpus_plan.get("path", "")).expanduser().resolve()
    plan = load_json(plan_path)
    measurement_rows = measurement.get("results")
    support_rows = support_report.get("cases")
    expected_gate = {
        "maximum_tier_a_negative_false_positive_count": 0,
        "minimum_supported_recall_per_scoped_class": 0.9,
        "minimum_support_coverage_per_scoped_class": 0.75,
        "scoped_classes": sorted(SCOPED_CLASSES),
        "difficult_classes": sorted(DIFFICULT_CLASSES),
        "hard_negative_classes": sorted(NEGATIVE_CLASSES),
        "aac_invariant_source_group_count": 30,
        "maximum_aac_invariant_mismatch_source_groups": 0,
        "required_positive_reason_families": [
            "persistent_spectral_edge",
            "transform_frame_periodicity",
        ],
        "maximum_p95_runtime_overhead_percent": 10.0,
        "minimum_independent_source_groups": 150,
    }
    if (
        precommit.get("schema_version") != 1
        or precommit.get("state") != "frozen_before_external_transfer"
        or precommit.get("candidate_id") != CANDIDATE_ID
        or precommit.get("candidate_frozen") is not True
        or precommit.get("external_transfer_feature_scores_opened") is not False
        or precommit.get("release_heldout_opened") is not False
        or precommit.get("public_verdict_enabled") is not False
        or precommit.get("feature_version") != 0
        or precommit.get("transform_profile") != PROFILE
        or precommit.get("external_transfer_gate") != expected_gate
        or measurement.get("schema_version") != 1
        or measurement.get("state")
        != "frozen_external_transfer_measurement_complete"
        or measurement.get("candidate_id") != CANDIDATE_ID
        or measurement.get("candidate_frozen") is not True
        or measurement.get("profile") != PROFILE
        or measurement.get("public_verdict_enabled") is not False
        or support_report.get("schema_version") != 1
        or support_report.get("state")
        != "frozen_external_transfer_support_measurement"
        or support_report.get("candidate_id") != CANDIDATE_ID
        or support_report.get("candidate_frozen") is not True
        or support_report.get("method_id")
        != "low-bandwidth-support-discovery-v0"
        or support_report.get("public_verdict_enabled") is not False
        or corpus_plan.get("sha256") != sha256_file(plan_path)
        or manifest != plan.get("manifest")
        or tools.get("evaluator_sha256")
        != sha256_file(Path(__file__).resolve())
        or tools.get("policy_module_sha256")
        != sha256_file(policy_path)
        or measurement.get("candidate_precommit", {}).get("sha256")
        != sha256_file(precommit_path)
        or measurement.get("harness", {}).get("sha256")
        != tools.get("external_runner_sha256")
        or measurement.get("runner", {}).get("sha256")
        != tools.get("benchmark_runner_sha256")
        or support_report.get("candidate_precommit", {}).get("sha256")
        != sha256_file(precommit_path)
        or support_report.get("tool", {}).get("sha256")
        != tools.get("low_bandwidth_probe_sha256")
        or evidence.get("performance_report_sha256")
        != sha256_file(performance_path)
        or performance.get("commitments", {}).get("runner_sha256")
        != tools.get("benchmark_runner_sha256")
        or fingerprints.get("corpus_id") != manifest.get("corpus_id")
        or len(manifest.get("cases", [])) != EXPECTED_CASE_COUNT
        or measurement.get("case_count") != EXPECTED_CASE_COUNT
        or support_report.get("case_count") != EXPECTED_CASE_COUNT
        or not isinstance(measurement_rows, list)
        or len(measurement_rows) != EXPECTED_CASE_COUNT
        or not isinstance(support_rows, list)
        or len(support_rows) != EXPECTED_CASE_COUNT
        or measurement.get("external_transfer_feature_scores_opened")
        is not True
        or support_report.get("external_transfer_feature_scores_opened")
        is not True
        or measurement.get("opening", {}).get("state")
        != "external_transfer_feature_scores_opened"
        or measurement.get("opening", {}).get(
            "candidate_precommit_sha256"
        )
        != sha256_file(precommit_path)
        or measurement.get("opening", {}).get("release_heldout_opened")
        is not False
        or measurement.get("opening", {}).get("public_verdict_enabled")
        is not False
        or support_report.get("opening", {}).get("state")
        != "external_transfer_feature_scores_opened"
        or support_report.get("opening", {}).get(
            "candidate_precommit_sha256"
        )
        != sha256_file(precommit_path)
        or support_report.get("opening", {}).get(
            "release_heldout_opened"
        )
        is not False
        or support_report.get("opening", {}).get(
            "public_verdict_enabled"
        )
        is not False
        or measurement.get("release_heldout_opened") is not False
        or support_report.get("release_heldout_opened") is not False
        or sha256_file(manifest_path)
        != measurement.get("manifest", {}).get("sha256")
        or sha256_file(fingerprints_path)
        != measurement.get("fingerprints", {}).get("sha256")
        or sha256_file(manifest_path)
        != support_report.get("manifest", {}).get("sha256")
        or sha256_file(fingerprints_path)
        != support_report.get("fingerprints", {}).get("sha256")
    ):
        raise SystemExit("frozen external evaluation contract differs")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--precommit", type=Path, required=True)
    parser.add_argument("--policy-module", type=Path, required=True)
    parser.add_argument("--measurement", type=Path, required=True)
    parser.add_argument("--support-report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--fingerprints", type=Path, required=True)
    parser.add_argument("--performance-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    precommit_path = args.precommit.expanduser().resolve()
    policy_path = args.policy_module.expanduser().resolve()
    measurement_path = args.measurement.expanduser().resolve()
    support_path = args.support_report.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    fingerprints_path = args.fingerprints.expanduser().resolve()
    performance_path = args.performance_report.expanduser().resolve()
    precommit = load_json(precommit_path)
    policy = load_module(policy_path)
    measurement = load_json(measurement_path)
    support_report = load_json(support_path)
    manifest = load_json(manifest_path)
    fingerprints = load_json(fingerprints_path)
    performance = load_json(performance_path)
    validate_frozen_inputs(
        precommit_path=precommit_path,
        precommit=precommit,
        policy_path=policy_path,
        measurement_path=measurement_path,
        measurement=measurement,
        support_path=support_path,
        support_report=support_report,
        manifest_path=manifest_path,
        manifest=manifest,
        fingerprints_path=fingerprints_path,
        fingerprints=fingerprints,
        performance_path=performance_path,
        performance=performance,
    )
    if (
        policy.CANDIDATE_ID != CANDIDATE_ID
        or policy.PROFILE != PROFILE
        or policy.contract() != precommit.get("policy")
    ):
        raise SystemExit("frozen policy module contract differs")

    manifest_by_id = {
        case["case_id"]: case for case in manifest["cases"]
    }
    measurement_by_id = {
        row["case_id"]: row for row in measurement["results"]
    }
    support_by_id = {
        row["case_id"]: row for row in support_report["cases"]
    }
    expected_ids = set(manifest_by_id)
    if (
        len(manifest_by_id) != EXPECTED_CASE_COUNT
        or len(measurement_by_id) != EXPECTED_CASE_COUNT
        or len(support_by_id) != EXPECTED_CASE_COUNT
        or set(measurement_by_id) != expected_ids
        or set(support_by_id) != expected_ids
        or set(fingerprints["case_sha256"]) != expected_ids
    ):
        raise SystemExit("external evaluation inventories differ")

    rows = []
    for case_id in sorted(expected_ids):
        case = manifest_by_id[case_id]
        measured = measurement_by_id[case_id]
        supported = support_by_id[case_id]
        if (
            measured["source_group"] != case["source_group"]
            or measured["class"] != case["class"]
            or measured["expectation"] != case["expectation"]
            or supported["source_group"] != case["source_group"]
            or supported["class"] != case["class"]
            or supported["expectation"] != case["expectation"]
            or measured["audio_sha256"]
            != fingerprints["case_sha256"][case_id]
            or supported["audio_sha256"]
            != fingerprints["case_sha256"][case_id]
        ):
            raise SystemExit(f"{case_id}: joined evidence identity differs")
        try:
            assessment = policy.assess(
                measured["runner"],
                supported["features"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise SystemExit(f"{case_id}: policy failed: {error}") from error
        rows.append(
            {
                "case_id": case_id,
                "source_group": case["source_group"],
                "class": case["class"],
                "expectation": case["expectation"],
                **assessment,
            }
        )

    source_groups = {row["source_group"] for row in rows}
    if (
        len(rows) != EXPECTED_CASE_COUNT
        or len(source_groups) != EXPECTED_SOURCE_COUNT
        or sum(row["expectation"] == "negative" for row in rows)
        != EXPECTED_NEGATIVE_COUNT
    ):
        raise SystemExit("evaluated corpus inventory differs")
    overall = metrics(rows)
    by_class = grouped_metrics(rows, "class")
    class_inventory = set(by_class)
    if not (
        SCOPED_CLASSES
        | DIFFICULT_CLASSES
        | NEGATIVE_CLASSES
        | AAC_INVARIANT_CLASSES
    ).issubset(class_inventory):
        raise SystemExit("required evaluation classes are missing")

    scoped_gate = {}
    for class_name in sorted(SCOPED_CLASSES):
        value = by_class[class_name]
        if value["positive_count"] != EXPECTED_SOURCE_COUNT:
            raise SystemExit(f"{class_name}: source inventory differs")
        recall = value["supported_recall"]
        coverage = value["positive_coverage"]
        scoped_gate[class_name] = {
            "supported_count": value["supported_positive_count"],
            "true_positive_count": value["true_positive_count"],
            "supported_recall": recall,
            "positive_coverage": coverage,
            "minimum_supported_recall": MINIMUM_SUPPORTED_RECALL,
            "minimum_support_coverage": MINIMUM_SUPPORT_COVERAGE,
            "passed": bool(
                recall is not None
                and recall >= MINIMUM_SUPPORTED_RECALL
                and coverage is not None
                and coverage >= MINIMUM_SUPPORT_COVERAGE
            ),
        }
    hard_negative_gate = {
        class_name: {
            "case_count": by_class[class_name]["negative_count"],
            "false_positive_count": by_class[class_name][
                "false_positive_count"
            ],
            "passed": (
                by_class[class_name]["negative_count"]
                == EXPECTED_SOURCE_COUNT
                and by_class[class_name]["false_positive_count"] == 0
            ),
        }
        for class_name in sorted(NEGATIVE_CLASSES)
    }
    invariance = invariant_audit(rows)
    reason_failures = [
        row["case_id"]
        for row in rows
        if row["predicted_positive"]
        and set(row["reason_families"])
        != {
            "persistent_spectral_edge",
            "transform_frame_periodicity",
        }
    ]
    performance_p95 = float(
        performance["summary"]["p95_wall_time_overhead_percent"]
    )
    performance_passed = (
        performance_p95 <= MAXIMUM_P95_RUNTIME_OVERHEAD_PERCENT
    )
    gate_passed = bool(
        overall["false_positive_count"] == MAXIMUM_FALSE_POSITIVES
        and all(value["passed"] for value in scoped_gate.values())
        and all(
            value["passed"] for value in hard_negative_gate.values()
        )
        and invariance["mismatch_source_group_count"] == 0
        and not reason_failures
        and performance_passed
        and precommit.get("memory_contract", {}).get(
            "no_new_full_spectrogram_sized_allocation"
        )
        is True
    )
    branch_counts = Counter(
        branch for row in rows for branch in row["branches"]
    )
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": "one_use_external_transfer_evaluated",
        "candidate_id": CANDIDATE_ID,
        "candidate_frozen": True,
        "external_transfer_feature_scores_opened": True,
        "external_transfer_consumed": True,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "policy": policy.contract(),
        "inputs": {
            "precommit": {
                "path": str(precommit_path),
                "sha256": sha256_file(precommit_path),
            },
            "policy_module": {
                "path": str(policy_path),
                "sha256": sha256_file(policy_path),
            },
            "measurement": {
                "path": str(measurement_path),
                "sha256": sha256_file(measurement_path),
            },
            "support_report": {
                "path": str(support_path),
                "sha256": sha256_file(support_path),
            },
            "manifest": {
                "path": str(manifest_path),
                "sha256": sha256_file(manifest_path),
            },
            "fingerprints": {
                "path": str(fingerprints_path),
                "sha256": sha256_file(fingerprints_path),
            },
            "performance_report": {
                "path": str(performance_path),
                "sha256": sha256_file(performance_path),
            },
            "evaluator": {
                "path": str(Path(__file__).resolve()),
                "sha256": sha256_file(Path(__file__).resolve()),
            },
        },
        "inventory": {
            "case_count": len(rows),
            "source_group_count": len(source_groups),
            "class_counts": dict(
                sorted(Counter(row["class"] for row in rows).items())
            ),
        },
        "metrics": {
            "overall": overall,
            "by_class": by_class,
            "branch_fire_counts": dict(sorted(branch_counts.items())),
            "difficult_codec_results": {
                class_name: by_class[class_name]
                for class_name in sorted(DIFFICULT_CLASSES)
            },
        },
        "invariance": {
            "aac_128_wrapper_gain_trim": invariance,
        },
        "gate": {
            "maximum_false_positives": MAXIMUM_FALSE_POSITIVES,
            "observed_false_positives": overall[
                "false_positive_count"
            ],
            "hard_negative_results": hard_negative_gate,
            "scoped_class_results": scoped_gate,
            "positive_reason_failure_case_ids": reason_failures,
            "runtime": {
                "maximum_p95_overhead_percent": (
                    MAXIMUM_P95_RUNTIME_OVERHEAD_PERCENT
                ),
                "observed_p95_overhead_percent": performance_p95,
                "passed": performance_passed,
            },
            "memory": {
                **precommit["memory_contract"],
                "performance_p95_peak_rss_increase_percent": performance[
                    "summary"
                ]["p95_peak_rss_increase_percent"],
            },
            "passed": gate_passed,
        },
        "disposition": (
            "external_transfer_passed_release_heldout_still_sealed"
            if gate_passed
            else "candidate_rejected_external_transfer_consumed"
        ),
        "warnings": [
            (
                "This corpus is now observed and cannot be reused as an "
                "untouched gate for a revised candidate."
            ),
            (
                "A pass is external-transfer evidence only. The separate "
                "release-held-out labels remain sealed, feature version 0 "
                "remains experimental, and the public verdict stays disabled."
            ),
        ],
        "case_results": rows,
    }
    write_new_json(args.output, report)
    print(
        f"evaluated {len(rows)} cases; FP="
        f"{overall['false_positive_count']}/{overall['negative_count']}; "
        f"gate_passed={gate_passed}"
    )
    return 0 if gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
