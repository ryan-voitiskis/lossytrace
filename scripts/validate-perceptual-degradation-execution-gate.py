#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "metric-execution-gate.json"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(gate: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if gate.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if gate.get("state") != "metric_execution_blocked_pending_cross_environment_and_legal_clearance":
        errors.append("metric gate must remain blocked pending cross-environment and legal gates")
    for key in (
        "public_verdict_enabled",
        "retained_audio_metric_execution_authorized",
        "public_development_audio_metric_execution_authorized",
        "perceptual_metric_execution_authorized",
        "human_collection_authorized",
        "no_reference_training_authorized",
    ):
        if gate.get(key) is not False:
            errors.append(f"{key} must remain false")
    completed = gate.get("completed_prerequisites", {})
    if completed.get("score_blind_public_development_manifest_frozen") is not True:
        errors.append("score-blind public-development manifest must remain frozen")
    if completed.get("visqol_synthetic_replay_plan_frozen") is not True:
        errors.append("ViSQOL synthetic replay plan must remain frozen")
    if completed.get("visqol_single_environment_synthetic_replay_complete") is not True:
        errors.append("ViSQOL single-environment synthetic replay must be complete")
    if completed.get("visqol_second_environment_plan_frozen_before_scores") is not True:
        errors.append("ViSQOL second-environment plan must be frozen before scores")
    for key, binding in gate.get("bindings", {}).items():
        path = root / binding.get("path", "")
        if not path.is_file():
            errors.append(f"missing bound file {key}: {binding.get('path')}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"hash mismatch for bound file {key}: {binding.get('path')}")

    families = gate.get("metric_families", {})
    if set(families) != {"visqol_audio_v3_3_3", "gstpeaq_proxy_v0_6_1"}:
        errors.append("exactly the two preregistered metric families are required")
    for family_id, family in families.items():
        if family.get("execution_authorized") is not False:
            errors.append(f"{family_id}.execution_authorized must remain false")
    visqol = families.get("visqol_audio_v3_3_3", {})
    if visqol.get("build_recipe_frozen") is not True:
        errors.append("visqol_audio_v3_3_3.build_recipe_frozen must be true")
    if visqol.get("model_sha256") != "1e8246ed33bf36dc5c859351f7110f2cd31f98661989715c0fcf974ec48d3e2e":
        errors.append("visqol_audio_v3_3_3.model_sha256 differs")
    if visqol.get("binary_sha256") != "7384c8d21725e6fa3921aea4e66ff9cb9481b57acef868304192df437a467319":
        errors.append("visqol_audio_v3_3_3.binary_sha256 differs")
    if visqol.get("synthetic_fixture_execution_authorized") is not True:
        errors.append("visqol_audio_v3_3_3 exact second synthetic execution must be authorized")
    if visqol.get("synthetic_replay_complete") is not True:
        errors.append("visqol_audio_v3_3_3.synthetic_replay_complete must be true")
    if visqol.get("second_environment_synthetic_replay_complete") is not False:
        errors.append("visqol_audio_v3_3_3 second-environment replay must remain incomplete")
    second = gate.get("second_environment_execution", {})
    if second.get("metric_family") != "visqol_audio_v3_3_3":
        errors.append("second environment must be limited to ViSQOL")
    if second.get("environment_id") != "ubuntu24-gcc13-python312-v1":
        errors.append("second environment identifier differs")
    if second.get("synthetic_fixture_execution_authorized") is not True:
        errors.append("second-environment synthetic fixture execution must be authorized")
    for key in (
        "public_or_retained_audio_execution_authorized",
        "human_listening_score_access_authorized",
        "provider_audio_download_authorized",
        "execution_complete",
    ):
        if second.get(key) is not False:
            errors.append(f"second_environment_execution.{key} must remain false")
    if second.get("ephemeral_remote_execution_only") is not True:
        errors.append("second-environment execution must remain ephemeral remote only")
    if second.get("maximum_workers") != 6:
        errors.append("second-environment worker ceiling must equal six")
    if second.get("minimum_local_free_disk_gib") != 15:
        errors.append("second-environment disk reserve must equal 15 GiB")
    if second.get("score_blind_before_execution") is not True:
        errors.append("second-environment execution must remain score-blind")
    proxy = families.get("gstpeaq_proxy_v0_6_1", {})
    if proxy.get("binary_sha256") is not None:
        errors.append("gstpeaq_proxy_v0_6_1.binary_sha256 must remain null")
    if proxy.get("synthetic_fixture_execution_authorized") is not False:
        errors.append("gstpeaq_proxy_v0_6_1 synthetic fixture execution must remain unauthorized")
    for key in (
        "upstream_conforms_to_itu_tolerance",
        "itu_technology_consent_or_licence_cleared",
        "research_use_legal_record_present",
        "redistribution_boundary_approved",
    ):
        if proxy.get(key) is not False:
            errors.append(f"gstpeaq_proxy_v0_6_1.{key} must remain false")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gate", nargs="?", type=Path, default=DEFAULT_GATE)
    args = parser.parse_args()
    gate_path = args.gate.resolve()
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    errors = validate(gate)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print(
        json.dumps(
            {
                "gate": str(gate_path.relative_to(ROOT)),
                "gate_sha256": sha256_file(gate_path),
                "status": "blocked_as_required",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
