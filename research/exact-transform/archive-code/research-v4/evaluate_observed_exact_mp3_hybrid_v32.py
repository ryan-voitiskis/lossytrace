#!/usr/bin/env python3
"""Evaluate the pre-locked v32 exact MP3 hybrid branch on observed MUSDB data."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_LOCK = ROOT / "observed-exact-mp3-hybrid-v32-rule-lock.json"
DEFAULT_AMENDMENT = ROOT / "observed-exact-mp3-hybrid-v32-lock-amendment-001.json"
DEFAULT_PROBE = ROOT / "observed-musdb-mp3-history-v32.json"
DEFAULT_V29_EVALUATION = ROOT / "observed-v29-policy-evaluation.json"
DEFAULT_FEATURES = (
    ROOT
    / "prior-gate-evidence"
    / "research-v3"
    / "external-transfer"
    / "musdb18hq-frozen-measurement-v28.json"
)
DEFAULT_OUTPUT = ROOT / "observed-exact-mp3-hybrid-v32-musdb-evaluation.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def unique_by_case(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{label} row lacks a non-empty case_id")
        if case_id in result:
            raise ValueError(f"{label} contains duplicate case_id {case_id}")
        result[case_id] = row
    return result


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    supported = [row for row in rows if row["signal_supported"]]
    negatives = [row for row in supported if row["expectation"] == "controlled_negative"]
    positives = [row for row in supported if row["expectation"] == "controlled_positive"]
    branch_negative_alerts = [row for row in negatives if row["branch_predicted_positive"]]
    branch_positive_alerts = [row for row in positives if row["branch_predicted_positive"]]
    union_negative_alerts = [row for row in negatives if row["union_predicted_positive"]]
    union_positive_alerts = [row for row in positives if row["union_predicted_positive"]]
    return {
        "case_count": len(rows),
        "supported_case_count": len(supported),
        "supported_negative_count": len(negatives),
        "supported_positive_count": len(positives),
        "branch_supported_negative_alert_count": len(branch_negative_alerts),
        "branch_supported_negative_alert_rate": ratio(len(branch_negative_alerts), len(negatives)),
        "branch_supported_positive_alert_count": len(branch_positive_alerts),
        "branch_supported_positive_recall": ratio(len(branch_positive_alerts), len(positives)),
        "union_supported_negative_alert_count": len(union_negative_alerts),
        "union_supported_negative_alert_rate": ratio(len(union_negative_alerts), len(negatives)),
        "union_supported_positive_alert_count": len(union_positive_alerts),
        "union_supported_positive_recall": ratio(len(union_positive_alerts), len(positives)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--v29-evaluation", type=Path, default=DEFAULT_V29_EVALUATION)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    paths = {
        "rule_lock": args.lock.resolve(),
        "lock_amendment": args.amendment.resolve(),
        "probe_measurement": args.probe.resolve(),
        "v29_evaluation": args.v29_evaluation.resolve(),
        "v28_feature_measurement": args.features.resolve(),
        "evaluator": Path(__file__).resolve(),
    }
    inputs = {
        name: {"path": str(path), "sha256": sha256(path)}
        for name, path in paths.items()
    }

    lock = load(paths["rule_lock"])
    amendment = load(paths["lock_amendment"])
    probe = load(paths["probe_measurement"])
    v29 = load(paths["v29_evaluation"])
    features = load(paths["v28_feature_measurement"])

    if lock.get("candidate_id") != "exact-mp3-hybrid-sparsity-edge-v32-development":
        raise ValueError("unexpected v32 candidate_id")
    if lock.get("public_verdict_enabled") is not False:
        raise ValueError("rule lock unexpectedly enables a public verdict")
    if amendment.get("original_rule_lock", {}).get("sha256") != inputs["rule_lock"]["sha256"]:
        raise ValueError("administrative amendment does not bind the supplied rule lock")
    amended_harness_sha = amendment.get("amendment", {}).get("amended_harness_sha256")
    if probe.get("inputs", {}).get("harness", {}).get("sha256") != amended_harness_sha:
        raise ValueError("probe report does not use the administratively amended harness")
    if probe.get("public_verdict_enabled") is not False:
        raise ValueError("probe report unexpectedly enables a public verdict")
    if probe.get("release_heldout_opened") is not False:
        raise ValueError("probe report unexpectedly opened the release heldout")
    if probe.get("case_count") != len(probe.get("results", [])):
        raise ValueError("probe case_count does not match result rows")

    probe_rows = unique_by_case(probe["results"], "probe")
    v29_rows = unique_by_case(v29["case_results"], "v29 evaluation")
    feature_rows = unique_by_case(features["results"], "v28 features")
    if set(probe_rows) - set(v29_rows):
        raise ValueError("some probe cases are absent from the v29 evaluation")
    if set(probe_rows) - set(feature_rows):
        raise ValueError("some probe cases are absent from the v28 feature measurement")

    expected_runner_sha = probe.get("inputs", {}).get("runner", {}).get("sha256")
    expected_harness_sha = probe.get("inputs", {}).get("harness", {}).get("sha256")
    expected_manifest_sha = probe.get("inputs", {}).get("manifest", {}).get("sha256")
    expected_fingerprints_sha = probe.get("inputs", {}).get("fingerprints", {}).get("sha256")
    for row in probe_rows.values():
        if row.get("runner_sha256") != expected_runner_sha:
            raise ValueError(f"{row['case_id']} has the wrong runner hash")
        if row.get("harness_sha256") != expected_harness_sha:
            raise ValueError(f"{row['case_id']} has the wrong harness hash")
        if row.get("manifest_sha256") != expected_manifest_sha:
            raise ValueError(f"{row['case_id']} has the wrong manifest hash")
        if row.get("fingerprints_sha256") != expected_fingerprints_sha:
            raise ValueError(f"{row['case_id']} has the wrong fingerprints hash")

    branch = lock["branch"]
    drop_threshold = float(branch["spectral_edge_drop_db_exclusive"])
    persistence_threshold = float(branch["spectral_edge_persistence_inclusive"])
    hybrid_threshold = float(branch["hybrid_small_coefficient_fraction_exclusive"])
    selected_bin = int(lock["probe"]["selected_zero_based_bin"])
    selection_groups = set(lock["selection_evidence"]["source_groups"])

    evaluated: list[dict[str, Any]] = []
    for case_id in sorted(probe_rows):
        probe_row = probe_rows[case_id]
        v29_row = v29_rows[case_id]
        feature_row = feature_rows[case_id]
        trace = feature_row["runner"]["compression_trace"]
        hybrid_fraction = float(
            probe_row["probe"]["small_fraction_1e4_by_bin_24"][selected_bin]
        )
        signal_supported = bool(v29_row["signal_supported"])
        edge_passed = (
            float(trace["spectral_edge_drop_db"]) > drop_threshold
            and float(trace["spectral_edge_persistence"]) >= persistence_threshold
        )
        hybrid_passed = hybrid_fraction > hybrid_threshold
        branch_alert = signal_supported and edge_passed and hybrid_passed
        old_alert = signal_supported and bool(v29_row["predicted_positive"])
        union_alert = old_alert or branch_alert
        if (
            probe_row["class"] != v29_row["class"]
            or probe_row["class"] != feature_row["class"]
            or probe_row["expectation"] != v29_row["expectation"]
            or probe_row["expectation"] != feature_row["expectation"]
            or probe_row["source_group"] != v29_row["source_group"]
            or probe_row["source_group"] != feature_row["source_group"]
        ):
            raise ValueError(f"joined metadata mismatch for {case_id}")
        evaluated.append(
            {
                "case_id": case_id,
                "class": probe_row["class"],
                "expectation": probe_row["expectation"],
                "source_group": probe_row["source_group"],
                "selection_source_group": probe_row["source_group"] in selection_groups,
                "signal_supported": signal_supported,
                "support_failures": v29_row["support_failures"],
                "spectral_edge_drop_db": trace["spectral_edge_drop_db"],
                "spectral_edge_persistence": trace["spectral_edge_persistence"],
                "hybrid_small_fraction": hybrid_fraction,
                "edge_passed": edge_passed,
                "hybrid_passed": hybrid_passed,
                "branch_predicted_positive": branch_alert,
                "v29_predicted_positive": old_alert,
                "union_predicted_positive": union_alert,
            }
        )

    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evaluated:
        by_class[row["class"]].append(row)
    selection = [row for row in evaluated if row["selection_source_group"]]
    non_selection = [row for row in evaluated if not row["selection_source_group"]]

    mp3_class = "musdb_mp3_128_to_flac16"
    apple_class = "musdb_aac_at_128_to_flac16"
    mp3_non_selection = [
        row for row in non_selection if row["class"] == mp3_class and row["signal_supported"]
    ]
    apple_non_selection = [
        row for row in non_selection if row["class"] == apple_class and row["signal_supported"]
    ]
    mp3_recall = ratio(
        sum(row["branch_predicted_positive"] for row in mp3_non_selection),
        len(mp3_non_selection),
    )
    apple_recall = ratio(
        sum(row["branch_predicted_positive"] for row in apple_non_selection),
        len(apple_non_selection),
    )
    negative_alerts = [
        row
        for row in evaluated
        if row["signal_supported"]
        and row["expectation"] == "controlled_negative"
        and row["branch_predicted_positive"]
    ]
    non_selection_negative_alerts = [
        row for row in negative_alerts if not row["selection_source_group"]
    ]
    safety_passed = not negative_alerts and not non_selection_negative_alerts
    recall_passed = (
        mp3_recall is not None
        and mp3_recall >= 0.9
        and apple_recall is not None
        and apple_recall >= 0.9
    )
    musdb_gate_passed = safety_passed and recall_passed

    unsupported_counts = Counter(
        row["class"] for row in evaluated if not row["signal_supported"]
    )
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "state": (
            "musdb_broad_observed_screen_passed_pending_other_corpora"
            if musdb_gate_passed
            else "locked_v32_branch_rejected_by_musdb_broad_observed_screen"
        ),
        "candidate_id": lock["candidate_id"],
        "candidate_frozen": False,
        "new_external_transfer_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "warning": (
            "Development evidence only. Passing this MUSDB screen does not freeze a "
            "candidate, open a fresh external transfer, or authorize a public verdict."
        ),
        "inputs": inputs,
        "locked_rule": {
            "support": branch["support"],
            "spectral_edge_drop_db_exclusive": drop_threshold,
            "spectral_edge_persistence_inclusive": persistence_threshold,
            "selected_zero_based_bin": selected_bin,
            "hybrid_small_coefficient_fraction_exclusive": hybrid_threshold,
            "successor": branch["successor"],
        },
        "inventory": {
            "case_count": len(evaluated),
            "source_group_count": len({row["source_group"] for row in evaluated}),
            "selection_source_group_count": len(selection_groups),
            "selection_case_count": len(selection),
            "non_selection_case_count": len(non_selection),
            "unsupported_by_class": dict(sorted(unsupported_counts.items())),
        },
        "metrics": {
            "all": metrics(evaluated),
            "selection": metrics(selection),
            "non_selection": metrics(non_selection),
            "by_class": {
                class_name: metrics(rows)
                for class_name, rows in sorted(by_class.items())
            },
        },
        "declared_musdb_gate": {
            "safety": {
                "required_supported_negative_alert_count": 0,
                "observed_supported_negative_alert_count": len(negative_alerts),
                "observed_non_selection_supported_negative_alert_count": len(
                    non_selection_negative_alerts
                ),
                "passed": safety_passed,
            },
            "non_selection_recall": {
                "mp3_128_minimum": 0.9,
                "mp3_128_observed": mp3_recall,
                "apple_aac_128_minimum": 0.9,
                "apple_aac_128_observed": apple_recall,
                "passed": recall_passed,
            },
            "passed": musdb_gate_passed,
            "next_required_action": (
                "Measure the unchanged locked rule on the remaining named observed corpora."
                if musdb_gate_passed
                else "Reject v32 unchanged. Do not tune against these broad-screen cases."
            ),
        },
        "supported_negative_branch_alert_case_ids": [
            row["case_id"] for row in negative_alerts
        ],
        "case_results": evaluated,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["declared_musdb_gate"], indent=2, sort_keys=True))
    print(f"wrote {args.output}")
    return 0 if musdb_gate_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
