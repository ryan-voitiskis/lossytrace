#!/usr/bin/env python3
"""Validate the bounded sparse non-tonal metadata-search v3 checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-metadata-search-v3-plan.json"
PLAN_ID = "perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v3-20260819-001"
EXPECTED_BINDINGS = {
    "current_objective_audit",
    "descriptor_implementation",
    "descriptor_plan",
    "failed_exact_member_v2_audit",
    "failed_exact_member_v2_report",
    "predecessor_metadata_implementation",
    "predecessor_metadata_plan",
    "predecessor_metadata_report",
    "research_contract",
}
EXPECTED_EXCLUDED_IDS = {
    "freesound_sound_856645",
    "freesound_sound_866967",
    "freesound_sound_273338",
    "freesound_sound_710084",
    "freesound_sound_73385",
    "freesound_sound_728514",
    "freesound_sound_845921",
    "freesound_sound_543775",
    "freesound_sound_193044",
    "freesound_sound_345762",
    "freesound_sound_240344",
    "freesound_sound_151320",
    "freesound_sound_23040",
    "freesound_sound_367702",
    "freesound_sound_703342",
}
TRUE_AUTHORIZATIONS = {
    "browser_authentication_state_verification_authorized",
    "exact_member_metadata_nomination_authorized",
    "metadata_only_network_research_authorized",
    "public_and_provider_metadata_read_authorized",
}
EXPECTED_AUTHORIZATIONS = TRUE_AUTHORIZATIONS | {
    "human_collection_authorized",
    "no_reference_training_authorized",
    "perceptual_metric_execution_authorized",
    "provider_processed_condition_or_score_access_authorized",
    "public_verdict_enabled",
    "sealed_evidence_access_authorized",
    "source_manifest_allocation_authorized",
    "source_trait_assignment_authorized",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != "bounded_metadata_only_sparse_non_tonal_successor_search_v3_frozen_before_query_execution":
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
    if set(authorization) != EXPECTED_AUTHORIZATIONS:
        errors.append("authorization inventory differs")
    for key, value in authorization.items():
        if value is not (key in TRUE_AUTHORIZATIONS):
            errors.append(f"authorization differs: {key}")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")

    eligibility = plan.get("candidate_eligibility", {})
    if eligibility.get("allowed_licences") != ["CC0 1.0", "CC BY 4.0"]:
        errors.append("allowed licences differ")
    minimum = Decimal(str(eligibility.get("duration_seconds_minimum")))
    maximum = Decimal(str(eligibility.get("duration_seconds_maximum")))
    if minimum != Decimal("5.000") or maximum != Decimal("60.000") or minimum >= maximum:
        errors.append("duration boundary differs")
    excluded = set(eligibility.get("excluded_exact_member_ids", []))
    if excluded != EXPECTED_EXCLUDED_IDS:
        errors.append("excluded exact-member inventory differs")
    for key in (
        "all_channel_capture_chain_must_be_explicit",
        "exact_transformation_history_must_be_explicit",
        "natural_waveform_intent_must_be_explicit",
        "original_lossless_provider_wav_lineage_must_be_explicit",
        "single_broadband_natural_transient_with_recording_context_must_be_supported_by_metadata",
    ):
        if eligibility.get(key) is not True:
            errors.append(f"eligibility boundary differs: {key}")

    predecessor = load_json(_bound(plan, "predecessor_metadata_report"))
    prior_ids = {row["exact_member_id"] for row in predecessor.get("record_dispositions", [])}
    prior_plan = load_json(_bound(plan, "predecessor_metadata_plan"))
    prior_ids.update(prior_plan["candidate_eligibility"]["excluded_exact_member_ids"])
    if prior_ids != EXPECTED_EXCLUDED_IDS:
        errors.append("predecessor consumed-member chain differs")
    failed = load_json(_bound(plan, "failed_exact_member_v2_report"))
    failed_audit = load_json(_bound(plan, "failed_exact_member_v2_audit"))
    if failed.get("nominated_exact_member_id") != "freesound_sound_703342":
        errors.append("failed exact member differs")
    if failed.get("decision", {}).get("terminal_outcome") != "class_mismatch":
        errors.append("failed exact-member outcome differs")
    if failed_audit.get("decision", {}).get("rigorous_negative_preserved") is not True:
        errors.append("failed exact-member audit differs")

    media = plan.get("media_boundary", {})
    for key, value in media.items():
        if key not in {"maximum_text_response_bytes", "permitted_primary_record_content_types"} and value is not False:
            errors.append(f"media boundary differs: {key}")
    if media.get("maximum_text_response_bytes") != 2 * 1024 * 1024:
        errors.append("text response size bound differs")
    if media.get("permitted_primary_record_content_types") != ["text/html", "application/json"]:
        errors.append("permitted content types differ")

    protocol = plan.get("search_protocol", {})
    queries = protocol.get("query_order", [])
    if protocol.get("discovery_query_count_maximum") != 8 or len(queries) != 8 or len(set(queries)) != 8:
        errors.append("discovery query bound differs")
    if protocol.get("exact_primary_record_count_maximum") != 20:
        errors.append("primary record bound differs")
    if protocol.get("primary_record_hosts") != ["freesound.org"]:
        errors.append("primary record hosts differ")
    if protocol.get("discovery_snippets_are_evidence") is not False:
        errors.append("discovery snippets cannot be evidence")

    policy = plan.get("result_policy", {})
    for key in (
        "bounded_negative_is_valid",
        "eligible_member_requires_new_committed_audio_checkpoint",
        "first_fully_eligible_exact_member_is_nominated",
        "search_stops_after_first_fully_eligible_exact_member",
    ):
        if policy.get(key) is not True:
            errors.append(f"result policy differs: {key}")
    if policy.get("metadata_nomination_is_trait_assignment") is not False:
        errors.append("metadata nomination cannot assign a trait")
    if policy.get("member_substitution_after_audio_observation_allowed") is not False:
        errors.append("post-observation member substitution must remain closed")
    if policy.get("threshold_change_allowed") is not False:
        errors.append("threshold change must remain closed")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    args = parser.parse_args()
    errors = validate_plan(load_json(args.plan))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated {PLAN_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
