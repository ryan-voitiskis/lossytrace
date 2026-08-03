#!/usr/bin/env python3
"""Validate path-free synthetic production/generation replay evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = (
    ROOT
    / "research/toolchains/evidence/perceptual-degradation-production-generation-synthetic-replay-20260804-001.json"
)
PRODUCTION_IDS = {
    "production-hard-clip-minus6dbfs-v1",
    "production-high-shelf-minus6db-nyquist-fir3-v1",
    "production-block-limiter-minus6dbfs-5ms-v1",
    "production-stereo-width-half-mid-side-v1",
}
GENERATION_TRANSITIONS = {
    "generation-repeat-mp3-lame-v2-v1": (["mp3", "mp3"], False),
    "generation-repeat-aac-ffmpeg-128-v1": (["aac_lc", "aac_lc"], False),
    "generation-repeat-opus-libopus-128-v1": (["opus", "opus"], False),
    "generation-repeat-vorbis-libvorbis-q6-v1": (["vorbis", "vorbis"], False),
    "generation-cross-mp3-v2-to-aac-128-v1": (["mp3", "aac_lc"], False),
    "generation-cross-aac-128-to-opus-128-v1": (["aac_lc", "opus"], True),
    "generation-cross-opus-128-to-vorbis-q6-v1": (["opus", "vorbis"], True),
    "generation-cross-vorbis-q6-to-mp3-v2-v1": (["vorbis", "mp3"], False),
}
REQUIRED_TOOL_IDS = {
    "ffmpeg_8_1_2_1",
    "lame_cli_4_0",
    "oggenc_1_4_3_libvorbis_1_3_7",
    "opusenc_0_2_2_libopus_1_6_1",
}


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


def validate(evidence: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if evidence.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if evidence.get("state") != (
        "two_fresh_byte_identical_synthetic_replays_passed_actual_audio_unopened"
    ):
        errors.append("replay evidence state differs")

    for binding_id in ("recipe_plan", "execution_plan", "implementation", "toolchain"):
        binding = evidence.get("bindings", {}).get(binding_id, {})
        relative = binding.get("path", "")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            errors.append(f"invalid repository-relative binding: {binding_id}")
            continue
        path = root / relative
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"binding hash differs: {binding_id}")

    toolchain_binding = evidence.get("bindings", {}).get("toolchain", {})
    toolchain_path = root / toolchain_binding.get("path", "missing")
    toolchain = load_json(toolchain_path) if toolchain_path.is_file() else {}
    bound_tools = {
        item.get("tool_id"): item.get("binary_sha256")
        for item in toolchain.get("tool_bindings", [])
        if item.get("tool_id") in REQUIRED_TOOL_IDS
    }
    if evidence.get("verified_tools") != bound_tools:
        errors.append("verified tool bindings differ")

    replay = evidence.get("replay_observation", {})
    hashes = replay.get("report_sha256s", [])
    if replay.get("replay_count") != 2 or len(hashes) != 2:
        errors.append("exactly two replay reports are required")
    if len(hashes) != 2 or len(set(hashes)) != 1:
        errors.append("replay report hashes differ")
    if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes):
        errors.append("replay report hash format differs")
    for field in (
        "fresh_temporary_directories",
        "byte_identical_reports",
        "path_free_aggregate_retained",
    ):
        if replay.get(field) is not True:
            errors.append(f"replay observation differs: {field}")
    for field in (
        "full_reports_retained_in_research_corpus",
        "generated_audio_or_bitstreams_retained",
        "timing_retained",
    ):
        if replay.get(field) is not False:
            errors.append(f"replay retention boundary differs: {field}")
    if replay.get("reports_moved_to_recoverable_trash") is not True:
        errors.append("report disposal boundary differs")
    if replay.get("minimum_free_disk_gib_enforced") != 15:
        errors.append("disk reserve enforcement differs")

    production = evidence.get("production_cases", [])
    if {item.get("recipe_id") for item in production} != PRODUCTION_IDS:
        errors.append("production replay case set differs")
    for item in production:
        if item.get("support_passed") is not True:
            errors.append(f"production support failed: {item.get('recipe_id')}")
        fraction = item.get("changed_frame_fraction")
        if not isinstance(fraction, (int, float)) or fraction < 0.001:
            errors.append(f"production support fraction differs: {item.get('recipe_id')}")
        changed = item.get("changed_frame_count")
        if (
            not isinstance(changed, int)
            or not 0 < changed <= 96000
            or not isinstance(fraction, (int, float))
            or abs(fraction - changed / 96000) > 1e-15
        ):
            errors.append(f"production changed-frame aggregate differs: {item.get('recipe_id')}")

    generations = evidence.get("generation_cases", [])
    observed_generations = {item.get("recipe_id"): item for item in generations}
    if set(observed_generations) != set(GENERATION_TRANSITIONS):
        errors.append("generation replay case set differs")
    for recipe_id, (codecs, resampled) in GENERATION_TRANSITIONS.items():
        item = observed_generations.get(recipe_id, {})
        if item.get("stage_count") != 2 or item.get("codec_families") != codecs:
            errors.append(f"generation replay stages differ: {recipe_id}")
        if item.get("intermediate_resampling_applied") is not resampled:
            errors.append(f"generation replay transition differs: {recipe_id}")

    summary = evidence.get("summary", {})
    counts = {
        "synthetic_case_count": 12,
        "production_case_count": 4,
        "production_support_pass_count": 4,
        "generation_case_count": 8,
        "codec_family_count": 4,
    }
    for field, expected in counts.items():
        if summary.get(field) != expected:
            errors.append(f"replay summary differs: {field}")
    for field in (
        "actual_audio_accessed",
        "metric_score_opened",
        "listener_response_collected",
        "perceptual_truth_included",
        "codec_quality_ranking_included",
    ):
        if summary.get(field) is not False:
            errors.append(f"outcome boundary differs: {field}")

    decision = evidence.get("decision", {})
    for field in (
        "synthetic_recipe_replay_complete",
        "production_controls_complete_for_manifest_construction",
        "multi_generation_controls_complete_for_manifest_construction",
    ):
        if decision.get(field) is not True:
            errors.append(f"replay decision differs: {field}")
    for field in (
        "actual_stimuli_generated",
        "condition_perceptual_truth_assigned",
        "human_collection_authorized",
    ):
        if decision.get(field) is not False:
            errors.append(f"replay decision boundary differs: {field}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    errors = validate(load_json(args.evidence))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated {args.evidence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
