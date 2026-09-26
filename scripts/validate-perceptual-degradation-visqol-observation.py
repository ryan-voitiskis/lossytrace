#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUILD = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "visqol-synthetic-build-observed-20260803-001.json"
)
DEFAULT_REPLAY = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "visqol-synthetic-replay-observed-20260803-001.json"
)
EXPECTED_BINARY_SHA256 = "7384c8d21725e6fa3921aea4e66ff9cb9481b57acef868304192df437a467319"
EXPECTED_MODEL_SHA256 = "1e8246ed33bf36dc5c859351f7110f2cd31f98661989715c0fcf974ec48d3e2e"
EXPECTED_REPLAY_SHA256 = "d21c8d0879ce0a5f1efeac5c8e38105b9c017d0c0777bc48655fc0916befe175"
EXPECTED_CASES = {
    "synthetic-identity",
    "synthetic-bandwidth-loss",
    "synthetic-tonal-noise",
    "synthetic-transient-smear",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(build: dict[str, Any], replay: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    encoded = json.dumps({"build": build, "replay": replay}, sort_keys=True)
    forbidden_paths = (
        "/".join(("", "home", "runner", "")),
        "/".join(("", "Users", "")),
        "/".join(("Library", "Application Support")),
    )
    for forbidden in forbidden_paths:
        if forbidden in encoded:
            errors.append(f"committed observation contains forbidden path: {forbidden}")

    if replay.get("schema_version") != 1:
        errors.append("replay schema_version must equal 1")
    if replay.get("state") != "visqol_synthetic_replay_passed_not_human_truth":
        errors.append("replay state differs")
    if replay.get("metric_family") != "visqol_audio_v3_3_3":
        errors.append("replay metric family differs")
    if replay.get("binary_sha256") != EXPECTED_BINARY_SHA256:
        errors.append("replay binary hash differs")
    if replay.get("audio_model_sha256") != EXPECTED_MODEL_SHA256:
        errors.append("replay model hash differs")
    source = replay.get("source", {})
    if source.get("git_commit") != "c3aa2e498e0f7f14202643594335a0b9ee40bdd9":
        errors.append("replay source commit differs")
    if source.get("git_tree") != "7a0c95a103c4ba40d6337f06f80848e571b00b3c":
        errors.append("replay source tree differs")
    results = replay.get("results", [])
    if {result.get("case_id") for result in results} != EXPECTED_CASES:
        errors.append("replay synthetic case set differs")
    for result in results:
        case_id = result.get("case_id")
        if result.get("complete_replays") != 2:
            errors.append(f"replay count differs: {case_id}")
        if result.get("numeric_replay_identical") is not True:
            errors.append(f"numeric replay differs: {case_id}")
        if result.get("stderr_observed") is not True:
            errors.append(f"diagnostic observation differs: {case_id}")
        if result.get("patch_count") != 12:
            errors.append(f"patch count differs: {case_id}")
        if len(result.get("patch_similarity", [])) != 12:
            errors.append(f"patch vector length differs: {case_id}")
        if len(result.get("band_similarity", [])) != 32:
            errors.append(f"band vector length differs: {case_id}")
        for key in ("mos_lqo", "similarity"):
            if not isinstance(result.get(key), (int, float)) or not math.isfinite(
                result[key]
            ):
                errors.append(f"invalid numeric result {key}: {case_id}")
        if len(result.get("complete_result_sha256", "")) != 64:
            errors.append(f"complete result hash differs: {case_id}")
    identity = next(
        (item for item in results if item.get("case_id") == "synthetic-identity"),
        {},
    )
    if identity.get("similarity") != 1:
        errors.append("identity similarity must equal one")

    for key in (
        "cross_environment_replay_complete",
        "existing_280_case_future_subset_opened",
        "human_listening_scores_opened",
        "paths_included",
        "public_or_provider_audio_accessed",
        "public_verdict_enabled",
        "retained_audio_accessed",
        "retained_metric_scores_opened",
        "sealed_labels_opened",
        "synthetic_scores_are_human_truth",
        "threshold_selected",
    ):
        if replay.get(key) is not False:
            errors.append(f"replay boundary must remain false: {key}")
    if replay.get("synthetic_metric_scores_opened") is not True:
        errors.append("synthetic metric scores must be explicitly recorded as opened")

    if build.get("schema_version") != 1:
        errors.append("build schema_version must equal 1")
    if build.get("state") != "visqol_synthetic_build_observed_single_environment":
        errors.append("build observation state differs")
    execution_plan = build.get("execution_plan", {})
    if execution_plan.get("sha256") != "c029e9bb2617eee83eebf32d020087e2404090b38ffdf92dd6842c5599c7b698":
        errors.append("executed plan hash differs")
    github = build.get("github", {})
    if github.get("run_id") != 30822439141:
        errors.append("build run ID differs")
    if github.get("head_sha") != "38d88f11e0c31c478ab0b20013f2f0bb6125b13d":
        errors.append("build head differs")
    if github.get("workflow_conclusion") != "success":
        errors.append("build workflow conclusion differs")
    environment = build.get("build_environment", {})
    if environment.get("runner_image") != "ubuntu22":
        errors.append("build runner image differs")
    if environment.get("bazel") != "bazel 3.7.2":
        errors.append("build Bazel version differs")
    if environment.get("python") != "Python 3.10.12":
        errors.append("build Python version differs")
    if environment.get("numpy") != "1.21.6":
        errors.append("build NumPy version differs")
    if environment.get("compilation_mode") != "opt":
        errors.append("build compilation mode differs")
    if environment.get("maximum_workers") != 6:
        errors.append("build worker ceiling differs")
    files = build.get("files", {})
    if files.get("binary", {}).get("sha256") != EXPECTED_BINARY_SHA256:
        errors.append("build binary hash differs")
    if files.get("audio_model", {}).get("sha256") != EXPECTED_MODEL_SHA256:
        errors.append("build model hash differs")
    replay_file = files.get("synthetic_replay", {})
    if replay_file.get("committed_sha256") != EXPECTED_REPLAY_SHA256:
        errors.append("committed replay hash binding differs")
    if replay_file.get("semantic_json_equality_verified") is not True:
        errors.append("artifact/committed replay semantic equality is not verified")
    raw_resolution = files.get("raw_repository_resolution", {})
    if raw_resolution.get("absolute_runner_paths_present") is not True:
        errors.append("raw repository path boundary differs")
    if raw_resolution.get("committed") is not False:
        errors.append("raw repository resolution record must not be committed")
    resolution = build.get("repository_resolution", {})
    names = resolution.get("repository_names", [])
    if resolution.get("repository_count") != 46 or len(names) != 46:
        errors.append("repository resolution count differs")
    if names != sorted(set(names)):
        errors.append("repository names must be unique and sorted")
    if resolution.get("raw_record_committed") is not False:
        errors.append("raw repository record must remain uncommitted")
    boundaries = build.get("boundaries", {})
    if boundaries.get("synthetic_audio_only") is not True:
        errors.append("build must remain synthetic-audio-only")
    for key in (
        "audio_files_committed",
        "binary_or_model_committed",
        "public_or_provider_audio_accessed",
        "retained_audio_accessed",
        "sealed_labels_opened",
        "existing_280_case_future_subset_opened",
        "human_listening_scores_opened",
        "threshold_selected",
        "cross_environment_replay_complete",
        "public_verdict_enabled",
        "paths_in_committed_evidence",
    ):
        if boundaries.get(key) is not False:
            errors.append(f"build boundary must remain false: {key}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, default=DEFAULT_BUILD)
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY)
    args = parser.parse_args()
    build_path = args.build.resolve()
    replay_path = args.replay.resolve()
    build = json.loads(build_path.read_text(encoding="utf-8"))
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    errors = validate(build, replay)
    if sha256_file(replay_path) != EXPECTED_REPLAY_SHA256:
        errors.append("committed replay file hash differs")
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print(
        json.dumps(
            {
                "binary_sha256": replay["binary_sha256"],
                "build": str(build_path.relative_to(ROOT)),
                "replay": str(replay_path.relative_to(ROOT)),
                "status": "single_environment_synthetic_replay_observed",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
