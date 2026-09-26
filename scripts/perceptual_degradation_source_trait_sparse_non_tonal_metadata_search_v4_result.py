#!/usr/bin/env python3
"""Replay the bounded sparse non-tonal metadata-search v4 result."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-metadata-search-v4-plan.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v4-20260819-001.json"
PLAN_ID = "perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v4-20260819-001"
REPORT_ID = PLAN_ID
EXACT_HEAD_COMMIT = "06b40720a0bd3221f3adf681ee5679438a6e6eb5"
EXACT_HEAD_CI_URL = "https://github.com/ryan-voitiskis/lossytrace/actions/runs/32220447972"

PRIMARY_RECORD_ATTEMPTS: list[dict[str, Any]] = [
    {
        "exact_member_id": "freesound_sound_9679",
        "provider_record_url": "https://freesound.org/people/dobroide/sounds/9679/",
        "fetch_outcome": "inspected_text_html",
        "source_line_count": 157,
        "rejection_reasons": [
            "capture_chain_absent",
            "duration_below_minimum",
            "original_format_not_wav",
            "quiet_context_before_and_after_absent",
            "transformation_history_absent",
        ],
    },
    {
        "exact_member_id": "freesound_sound_9677",
        "provider_record_url": "https://freesound.org/people/dobroide/sounds/9677/",
        "fetch_outcome": "inspected_text_html",
        "source_line_count": 134,
        "rejection_reasons": [
            "capture_chain_absent",
            "duration_below_minimum",
            "original_format_not_wav",
            "quiet_context_before_and_after_absent",
            "transformation_history_absent",
        ],
    },
    {
        "exact_member_id": "freesound_sound_826162",
        "provider_record_url": "https://freesound.org/people/qubodup/sounds/826162/",
        "fetch_outcome": "inspected_text_html",
        "source_line_count": 161,
        "rejection_reasons": [
            "capture_chain_absent",
            "disallowed_transformations_disclosed",
            "duration_below_minimum",
            "not_natural_recorded_waveform",
            "quiet_context_before_and_after_absent",
            "rendered_or_synthesized_sound_design",
        ],
    },
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


def validate_observations(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_ids = ["freesound_sound_9679", "freesound_sound_9677", "freesound_sound_826162"]
    observed_ids = [row.get("exact_member_id") for row in PRIMARY_RECORD_ATTEMPTS]
    if observed_ids != expected_ids:
        errors.append("primary record attempt order differs")
    if len(PRIMARY_RECORD_ATTEMPTS) > plan["search_protocol"]["exact_primary_record_count_maximum"]:
        errors.append("distinct primary record cap exceeded")
    excluded = set(plan["candidate_eligibility"]["excluded_exact_member_ids"])
    if excluded.intersection(observed_ids):
        errors.append("consumed exact member was reinspected")
    for row in PRIMARY_RECORD_ATTEMPTS:
        parsed = urlparse(str(row.get("provider_record_url", "")))
        sound_id = str(row.get("exact_member_id", "")).rsplit("_", 1)[-1]
        if parsed.scheme != "https" or parsed.netloc != "freesound.org" or f"/sounds/{sound_id}/" not in parsed.path:
            errors.append(f"provider URL differs: {row.get('exact_member_id')}")
        if row.get("fetch_outcome") != "inspected_text_html":
            errors.append(f"fetch outcome differs: {row.get('exact_member_id')}")
        if not isinstance(row.get("source_line_count"), int) or row["source_line_count"] <= 0:
            errors.append(f"primary text line count differs: {row.get('exact_member_id')}")
        reasons = row.get("rejection_reasons")
        if not isinstance(reasons, list) or not reasons or reasons != sorted(set(reasons)):
            errors.append(f"rejection inventory differs: {row.get('exact_member_id')}")
    if any(not row["rejection_reasons"] for row in PRIMARY_RECORD_ATTEMPTS):
        errors.append("unexpected eligible exact member")
    return sorted(set(errors))


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    validator = _load_module(
        ROOT / "scripts/perceptual_degradation_source_trait_sparse_non_tonal_metadata_search_v4.py",
        "metadata_search_v4_plan",
    )
    errors = validator.validate_plan(plan) + validate_observations(plan)
    if errors:
        raise ValueError("; ".join(sorted(set(errors))))
    dispositions = [
        {
            "audio_accessed": False,
            "eligible_for_exact_member_checkpoint": False,
            "exact_member_id": row["exact_member_id"],
            "fetch_outcome": row["fetch_outcome"],
            "provider_id": "freesound",
            "provider_record_url": row["provider_record_url"],
            "rejection_reasons": row["rejection_reasons"],
        }
        for row in PRIMARY_RECORD_ATTEMPTS
    ]
    return {
        "audio_accessed": False,
        "claim_boundary": plan["claim_boundary"],
        "decision": {
            "bounded_negative_preserved": True,
            "eligible_successor_count": 0,
            "metadata_nomination_is_descriptor_evidence": False,
            "metadata_nomination_is_source_trait_truth": False,
            "next_gate": "Reconcile this bounded negative in the objective audit before selecting a materially different source route; do not repeat the same metadata search or access candidate audio.",
            "nominated_exact_member_id": None,
            "search_exhausted_without_eligible_member": True,
            "source_manifest_allocated": False,
            "source_trait_assigned": False,
            "thresholds_changed_after_observation": False,
        },
        "execution": {
            "candidate_detail_page_browser_rendered": False,
            "discovery_query_batch_count": 2,
            "discovery_query_count_executed": 8,
            "discovery_query_transport_batch_retry_count": 0,
            "discovery_query_transport_request_count": 8,
            "distinct_primary_record_count_attempted": 3,
            "exact_head_ci_url": EXACT_HEAD_CI_URL,
            "exact_head_commit": EXACT_HEAD_COMMIT,
            "media_asset_request_count": 0,
            "primary_record_fetch_timeout_count": 0,
            "primary_record_request_attempt_count": 3,
            "primary_records_inspected_as_text_html": 3,
            "preview_or_waveform_accessed": False,
            "response_bodies_retained": False,
        },
        "implementation_sha256": sha256_file(Path(__file__)),
        "observed_on": "2026-08-19",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "record_dispositions": dispositions,
        "report_id": REPORT_ID,
        "schema_version": 1,
        "state": "bounded_metadata_only_search_v4_exhausted_without_eligible_exact_member",
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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
