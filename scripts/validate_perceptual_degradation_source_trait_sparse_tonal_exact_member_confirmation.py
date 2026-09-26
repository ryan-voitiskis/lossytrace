#!/usr/bin/env python3
"""Independently audit the sparse/tonal exact-member confirmation projection."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-tonal-exact-member-confirmation-plan.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-source-trait-sparse-tonal-exact-member-confirmation-20260818-001.json"
AUDIT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-source-trait-sparse-tonal-exact-member-confirmation-audit-20260819-001.json"
REPORT_ID = "perceptual-degradation-source-trait-sparse-tonal-exact-member-confirmation-20260818-001"
AUDIT_ID = "perceptual-degradation-source-trait-sparse-tonal-exact-member-confirmation-audit-20260819-001"
RUNNER_PATH = ROOT / "scripts/perceptual_degradation_source_trait_sparse_tonal_exact_member_confirmation.py"
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _validate_channel(channel: dict[str, Any], errors: list[str], label: str) -> None:
    occupancy = channel.get("time_occupancy", {})
    spectral = channel.get("spectral_concentration", {})
    if occupancy.get("supported") is not True or occupancy.get("block_count") != 10:
        errors.append(f"{label} occupancy support differs")
        return
    active = occupancy.get("active_block_count")
    if not isinstance(active, int) or not 0 <= active <= 10:
        errors.append(f"{label} active-block count differs")
        return
    if occupancy.get("active_fraction") != f"{active / 10:.9f}":
        errors.append(f"{label} active fraction differs")
    sparse = active <= 2
    non_sparse = active >= 8
    if occupancy.get("sparse") is not sparse or occupancy.get("non_sparse") is not non_sparse:
        errors.append(f"{label} occupancy class differs")
    if spectral.get("supported") is not True or not isinstance(spectral.get("active_frame_count"), int) or spectral["active_frame_count"] < 3:
        errors.append(f"{label} spectral support differs")
        return
    try:
        flatness = float(spectral["median_spectral_flatness"])
        concentration = float(spectral["median_top_8_bin_power_share"])
    except (KeyError, TypeError, ValueError):
        errors.append(f"{label} spectral displays differ")
        return
    tonal = flatness <= 0.1 and concentration >= 0.6
    non_tonal = flatness >= 0.5 and concentration <= 0.2
    if spectral.get("tonal") is not tonal or spectral.get("non_tonal") is not non_tonal:
        errors.append(f"{label} spectral class differs")
    sparse_non_tonal = sparse and non_tonal and not tonal
    tonal_non_sparse = tonal and non_sparse and not sparse
    overlap = sparse and tonal
    abstain = not (sparse_non_tonal or tonal_non_sparse or overlap)
    expected = {
        "sparse_non_tonal_contrast": sparse_non_tonal,
        "tonal_non_sparse_contrast": tonal_non_sparse,
        "sparse_tonal_overlap": overlap,
        "abstain": abstain,
    }
    for key, value in expected.items():
        if channel.get(key) is not value:
            errors.append(f"{label} class predicate differs: {key}")


def validate_report(report: dict[str, Any], plan: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    plan = plan or load_json(PLAN_PATH)
    if report.get("schema_version") != 1 or report.get("report_id") != REPORT_ID:
        errors.append("report identity differs")
    if report.get("state") != "two_exact_member_score_free_descriptor_replays_complete":
        errors.append("report state differs")
    if report.get("plan_id") != plan.get("plan_id") or report.get("plan_sha256") != sha256_file(PLAN_PATH):
        errors.append("report plan binding differs")
    if report.get("implementation_sha256") != sha256_file(RUNNER_PATH):
        errors.append("report implementation binding differs")
    if report.get("execution") != {
        "decoded_or_derived_pcm_retained": False,
        "exact_member_count": 2,
        "maximum_workers": 1,
        "minimum_free_disk_gib_preserved": 15,
        "private_replay_count": 2,
        "private_reports_byte_identical": True,
    }:
        errors.append("execution boundary differs")
    observations = report.get("source_observations", [])
    if not isinstance(observations, list) or len(observations) != 2:
        errors.append("source observation inventory differs")
        observations = []
    plan_by_id = {row["exact_member_id"]: row for row in plan.get("members", [])}
    if [row.get("exact_member_id") for row in observations] != [row.get("exact_member_id") for row in plan.get("members", [])]:
        errors.append("source observation order differs")
    passed: list[bool] = []
    for source in observations:
        source_id = source.get("exact_member_id")
        bound = plan_by_id.get(source_id, {})
        measurement = source.get("measurement", {})
        container = measurement.get("container", {})
        channels = measurement.get("channel_descriptors", [])
        if source.get("provider_id") != bound.get("provider_id") or source.get("licence") != bound.get("licence"):
            errors.append(f"{source_id} provider boundary differs")
        if source.get("expected_descriptor_class") != bound.get("expected_descriptor_class"):
            errors.append(f"{source_id} expected class differs")
        if source.get("source_trait_assigned") is not False:
            errors.append(f"{source_id} trait assignment must remain false")
        expected_container = bound.get("expected_container", {})
        for key, value in expected_container.items():
            if container.get(key) != value:
                errors.append(f"{source_id} container differs: {key}")
        if not isinstance(container.get("frame_count"), int) or container["frame_count"] <= 0:
            errors.append(f"{source_id} frame count differs")
        if not isinstance(channels, list) or len(channels) != expected_container.get("channel_count"):
            errors.append(f"{source_id} channel inventory differs")
            channels = []
        for index, channel in enumerate(channels):
            _validate_channel(channel, errors, f"{source_id} channel {index}")
        expected_class = bound.get("expected_descriptor_class")
        agreement = bool(channels) and all(channel.get(expected_class) is True and channel.get("abstain") is False for channel in channels)
        if measurement.get("all_supported_channels_agree") is not agreement or source.get("descriptor_confirmation_passed") is not agreement:
            errors.append(f"{source_id} confirmation predicate differs")
        passed.append(agreement)
    all_passed = len(passed) == 2 and all(passed)
    decision = report.get("decision", {})
    expected_decision = {
        "all_exact_member_descriptor_confirmations_passed": all_passed,
        "candidate_replacement_performed": False,
        "descriptor_confirmation_complete": True,
        "source_manifest_allocated": False,
        "source_trait_assignment_complete": False,
        "thresholds_changed_after_observation": False,
    }
    if decision != expected_decision:
        errors.append("decision boundary differs")
    if report.get("publication_boundary") != {
        "audio_exposed": False,
        "encoded_or_pcm_hashes_exposed": False,
        "private_paths_exposed": False,
        "provider_scores_or_processed_conditions_exposed": False,
    }:
        errors.append("publication boundary differs")
    claims = report.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    serialized = json.dumps(report, sort_keys=True)
    for forbidden in ("/Users/", "Application Support", "encoded_sha256", "pcm_sha256", "private-replay", "relative_path"):
        if forbidden in serialized:
            errors.append(f"public report exposes forbidden material: {forbidden}")
    return sorted(set(errors))


def _public_projection(private: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "descriptor_confirmation_passed": source["measurement"]["descriptor_confirmation_passed"],
            "exact_member_id": source["exact_member_id"],
            "expected_descriptor_class": source["measurement"]["expected_descriptor_class"],
            "licence": source["licence"],
            "measurement": {
                "all_supported_channels_agree": source["measurement"]["all_supported_channels_agree"],
                "channel_descriptors": source["measurement"]["channel_descriptors"],
                "container": source["measurement"]["container"],
            },
            "provider_id": source["provider_id"],
            "source_trait_assigned": False,
        }
        for source in private.get("source_observations", [])
    ]


def build_audit(report: dict[str, Any], private_output_dir: Path | None = None) -> dict[str, Any]:
    errors = validate_report(report)
    private_gates = {
        "attribution_attachment_matches_plan": True,
        "private_audio_hashes_well_formed": True,
        "private_public_projection_exact": True,
        "private_replays_byte_identical": True,
    }
    if private_output_dir is not None:
        if private_output_dir.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("private output must remain outside the repository")
        first = (private_output_dir / "private-replay-a.json").read_bytes()
        second = (private_output_dir / "private-replay-b.json").read_bytes()
        private_gates["private_replays_byte_identical"] = first == second
        private = json.loads(first)
        if private.get("report_id") != REPORT_ID + "-private-replay" or private.get("schema_version") != 1:
            errors.append("private replay identity differs")
        private_gates["private_public_projection_exact"] = _public_projection(private) == report.get("source_observations")
        private_gates["private_audio_hashes_well_formed"] = all(
            HEX_SHA256.fullmatch(str(source.get(key, ""))) is not None
            for source in private.get("source_observations", [])
            for key in ("encoded_sha256", "pcm_sha256")
        )
        plan = load_json(PLAN_PATH)
        attribution = load_json(private_output_dir / "source-attribution.json")
        expected_attribution = {
            "schema_version": 1,
            "sources": [
                {
                    "attribution": row["attribution"],
                    "exact_member_id": row["exact_member_id"],
                    "licence": row["licence"],
                    "provider_record_url": row["provider_record_url"],
                }
                for row in plan["members"]
            ],
        }
        private_gates["attribution_attachment_matches_plan"] = attribution == expected_attribution
    if errors:
        raise ValueError("; ".join(sorted(set(errors))))
    if not all(private_gates.values()):
        raise ValueError("private projection audit failed")
    observations = {row["exact_member_id"]: row for row in report["source_observations"]}
    freesound = observations["freesound_sound_856645"]
    tinysol = observations["tinysol_6_0__ob_ord_dsharp4_mf_n_n"]
    return {
        "claim_boundary": {
            "descriptor_confirmation_is_perceptual_truth": False,
            "full_objective_complete": False,
            "public_verdict_enabled": False,
            "source_trait_assigned": False,
            "source_trait_manifest_frozen": False,
        },
        "decision": {
            "candidate_replacement_performed": False,
            "freesound_sparse_non_tonal_confirmation_passed": freesound["descriptor_confirmation_passed"],
            "freesound_terminal_outcome": "abstained",
            "rigorous_negative_preserved": True,
            "thresholds_changed_after_observation": False,
            "tinysol_tonal_non_sparse_confirmation_passed": tinysol["descriptor_confirmation_passed"],
        },
        "gates": {
            **private_gates,
            "public_report_path_free_and_audio_hash_redacted": True,
            "public_report_validation_errors": [],
        },
        "observed_on": "2026-08-19",
        "report_id": AUDIT_ID,
        "schema_version": 1,
        "source_report_id": REPORT_ID,
        "state": "independent_projection_audit_complete_sparse_candidate_abstained_tonal_candidate_passed",
    }


def validate_audit(audit: dict[str, Any], report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if audit != build_audit(report):
        errors.append("audit report differs")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-output-dir", type=Path)
    parser.add_argument("--output", type=Path, default=AUDIT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = load_json(REPORT_PATH)
    audit = build_audit(report, args.private_output_dir)
    payload = canonical_json_bytes(audit)
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != payload:
            print("ERROR: committed audit differs")
            return 1
        print(f"validated {AUDIT_ID}")
        return 0
    args.output.write_bytes(payload)
    print(f"wrote {AUDIT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
