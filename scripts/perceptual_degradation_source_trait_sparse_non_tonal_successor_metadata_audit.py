#!/usr/bin/env python3
"""Replay the metadata-only sparse non-tonal successor audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-successor-metadata-audit-plan.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-successor-metadata-audit-20260819-001.json"
PLAN_ID = "perceptual-degradation-source-trait-sparse-non-tonal-successor-metadata-audit-20260819-001"
REPORT_ID = PLAN_ID
EXPECTED_BINDINGS = {"failed_confirmation_audit", "failed_confirmation_plan", "failed_confirmation_report"}
EXPECTED_IDS = {
    "freesound_sound_866967",
    "freesound_sound_273338",
    "freesound_sound_710084",
    "freesound_sound_73385",
    "freesound_sound_728514",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def _duration(container_summary: str) -> Decimal:
    marker = container_summary.rsplit(";", 1)[-1].strip().split(" ", 1)[0]
    return Decimal(marker)


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != "metadata_only_sparse_non_tonal_successor_audit_frozen_without_audio_access":
        errors.append("plan state differs")
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != EXPECTED_BINDINGS:
        errors.append("binding inventory differs")
        bindings = {}
    for binding_id, binding in bindings.items():
        path = Path(str(binding.get("path", "")))
        if path.is_absolute() or ".." in path.parts or not (ROOT / path).is_file():
            errors.append(f"invalid binding: {binding_id}")
        elif sha256_file(ROOT / path) != binding.get("sha256"):
            errors.append(f"binding hash differs: {binding_id}")
    authorization = plan.get("authorization", {})
    allowed = {"exact_member_metadata_audit_authorized", "public_and_provider_metadata_read_authorized"}
    for key, value in authorization.items():
        if value is not (key in allowed):
            errors.append(f"authorization differs: {key}")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    eligibility = plan.get("candidate_eligibility", {})
    if eligibility.get("allowed_licences") != ["CC0 1.0", "CC BY 4.0"]:
        errors.append("allowed licences differ")
    for key in (
        "all_channel_capture_chain_must_be_explicit",
        "exact_transformation_history_must_be_explicit",
        "original_lossless_provider_wav_must_be_supported",
        "previously_failed_exact_member_must_be_excluded",
        "single_natural_transient_must_be_supported_by_metadata",
    ):
        if eligibility.get(key) is not True:
            errors.append(f"eligibility boundary differs: {key}")
    if Decimal(str(eligibility.get("minimum_duration_seconds"))) != Decimal("2.000"):
        errors.append("duration boundary differs")
    rows = plan.get("observed_records", [])
    if not isinstance(rows, list) or {row.get("exact_member_id") for row in rows} != EXPECTED_IDS:
        errors.append("observed record inventory differs")
        rows = []
    for row in rows:
        parsed = urlparse(str(row.get("provider_record_url", "")))
        sound_number = row.get("exact_member_id", "").rsplit("_", 1)[-1]
        if parsed.scheme != "https" or parsed.netloc != "freesound.org" or f"/sounds/{sound_number}/" not in parsed.path:
            errors.append(f"provider URL differs: {row.get('exact_member_id')}")
        if row.get("provider_id") != "freesound" or row.get("licence") != "CC0 1.0":
            errors.append(f"provider or licence differs: {row.get('exact_member_id')}")
        if not row.get("rejection_reasons"):
            errors.append(f"candidate lacks rejection reason: {row.get('exact_member_id')}")
    return sorted(set(errors))


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    failed_plan = load_json(_bound(plan, "failed_confirmation_plan"))
    failed_report = load_json(_bound(plan, "failed_confirmation_report"))
    failed_audit = load_json(_bound(plan, "failed_confirmation_audit"))
    failed_id = "freesound_sound_856645"
    if failed_id not in {row["exact_member_id"] for row in failed_plan["members"]}:
        raise ValueError("failed exact member is not bound")
    failed_observation = next(row for row in failed_report["source_observations"] if row["exact_member_id"] == failed_id)
    if failed_observation["descriptor_confirmation_passed"] is not False:
        raise ValueError("bound failed candidate no longer abstains")
    if failed_audit["decision"]["freesound_terminal_outcome"] != "abstained":
        raise ValueError("bound failed-candidate audit differs")

    minimum_duration = Decimal(plan["candidate_eligibility"]["minimum_duration_seconds"])
    dispositions = []
    for row in plan["observed_records"]:
        reasons = list(row["rejection_reasons"])
        duration = _duration(row["container_summary"])
        if duration < minimum_duration and "duration_below_frozen_minimum" not in reasons:
            raise ValueError(f"duration rejection missing: {row['exact_member_id']}")
        if duration >= minimum_duration and "duration_below_frozen_minimum" in reasons:
            raise ValueError(f"unexpected duration rejection: {row['exact_member_id']}")
        dispositions.append({
            "audio_accessed": False,
            "eligible_for_audio_access_successor": False,
            "exact_member_id": row["exact_member_id"],
            "licence": row["licence"],
            "metadata_supports_single_natural_transient": row["metadata_supports_single_natural_transient"],
            "provider_id": row["provider_id"],
            "provider_record_url": row["provider_record_url"],
            "rejection_reasons": reasons,
        })
    if any(row["eligible_for_audio_access_successor"] for row in dispositions):
        raise ValueError("audit unexpectedly selected a successor")
    return {
        "audio_accessed": False,
        "claim_boundary": plan["claim_boundary"],
        "decision": {
            "candidate_replacement_performed": False,
            "eligible_successor_count": 0,
            "next_gate": "Continue metadata-only research until one new exact member has permissive rights, a provider-original lossless WAV, an explicit all-channel capture chain, an explicit no-processing or trim-only history, and metadata support for one natural transient of at least two seconds. Bind that member in a new checkpoint before any audio access.",
            "previous_abstention_preserved": True,
            "source_manifest_allocated": False,
            "source_trait_assigned": False,
            "thresholds_changed_after_observation": False,
        },
        "implementation_sha256": sha256_file(Path(__file__)),
        "observed_on": "2026-08-19",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "record_dispositions": dispositions,
        "report_id": REPORT_ID,
        "schema_version": 1,
        "state": "metadata_only_sparse_non_tonal_successor_routes_rejected_before_audio_access",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report(load_json(args.plan), args.plan)
    payload = canonical_json_bytes(report)
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != payload:
            print("ERROR: committed report differs from deterministic replay")
            return 1
        print(f"validated {REPORT_ID}")
        return 0
    args.output.write_bytes(payload)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
