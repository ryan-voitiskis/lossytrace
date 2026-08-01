#!/usr/bin/env python3
"""Apply the locked quantization/periodicity rule to consumed observed data."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


LOW_MPV = 0.5
LOW_QMAD = 0.0035
HIGH_MPV = 2.5
HIGH_QMAD = 0.001
EDGE_QUANT_PROBABILITY = 0.055
EDGE_MINIMUM_KHZ = 3.0
EDGE_MINIMUM_PERSISTENCE = 0.0015
STRONG_EDGE_QUANT_PROBABILITY = 0.031
STRONG_EDGE_MINIMUM_KHZ = 20.0
STRONG_EDGE_MINIMUM_PERSISTENCE = 0.2


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_atomic(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace report: {path}")
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


def keyed(rows: list[dict], *, source: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for row in rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or case_id in result:
            raise SystemExit(f"{source}: invalid or duplicate case_id")
        result[case_id] = row
    return result


def mp3_verification_peak(row: dict) -> float | None:
    mp3 = row["runner"]["transform_grid_probe"]["mp3_long_sine"]
    if not isinstance(mp3, dict):
        return None
    verification = mp3.get("multi_candidate_phase_verification")
    if not isinstance(verification, dict):
        return None
    value = verification.get("peak_z_median")
    return float(value) if value is not None else None


def primary_alert(mpv: float | None, qmad: float | None) -> bool:
    if mpv is None or qmad is None:
        return False
    return (mpv > LOW_MPV and qmad > LOW_QMAD) or (
        mpv > HIGH_MPV and qmad > HIGH_QMAD
    )


def metrics(rows: list[dict]) -> dict:
    negatives = [row for row in rows if row["expectation"] == "negative"]
    positives = [row for row in rows if row["expectation"] != "negative"]
    supported = [row for row in rows if row["signal_supported"]]
    supported_negatives = [
        row for row in negatives if row["signal_supported"]
    ]
    supported_positives = [
        row for row in positives if row["signal_supported"]
    ]
    return {
        "case_count": len(rows),
        "negative_count": len(negatives),
        "positive_count": len(positives),
        "supported_count": len(supported),
        "supported_negative_count": len(supported_negatives),
        "supported_positive_count": len(supported_positives),
        "primary_raw_alert_count": sum(
            row["primary_complement_alert"] for row in rows
        ),
        "primary_raw_false_positive_count": sum(
            row["primary_complement_alert"] for row in negatives
        ),
        "edge_quantization_raw_false_positive_count": sum(
            row["edge_quantization_alert"] for row in negatives
        ),
        "strong_edge_quantization_raw_false_positive_count": sum(
            row["strong_edge_quantization_alert"] for row in negatives
        ),
        "primary_raw_true_positive_count": sum(
            row["primary_complement_alert"] for row in positives
        ),
        "primary_supported_false_positive_count": sum(
            row["primary_complement_alert"] for row in supported_negatives
        ),
        "primary_supported_true_positive_count": sum(
            row["primary_complement_alert"] for row in supported_positives
        ),
        "edge_quantization_supported_false_positive_count": sum(
            row["edge_quantization_alert"] for row in supported_negatives
        ),
        "edge_quantization_supported_true_positive_count": sum(
            row["edge_quantization_alert"] for row in supported_positives
        ),
        "strong_edge_quantization_supported_false_positive_count": sum(
            row["strong_edge_quantization_alert"]
            for row in supported_negatives
        ),
        "strong_edge_quantization_supported_true_positive_count": sum(
            row["strong_edge_quantization_alert"]
            for row in supported_positives
        ),
        "v29_supported_false_positive_count": sum(
            row["v29_predicted_positive"] for row in supported_negatives
        ),
        "v29_supported_true_positive_count": sum(
            row["v29_predicted_positive"] for row in supported_positives
        ),
        "union_supported_false_positive_count": sum(
            row["successor_union_alert"] for row in supported_negatives
        ),
        "union_supported_true_positive_count": sum(
            row["successor_union_alert"] for row in supported_positives
        ),
        "primary_supported_false_positive_case_ids": [
            row["case_id"]
            for row in supported_negatives
            if row["primary_complement_alert"]
        ],
        "primary_raw_false_positive_case_ids": [
            row["case_id"]
            for row in negatives
            if row["primary_complement_alert"]
        ],
        "edge_quantization_raw_false_positive_case_ids": [
            row["case_id"]
            for row in negatives
            if row["edge_quantization_alert"]
        ],
        "strong_edge_quantization_raw_false_positive_case_ids": [
            row["case_id"]
            for row in negatives
            if row["strong_edge_quantization_alert"]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule-lock", type=Path, required=True)
    parser.add_argument("--policy-evaluation", type=Path, required=True)
    parser.add_argument(
        "--quantization-report",
        type=Path,
        action="append",
        required=True,
    )
    parser.add_argument(
        "--transform-report",
        type=Path,
        action="append",
        required=True,
    )
    parser.add_argument(
        "--feature-report",
        type=Path,
        action="append",
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rule_path = args.rule_lock.expanduser().resolve()
    policy_path = args.policy_evaluation.expanduser().resolve()
    output = args.output.expanduser().resolve()
    rule_lock = load_json(rule_path)
    policy = load_json(policy_path)
    if (
        rule_lock.get("state")
        != "development_rule_locked_before_observed_quantization_report"
        or rule_lock.get("candidate_frozen") is not False
        or rule_lock.get("release_heldout_opened") is not False
        or rule_lock.get("public_verdict_enabled") is not False
    ):
        raise SystemExit("rule lock contract differs")
    locked_policy = rule_lock["inputs"]["observed_v29_policy_evaluation"]
    if (
        sha256_file(policy_path) != locked_policy["sha256"]
        or policy.get("state") != "observed_development_candidate_screen"
        or policy.get("candidate_frozen") is not False
        or policy.get("release_heldout_opened") is not False
        or policy.get("public_verdict_enabled") is not False
    ):
        raise SystemExit("observed v29 policy input differs from rule lock")
    policy_rows = keyed(
        policy["case_results"],
        source=str(policy_path),
    )

    locked_transform_hashes = {
        rule_lock["inputs"][key]["sha256"]
        for key in ("sqam_transform", "musdb18hq_transform")
    }
    transform_by_manifest: dict[str, tuple[Path, dict, dict[str, dict]]] = {}
    actual_transform_hashes = set()
    for value in args.transform_report:
        path = value.expanduser().resolve()
        report = load_json(path)
        digest = sha256_file(path)
        actual_transform_hashes.add(digest)
        if (
            report.get("state")
            != "observed_development_research_measurement"
            or report.get("candidate_frozen") is not False
            or report.get("new_external_transfer_opened") is not False
            or report.get("release_heldout_opened") is not False
            or report.get("public_verdict_enabled") is not False
        ):
            raise SystemExit(f"{path}: transform report contract differs")
        manifest_sha = report["inputs"]["manifest"]["sha256"]
        if manifest_sha in transform_by_manifest:
            raise SystemExit(f"{path}: duplicate transform manifest")
        transform_by_manifest[manifest_sha] = (
            path,
            report,
            keyed(report["results"], source=str(path)),
        )
    if (
        not actual_transform_hashes
        or not actual_transform_hashes <= locked_transform_hashes
    ):
        raise SystemExit("transform inputs differ from rule lock")

    locked_feature_hashes = {
        rule_lock["inputs"][key]["sha256"]
        for key in ("sqam_features", "musdb18hq_features")
    }
    actual_feature_hashes = set()
    feature_rows: dict[str, dict] = {}
    feature_inputs = []
    for value in args.feature_report:
        path = value.expanduser().resolve()
        report = load_json(path)
        digest = sha256_file(path)
        actual_feature_hashes.add(digest)
        rows = keyed(report["results"], source=str(path))
        overlap = set(rows) & set(feature_rows)
        if overlap:
            raise SystemExit(f"{path}: duplicate feature cases")
        feature_rows.update(rows)
        feature_inputs.append(
            {
                "path": str(path),
                "sha256": digest,
                "case_count": len(rows),
            }
        )
    if (
        not actual_feature_hashes
        or not actual_feature_hashes <= locked_feature_hashes
    ):
        raise SystemExit("feature inputs differ from rule lock")

    input_reports = []
    results = []
    corpus_case_ids: dict[str, set[str]] = {}
    for value in args.quantization_report:
        path = value.expanduser().resolve()
        report = load_json(path)
        if (
            report.get("state")
            != "retained_observed_development_research"
            or report.get("release_heldout_opened") is not False
            or report.get("public_verdict_enabled") is not False
            or report.get("sampling", {}).get("audio_window_count") != 8
            or report.get("sampling", {}).get(
                "scale_factor_hypothesis_count"
            )
            != 8
        ):
            raise SystemExit(f"{path}: quantization report contract differs")
        commitment = report["input_commitment"]
        manifest_sha = commitment["manifest_sha256"]
        transform_item = transform_by_manifest.get(manifest_sha)
        if transform_item is None:
            raise SystemExit(f"{path}: no bound transform report")
        transform_path, transform_report, transform_rows = transform_item
        if (
            commitment["fingerprints_sha256"]
            != transform_report["inputs"]["fingerprints"]["sha256"]
        ):
            raise SystemExit(f"{path}: corpus fingerprints differ")
        quant_rows = keyed(report["cases"], source=str(path))
        case_ids = set(quant_rows)
        if (
            case_ids != set(transform_rows)
            or not case_ids <= set(policy_rows)
            or len(case_ids) != report.get("case_count")
        ):
            raise SystemExit(f"{path}: joined case inventory differs")
        corpus_id = commitment["corpus_id"]
        if corpus_id in corpus_case_ids:
            raise SystemExit(f"{path}: duplicate corpus_id")
        corpus_case_ids[corpus_id] = case_ids
        for case_id in sorted(case_ids):
            quant = quant_rows[case_id]
            transform = transform_rows[case_id]
            old = policy_rows[case_id]
            feature = feature_rows.get(case_id)
            if feature is None:
                raise SystemExit(f"{case_id}: missing feature row")
            if (
                quant["audio_sha256"] != transform["audio_sha256"]
                or quant["audio_sha256"]
                != feature["runner"]["audio_sha256"]
                or any(
                    quant[field] != transform[field]
                    for field in (
                        "class",
                        "expectation",
                        "source_group",
                    )
                )
                or any(
                    quant[field] != old[field]
                    for field in (
                        "class",
                        "expectation",
                        "source_group",
                    )
                )
                or any(
                    quant[field] != feature[field]
                    for field in (
                        "class",
                        "expectation",
                        "source_group",
                    )
                )
            ):
                raise SystemExit(f"{case_id}: joined row differs")
            mpv = mp3_verification_peak(transform)
            qmad = quant.get("offset_probability_mad")
            qmad = float(qmad) if qmad is not None else None
            qprob = quant.get("aac_quantization_probability")
            qprob = float(qprob) if qprob is not None else None
            trace = feature["runner"]["compression_trace"]
            edge_hz = trace.get("spectral_edge_hz")
            edge_khz = (
                float(edge_hz) / 1_000.0 if edge_hz is not None else None
            )
            persistence = trace.get("spectral_edge_persistence")
            persistence = (
                float(persistence) if persistence is not None else None
            )
            alert = primary_alert(mpv, qmad)
            edge_quantization_alert = (
                qprob is not None
                and qprob > EDGE_QUANT_PROBABILITY
                and edge_khz is not None
                and edge_khz > EDGE_MINIMUM_KHZ
                and persistence is not None
                and persistence >= EDGE_MINIMUM_PERSISTENCE
            )
            strong_edge_quantization_alert = (
                qprob is not None
                and qprob > STRONG_EDGE_QUANT_PROBABILITY
                and edge_khz is not None
                and edge_khz > STRONG_EDGE_MINIMUM_KHZ
                and persistence is not None
                and persistence > STRONG_EDGE_MINIMUM_PERSISTENCE
            )
            supported = bool(old["signal_supported"])
            v29_alert = bool(old["predicted_positive"]) and supported
            results.append(
                {
                    "case_id": case_id,
                    "corpus_id": corpus_id,
                    "class": quant["class"],
                    "expectation": quant["expectation"],
                    "source_group": quant["source_group"],
                    "signal_supported": supported,
                    "support_failures": old["support_failures"],
                    "mp3_multi_candidate_peak_z_median": mpv,
                    "offset_probability_mad": qmad,
                    "aac_quantization_probability": qprob,
                    "spectral_edge_khz": edge_khz,
                    "spectral_edge_persistence": persistence,
                    "primary_complement_alert": alert,
                    "edge_quantization_alert": edge_quantization_alert,
                    "strong_edge_quantization_alert": (
                        strong_edge_quantization_alert
                    ),
                    "v29_predicted_positive": v29_alert,
                    "successor_union_alert": supported
                    and (
                        v29_alert
                        or alert
                        or edge_quantization_alert
                        or strong_edge_quantization_alert
                    ),
                }
            )
        input_reports.append(
            {
                "corpus_id": corpus_id,
                "quantization_report": {
                    "path": str(path),
                    "sha256": sha256_file(path),
                },
                "transform_report": {
                    "path": str(transform_path),
                    "sha256": sha256_file(transform_path),
                },
                "case_count": len(case_ids),
                "manifest_sha256": manifest_sha,
                "fingerprints_sha256": commitment[
                    "fingerprints_sha256"
                ],
            }
        )

    expected_case_ids = set().union(*corpus_case_ids.values())
    if len(expected_case_ids) != sum(map(len, corpus_case_ids.values())):
        raise SystemExit("duplicate case across observed corpora")
    if {row["case_id"] for row in results} != expected_case_ids:
        raise SystemExit("result inventory differs")
    if set(feature_rows) != expected_case_ids:
        raise SystemExit("feature inventory differs")

    by_corpus_rows: dict[str, list[dict]] = defaultdict(list)
    by_class_rows: dict[str, list[dict]] = defaultdict(list)
    for row in results:
        by_corpus_rows[row["corpus_id"]].append(row)
        by_class_rows[row["class"]].append(row)
    pooled = metrics(results)
    by_corpus = {
        key: metrics(value) for key, value in sorted(by_corpus_rows.items())
    }
    by_class = {
        key: metrics(value) for key, value in sorted(by_class_rows.items())
    }
    corpus_gates = {
        key: value["supported_negative_count"] > 0
        and value["primary_supported_false_positive_count"] == 0
        for key, value in by_corpus.items()
    }
    edge_corpus_gates = {
        key: value["supported_negative_count"] > 0
        and value["edge_quantization_supported_false_positive_count"] == 0
        for key, value in by_corpus.items()
    }
    strong_edge_corpus_gates = {
        key: value["supported_negative_count"] > 0
        and value[
            "strong_edge_quantization_supported_false_positive_count"
        ]
        == 0
        for key, value in by_corpus.items()
    }
    gate_passed = (
        len(corpus_gates) == 2
        and all(corpus_gates.values())
        and pooled["primary_supported_false_positive_count"] == 0
    )
    early_stop_triggered = (
        pooled["primary_supported_false_positive_count"] > 0
    )
    if early_stop_triggered:
        disposition = "primary_complement_rejected_supported_false_positive"
    elif gate_passed:
        disposition = (
            "primary_complement_passed_consumed_observed_safety_screen"
        )
    else:
        disposition = "primary_complement_screen_incomplete"
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": "consumed_observed_quantization_rule_evaluated",
        "disposition": disposition,
        "candidate_frozen": False,
        "new_external_transfer_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "warning": (
            "This is post-selected, consumed development evidence. Passing "
            "does not authorize a public verdict or opening release holdout."
        ),
        "inputs": {
            "evaluator": {
                "path": str(Path(__file__).resolve()),
                "sha256": sha256_file(Path(__file__).resolve()),
            },
            "rule_lock": {
                "path": str(rule_path),
                "sha256": sha256_file(rule_path),
            },
            "policy_evaluation": {
                "path": str(policy_path),
                "sha256": sha256_file(policy_path),
            },
            "reports": sorted(
                input_reports,
                key=lambda row: row["corpus_id"],
            ),
            "feature_reports": sorted(
                feature_inputs,
                key=lambda row: row["path"],
            ),
        },
        "rule": {
            "low_mpv_exclusive": LOW_MPV,
            "low_qmad_exclusive": LOW_QMAD,
            "high_mpv_exclusive": HIGH_MPV,
            "high_qmad_exclusive": HIGH_QMAD,
            "edge_quantization_probability_exclusive": (
                EDGE_QUANT_PROBABILITY
            ),
            "edge_minimum_khz_exclusive": EDGE_MINIMUM_KHZ,
            "edge_minimum_persistence_inclusive": (
                EDGE_MINIMUM_PERSISTENCE
            ),
            "strong_edge_quantization_probability_exclusive": (
                STRONG_EDGE_QUANT_PROBABILITY
            ),
            "strong_edge_minimum_khz_exclusive": (
                STRONG_EDGE_MINIMUM_KHZ
            ),
            "strong_edge_minimum_persistence_exclusive": (
                STRONG_EDGE_MINIMUM_PERSISTENCE
            ),
        },
        "gate": {
            "scope": "v29 signal_supported negative cases",
            "required_supported_false_positives": 0,
            "intended_corpus_count": 2,
            "measured_corpus_count": len(corpus_gates),
            "early_stop_triggered": early_stop_triggered,
            "early_stop_reason": (
                "The locked decision rejects the branch on any supported "
                "negative alert, so measuring another observed corpus "
                "cannot change the rejection."
                if early_stop_triggered
                else None
            ),
            "primary_by_corpus_passed": corpus_gates,
            "primary_passed": gate_passed,
            "edge_quantization_by_corpus_passed": edge_corpus_gates,
            "edge_quantization_passed": (
                len(edge_corpus_gates) == 2
                and all(edge_corpus_gates.values())
            ),
            "strong_edge_quantization_by_corpus_passed": (
                strong_edge_corpus_gates
            ),
            "strong_edge_quantization_passed": (
                len(strong_edge_corpus_gates) == 2
                and all(strong_edge_corpus_gates.values())
            ),
        },
        "pooled_metrics": pooled,
        "by_corpus": by_corpus,
        "by_class": by_class,
        "case_count": len(results),
        "case_results": sorted(
            results,
            key=lambda row: (row["corpus_id"], row["case_id"]),
        ),
    }
    write_atomic(output, report)
    print(
        f"wrote {len(results)} cases; "
        f"supported FP={pooled['primary_supported_false_positive_count']}/"
        f"{pooled['supported_negative_count']}; "
        f"supported TP={pooled['primary_supported_true_positive_count']}/"
        f"{pooled['supported_positive_count']}; "
        f"gate_passed={gate_passed}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
