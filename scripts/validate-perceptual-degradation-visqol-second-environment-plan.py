#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "visqol-synthetic-second-environment-plan.json"
)
EXPECTED_COMMIT = "c3aa2e498e0f7f14202643594335a0b9ee40bdd9"
EXPECTED_TREE = "7a0c95a103c4ba40d6337f06f80848e571b00b3c"
EXPECTED_MODEL_SHA256 = "1e8246ed33bf36dc5c859351f7110f2cd31f98661989715c0fcf974ec48d3e2e"
EXPECTED_PATCH_SHA256 = "d768dc5d312d874d308937454308b48c9ff172a7e648e6314cf2b51110e6a039"
EXPECTED_BAZEL_SHA256 = "70dc0bee198a4c3d332925a32d464d9036a831977501f66d4996854ad4e4fc0d"
EXPECTED_NUMPY_SHA256 = "675d61ffbfa78604709862923189bad94014bef562cc35cf61d3a07bba02a7ed"
EXPECTED_FIRST_REPLAY_SHA256 = "d21c8d0879ce0a5f1efeac5c8e38105b9c017d0c0777bc48655fc0916befe175"
EXPECTED_SETUP_PYTHON_COMMIT = "5fda3b95a4ea91299a34e894583c3862153e4b97"
EXPECTED_CASES = {
    "synthetic-identity",
    "synthetic-bandwidth-loss",
    "synthetic-tonal-noise",
    "synthetic-transient-smear",
}
EXPECTED_FILES = {
    "synthetic-reference.wav",
    "synthetic-bandwidth-loss.wav",
    "synthetic-tonal-noise.wav",
    "synthetic-transient-smear.wav",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(plan: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if plan.get("state") != "visqol_synthetic_build_and_replay_frozen_before_scores":
        errors.append("second-environment plan must be frozen before scores")

    authorization = plan.get("authorization", {})
    if authorization.get("synthetic_fixture_execution") is not True:
        errors.append("only synthetic fixture execution must be authorized")
    for key in (
        "public_or_retained_audio_execution",
        "human_listening_score_access",
        "retained_audio_access",
        "provider_audio_download",
        "no_reference_training",
        "public_verdict",
    ):
        if authorization.get(key) is not False:
            errors.append(f"authorization.{key} must remain false")

    visqol = plan.get("visqol", {})
    if visqol.get("git_commit") != EXPECTED_COMMIT:
        errors.append("ViSQOL commit differs")
    if visqol.get("git_tree") != EXPECTED_TREE:
        errors.append("ViSQOL tree differs")
    if visqol.get("audio_model_sha256") != EXPECTED_MODEL_SHA256:
        errors.append("ViSQOL audio model hash differs")
    if visqol.get("workspace_patch_sha256") != EXPECTED_PATCH_SHA256:
        errors.append("ViSQOL workspace patch hash differs")
    if visqol.get("binary_sha256") is not None:
        errors.append("second-environment binary must remain unknown before build")
    if visqol.get("synthetic_replay_complete") is not False:
        errors.append("second-environment replay must remain incomplete before execution")

    environment = plan.get("build_environment", {})
    if environment.get("runner") != "ubuntu-24.04":
        errors.append("second runner must equal ubuntu-24.04")
    if environment.get("architecture") != "x86_64":
        errors.append("second architecture must equal x86_64")
    if environment.get("maximum_workers") != 6:
        errors.append("build worker ceiling must equal six")
    if environment.get("minimum_local_free_disk_gib") != 15:
        errors.append("local free-disk reserve must equal 15 GiB")
    if environment.get("persistent_local_build_authorized") is not False:
        errors.append("persistent local build must remain unauthorized")
    if environment.get("ephemeral_remote_build_authorized") is not True:
        errors.append("exact ephemeral second-environment build must be authorized")
    compiler = environment.get("compiler", {})
    if compiler != {
        "cc": "/usr/bin/gcc-13",
        "cxx": "/usr/bin/g++-13",
        "expected_full_version": "13.3.0",
    }:
        errors.append("second compiler binding differs")
    bazel = environment.get("bazel", {})
    if bazel.get("version") != "3.7.2" or bazel.get("binary_sha256") != EXPECTED_BAZEL_SHA256:
        errors.append("Bazel binding differs")
    python = environment.get("python", {})
    if python.get("version") != "3.12.3":
        errors.append("Python version differs")
    setup = python.get("setup_action", {})
    if setup.get("repository") != "actions/setup-python" or setup.get("git_commit") != EXPECTED_SETUP_PYTHON_COMMIT:
        errors.append("setup-python binding differs")
    wheel = python.get("numpy_wheel", {})
    expected_filename = (
        "numpy-1.26.4-cp312-cp312-manylinux_2_17_x86_64."
        "manylinux2014_x86_64.whl"
    )
    if wheel.get("version") != "1.26.4":
        errors.append("NumPy bootstrap version differs")
    if wheel.get("filename") != expected_filename:
        errors.append("NumPy bootstrap wheel filename differs")
    if wheel.get("sha256") != EXPECTED_NUMPY_SHA256 or wheel.get("bytes") != 17950613:
        errors.append("NumPy bootstrap wheel bytes differ")
    if not wheel.get("download_url", "").endswith(f"/{expected_filename}"):
        errors.append("NumPy bootstrap wheel ABI differs")
    if environment.get("build_target") != "//:visqol" or environment.get("build_configuration") != "opt":
        errors.append("ViSQOL build target or configuration differs")

    generation = plan.get("fixture_generation", {})
    if generation.get("sample_rate_hz") != 48000 or generation.get("channel_count") != 2:
        errors.append("synthetic fixture audio format differs")
    if generation.get("duration_seconds") != 8 or generation.get("frames") != 384000:
        errors.append("synthetic fixture duration differs")
    if set(generation.get("files", {})) != EXPECTED_FILES:
        errors.append("synthetic fixture file set differs")
    if {case.get("case_id") for case in plan.get("synthetic_cases", [])} != EXPECTED_CASES:
        errors.append("synthetic case set differs")

    comparison = plan.get("cross_environment_comparison", {})
    if comparison.get("first_environment_id") != "ubuntu22-gcc11-python310-v1":
        errors.append("first environment identifier differs")
    if comparison.get("second_environment_id") != "ubuntu24-gcc13-python312-v1":
        errors.append("second environment identifier differs")
    if comparison.get("first_replay_path") != "research/toolchains/evidence/visqol-synthetic-replay-observed-20260803-001.json":
        errors.append("first replay path differs")
    if comparison.get("first_replay_sha256") != EXPECTED_FIRST_REPLAY_SHA256:
        errors.append("first replay hash differs")
    for key in (
        "mos_lqo_absolute_tolerance",
        "similarity_absolute_tolerance",
        "band_similarity_absolute_tolerance",
        "patch_similarity_absolute_tolerance",
    ):
        if comparison.get(key) != 1e-12:
            errors.append(f"{key} must equal the frozen 1e-12 tolerance")
    if comparison.get("array_shapes_must_match_exactly") is not True:
        errors.append("comparison array shapes must match exactly")
    if comparison.get("within_environment_numeric_replay_must_be_exact") is not True:
        errors.append("within-environment numeric replay must remain exact")
    if comparison.get("tolerance_is_audibility_or_materiality_threshold") is not False:
        errors.append("numeric tolerance must not be a perceptual threshold")

    encoded = json.dumps(plan, sort_keys=True).lower()
    for forbidden in (
        "expected_mos",
        "expected_score",
        "quality_threshold",
        "material_threshold",
        "listening_result",
    ):
        if forbidden in encoded:
            errors.append(f"score-bearing field is forbidden before replay: {forbidden}")

    for key, binding in plan.get("bindings", {}).items():
        relative = binding.get("path", "")
        path = root / relative
        if not path.is_file():
            errors.append(f"missing bound file {key}: {relative}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"hash mismatch for bound file {key}: {relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", nargs="?", type=Path, default=DEFAULT_PLAN)
    args = parser.parse_args()
    plan_path = args.plan.resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    errors = validate(plan)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print(
        json.dumps(
            {
                "plan": str(plan_path.relative_to(ROOT)),
                "plan_sha256": sha256_file(plan_path),
                "status": "second_environment_frozen_before_scores",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
