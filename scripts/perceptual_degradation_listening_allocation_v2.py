#!/usr/bin/env python3
"""Allocate v2 listening manifests without assigning transparency truth."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
V1_PATH = SCRIPT_DIR / "perceptual_degradation_listening_allocation.py"
SPEC = importlib.util.spec_from_file_location("listening_allocation_v1", V1_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load v1 listening allocator")
V1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V1)


def _as_v1(manifest: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(manifest)
    value["schema_version"] = 1
    for stimulus in value.get("stimuli", []):
        if stimulus.get("condition_class") == "transparency_candidate":
            stimulus["condition_class"] = "transparent_codec"
    return value


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 2:
        errors.append("schema_version must equal 2")
    for stimulus in manifest.get("stimuli", []):
        if stimulus.get("condition_class") == "transparent_codec":
            errors.append(
                f"{stimulus.get('stimulus_id', '<missing>')}: v2 requires transparency_candidate"
            )
    if errors:
        return errors
    return V1.validate_manifest(_as_v1(manifest))


def allocate(
    manifest: dict[str, Any],
    participant_key: str,
    allocation_seed: str,
    allocation_index: int = 0,
) -> dict[str, Any]:
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    result = V1.allocate(
        _as_v1(manifest), participant_key, allocation_seed, allocation_index
    )
    result["schema_version"] = 2
    result["manifest_schema_version"] = 2
    return result


def audit_balance(
    manifest: dict[str, Any], participant_count: int, allocation_seed: str
) -> dict[str, Any]:
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    result = V1.audit_balance(_as_v1(manifest), participant_count, allocation_seed)
    result["schema_version"] = 2
    result["manifest_schema_version"] = 2
    return result


def serialize_assignment(result: dict[str, Any], output_format: str) -> str:
    return V1.serialize_assignment(result, output_format)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--participant-key", required=True)
    parser.add_argument("--allocation-index", type=int, required=True)
    parser.add_argument("--allocation-seed", required=True)
    parser.add_argument("--format", choices=("json", "javascript"), default="json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = allocate(
        manifest,
        args.participant_key,
        args.allocation_seed,
        args.allocation_index,
    )
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit(f"refusing to replace output: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialize_assignment(result, args.format), encoding="utf-8")
    print(
        json.dumps(
            {"assignment_id": result["assignment_id"], "status": result["state"]},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
