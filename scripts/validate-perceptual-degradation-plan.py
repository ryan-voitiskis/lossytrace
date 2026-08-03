#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "benchmarks" / "perceptual-degradation-v1" / "research-plan.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    if plan.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if plan.get("state") != "contract_frozen_before_metric_execution":
        errors.append("plan must remain frozen before metric execution")

    public = plan.get("public_state", {})
    if public.get("evidence_schema_version") != 1:
        errors.append("public evidence schema must remain 1")
    if public.get("measurement_feature_version") != 0:
        errors.append("public measurement feature version must remain 0")
    if public.get("public_verdict_enabled") is not False:
        errors.append("public verdict must remain disabled")
    if public.get("reklawdbox_in_scope") is not False:
        errors.append("Reklawdbox must remain out of scope")

    access = plan.get("score_access", {})
    prohibited_true = (
        "retained_waveform_metric_execution",
        "retained_metric_scores_opened",
        "sealed_labels_opened",
        "existing_280_case_future_subset_opened",
    )
    for key in prohibited_true:
        if access.get(key) is not False:
            errors.append(f"score_access.{key} must be false")

    families = plan.get("primary_metric_families", [])
    if plan.get("metric_family_limit") != 2 or len(families) != 2:
        errors.append("exactly two primary metric families must be frozen")
    family_ids = {family.get("family_id") for family in families}
    if family_ids != {"visqol_audio_v3_3_3", "gstpeaq_proxy_v0_6_1"}:
        errors.append("unexpected primary metric family binding")
    for family in families:
        commit = family.get("git_commit", "")
        if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
            errors.append(f"invalid commit binding for {family.get('family_id')}")
    proxy = next((item for item in families if item.get("family_id") == "gstpeaq_proxy_v0_6_1"), {})
    if proxy.get("legal_gate_required") is not True:
        errors.append("GstPEAQ proxy legal gate must be required")
    if proxy.get("public_name_forbidden") != "peaq":
        errors.append("standardized PEAQ public name must remain forbidden")

    if plan.get("human_truth", {}).get("main_collection_authorized") is not False:
        errors.append("main human collection must remain unauthorized")
    if plan.get("no_reference", {}).get("eligible_before_full_reference_pass") is not False:
        errors.append("no-reference work must remain gated by full-reference success")

    axes = set(plan.get("grouping", {}).get("required_holdout_axes", []))
    if axes != {"source", "domain", "codec", "encoder"}:
        errors.append("all four grouped holdout axes are required")
    negatives = set(plan.get("required_negative_classes", []))
    if "transparent_lossy_encode" not in negatives:
        errors.append("transparent lossy encodes must remain negative controls")

    resources = plan.get("resources", {})
    if resources.get("sustained_worker_limit", 99) > 6:
        errors.append("sustained worker limit must not exceed 6")
    if resources.get("minimum_free_disk_gib", 0) < 15:
        errors.append("minimum free disk reserve must be at least 15 GiB")
    if resources.get("duplicate_corpus_forbidden") is not True:
        errors.append("duplicate corpus must remain forbidden")

    for key, binding in plan.get("bindings", {}).items():
        relative = binding.get("path", "")
        expected_sha256 = binding.get("sha256", "")
        path = root / relative
        if not path.is_file():
            errors.append(f"missing bound file {key}: {relative}")
        elif sha256_file(path) != expected_sha256:
            errors.append(f"hash mismatch for bound file {key}: {relative}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", nargs="?", type=Path, default=DEFAULT_PLAN)
    args = parser.parse_args()
    plan_path = args.plan.resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    errors = validate(plan)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print(
        json.dumps(
            {
                "plan": str(plan_path.relative_to(ROOT)),
                "plan_sha256": sha256_file(plan_path),
                "status": "valid",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
