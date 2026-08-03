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
    if gate.get("state") != "metric_execution_blocked_pending_exact_binaries_and_legal_clearance":
        errors.append("metric gate must remain in its score-blind blocked state")
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
        if family.get("binary_sha256") is not None:
            errors.append(f"{family_id}.binary_sha256 must remain null until a new gate freeze")
    proxy = families.get("gstpeaq_proxy_v0_6_1", {})
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
