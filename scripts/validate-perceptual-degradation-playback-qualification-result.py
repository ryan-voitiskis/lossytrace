#!/usr/bin/env python3
"""Validate the path-free physical-playback qualification result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "benchmarks/perceptual-degradation-v1/playback-qualification-result-20260813.json"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if result.get("schema_version") != 1:
        errors.append("schema version differs")
    if result.get("state") != "declared_physical_playback_chain_qualified_no_perceptual_truth_collected":
        errors.append("qualification result state differs")
    bindings = result.get("bindings", {})
    if set(bindings) != {
        "playback_qualification_preparation",
        "playback_declaration",
        "private_lossless_delivery",
        "fixture_generator",
        "loopback_server",
        "player_javascript",
        "pcm_wav_parser",
    }:
        errors.append("qualification result binding set differs")
    for binding_id, binding in bindings.items():
        relative = Path(str(binding.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"invalid repository-relative binding: {binding_id}")
            continue
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")

    execution = result.get("execution", {})
    for key, expected in {
        "exact_head_commit": "ce08bf4b8487abcdae8e1b48e757dfc2f115e967",
        "exact_head_ci_url": "https://github.com/ryan-voitiskis/lossytrace/actions/runs/31689599039",
        "exact_head_ci_passed": True,
        "origin_class": "numeric_ipv4_loopback_only",
        "manifest_id": "manifest-playback-qualification-0001",
        "player_build_id": "player-lossless-qualification-v1",
        "session_sample_rate_hz": 48_000,
        "audio_context_state": "running",
        "audio_context_sample_rate_hz": 48_000,
        "required_sample_rate_hz": 48_000,
        "browser_resampling_requested": False,
        "collection_enabled": False,
    }.items():
        if execution.get(key) != expected:
            errors.append(f"execution evidence differs: {key}")

    fixtures = result.get("fixture_verification", [])
    expected_fixtures = {
        "channel-check-0001": ("9ad35f025a79d5373e7f3ba12c37531ac12879a8fbcca59dd322dec8899f93d2", 1_152_044, 288_000),
        "level-calibration-0001": ("3f6c800d6cd2800b1f5bd5d56747cd817cc7b13947bf8170226efed9f422fc7a", 3_840_044, 960_000),
    }
    if not isinstance(fixtures, list) or len(fixtures) != 2:
        errors.append("fixture verification count differs")
    else:
        for fixture in fixtures:
            stimulus_id = fixture.get("stimulus_id")
            expected = expected_fixtures.get(stimulus_id)
            if expected is None or (
                fixture.get("sha256"),
                fixture.get("byte_length"),
                fixture.get("pcm_frame_count"),
            ) != expected:
                errors.append(f"fixture identity differs: {stimulus_id}")
            for key, value in {
                "sample_rate_hz": 48_000,
                "channel_count": 2,
                "bit_depth": 16,
                "browser_sha256_and_geometry_verified": True,
                "browser_resampling_requested": False,
            }.items():
                if fixture.get(key) != value:
                    errors.append(f"fixture evidence differs: {stimulus_id}:{key}")

    system = result.get("system_audio_observation", {})
    if system != {
        "observation_method": "macOS system audio inventory after qualification",
        "manufacturer": "RME",
        "device_name": "ADI-2 Pro",
        "transport": "USB",
        "default_output": True,
        "default_system_device": True,
        "input_channel_count": 2,
        "output_channel_count": 2,
        "sample_rate_hz": 48_000,
    }:
        errors.append("system audio observation differs")

    human = result.get("responsible_human_observations", {})
    for key in (
        "interface_set_to_exact_48khz",
        "audio_context_reports_exact_48khz",
        "left_button_audible_from_left_only",
        "right_button_audible_from_right_only",
        "quiet_session_and_fixed_position_present",
        "declared_effects_off_confirmed_for_session",
        "comfortable_conservative_level_set",
        "level_held_fixed_during_testing",
        "no_discomfort_observed",
    ):
        if human.get(key) is not True:
            errors.append(f"responsible-human observation differs: {key}")
    if human.get("degradation_rating_provided") is not False:
        errors.append("a degradation rating was improperly recorded")

    if result.get("qualified_chain", {}).get("physical_playback_qualified") is not True:
        errors.append("physical playback qualification differs")
    disposition = result.get("fixture_disposition", {})
    for key in (
        "loopback_server_stopped",
        "private_fixture_removed_from_active_research_storage",
        "moved_to_recoverable_trash",
    ):
        if disposition.get(key) is not True:
            errors.append(f"fixture disposition differs: {key}")
    if disposition.get("retained_odaq_reference_corpus_touched") is not False:
        errors.append("retained ODAQ corpus was improperly touched")
    if disposition.get("private_path_published") is not False:
        errors.append("a private fixture path was published")

    access = result.get("access_boundary", {})
    if access.get("synthetic_qualification_fixture_played") is not True:
        errors.append("synthetic fixture playback evidence differs")
    for key in (
        "retained_reference_played",
        "processed_condition_played",
        "degradation_rating_collected",
        "listener_response_collected",
        "perceptual_metric_executed",
        "sealed_evidence_opened",
    ):
        if access.get(key) is not False:
            errors.append(f"access boundary must remain false: {key}")

    claim = result.get("claim_boundary", {})
    if claim.get("physical_playback_chain_qualified") is not True:
        errors.append("physical playback claim differs")
    for key in (
        "comfortable_level_is_calibrated_spl",
        "qualification_is_listening_evidence",
        "qualification_is_perceptual_validation",
        "independent_transfer_supported",
        "final_validation_supported",
        "stimulus_generation_authorized",
        "retained_reference_conversion_authorized",
        "human_collection_authorized",
        "public_verdict_enabled",
    ):
        if claim.get(key) is not False:
            errors.append(f"claim boundary must remain false: {key}")
    serialized = json.dumps(result, sort_keys=True)
    if "/Users/" in serialized or "Application Support" in serialized:
        errors.append("qualification result must not contain a private absolute path")
    if result.get("paths_redacted") is not True:
        errors.append("qualification result paths must be redacted")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=RESULT)
    args = parser.parse_args()
    errors = validate(load_json(args.result))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(json.dumps({
        "result": str(args.result.relative_to(ROOT)),
        "result_sha256": sha256_file(args.result),
        "status": "physical_playback_chain_qualified",
        "perceptual_truth_collected": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
