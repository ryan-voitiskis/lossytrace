#!/usr/bin/env python3
"""Freeze the v29 candidate before independent gate features are opened."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


CANDIDATE_ID = "verified-mp3-two-grid-edge-v29-independent-transfer-v1"
PROFILE = "verified-mp3-two-grid-v29"
EXPECTED_SOURCE_COUNT = 36
EXPECTED_CASE_COUNT = 436
EXPECTED_NEGATIVE_COUNT = 144
INVARIANT_SOURCE_COUNT = 10
SCOPED_CLASSES = {
    "independent_aac_at_128_to_flac16",
    "independent_aac_lc_128_to_flac16",
    "independent_mp3_128_to_flac16",
    "independent_vorbis_native_q3_to_flac16",
}
DIFFICULT_CLASSES = {
    "independent_aac_lc_192_to_flac16",
    "independent_mp3_320_to_flac16",
    "independent_opus_96_to_flac16",
}
NEGATIVE_CLASSES = {
    "independent_pcm_reference_wav16",
    "independent_pcm_sharp_lowpass_16000_flac16",
    "independent_pcm_lowpass_19000_flac16",
    "independent_pcm_resample_32000_44100_flac16",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_new_json(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace precommit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def committed_file(path: Path) -> dict:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise SystemExit(f"committed file is missing: {resolved}")
    return {
        "path": str(resolved),
        "sha256": sha256_file(resolved),
        "bytes": resolved.stat().st_size,
    }


def command_version(path: Path) -> str:
    return subprocess.run(
        [str(path), "-version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "acquisition",
        "acquisition_tool",
        "corpus_plan",
        "observed_evaluation",
        "policy_equivalence",
        "performance_report",
        "runner",
        "runner_source",
        "cargo_lock",
        "dsp_cargo_toml",
        "development_policy",
        "policy_module",
        "stager",
        "base_stager",
        "low_bandwidth_probe",
        "base_low_bandwidth_probe",
        "external_runner",
        "base_external_runner",
        "evaluator",
        "base_evaluator",
    ):
        parser.add_argument(
            f"--{name.replace('_', '-')}",
            type=Path,
            required=True,
        )
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = {
        name: value.expanduser().resolve()
        for name, value in vars(args).items()
        if isinstance(value, Path) and name != "output"
    }
    files = {
        name: committed_file(path) for name, path in paths.items()
    }
    acquisition = load_json(paths["acquisition"])
    plan = load_json(paths["corpus_plan"])
    observed = load_json(paths["observed_evaluation"])
    equivalence = load_json(paths["policy_equivalence"])
    performance = load_json(paths["performance_report"])
    policy = load_module("frozen_v29_policy", paths["policy_module"])
    stager = load_module("independent_stager", paths["stager"])

    overall = observed.get("observed_metrics", {}).get("overall", {})
    scoped = observed.get("observed_metrics", {}).get(
        "scoped_recall",
        {},
    )
    invariance = observed.get("invariance", {})
    performance_p95 = float(
        performance.get("summary", {}).get(
            "p95_wall_time_overhead_percent",
            math.nan,
        )
    )
    if (
        acquisition.get("state") != "acquisition_complete"
        or acquisition.get("completed_count") != EXPECTED_SOURCE_COUNT
        or acquisition.get("feature_scores_opened") is not False
        or acquisition.get("release_heldout_opened") is not False
        or plan.get("state")
        != "planned_before_external_transfer_feature_opening"
        or plan.get("corpus", {}).get("source_count")
        != EXPECTED_SOURCE_COUNT
        or plan.get("corpus", {}).get("case_count")
        != EXPECTED_CASE_COUNT
        or plan.get("corpus", {}).get("negative_count")
        != EXPECTED_NEGATIVE_COUNT
        or plan.get("corpus", {}).get("provider_counts")
        != {"demand-v1.0": 18, "maestro-v3.0.0": 18}
        or plan.get("corpus", {}).get("invariant_source_count")
        != INVARIANT_SOURCE_COUNT
        or plan.get("external_transfer_feature_scores_opened")
        is not False
        or plan.get("release_heldout_opened") is not False
        or plan.get("acquisition", {}).get("sha256")
        != sha256_file(paths["acquisition"])
        or plan.get("tool", {}).get("sha256")
        != sha256_file(paths["stager"])
        or plan.get("tool", {}).get("base_sha256")
        != sha256_file(paths["base_stager"])
        or observed.get("state")
        != "observed_development_candidate_screen"
        or observed.get("development_screen", {}).get("passed") is not True
        or observed.get("candidate_frozen") is not False
        or observed.get("development_screen", {}).get(
            "external_transfer_gate_passed"
        )
        is not False
        or observed.get("development_screen", {}).get(
            "release_gate_passed"
        )
        is not False
        or overall.get("false_positive_count") != 0
        or overall.get("supported_negative_count") != 796
        or not scoped
        or not all(value.get("passed") is True for value in scoped.values())
        or not invariance
        or not all(
            value.get("mismatch_source_group_count") == 0
            for value in invariance.values()
        )
        or equivalence.get("state")
        != "observed_frozen_policy_replay_verified"
        or equivalence.get("passed") is not True
        or equivalence.get("case_count") != 3404
        or equivalence.get("mismatch_count") != 0
        or equivalence.get("inputs", {})
        .get("frozen_policy", {})
        .get("sha256")
        != sha256_file(paths["policy_module"])
        or performance.get("method", {}).get("transform_grid_profile")
        != PROFILE
        or performance.get("case_count") != 16
        or not math.isfinite(performance_p95)
        or performance_p95 > 10.0
        or performance.get("commitments", {}).get("runner_sha256")
        != sha256_file(paths["runner"])
        or policy.CANDIDATE_ID != CANDIDATE_ID
        or policy.PROFILE != PROFILE
        or policy.contract().get("candidate_frozen") is not True
        or policy.contract().get("public_verdict_enabled") is not False
        or policy.contract().get("feature_version") != 0
    ):
        raise SystemExit("independent candidate freeze prerequisite differs")

    ffmpeg = Path(args.ffmpeg).expanduser().resolve()
    ffprobe = Path(args.ffprobe).expanduser().resolve()
    ffmpeg_version = command_version(ffmpeg)
    ffprobe_version = command_version(ffprobe)
    required_encoders = [
        "aac",
        "aac_at",
        "flac",
        "libmp3lame",
        "libopus",
        "vorbis",
    ]
    encoder_output = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-encoders"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    available_encoders = {
        fields[1]
        for line in encoder_output.splitlines()
        if len(fields := line.split()) >= 2
    }
    missing = sorted(set(required_encoders) - available_encoders)
    if missing:
        raise SystemExit(
            "FFmpeg lacks required encoders: " + ", ".join(missing)
        )
    capability = stager.BASE.validate_ffmpeg_plan_capabilities(
        str(ffmpeg),
        plan,
    )
    analysis_packages = {}
    for package in ("numpy",):
        try:
            analysis_packages[package] = version(package)
        except PackageNotFoundError as error:
            raise SystemExit(
                f"analysis package is missing: {package}"
            ) from error

    git_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    git_diff = subprocess.run(
        ["git", "diff", "--binary", "--no-ext-diff"],
        check=True,
        capture_output=True,
    ).stdout
    git_untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        check=True,
        capture_output=True,
    ).stdout
    gate = {
        "maximum_tier_a_negative_false_positive_count": 0,
        "minimum_supported_recall_per_scoped_class": 0.90,
        "minimum_support_coverage_per_scoped_class": 0.75,
        "scoped_classes": sorted(SCOPED_CLASSES),
        "difficult_classes": sorted(DIFFICULT_CLASSES),
        "hard_negative_classes": sorted(NEGATIVE_CLASSES),
        "aac_invariant_source_group_count": INVARIANT_SOURCE_COUNT,
        "maximum_aac_invariant_mismatch_source_groups": 0,
        "required_positive_reason_families": [
            "persistent_spectral_edge",
            "transform_frame_periodicity",
        ],
        "maximum_p95_runtime_overhead_percent": 10.0,
        "minimum_independent_source_groups": EXPECTED_SOURCE_COUNT,
        "required_provider_source_groups": {
            "demand-v1.0": 18,
            "maestro-v3.0.0": 18,
        },
    }
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": acquisition["run_id"],
        "state": "frozen_before_external_transfer",
        "candidate_id": CANDIDATE_ID,
        "candidate_frozen": True,
        "external_transfer_feature_scores_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "feature_version": 0,
        "cache_schema_version": 21,
        "transform_profile": PROFILE,
        "policy": policy.contract(),
        "corpus_plan": {
            **files["corpus_plan"],
            "transformation_inventory_sha256": plan[
                "transformation_inventory_sha256"
            ],
            "source_count": EXPECTED_SOURCE_COUNT,
            "case_count": EXPECTED_CASE_COUNT,
        },
        "source_acquisition": {
            **files["acquisition"],
            "source_output_inventory_sha256": acquisition[
                "source_output_inventory_sha256"
            ],
            "feature_scores_opened": False,
        },
        "tools": {
            "freezer_path": str(Path(__file__).resolve()),
            "freezer_sha256": sha256_file(Path(__file__).resolve()),
            "acquisition_tool_sha256": files["acquisition_tool"]["sha256"],
            "benchmark_runner_path": files["runner"]["path"],
            "benchmark_runner_sha256": files["runner"]["sha256"],
            "benchmark_runner_source_sha256": files[
                "runner_source"
            ]["sha256"],
            "development_policy_sha256": files[
                "development_policy"
            ]["sha256"],
            "policy_module_path": files["policy_module"]["path"],
            "policy_module_sha256": files["policy_module"]["sha256"],
            "stager_path": files["stager"]["path"],
            "stager_sha256": files["stager"]["sha256"],
            "base_stager_sha256": files["base_stager"]["sha256"],
            "low_bandwidth_probe_path": files[
                "low_bandwidth_probe"
            ]["path"],
            "low_bandwidth_probe_sha256": files[
                "low_bandwidth_probe"
            ]["sha256"],
            "base_low_bandwidth_probe_sha256": files[
                "base_low_bandwidth_probe"
            ]["sha256"],
            "external_runner_path": files["external_runner"]["path"],
            "external_runner_sha256": files["external_runner"]["sha256"],
            "base_external_runner_sha256": files[
                "base_external_runner"
            ]["sha256"],
            "evaluator_path": files["evaluator"]["path"],
            "evaluator_sha256": files["evaluator"]["sha256"],
            "base_evaluator_sha256": files["base_evaluator"]["sha256"],
        },
        "source_contract": {
            "cargo_lock": files["cargo_lock"],
            "dsp_cargo_toml": files["dsp_cargo_toml"],
            "git_head": git_head,
            "git_tracked_diff_sha256": hashlib.sha256(
                git_diff
            ).hexdigest(),
            "git_untracked_inventory_sha256": hashlib.sha256(
                git_untracked
            ).hexdigest(),
            "warning": (
                "The repository is intentionally dirty. Exact executed "
                "binary and tool hashes are the frozen execution identity."
            ),
        },
        "environment": {
            "platform": platform.platform(),
            "analysis_python": {
                "path": str(Path(sys.executable).resolve()),
                "version": platform.python_version(),
                "packages": analysis_packages,
            },
            "ffmpeg_executable": committed_file(ffmpeg),
            "ffprobe_executable": committed_file(ffprobe),
            "ffmpeg_version": ffmpeg_version,
            "ffprobe_version": ffprobe_version,
            "required_audio_encoders": required_encoders,
            "audio_encoder_inventory_sha256": hashlib.sha256(
                encoder_output.encode()
            ).hexdigest(),
            "ffmpeg_plan_capability": capability,
        },
        "evidence": {
            "observed_evaluation": files["observed_evaluation"],
            "policy_equivalence": files["policy_equivalence"],
            "performance_report": files["performance_report"],
            "performance_report_sha256": files[
                "performance_report"
            ]["sha256"],
        },
        "external_transfer_gate": gate,
        "memory_contract": {
            "no_new_full_spectrogram_sized_allocation": True,
            "basis": (
                "The two-grid probe uses borrowed mono samples and bounded "
                "regional aggregates; paired process evidence measures RSS."
            ),
            "observed_performance_p95_peak_rss_increase_percent": (
                performance["summary"][
                    "p95_peak_rss_increase_percent"
                ]
            ),
        },
        "one_use_rule": (
            "After any independent external-transfer feature score is "
            "opened, this candidate may only pass or fail unchanged. A "
            "failure consumes this corpus as observed evidence."
        ),
        "warning": (
            "Even a passing external transfer does not enable the public "
            "verdict. The separate release-held-out gate remains sealed."
        ),
    }
    write_new_json(args.output.expanduser().resolve(), report)
    print(
        f"froze {CANDIDATE_ID} before {EXPECTED_CASE_COUNT} "
        "independent feature scores"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
