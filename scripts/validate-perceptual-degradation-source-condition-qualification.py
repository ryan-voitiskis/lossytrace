#!/usr/bin/env python3
"""Validate the score-blind perceptual source/condition qualification plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = (
    REPO_ROOT
    / "benchmarks/perceptual-degradation-v1/source-condition-qualification-plan.json"
)
REQUIRED_CODECS = {"aac_lc", "mp3", "opus", "vorbis"}
FORBIDDEN_SOURCE_IDS = {
    "consumed_v1_non_holdout",
    "existing_280_case_future_subset",
    "release_holdouts",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    return value


def validate(plan: dict[str, Any], repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if plan.get("state") != "metadata_only_candidates_qualified_manifest_not_frozen":
        errors.append("qualification state differs")

    access = plan.get("access_boundary", {})
    for field, value in access.items():
        if value is not False:
            errors.append(f"access boundary must remain false: {field}")

    resources = plan.get("resources", {})
    if resources.get("minimum_free_disk_gib", 0) < 15:
        errors.append("minimum free-disk reserve is below 15 GiB")
    if resources.get("maximum_sustained_workers", 99) > 6:
        errors.append("sustained worker ceiling exceeds six")
    if resources.get("duplicate_corpus_forbidden") is not True:
        errors.append("duplicate corpus boundary differs")

    bound_values: dict[str, dict[str, Any]] = {}
    for binding_id, binding in plan.get("bindings", {}).items():
        relative = binding.get("path", "")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            errors.append(f"invalid repository-relative binding: {binding_id}")
            continue
        path = repo_root / relative
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
            continue
        if sha256_file(path) != binding.get("sha256"):
            errors.append(f"binding hash differs: {binding_id}")
            continue
        if path.suffix == ".json":
            bound_values[binding_id] = load_json(path)

    inventory = bound_values.get("v2_inventory", {})
    inventory_sources = {
        item.get("source_id"): item for item in inventory.get("source_candidates", [])
    }
    qualified_ids: set[str] = set()
    for source in plan.get("source_candidates", []):
        source_id = source.get("source_id")
        if source_id in qualified_ids:
            errors.append(f"duplicate source candidate: {source_id}")
            continue
        qualified_ids.add(source_id)
        if source_id in FORBIDDEN_SOURCE_IDS:
            errors.append(f"forbidden source candidate: {source_id}")
        observed = inventory_sources.get(source_id)
        if observed is None:
            errors.append(f"source missing from bound inventory: {source_id}")
            continue
        if source.get("licence") != observed.get("license"):
            errors.append(f"source licence differs: {source_id}")
        if source.get("conservative_group_count") != observed.get(
            "conservative_partition_groups"
        ):
            errors.append(f"source group count differs: {source_id}")
        if not source.get("candidate_use"):
            errors.append(f"source candidate use is empty: {source_id}")
        if source.get("licence_status") in {"cleared", "frozen"}:
            errors.append(f"source licence prematurely represented as frozen: {source_id}")

    odaq = plan.get("odaq_development_evidence", {})
    odaq_evidence = bound_values.get("odaq_attribution_evidence", {})
    odaq_selection = odaq_evidence.get("selection", {})
    for field in ("source_count", "group_count", "wav_member_count"):
        if odaq.get(field) != odaq_selection.get(field):
            errors.append(f"ODAQ selection count differs: {field}")
    if odaq.get("published_conditions_are_actual_codec_examples") is not False:
        errors.append("ODAQ conditions must not be represented as actual codecs")
    if odaq.get("eligible_for_grouped_transfer") is not False:
        errors.append("ODAQ must remain outside grouped transfer")
    if odaq.get("eligible_for_final_validation") is not False:
        errors.append("ODAQ must remain outside final validation")
    if odaq.get("audio_acquisition_authorized") is not False:
        errors.append("ODAQ audio acquisition must remain unauthorized")

    factor_levels = bound_values.get("v2_factor_levels", {})
    templates = {
        item.get("template_id"): item
        for item in factor_levels.get("codec_setting_templates", [])
    }
    conditions = plan.get("codec_condition_candidates", {})
    selected_by_partition = {
        "mechanism_development": conditions.get("development_template_ids", []),
        "encoder_transfer": conditions.get("encoder_transfer_template_ids", []),
    }
    observed_codecs: dict[str, set[str]] = {
        "mechanism_development": set(),
        "encoder_transfer": set(),
    }
    for partition, template_ids in selected_by_partition.items():
        if len(template_ids) != len(set(template_ids)):
            errors.append(f"duplicate condition template in {partition}")
        for template_id in template_ids:
            template = templates.get(template_id)
            if template is None:
                errors.append(f"unknown condition template: {template_id}")
                continue
            if template.get("evidence_partition") != partition:
                errors.append(f"condition partition differs: {template_id}")
            observed_codecs[partition].add(template.get("codec_family"))
    for partition, codec_families in observed_codecs.items():
        if codec_families != REQUIRED_CODECS:
            errors.append(f"codec coverage differs in {partition}")
    if set(conditions.get("required_codec_families", [])) != REQUIRED_CODECS:
        errors.append("required codec family declaration differs")

    truth = conditions.get("ground_truth_policy", {})
    if truth.get("bitrate_or_quality_is_target") is not False:
        errors.append("bitrate or quality must not be a target")
    if truth.get("codec_or_encoder_is_target") is not False:
        errors.append("codec or encoder must not be a target")
    if truth.get("nominal_upper_quality_implies_transparency") is not False:
        errors.append("nominal quality must not imply transparency")
    if truth.get("transparency_truth_state") != "unresolved_until_frozen_listening_analysis":
        errors.append("transparency truth was assigned before listening")
    if truth.get("future_manifest_schema_version") != 2:
        errors.append("future listening manifest schema must equal 2")
    if truth.get("future_manifest_condition_class") != "transparency_candidate":
        errors.append("transparency candidate terminology differs")
    if conditions.get("actual_stimuli_generated") is not False:
        errors.append("actual stimuli must remain ungenerated")
    if conditions.get("condition_outcomes_opened") is not False:
        errors.append("condition outcomes must remain unopened")

    controls = plan.get("production_and_negative_control_coverage", {})
    transform_ids = {
        item.get("transform_id") for item in factor_levels.get("pcm_transform_levels", [])
    }
    if not set(controls.get("existing_recipe_candidates", [])).issubset(transform_ids):
        errors.append("existing control recipe is not bound by factor levels")
    if not controls.get("missing_recipe_families"):
        errors.append("missing control recipe families were not declared")
    if controls.get("non_codec_condition_truth_state") != "unresolved_until_listening":
        errors.append("non-codec control truth was assigned before listening")

    decision = plan.get("decision", {})
    for field in (
        "mastered_music_coverage_qualified",
        "production_control_recipes_complete",
        "repeated_and_cross_codec_recipes_complete",
        "licences_frozen",
        "source_and_condition_manifest_frozen",
        "source_and_condition_manifest_freezable",
    ):
        if decision.get(field) is not False:
            errors.append(f"incomplete decision must remain false: {field}")
    if not plan.get("remaining_gates"):
        errors.append("remaining gates must be explicit")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    args = parser.parse_args()
    errors = validate(load_json(args.plan))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated {args.plan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
