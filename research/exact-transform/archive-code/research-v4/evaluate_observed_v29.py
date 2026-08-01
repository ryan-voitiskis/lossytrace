#!/usr/bin/env python3
"""Evaluate the v29 development policy on consumed evidence only."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import statistics
import subprocess
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path


EXPECTED_OLD_CASES = 1_634
EXPECTED_OLD_NEGATIVES = 390
EXPECTED_OLD_SUPPORTED_NEGATIVES = 196
EXPECTED_MUSDB_CASES = 1_770
EXPECTED_MUSDB_NEGATIVES = 600
EXPECTED_MUSDB_SUPPORTED_NEGATIVES = 600
PRIOR_EVALUATION_MEMBER = (
    "research/discovery/"
    "sqam-candidate-v2-external-transfer-evaluation.json"
)
SCOPED_CLASSES = {
    "musdb_aac_at_128_to_flac16",
    "musdb_aac_lc_128_to_flac16",
    "musdb_mp3_128_to_flac16",
    "musdb_vorbis_native_q3_to_flac16",
    "public_aac_lc_128_to_flac16",
    "public_mp3_128_to_flac16",
    "public_vorbis_native_q3_to_flac16",
    "sqam_aac_lc_128_to_flac16",
    "sqam_aac_lc_96_to_flac16",
    "sqam_mp3_128_to_flac16",
    "sqam_vorbis_native_q3_to_flac16",
}
PUBLIC_PCM_PAIR_CLASSES = {
    "public_pcm_excerpt_flac16",
    "public_pcm_resample_48000_flac16",
}
SQAM_AAC_INVARIANT_CLASSES = {
    "sqam_aac_lc_128_gain_minus3db_to_flac16",
    "sqam_aac_lc_128_resample_44100_to_flac16",
    "sqam_aac_lc_128_to_aiff24",
    "sqam_aac_lc_128_to_flac16",
    "sqam_aac_lc_128_to_wav16",
    "sqam_aac_lc_128_trim_137_to_flac16",
}
MUSDB_AAC_INVARIANT_CLASSES = {
    "musdb_aac_lc_128_gain_minus3db_to_flac16",
    "musdb_aac_lc_128_to_aiff24",
    "musdb_aac_lc_128_to_flac16",
    "musdb_aac_lc_128_to_wav16",
    "musdb_aac_lc_128_trim_137_to_flac16",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--research-v3", type=Path, required=True)
    parser.add_argument("--predecessor-archive", type=Path, required=True)
    parser.add_argument(
        "--v29-transform-report",
        type=Path,
        action="append",
        default=[],
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    return value


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(
        "audio_integrity_verified_mp3_v29_policy",
        path,
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import policy: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def archive_json(archive: Path, member: str) -> dict:
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
    decompressor_status = decompressor.wait()
    if decompressor_status or extracted.returncode:
        raise SystemExit(
            f"read archive member failed: {extracted.stderr.decode().strip()}"
        )
    value = json.loads(extracted.stdout)
    if not isinstance(value, dict):
        raise SystemExit(f"{member}: expected JSON object")
    return value


def low_map(path: Path) -> dict[str, dict]:
    return {
        row["case_id"]: row["features"]
        for row in load_json(path)["cases"]
    }


def feature_rows(path: Path) -> list[dict]:
    rows = load_json(path).get("results")
    if not isinstance(rows, list):
        raise SystemExit(f"{path}: feature results missing")
    return rows


def add_with_low(
    *,
    state: dict[str, dict],
    evidence: str,
    feature_path: Path,
    low_path: Path,
    policy,
) -> None:
    low = low_map(low_path)
    for row in feature_rows(feature_path):
        case_id = row["case_id"]
        if case_id in state:
            raise SystemExit(f"duplicate feature state: {case_id}")
        support = policy.support(row["runner"], low[case_id])
        state[case_id] = {
            "case_id": case_id,
            "class": row["class"],
            "expectation": row["expectation"],
            "source_group": row["source_group"],
            "evidence": evidence,
            "signal_supported": support["signal_supported"],
            "support_failures": support["failures"],
            "feature_runner": row["runner"],
        }


def add_with_prior(
    *,
    state: dict[str, dict],
    evidence: str,
    feature_path: Path,
    prior: dict[str, dict],
    policy,
) -> None:
    for row in feature_rows(feature_path):
        case_id = row["case_id"]
        if case_id in state:
            raise SystemExit(f"duplicate feature state: {case_id}")
        prior_row = prior[case_id]
        runner = row["runner"]
        compression = runner["compression_trace"]
        active_frames = int(compression["active_frame_count"])
        high_frames = int(compression["high_band_supported_frame_count"])
        high_ratio = high_frames / active_frames if active_frames else 0.0
        raw_active_bins = compression.get("median_active_bin_fraction")
        source_rate = int(runner["source_facts"]["sample_rate_hz"])
        normalized_active_bins = (
            float(raw_active_bins)
            * source_rate
            / policy.ACTIVE_BIN_REFERENCE_SAMPLE_RATE_HZ
            if raw_active_bins is not None
            else None
        )
        failures = []
        if (
            normalized_active_bins is None
            or normalized_active_bins
            < policy.MINIMUM_ACTIVE_BIN_FRACTION
        ):
            failures.append("insufficient_active_bin_fraction")
        if high_frames < policy.MINIMUM_HIGH_BAND_FRAMES:
            failures.append("insufficient_high_band_frames")
        if high_ratio < policy.MINIMUM_HIGH_BAND_FRAME_RATIO:
            failures.append(
                "insufficient_high_band_supported_frame_ratio"
            )
        failures.extend(prior_row.get("low_bandwidth_reasons", []))
        state[case_id] = {
            "case_id": case_id,
            "class": row["class"],
            "expectation": row["expectation"],
            "source_group": row["source_group"],
            "evidence": evidence,
            "signal_supported": not failures,
            "support_failures": failures,
            "feature_runner": runner,
        }


def assess(row: dict, transform: dict, policy) -> dict:
    if not row["signal_supported"]:
        return {
            "predicted_positive": False,
            "branches": [],
            "reason_families": [],
            "verification_phase_distance_samples": None,
            "verification_peak_z_median": None,
        }
    compression = row["feature_runner"]["compression_trace"]
    edge_drop = compression.get("spectral_edge_drop_db")
    edge_persistence = compression.get("spectral_edge_persistence")
    if (
        edge_drop is None
        or edge_persistence is None
        or edge_drop <= policy.EDGE_DROP_THRESHOLD_DB
        or edge_persistence < policy.EDGE_PERSISTENCE_THRESHOLD
    ):
        return {
            "predicted_positive": False,
            "branches": [],
            "reason_families": [],
            "verification_phase_distance_samples": None,
            "verification_peak_z_median": None,
        }

    profiles = transform["runner"]["transform_grid_probe"]
    mp3 = profiles.get("mp3_long_sine")
    vorbis = profiles.get("long_vorbis")
    verification = (
        mp3.get("multi_candidate_phase_verification")
        if isinstance(mp3, dict)
        else None
    )
    if (
        transform["runner"].get("research_transform_grid_profile")
        != policy.PROFILE
        or not isinstance(mp3, dict)
        or not isinstance(vorbis, dict)
        or profiles.get("opus_long_celt") is not None
        or profiles.get("opus_short_celt") is not None
    ):
        raise SystemExit(f"{row['case_id']}: v29 transform contract differs")
    if isinstance(verification, dict) and (
        int(verification["audio_block_count"])
        < policy.MP3_VERIFICATION_MINIMUM_AUDIO_BLOCK_COUNT
        or int(verification["audio_block_count"])
        > policy.MP3_VERIFICATION_MAXIMUM_AUDIO_BLOCK_COUNT
        or int(verification["frames_per_phase"])
        != policy.MP3_VERIFICATION_FRAMES_PER_PHASE
        or int(verification["control_phase_stride_samples"])
        != policy.MP3_VERIFICATION_CONTROL_PHASE_STRIDE
    ):
        raise SystemExit(f"{row['case_id']}: v29 verification contract differs")
    if verification is not None and not isinstance(verification, dict):
        raise SystemExit(f"{row['case_id']}: invalid v29 verification shape")

    distance = (
        policy._circular_distance(
            int(verification["discovery_aggregate_phase_samples"]),
            int(verification["verified_phase_samples"]),
            int(mp3["block_samples"]),
        )
        if isinstance(verification, dict)
        else None
    )
    branches = []
    if (
        isinstance(verification, dict)
        and float(verification["peak_z_median"])
        > policy.MP3_VERIFICATION_MEDIAN_THRESHOLD
        and distance is not None
        and distance <= int(verification["candidate_radius_samples"])
    ):
        branches.append("mp3_verified")
    if (
        float(vorbis["long_block_phase_aggregate_peak_z"])
        > policy.VORBIS_AGGREGATE_THRESHOLD
    ):
        branches.append("vorbis_aggregate")
    if (
        float(mp3["long_block_phase_peak_z_median"])
        - float(vorbis["long_block_phase_peak_z_median"])
        < policy.RELATIVE_MEDIAN_THRESHOLD
    ):
        branches.append("relative_median")
    return {
        "predicted_positive": bool(branches),
        "branches": branches,
        "reason_families": (
            [
                "persistent_spectral_edge",
                "transform_frame_periodicity",
            ]
            if branches
            else []
        ),
        "verification_phase_distance_samples": distance,
        "verification_peak_z_median": (
            float(verification["peak_z_median"])
            if isinstance(verification, dict)
            else None
        ),
    }


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
        row for row in supported_positives if row["predicted_positive"]
    ]
    false_positives = [
        row for row in supported_negatives if row["predicted_positive"]
    ]
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
        "positive_coverage": (
            len(supported_positives) / len(positives) if positives else None
        ),
        "supported_recall": (
            len(true_positives) / len(supported_positives)
            if supported_positives
            else None
        ),
        "supported_false_positive_rate": (
            len(false_positives) / len(supported_negatives)
            if supported_negatives
            else None
        ),
        "supported_false_positive_rate_wilson_95": wilson_interval(
            len(false_positives),
            len(supported_negatives),
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


def invariant_audit(rows: list[dict], classes: set[str]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["class"] in classes:
            grouped[row["source_group"]].append(row)
    mismatches = []
    for source_group, group in sorted(grouped.items()):
        if {row["class"] for row in group} != classes:
            continue
        states = {
            (row["signal_supported"], row["predicted_positive"])
            for row in group
        }
        if len(states) != 1:
            mismatches.append(
                {
                    "source_group": source_group,
                    "states": [
                        {
                            "case_id": row["case_id"],
                            "signal_supported": row["signal_supported"],
                            "predicted_positive": row[
                                "predicted_positive"
                            ],
                        }
                        for row in sorted(
                            group,
                            key=lambda value: value["case_id"],
                        )
                    ],
                }
            )
    complete_groups = [
        group
        for group in grouped.values()
        if {row["class"] for row in group} == classes
    ]
    return {
        "complete_source_group_count": len(complete_groups),
        "mismatch_source_group_count": len(mismatches),
        "mismatches": mismatches,
    }


def main() -> int:
    args = parse_args()
    if not args.v29_transform_report:
        raise SystemExit("at least one --v29-transform-report is required")
    policy_path = args.policy.expanduser().resolve()
    research = args.research_v3.expanduser().resolve()
    archive = args.predecessor_archive.expanduser().resolve()
    output = args.output.expanduser().resolve()
    policy = load_module(policy_path)

    prior_report = archive_json(archive, PRIOR_EVALUATION_MEMBER)
    prior = {
        row["case_id"]: row for row in prior_report["case_results"]
    }
    discovery = research / "discovery"
    state: dict[str, dict] = {}
    add_with_low(
        state=state,
        evidence="public_development",
        feature_path=discovery
        / "public-controlled-transcodes-features-v17.json",
        low_path=discovery
        / "public-controlled-transcodes-low-bandwidth.json",
        policy=policy,
    )
    add_with_low(
        state=state,
        evidence="public_negative",
        feature_path=discovery / "public-negatives-features-v17.json",
        low_path=discovery / "public-negatives-low-bandwidth.json",
        policy=policy,
    )
    add_with_low(
        state=state,
        evidence="nsynth_robustness",
        feature_path=discovery / "nsynth-features-v17.json",
        low_path=discovery / "nsynth-low-bandwidth.json",
        policy=policy,
    )
    add_with_prior(
        state=state,
        evidence="sqam_aac_observed",
        feature_path=discovery
        / "sqam-observed-aac-positives-features-v17.json",
        prior=prior,
        policy=policy,
    )
    add_with_prior(
        state=state,
        evidence="sqam_pcm_observed",
        feature_path=discovery
        / "sqam-observed-pcm-negatives-features-v17-corrected.json",
        prior=prior,
        policy=policy,
    )
    add_with_low(
        state=state,
        evidence="sqam_future_observed",
        feature_path=discovery
        / "sqam-future-observed-features-v17-corrected.json",
        low_path=discovery
        / "sqam-future-observed-low-bandwidth.json",
        policy=policy,
    )
    old_inventory = {
        row["case_id"]
        for row in load_json(
            discovery
            / "observed-retained-plus-sqam-future-transform-only-v28.json"
        )["results"]
    }
    if (
        set(state) != old_inventory
        or len(state) != EXPECTED_OLD_CASES
        or sum(
            row["expectation"] == "negative"
            for row in state.values()
        )
        != EXPECTED_OLD_NEGATIVES
        or sum(
            row["expectation"] == "negative"
            and row["signal_supported"]
            for row in state.values()
        )
        != EXPECTED_OLD_SUPPORTED_NEGATIVES
    ):
        raise SystemExit("old observed support inventory differs")

    musdb_measurement = load_json(
        research
        / "external-transfer"
        / "musdb18hq-frozen-measurement-v28.json"
    )
    musdb_evaluation = {
        row["case_id"]: row
        for row in load_json(
            research
            / "external-transfer"
            / "musdb18hq-external-evaluation-v28.json"
        )["case_results"]
    }
    for row in musdb_measurement["results"]:
        evaluation = musdb_evaluation[row["case_id"]]
        if row["case_id"] in state:
            raise SystemExit(f"duplicate MUSDB case: {row['case_id']}")
        state[row["case_id"]] = {
            "case_id": row["case_id"],
            "class": row["class"],
            "expectation": row["expectation"],
            "source_group": row["source_group"],
            "evidence": "musdb_consumed_external_transfer",
            "signal_supported": evaluation["signal_supported"],
            "support_failures": evaluation["failures"],
            "feature_runner": row["runner"],
        }
    musdb_rows = [
        row
        for row in state.values()
        if row["evidence"] == "musdb_consumed_external_transfer"
    ]
    if (
        len(musdb_rows) != EXPECTED_MUSDB_CASES
        or sum(
            row["expectation"] == "negative" for row in musdb_rows
        )
        != EXPECTED_MUSDB_NEGATIVES
        or sum(
            row["expectation"] == "negative"
            and row["signal_supported"]
            for row in musdb_rows
        )
        != EXPECTED_MUSDB_SUPPORTED_NEGATIVES
    ):
        raise SystemExit("MUSDB observed support inventory differs")

    transform: dict[str, dict] = {}
    transform_inputs = []
    runner_hashes = set()
    for value in args.v29_transform_report:
        path = value.expanduser().resolve()
        report = load_json(path)
        if (
            report.get("state")
            != "observed_development_research_measurement"
            or report.get("candidate_frozen") is not False
            or report.get("new_external_transfer_opened") is not False
            or report.get("release_heldout_opened") is not False
            or report.get("public_verdict_enabled") is not False
            or report.get("profile") != policy.PROFILE
        ):
            raise SystemExit(f"{path}: transform report contract differs")
        runner_hashes.add(report["runner"]["sha256"])
        for row in report["results"]:
            existing = transform.get(row["case_id"])
            if existing is not None:
                if (
                    existing["audio_sha256"] != row["audio_sha256"]
                    or existing["runner"]["transform_grid_probe"]
                    != row["runner"]["transform_grid_probe"]
                ):
                    raise SystemExit(
                        f"{row['case_id']}: duplicate transform differs"
                    )
                continue
            transform[row["case_id"]] = row
        transform_inputs.append(
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "case_count": report["case_count"],
                "runner": report["runner"],
                "harness": report["harness"],
            }
        )
    if len(runner_hashes) != 1 or not set(state) <= set(transform):
        raise SystemExit("v29 transform inventory differs")

    rows = []
    for case_id in sorted(state):
        source = state[case_id]
        result = assess(source, transform[case_id], policy)
        rows.append(
            {
                "case_id": case_id,
                "class": source["class"],
                "expectation": source["expectation"],
                "source_group": source["source_group"],
                "evidence": source["evidence"],
                "signal_supported": source["signal_supported"],
                "support_failures": source["support_failures"],
                **result,
            }
        )

    overall = metrics(rows)
    by_class = grouped_metrics(rows, "class")
    scoped = {
        class_name: {
            "supported_positive_count": by_class[class_name][
                "supported_positive_count"
            ],
            "true_positive_count": by_class[class_name][
                "true_positive_count"
            ],
            "supported_recall": by_class[class_name][
                "supported_recall"
            ],
            "passed": (
                by_class[class_name]["supported_recall"] is not None
                and by_class[class_name]["supported_recall"] >= 0.90
            ),
        }
        for class_name in sorted(SCOPED_CLASSES)
    }
    supported_negative_verification = [
        row["verification_peak_z_median"]
        for row in rows
        if row["expectation"] == "negative"
        and row["signal_supported"]
        and row["verification_peak_z_median"] is not None
    ]
    phase_matched_supported_negative_verification = [
        row["verification_peak_z_median"]
        for row in rows
        if row["expectation"] == "negative"
        and row["signal_supported"]
        and row["verification_peak_z_median"] is not None
        and row["verification_phase_distance_samples"] <= 2
    ]
    invariant = {
        "public_pcm_excerpt_resample": invariant_audit(
            rows,
            PUBLIC_PCM_PAIR_CLASSES,
        ),
        "sqam_aac_128_wrappers_gain_trim_resample": invariant_audit(
            rows,
            SQAM_AAC_INVARIANT_CLASSES,
        ),
        "musdb_aac_128_wrappers_gain_trim": invariant_audit(
            rows,
            MUSDB_AAC_INVARIANT_CLASSES,
        ),
    }
    development_screen_passed = bool(
        overall["false_positive_count"] == 0
        and all(item["passed"] for item in scoped.values())
        and all(
            item["mismatch_source_group_count"] == 0
            for item in invariant.values()
        )
        and all(
            set(row["reason_families"])
            == {
                "persistent_spectral_edge",
                "transform_frame_periodicity",
            }
            for row in rows
            if row["predicted_positive"]
        )
    )
    timings = [
        row["runner"]["research_transform_grid_elapsed_ms"]
        for case_id, row in transform.items()
        if case_id in state
    ]
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": (
            "audio-integrity-verified-mp3-successor-"
            "research-20260731-001"
        ),
        "state": "observed_development_candidate_screen",
        "candidate_frozen": False,
        "new_external_transfer_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "evidence_warning": (
            "Every scored corpus is consumed development evidence. This "
            "screen is not an external-transfer or release gate."
        ),
        "policy": policy.contract(),
        "inputs": {
            "policy": {
                "path": str(policy_path),
                "sha256": sha256_file(policy_path),
            },
            "research_v3": str(research),
            "predecessor_archive": {
                "path": str(archive),
                "sha256": sha256_file(archive),
                "member": PRIOR_EVALUATION_MEMBER,
            },
            "v29_transform_reports": transform_inputs,
            "evaluator": {
                "path": str(Path(__file__).resolve()),
                "sha256": sha256_file(Path(__file__).resolve()),
            },
        },
        "inventory": {
            "case_count": len(rows),
            "source_group_count": len(
                {row["source_group"] for row in rows}
            ),
            "evidence_counts": dict(
                sorted(Counter(row["evidence"] for row in rows).items())
            ),
            "transform_unique_case_count": len(transform),
        },
        "observed_metrics": {
            "overall": overall,
            "by_class": by_class,
            "by_evidence": grouped_metrics(rows, "evidence"),
            "branch_fire_counts": dict(
                sorted(
                    Counter(
                        branch
                        for row in rows
                        for branch in row["branches"]
                    ).items()
                )
            ),
            "scoped_recall": scoped,
            "verification_negative_boundaries": {
                "supported_negative_count_with_score": len(
                    supported_negative_verification
                ),
                "supported_negative_peak_z_median_maximum": max(
                    supported_negative_verification
                ),
                "phase_matched_supported_negative_count": len(
                    phase_matched_supported_negative_verification
                ),
                "phase_matched_supported_negative_peak_z_median_maximum": (
                    max(phase_matched_supported_negative_verification)
                ),
                "threshold_margin_above_phase_matched_maximum": (
                    policy.MP3_VERIFICATION_MEDIAN_THRESHOLD
                    - max(
                        phase_matched_supported_negative_verification
                    )
                ),
            },
        },
        "invariance": invariant,
        "transform_only_runtime": {
            "case_count": len(timings),
            "median_ms": statistics.median(timings),
            "p95_ms": sorted(timings)[math.ceil(0.95 * len(timings)) - 1],
            "maximum_ms": max(timings),
            "warning": (
                "Transform-only timing is diagnostic. A frozen candidate "
                "still requires paired full-pipeline performance evidence."
            ),
        },
        "development_screen": {
            "passed": development_screen_passed,
            "external_transfer_gate_passed": False,
            "release_gate_passed": False,
            "next_required_action": (
                "Freeze the candidate and a new independent untouched "
                "external-transfer corpus before opening any scores."
            ),
        },
        "case_results": rows,
    }
    write_atomic(output, report)
    print(
        f"wrote {len(rows)} observed rows; "
        f"FP={overall['false_positive_count']} "
        f"screen_passed={development_screen_passed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
