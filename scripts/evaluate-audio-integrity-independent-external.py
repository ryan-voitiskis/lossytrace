#!/usr/bin/env python3
"""Evaluate the one-use frozen v29 independent external transfer."""

from __future__ import annotations

import importlib.util
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = (
    ROOT / "scripts" / "evaluate-audio-integrity-musdb18hq-external.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audio_integrity_external_evaluator_base",
    BASE_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise SystemExit(f"cannot load external evaluator base: {BASE_PATH}")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

CANDIDATE_ID = "verified-mp3-two-grid-edge-v29-independent-transfer-v1"
PROFILE = "verified-mp3-two-grid-v29"
EXPECTED_CASE_COUNT = 436
EXPECTED_SOURCE_COUNT = 36
EXPECTED_NEGATIVE_COUNT = 144
INVARIANT_SOURCE_COUNT = 10
SCOPED_CLASSES = {
    "independent_aac_at_128_to_flac16",
    "independent_aac_lc_128_to_flac16",
    "independent_mp3_128_to_flac16",
    "independent_vorbis_native_q3_to_flac16",
}
DIFFICULT_CLASSES = {
    "independent_aac_lc_192_to_flac16",
    "independent_mp3_320_to_flac16",
    "independent_opus_96_to_flac16",
}
NEGATIVE_CLASSES = {
    "independent_pcm_reference_wav16",
    "independent_pcm_sharp_lowpass_16000_flac16",
    "independent_pcm_lowpass_19000_flac16",
    "independent_pcm_resample_32000_44100_flac16",
}
AAC_INVARIANT_CLASSES = {
    "independent_aac_lc_128_to_flac16",
    "independent_aac_lc_128_gain_minus3db_to_flac16",
    "independent_aac_lc_128_trim_137_to_flac16",
    "independent_aac_lc_128_to_wav16",
    "independent_aac_lc_128_to_aiff24",
}

BASE.CANDIDATE_ID = CANDIDATE_ID
BASE.PROFILE = PROFILE
BASE.EXPECTED_CASE_COUNT = EXPECTED_CASE_COUNT
BASE.EXPECTED_SOURCE_COUNT = EXPECTED_SOURCE_COUNT
BASE.EXPECTED_NEGATIVE_COUNT = EXPECTED_NEGATIVE_COUNT
BASE.SCOPED_CLASSES = SCOPED_CLASSES
BASE.DIFFICULT_CLASSES = DIFFICULT_CLASSES
BASE.NEGATIVE_CLASSES = NEGATIVE_CLASSES
BASE.AAC_INVARIANT_CLASSES = AAC_INVARIANT_CLASSES
BASE.__file__ = str(Path(__file__).resolve())


def invariant_audit(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["class"] in AAC_INVARIANT_CLASSES:
            grouped[row["source_group"]].append(row)
    selected = {
        source_group: group
        for source_group, group in grouped.items()
        if {row["class"] for row in group} == AAC_INVARIANT_CLASSES
    }
    if len(selected) != INVARIANT_SOURCE_COUNT:
        raise SystemExit("independent invariant inventory differs")
    provider_counts = {
        "demand": sum(
            source.startswith("independent-demand-")
            for source in selected
        ),
        "maestro": sum(
            source.startswith("independent-maestro-")
            for source in selected
        ),
    }
    if provider_counts != {"demand": 5, "maestro": 5}:
        raise SystemExit("independent invariant provider balance differs")
    mismatches = []
    for source_group, group in sorted(selected.items()):
        states = {
            (
                row["signal_supported"],
                row["assessment"],
                row["predicted_positive"],
            )
            for row in group
        }
        if len(states) != 1:
            mismatches.append(
                {
                    "source_group": source_group,
                    "states": [
                        {
                            "class": row["class"],
                            "signal_supported": row["signal_supported"],
                            "assessment": row["assessment"],
                            "predicted_positive": row[
                                "predicted_positive"
                            ],
                        }
                        for row in sorted(
                            group,
                            key=lambda value: value["class"],
                        )
                    ],
                }
            )
    return {
        "source_group_count": len(selected),
        "provider_source_group_counts": provider_counts,
        "mismatch_source_group_count": len(mismatches),
        "mismatches": mismatches,
    }


def validate_frozen_inputs(
    *,
    precommit_path: Path,
    precommit: dict,
    policy_path: Path,
    measurement_path: Path,
    measurement: dict,
    support_path: Path,
    support_report: dict,
    manifest_path: Path,
    manifest: dict,
    fingerprints_path: Path,
    fingerprints: dict,
    performance_path: Path,
    performance: dict,
) -> None:
    tools = precommit.get("tools", {})
    evidence = precommit.get("evidence", {})
    corpus_plan = precommit.get("corpus_plan", {})
    plan_path = Path(corpus_plan.get("path", "")).expanduser().resolve()
    plan = BASE.load_json(plan_path)
    measurement_rows = measurement.get("results")
    support_rows = support_report.get("cases")
    expected_gate = {
        "maximum_tier_a_negative_false_positive_count": 0,
        "minimum_supported_recall_per_scoped_class": 0.9,
        "minimum_support_coverage_per_scoped_class": 0.75,
        "scoped_classes": sorted(SCOPED_CLASSES),
        "difficult_classes": sorted(DIFFICULT_CLASSES),
        "hard_negative_classes": sorted(NEGATIVE_CLASSES),
        "aac_invariant_source_group_count": INVARIANT_SOURCE_COUNT,
        "maximum_aac_invariant_mismatch_source_groups": 0,
        "required_positive_reason_families": [
            "persistent_spectral_edge",
            "transform_frame_periodicity",
        ],
        "maximum_p95_runtime_overhead_percent": 10.0,
        "minimum_independent_source_groups": EXPECTED_SOURCE_COUNT,
        "required_provider_source_groups": {
            "demand-v1.0": 18,
            "maestro-v3.0.0": 18,
        },
    }
    if (
        precommit.get("schema_version") != 1
        or precommit.get("state") != "frozen_before_external_transfer"
        or precommit.get("candidate_id") != CANDIDATE_ID
        or precommit.get("candidate_frozen") is not True
        or precommit.get("external_transfer_feature_scores_opened")
        is not False
        or precommit.get("release_heldout_opened") is not False
        or precommit.get("public_verdict_enabled") is not False
        or precommit.get("feature_version") != 0
        or precommit.get("transform_profile") != PROFILE
        or precommit.get("external_transfer_gate") != expected_gate
        or measurement.get("schema_version") != 1
        or measurement.get("state")
        != "frozen_external_transfer_measurement_complete"
        or measurement.get("candidate_id") != CANDIDATE_ID
        or measurement.get("candidate_frozen") is not True
        or measurement.get("profile") != PROFILE
        or measurement.get("public_verdict_enabled") is not False
        or support_report.get("schema_version") != 1
        or support_report.get("state")
        != "frozen_external_transfer_support_measurement"
        or support_report.get("candidate_id") != CANDIDATE_ID
        or support_report.get("candidate_frozen") is not True
        or support_report.get("method_id")
        != "low-bandwidth-support-discovery-v0"
        or support_report.get("public_verdict_enabled") is not False
        or corpus_plan.get("sha256") != BASE.sha256_file(plan_path)
        or manifest != plan.get("manifest")
        or tools.get("evaluator_sha256")
        != BASE.sha256_file(Path(__file__).resolve())
        or tools.get("base_evaluator_sha256")
        != BASE.sha256_file(BASE_PATH)
        or tools.get("policy_module_sha256")
        != BASE.sha256_file(policy_path)
        or measurement.get("candidate_precommit", {}).get("sha256")
        != BASE.sha256_file(precommit_path)
        or measurement.get("harness", {}).get("sha256")
        != tools.get("external_runner_sha256")
        or measurement.get("runner", {}).get("sha256")
        != tools.get("benchmark_runner_sha256")
        or support_report.get("candidate_precommit", {}).get("sha256")
        != BASE.sha256_file(precommit_path)
        or support_report.get("tool", {}).get("sha256")
        != tools.get("low_bandwidth_probe_sha256")
        or evidence.get("performance_report_sha256")
        != BASE.sha256_file(performance_path)
        or performance.get("commitments", {}).get("runner_sha256")
        != tools.get("benchmark_runner_sha256")
        or fingerprints.get("corpus_id") != manifest.get("corpus_id")
        or len(manifest.get("cases", [])) != EXPECTED_CASE_COUNT
        or measurement.get("case_count") != EXPECTED_CASE_COUNT
        or support_report.get("case_count") != EXPECTED_CASE_COUNT
        or not isinstance(measurement_rows, list)
        or len(measurement_rows) != EXPECTED_CASE_COUNT
        or not isinstance(support_rows, list)
        or len(support_rows) != EXPECTED_CASE_COUNT
        or measurement.get("external_transfer_feature_scores_opened")
        is not True
        or support_report.get("external_transfer_feature_scores_opened")
        is not True
        or measurement.get("opening", {}).get("state")
        != "external_transfer_feature_scores_opened"
        or measurement.get("opening", {}).get(
            "candidate_precommit_sha256"
        )
        != BASE.sha256_file(precommit_path)
        or support_report.get("opening", {}).get("state")
        != "external_transfer_feature_scores_opened"
        or support_report.get("opening", {}).get(
            "candidate_precommit_sha256"
        )
        != BASE.sha256_file(precommit_path)
        or measurement.get("release_heldout_opened") is not False
        or support_report.get("release_heldout_opened") is not False
        or BASE.sha256_file(manifest_path)
        != measurement.get("manifest", {}).get("sha256")
        or BASE.sha256_file(fingerprints_path)
        != measurement.get("fingerprints", {}).get("sha256")
        or BASE.sha256_file(manifest_path)
        != support_report.get("manifest", {}).get("sha256")
        or BASE.sha256_file(fingerprints_path)
        != support_report.get("fingerprints", {}).get("sha256")
    ):
        raise SystemExit("frozen independent evaluation contract differs")


BASE.invariant_audit = invariant_audit
BASE.validate_frozen_inputs = validate_frozen_inputs


if __name__ == "__main__":
    raise SystemExit(BASE.main())
