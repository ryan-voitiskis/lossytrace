#!/usr/bin/env python3
"""Validate the bounded ODAQ clean-reference acquisition authorization."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FREEZE = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "odaq-reference-acquisition-freeze.json"
)
AUTHORIZATION = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "odaq-reference-acquisition-authorization-20260813.json"
)
EXTRACTOR = ROOT / "scripts/acquire-perceptual-degradation-odaq-references.py"
SPEC = importlib.util.spec_from_file_location("odaq_reference_extractor", EXTRACTOR)
assert SPEC and SPEC.loader
CORE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CORE
SPEC.loader.exec_module(CORE)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def validate(authorization: dict[str, Any], freeze: dict[str, Any]) -> list[str]:
    errors = CORE.validate_live_authorization(
        authorization, freeze, CORE.sha256_file(FREEZE)
    )
    if authorization.get("authorization_id") != (
        "perceptual-degradation-odaq-reference-acquisition-20260813-001"
    ):
        errors.append("authorization identity differs")
    if authorization.get("authorized_on") != "2026-08-13":
        errors.append("authorization date differs")

    bindings = authorization.get("bindings", {})
    expected_binding_ids = {
        "reference_metadata_freeze",
        "bounded_extractor",
        "authorization_validator",
        "authorization_tests",
        "authorization_report",
    }
    if set(bindings) != expected_binding_ids:
        errors.append("authorization binding set differs")
    for binding_id, binding in bindings.items():
        relative = Path(str(binding.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"invalid repository-relative binding: {binding_id}")
            continue
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif CORE.sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")

    expected_scope = {
        "reference_member_basename": "reference.wav",
        "reference_count": 16,
        "total_compressed_bytes": 46_721_638,
        "total_uncompressed_bytes": 54_633_154,
        "full_archive_persistence_authorized": False,
        "provider_processed_condition_access_authorized": False,
        "provider_listening_score_access_authorized": False,
    }
    if authorization.get("authorization_scope") != expected_scope:
        errors.append("authorization scope differs")

    expected_source_decision = {
        "one_provider_development_only_limit_accepted": True,
        "bound_attribution_requirements_accepted": True,
        "noncommercial_or_sharealike_source_authorized": False,
        "broad_music_transfer_claim_authorized": False,
        "final_validation_claim_authorized": False,
    }
    if authorization.get("source_decision") != expected_source_decision:
        errors.append("responsible-human source decision differs")

    playback = authorization.get("playback_declaration", {})
    if playback.get("state") != "declared_observation_pending":
        errors.append("playback declaration state differs")
    if playback.get("source_device_class") != "macos_computer":
        errors.append("playback source-device class differs")
    if playback.get("operating_system_observed") != "macOS 26.6.1 (25G76)":
        errors.append("playback operating-system observation differs")
    if playback.get("interface") != {
        "manufacturer": "RME",
        "model": "ADI-2 Pro FS",
        "transport": "USB",
        "channel_count_observed": 2,
        "current_sample_rate_hz_observed": 96_000,
    }:
        errors.append("declared interface differs")
    if playback.get("transducer") != {
        "manufacturer": "Adam Audio",
        "model": "T7V",
        "class": "active_loudspeaker_pair",
    }:
        errors.append("declared transducer differs")
    if playback.get("environment") != {
        "class": "treated_domestic_living_room",
        "treatment": ["bass traps", "soft sofa", "carpets", "rugs", "curtains"],
        "quiet_session_observation_present": False,
        "fixed_listening_position_observation_present": False,
    }:
        errors.append("declared listening environment differs")
    if playback.get("effects") != {
        "spatial_audio": False,
        "equalization": False,
        "loudness_normalization": False,
        "crossfade": False,
        "communications_ducking": False,
        "headphone_accommodations": False,
        "other_audio_effects": False,
    }:
        errors.append("declared audio-effects boundary differs")
    if playback.get("calibration") != {
        "method": "supplied_band_limited_signal_at_comfortable_conservative_level",
        "level_fixed_during_testing": True,
        "level_increase_during_testing_authorized": False,
        "listener_may_lower_level_or_stop": True,
        "observed": False,
    }:
        errors.append("declared calibration boundary differs")
    if playback.get("physical_playback_qualified") is not False:
        errors.append("physical playback was prematurely qualified")

    expected_claim_boundary = {
        "provider_references_are_actual_codec_conditions": False,
        "one_provider_proves_independent_transfer": False,
        "acquisition_authorizes_stimulus_generation": False,
        "acquisition_authorizes_listening_scores": False,
        "acquisition_authorizes_listener_collection": False,
    }
    if authorization.get("claim_boundary") != expected_claim_boundary:
        errors.append("authorization claim boundary differs")
    if "/Users/" in json.dumps(authorization, sort_keys=True):
        errors.append("authorization must not contain a private absolute path")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, default=AUTHORIZATION)
    parser.add_argument("--freeze", type=Path, default=FREEZE)
    args = parser.parse_args()
    errors = validate(load_json(args.authorization), load_json(args.freeze))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        json.dumps(
            {
                "authorization": str(args.authorization.relative_to(ROOT)),
                "authorization_sha256": CORE.sha256_file(args.authorization),
                "reference_count": 16,
                "status": "reference_only_acquisition_authorized",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
