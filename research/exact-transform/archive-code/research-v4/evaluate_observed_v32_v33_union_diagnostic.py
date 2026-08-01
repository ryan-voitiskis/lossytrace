#!/usr/bin/env python3
"""Reproduce the rejected v32/v33 diagnostic union without selecting a v34 rule."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
V32 = ROOT / "observed-exact-mp3-hybrid-v32-broad-evaluation.json"
V33 = ROOT / "observed-exact-mp3-tail-flatness-v33-evaluation.json"
OUTPUT = ROOT / "observed-v32-v33-union-diagnostic.json"

INVARIANCE = [
    (
        "musdb18hq",
        [
            "musdb_aac_lc_128_to_flac16",
            "musdb_aac_lc_128_gain_minus3db_to_flac16",
            "musdb_aac_lc_128_to_aiff24",
            "musdb_aac_lc_128_to_wav16",
            "musdb_aac_lc_128_trim_137_to_flac16",
        ],
    ),
    (
        "independent_demand_maestro",
        [
            "independent_aac_lc_128_to_flac16",
            "independent_aac_lc_128_gain_minus3db_to_flac16",
            "independent_aac_lc_128_to_aiff24",
            "independent_aac_lc_128_to_wav16",
            "independent_aac_lc_128_trim_137_to_flac16",
        ],
    ),
    (
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def by_case(document: dict, label: str) -> dict[str, dict]:
    result = {}
    for row in document["case_results"]:
        case_id = row["case_id"]
        if case_id in result:
            raise ValueError(f"{label} duplicates {case_id}")
        result[case_id] = row
    return result


def main() -> int:
    v32_document = load(V32)
    v33_document = load(V33)
    v32 = by_case(v32_document, "v32")
    v33 = by_case(v33_document, "v33")
    if (
        set(v32) != set(v33)
        or len(v32) != 3840
        or v32_document.get("public_verdict_enabled") is not False
        or v33_document.get("public_verdict_enabled") is not False
        or v32_document.get("release_heldout_opened") is not False
        or v33_document.get("release_heldout_opened") is not False
    ):
        raise ValueError("v32/v33 diagnostic input contract differs")

    def decision(case_id: str) -> bool:
        return bool(
            v32[case_id]["branch_predicted_positive"]
            or v33[case_id]["branch_predicted_positive"]
        )

    negative_alerts = [
        row["case_id"]
        for row in v33.values()
        if row["signal_supported"]
        and row["expectation"] == "controlled_negative"
        and decision(row["case_id"])
    ]
    recall = {}
    for class_name, prefix, minimum in [
        ("musdb_mp3_128_to_flac16", None, 0.9),
        ("musdb_aac_at_128_to_flac16", None, 0.9),
        ("independent_mp3_128_to_flac16", "independent-demand-", 0.75),
        ("independent_aac_at_128_to_flac16", "independent-demand-", 0.75),
    ]:
        rows = [
            row
            for row in v33.values()
            if row["class"] == class_name
            and row["signal_supported"]
            and (
                prefix is None or row["source_group"].startswith(prefix)
            )
        ]
        alerts = sum(decision(row["case_id"]) for row in rows)
        observed = alerts / len(rows)
        recall[class_name] = {
            "supported_case_count": len(rows),
            "alert_count": alerts,
            "minimum": minimum,
            "observed": observed,
            "passed": observed >= minimum,
        }

    invariance = []
    for corpus, classes in INVARIANCE:
        groups: dict[str, dict[str, dict]] = defaultdict(dict)
        for row in v33.values():
            if row["corpus"] == corpus and row["class"] in classes:
                groups[row["source_group"]][row["class"]] = row
        complete = 0
        mismatches = []
        for source_group, rows in sorted(groups.items()):
            if set(rows) != set(classes):
                continue
            if not all(rows[name]["signal_supported"] for name in classes):
                continue
            complete += 1
            decisions = {
                name: decision(rows[name]["case_id"]) for name in classes
            }
            if len(set(decisions.values())) != 1:
                mismatches.append(
                    {"source_group": source_group, "decisions": decisions}
                )
        invariance.append(
            {
                "corpus": corpus,
                "complete_supported_group_count": complete,
                "mismatch_count": len(mismatches),
                "mismatches": mismatches,
                "passed": not mismatches,
            }
        )

    safety_passed = not negative_alerts
    recall_passed = all(result["passed"] for result in recall.values())
    invariance_passed = all(result["passed"] for result in invariance)
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": "diagnostic_v32_v33_union_rejected_no_v34_selected",
        "candidate_id": None,
        "candidate_frozen": False,
        "new_external_transfer_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "warning": (
            "Post hoc consumed-development diagnostic only. This union was "
            "not frozen and is explicitly rejected rather than promoted."
        ),
        "inputs": {
            "v32_evaluation": {"path": str(V32), "sha256": sha256(V32)},
            "v33_evaluation": {"path": str(V33), "sha256": sha256(V33)},
            "evaluator": {
                "path": str(Path(__file__).resolve()),
                "sha256": sha256(Path(__file__).resolve()),
            },
        },
        "inventory": {"case_count": len(v33)},
        "diagnostic": {
            "safety": {
                "supported_negative_alert_count": len(negative_alerts),
                "case_ids": negative_alerts,
                "passed": safety_passed,
            },
            "recall": {"classes": recall, "passed": recall_passed},
            "aac_invariance": {
                "groups": invariance,
                "passed": invariance_passed,
            },
            "passed": safety_passed and recall_passed and invariance_passed,
        },
        "decision": (
            "Stop the hand-built candidate sequence. Do not create v34 by "
            "tuning v32/v33 against consumed cases."
        ),
        "allowed_reuse": (
            "Retain the exact probe and v32/v33 features as development "
            "diagnostics; do not enable a public likely-lossy-derived verdict."
        ),
    }
    OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["diagnostic"], indent=2, sort_keys=True))
    print(f"wrote {OUTPUT}")
    return 0 if report["diagnostic"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
