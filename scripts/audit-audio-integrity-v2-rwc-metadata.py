#!/usr/bin/env python3
"""Audit RWC metadata artist families without opening benchmark audio or scores."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import itertools
import json
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any


REPORT_SCHEMA_VERSION = 1
SOURCE_ID = "rwc_music_v2_2026"
REQUIRED_COLUMNS = {
    "RWCID",
    "CollID",
    "PieceNo",
    "Title",
    "Artist",
}
OVERLAP_STOP_WORDS = {
    "and",
    "band",
    "feat",
    "project",
    "quartet",
    "the",
    "trio",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: top-level JSON must be an object")
    return value


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def load_metadata(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter=";")
        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError("RWC metadata lacks required columns")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("RWC metadata contains malformed delimited rows")
    if len({row["RWCID"] for row in rows}) != len(rows):
        raise ValueError("RWCID values must be unique")
    if any(not row["Artist"].strip() for row in rows):
        raise ValueError("every RWC row must have a nonempty artist label")
    return rows


def normalized_tokens(label: str) -> set[str]:
    ascii_label = (
        unicodedata.normalize("NFKD", label)
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
    )
    return {
        token
        for token in re.findall(r"[a-z]+", ascii_label)
        if len(token) > 1 and token not in OVERLAP_STOP_WORDS
    }


def normalized_work_title(title: str) -> str:
    without_trailing_arrangement = re.sub(r"\s*\([^)]*\)\s*$", "", title)
    ascii_title = (
        unicodedata.normalize("NFKD", without_trailing_arrangement)
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
    )
    return " ".join(re.findall(r"[a-z0-9]+", ascii_title))


class DisjointSets:
    def __init__(self, values: set[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def pair_key(labels: Any) -> tuple[str, str]:
    if (
        not isinstance(labels, list)
        or len(labels) != 2
        or not all(isinstance(label, str) and label for label in labels)
    ):
        raise ValueError("reviewed artist-label pair must contain two labels")
    return tuple(sorted(labels))  # type: ignore[return-value]


def audit(metadata_path: Path, rules_path: Path, metadata_revision: str) -> dict[str, Any]:
    rules = load_object(rules_path)
    metadata_sha256 = sha256_file(metadata_path)
    if rules.get("schema_version") != 1:
        raise ValueError("unsupported RWC family-rule schema")
    if rules.get("state") != "source_identity_rules_not_allocation":
        raise ValueError("RWC family rules must remain pre-allocation")
    if rules.get("source_id") != SOURCE_ID:
        raise ValueError("RWC family-rule source differs")
    if rules.get("metadata_revision") != metadata_revision:
        raise ValueError("RWC metadata revision differs from family rules")
    if rules.get("metadata_sha256") != metadata_sha256:
        raise ValueError("RWC metadata hash differs from family rules")
    for field in ("audio_generated", "scores_opened", "selection_authorized"):
        if rules.get(field) is not False:
            raise ValueError(f"RWC family-rule {field} must be false")

    rows = load_metadata(metadata_path)
    exact_labels = {row["Artist"].strip() for row in rows}
    exclusions = rules.get("eligibility_exclusions")
    if not isinstance(exclusions, list) or not exclusions:
        raise ValueError("RWC family rules require eligibility exclusions")
    excluded_ids: set[str] = set()
    exclusion_counts: dict[str, int] = {}
    for exclusion in exclusions:
        if not isinstance(exclusion, dict):
            raise ValueError("RWC exclusion must be an object")
        collection = exclusion.get("collection_id")
        minimum = exclusion.get("piece_number_minimum")
        maximum = exclusion.get("piece_number_maximum")
        rule_id = exclusion.get("rule_id")
        if (
            not isinstance(collection, str)
            or not isinstance(minimum, int)
            or not isinstance(maximum, int)
            or minimum > maximum
            or not isinstance(rule_id, str)
            or not rule_id
        ):
            raise ValueError("invalid RWC exclusion rule")
        matches = {
            row["RWCID"]
            for row in rows
            if row["CollID"] == collection
            and minimum <= int(row["PieceNo"]) <= maximum
        }
        if excluded_ids & matches:
            raise ValueError("RWC exclusion rules overlap")
        excluded_ids.update(matches)
        exclusion_counts[rule_id] = len(matches)

    eligible_rows = [row for row in rows if row["RWCID"] not in excluded_ids]
    eligible_labels = {row["Artist"].strip() for row in eligible_rows}
    families = DisjointSets(eligible_labels)
    merge_rows = rules.get("family_merges")
    if not isinstance(merge_rows, list):
        raise ValueError("RWC family_merges must be a list")
    merge_label_sets: list[set[str]] = []
    for merge in merge_rows:
        if not isinstance(merge, dict) or not isinstance(merge.get("artist_labels"), list):
            raise ValueError("invalid RWC family merge")
        labels = merge["artist_labels"]
        if len(labels) < 2 or not all(label in eligible_labels for label in labels):
            raise ValueError("RWC family merge refers to absent or insufficient labels")
        merge_label_sets.append(set(labels))
        for label in labels[1:]:
            families.union(labels[0], label)

    overlap_pairs = {
        tuple(sorted((left, right)))
        for left, right in itertools.combinations(sorted(eligible_labels), 2)
        if normalized_tokens(left) & normalized_tokens(right)
    }
    reviewed_rows = rules.get("reviewed_label_overlap_pairs")
    if not isinstance(reviewed_rows, list):
        raise ValueError("RWC reviewed overlap pairs must be a list")
    reviewed: dict[tuple[str, str], str] = {}
    for row in reviewed_rows:
        if not isinstance(row, dict):
            raise ValueError("RWC reviewed overlap row must be an object")
        key = pair_key(row.get("artist_labels"))
        decision = row.get("decision")
        if decision not in {"merge", "separate"} or key in reviewed:
            raise ValueError("RWC overlap review has invalid or duplicate decision")
        reviewed[key] = decision
    if set(reviewed) != overlap_pairs:
        raise ValueError("RWC overlap review queue is incomplete or stale")
    for (left, right), decision in reviewed.items():
        merged = families.find(left) == families.find(right)
        if merged != (decision == "merge"):
            raise ValueError("RWC overlap decision differs from family merges")

    family_count = len({families.find(label) for label in eligible_labels})
    work_titles = collections.Counter(
        normalized_work_title(row["Title"]) for row in eligible_rows
    )
    expected = rules.get("expected")
    observed_expected = {
        "metadata_row_count": len(rows),
        "global_exact_artist_label_count": len(exact_labels),
        "excluded_row_count": len(excluded_ids),
        "eligible_row_count": len(eligible_rows),
        "eligible_exact_artist_label_count": len(eligible_labels),
        "artist_family_count": family_count,
        "reviewed_overlap_pair_count": len(reviewed),
    }
    if expected != observed_expected:
        raise ValueError("RWC observed counts differ from family-rule expectations")

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "state": "source_metadata_identity_evidence_only",
        "source_id": SOURCE_ID,
        "audio_acquired": False,
        "benchmark_audio_generated": False,
        "scores_opened": False,
        "selection_authorized": False,
        "paths_redacted": True,
        "metadata_binding": {
            "revision": metadata_revision,
            "sha256": metadata_sha256,
        },
        "observed": {
            **observed_expected,
            "collection_row_counts_before_exclusion": dict(
                sorted(collections.Counter(row["CollID"] for row in rows).items())
            ),
            "collection_row_counts_after_exclusion": dict(
                sorted(
                    collections.Counter(row["CollID"] for row in eligible_rows).items()
                )
            ),
            "collection_exact_artist_label_counts_after_exclusion": {
                collection: len(
                    {
                        row["Artist"].strip()
                        for row in eligible_rows
                        if row["CollID"] == collection
                    }
                )
                for collection in sorted({row["CollID"] for row in eligible_rows})
            },
            "exact_artist_labels_spanning_collections": sum(
                len(
                    {
                        row["CollID"]
                        for row in eligible_rows
                        if row["Artist"].strip() == label
                    }
                )
                > 1
                for label in eligible_labels
            ),
            "exclusion_rule_counts": dict(sorted(exclusion_counts.items())),
            "family_merge_count": len(merge_rows),
            "reviewed_overlap_decision_counts": dict(
                sorted(collections.Counter(reviewed.values()).items())
            ),
            "normalized_work_title_count": len(work_titles),
            "duplicate_normalized_work_title_group_count": sum(
                count > 1 for count in work_titles.values()
            ),
            "duplicate_normalized_work_title_excess_rows": sum(
                count - 1 for count in work_titles.values() if count > 1
            ),
        },
        "conservative_group_boundary": {
            "grouping_unit": "artist family after declared merges",
            "eligible_group_count": family_count,
            "known_instrumentation_variation_rows_excluded": len(excluded_ids),
            "future_selection_constraints_bound_in_rules": True,
            "independence_limit": (
                "Artist families do not establish independent recording sessions or "
                "disjoint backing personnel; retain RWC as one provider stratum."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-csv", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--metadata-revision", required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(args.metadata_csv, args.rules, args.metadata_revision)
    if args.output:
        write_json_atomic(args.output, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
