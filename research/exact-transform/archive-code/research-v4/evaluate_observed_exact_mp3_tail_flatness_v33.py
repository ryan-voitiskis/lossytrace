#!/usr/bin/env python3
"""Evaluate the locked v33 transform-tail branch on consumed development data."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
LOCK = ROOT / "observed-exact-mp3-tail-flatness-v33-rule-lock.json"
PREDECESSOR = ROOT / "observed-exact-mp3-hybrid-v32-broad-evaluation.json"
OUTPUT = ROOT / "observed-exact-mp3-tail-flatness-v33-evaluation.json"
PROBES = [
    ROOT / "observed-musdb-mp3-history-v32.json",
    ROOT / "observed-musdb-mp3-history-v32-complement.json",
    ROOT / "observed-independent-mp3-history-v32.json",
    ROOT / "observed-sqam-mp3-history-v32.json",
    ROOT / "observed-public-controlled-mp3-history-v32.json",
    ROOT / "observed-public-negative-mp3-history-v32.json",
    ROOT / "observed-public-hard-negative-mp3-history-v32.json",
]


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


def add_unique(
    target: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
    label: str,
) -> None:
    for row in rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{label} row lacks case_id")
        if case_id in target:
            raise ValueError(f"{label} duplicates {case_id}")
        target[case_id] = row


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    supported = [row for row in rows if row["signal_supported"]]
    negatives = [
        row for row in supported if row["expectation"] == "controlled_negative"
    ]
    positives = [
        row for row in supported if row["expectation"] == "controlled_positive"
    ]
    branch_negatives = [
        row for row in negatives if row["branch_predicted_positive"]
    ]
    branch_positives = [
        row for row in positives if row["branch_predicted_positive"]
    ]
    union_negatives = [
        row for row in negatives if row["union_predicted_positive"]
    ]
    union_positives = [
        row for row in positives if row["union_predicted_positive"]
    ]
    return {
        "case_count": len(rows),
        "supported_case_count": len(supported),
        "supported_negative_count": len(negatives),
        "supported_positive_count": len(positives),
        "branch_supported_negative_alert_count": len(branch_negatives),
        "branch_supported_positive_alert_count": len(branch_positives),
        "branch_supported_positive_recall": ratio(
            len(branch_positives), len(positives)
        ),
        "union_supported_negative_alert_count": len(union_negatives),
        "union_supported_positive_alert_count": len(union_positives),
        "union_supported_positive_recall": ratio(
            len(union_positives), len(positives)
        ),
    }


def invariance(
    rows: list[dict[str, Any]],
    corpus: str,
    classes: list[str],
) -> dict[str, Any]:
    relevant = [
        row
        for row in rows
        if row["corpus"] == corpus and row["class"] in classes
    ]
    groups: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in relevant:
        groups[row["source_group"]][row["class"]] = row
    complete_supported = 0
    mismatches = []
    for source_group, group in sorted(groups.items()):
        if set(group) != set(classes):
            continue
        if not all(group[name]["signal_supported"] for name in classes):
            continue
        complete_supported += 1
        decisions = {
            name: group[name]["branch_predicted_positive"] for name in classes
        }
        if len(set(decisions.values())) != 1:
            mismatches.append(
                {"source_group": source_group, "decisions": decisions}
            )
    return {
        "corpus": corpus,
        "classes": classes,
        "complete_supported_group_count": complete_supported,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "passed": not mismatches,
    }


def main() -> int:
    inputs = {
        "rule_lock": {"path": str(LOCK), "sha256": sha256(LOCK)},
        "predecessor_evaluation": {
            "path": str(PREDECESSOR),
            "sha256": sha256(PREDECESSOR),
        },
        "evaluator": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256(Path(__file__).resolve()),
        },
        "probe_reports": [
            {"path": str(path), "sha256": sha256(path)} for path in PROBES
        ],
    }
    lock = load(LOCK)
    predecessor = load(PREDECESSOR)
    if (
        lock.get("evidence_status", {}).get("current_evaluation_sha256")
        != inputs["predecessor_evaluation"]["sha256"]
    ):
        raise ValueError("v33 lock does not bind predecessor evaluation")
    if (
        predecessor.get("inventory", {}).get("case_count") != 3840
        or predecessor.get("release_heldout_opened") is not False
        or predecessor.get("public_verdict_enabled") is not False
    ):
        raise ValueError("predecessor evaluation contract differs")

    probe_rows: dict[str, dict[str, Any]] = {}
    expected_runner_sha = lock["probe"]["runner_sha256"]
    for path in PROBES:
        document = load(path)
        if (
            document.get("case_count") != len(document.get("results", []))
            or document.get("release_heldout_opened") is not False
            or document.get("public_verdict_enabled") is not False
            or document.get("inputs", {}).get("runner", {}).get("sha256")
            != expected_runner_sha
        ):
            raise ValueError(f"{path}: probe contract differs")
        add_unique(probe_rows, document["results"], str(path))
    predecessor_rows: dict[str, dict[str, Any]] = {}
    add_unique(
        predecessor_rows,
        predecessor["case_results"],
        str(PREDECESSOR),
    )
    if set(probe_rows) != set(predecessor_rows):
        raise ValueError("probe and predecessor inventories differ")

    branch = lock["branch"]
    cv_threshold = float(
        branch["tail_coefficient_of_variation_exclusive"]
    )
    attenuation_threshold = float(
        branch["tail_attenuation_ratio_exclusive"]
    )
    drop_threshold = float(branch["spectral_edge_drop_db_exclusive"])
    persistence_threshold = float(
        branch["spectral_edge_persistence_inclusive"]
    )
    evaluated = []
    for case_id in sorted(probe_rows):
        probe_row = probe_rows[case_id]
        old = predecessor_rows[case_id]
        means = probe_row["probe"]["mean_normalized_magnitude_by_bin_24"]
        if (
            not isinstance(means, list)
            or len(means) != 24
            or not all(
                isinstance(value, (int, float))
                and math.isfinite(float(value))
                and float(value) >= 0.0
                for value in means
            )
        ):
            raise ValueError(f"{case_id}: invalid mean feature")
        tail = [float(value) for value in means[19:24]]
        reference = [float(value) for value in means[14:18]]
        tail_mean = statistics.fmean(tail)
        reference_median = statistics.median(reference)
        finite_denominators = tail_mean > 0.0 and reference_median > 0.0
        tail_cv = (
            statistics.pstdev(tail) / tail_mean
            if finite_denominators
            else None
        )
        attenuation = (
            tail_mean / reference_median
            if finite_denominators
            else None
        )
        transform_passed = (
            tail_cv is not None
            and attenuation is not None
            and tail_cv < cv_threshold
            and attenuation < attenuation_threshold
        )
        drop = old["spectral_edge_drop_db"]
        persistence = old["spectral_edge_persistence"]
        edge_passed = (
            isinstance(drop, (int, float))
            and isinstance(persistence, (int, float))
            and float(drop) > drop_threshold
            and float(persistence) >= persistence_threshold
        )
        if (
            probe_row["class"] != old["class"]
            or probe_row["expectation"] != old["expectation"]
            or probe_row["source_group"] != old["source_group"]
        ):
            raise ValueError(f"{case_id}: joined metadata differs")
        signal_supported = bool(old["signal_supported"])
        branch_alert = signal_supported and edge_passed and transform_passed
        old_alert = signal_supported and bool(old["v29_predicted_positive"])
        evaluated.append(
            {
                "corpus": old["corpus"],
                "case_id": case_id,
                "class": old["class"],
                "expectation": old["expectation"],
                "source_group": old["source_group"],
                "signal_supported": signal_supported,
                "spectral_edge_drop_db": drop,
                "spectral_edge_persistence": persistence,
                "tail_mean": tail_mean,
                "tail_reference_median": reference_median,
                "tail_coefficient_of_variation": tail_cv,
                "tail_attenuation_ratio": attenuation,
                "edge_passed": edge_passed,
                "transform_passed": transform_passed,
                "branch_predicted_positive": branch_alert,
                "v29_predicted_positive": old_alert,
                "union_predicted_positive": old_alert or branch_alert,
            }
        )

    by_corpus: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evaluated:
        by_corpus[row["corpus"]].append(row)
        by_class[row["class"]].append(row)
    negative_alerts = [
        row
        for row in evaluated
        if row["signal_supported"]
        and row["expectation"] == "controlled_negative"
        and row["branch_predicted_positive"]
    ]
    corpus_safety = {
        corpus: {
            "supported_negative_alert_count": sum(
                row["signal_supported"]
                and row["expectation"] == "controlled_negative"
                and row["branch_predicted_positive"]
                for row in rows
            ),
        }
        for corpus, rows in sorted(by_corpus.items())
    }
    for result in corpus_safety.values():
        result["passed"] = result["supported_negative_alert_count"] == 0
    safety_passed = not negative_alerts and all(
        result["passed"] for result in corpus_safety.values()
    )

    recall_specs = [
        ("musdb_mp3_128_to_flac16", "musdb18hq", None, 0.9),
        ("musdb_aac_at_128_to_flac16", "musdb18hq", None, 0.9),
        (
            "independent_mp3_128_to_flac16",
            "independent_demand_maestro",
            "independent-demand-",
            0.75,
        ),
        (
            "independent_aac_at_128_to_flac16",
            "independent_demand_maestro",
            "independent-demand-",
            0.75,
        ),
    ]
    recall_results = {}
    recall_passed = True
    for class_name, corpus, source_prefix, minimum in recall_specs:
        rows = [
            row
            for row in evaluated
            if row["corpus"] == corpus
            and row["class"] == class_name
            and row["signal_supported"]
            and (
                source_prefix is None
                or row["source_group"].startswith(source_prefix)
            )
        ]
        observed = ratio(
            sum(row["branch_predicted_positive"] for row in rows), len(rows)
        )
        passed = observed is not None and observed >= minimum
        recall_passed = recall_passed and passed
        recall_results[class_name] = {
            "supported_case_count": len(rows),
            "alert_count": sum(
                row["branch_predicted_positive"] for row in rows
            ),
            "minimum": minimum,
            "observed": observed,
            "passed": passed,
        }

    invariance_results = [
        invariance(
            evaluated,
            "musdb18hq",
            [
                "musdb_aac_lc_128_to_flac16",
                "musdb_aac_lc_128_gain_minus3db_to_flac16",
                "musdb_aac_lc_128_to_aiff24",
                "musdb_aac_lc_128_to_wav16",
                "musdb_aac_lc_128_trim_137_to_flac16",
            ],
        ),
        invariance(
            evaluated,
            "independent_demand_maestro",
            [
                "independent_aac_lc_128_to_flac16",
                "independent_aac_lc_128_gain_minus3db_to_flac16",
                "independent_aac_lc_128_to_aiff24",
                "independent_aac_lc_128_to_wav16",
                "independent_aac_lc_128_trim_137_to_flac16",
            ],
        ),
        invariance(
            evaluated,
            "sqam",
            [
                "sqam_aac_lc_128_to_flac16",
                "sqam_aac_lc_128_gain_minus3db_to_flac16",
                "sqam_aac_lc_128_resample_44100_to_flac16",
                "sqam_aac_lc_128_to_aiff24",
                "sqam_aac_lc_128_to_wav16",
                "sqam_aac_lc_128_trim_137_to_flac16",
            ],
        ),
    ]
    invariance_passed = all(
        result["passed"] for result in invariance_results
    )
    passed = safety_passed and recall_passed and invariance_passed
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": (
            "v33_complete_consumed_development_screen_passed"
            if passed
            else "locked_v33_branch_rejected_by_consumed_development_screen"
        ),
        "candidate_id": lock["candidate_id"],
        "candidate_frozen": False,
        "new_external_transfer_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "warning": (
            "All cases are consumed development evidence. A pass cannot be "
            "represented as independent validation."
        ),
        "inputs": inputs,
        "locked_rule": branch,
        "inventory": {
            "case_count": len(evaluated),
            "corpus_case_counts": {
                corpus: len(rows)
                for corpus, rows in sorted(by_corpus.items())
            },
        },
        "metrics": {
            "pooled": metrics(evaluated),
            "by_corpus": {
                corpus: metrics(rows)
                for corpus, rows in sorted(by_corpus.items())
            },
            "by_class": {
                class_name: metrics(rows)
                for class_name, rows in sorted(by_class.items())
            },
        },
        "declared_gate": {
            "safety": {
                "required_supported_negative_alert_count": 0,
                "observed_supported_negative_alert_count": len(
                    negative_alerts
                ),
                "by_corpus": corpus_safety,
                "passed": safety_passed,
            },
            "recall": {
                "classes": recall_results,
                "passed": recall_passed,
            },
            "aac_invariance": {
                "groups": invariance_results,
                "passed": invariance_passed,
            },
            "passed": passed,
            "next_required_action": (
                "Prepare product integration and a genuinely fresh compact gate."
                if passed
                else "Reject v33 unchanged; do not tune against this screen."
            ),
        },
        "supported_negative_branch_alert_case_ids": [
            row["case_id"] for row in negative_alerts
        ],
        "case_results": evaluated,
    }
    OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["declared_gate"], indent=2, sort_keys=True))
    print(f"wrote {OUTPUT}")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
