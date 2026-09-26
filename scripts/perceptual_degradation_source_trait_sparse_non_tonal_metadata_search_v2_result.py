#!/usr/bin/env python3
"""Replay the bounded sparse non-tonal metadata-search v2 result."""

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
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-metadata-search-v2-plan.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v2-20260819-001.json"
PLAN_ID = "perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v2-20260819-001"
REPORT_ID = PLAN_ID
EXACT_HEAD_COMMIT = "7a484a1cf05c7ad8763d8dd3b20bf741a5533e39"
EXACT_HEAD_CI_URL = "https://github.com/ryan-voitiskis/lossytrace/actions/runs/32208051970"

OBSERVED_RECORDS: list[dict[str, Any]] = [
    {
        "exact_member_id": "freesound_sound_845921",
        "provider_record_url": "https://freesound.org/people/inspire153/sounds/845921/",
        "licence": "CC BY 4.0",
        "text_response_bytes": 41251,
        "rejection_reasons": ["not_single_natural_transient"],
    },
    {
        "exact_member_id": "freesound_sound_543775",
        "provider_record_url": "https://freesound.org/people/walthamstow_walker/sounds/543775/",
        "licence": "CC0 1.0",
        "text_response_bytes": 43992,
        "rejection_reasons": ["normalization_disclosed", "multiple_natural_events"],
    },
    {
        "exact_member_id": "freesound_sound_193044",
        "provider_record_url": "https://freesound.org/people/lossfound/sounds/193044/",
        "licence": "CC0 1.0",
        "text_response_bytes": 38955,
        "rejection_reasons": ["normalization_disclosed", "processed_and_multiple_snippets_disclosed"],
    },
    {
        "exact_member_id": "freesound_sound_345762",
        "provider_record_url": "https://freesound.org/people/djtiii/sounds/345762/",
        "licence": "CC BY 3.0",
        "text_response_bytes": 36224,
        "rejection_reasons": ["licence_not_allowed", "normalization_disclosed", "not_single_natural_transient"],
    },
    {
        "exact_member_id": "freesound_sound_240344",
        "provider_record_url": "https://freesound.org/people/klankbeeld/sounds/240344/",
        "licence": "CC BY 4.0",
        "text_response_bytes": 50585,
        "rejection_reasons": ["explicit_transformation_history_absent"],
    },
    {
        "exact_member_id": "freesound_sound_151320",
        "provider_record_url": "https://freesound.org/people/cgrote/sounds/151320/",
        "licence": "CC BY 4.0",
        "text_response_bytes": 42882,
        "rejection_reasons": ["not_single_natural_transient"],
    },
    {
        "exact_member_id": "freesound_sound_23040",
        "provider_record_url": "https://freesound.org/people/pcaeldries/sounds/23040/",
        "licence": "CC BY 4.0",
        "text_response_bytes": 44130,
        "rejection_reasons": ["not_single_natural_transient"],
    },
    {
        "exact_member_id": "freesound_sound_367702",
        "provider_record_url": "https://freesound.org/people/BlueDelta/sounds/367702/",
        "licence": "CC0 1.0",
        "text_response_bytes": 47889,
        "rejection_reasons": ["capture_chain_absent", "explicit_transformation_history_absent"],
    },
    {
        "exact_member_id": "freesound_sound_703342",
        "provider_record_url": "https://freesound.org/people/AnthonyChan0/sounds/703342/",
        "licence": "CC0 1.0",
        "text_response_bytes": 41785,
        "capture_chain": "dual Shure SM58 microphones in stereo into a Zoom F3 recorder",
        "container_summary": "provider WAV; 192000 Hz; 32-bit float; stereo; 11.802 seconds",
        "metadata_supports_single_natural_transient": True,
        "natural_waveform_intent": "one 9 mm pistol round; record explicitly says the sound is not assembled",
        "provider_original_lossless_lineage": "provider record identifies 32-bit-float stereo gunfire and a Wave original",
        "transformation_history": "none; provider title explicitly says no processing and describes the recording as it came",
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
        "freesound_sound_845921",
        "freesound_sound_543775",
        "freesound_sound_193044",
        "freesound_sound_345762",
        "freesound_sound_240344",
        "freesound_sound_151320",
        "freesound_sound_23040",
        "freesound_sound_367702",
        "freesound_sound_703342",
    ]
    observed_ids = [row.get("exact_member_id") for row in OBSERVED_RECORDS]
    if observed_ids != expected_ids:
        errors.append("primary record order differs")
    if len(OBSERVED_RECORDS) > plan["search_protocol"]["exact_primary_record_count_maximum"]:
        errors.append("primary record cap exceeded")
    excluded = set(plan["candidate_eligibility"]["excluded_exact_member_ids"])
    if excluded.intersection(observed_ids):
        errors.append("consumed exact member was reinspected")
    maximum_bytes = plan["media_boundary"]["maximum_text_response_bytes"]
    for row in OBSERVED_RECORDS:
        parsed = urlparse(str(row.get("provider_record_url", "")))
        sound_id = str(row.get("exact_member_id", "")).rsplit("_", 1)[-1]
        if parsed.scheme != "https" or parsed.netloc != "freesound.org" or f"/sounds/{sound_id}/" not in parsed.path:
            errors.append(f"provider URL differs: {row.get('exact_member_id')}")
        if not 0 < row.get("text_response_bytes", 0) <= maximum_bytes:
            errors.append(f"text response bound differs: {row.get('exact_member_id')}")
    eligible = [row for row in OBSERVED_RECORDS if not row.get("rejection_reasons")]
    if len(eligible) != 1 or eligible[0].get("exact_member_id") != "freesound_sound_703342":
        errors.append("eligible exact member differs")
    candidate = eligible[0] if eligible else {}
    for key in (
        "capture_chain",
        "container_summary",
        "metadata_supports_single_natural_transient",
        "natural_waveform_intent",
        "provider_original_lossless_lineage",
        "transformation_history",
    ):
        if not candidate.get(key):
            errors.append(f"candidate prerequisite absent: {key}")
    if candidate.get("licence") != "CC0 1.0":
        errors.append("candidate licence differs")
    return sorted(set(errors))


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH) -> dict[str, Any]:
    validator = _load_module(
        ROOT / "scripts/perceptual_degradation_source_trait_sparse_non_tonal_metadata_search_v2.py",
        "metadata_search_v2_plan",
    )
    plan_errors = validator.validate_plan(plan)
    errors = plan_errors + validate_observations(plan)
    if errors:
        raise ValueError("; ".join(sorted(set(errors))))
    candidate = OBSERVED_RECORDS[-1]
    dispositions = []
    for row in OBSERVED_RECORDS:
        disposition = {
            "audio_accessed": False,
            "eligible_for_exact_member_checkpoint": not row["rejection_reasons"],
            "exact_member_id": row["exact_member_id"],
            "licence": row["licence"],
            "provider_id": "freesound",
            "provider_record_url": row["provider_record_url"],
            "rejection_reasons": row["rejection_reasons"],
        }
        dispositions.append(disposition)
    return {
        "audio_accessed": False,
        "claim_boundary": plan["claim_boundary"],
        "decision": {
            "eligible_successor_count": 1,
            "metadata_nomination_is_descriptor_evidence": False,
            "metadata_nomination_is_source_trait_truth": False,
            "nominated_exact_member_id": candidate["exact_member_id"],
            "next_gate": "Freeze, validate, commit and pass exact-head CI for a one-member descriptor-confirmation checkpoint before acquiring the exact provider original.",
            "search_stopped_at_first_fully_eligible_member": True,
            "source_manifest_allocated": False,
            "source_trait_assigned": False,
            "thresholds_changed_after_observation": False,
        },
        "execution": {
            "candidate_detail_page_browser_rendered": False,
            "discovery_query_count_executed": 4,
            "discovery_query_count_not_executed_after_stop": 4,
            "exact_head_ci_url": EXACT_HEAD_CI_URL,
            "exact_head_commit": EXACT_HEAD_COMMIT,
            "freesound_authenticated_chrome_session_verified": True,
            "media_asset_request_count": 0,
            "primary_record_count_inspected": len(OBSERVED_RECORDS),
            "primary_records_retrieved_as_text_html": True,
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
            "attribution": "Sound 703342 by AnthonyChan0 on Freesound.org, CC0 1.0",
            "capture_chain": candidate["capture_chain"],
            "container_summary": candidate["container_summary"],
            "exact_member_id": candidate["exact_member_id"],
            "licence": candidate["licence"],
            "metadata_supports_single_natural_transient": candidate["metadata_supports_single_natural_transient"],
            "natural_waveform_intent": candidate["natural_waveform_intent"],
            "provider_id": "freesound",
            "provider_original_lossless_lineage": candidate["provider_original_lossless_lineage"],
            "provider_record_url": candidate["provider_record_url"],
            "transformation_history": candidate["transformation_history"],
        },
        "state": "bounded_metadata_only_search_stopped_after_one_eligible_exact_member_nomination",
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
