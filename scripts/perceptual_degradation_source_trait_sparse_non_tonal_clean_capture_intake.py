#!/usr/bin/env python3
"""Validate a metadata-only clean-capture intake manifest without opening audio."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-clean-capture-intake-plan.json"
SPEC_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-clean-capture-acquisition-spec.json"
FIXTURE_PATH = ROOT / "scripts/tests/fixtures/clean_capture_intake_valid_synthetic.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-clean-capture-intake-synthetic-20260819-001.json"
PLAN_ID = "perceptual-degradation-source-trait-sparse-non-tonal-clean-capture-intake-20260819-001"
REPORT_ID = "perceptual-degradation-source-trait-sparse-non-tonal-clean-capture-intake-synthetic-20260819-001"
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
OPAQUE_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,79}\Z")
EXPECTED_BINDINGS = {
    "acquisition_specification",
    "current_objective_audit",
    "descriptor_implementation",
    "descriptor_plan",
    "research_contract",
}
TRUE_AUTHORIZATIONS = {"metadata_only_synthetic_validation_authorized"}
GATE_ORDER = [
    "rights_and_attribution",
    "exact_member_and_source_group_identity",
    "original_wav_lineage",
    "complete_channel_capture_chain",
    "transformation_history",
    "container_and_duration",
    "quiet_context_and_single_event_declaration",
    "safety_declaration",
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load module: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _decimal(value: Any, label: str, errors: list[str]) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        errors.append(f"{label} must be a decimal")
        return None
    if not parsed.is_finite():
        errors.append(f"{label} must be finite")
        return None
    return parsed


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != "metadata_only_clean_capture_intake_gate_frozen_before_live_delivery":
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
    expected = TRUE_AUTHORIZATIONS | {
        "audio_access_authorized",
        "collection_authorized",
        "external_communication_authorized",
        "live_delivery_acceptance_authorized",
        "payment_or_purchase_authorized",
        "public_verdict_enabled",
        "source_manifest_allocation_authorized",
        "source_trait_assignment_authorized",
    }
    if set(authorization) != expected:
        errors.append("authorization inventory differs")
    for key, value in authorization.items():
        if value is not (key in TRUE_AUTHORIZATIONS):
            errors.append(f"authorization differs: {key}")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    if plan.get("input_boundary") != {
        "audio_file_path_field_allowed": False,
        "audio_payload_field_allowed": False,
        "live_manifest_must_remain_outside_repository": True,
        "maximum_manifest_bytes": 65536,
        "permitted_content_type": "application/json",
        "synthetic_fixture_inside_repository_authorized": True,
    }:
        errors.append("input boundary differs")
    output = plan.get("output_boundary", {})
    if output.get("public_result_is_aggregate_gate_status_only") is not True:
        errors.append("aggregate output boundary differs")
    if any(value is not False for key, value in output.items() if key != "public_result_is_aggregate_gate_status_only"):
        errors.append("private output boundary differs")
    policy = plan.get("result_policy", {})
    if policy != {
        "accepted_metadata_requires_separate_exact_member_checkpoint": True,
        "all_gate_groups_must_pass": True,
        "ambiguous_or_missing_field_fails_closed": True,
        "member_substitution_after_audio_observation_allowed": False,
        "synthetic_pass_is_live_delivery_acceptance": False,
        "threshold_change_allowed": False,
    }:
        errors.append("result policy differs")
    prerequisite = plan.get("prerequisite_state", {})
    if prerequisite != {
        "acquisition_specification_commit": "bea06387ed325008768402641a8bb34c85b77275",
        "acquisition_specification_exact_head_ci_attempt": 2,
        "acquisition_specification_exact_head_ci_conclusion": "success",
        "acquisition_specification_exact_head_ci_run": 32224733497,
    }:
        errors.append("prerequisite exact-head state differs")
    specification = load_json(SPEC_PATH)
    if specification.get("authorization", {}).get("external_communication_authorized") is not False:
        errors.append("bound specification external action differs")
    objective = load_json(ROOT / bindings.get("current_objective_audit", {}).get("path", "missing")) if bindings else {}
    if objective.get("summary", {}).get("satisfied_count") != 4 or objective.get("summary", {}).get("objective_complete") is not False:
        errors.append("bound objective state differs")
    return sorted(set(errors))


def _manifest_shape_errors(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(manifest) != {
        "capture",
        "declarations",
        "delivery_id",
        "exact_member_id",
        "file",
        "processing",
        "rights",
        "schema_version",
        "source_group_id",
        "synthetic_fixture",
    }:
        errors.append("manifest top-level inventory differs")
    serialized = json.dumps(manifest, sort_keys=True)
    for forbidden in ("audio_path", "file_path", "payload", "base64", "file://", "/Users/", "/home/"):
        if forbidden in serialized:
            errors.append(f"manifest contains forbidden path or payload material: {forbidden}")

    def scan(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered = str(key).lower()
                if "path" in lowered or "payload" in lowered or "base64" in lowered:
                    errors.append(f"manifest contains forbidden path or payload field: {key}")
                scan(child)
        elif isinstance(value, list):
            for child in value:
                scan(child)
        elif isinstance(value, str) and (value.startswith("/") or value.startswith("file:") or re.match(r"^[A-Za-z]:\\", value)):
            errors.append("manifest contains forbidden path-like value")

    scan(manifest)
    return errors


def validate_manifest(manifest: dict[str, Any], specification: dict[str, Any] | None = None) -> dict[str, list[str]]:
    specification = specification or load_json(SPEC_PATH)
    gates = {gate: [] for gate in GATE_ORDER}
    gates["exact_member_and_source_group_identity"].extend(_manifest_shape_errors(manifest))
    if manifest.get("schema_version") != 1:
        gates["exact_member_and_source_group_identity"].append("manifest schema differs")
    for key in ("delivery_id", "exact_member_id", "source_group_id"):
        if OPAQUE_ID.fullmatch(str(manifest.get(key, ""))) is None:
            gates["exact_member_and_source_group_identity"].append(f"{key} is not an opaque identifier")

    rights = manifest.get("rights", {})
    if not isinstance(rights, dict):
        gates["rights_and_attribution"].append("rights must be an object")
        rights = {}
    if rights.get("licence") not in specification["delivery_requirements"]["licences_allowed"]:
        gates["rights_and_attribution"].append("licence is not allowed")
    for key in ("attribution_text", "rights_holder_identity", "performer_clearance_status", "location_clearance_status"):
        if not isinstance(rights.get(key), str) or not rights[key].strip():
            gates["rights_and_attribution"].append(f"rights field missing: {key}")
    declarations = manifest.get("declarations", {})
    if not isinstance(declarations, dict):
        gates["rights_and_attribution"].append("declarations must be an object")
        declarations = {}
    for key in ("capture_log_complete_and_accurate", "one_exact_take_only", "original_recorder_file", "rights_information_complete_and_accurate"):
        if declarations.get(key) is not True:
            gates["original_wav_lineage" if key == "original_recorder_file" else "rights_and_attribution"].append(
                f"declaration differs: {key}"
            )

    file_record = manifest.get("file", {})
    if not isinstance(file_record, dict):
        gates["original_wav_lineage"].append("file must be an object")
        file_record = {}
    logical_name = file_record.get("logical_name")
    if not isinstance(logical_name, str) or Path(logical_name).name != logical_name or not logical_name.lower().endswith(".wav"):
        gates["original_wav_lineage"].append("logical WAV name differs")
    if HEX_SHA256.fullmatch(str(file_record.get("sha256", ""))) is None:
        gates["original_wav_lineage"].append("file SHA-256 differs")
    if not isinstance(file_record.get("byte_size"), int) or file_record["byte_size"] <= 0:
        gates["original_wav_lineage"].append("file byte size differs")

    processing = manifest.get("processing", {})
    if processing != {"transformations": []}:
        gates["transformation_history"].append("transformations must be explicitly empty")

    capture = manifest.get("capture", {})
    if not isinstance(capture, dict):
        gates["complete_channel_capture_chain"].append("capture must be an object")
        capture = {}
    timestamp = capture.get("capture_utc_timestamp")
    if not isinstance(timestamp, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", timestamp) is None:
        gates["complete_channel_capture_chain"].append("UTC timestamp differs")
    for key in ("event_material_and_actuation", "location_and_room_description", "recorder_make_model", "recorder_firmware"):
        if not isinstance(capture.get(key), str) or not capture[key].strip():
            gates["complete_channel_capture_chain"].append(f"capture field missing: {key}")
    controls = capture.get("processing_controls", {})
    if controls != {
        "automatic_gain_control_enabled": False,
        "filters_enabled": False,
        "limiter_enabled": False,
        "safety_track_enabled": False,
    }:
        gates["complete_channel_capture_chain"].append("capture processing controls differ")
    channels = capture.get("channels", [])
    container = file_record.get("container", {})
    if not isinstance(container, dict):
        gates["container_and_duration"].append("container must be an object")
        container = {}
    channel_count = container.get("channel_count")
    if not isinstance(channels, list) or not isinstance(channel_count, int) or len(channels) != channel_count or channel_count not in {1, 2}:
        gates["complete_channel_capture_chain"].append("channel inventory differs")
        channels = []
    indices = []
    for channel in channels:
        if not isinstance(channel, dict):
            gates["complete_channel_capture_chain"].append("channel must be an object")
            continue
        indices.append(channel.get("channel_index"))
        for key in ("gain_setting", "microphone_make_model", "microphone_mapping", "orientation", "position"):
            if not isinstance(channel.get(key), str) or not channel[key].strip():
                gates["complete_channel_capture_chain"].append(f"channel field missing: {key}")
        distance = _decimal(channel.get("source_distance_metres"), "source distance", gates["complete_channel_capture_chain"])
        if distance is not None and distance <= 0:
            gates["complete_channel_capture_chain"].append("source distance must be positive")
    if indices != list(range(1, len(channels) + 1)):
        gates["complete_channel_capture_chain"].append("channel indices differ")

    spec_capture = specification["capture_specification"]
    if container.get("format") != "WAV" or container.get("sample_format") != spec_capture["sample_format"]:
        gates["container_and_duration"].append("container format differs")
    if container.get("sample_rate_hz") not in spec_capture["sample_rate_hz_allowed"]:
        gates["container_and_duration"].append("sample rate differs")
    if container.get("bits_per_sample") not in spec_capture["wav_bits_per_sample_allowed"]:
        gates["container_and_duration"].append("bit depth differs")
    duration = _decimal(container.get("duration_seconds"), "duration", gates["container_and_duration"])
    peak = _decimal(container.get("peak_dbfs"), "peak", gates["container_and_duration"])
    if duration is not None and not Decimal(spec_capture["duration_seconds_minimum"]) <= duration <= Decimal(
        spec_capture["duration_seconds_maximum"]
    ):
        gates["container_and_duration"].append("duration outside frozen range")
    if peak is not None and peak > Decimal(spec_capture["peak_headroom_dbfs_maximum"]):
        gates["container_and_duration"].append("peak headroom differs")

    if capture.get("event_family") not in spec_capture["accepted_event_families"]:
        gates["quiet_context_and_single_event_declaration"].append("event family differs")
    if capture.get("event_count") != 1 or capture.get("other_salient_event_present") is not False:
        gates["quiet_context_and_single_event_declaration"].append("single-event declaration differs")
    quiet_before = _decimal(capture.get("pre_event_quiet_seconds"), "pre-event quiet", gates["quiet_context_and_single_event_declaration"])
    quiet_after = _decimal(capture.get("post_event_quiet_seconds"), "post-event quiet", gates["quiet_context_and_single_event_declaration"])
    if quiet_before is not None and quiet_before < Decimal(spec_capture["minimum_pre_event_quiet_seconds"]):
        gates["quiet_context_and_single_event_declaration"].append("pre-event quiet margin differs")
    if quiet_after is not None and quiet_after < Decimal(spec_capture["minimum_post_event_quiet_seconds"]):
        gates["quiet_context_and_single_event_declaration"].append("post-event quiet margin differs")
    if capture.get("safe_non_hazardous_event_confirmed") is not True:
        gates["safety_declaration"].append("safe event declaration differs")
    return {key: sorted(set(value)) for key, value in gates.items()}


def build_public_report(plan: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    plan_errors = validate_plan(plan)
    if plan_errors:
        raise ValueError("; ".join(plan_errors))
    if fixture.get("synthetic_fixture") is not True:
        raise ValueError("only the committed synthetic fixture is authorized")
    gate_errors = validate_manifest(fixture)
    gate_status = {gate: not errors for gate, errors in gate_errors.items()}
    accepted = all(gate_status.values())
    if not accepted:
        raise ValueError("synthetic fixture failed: " + "; ".join(error for errors in gate_errors.values() for error in errors))
    return {
        "audio_accessed": False,
        "claim_boundary": plan["claim_boundary"],
        "decision": {
            "accepted_metadata_requires_separate_exact_member_checkpoint": True,
            "live_delivery_accepted": False,
            "synthetic_fixture_passed": True,
        },
        "execution": {
            "audio_file_open_attempt_count": 0,
            "gate_count": len(gate_status),
            "gate_pass_count": sum(gate_status.values()),
            "manifest_count": 1,
            "synthetic_fixture_only": True,
        },
        "gates": gate_status,
        "implementation_sha256": sha256_file(Path(__file__)),
        "observed_on": "2026-08-19",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(PLAN_PATH),
        "publication_boundary": plan["output_boundary"],
        "report_id": REPORT_ID,
        "schema_version": 1,
        "state": "metadata_only_clean_capture_intake_synthetic_validation_passed_without_live_acceptance",
        "synthetic_fixture_sha256": sha256_file(FIXTURE_PATH),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.synthetic:
        print("ERROR: live delivery acceptance is not authorized; use --synthetic")
        return 1
    report = build_public_report(load_json(PLAN_PATH), load_json(FIXTURE_PATH))
    payload = canonical_json_bytes(report)
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != payload:
            print("ERROR: committed synthetic report differs")
            return 1
        print(f"validated {REPORT_ID}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
