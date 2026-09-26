#!/usr/bin/env python3
"""Replay metadata-only sparse/tonal exact-member selection."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/perceptual-degradation-v1/source-trait-sparse-tonal-exact-member-selection-plan.json"
REPORT_PATH = ROOT / "research/toolchains/evidence/perceptual-degradation-source-trait-sparse-tonal-exact-member-selection-20260818-001.json"
PLAN_ID = "perceptual-degradation-source-trait-sparse-tonal-exact-member-selection-20260818-001"
REPORT_ID = PLAN_ID


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def select_tinysol(rows: Iterable[dict[str, str]], plan: dict[str, Any]) -> dict[str, str]:
    selection = plan["tinysol_selection"]
    rule = selection["candidate_filter"]
    candidates = [
        row for row in rows
        if row["Instrument (abbr.)"] == rule["instrument_abbreviation"]
        and row["Technique (abbr.)"] == rule["technique_abbreviation"]
        and row["Dynamics"] == rule["dynamics"]
        and row["Instance ID"] == rule["instance_id"]
        and row["Needed digital retuning"] == rule["needed_digital_retuning"]
        and rule["pitch_id_inclusive_minimum"] <= int(row["Pitch ID"]) <= rule["pitch_id_inclusive_maximum"]
        and "_R" not in row["Path"] and "-R" not in row["Path"]
    ]
    if len(candidates) != selection["candidate_row_count"]:
        raise ValueError("TinySOL candidate count differs")
    seed = selection["rank_seed"] + "\0"
    ranked = sorted((hashlib.sha256((seed + row["Path"]).encode()).hexdigest(), row) for row in candidates)
    digest, selected = ranked[0]
    if digest != selection["selected_rank_sha256"] or selected["Path"] != selection["selected_metadata_path"]:
        raise ValueError("TinySOL selected member differs")
    return selected


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("plan_id") != PLAN_ID:
        errors.append("plan identity differs")
    if plan.get("state") != "metadata_only_sparse_tonal_exact_member_selection_frozen_before_audio_access":
        errors.append("plan state differs")
    for binding_id, binding in plan.get("bindings", {}).items():
        path = ROOT / binding.get("path", "")
        if not path.is_file() or sha256_file(path) != binding.get("sha256"):
            errors.append(f"binding differs: {binding_id}")
    authorization = plan.get("authorization", {})
    for key, value in authorization.items():
        expected = key in {"exact_member_metadata_selection_authorized", "public_and_provider_metadata_read_authorized"}
        if value is not expected:
            errors.append(f"authorization differs: {key}")
    if plan.get("resources") != {"maximum_workers": 1, "minimum_free_disk_gib": 15, "new_audio_download_bytes": 0}:
        errors.append("resource boundary differs")
    candidate = plan.get("freesound_candidate", {})
    if candidate.get("exact_member_id") != "freesound_sound_856645" or candidate.get("licence") != "CC0 1.0" or candidate.get("transformation_history") != "no_processing_done":
        errors.append("Freesound candidate boundary differs")
    claims = plan.get("claim_boundary", {})
    if not claims or any(value is not False for value in claims.values()):
        errors.append("claim boundary must remain false")
    return sorted(set(errors))


def build_report(plan: dict[str, Any], plan_path: Path = PLAN_PATH, metadata_path: Path | None = None) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    replayed = False
    if metadata_path is not None:
        with metadata_path.open(newline="", encoding="utf-8-sig") as handle:
            select_tinysol(csv.DictReader(handle), plan)
        replayed = True
    return {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "state": "two_sparse_tonal_exact_metadata_candidates_selected_audio_access_closed",
        "observed_on": "2026-08-18",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "access_boundary": {
            "public_and_provider_metadata_read": True,
            "private_tinysol_metadata_selection_replayed": replayed,
            "audio_samples_read": False,
            "audio_downloaded": False,
            "audio_descriptors_computed": False,
            "provider_scores_or_processed_conditions_accessed": False,
            "source_traits_assigned": False,
            "source_manifest_allocated": False,
            "public_verdict_enabled": False,
        },
        "selected_candidates": [
            {
                "trait_contrast": "sparse_non_tonal",
                "exact_member_id": plan["freesound_candidate"]["exact_member_id"],
                "provider_id": "freesound",
                "licence": plan["freesound_candidate"]["licence"],
                "original_lossless_upload_supported": True,
                "capture_and_transformation_record_supported": True,
                "descriptor_confirmation_complete": False,
                "trait_assigned": False,
            },
            {
                "trait_contrast": "tonal_non_sparse",
                "exact_member_id": plan["tinysol_selection"]["selected_exact_member_id"],
                "provider_id": "tinysol_6_0",
                "licence": plan["tinysol_selection"]["licence"],
                "non_retuned_distributed_wav_supported": True,
                "deterministic_metadata_selection_replayed": replayed,
                "descriptor_confirmation_complete": False,
                "trait_assigned": False,
            },
        ],
        "decision": {
            "exact_metadata_candidate_count": 2,
            "sparse_non_tonal_candidate_selected": True,
            "tonal_non_sparse_candidate_selected": True,
            "audio_accessed": False,
            "descriptor_confirmation_complete": False,
            "source_trait_assignment_complete": False,
            "source_trait_manifest_frozen": False,
            "next_gate": "Acquire only the selected Freesound provider original and project only the selected TinySOL archive member into memory, then run the already-frozen sparse/tonal descriptor twice without retaining derived PCM. Preserve attribution and relationship groups; do not allocate a manifest until the descriptor and assignment gates pass.",
            "public_verdict_enabled": False,
        },
        "claim_boundary": plan["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    parser.add_argument("--tinysol-metadata", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report(load_json(args.plan), args.plan, args.tinysol_metadata)
    payload = canonical_json_bytes(report)
    if args.check:
        committed = load_json(args.output)
        expected = json.loads(payload)
        expected["access_boundary"]["private_tinysol_metadata_selection_replayed"] = committed["access_boundary"]["private_tinysol_metadata_selection_replayed"]
        expected["selected_candidates"][1]["deterministic_metadata_selection_replayed"] = committed["selected_candidates"][1]["deterministic_metadata_selection_replayed"]
        if committed != expected:
            print("ERROR: committed report differs")
            return 1
        print(f"validated {REPORT_ID}")
        return 0
    args.output.write_bytes(payload)
    print(f"wrote {REPORT_ID} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
