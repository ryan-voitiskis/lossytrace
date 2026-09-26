#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "research" / "toolchains" / "evidence"
DEFAULT_BUILD = EVIDENCE / "visqol-synthetic-second-build-observed-20260803-001.json"
DEFAULT_COMPARISON = (
    EVIDENCE / "visqol-synthetic-cross-environment-observed-20260803-001.json"
)
FIRST_REPLAY = EVIDENCE / "visqol-synthetic-replay-observed-20260803-001.json"
FIRST_BINARY_SHA256 = "7384c8d21725e6fa3921aea4e66ff9cb9481b57acef868304192df437a467319"
SECOND_BINARY_SHA256 = "6c7807891cb5cb267649f09fbc20eecc22a3b2f62e50698e38134b2e08d18d5f"
MODEL_SHA256 = "1e8246ed33bf36dc5c859351f7110f2cd31f98661989715c0fcf974ec48d3e2e"
FIRST_REPLAY_SHA256 = "d21c8d0879ce0a5f1efeac5c8e38105b9c017d0c0777bc48655fc0916befe175"
SECOND_REPLAY_SHA256 = "5ab3210ec9f66e891e2343df22fd468f16ae1fdfe47bde4a86dd131b6b25affe"
COMPARISON_SHA256 = "63fdf3d6e4c85e42950d735f2a4bba2974bc23a464318708311a750177ae9c66"
EXPECTED_CASES = {
    "synthetic-identity",
    "synthetic-bandwidth-loss",
    "synthetic-tonal-noise",
    "synthetic-transient-smear",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(build: dict[str, Any], comparison: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    encoded = json.dumps({"build": build, "comparison": comparison}, sort_keys=True)
    for forbidden in (
        "/".join(("", "home", "runner", "")),
        "/".join(("", "Users", "")),
        "/".join(("Library", "Application Support")),
    ):
        if forbidden in encoded:
            errors.append(f"committed observation contains forbidden path: {forbidden}")

    if build.get("schema_version") != 1:
        errors.append("build schema_version must equal 1")
    if build.get("state") != "visqol_synthetic_cross_environment_observed":
        errors.append("second build observation state differs")
    plan = build.get("execution_plan", {})
    if plan.get("plan_id") != "visqol-audio-v3-3-3-synthetic-second-environment-20260803-003":
        errors.append("executed second plan identifier differs")
    if plan.get("sha256") != "52a8b899bd7b937d4d9ddab1dc347a1b5996cb49ba3fbfe81b4ac43d216505b3":
        errors.append("executed second plan hash differs")
    github = build.get("github", {})
    if github.get("run_id") != 30826870568:
        errors.append("second build run ID differs")
    if github.get("head_sha") != "1e960e95479fc5edca4e7dd7eb9da69714398ee6":
        errors.append("second build head differs")
    if github.get("workflow_conclusion") != "success":
        errors.append("second build workflow conclusion differs")
    artifact = build.get("artifact", {})
    if artifact.get("id") != 8861523671:
        errors.append("second artifact ID differs")
    if artifact.get("size_bytes") != 6534583:
        errors.append("second artifact size differs")
    if artifact.get("archive_sha256") != "1afdcf9d01c33031ddead3f6ec856097280444e6e350634e78da5ee90e2a1f22":
        errors.append("second artifact archive hash differs")

    environment = build.get("build_environment", {})
    if environment.get("runner_image") != "ubuntu24":
        errors.append("second runner image differs")
    if "13.3.0" not in environment.get("compiler", ""):
        errors.append("second compiler version differs")
    if environment.get("bazel") != "bazel 3.7.2":
        errors.append("second Bazel version differs")
    if environment.get("python") != "Python 3.12.3":
        errors.append("second Python version differs")
    if environment.get("numpy") != "1.26.4":
        errors.append("second NumPy version differs")
    if environment.get("compilation_mode") != "opt":
        errors.append("second build configuration differs")
    if environment.get("maximum_workers") != 6:
        errors.append("second worker ceiling differs")
    if environment.get("minimum_free_disk_gib_restored_after_build") != 15:
        errors.append("second disk reserve restoration differs")
    if environment.get("compatibility_header") != "cstdint":
        errors.append("second compatibility header differs")
    if environment.get("flatbuffers_locale_independent") is not True:
        errors.append("FlatBuffers locale-independent mode must be explicit")

    files = build.get("files", {})
    if files.get("binary", {}).get("sha256") != SECOND_BINARY_SHA256:
        errors.append("second binary hash differs")
    if files.get("binary", {}).get("bytes") != 6264312:
        errors.append("second binary size differs")
    if files.get("audio_model", {}).get("sha256") != MODEL_SHA256:
        errors.append("second model hash differs")
    replay = files.get("synthetic_replay", {})
    if replay.get("artifact_sha256") != SECOND_REPLAY_SHA256:
        errors.append("second replay artifact hash differs")
    if replay.get("first_replay_sha256") != FIRST_REPLAY_SHA256:
        errors.append("first replay binding differs")
    if replay.get("semantic_json_equality_after_removing_binary_sha256") is not True:
        errors.append("cross-environment replay semantic equality must be verified")
    comparison_file = files.get("cross_environment_comparison", {})
    if comparison_file.get("artifact_sha256") != COMPARISON_SHA256:
        errors.append("comparison artifact hash differs")
    if comparison_file.get("semantic_json_equality_verified") is not True:
        errors.append("comparison artifact equality must be verified")
    raw = files.get("raw_repository_resolution", {})
    if raw.get("sha256") != "186904be4d0b11f7f962f49115626aef7bed51cff5ec6f73fb407f5107299d2a":
        errors.append("second repository resolution hash differs")
    if raw.get("absolute_runner_paths_present") is not True or raw.get("committed") is not False:
        errors.append("raw repository resolution boundary differs")

    resolution = build.get("repository_resolution", {})
    names = resolution.get("repository_names", [])
    if resolution.get("repository_count") != 46 or len(names) != 46:
        errors.append("second repository resolution count differs")
    if names != sorted(set(names)):
        errors.append("second repository names must be unique and sorted")
    if resolution.get("matches_first_environment_name_projection") is not True:
        errors.append("repository projection equality must be verified")
    if resolution.get("raw_record_committed") is not False:
        errors.append("raw repository record must remain uncommitted")

    summary = build.get("synthetic_replay_summary", {})
    if summary.get("complete_replays_per_case") != 2:
        errors.append("second replay count differs")
    if summary.get("synthetic_case_count") != 4:
        errors.append("second synthetic case count differs")
    if summary.get("all_within_environment_numeric_replays_identical") is not True:
        errors.append("second within-environment replay differs")
    if summary.get("semantic_json_equality_to_first_environment_after_binary_removal") is not True:
        errors.append("second replay does not match first after binary removal")
    if summary.get("cross_environment_score_determinism_pass") is not True:
        errors.append("cross-environment determinism must pass")
    if summary.get("maximum_observed_absolute_delta") != 0:
        errors.append("maximum observed score delta must equal zero")
    if set(summary.get("case_result_sha256", {})) != EXPECTED_CASES:
        errors.append("second case-result hash set differs")

    if comparison.get("schema_version") != 1:
        errors.append("comparison schema_version must equal 1")
    if comparison.get("state") != "cross_environment_comparison_complete":
        errors.append("comparison state differs")
    if comparison.get("fixture_set_id") != "visqol-synthetic-48k-stereo-v1":
        errors.append("comparison fixture set differs")
    first = comparison.get("first_environment", {})
    second = comparison.get("second_environment", {})
    if first.get("binary_sha256") != FIRST_BINARY_SHA256:
        errors.append("comparison first binary differs")
    if second.get("binary_sha256") != SECOND_BINARY_SHA256:
        errors.append("comparison second binary differs")
    if FIRST_BINARY_SHA256 == SECOND_BINARY_SHA256:
        errors.append("cross-environment binaries must be independently distinct")
    tolerances = comparison.get("frozen_absolute_tolerances", {})
    if set(tolerances.values()) != {1e-12} or len(tolerances) != 4:
        errors.append("comparison tolerances differ")
    results = comparison.get("results", [])
    if {result.get("case_id") for result in results} != EXPECTED_CASES:
        errors.append("comparison case set differs")
    for result in results:
        case_id = result.get("case_id")
        if result.get("shape_identical") is not True:
            errors.append(f"comparison shape differs: {case_id}")
        if result.get("within_frozen_tolerance") is not True:
            errors.append(f"comparison tolerance failed: {case_id}")
        if result.get("comparison_pass") is not True:
            errors.append(f"comparison failed: {case_id}")
        if any(delta != 0 for delta in result.get("absolute_deltas", {}).values()):
            errors.append(f"comparison delta is nonzero: {case_id}")
    if comparison.get("score_determinism_pass") is not True:
        errors.append("cross-environment score determinism must pass")
    if comparison.get("comparison_complete") is not True:
        errors.append("comparison must be complete")

    boundaries = build.get("boundaries", {})
    if boundaries.get("synthetic_audio_only") is not True:
        errors.append("second observation must remain synthetic-only")
    if boundaries.get("cross_environment_replay_complete") is not True:
        errors.append("build must record completed cross-environment replay")
    for key in (
        "audio_files_committed",
        "binary_or_model_committed",
        "public_or_provider_audio_accessed",
        "retained_audio_accessed",
        "sealed_labels_opened",
        "existing_280_case_future_subset_opened",
        "human_listening_scores_opened",
        "synthetic_scores_are_human_truth",
        "audibility_or_materiality_threshold_selected",
        "public_verdict_enabled",
        "paths_in_committed_evidence",
    ):
        if boundaries.get(key) is not False:
            errors.append(f"second build boundary must remain false: {key}")
    for key in (
        "audibility_or_materiality_threshold_selected",
        "existing_280_case_future_subset_opened",
        "human_listening_scores_opened",
        "paths_included",
        "public_or_provider_audio_accessed",
        "public_verdict_enabled",
        "retained_audio_accessed",
        "retained_metric_scores_opened",
        "sealed_labels_opened",
        "synthetic_scores_are_human_truth",
    ):
        if comparison.get(key) is not False:
            errors.append(f"comparison boundary must remain false: {key}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, default=DEFAULT_BUILD)
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    args = parser.parse_args()
    build_path = args.build.resolve()
    comparison_path = args.comparison.resolve()
    build = json.loads(build_path.read_text(encoding="utf-8"))
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    errors = validate(build, comparison)
    if sha256_file(FIRST_REPLAY) != FIRST_REPLAY_SHA256:
        errors.append("first replay file hash differs")
    if sha256_file(comparison_path) != COMPARISON_SHA256:
        errors.append("committed comparison file hash differs")
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print(
        json.dumps(
            {
                "build": str(build_path.relative_to(ROOT)),
                "comparison": str(comparison_path.relative_to(ROOT)),
                "maximum_observed_absolute_delta": 0,
                "status": "cross_environment_synthetic_score_determinism_observed",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
