#!/usr/bin/env python3
"""Evaluate the locked v32 branch across every predeclared observed corpus."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
LOCK = ROOT / "observed-exact-mp3-hybrid-v32-rule-lock.json"
AMENDMENT = ROOT / "observed-exact-mp3-hybrid-v32-lock-amendment-001.json"
SUPPLEMENT = ROOT / "observed-exact-mp3-hybrid-v32-lock-supplement-002.json"
V29_OBSERVED = ROOT / "observed-v29-policy-evaluation.json"
INDEPENDENT_V29 = ROOT / "external-transfer" / "independent-v29-evaluation.json"
OUTPUT = ROOT / "observed-exact-mp3-hybrid-v32-broad-evaluation.json"
DATA_HOME = Path(
    os.environ.get(
        "LOSSYTRACE_DATA_HOME",
        Path.home()
        / "Library/Application Support/lossytrace/benchmarks/audio-integrity-v1",
    )
).resolve()
MULTICODEC_ARCHIVE = (
    DATA_HOME
    / "private/audio-integrity-multicodec-explainable-research-20260731-001.tar.zst"
)
EXPLAINABLE_ARCHIVE = (
    DATA_HOME
    / "private/audio-integrity-explainable-sqam-research-20260731-001.tar.zst"
)

CORPORA = {
    "musdb18hq": {
        "probes": [
            ROOT / "observed-musdb-mp3-history-v32.json",
            ROOT / "observed-musdb-mp3-history-v32-complement.json",
        ],
        "feature_files": [
            ROOT
            / "prior-gate-evidence"
            / "research-v3"
            / "external-transfer"
            / "musdb18hq-frozen-measurement-v28.json"
        ],
        "evaluation": V29_OBSERVED,
        "expected_cases": 1770,
    },
    "independent_demand_maestro": {
        "probes": [ROOT / "observed-independent-mp3-history-v32.json"],
        "feature_files": [
            ROOT / "external-transfer" / "independent-v29-measurement.json"
        ],
        "evaluation": INDEPENDENT_V29,
        "expected_cases": 436,
    },
    "sqam": {
        "probes": [ROOT / "observed-sqam-mp3-history-v32.json"],
        "feature_archive": {
            "path": MULTICODEC_ARCHIVE,
            "members": [
                "research-v3/discovery/"
                "sqam-observed-aac-positives-features-v17.json",
                "research-v3/discovery/"
                "sqam-observed-pcm-negatives-features-v17-corrected.json",
                "research-v3/discovery/"
                "sqam-future-observed-features-v17-corrected.json",
            ],
        },
        "evaluation": V29_OBSERVED,
        "expected_cases": 980,
    },
    "public_controlled": {
        "probes": [ROOT / "observed-public-controlled-mp3-history-v32.json"],
        "feature_archive": {
            "path": EXPLAINABLE_ARCHIVE,
            "members": [
                "research/prior-evidence/long-block/"
                "public-controlled-transcodes-v16-report.json"
            ],
        },
        "evaluation": V29_OBSERVED,
        "expected_cases": 288,
    },
    "public_confirmed_pcm": {
        "probes": [ROOT / "observed-public-negative-mp3-history-v32.json"],
        "feature_archive": {
            "path": EXPLAINABLE_ARCHIVE,
            "members": [
                "research/prior-evidence/long-block/"
                "public-negatives-v16-report.json"
            ],
        },
        "evaluation": V29_OBSERVED,
        "expected_cases": 48,
    },
    "public_nsynth_sparse": {
        "probes": [
            ROOT / "observed-public-hard-negative-mp3-history-v32.json"
        ],
        "feature_archive": {
            "path": EXPLAINABLE_ARCHIVE,
            "members": [
                "research/prior-evidence/long-block/nsynth-v16-report.json"
            ],
        },
        "evaluation": V29_OBSERVED,
        "expected_cases": 318,
    },
}


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


def archive_json(archive: Path, member: str) -> dict[str, Any]:
    decompressor = subprocess.Popen(
        ["zstd", "-dc", str(archive)],
        stdout=subprocess.PIPE,
    )
    assert decompressor.stdout is not None
    extracted = subprocess.run(
        ["tar", "-xOf", "-", member],
        stdin=decompressor.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    decompressor.stdout.close()
    decompressor_returncode = decompressor.wait()
    if decompressor_returncode or extracted.returncode:
        raise ValueError(
            f"cannot read {member} from {archive}: "
            f"{extracted.stderr.decode(errors='replace').strip()}"
        )
    value = json.loads(extracted.stdout)
    if not isinstance(value, dict):
        raise ValueError(f"{archive}:{member} must contain a JSON object")
    return value


def add_unique(
    target: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
    label: str,
) -> None:
    for row in rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{label} row lacks a non-empty case_id")
        if case_id in target:
            raise ValueError(f"{label} contains duplicate case_id {case_id}")
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
        "unsupported_case_count": len(rows) - len(supported),
        "supported_negative_count": len(negatives),
        "supported_positive_count": len(positives),
        "branch_supported_negative_alert_count": len(branch_negatives),
        "branch_supported_negative_alert_rate": ratio(
            len(branch_negatives), len(negatives)
        ),
        "branch_supported_positive_alert_count": len(branch_positives),
        "branch_supported_positive_recall": ratio(
            len(branch_positives), len(positives)
        ),
        "union_supported_negative_alert_count": len(union_negatives),
        "union_supported_negative_alert_rate": ratio(
            len(union_negatives), len(negatives)
        ),
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
    relevant = [row for row in rows if row["class"] in classes]
    by_group: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in relevant:
        by_group[row["source_group"]][row["class"]] = row
    complete: list[dict[str, Any]] = []
    incomplete: list[str] = []
    unsupported: list[str] = []
    mismatches: list[dict[str, Any]] = []
    for source_group, group_rows in sorted(by_group.items()):
        if set(group_rows) != set(classes):
            incomplete.append(source_group)
            continue
        if not all(group_rows[name]["signal_supported"] for name in classes):
            unsupported.append(source_group)
            continue
        decisions = {
            name: group_rows[name]["branch_predicted_positive"]
            for name in classes
        }
        item = {"source_group": source_group, "decisions": decisions}
        complete.append(item)
        if len(set(decisions.values())) != 1:
            mismatches.append(item)
    return {
        "corpus": corpus,
        "classes": classes,
        "complete_supported_group_count": len(complete),
        "incomplete_group_count": len(incomplete),
        "incomplete_source_groups": incomplete,
        "complete_but_unsupported_group_count": len(unsupported),
        "complete_but_unsupported_source_groups": unsupported,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "passed": not mismatches,
    }


def main() -> int:
    paths = {
        "rule_lock": LOCK,
        "first_harness_amendment": AMENDMENT,
        "generic_harness_supplement": SUPPLEMENT,
        "v29_observed_evaluation": V29_OBSERVED,
        "independent_v29_evaluation": INDEPENDENT_V29,
        "evaluator": Path(__file__).resolve(),
    }
    feature_archive_members: dict[str, list[str]] = {}
    for corpus in CORPORA.values():
        for probe in corpus["probes"]:
            paths[f"probe_{probe.stem}"] = probe
        for feature_file in corpus.get("feature_files", []):
            paths[f"features_{feature_file.stem}"] = feature_file
        archive = corpus.get("feature_archive")
        if archive is not None:
            archive_path = archive["path"]
            paths[f"feature_archive_{archive_path.stem}"] = archive_path
            members = feature_archive_members.setdefault(
                str(archive_path), []
            )
            members.extend(
                member
                for member in archive["members"]
                if member not in members
            )
    input_records = {
        name: {"path": str(path.resolve()), "sha256": sha256(path)}
        for name, path in paths.items()
    }
    lock = load(LOCK)
    amendment = load(AMENDMENT)
    supplement = load(SUPPLEMENT)
    observed_evaluation = load(V29_OBSERVED)
    independent_evaluation = load(INDEPENDENT_V29)

    if lock.get("candidate_id") != supplement.get("candidate_id"):
        raise ValueError("supplement candidate differs from rule lock")
    if (
        supplement.get("locked_evidence", {})
        .get("rule_lock", {})
        .get("sha256")
        != input_records["rule_lock"]["sha256"]
    ):
        raise ValueError("supplement does not bind the supplied rule lock")
    if (
        supplement.get("locked_evidence", {})
        .get("first_harness_amendment", {})
        .get("sha256")
        != input_records["first_harness_amendment"]["sha256"]
    ):
        raise ValueError("supplement does not bind the first amendment")
    generic_harness_sha = (
        supplement.get("administrative_change", {})
        .get("new_harness", {})
        .get("sha256")
    )
    supplement_runs = {
        row["manifest_sha256"]: row
        for row in supplement["remaining_runs_locked_before_measurement"]
    }

    old_evaluations: dict[Path, dict[str, dict[str, Any]]] = {}
    for path, document in [
        (V29_OBSERVED, observed_evaluation),
        (INDEPENDENT_V29, independent_evaluation),
    ]:
        rows: dict[str, dict[str, Any]] = {}
        add_unique(rows, document["case_results"], str(path))
        old_evaluations[path] = rows

    branch = lock["branch"]
    drop_threshold = float(branch["spectral_edge_drop_db_exclusive"])
    persistence_threshold = float(
        branch["spectral_edge_persistence_inclusive"]
    )
    hybrid_threshold = float(
        branch["hybrid_small_coefficient_fraction_exclusive"]
    )
    selected_bin = int(lock["probe"]["selected_zero_based_bin"])
    evaluated: list[dict[str, Any]] = []

    for corpus_name, config in CORPORA.items():
        probe_rows: dict[str, dict[str, Any]] = {}
        for probe_path in config["probes"]:
            probe_document = load(probe_path)
            if probe_document.get("case_count") != len(
                probe_document.get("results", [])
            ):
                raise ValueError(f"{probe_path}: case_count differs")
            if (
                probe_document.get("public_verdict_enabled") is not False
                or probe_document.get("release_heldout_opened") is not False
            ):
                raise ValueError(f"{probe_path}: prohibited gate state")
            manifest_sha = (
                probe_document.get("inputs", {})
                .get("manifest", {})
                .get("sha256")
            )
            if probe_path.name == "observed-musdb-mp3-history-v32.json":
                expected_harness_sha = (
                    amendment.get("amendment", {}).get(
                        "amended_harness_sha256"
                    )
                )
            else:
                expected_harness_sha = generic_harness_sha
                locked_run = supplement_runs.get(manifest_sha)
                if locked_run is None:
                    raise ValueError(
                        f"{probe_path}: manifest absent from supplement"
                    )
                selection = probe_document.get("selection", {})
                if (
                    probe_document.get("case_count")
                    != locked_run["expected_case_count"]
                    or selection.get("include_class_fullmatch_regex")
                    != locked_run["include_class_fullmatch_regex"]
                ):
                    raise ValueError(
                        f"{probe_path}: selection differs from supplement"
                    )
            if (
                probe_document.get("inputs", {})
                .get("harness", {})
                .get("sha256")
                != expected_harness_sha
            ):
                raise ValueError(f"{probe_path}: harness hash differs")
            add_unique(probe_rows, probe_document["results"], str(probe_path))
        if len(probe_rows) != config["expected_cases"]:
            raise ValueError(
                f"{corpus_name}: expected {config['expected_cases']} probe "
                f"rows, found {len(probe_rows)}"
            )

        feature_rows: dict[str, dict[str, Any]] = {}
        for feature_file in config.get("feature_files", []):
            feature_document = load(feature_file)
            add_unique(
                feature_rows,
                feature_document["results"],
                str(feature_file),
            )
        archive = config.get("feature_archive")
        if archive is not None:
            for member in archive["members"]:
                feature_document = archive_json(archive["path"], member)
                add_unique(
                    feature_rows,
                    feature_document["results"],
                    f"{archive['path']}:{member}",
                )
        old_rows = old_evaluations[config["evaluation"]]
        if set(probe_rows) - set(feature_rows):
            raise ValueError(f"{corpus_name}: probe cases lack features")
        if set(probe_rows) - set(old_rows):
            raise ValueError(f"{corpus_name}: probe cases lack v29 results")

        for case_id in sorted(probe_rows):
            probe_row = probe_rows[case_id]
            feature_row = feature_rows[case_id]
            old_row = old_rows[case_id]
            if (
                probe_row["class"] != feature_row["class"]
                or probe_row["class"] != old_row["class"]
                or probe_row["expectation"] != feature_row["expectation"]
                or probe_row["expectation"] != old_row["expectation"]
                or probe_row["source_group"] != feature_row["source_group"]
                or probe_row["source_group"] != old_row["source_group"]
            ):
                raise ValueError(f"{corpus_name}/{case_id}: metadata mismatch")
            trace = feature_row["runner"]["compression_trace"]
            hybrid_fraction = float(
                probe_row["probe"]["small_fraction_1e4_by_bin_24"][
                    selected_bin
                ]
            )
            signal_supported = bool(old_row["signal_supported"])
            edge_drop = trace["spectral_edge_drop_db"]
            edge_persistence = trace["spectral_edge_persistence"]
            edge_passed = (
                isinstance(edge_drop, (int, float))
                and isinstance(edge_persistence, (int, float))
                and float(edge_drop) > drop_threshold
                and float(edge_persistence) >= persistence_threshold
            )
            hybrid_passed = hybrid_fraction > hybrid_threshold
            branch_alert = signal_supported and edge_passed and hybrid_passed
            old_alert = signal_supported and bool(old_row["predicted_positive"])
            evaluated.append(
                {
                    "corpus": corpus_name,
                    "case_id": case_id,
                    "class": probe_row["class"],
                    "expectation": probe_row["expectation"],
                    "source_group": probe_row["source_group"],
                    "signal_supported": signal_supported,
                    "spectral_edge_drop_db": trace["spectral_edge_drop_db"],
                    "spectral_edge_persistence": trace[
                        "spectral_edge_persistence"
                    ],
                    "hybrid_small_fraction": hybrid_fraction,
                    "edge_passed": edge_passed,
                    "hybrid_passed": hybrid_passed,
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
        name: {
            "supported_negative_alert_count": sum(
                row["signal_supported"]
                and row["expectation"] == "controlled_negative"
                and row["branch_predicted_positive"]
                for row in rows
            ),
            "passed": not any(
                row["signal_supported"]
                and row["expectation"] == "controlled_negative"
                and row["branch_predicted_positive"]
                for row in rows
            ),
        }
        for name, rows in sorted(by_corpus.items())
    }
    safety_passed = not negative_alerts and all(
        result["passed"] for result in corpus_safety.values()
    )

    independent_demand = [
        row
        for row in by_corpus["independent_demand_maestro"]
        if row["source_group"].startswith("independent-demand-")
        and row["signal_supported"]
    ]
    independent_recall = {}
    recall_passed = True
    for class_name, minimum in [
        ("independent_mp3_128_to_flac16", 0.75),
        ("independent_aac_at_128_to_flac16", 0.75),
    ]:
        rows = [
            row for row in independent_demand if row["class"] == class_name
        ]
        observed = ratio(
            sum(row["branch_predicted_positive"] for row in rows), len(rows)
        )
        passed = observed is not None and observed >= minimum
        recall_passed = recall_passed and passed
        independent_recall[class_name] = {
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
    broad_passed = safety_passed and recall_passed and invariance_passed
    unsupported_counts = Counter(
        (row["corpus"], row["class"])
        for row in evaluated
        if not row["signal_supported"]
    )

    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": (
            "v32_broad_observed_screen_passed_candidate_freeze_allowed"
            if broad_passed
            else "locked_v32_branch_rejected_by_broad_observed_screen"
        ),
        "candidate_id": lock["candidate_id"],
        "candidate_frozen": False,
        "new_external_transfer_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "warning": (
            "Consumed development evidence only. A pass authorizes candidate "
            "freeze preparation, not a public verdict or release-heldout access."
        ),
        "inputs": input_records,
        "feature_archive_members": feature_archive_members,
        "locked_rule": {
            "spectral_edge_drop_db_exclusive": drop_threshold,
            "spectral_edge_persistence_inclusive": persistence_threshold,
            "selected_zero_based_bin": selected_bin,
            "hybrid_small_coefficient_fraction_exclusive": hybrid_threshold,
        },
        "inventory": {
            "case_count": len(evaluated),
            "corpus_case_counts": {
                name: len(rows) for name, rows in sorted(by_corpus.items())
            },
            "source_group_count": len(
                {(row["corpus"], row["source_group"]) for row in evaluated}
            ),
            "unsupported_by_corpus_and_class": {
                f"{corpus}/{class_name}": count
                for (corpus, class_name), count in sorted(
                    unsupported_counts.items()
                )
            },
        },
        "metrics": {
            "pooled": metrics(evaluated),
            "by_corpus": {
                name: metrics(rows)
                for name, rows in sorted(by_corpus.items())
            },
            "by_class": {
                name: metrics(rows)
                for name, rows in sorted(by_class.items())
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
            "independent_demand_recall": {
                "classes": independent_recall,
                "passed": recall_passed,
            },
            "aac_invariance": {
                "groups": invariance_results,
                "passed": invariance_passed,
            },
            "passed": broad_passed,
            "next_required_action": (
                "Prepare and freeze a product-integrated successor, then acquire "
                "one compact untouched independent development gate."
                if broad_passed
                else "Reject v32 unchanged. Do not tune against broad-screen cases."
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
    return 0 if broad_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
