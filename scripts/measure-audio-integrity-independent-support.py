#!/usr/bin/env python3
"""Measure frozen low-bandwidth support for the independent v29 gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = (
    ROOT / "scripts" / "measure-audio-integrity-low-bandwidth-support.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audio_integrity_support_measurement_base",
    BASE_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise SystemExit(f"cannot load support measurement base: {BASE_PATH}")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

CANDIDATE_ID = "verified-mp3-two-grid-edge-v29-independent-transfer-v1"
PROFILE = "verified-mp3-two-grid-v29"
EXPECTED_CASE_COUNT = 436

BASE.CANDIDATE_ID = CANDIDATE_ID
BASE.PROFILE = PROFILE
BASE.__file__ = str(Path(__file__).resolve())


def validate_contract(
    *,
    manifest_path: Path,
    manifest: dict,
    fingerprints_path: Path,
    fingerprints: dict,
    precommit_path: Path,
    precommit: dict,
    policy_path: Path,
) -> None:
    corpus_plan = precommit.get("corpus_plan", {})
    tools = precommit.get("tools", {})
    plan_path = Path(corpus_plan.get("path", "")).expanduser().resolve()
    plan = BASE.load_json(plan_path)
    cases = manifest.get("cases", [])
    if (
        precommit.get("schema_version") != 1
        or precommit.get("state") != "frozen_before_external_transfer"
        or precommit.get("candidate_id") != CANDIDATE_ID
        or precommit.get("candidate_frozen") is not True
        or precommit.get("external_transfer_feature_scores_opened")
        is not False
        or precommit.get("release_heldout_opened") is not False
        or precommit.get("public_verdict_enabled") is not False
        or precommit.get("feature_version") != 0
        or precommit.get("transform_profile") != PROFILE
        or corpus_plan.get("sha256") != BASE.sha256_file(plan_path)
        or tools.get("low_bandwidth_probe_sha256")
        != BASE.sha256_file(Path(__file__).resolve())
        or tools.get("base_low_bandwidth_probe_sha256")
        != BASE.sha256_file(BASE_PATH)
        or tools.get("policy_module_sha256")
        != BASE.sha256_file(policy_path)
        or manifest != plan.get("manifest")
        or fingerprints.get("corpus_id") != manifest.get("corpus_id")
        or set(fingerprints.get("case_sha256", {}))
        != {case["case_id"] for case in cases}
        or any(case.get("split") != "held_out" for case in cases)
        or len(cases) != EXPECTED_CASE_COUNT
    ):
        raise SystemExit("frozen independent support contract differs")
    retained_plan = manifest_path.parent / "corpus-plan.json"
    retained_precommit = manifest_path.parent / "candidate-precommit.json"
    if (
        not retained_plan.is_file()
        or BASE.load_json(retained_plan) != plan
        or not retained_precommit.is_file()
        or BASE.load_json(retained_precommit) != precommit
        or BASE.sha256_file(fingerprints_path)
        != BASE.sha256_file(manifest_path.parent / "fingerprints.json")
    ):
        raise SystemExit("retained independent commitments differ")


BASE.validate_contract = validate_contract


if __name__ == "__main__":
    raise SystemExit(BASE.main())
