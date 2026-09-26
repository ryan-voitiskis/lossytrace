#!/usr/bin/env python3
"""Validate frozen production and codec-generation control recipes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/production-generation-control-plan.json"
)
PRODUCTION_FAMILIES = {"clipping", "equalization", "limiting", "stereo_width"}
CODECS = {"aac_lc", "mp3", "opus", "vorbis"}
RESAMPLE_FILTER_TEMPLATE = (
    "aresample={target}:osf=s16:resampler=swr:filter_size=64:phase_shift=10:"
    "linear_interp=0:exact_rational=1:cutoff=0.95:filter_type=kaiser:"
    "kaiser_beta=9:dither_method=none"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    return value


def validate(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if plan.get("state") != "score_blind_recipes_frozen_before_implementation_or_audio":
        errors.append("recipe freeze state differs")
    for field, value in plan.get("access_boundary", {}).items():
        if value is not False:
            errors.append(f"access boundary must remain false: {field}")

    bound: dict[str, dict[str, Any]] = {}
    for binding_id, binding in plan.get("bindings", {}).items():
        relative = binding.get("path", "")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            errors.append(f"invalid repository-relative binding: {binding_id}")
            continue
        path = root / relative
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
            continue
        if sha256_file(path) != binding.get("sha256"):
            errors.append(f"binding hash differs: {binding_id}")
            continue
        if path.suffix == ".json":
            bound[binding_id] = load_json(path)

    input_contract = plan.get("input_contract", {})
    if input_contract.get("sample_format") != "signed_s16le":
        errors.append("input sample format differs")
    if input_contract.get("normalization_applied") is not False:
        errors.append("normalization must remain disabled")
    if input_contract.get("condition_truth_state") != (
        "unresolved_until_frozen_listening_analysis"
    ):
        errors.append("condition truth was assigned before listening")
    support = input_contract.get("minimum_changed_frame_fraction")
    if not isinstance(support, (int, float)) or not 0 < support <= 0.01:
        errors.append("changed-frame support threshold differs")

    production = plan.get("production_control_recipes", [])
    families = {item.get("family") for item in production}
    if families != PRODUCTION_FAMILIES or len(production) != 4:
        errors.append("production control family coverage differs")
    recipe_ids = [item.get("recipe_id") for item in production]
    if None in recipe_ids or len(recipe_ids) != len(set(recipe_ids)):
        errors.append("production recipe IDs must be unique")
    for recipe in production:
        if not recipe.get("algorithm") or recipe.get("perceptual_truth") != "unresolved":
            errors.append(f"production recipe truth or algorithm differs: {recipe.get('recipe_id')}")

    toolchain = bound.get("v2_toolchain_bindings", {})
    settings = {
        item.get("expanded_setting_id"): item
        for item in toolchain.get("expanded_encoder_settings", [])
    }
    generations = plan.get("codec_generation_recipes", [])
    if len(generations) != 8:
        errors.append("exactly eight codec-generation recipes are required")
    generation_ids = [item.get("recipe_id") for item in generations]
    if None in generation_ids or len(generation_ids) != len(set(generation_ids)):
        errors.append("codec-generation recipe IDs must be unique")
    repeated_codecs: set[str] = set()
    cross_first: set[str] = set()
    for recipe in generations:
        setting_ids = recipe.get("expanded_setting_ids", [])
        if len(setting_ids) != 2:
            errors.append(f"generation count differs: {recipe.get('recipe_id')}")
            continue
        rows = [settings.get(setting_id) for setting_id in setting_ids]
        if any(row is None for row in rows):
            errors.append(f"unknown expanded setting: {recipe.get('recipe_id')}")
            continue
        if any(row.get("channel_treatment_id") != "stereo" for row in rows):
            errors.append(f"generation recipe must remain stereo: {recipe.get('recipe_id')}")
        codecs = [row.get("codec_family") for row in rows]
        if recipe.get("family") == "repeated_same_codec":
            if setting_ids[0] != setting_ids[1] or codecs[0] != codecs[1]:
                errors.append(f"repeated-codec recipe differs: {recipe.get('recipe_id')}")
            repeated_codecs.add(codecs[0])
        elif recipe.get("family") == "cross_codec_generation":
            if codecs[0] == codecs[1]:
                errors.append(f"cross-codec recipe repeats a codec: {recipe.get('recipe_id')}")
            cross_first.add(codecs[0])
        else:
            errors.append(f"unknown generation family: {recipe.get('family')}")
    if repeated_codecs != CODECS:
        errors.append("repeated-codec coverage differs")
    if cross_first != CODECS:
        errors.append("cross-codec first-generation coverage differs")

    execution = plan.get("codec_generation_execution", {})
    if execution.get("generation_count") != 2:
        errors.append("codec generation count must equal two")
    for field in (
        "actual_codec_or_encoder_is_quality_target",
        "nominal_setting_assigns_severity_or_transparency",
    ):
        if execution.get(field) is not False:
            errors.append(f"codec generation target boundary differs: {field}")
    resampler = execution.get("intermediate_resampler", {})
    if resampler.get("tool_id") != "ffmpeg_8_1_2_1":
        errors.append("intermediate resampler tool differs")
    if resampler.get("filter_template") != RESAMPLE_FILTER_TEMPLATE:
        errors.append("intermediate resampler filter differs")
    if resampler.get("sample_format") != "signed_s16le" or resampler.get("channels") != 2:
        errors.append("intermediate resampler PCM geometry differs")
    for field in ("dither_applied", "normalization_applied"):
        if resampler.get(field) is not False:
            errors.append(f"intermediate resampler boundary differs: {field}")

    replay = plan.get("replay_requirements", {})
    if replay.get("synthetic_cases_required") != 12:
        errors.append("synthetic case count must equal 12")
    if replay.get("two_fresh_replays_required") is not True:
        errors.append("two fresh replays must be required")
    if replay.get("actual_source_audio_forbidden_during_replay") is not True:
        errors.append("actual source audio must remain forbidden during replay")

    decision = plan.get("decision", {})
    if decision.get("recipes_frozen") is not True:
        errors.append("recipes must be frozen")
    for field in (
        "implementation_present",
        "synthetic_replay_complete",
        "actual_stimuli_generated",
        "production_controls_complete_for_manifest",
        "multi_generation_controls_complete_for_manifest",
    ):
        if decision.get(field) is not False:
            errors.append(f"premature recipe completion: {field}")
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
