#!/usr/bin/env python3
"""Validate the score-blind ViSQOL-only successor-readiness disposition."""

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
    / "visqol-only-successor-readiness-disposition.json"
)
DISPOSITION_ID = (
    "perceptual-degradation-visqol-only-successor-readiness-disposition-"
    "20260814-001"
)
OBSERVATION_ID = (
    "perceptual-degradation-visqol-current-public-readiness-observation-"
    "20260814-001"
)
VISQOL_COMMIT = "c3aa2e498e0f7f14202643594335a0b9ee40bdd9"
VISQOL_TREE = "7a0c95a103c4ba40d6337f06f80848e571b00b3c"
MODEL_SHA256 = "1e8246ed33bf36dc5c859351f7110f2cd31f98661989715c0fcf974ec48d3e2e"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(disposition: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if disposition.get("schema_version") != 1:
        errors.append("schema version differs")
    if disposition.get("disposition_id") != DISPOSITION_ID:
        errors.append("disposition identity differs")
    if disposition.get("state") != (
        "visqol_only_successor_preregisterable_not_selected_or_execution_ready"
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

    observation = bound.get("current_public_observation", {})
    if observation.get("observation_id") != OBSERVATION_ID:
        errors.append("current public observation identity differs")
    if observation.get("state") != "current_public_record_observed_no_successor_selected":
        errors.append("current public observation state differs")

    observation_access = observation.get("access_boundary", {})
    for key in (
        "source_or_binary_downloaded_by_this_checkpoint",
        "audio_accessed",
        "visqol_executed_by_this_checkpoint",
        "metric_score_opened_by_this_checkpoint",
        "human_score_opened",
        "sealed_evidence_opened",
        "successor_selected",
        "execution_authorized",
        "public_verdict_enabled",
    ):
        if observation_access.get(key) is not False:
            errors.append(f"observation access boundary must remain false: {key}")

    repository = observation.get("official_repository", {})
    if (
        repository.get("license_spdx") != "Apache-2.0"
        or repository.get("archived") is not False
        or repository.get("disabled") is not False
    ):
        errors.append("official repository readiness record differs")

    release = observation.get("frozen_release", {})
    if (
        release.get("version") != "v3.3.3"
        or release.get("git_commit") != VISQOL_COMMIT
        or release.get("git_tree") != VISQOL_TREE
    ):
        errors.append("frozen ViSQOL release differs")
    comparison = observation.get("current_branch_comparison", {})
    if comparison.get("frozen_release_silently_advanced") is not False:
        errors.append("frozen release cannot be silently advanced")

    files = observation.get("pinned_files", {})
    if files.get("audio_model", {}).get("sha256") != MODEL_SHA256:
        errors.append("frozen audio model differs")
    if files.get("license", {}).get("sha256") != (
        "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
    ):
        errors.append("frozen ViSQOL license differs")

    audio = observation.get("official_audio_mode_record", {})
    expected_audio = {
        "full_reference_metric": True,
        "required_sample_rate_hz": 48000,
        "multi_channel_input_downmixed_to_mono": True,
        "single_scores_meaningful_as_treatment_conclusions": False,
        "treatment_aggregation_over_multiple_samples_recommended": True,
        "subjective_scores_required_to_train_domain_specific_audio_model": True,
    }
    for key, expected in expected_audio.items():
        if audio.get(key) != expected:
            errors.append(f"official audio-mode boundary differs: {key}")

    official_output = observation.get("official_output_record", {})
    for key in (
        "outputs_documented_as_lossytrace_audibility_probability",
        "outputs_documented_as_lossytrace_materiality_truth",
        "outputs_documented_as_human_calibrated_artifact_labels",
    ):
        if official_output.get(key) is not False:
            errors.append(f"official output cannot be promoted to truth: {key}")

    limits = observation.get("documented_domain_limits", {})
    if (
        limits.get("trained_full_band_audio_minimum_bitrate_kbps") != 24
        or limits.get("below_training_bitrate_may_behave_poorly") is not True
        or limits.get("all_lossytrace_source_domains_validated") is not False
        or limits.get("stereo_image_or_phase_change_supported") is not False
    ):
        errors.append("documented domain limits differ")

    rights = observation.get("software_rights_record", {})
    if (
        rights.get("software_copyright_license_identified") is not True
        or rights.get("software_copyright_license") != "Apache License 2.0"
        or rights.get("dependency_redistribution_and_sbom_review_complete") is not False
        or rights.get("fact_specific_legal_advice_obtained") is not False
        or rights.get("this_record_is_legal_advice") is not False
    ):
        errors.append("software rights boundary differs")

    predecessor = bound.get("predecessor_disposition", {})
    if predecessor.get("decision", {}).get("selected_successor_option") is not None:
        errors.append("predecessor successor was selected")
    if predecessor.get("decision", {}).get("current_metric_gate_remains_closed") is not True:
        errors.append("predecessor metric gate is not closed")

    research = bound.get("research_plan", {})
    families = [
        family.get("family_id") for family in research.get("primary_metric_families", [])
    ]
    if families != ["visqol_audio_v3_3_3", "gstpeaq_proxy_v0_6_1"]:
        errors.append("frozen predecessor metric families differ")

    metric_gate = bound.get("metric_execution_gate", {})
    if metric_gate.get("perceptual_metric_execution_authorized") is not False:
        errors.append("predecessor metric execution gate is open")
    if metric_gate.get("metric_families", {}).get("visqol_audio_v3_3_3", {}).get(
        "execution_authorized"
    ) is not False:
        errors.append("predecessor ViSQOL execution is open")

    score_free_schema = bound.get("score_free_schema", {})
    family_schema = score_free_schema.get("properties", {}).get("metric_families", {})
    if family_schema.get("minItems") != 2 or family_schema.get("maxItems") != 2:
        errors.append("predecessor exactly-two-family schema differs")

    first_build = bound.get("first_environment_build_observation", {})
    second_build = bound.get("second_environment_build_observation", {})
    replay = bound.get("first_environment_replay_observation", {})
    cross = bound.get("cross_environment_replay_observation", {})
    if first_build.get("files", {}).get("binary", {}).get("sha256") != (
        "7384c8d21725e6fa3921aea4e66ff9cb9481b57acef868304192df437a467319"
    ):
        errors.append("first ViSQOL binary differs")
    if second_build.get("files", {}).get("binary", {}).get("sha256") != (
        "6c7807891cb5cb267649f09fbc20eecc22a3b2f62e50698e38134b2e08d18d5f"
    ):
        errors.append("second ViSQOL binary differs")
    if replay.get("synthetic_scores_are_human_truth") is not False:
        errors.append("synthetic replay cannot be human truth")
    if (
        cross.get("score_determinism_pass") is not True
        or len(cross.get("results", [])) != 4
        or any(
            max(result.get("absolute_deltas", {}).values(), default=1) != 0
            for result in cross.get("results", [])
        )
    ):
        errors.append("cross-environment synthetic replay differs")

    expected_access = {
        "public_primary_sources_read": True,
        "retained_audio_access_authorized": False,
        "public_or_provider_audio_access_authorized": False,
        "perceptual_metric_execution_authorized": False,
        "metric_score_access_authorized": False,
        "listening_score_access_authorized": False,
        "human_collection_authorized": False,
        "sealed_evidence_access_authorized": False,
        "no_reference_training_authorized": False,
        "source_successor_selected": False,
        "metric_successor_selected": False,
        "public_verdict_enabled": False,
    }
    if disposition.get("access_boundary") != expected_access:
        errors.append("access boundary differs")

    readiness = disposition.get("readiness", {})
    for key in (
        "visqol_only_successor_preregisterable",
        "software_copyright_license_record_clear_for_internal_research_candidate",
        "technical_synthetic_replay_readiness",
        "cross_environment_numeric_replay_passed",
    ):
        if readiness.get(key) is not True:
            errors.append(f"readiness finding must remain true: {key}")
    for key in (
        "dependency_redistribution_and_sbom_review_complete",
        "scientific_readiness",
        "human_calibration_complete",
        "source_manifest_complete",
        "eligible_audio_metric_execution_complete",
        "artifact_profile_readiness",
        "stereo_profile_supported_by_visqol",
        "no_reference_work_eligible",
        "final_recommendation_frozen",
    ):
        if readiness.get(key) is not False:
            errors.append(f"readiness finding must remain false: {key}")

    amendment = disposition.get("required_score_blind_successor_amendment", {})
    for key in (
        "new_successor_id_required",
        "must_be_committed_before_retained_or_human_metric_outcomes",
        "frozen_release_and_model_preserved",
        "mono_downmix_reported",
        "visqol_only_stereo_conclusion_forbidden",
        "human_calibration_required_for_severity_audibility_and_materiality",
        "treatment_and_source_group_aggregation_required",
        "predecessor_exactly_two_family_schema_requires_new_version",
        "gstpeaq_family_removed_from_successor",
        "raw_visqol_baseline_retained",
        "signal_distance_baseline_retained",
        "transparent_lossy_non_degraded_control_preserved",
        "hard_natural_and_production_negatives_preserved",
        "grouped_source_domain_codec_encoder_holdouts_preserved",
        "public_cli_remains_verdict_free",
    ):
        if amendment.get(key) is not True:
            errors.append(f"required successor amendment differs: {key}")

    artifact = disposition.get("artifact_profile_boundary", {})
    if artifact.get("stereo_image_or_phase_change") != "null_visqol_downmixes_to_mono":
        errors.append("stereo artifact boundary differs")
    if artifact.get("patch_or_frequency_similarity_may_be_used_as_truth_labels") is not False:
        errors.append("similarity diagnostics cannot become artifact truth")
    for key, value in artifact.items():
        if key not in {
            "stereo_image_or_phase_change",
            "patch_or_frequency_similarity_may_be_used_as_truth_labels",
        } and value != "null_until_separately_human_calibrated":
            errors.append(f"artifact component cannot be prematurely populated: {key}")

    decision = disposition.get("decision", {})
    if decision.get("selected_successor_option") is not None:
        errors.append("successor option was prematurely selected")
    if decision.get("responsible_human_selection_required") is not True:
        errors.append("responsible-human selection must remain required")
    if decision.get("current_two_family_metric_gate_remains_closed") is not True:
        errors.append("current two-family metric gate must remain closed")
    if decision.get("new_successor_metric_gate_exists") is not False:
        errors.append("successor metric gate cannot be invented")
    if decision.get("execution_authorized_by_this_disposition") is not False:
        errors.append("disposition cannot authorize execution")

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
