#!/usr/bin/env python3
"""Independently audit the sparse non-tonal exact-member v3 projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-exact-member-confirmation-v3-plan.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v3-20260819-001.json"
AUDIT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v3-audit-20260819-001.json"
RUNNER_PATH = ROOT / "scripts/perceptual_degradation_source_trait_sparse_non_tonal_exact_member_confirmation_v3.py"
REPORT_ID = "perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v3-20260819-001"
AUDIT_ID = "perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v3-audit-20260819-001"
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
    occupancy_supported = occupancy.get("supported") is True
    spectral_supported = spectral.get("supported") is True
    if occupancy_supported:
        active = occupancy.get("active_block_count")
        if occupancy.get("block_count") != 10 or not isinstance(active, int) or not 0 <= active <= 10:
            errors.append(f"{label} occupancy support differs")
            return
        if occupancy.get("active_fraction") != f"{active / 10:.9f}":
            errors.append(f"{label} active fraction differs")
        if occupancy.get("sparse") is not (active <= 2) or occupancy.get("non_sparse") is not (active >= 8):
            errors.append(f"{label} occupancy class differs")
    elif occupancy != {"supported": False}:
        errors.append(f"{label} unsupported occupancy differs")
    if spectral_supported:
        active_frames = spectral.get("active_frame_count")
        if not isinstance(active_frames, int) or active_frames < 3:
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
    elif set(spectral) not in ({"supported"}, {"supported", "active_frame_count"}) or spectral.get("active_frame_count", 0) >= 3:
        errors.append(f"{label} unsupported spectral differs")
    supported = occupancy_supported and spectral_supported
    sparse = supported and occupancy.get("sparse") is True
    non_sparse = supported and occupancy.get("non_sparse") is True
    tonal = supported and spectral.get("tonal") is True
    non_tonal = supported and spectral.get("non_tonal") is True
    expected = {
        "sparse_non_tonal_contrast": sparse and non_tonal and not tonal,
        "tonal_non_sparse_contrast": tonal and non_sparse and not sparse,
        "sparse_tonal_overlap": sparse and tonal,
    }
    expected["abstain"] = not supported or not any(expected.values())
    for key, value in expected.items():
        if channel.get(key) is not value:
            errors.append(f"{label} class predicate differs: {key}")


def validate_report(report: dict[str, Any], plan: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    plan = plan or load_json(PLAN_PATH)
    if report.get("schema_version") != 1 or report.get("report_id") != REPORT_ID:
        errors.append("report identity differs")
    if report.get("state") != "one_exact_sparse_non_tonal_successor_v3_score_free_descriptor_replays_complete":
        errors.append("report state differs")
    if report.get("plan_id") != plan.get("plan_id") or report.get("plan_sha256") != sha256_file(PLAN_PATH):
        errors.append("report plan binding differs")
    if report.get("implementation_sha256") != sha256_file(RUNNER_PATH):
        errors.append("report implementation binding differs")
    if report.get("nominated_exact_member_id") != "freesound_sound_476736":
        errors.append("exact member differs")
    if report.get("execution") != {
        "decoded_or_derived_pcm_retained": False,
        "exact_member_count": 1,
        "maximum_workers": 1,
        "minimum_free_disk_gib_preserved": 15,
        "private_replay_count": 2,
        "private_reports_byte_identical": True,
    }:
        errors.append("execution boundary differs")
    decision = report.get("decision", {})
    terminal = decision.get("terminal_outcome")
    passed = decision.get("descriptor_confirmation_passed")
    if terminal not in {"passed", "abstained", "class_mismatch"}:
        errors.append("terminal outcome differs")
    if passed is not (terminal == "passed"):
        errors.append("public confirmation predicate differs")
    if decision != {
        "candidate_replacement_performed": False,
        "descriptor_confirmation_complete": True,
        "descriptor_confirmation_passed": passed,
        "source_manifest_allocated": False,
        "source_trait_assignment_complete": False,
        "terminal_outcome": terminal,
        "thresholds_changed_after_observation": False,
    }:
        errors.append("decision boundary differs")
    if report.get("publication_boundary") != {
        "audio_exposed": False,
        "channel_measurements_exposed": False,
        "encoded_or_pcm_hashes_exposed": False,
        "private_paths_exposed": False,
        "provider_scores_or_processed_conditions_exposed": False,
    }:
        errors.append("publication boundary differs")
    claims = report.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")

    def scan_paths(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values():
                scan_paths(child)
        elif isinstance(value, list):
            for child in value:
                scan_paths(child)
        elif isinstance(value, str) and (value.startswith("/") or value.startswith("file:")):
            errors.append("public report exposes path-like value")

    scan_paths(report)
    serialized = json.dumps(report, sort_keys=True)
    for forbidden in (
        "Application Support",
        "channel_descriptors",
        "container",
        "encoded_sha256",
        "pcm_sha256",
        "private-replay",
        "provider_original",
        "relative_path",
    ):
        if forbidden in serialized:
            errors.append(f"public report exposes forbidden material: {forbidden}")
    return sorted(set(errors))


def _validate_private(private: dict[str, Any], plan: dict[str, Any]) -> tuple[list[str], str, bool]:
    errors: list[str] = []
    if private.get("report_id") != REPORT_ID + "-private-replay" or private.get("schema_version") != 1:
        errors.append("private replay identity differs")
    source = private.get("source_observation", {})
    member = plan["member"]
    for key in ("attribution", "exact_member_id", "licence", "provider_id", "provider_record_url"):
        if source.get(key) != member.get(key):
            errors.append(f"private source binding differs: {key}")
    for key in ("encoded_sha256", "pcm_sha256"):
        if HEX_SHA256.fullmatch(str(source.get(key, ""))) is None:
            errors.append(f"private audio hash differs: {key}")
    measurement = source.get("measurement", {})
    container = measurement.get("container", {})
    expected_container = member["expected_container"]
    for key in ("bits_per_sample", "channel_count", "sample_format", "sample_rate_hz"):
        if container.get(key) != expected_container[key]:
            errors.append(f"private container differs: {key}")
    if not isinstance(container.get("frame_count"), int) or container["frame_count"] <= 0:
        errors.append("private frame count differs")
    try:
        duration = Decimal(str(container["duration_seconds"]))
        if not Decimal(expected_container["duration_seconds_minimum"]) <= duration <= Decimal(
            expected_container["duration_seconds_maximum"]
        ):
            errors.append("private duration differs")
    except (KeyError, TypeError, ValueError):
        errors.append("private duration display differs")
    channels = measurement.get("channel_descriptors", [])
    if not isinstance(channels, list) or len(channels) != expected_container["channel_count"]:
        errors.append("private channel inventory differs")
        channels = []
    for index, channel in enumerate(channels):
        _validate_channel(channel, errors, f"private channel {index}")
    expected_class = member["expected_descriptor_class"]
    agreement = bool(channels) and all(
        channel.get(expected_class) is True and channel.get("abstain") is False for channel in channels
    )
    terminal = "passed" if agreement else ("abstained" if any(row.get("abstain") is True for row in channels) else "class_mismatch")
    if measurement.get("expected_descriptor_class") != expected_class:
        errors.append("private expected class differs")
    if measurement.get("all_supported_channels_agree") is not agreement:
        errors.append("private agreement predicate differs")
    if measurement.get("descriptor_confirmation_passed") is not agreement:
        errors.append("private confirmation predicate differs")
    if measurement.get("terminal_outcome") != terminal:
        errors.append("private terminal outcome differs")
    return errors, terminal, agreement


def _expected_public(plan: dict[str, Any], terminal: str, passed: bool) -> dict[str, Any]:
    return {
        "claim_boundary": plan["claim_boundary"],
        "decision": {
            "candidate_replacement_performed": False,
            "descriptor_confirmation_complete": True,
            "descriptor_confirmation_passed": passed,
            "source_manifest_allocated": False,
            "source_trait_assignment_complete": False,
            "terminal_outcome": terminal,
            "thresholds_changed_after_observation": False,
        },
        "execution": {
            "decoded_or_derived_pcm_retained": False,
            "exact_member_count": 1,
            "maximum_workers": 1,
            "minimum_free_disk_gib_preserved": 15,
            "private_replay_count": 2,
            "private_reports_byte_identical": True,
        },
        "implementation_sha256": sha256_file(RUNNER_PATH),
        "nominated_exact_member_id": plan["member"]["exact_member_id"],
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(PLAN_PATH),
        "publication_boundary": {
            "audio_exposed": False,
            "channel_measurements_exposed": False,
            "encoded_or_pcm_hashes_exposed": False,
            "private_paths_exposed": False,
            "provider_scores_or_processed_conditions_exposed": False,
        },
        "report_id": REPORT_ID,
        "schema_version": 1,
        "state": "one_exact_sparse_non_tonal_successor_v3_score_free_descriptor_replays_complete",
    }


def build_audit(report: dict[str, Any], private_output_dir: Path | None = None) -> dict[str, Any]:
    errors = validate_report(report)
    gates = {
        "attribution_attachment_matches_plan": True,
        "private_audio_hashes_well_formed": True,
        "private_public_projection_exact": True,
        "private_replays_byte_identical": True,
    }
    terminal = report.get("decision", {}).get("terminal_outcome")
    passed = report.get("decision", {}).get("descriptor_confirmation_passed")
    if private_output_dir is not None:
        if private_output_dir.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("private output must remain outside the repository")
        first = (private_output_dir / "private-replay-a.json").read_bytes()
        second = (private_output_dir / "private-replay-b.json").read_bytes()
        gates["private_replays_byte_identical"] = first == second
        plan = load_json(PLAN_PATH)
        private = json.loads(first)
        private_errors, terminal, passed = _validate_private(private, plan)
        errors.extend(private_errors)
        gates["private_audio_hashes_well_formed"] = all(
            HEX_SHA256.fullmatch(str(private["source_observation"].get(key, ""))) is not None
            for key in ("encoded_sha256", "pcm_sha256")
        )
        gates["private_public_projection_exact"] = _expected_public(plan, terminal, passed) == report
        attribution = load_json(private_output_dir / "source-attribution.json")
        gates["attribution_attachment_matches_plan"] = attribution == {
            "attribution": plan["member"]["attribution"],
            "exact_member_id": plan["member"]["exact_member_id"],
            "licence": plan["member"]["licence"],
            "provider_record_url": plan["member"]["provider_record_url"],
            "schema_version": 1,
        }
    if errors:
        raise ValueError("; ".join(sorted(set(errors))))
    if not all(gates.values()):
        raise ValueError("private projection audit failed")
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
            "descriptor_confirmation_passed": passed,
            "rigorous_negative_preserved": passed is False,
            "terminal_outcome": terminal,
            "thresholds_changed_after_observation": False,
        },
        "gates": {
            **gates,
            "public_report_path_measurement_and_audio_hash_redacted": True,
            "public_report_validation_errors": [],
        },
        "observed_on": "2026-08-19",
        "report_id": AUDIT_ID,
        "schema_version": 1,
        "source_report_id": REPORT_ID,
        "state": f"independent_projection_audit_complete_sparse_successor_v3_{terminal}",
    }


def validate_audit(audit: dict[str, Any], report: dict[str, Any]) -> list[str]:
    return [] if audit == build_audit(report) else ["audit report differs"]


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
