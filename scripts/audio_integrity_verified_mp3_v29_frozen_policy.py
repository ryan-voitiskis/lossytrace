#!/usr/bin/env python3
"""Frozen v29 policy for the independent one-use external-transfer gate."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts" / "audio_integrity_verified_mp3_v29_policy.py"
SPEC = importlib.util.spec_from_file_location(
    "audio_integrity_verified_mp3_v29_development_policy",
    BASE_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load development policy: {BASE_PATH}")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

CANDIDATE_ID = "verified-mp3-two-grid-edge-v29-independent-transfer-v1"
POLICY_ID = BASE.POLICY_ID
PROFILE = BASE.PROFILE

for _name in (
    "MP3_VERIFICATION_MEDIAN_THRESHOLD",
    "VORBIS_AGGREGATE_THRESHOLD",
    "RELATIVE_MEDIAN_THRESHOLD",
    "EDGE_DROP_THRESHOLD_DB",
    "EDGE_PERSISTENCE_THRESHOLD",
    "MP3_VERIFICATION_MINIMUM_AUDIO_BLOCK_COUNT",
    "MP3_VERIFICATION_MAXIMUM_AUDIO_BLOCK_COUNT",
    "MP3_VERIFICATION_FRAMES_PER_PHASE",
    "MP3_VERIFICATION_CONTROL_PHASE_STRIDE",
    "MINIMUM_ACTIVE_BIN_FRACTION",
    "MINIMUM_HIGH_BAND_FRAMES",
    "MINIMUM_HIGH_BAND_FRAME_RATIO",
    "ACTIVE_BIN_REFERENCE_SAMPLE_RATE_HZ",
    "LOW_UPPER_BAND_POWER_SHARE",
    "LOW_EDGE_DROP_DB",
    "LOW_EDGE_PERSISTENCE",
    "LOW_EDGE_UPPER_POWER_SHARE",
):
    globals()[_name] = getattr(BASE, _name)


def contract() -> dict:
    value = copy.deepcopy(BASE.contract())
    value["candidate_id"] = CANDIDATE_ID
    value["candidate_frozen"] = True
    value["development_candidate_id"] = BASE.DEVELOPMENT_CANDIDATE_ID
    value["evidence_status"] = (
        "Frozen for one use on the provenance-locked independent PCM "
        "external-transfer corpus. Public verdict remains disabled and "
        "the separate release-held-out corpus remains sealed."
    )
    value["one_use_rule"] = (
        "After any independent external-transfer feature score is opened, "
        "this exact policy may only pass or fail unchanged."
    )
    return value


def support(runner: dict, low_bandwidth: dict) -> dict:
    return BASE.support(runner, low_bandwidth)


def assess(runner: dict, low_bandwidth: dict) -> dict:
    return BASE.assess(runner, low_bandwidth)


def _circular_distance(left: int, right: int, period: int) -> int:
    return BASE._circular_distance(left, right, period)
