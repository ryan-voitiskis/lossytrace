#!/usr/bin/env python3
"""Verify the new phase-zero probe against the sealed archived v32 replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path


EXPECTED_ARCHIVE_SHA256 = "10f6eff479639844c0836c531e2e08d2a442fb167b0ccffe11580dc02a63c8db"
LOCK_MEMBER = "research-v4/observed-exact-mp3-hybrid-v32-rule-lock.json"
PILOT_MEMBER = "research-v4/observed-musdb-mp3-history-pilot24.json"
EXPECTED_SOURCE_GROUPS = 24
EXPECTED_OVERLAP_CASES = 120
FRACTION_TOLERANCE = 1.0e-12
MAGNITUDE_TOLERANCE = 1.0e-10


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


def load_archive_objects(archive: Path, members: tuple[str, ...]) -> dict[str, dict]:
    if not members or len(set(members)) != len(members):
        raise ValueError("archive members must be present and unique")
    with tempfile.TemporaryDirectory(prefix="lossytrace-replay-") as directory:
        root = Path(directory).resolve()
        completed = subprocess.run(
            ["tar", "--zstd", "-xf", str(archive), "-C", str(root), *members],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if completed.returncode:
            raise ValueError(
                "read replay records from archive: "
                f"{completed.stderr.decode(errors='replace').strip()}"
            )
        values = {}
        for member in members:
            path = root / member
            if path.is_symlink() or not path.is_file() or root not in path.resolve().parents:
                raise ValueError(f"{member}: archive member is not a safe regular file")
            values[member] = load_object(path)
        return values


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


def maximum_absolute_difference(left: list, right: list, label: str) -> float:
    if len(left) != len(right) or not left:
        raise ValueError(f"{label}: arrays differ in length or are empty")
    differences = []
    for left_value, right_value in zip(left, right, strict=True):
        if (
            not isinstance(left_value, (int, float))
            or not math.isfinite(left_value)
            or not isinstance(right_value, (int, float))
            or not math.isfinite(right_value)
        ):
            raise ValueError(f"{label}: non-finite value")
        differences.append(abs(float(left_value) - float(right_value)))
    return max(differences)


def compare(lock: dict, pilot: dict, current: dict) -> dict:
    selection = lock.get("selection_evidence")
    source_groups = selection.get("source_groups") if isinstance(selection, dict) else None
    if not isinstance(source_groups, list) or len(source_groups) != EXPECTED_SOURCE_GROUPS:
        raise ValueError("archived v32 selection contract differs")
    if pilot.get("schema_version") != 1 or pilot.get("public_verdict_enabled") is not False:
        raise ValueError("archived pilot gate state differs")
    if (
        current.get("schema_version") != 1
        or current.get("feature_version") != 0
        or current.get("public_verdict_enabled") is not False
        or current.get("future_codec_only_opened") is not False
        or current.get("release_heldout_opened") is not False
    ):
        raise ValueError("current ablation gate state differs")
    archived = {row["case_id"]: row for row in pilot.get("results", [])}
    measured = {row["case_id"]: row for row in current.get("results", [])}
    if len(archived) != len(pilot.get("results", [])) or len(measured) != len(
        current.get("results", [])
    ):
        raise ValueError("case IDs are not unique")
    overlap = sorted(archived.keys() & measured.keys())
    overlap = [
        case_id
        for case_id in overlap
        if archived[case_id].get("source_group") in source_groups
    ]
    if len(overlap) != EXPECTED_OVERLAP_CASES:
        raise ValueError(
            f"expected {EXPECTED_OVERLAP_CASES} replay cases, found {len(overlap)}"
        )
    maxima = {
        "exact_zero_fraction": 0.0,
        "exact_zero_mean_count_per_granule": 0.0,
        "mean_normalized_magnitude_by_bin_24": 0.0,
        "small_fraction_1e4_by_bin_24": 0.0,
        "small_fraction_1e3_by_bin_24": 0.0,
    }
    mismatch_count = 0
    for case_id in overlap:
        expected_row = archived[case_id]
        current_row = measured[case_id]
        if expected_row.get("audio_sha256") != current_row.get("audio_sha256"):
            raise ValueError(f"{case_id}: audio commitment differs")
        expected = expected_row.get("probe")
        actual_probe = current_row.get("probe")
        actual = actual_probe.get("replay") if isinstance(actual_probe, dict) else None
        if not isinstance(expected, dict) or not isinstance(actual, dict):
            raise ValueError(f"{case_id}: replay measurement is missing")
        case_differences = {
            "exact_zero_fraction": abs(
                float(expected["exact_zero_fraction"])
                - float(actual["exact_zero_fraction"])
            ),
            "exact_zero_mean_count_per_granule": abs(
                float(expected["exact_zero_mean_count_per_granule"])
                - float(actual["exact_zero_mean_count_per_granule"])
            ),
            "mean_normalized_magnitude_by_bin_24": maximum_absolute_difference(
                expected["mean_normalized_magnitude_by_bin_24"],
                actual["mean_normalized_magnitude_by_bin_24"],
                "mean normalized magnitude",
            ),
            "small_fraction_1e4_by_bin_24": maximum_absolute_difference(
                expected["small_fraction_1e4_by_bin_24"],
                actual["small_fraction_1e4_by_bin_24"],
                "small fraction 1e-4",
            ),
            "small_fraction_1e3_by_bin_24": maximum_absolute_difference(
                expected["small_fraction_1e3_by_bin_24"],
                actual["small_fraction_1e3_by_bin_24"],
                "small fraction 1e-3",
            ),
        }
        for field, difference in case_differences.items():
            maxima[field] = max(maxima[field], difference)
        if (
            case_differences["exact_zero_fraction"] > FRACTION_TOLERANCE
            or case_differences["exact_zero_mean_count_per_granule"]
            > FRACTION_TOLERANCE
            or case_differences["small_fraction_1e4_by_bin_24"]
            > FRACTION_TOLERANCE
            or case_differences["small_fraction_1e3_by_bin_24"]
            > FRACTION_TOLERANCE
            or case_differences["mean_normalized_magnitude_by_bin_24"]
            > MAGNITUDE_TOLERANCE
        ):
            mismatch_count += 1
    return {
        "case_count": len(overlap),
        "source_group_count": len(source_groups),
        "mismatch_case_count": mismatch_count,
        "maximum_absolute_differences": maxima,
        "fraction_tolerance": FRACTION_TOLERANCE,
        "magnitude_tolerance": MAGNITUDE_TOLERANCE,
        "passed": mismatch_count == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--ablation-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        archive = args.archive.expanduser().resolve()
        ablation = args.ablation_report.expanduser().resolve()
        archive_sha256 = sha256_file(archive)
        if archive_sha256 != EXPECTED_ARCHIVE_SHA256:
            raise ValueError("exact-transform archive hash differs")
        archived = load_archive_objects(archive, (LOCK_MEMBER, PILOT_MEMBER))
        replay = compare(
            archived[LOCK_MEMBER], archived[PILOT_MEMBER], load_object(ablation)
        )
        value = {
            "schema_version": 1,
            "state": "exact_hybrid_front_end_replay_verification",
            "feature_version": 0,
            "public_verdict_enabled": False,
            "inputs": {
                "archive_sha256": archive_sha256,
                "lock_member": LOCK_MEMBER,
                "pilot_member": PILOT_MEMBER,
                "ablation_report_sha256": sha256_file(ablation),
            },
            "replay": replay,
        }
        write_new(args.output.expanduser().resolve(), value)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(
        f"verified {replay['case_count']} replay cases; "
        f"mismatches={replay['mismatch_case_count']}"
    )
    return 0 if replay["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
