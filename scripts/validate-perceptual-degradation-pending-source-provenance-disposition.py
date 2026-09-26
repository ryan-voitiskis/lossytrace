#!/usr/bin/env python3
"""Validate the score-blind MusicNet/FSD50K provenance disposition."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DISPOSITION = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "pending-source-provenance-disposition.json"
)
DISPOSITION_ID = (
    "perceptual-degradation-pending-source-provenance-disposition-20260814-001"
)
OBSERVATION_ID = (
    "perceptual-degradation-pending-source-public-provenance-observation-20260814-001"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(disposition: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if (
        disposition.get("schema_version") != 1
        or disposition.get("disposition_id") != DISPOSITION_ID
    ):
        errors.append("disposition identity differs")
    if disposition.get("state") != (
        "musicnet_and_fsd50k_rejected_for_truth_bearing_clean_reference_public_record_insufficient"
    ):
        errors.append("disposition state differs")

    bound: dict[str, dict[str, Any]] = {}
    for binding_id, binding in disposition.get("bindings", {}).items():
        path = root / str(binding.get("path", ""))
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")
        elif path.suffix == ".json":
            bound[binding_id] = load_json(path)

    observation = bound.get("public_provenance_observation", {})
    if observation.get("observation_id") != OBSERVATION_ID:
        errors.append("public provenance observation identity differs")

    candidate_plan = bound.get("candidate_plan", {})
    pending = next(
        (
            tier
            for tier in candidate_plan.get("candidate_tiers", [])
            if tier.get("tier_id") == "upstream_or_clip_origin_pending"
        ),
        {},
    )
    if pending.get("source_ids") != [
        "musicnet_5120004",
        "fsd50k_4060432_allowed_items",
    ]:
        errors.append("predecessor pending candidate set differs")
    if pending.get("qualified_reference_group_count") != 0:
        errors.append("predecessor pending candidates were already qualified")

    allocation = bound.get("provider_allocation_report", {})
    pending_scenario = next(
        (
            scenario
            for scenario in allocation.get("scenario_results", [])
            if scenario.get("scenario_id")
            == "add_all_pending_final_three_domain_minimum"
        ),
        {},
    )
    if (
        pending_scenario.get("arithmetic_feasible") is not True
        or pending_scenario.get("scientifically_eligible") is not False
    ):
        errors.append("predecessor pending allocation boundary differs")
    if allocation.get("decision", {}).get("no_reference_work_eligible") is not False:
        errors.append("predecessor no-reference gate is not closed")

    completion = bound.get("objective_completion_audit", {})
    if completion.get("summary", {}).get("objective_complete") is not False:
        errors.append("source disposition cannot follow a completed objective")

    expected_access = {
        "official_public_metadata_read": True,
        "new_audio_acquisition_authorized": False,
        "audio_member_access_authorized": False,
        "exact_member_selection_authorized": False,
        "retained_odaq_reference_read_authorized": False,
        "retained_reference_projection_authorized": False,
        "processed_condition_access_authorized": False,
        "perceptual_metric_execution_authorized": False,
        "metric_score_access_authorized": False,
        "listening_score_access_authorized": False,
        "human_collection_authorized": False,
        "recruitment_authorized": False,
        "sealed_evidence_access_authorized": False,
        "no_reference_training_authorized": False,
        "public_verdict_enabled": False,
    }
    if disposition.get("access_boundary") != expected_access:
        errors.append("access boundary differs")

    observation_access = observation.get("access_boundary", {})
    for key in (
        "official_public_dataset_pages_read",
        "official_public_papers_read",
        "small_public_metadata_files_streamed_or_read_ephemerally",
    ):
        if observation_access.get(key) is not True:
            errors.append(f"authorized public observation must remain true: {key}")
    for key in (
        "raw_metadata_persisted_in_research_storage",
        "audio_archive_downloaded",
        "audio_member_accessed",
        "exact_source_member_selected",
        "retained_odaq_reference_accessed",
        "processed_odaq_condition_accessed",
        "perceptual_metric_executed",
        "metric_score_accessed",
        "listening_score_accessed",
        "sealed_evidence_opened",
        "no_reference_training_performed",
        "public_verdict_enabled",
    ):
        if observation_access.get(key) is not False:
            errors.append(f"observation boundary must remain false: {key}")

    musicnet = observation.get("musicnet", {})
    musicnet_metadata = musicnet.get("metadata_file", {})
    if (
        musicnet.get("source_id") != "musicnet_5120004"
        or musicnet.get("record_count") != 330
        or musicnet_metadata.get("bytes") != 43775
        or musicnet_metadata.get("md5")
        != "1caef62cee9c875235e62aac368b49d8"
        or musicnet_metadata.get("sha256")
        != "1308d938bafb594e3b0471f2bdda3630da352f881857f265f92114cf398de7ca"
    ):
        errors.append("MusicNet public metadata binding differs")
    musicnet_findings = musicnet.get("public_record_findings", {})
    for key in (
        "original_acquisition_container_field_present",
        "original_acquisition_codec_field_present",
        "complete_transformation_chain_from_recording_to_delivered_pcm_documented_for_every_track",
        "absence_of_prior_lossy_coding_established_for_every_track",
    ):
        if musicnet_findings.get(key) is not False:
            errors.append(f"MusicNet provenance limit must remain false: {key}")

    fsd50k = observation.get("fsd50k", {})
    fsd50k_metadata = fsd50k.get("metadata_file", {})
    if (
        fsd50k.get("source_id") != "fsd50k_4060432_allowed_items"
        or fsd50k.get("record_count") != 51197
        or fsd50k_metadata.get("bytes") != 6700838
        or fsd50k_metadata.get("md5")
        != "b9ea0c829a411c1d42adb9da539ed237"
        or fsd50k_metadata.get("sha256")
        != "9a738e032546f9a2c6e3d04566928d04a65fb79b422cc9d78bb781723537bd19"
        or fsd50k_metadata.get("development_record_count") != 40966
        or fsd50k_metadata.get("evaluation_record_count") != 10231
    ):
        errors.append("FSD50K public metadata binding differs")
    if fsd50k_metadata.get("fields_present_for_every_clip") != [
        "description",
        "license",
        "tags",
        "title",
        "uploader",
    ]:
        errors.append("FSD50K released clip metadata fields differ")
    fsd50k_findings = fsd50k.get("public_record_findings", {})
    for key in (
        "original_upload_container_field_present_in_released_clip_metadata",
        "original_upload_codec_field_present_in_released_clip_metadata",
        "complete_transformation_chain_from_capture_to_delivered_pcm_documented_for_every_clip",
        "absence_of_prior_lossy_coding_established_for_every_clip",
    ):
        if fsd50k_findings.get(key) is not False:
            errors.append(f"FSD50K provenance limit must remain false: {key}")

    for key, value in observation.get("shared_limits", {}).items():
        if value is not False:
            errors.append(f"shared provenance limit must remain false: {key}")

    rule = disposition.get("qualification_rule", {})
    if rule.get("requires_non_circular_original_coding_history_evidence") is not True:
        errors.append("non-circular provenance requirement is absent")
    for key in (
        "decoded_pcm_codec_history_inference_is_admissible_provenance",
        "pcm_or_lossless_delivery_container_alone_is_sufficient",
        "unknown_origin_may_be_assigned_clean_negative_truth",
    ):
        if rule.get(key) is not False:
            errors.append(f"qualification rule must remain false: {key}")

    candidates = disposition.get("candidate_dispositions", [])
    if [candidate.get("source_id") for candidate in candidates] != [
        "musicnet_5120004",
        "fsd50k_4060432_allowed_items",
    ]:
        errors.append("candidate disposition order or identity differs")
    for candidate in candidates:
        source_id = candidate.get("source_id")
        if candidate.get("truth_bearing_clean_reference_eligible") is not False:
            errors.append(f"candidate was promoted to clean truth: {source_id}")
        if candidate.get("actual_prior_lossy_coding_asserted") is not False:
            errors.append(f"candidate was asserted lossy without evidence: {source_id}")
        if candidate.get("all_future_use_rejected") is not False:
            errors.append(f"candidate future stress role was silently rejected: {source_id}")

    consequence = disposition.get("allocation_consequence", {})
    for key in (
        "pending_provider_count_promoted_to_truth_reference",
        "pending_group_capacity_promoted_to_truth_reference",
    ):
        if consequence.get(key) != 0:
            errors.append(f"pending capacity was promoted: {key}")
    for key in (
        "musicnet_repairs_final_music_domain",
        "fsd50k_repairs_natural_domain_truth",
        "add_all_pending_arithmetic_witness_scientifically_eligible",
        "four_partition_truth_manifest_feasible_and_frozen",
    ):
        if consequence.get(key) is not False:
            errors.append(f"allocation consequence must remain false: {key}")
    if consequence.get("additional_provider_or_claim_narrowing_decision_required") is not True:
        errors.append("next source decision is not required")

    options = disposition.get("successor_options", [])
    if [option.get("option_id") for option in options] != [
        "qualify_additional_permissive_providers",
        "narrow_primary_domain_claim",
        "reject_current_truth_source_design",
    ]:
        errors.append("source successor options differ")
    for option in options:
        if option.get("requires_responsible_human_authority") is not True:
            errors.append(f"source option lacks human authority: {option.get('option_id')}")
        if option.get("audio_access_authorized_by_this_disposition") is not False:
            errors.append(f"source option prematurely authorizes audio: {option.get('option_id')}")

    decision = disposition.get("decision", {})
    if decision.get("selected_successor_option") is not None:
        errors.append("source successor was prematurely selected")
    if decision.get("source_manifest_remains_unfrozen") is not True:
        errors.append("source manifest was prematurely frozen")
    if decision.get("no_reference_work_remains_ineligible") is not True:
        errors.append("no-reference work was prematurely enabled")
    if decision.get("final_recommendation_frozen") is not False:
        errors.append("final recommendation was prematurely frozen")

    for key, value in disposition.get("claim_boundary", {}).items():
        if value is not False:
            errors.append(f"claim boundary must remain false: {key}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--disposition", type=Path, default=DEFAULT_DISPOSITION)
    args = parser.parse_args()
    errors = validate(load_json(args.disposition))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated {args.disposition}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
