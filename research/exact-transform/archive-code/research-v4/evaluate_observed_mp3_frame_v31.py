#!/usr/bin/env python3
"""Evaluate the predeclared 1152-sample MP3 diagnostic on consumed data."""

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
TRANSFORM = ROOT / "observed-independent-mp3-frame-v31.json"
BASELINE = ROOT / "external-transfer/independent-v29-evaluation.json"
LOCK = ROOT / "observed-aac-phase-v30-rule-lock.json"
OUTPUT = ROOT / "observed-independent-mp3-frame-v31-evaluation.json"


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


def circular_distance(left: int, right: int, modulus: int) -> int:
    distance = abs(left - right)
    return min(distance, modulus - distance)


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

    false_positives = [
        row for row in supported_negatives if row["mp3_frame_alert"]
    ]
    return {
        "case_count": len(rows),
        "positive_count": len(positives),
        "negative_count": len(negatives),
        "supported_positive_count": len(supported_positives),
        "supported_negative_count": len(supported_negatives),
        "mp3_frame_supported_true_positive_count": count(
            "mp3_frame_alert", supported_positives
        ),
        "mp3_frame_supported_false_positive_count": len(false_positives),
        "mp3_frame_supported_false_positive_case_ids": [
            row["case_id"] for row in false_positives
        ],
        "v29_supported_true_positive_count": count(
            "v29_baseline_alert", supported_positives
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
    if lock.get("separate_diagnostic", {}).get("profile") != (
        "mp3-frame-verification-v31"
    ):
        raise SystemExit("predeclared diagnostic contract differs")
    transform_report = load_json(TRANSFORM)
    baseline_report = load_json(BASELINE)
    if transform_report.get("profile") != "mp3-frame-verification-v31":
        raise SystemExit("transform profile differs")
    transform_rows = {
        row["case_id"]: row for row in transform_report["results"]
    }
    baseline_rows = {
        row["case_id"]: row for row in baseline_report["case_results"]
    }
    if set(transform_rows) != set(baseline_rows):
        raise SystemExit("transform/baseline inventory differs")

    results = []
    for case_id, transform in sorted(transform_rows.items()):
        baseline = baseline_rows[case_id]
        if any(
            transform[field] != baseline[field]
            for field in ("case_id", "class", "expectation", "source_group")
        ):
            raise SystemExit(f"{case_id}: joined row metadata differs")
        grid = transform["runner"]["transform_grid_probe"]
        mp3 = grid.get("mp3_long_sine")
        verification = (
            mp3.get("multi_candidate_phase_verification")
            if isinstance(mp3, dict)
            else None
        )
        if (
            transform["runner"].get("research_transform_grid_profile")
            != "mp3-frame-verification-v31"
            or grid.get("long_sine") is not None
            or grid.get("long_kbd") is not None
            or grid.get("opus_long_celt") is not None
            or grid.get("opus_short_celt") is not None
            or (
                grid.get("long_vorbis") is not None
                and not isinstance(grid.get("long_vorbis"), dict)
            )
            or (mp3 is not None and not isinstance(mp3, dict))
        ):
            raise SystemExit(f"{case_id}: v31 diagnostic contract differs")

        phase_distance = None
        peak_z_median = None
        peak_z_minimum = None
        if verification is not None:
            if (
                not isinstance(verification, dict)
                or int(mp3["block_samples"]) != 1152
                or int(verification["candidate_radius_samples"]) != 2
                or int(verification["control_phase_stride_samples"]) != 48
                or int(verification["frames_per_phase"]) != 16
                or not 3 <= int(verification["audio_block_count"]) <= 4
            ):
                raise SystemExit(
                    f"{case_id}: MP3 verification contract differs"
                )
            phase_distance = circular_distance(
                int(verification["discovery_aggregate_phase_samples"]),
                int(verification["verified_phase_samples"]),
                int(mp3["block_samples"]),
            )
            peak_z_median = float(verification["peak_z_median"])
            peak_z_minimum = float(verification["peak_z_minimum"])

        measurements = baseline["measurements"]
        edge_drop = measurements.get("low_edge_drop_db")
        persistence = measurements.get("low_edge_persistence")
        supported = bool(baseline["signal_supported"])
        edge_passed = (
            edge_drop is not None
            and float(edge_drop) > 3.0
            and persistence is not None
            and float(persistence) >= 0.0015
        )
        alert = (
            supported
            and edge_passed
            and peak_z_median is not None
            and peak_z_median > 3.0
            and phase_distance is not None
            and phase_distance <= 2
        )
        baseline_alert = supported and bool(baseline["predicted_positive"])
        results.append(
            {
                "case_id": case_id,
                "class": transform["class"],
                "expectation": transform["expectation"],
                "source_group": transform["source_group"],
                "signal_supported": supported,
                "support_failures": baseline["failures"],
                "spectral_edge_drop_db": edge_drop,
                "spectral_edge_persistence": persistence,
                "spectral_edge_passed": edge_passed,
                "verification_phase_distance_samples": phase_distance,
                "verification_peak_z_median": peak_z_median,
                "verification_peak_z_minimum": peak_z_minimum,
                "mp3_frame_alert": alert,
                "v29_baseline_alert": baseline_alert,
                "successor_union_alert": alert or baseline_alert,
            }
        )

    observed = metrics(results)
    mp3_128 = [
        row
        for row in results
        if row["class"] == "independent_mp3_128_to_flac16"
        and row["signal_supported"]
    ]
    incremental = sum(
        row["mp3_frame_alert"] and not row["v29_baseline_alert"]
        for row in mp3_128
    )
    safe = observed["mp3_frame_supported_false_positive_count"] == 0
    useful = incremental > 0
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": "predeclared_mp3_frame_diagnostic_evaluated",
        "disposition": (
            "diagnostic_supports_successor_research"
            if safe and useful
            else "diagnostic_rejected_no_safe_incremental_mp3_recall"
        ),
        "candidate_frozen": False,
        "new_external_transfer_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "warning": (
            "This diagnostic was evaluated only on consumed development data "
            "and cannot authorize a candidate, public verdict, or release."
        ),
        "inputs": {
            "evaluator": {
                "path": str(Path(__file__).resolve()),
                "sha256": sha256_file(Path(__file__).resolve()),
            },
            "rule_lock_with_predeclaration": {
                "path": str(LOCK),
                "sha256": sha256_file(LOCK),
            },
            "transform": {
                "path": str(TRANSFORM),
                "sha256": sha256_file(TRANSFORM),
            },
            "baseline": {
                "path": str(BASELINE),
                "sha256": sha256_file(BASELINE),
            },
        },
        "diagnostic_rule": {
            "profile": "mp3-frame-verification-v31",
            "spectral_edge_drop_db_exclusive": 3.0,
            "spectral_edge_persistence_inclusive": 0.0015,
            "verification_peak_z_median_exclusive": 3.0,
            "verification_phase_distance_inclusive": 2,
        },
        "decision": {
            "zero_supported_negative_false_positives": safe,
            "incremental_supported_mp3_128_true_positives": incremental,
            "proceed_to_successor_research": safe and useful,
        },
        "metrics": {
            "pooled": observed,
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
                "decision": report["decision"],
                "mp3_128": metrics(mp3_128),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
