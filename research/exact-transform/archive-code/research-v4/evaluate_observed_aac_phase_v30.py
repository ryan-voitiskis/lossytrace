#!/usr/bin/env python3
"""Evaluate the locked v30 AAC phase branch on consumed observed corpora."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(
    os.environ.get("LOSSYTRACE_EXACT_RESEARCH_ROOT", Path(__file__).resolve().parent)
).resolve()
LOCK = ROOT / "observed-aac-phase-v30-rule-lock.json"
BASELINE = ROOT / "observed-v29-policy-evaluation.json"
INPUTS = (
    {
        "corpus_id": "audio-integrity-external-transfer-sqam-20260731-001",
        "transform": ROOT / "observed-sqam-transform-v30.json",
        "features": (
            ROOT
            / "prior-gate-evidence/research/discovery/"
            "sqam-features-candidate-v2.json"
        ),
    },
    {
        "corpus_id": "audio-integrity-musdb18hq-controlled-20260731-001",
        "transform": ROOT / "observed-musdb18hq-transform-v30.json",
        "features": (
            ROOT
            / "prior-gate-evidence/research-v3/external-transfer/"
            "musdb18hq-frozen-measurement-v28.json"
        ),
    },
)
OUTPUT = ROOT / "observed-aac-phase-v30-evaluation.json"


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


def index_rows(report: dict, path: Path) -> dict[str, dict]:
    rows = report.get("results")
    if not isinstance(rows, list) or not rows:
        raise SystemExit(f"{path}: missing results")
    indexed = {row["case_id"]: row for row in rows}
    if len(indexed) != len(rows):
        raise SystemExit(f"{path}: duplicate case ids")
    return indexed


def circular_distance(left: int, right: int, modulus: int) -> int:
    distance = abs(left - right)
    return min(distance, modulus - distance)


def assess(
    transform: dict,
    feature: dict,
    baseline: dict,
    branch: dict,
) -> dict:
    case_id = transform["case_id"]
    if any(
        transform[field] != source[field]
        for source in (feature, baseline)
        for field in ("case_id", "class", "expectation", "source_group")
    ):
        raise SystemExit(f"{case_id}: joined row metadata differs")
    supported = bool(baseline["signal_supported"])
    trace = feature["runner"]["compression_trace"]
    edge_drop = trace.get("spectral_edge_drop_db")
    persistence = trace.get("spectral_edge_persistence")
    grid = transform["runner"]["transform_grid_probe"]
    sine = grid.get("long_sine")
    verification = (
        sine.get("multi_candidate_phase_verification")
        if isinstance(sine, dict)
        else None
    )
    optional_profiles = (
        sine,
        grid.get("mp3_long_sine"),
        grid.get("long_vorbis"),
    )
    if (
        transform["runner"].get("research_transform_grid_profile")
        != "verified-aac-sine-mp3-three-grid-v30"
        or grid.get("long_kbd") is not None
        or grid.get("opus_long_celt") is not None
        or grid.get("opus_short_celt") is not None
        or any(
            profile is not None and not isinstance(profile, dict)
            for profile in optional_profiles
        )
    ):
        raise SystemExit(f"{case_id}: v30 transform contract differs")

    phase_distance = None
    peak_z_median = None
    peak_z_minimum = None
    if verification is not None:
        if (
            not isinstance(verification, dict)
            or int(sine["block_samples"]) != 1024
            or int(verification["candidate_radius_samples"]) != 2
            or int(verification["control_phase_stride_samples"]) != 32
            or int(verification["frames_per_phase"]) != 16
            or not 3 <= int(verification["audio_block_count"]) <= 4
        ):
            raise SystemExit(f"{case_id}: AAC verification contract differs")
        phase_distance = circular_distance(
            int(verification["discovery_aggregate_phase_samples"]),
            int(verification["verified_phase_samples"]),
            int(sine["block_samples"]),
        )
        peak_z_median = float(verification["peak_z_median"])
        peak_z_minimum = float(verification["peak_z_minimum"])

    edge_passed = (
        edge_drop is not None
        and float(edge_drop)
        > float(branch["spectral_edge_drop_db_exclusive"])
        and persistence is not None
        and float(persistence)
        >= float(branch["spectral_edge_persistence_inclusive"])
    )
    branch_alert = (
        supported
        and edge_passed
        and peak_z_median is not None
        and peak_z_median
        > float(branch["verification_peak_z_median_exclusive"])
        and phase_distance is not None
        and phase_distance
        <= int(branch["verification_phase_distance_inclusive"])
    )
    baseline_alert = supported and bool(baseline["predicted_positive"])
    return {
        "case_id": case_id,
        "class": transform["class"],
        "expectation": transform["expectation"],
        "source_group": transform["source_group"],
        "signal_supported": supported,
        "support_failures": baseline["support_failures"],
        "spectral_edge_drop_db": edge_drop,
        "spectral_edge_persistence": persistence,
        "spectral_edge_passed": edge_passed,
        "verification_phase_distance_samples": phase_distance,
        "verification_peak_z_median": peak_z_median,
        "verification_peak_z_minimum": peak_z_minimum,
        "aac_sine_branch_alert": branch_alert,
        "v29_baseline_alert": baseline_alert,
        "successor_union_alert": branch_alert or baseline_alert,
    }


def metrics(rows: list[dict]) -> dict:
    positives = [
        row for row in rows if row["expectation"] == "controlled_positive"
    ]
    negatives = [row for row in rows if row["expectation"] == "negative"]
    supported_positives = [
        row for row in positives if row["signal_supported"]
    ]
    supported_negatives = [
        row for row in negatives if row["signal_supported"]
    ]

    def count(field: str, selected: list[dict]) -> int:
        return sum(bool(row[field]) for row in selected)

    branch_false_positives = [
        row for row in supported_negatives if row["aac_sine_branch_alert"]
    ]
    return {
        "case_count": len(rows),
        "positive_count": len(positives),
        "negative_count": len(negatives),
        "supported_positive_count": len(supported_positives),
        "supported_negative_count": len(supported_negatives),
        "aac_sine_branch_supported_true_positive_count": count(
            "aac_sine_branch_alert", supported_positives
        ),
        "aac_sine_branch_supported_false_positive_count": len(
            branch_false_positives
        ),
        "aac_sine_branch_supported_false_positive_case_ids": [
            row["case_id"] for row in branch_false_positives
        ],
        "aac_sine_branch_supported_false_positive_source_groups": sorted(
            {row["source_group"] for row in branch_false_positives}
        ),
        "v29_supported_true_positive_count": count(
            "v29_baseline_alert", supported_positives
        ),
        "v29_supported_false_positive_count": count(
            "v29_baseline_alert", supported_negatives
        ),
        "successor_union_supported_true_positive_count": count(
            "successor_union_alert", supported_positives
        ),
        "successor_union_supported_false_positive_count": count(
            "successor_union_alert", supported_negatives
        ),
    }


def grouped_metrics(rows: list[dict], field: str) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row[field]].append(row)
    return {
        group: metrics(selected) for group, selected in sorted(groups.items())
    }


def main() -> int:
    lock = load_json(LOCK)
    baseline_report = load_json(BASELINE)
    if (
        lock.get("candidate_id")
        != "verified-aac-sine-mp3-three-grid-v30-development"
        or lock.get("state")
        != "development_rule_locked_before_observed_sqam_musdb_v30"
    ):
        raise SystemExit("v30 rule lock contract differs")
    baseline_rows = {
        row["case_id"]: row for row in baseline_report["case_results"]
    }
    branch = lock["aac_sine_branch"]
    results = []
    input_reports = []
    for item in INPUTS:
        transform_report = load_json(item["transform"])
        feature_report = load_json(item["features"])
        transform_rows = index_rows(transform_report, item["transform"])
        feature_rows = index_rows(feature_report, item["features"])
        if set(transform_rows) != set(feature_rows):
            raise SystemExit(
                f"{item['corpus_id']}: feature/transform inventory differs"
            )
        missing_baseline = set(transform_rows) - set(baseline_rows)
        if missing_baseline:
            raise SystemExit(
                f"{item['corpus_id']}: missing baseline rows: "
                f"{sorted(missing_baseline)[:3]}"
            )
        for case_id, transform in sorted(transform_rows.items()):
            results.append(
                {
                    "corpus_id": item["corpus_id"],
                    **assess(
                        transform,
                        feature_rows[case_id],
                        baseline_rows[case_id],
                        branch,
                    ),
                }
            )
        input_reports.append(
            {
                "corpus_id": item["corpus_id"],
                "case_count": len(transform_rows),
                "transform": {
                    "path": str(item["transform"]),
                    "sha256": sha256_file(item["transform"]),
                },
                "features": {
                    "path": str(item["features"]),
                    "sha256": sha256_file(item["features"]),
                },
            }
        )

    by_corpus = grouped_metrics(results, "corpus_id")
    pooled = metrics(results)
    gates = {
        corpus_id: (
            corpus_metrics["supported_negative_count"] > 0
            and corpus_metrics[
                "aac_sine_branch_supported_false_positive_count"
            ]
            == 0
        )
        for corpus_id, corpus_metrics in by_corpus.items()
    }
    gate_passed = (
        len(gates) == len(INPUTS)
        and all(gates.values())
        and pooled["aac_sine_branch_supported_false_positive_count"] == 0
    )
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": "locked_v30_aac_phase_branch_observed_screen_complete",
        "disposition": (
            "locked_v30_branch_passed_consumed_observed_safety_screen"
            if gate_passed
            else "locked_v30_branch_rejected_supported_false_positive"
        ),
        "candidate_frozen": False,
        "new_external_transfer_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "warning": (
            "This is consumed development evidence. The locked branch cannot "
            "be tuned against these results; a successor must be identified "
            "separately and pass a fresh provenance-locked external gate."
        ),
        "inputs": {
            "evaluator": {
                "path": str(Path(__file__).resolve()),
                "sha256": sha256_file(Path(__file__).resolve()),
            },
            "rule_lock": {
                "path": str(LOCK),
                "sha256": sha256_file(LOCK),
            },
            "baseline_evaluation": {
                "path": str(BASELINE),
                "sha256": sha256_file(BASELINE),
            },
            "reports": input_reports,
        },
        "policy": {
            "candidate_id": lock["candidate_id"],
            "profile": lock["profile"],
            "aac_sine_branch": branch,
        },
        "gate": {
            "maximum_supported_negative_false_positives": 0,
            "by_corpus_passed": gates,
            "pooled_passed": gate_passed,
        },
        "metrics": {
            "pooled": pooled,
            "by_corpus": by_corpus,
            "by_class": grouped_metrics(results, "class"),
        },
        "case_results": results,
    }
    write_new_json(OUTPUT, report)
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "sha256": sha256_file(OUTPUT),
                "disposition": report["disposition"],
                "pooled": pooled,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
