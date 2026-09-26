#!/usr/bin/env python3
"""Validate the synthetic physical-playback qualification preparation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/playback-qualification-preparation-20260813.json"


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


def validate(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema version differs")
    if plan.get("state") != "synthetic_48khz_playback_qualification_ready_human_observation_pending":
        errors.append("qualification preparation state differs")
    bindings = plan.get("bindings", {})
    if set(bindings) != {
        "playback_declaration",
        "private_lossless_delivery",
        "loopback_server",
        "player_html",
        "player_javascript",
        "pcm_wav_parser",
        "fixture_generator",
        "fixture_tests",
        "plan_validator",
    }:
        errors.append("qualification binding set differs")
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
    if plan.get("signal_contract") != {
        "sample_rate_hz": 48_000,
        "channel_count": 2,
        "bit_depth": 16,
        "channel_check": {
            "duration_seconds": 6,
            "left_frequency_hz": 440,
            "right_frequency_hz": 660,
            "per_channel_peak_dbfs": -30.0,
            "fade_seconds": 0.25,
        },
        "level_calibration": {
            "duration_seconds": 20,
            "frequencies_hz": [500, 1000, 2000],
            "steady_state_rms_dbfs": -30.0,
            "maximum_peak_linear": 0.062,
            "identical_stereo": True,
            "fade_seconds": 0.5,
        },
        "random_noise_used": False,
        "normalization_used": False,
        "browser_resampling_allowed": False,
    }:
        errors.append("qualification signal contract differs")
    observations = plan.get("human_observations", {})
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
        "physical_playback_qualified",
    ):
        if observations.get(key) is not False:
            errors.append(f"human observation must remain pending: {key}")
    boundaries = plan.get("access_boundary", {})
    if boundaries.get("synthetic_qualification_playback_authorized") is not True:
        errors.append("synthetic qualification playback authorization differs")
    for key in (
        "retained_reference_playback_authorized",
        "processed_condition_playback_authorized",
        "degradation_rating_collection_authorized",
        "listener_response_collection_authorized",
        "perceptual_metric_execution_authorized",
        "sealed_evidence_access_authorized",
    ):
        if boundaries.get(key) is not False:
            errors.append(f"access boundary must remain false: {key}")
    if "/Users/" in json.dumps(plan, sort_keys=True):
        errors.append("qualification plan must not contain a private absolute path")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN)
    args = parser.parse_args()
    errors = validate(load_json(args.plan))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(json.dumps({
        "plan": str(args.plan.relative_to(ROOT)),
        "status": "synthetic_playback_qualification_ready",
        "human_observation_pending": True,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
