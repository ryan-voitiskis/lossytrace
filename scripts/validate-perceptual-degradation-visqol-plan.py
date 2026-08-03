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
    / "visqol-synthetic-replay-plan.json"
)
EXPECTED_COMMIT = "c3aa2e498e0f7f14202643594335a0b9ee40bdd9"
EXPECTED_TREE = "7a0c95a103c4ba40d6337f06f80848e571b00b3c"
EXPECTED_MODEL_SHA256 = "1e8246ed33bf36dc5c859351f7110f2cd31f98661989715c0fcf974ec48d3e2e"
EXPECTED_BAZEL_SHA256 = "70dc0bee198a4c3d332925a32d464d9036a831977501f66d4996854ad4e4fc0d"
EXPECTED_NUMPY_SHA256 = "5f30427731561ce75d7048ac254dbe47a2ba576229250fb60f0fb74db96501a1"


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
        errors.append("ViSQOL plan must remain frozen before synthetic scores")

    authorization = plan.get("authorization", {})
    if authorization.get("synthetic_fixture_execution") is not True:
        errors.append("synthetic fixture execution must be explicitly authorized")
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
    if visqol.get("binary_sha256") is not None:
        errors.append("ViSQOL binary hash must remain null before replay")

    environment = plan.get("build_environment", {})
    if environment.get("runner") != "ubuntu-22.04":
        errors.append("build runner differs")
    if environment.get("maximum_workers") != 6:
        errors.append("build worker ceiling must equal six")
    if environment.get("minimum_local_free_disk_gib") != 15:
        errors.append("local free-disk reserve must equal 15 GiB")
    bazel = environment.get("bazel", {})
    if bazel.get("version") != "3.7.2":
        errors.append("Bazel version differs")
    if bazel.get("binary_sha256") != EXPECTED_BAZEL_SHA256:
        errors.append("Bazel binary hash differs")
    python = environment.get("python", {})
    if python.get("major_minor") != "3.10":
        errors.append("Python major/minor differs")
    numpy_wheel = python.get("numpy_wheel", {})
    if numpy_wheel.get("version") != "1.21.6":
        errors.append("NumPy bootstrap version differs")
    if numpy_wheel.get("sha256") != EXPECTED_NUMPY_SHA256:
        errors.append("NumPy bootstrap wheel hash differs")
    if numpy_wheel.get("bytes") != 15906004:
        errors.append("NumPy bootstrap wheel size differs")
    expected_numpy_filename = (
        "numpy-1.21.6-cp310-cp310-manylinux_2_17_x86_64."
        "manylinux2014_x86_64.whl"
    )
    if numpy_wheel.get("filename") != expected_numpy_filename:
        errors.append("NumPy bootstrap wheel filename differs")
    if not numpy_wheel.get("download_url", "").endswith(
        f"/{expected_numpy_filename}"
    ):
        errors.append("NumPy bootstrap wheel ABI differs")
    if environment.get("build_configuration") != "opt":
        errors.append("ViSQOL build configuration must remain opt")

    attempts = plan.get("prior_attempts", [])
    if len(attempts) != 3:
        errors.append("exactly three score-free prior attempts must be recorded")
    for attempt in attempts:
        if attempt.get("synthetic_scores_produced") is not False:
            errors.append("prior failed attempt must not claim synthetic scores")

    generation = plan.get("fixture_generation", {})
    if generation.get("duration_seconds", 0) < 8:
        errors.append("synthetic fixtures must be at least eight seconds")
    if generation.get("sample_rate_hz") != 48000:
        errors.append("synthetic fixtures must be 48 kHz")
    if generation.get("channel_count") != 2:
        errors.append("synthetic fixtures must be stereo")
    files = set(generation.get("files", {}))
    expected_files = {
        "synthetic-reference.wav",
        "synthetic-bandwidth-loss.wav",
        "synthetic-tonal-noise.wav",
        "synthetic-transient-smear.wav",
    }
    if files != expected_files:
        errors.append("synthetic fixture file set differs")
    for name, record in generation.get("files", {}).items():
        if record.get("bytes", 0) <= 44 or len(record.get("sha256", "")) != 64:
            errors.append(f"invalid fixture binding: {name}")

    cases = plan.get("synthetic_cases", [])
    if {case.get("case_id") for case in cases} != {
        "synthetic-identity",
        "synthetic-bandwidth-loss",
        "synthetic-tonal-noise",
        "synthetic-transient-smear",
    }:
        errors.append("synthetic replay case set differs")
    for case in cases:
        if case.get("reference_file") != "synthetic-reference.wav":
            errors.append(f"synthetic reference differs: {case.get('case_id')}")
        if case.get("degraded_file") not in expected_files:
            errors.append(f"synthetic degraded file differs: {case.get('case_id')}")

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
                "status": "synthetic_only_execution_authorized",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
