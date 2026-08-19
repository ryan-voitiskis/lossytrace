#!/usr/bin/env python3
"""Validate the sparse non-tonal clean-capture acquisition specification."""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-clean-capture-acquisition-spec.json"
PLAN_ID = "perceptual-degradation-source-trait-sparse-non-tonal-clean-capture-acquisition-spec-20260819-001"
EXPECTED_BINDINGS = {
    "current_objective_audit",
    "descriptor_implementation",
    "descriptor_plan",
    "metadata_v4_negative",
    "research_contract",
}
TRUE_AUTHORIZATIONS = {"metadata_first_acceptance_design_authorized", "specification_authoring_authorized"}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != "clean_capture_acquisition_specification_frozen_without_outreach_spending_collection_or_audio_access":
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
    expected_authorizations = TRUE_AUTHORIZATIONS | {
        "audio_access_authorized",
        "collection_authorized",
        "external_communication_authorized",
        "payment_or_purchase_authorized",
        "public_verdict_enabled",
        "source_manifest_allocation_authorized",
        "source_trait_assignment_authorized",
    }
    if set(authorization) != expected_authorizations:
        errors.append("authorization inventory differs")
    for key, value in authorization.items():
        if value is not (key in TRUE_AUTHORIZATIONS):
            errors.append(f"authorization differs: {key}")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")

    capture = plan.get("capture_specification", {})
    if capture.get("accepted_event_families") != ["single_balloon_pop", "single_wooden_clapper_impact"]:
        errors.append("safe event inventory differs")
    if capture.get("physical_safety_policy") != "no_firearm_explosive_pyrotechnic_or_hazardous_event":
        errors.append("physical safety boundary differs")
    if capture.get("sample_rate_hz_allowed") != [48000, 96000] or capture.get("wav_bits_per_sample_allowed") != [24]:
        errors.append("container boundary differs")
    if capture.get("sample_format") != "signed_integer_pcm" or capture.get("event_count") != 1:
        errors.append("waveform boundary differs")
    minimum = Decimal(str(capture.get("duration_seconds_minimum")))
    maximum = Decimal(str(capture.get("duration_seconds_maximum")))
    quiet_before = Decimal(str(capture.get("minimum_pre_event_quiet_seconds")))
    quiet_after = Decimal(str(capture.get("minimum_post_event_quiet_seconds")))
    if minimum != Decimal("15.000") or maximum != Decimal("30.000") or minimum >= maximum:
        errors.append("duration boundary differs")
    if quiet_before != Decimal("5.000") or quiet_after != Decimal("5.000"):
        errors.append("quiet-context boundary differs")
    if Decimal(str(capture.get("peak_headroom_dbfs_maximum"))) != Decimal("-3.000"):
        errors.append("headroom boundary differs")

    delivery = plan.get("delivery_requirements", {})
    if delivery.get("licences_allowed") != ["CC0 1.0", "CC BY 4.0"]:
        errors.append("licence boundary differs")
    for key in (
        "attribution_text_required",
        "file_byte_size_required",
        "file_sha256_required",
        "licence_declaration_required",
        "one_exact_take_per_delivery",
        "original_recorder_wav_required",
        "rights_holder_identity_required_privately",
        "source_group_identity_required",
        "transformation_log_required",
    ):
        if delivery.get(key) is not True:
            errors.append(f"delivery requirement differs: {key}")
    required_capture_fields = delivery.get("capture_log_fields", [])
    if len(required_capture_fields) != 9 or len(set(required_capture_fields)) != 9:
        errors.append("capture log inventory differs")

    processing = plan.get("processing_boundary", {})
    if processing.get("allowed_transformations") != ["none"]:
        errors.append("allowed processing boundary differs")
    if processing.get("original_memory_card_or_recorder_file_required") is not True:
        errors.append("original recorder file boundary differs")
    if not {"automatic_gain_control", "limiter", "normalization", "trim"}.issubset(
        set(processing.get("disallowed_transformations", []))
    ):
        errors.append("disallowed processing inventory differs")

    acceptance = plan.get("metadata_first_acceptance", {})
    for key in ("exact_member_checkpoint_required_before_audio_access", "fail_closed_on_ambiguous_or_missing_field"):
        if acceptance.get(key) is not True:
            errors.append(f"acceptance boundary differs: {key}")
    for key in (
        "audio_preview_or_download_before_metadata_acceptance_authorized",
        "member_substitution_after_audio_observation_allowed",
        "threshold_change_allowed",
    ):
        if acceptance.get(key) is not False:
            errors.append(f"acceptance boundary differs: {key}")
    if len(acceptance.get("fixed_review_order", [])) != 8:
        errors.append("fixed review order differs")
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
