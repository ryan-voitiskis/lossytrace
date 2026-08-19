#!/usr/bin/env python3
"""Replay the bounded sparse non-tonal metadata-search v3 result."""

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
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-metadata-search-v3-plan.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v3-20260819-001.json"
PLAN_ID = "perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v3-20260819-001"
REPORT_ID = PLAN_ID
EXACT_HEAD_COMMIT = "eaa1a220708a3f2a217285c926bda1a59da0e61a"
EXACT_HEAD_CI_URL = "https://github.com/ryan-voitiskis/lossytrace/actions/runs/32215055528"

PRIMARY_RECORD_ATTEMPTS: list[dict[str, Any]] = [
    {
        "exact_member_id": "freesound_sound_734657",
        "provider_record_url": "https://freesound.org/people/logancircle2/sounds/734657/",
        "fetch_outcome": "inspected_text_html",
        "source_line_count": 147,
        "rejection_reasons": ["duration_below_minimum", "normalization_disclosed", "not_single_natural_transient"],
    },
    {
        "exact_member_id": "freesound_sound_734656",
        "provider_record_url": "https://freesound.org/people/logancircle2/sounds/734656/",
        "fetch_outcome": "timeout_no_primary_evidence",
        "rejection_reasons": ["primary_record_unavailable"],
    },
    {
        "exact_member_id": "freesound_sound_734653",
        "provider_record_url": "https://freesound.org/people/logancircle2/sounds/734653/",
        "fetch_outcome": "inspected_text_html",
        "source_line_count": 143,
        "rejection_reasons": ["duration_above_maximum", "normalization_disclosed", "not_single_natural_transient"],
    },
    {
        "exact_member_id": "freesound_sound_734658",
        "provider_record_url": "https://freesound.org/people/logancircle2/sounds/734658/",
        "fetch_outcome": "inspected_text_html",
        "source_line_count": 141,
        "rejection_reasons": ["normalization_disclosed", "not_single_natural_transient"],
    },
    {
        "exact_member_id": "freesound_sound_734654",
        "provider_record_url": "https://freesound.org/people/logancircle2/sounds/734654/",
        "fetch_outcome": "timeout_no_primary_evidence",
        "rejection_reasons": ["primary_record_unavailable"],
    },
    {
        "exact_member_id": "freesound_sound_734655",
        "provider_record_url": "https://freesound.org/people/logancircle2/sounds/734655/",
        "fetch_outcome": "timeout_no_primary_evidence",
        "rejection_reasons": ["primary_record_unavailable"],
    },
    {
        "exact_member_id": "freesound_sound_734651",
        "provider_record_url": "https://freesound.org/people/logancircle2/sounds/734651/",
        "fetch_outcome": "timeout_no_primary_evidence",
        "rejection_reasons": ["primary_record_unavailable"],
    },
    {
        "exact_member_id": "freesound_sound_463458",
        "provider_record_url": "https://freesound.org/people/sdotlyre/sounds/463458/",
        "fetch_outcome": "timeout_no_primary_evidence",
        "rejection_reasons": ["primary_record_unavailable"],
    },
    {
        "exact_member_id": "freesound_sound_463456",
        "provider_record_url": "https://freesound.org/people/sdotlyre/sounds/463456/",
        "fetch_outcome": "timeout_no_primary_evidence",
        "rejection_reasons": ["primary_record_unavailable"],
    },
    {
        "exact_member_id": "freesound_sound_852111",
        "provider_record_url": "https://freesound.org/people/SiliconeSound/sounds/852111/",
        "fetch_outcome": "inspected_text_html",
        "source_line_count": 135,
        "rejection_reasons": [
            "duration_above_maximum",
            "licence_not_allowed",
            "not_single_natural_transient",
            "original_format_not_wav",
            "processing_disclosed",
        ],
    },
    {
        "exact_member_id": "freesound_sound_476736",
        "provider_record_url": "https://freesound.org/people/elmoustachio/sounds/476736/",
        "fetch_outcome": "inspected_text_html",
        "source_line_count": 182,
        "text_extraction_characters": 3892,
        "licence": "CC0 1.0",
        "capture_chain": "Zoom H6 recorder with its XY stereo capsule",
        "container_summary": "provider WAV; 48000 Hz; 24 bit; stereo; 26.745 seconds; 7.3 MB",
        "metadata_supports_single_broadband_natural_transient_with_context": True,
        "natural_waveform_intent": "one natural thunder clap with light-rain recording context",
        "provider_original_lossless_lineage": "provider record identifies the captured sound as a Wave original",
        "transformation_history": "none; provider record explicitly states no processing",
        "rejection_reasons": [],
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
    expected_ids = [
        "freesound_sound_734657",
        "freesound_sound_734656",
        "freesound_sound_734653",
        "freesound_sound_734658",
        "freesound_sound_734654",
        "freesound_sound_734655",
        "freesound_sound_734651",
        "freesound_sound_463458",
        "freesound_sound_463456",
        "freesound_sound_852111",
        "freesound_sound_476736",
    ]
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
        outcome = row.get("fetch_outcome")
        if outcome == "timeout_no_primary_evidence":
            if row.get("rejection_reasons") != ["primary_record_unavailable"]:
                errors.append(f"timeout evidence boundary differs: {row.get('exact_member_id')}")
            if set(row) != {"exact_member_id", "fetch_outcome", "provider_record_url", "rejection_reasons"}:
                errors.append(f"timeout row exposes unobserved metadata: {row.get('exact_member_id')}")
        elif outcome == "inspected_text_html":
            if not isinstance(row.get("source_line_count"), int) or row["source_line_count"] <= 0:
                errors.append(f"primary text line count differs: {row.get('exact_member_id')}")
        else:
            errors.append(f"fetch outcome differs: {row.get('exact_member_id')}")
    eligible = [row for row in PRIMARY_RECORD_ATTEMPTS if not row.get("rejection_reasons")]
    if len(eligible) != 1 or eligible[0].get("exact_member_id") != "freesound_sound_476736":
        errors.append("eligible exact member differs")
    candidate = eligible[0] if eligible else {}
    for key in (
        "capture_chain",
        "container_summary",
        "metadata_supports_single_broadband_natural_transient_with_context",
        "natural_waveform_intent",
        "provider_original_lossless_lineage",
        "transformation_history",
    ):
        if not candidate.get(key):
            errors.append(f"candidate prerequisite absent: {key}")
    if candidate.get("licence") != "CC0 1.0":
        errors.append("candidate licence differs")
    if not 0 < candidate.get("text_extraction_characters", 0) < plan["media_boundary"]["maximum_text_response_bytes"]:
        errors.append("candidate text response bound differs")
    return sorted(set(errors))


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    validator = _load_module(
        ROOT / "scripts/perceptual_degradation_source_trait_sparse_non_tonal_metadata_search_v3.py",
        "metadata_search_v3_plan",
    )
    errors = validator.validate_plan(plan) + validate_observations(plan)
    if errors:
        raise ValueError("; ".join(sorted(set(errors))))
    candidate = PRIMARY_RECORD_ATTEMPTS[-1]
    dispositions = []
    for row in PRIMARY_RECORD_ATTEMPTS:
        dispositions.append({
            "audio_accessed": False,
            "eligible_for_exact_member_checkpoint": not row["rejection_reasons"],
            "exact_member_id": row["exact_member_id"],
            "fetch_outcome": row["fetch_outcome"],
            "provider_id": "freesound",
            "provider_record_url": row["provider_record_url"],
            "rejection_reasons": row["rejection_reasons"],
        })
    return {
        "audio_accessed": False,
        "claim_boundary": plan["claim_boundary"],
        "decision": {
            "eligible_successor_count": 1,
            "metadata_nomination_is_descriptor_evidence": False,
            "metadata_nomination_is_source_trait_truth": False,
            "nominated_exact_member_id": candidate["exact_member_id"],
            "next_gate": "Freeze, validate, commit and pass exact-head CI for a one-member integer-PCM descriptor-confirmation checkpoint before acquiring the exact provider original.",
            "search_stopped_at_first_fully_eligible_member": True,
            "source_manifest_allocated": False,
            "source_trait_assigned": False,
            "thresholds_changed_after_observation": False,
        },
        "execution": {
            "candidate_detail_page_browser_rendered": False,
            "discovery_query_count_executed": 8,
            "discovery_query_transport_batch_retry_count": 1,
            "discovery_query_transport_request_count": 12,
            "discovery_scope_expanded_by_transport_retry": False,
            "distinct_primary_record_count_attempted": 11,
            "exact_head_ci_url": EXACT_HEAD_CI_URL,
            "exact_head_commit": EXACT_HEAD_COMMIT,
            "media_asset_request_count": 0,
            "primary_record_fetch_timeout_count": 6,
            "primary_record_request_attempt_count": 19,
            "primary_records_inspected_as_text_html": 5,
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
        "selected_candidate_metadata": {
            "attribution": "Sound 476736 by elmoustachio on Freesound.org, CC0 1.0",
            "capture_chain": candidate["capture_chain"],
            "container_summary": candidate["container_summary"],
            "exact_member_id": candidate["exact_member_id"],
            "licence": candidate["licence"],
            "metadata_supports_single_broadband_natural_transient_with_context": candidate[
                "metadata_supports_single_broadband_natural_transient_with_context"
            ],
            "natural_waveform_intent": candidate["natural_waveform_intent"],
            "provider_id": "freesound",
            "provider_original_lossless_lineage": candidate["provider_original_lossless_lineage"],
            "provider_record_url": candidate["provider_record_url"],
            "transformation_history": candidate["transformation_history"],
        },
        "state": "bounded_metadata_only_search_v3_stopped_after_one_eligible_exact_member_nomination",
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
