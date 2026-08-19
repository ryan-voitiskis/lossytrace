#!/usr/bin/env python3
"""Validate one private live clean-capture manifest without opening audio."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import stat
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-clean-capture-live-intake-plan.json"
)
PLAN_ID = "perceptual-degradation-source-trait-sparse-non-tonal-clean-capture-live-intake-20260819-001"
EXPECTED_BINDINGS = {
    "acquisition_specification",
    "objective_audit",
    "research_contract",
    "synthetic_intake_implementation",
    "synthetic_intake_plan",
    "synthetic_intake_report",
}
EXPECTED_AUTHORITY = {
    "authority_source": "explicit_user_instruction_2026-08-19",
    "one_safe_clean_capture_conduct_or_arrange_authorized": True,
    "outreach_authorized": False,
    "spending_authorized": False,
}
EXPECTED_OPERATIONAL_AUTHORIZATION = {
    "audio_access_authorized": False,
    "capture_execution_authorized_by_this_checkpoint": False,
    "external_communication_authorized": False,
    "human_listener_collection_authorized": False,
    "live_delivery_metadata_acceptance_authorized": True,
    "live_manifest_read_authorized": True,
    "no_reference_training_authorized": False,
    "payment_or_purchase_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "public_verdict_enabled": False,
    "source_manifest_allocation_authorized": False,
    "source_trait_assignment_authorized": False,
}
EXPECTED_INPUT_BOUNDARY = {
    "audio_file_path_field_allowed": False,
    "audio_payload_field_allowed": False,
    "live_manifest_must_remain_outside_repository": True,
    "maximum_manifest_bytes": 65536,
    "permitted_content_type": "application/json",
    "synthetic_fixture_allowed": False,
}
EXPECTED_POST_ACCEPTANCE_GATE = {
    "audio_access_before_exact_member_checkpoint_allowed": False,
    "exact_physical_capture_chain_must_be_bound": True,
    "separate_exact_member_capture_or_confirmation_checkpoint_required": True,
    "threshold_change_allowed": False,
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load bound implementation: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _bound(plan: dict[str, Any], binding_id: str) -> Path:
    return ROOT / plan["bindings"][binding_id]["path"]


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != "live_metadata_acceptance_checkpoint_frozen_before_delivery_capture_execution_and_audio_access":
        errors.append("plan state differs")
    bindings = plan.get("bindings", {})
    if not isinstance(bindings, dict) or set(bindings) != EXPECTED_BINDINGS:
        errors.append("binding inventory differs")
        bindings = {}
    for binding_id, binding in bindings.items():
        if not isinstance(binding, dict):
            errors.append(f"binding must be an object: {binding_id}")
            continue
        path = Path(str(binding.get("path", "")))
        if path.is_absolute() or ".." in path.parts or not (ROOT / path).is_file():
            errors.append(f"invalid binding: {binding_id}")
        elif sha256_file(ROOT / path) != binding.get("sha256"):
            errors.append(f"binding hash differs: {binding_id}")
    if plan.get("authority_received") != EXPECTED_AUTHORITY:
        errors.append("received authority differs")
    if plan.get("operational_authorization") != EXPECTED_OPERATIONAL_AUTHORIZATION:
        errors.append("operational authorization differs")
    if plan.get("input_boundary") != EXPECTED_INPUT_BOUNDARY:
        errors.append("input boundary differs")
    if plan.get("post_acceptance_gate") != EXPECTED_POST_ACCEPTANCE_GATE:
        errors.append("post-acceptance gate differs")
    claims = plan.get("claim_boundary", {})
    if not isinstance(claims, dict) or not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    execution = plan.get("execution_protocol", {})
    if execution != {
        "audio_file_open_attempt_limit": 0,
        "fixed_gate_order": [
            "rights_and_attribution",
            "exact_member_and_source_group_identity",
            "original_wav_lineage",
            "complete_channel_capture_chain",
            "transformation_history",
            "container_and_duration",
            "quiet_context_and_single_event_declaration",
            "safety_declaration",
        ],
        "manifest_count": 1,
        "private_replay_count": 2,
        "public_projection_requires_independent_audit": True,
        "replays_must_be_byte_identical": True,
        "worker_count": 1,
    }:
        errors.append("execution protocol differs")
    output = plan.get("output_boundary", {})
    if not isinstance(output, dict):
        errors.append("output boundary must be an object")
    else:
        if output.get("public_projection_is_aggregate_gate_status_only") is not True:
            errors.append("aggregate output boundary differs")
        if output.get("private_replay_reports_must_remain_outside_repository") is not True:
            errors.append("private replay boundary differs")
        for key, value in output.items():
            if key not in {
                "public_projection_is_aggregate_gate_status_only",
                "private_replay_reports_must_remain_outside_repository",
            } and value is not False:
                errors.append(f"private public-projection field differs: {key}")
    if bindings:
        audit = load_json(_bound(plan, "objective_audit"))
        if audit.get("summary", {}).get("satisfied_count") != 4 or audit.get("summary", {}).get("objective_complete") is not False:
            errors.append("bound objective state differs")
        synthetic = _load_module(_bound(plan, "synthetic_intake_implementation"), "bound_clean_capture_intake")
        synthetic_plan = synthetic.load_json(_bound(plan, "synthetic_intake_plan"))
        if synthetic.validate_plan(synthetic_plan):
            errors.append("bound synthetic intake plan is invalid")
        else:
            report = synthetic.build_public_report(synthetic_plan, synthetic.load_json(synthetic.FIXTURE_PATH))
            if synthetic.canonical_json_bytes(report) != _bound(plan, "synthetic_intake_report").read_bytes():
                errors.append("bound synthetic intake report differs")
    return sorted(set(errors))


def load_private_live_manifest(path: Path, plan: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
    if not path.is_absolute():
        raise ValueError("live manifest path must be absolute")
    if path.is_symlink():
        raise ValueError("live manifest must not be a symbolic link")
    resolved = path.resolve(strict=True)
    if _is_within(resolved, ROOT):
        raise ValueError("live manifest must remain outside the repository")
    mode = resolved.stat().st_mode
    if not stat.S_ISREG(mode):
        raise ValueError("live manifest must be a regular file")
    maximum = int(plan["input_boundary"]["maximum_manifest_bytes"])
    size = resolved.stat().st_size
    if size <= 0 or size > maximum:
        raise ValueError("live manifest byte size is outside the frozen boundary")
    payload = resolved.read_bytes()
    if len(payload) != size:
        raise ValueError("live manifest changed while being read")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("live manifest is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("live manifest must be an object")
    if value.get("synthetic_fixture") is not False:
        raise ValueError("live manifest must explicitly declare synthetic_fixture false")
    return value, payload


def build_private_report(plan: dict[str, Any], manifest: dict[str, Any], manifest_bytes: bytes) -> dict[str, Any]:
    plan_errors = validate_plan(plan)
    if plan_errors:
        raise ValueError("; ".join(plan_errors))
    if manifest.get("synthetic_fixture") is not False:
        raise ValueError("live manifest must explicitly declare synthetic_fixture false")
    intake = _load_module(_bound(plan, "synthetic_intake_implementation"), "clean_capture_intake_for_live_run")
    gate_errors = intake.validate_manifest(manifest, intake.load_json(_bound(plan, "acquisition_specification")))
    if list(gate_errors) != plan["execution_protocol"]["fixed_gate_order"]:
        raise ValueError("live gate order differs")
    gate_status = {gate: not errors for gate, errors in gate_errors.items()}
    accepted = all(gate_status.values())
    return {
        "audio_accessed": False,
        "claim_boundary": plan["claim_boundary"],
        "decision": {
            "exact_member_checkpoint_required_before_audio_access": True,
            "live_delivery_metadata_accepted": accepted,
            "source_trait_manifest_frozen": False,
        },
        "execution": {
            "audio_file_open_attempt_count": 0,
            "gate_count": len(gate_status),
            "gate_pass_count": sum(gate_status.values()),
            "manifest_count": 1,
            "worker_count": 1,
        },
        "gate_errors": gate_errors,
        "gates": gate_status,
        "implementation_sha256": sha256_file(Path(__file__)),
        "observed_on": "2026-08-19",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(PLAN_PATH),
        "private_input_binding": {
            "manifest_byte_size": len(manifest_bytes),
            "manifest_sha256": sha256_bytes(manifest_bytes),
        },
        "schema_version": 1,
        "state": (
            "private_live_clean_capture_metadata_accepted_without_audio_access"
            if accepted
            else "private_live_clean_capture_metadata_rejected_without_audio_access"
        ),
    }


def build_public_projection(plan: dict[str, Any], private_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "audio_accessed": private_report["audio_accessed"],
        "claim_boundary": private_report["claim_boundary"],
        "decision": private_report["decision"],
        "execution": private_report["execution"],
        "gates": private_report["gates"],
        "implementation_sha256": private_report["implementation_sha256"],
        "observed_on": private_report["observed_on"],
        "plan_id": private_report["plan_id"],
        "plan_sha256": private_report["plan_sha256"],
        "publication_boundary": plan["output_boundary"],
        "schema_version": private_report["schema_version"],
        "state": private_report["state"].replace("private_", "public_projection_"),
    }


def _validate_private_output_path(path: Path, *, must_exist: bool) -> Path:
    if not path.is_absolute():
        raise ValueError("private output path must be absolute")
    if path.is_symlink():
        raise ValueError("private output must not be a symbolic link")
    resolved_parent = path.parent.resolve(strict=True)
    if _is_within(resolved_parent, ROOT):
        raise ValueError("private output must remain outside the repository")
    resolved = resolved_parent / path.name
    if must_exist:
        if not resolved.is_file():
            raise ValueError("private replay report does not exist")
    elif resolved.exists():
        raise ValueError("private replay report already exists")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        plan = load_json(PLAN_PATH)
        manifest, manifest_bytes = load_private_live_manifest(args.manifest, plan)
        report = build_private_report(plan, manifest, manifest_bytes)
        payload = canonical_json_bytes(report)
        output = _validate_private_output_path(args.private_output, must_exist=args.check)
        if args.check:
            if output.read_bytes() != payload:
                print("ERROR: private replay report differs")
                return 1
            print("validated private live clean-capture intake replay")
            return 0
        with output.open("xb") as handle:
            handle.write(payload)
        decision = "accepted" if report["decision"]["live_delivery_metadata_accepted"] else "rejected"
        print(f"wrote private live clean-capture intake replay: {decision}")
        return 0 if decision == "accepted" else 2
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
