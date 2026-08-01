#!/usr/bin/env python3
"""Freeze the v28 candidate before MUSDB18-HQ feature scores are opened."""

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


CANDIDATE_ID = "conservative-two-grid-edge-v28-musdb-transfer-v1"
PROFILE = "conservative-two-grid-v28"
EXPECTED_SOURCE_COUNT = 150
EXPECTED_CASE_COUNT = 1_770
EXPECTED_PREDECESSOR_ARCHIVE_SHA256 = (
    "49b2b23ea4e16fb79627e7d359df184d0d86107d2f52f902bee74295b890c940"
)
SCOPED_CLASSES = {
    "musdb_aac_at_128_to_flac16",
    "musdb_aac_lc_128_to_flac16",
    "musdb_mp3_128_to_flac16",
    "musdb_vorbis_native_q3_to_flac16",
}
DIFFICULT_CLASSES = {
    "musdb_aac_lc_192_to_flac16",
    "musdb_mp3_320_to_flac16",
    "musdb_opus_96_to_flac16",
}
NEGATIVE_CLASSES = {
    "musdb_pcm_reference_wav16",
    "musdb_pcm_sharp_lowpass_16000_flac16",
    "musdb_pcm_lowpass_19000_flac16",
    "musdb_pcm_resample_32000_44100_flac16",
}
EXPECTED_ANALYSIS_PACKAGES = {
    "cffi": "2.1.0",
    "numpy": "2.3.2",
    "pycparser": "3.0",
    "soundfile": "0.13.1",
}


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(
        "audio_integrity_conservative_policy",
        path,
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import policy module: {path}")
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
    path = path.expanduser().resolve()
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
    if not resolved.is_file():
        raise SystemExit(f"committed file is missing: {resolved}")
    return {
        "path": str(resolved),
        "sha256": sha256_file(resolved),
        "bytes": resolved.stat().st_size,
    }


def validate_environment_lock(
    path: Path,
    *,
    ffmpeg: Path,
    ffprobe: Path,
    ffmpeg_version: str,
    ffprobe_version: str,
) -> tuple[dict, dict[str, str]]:
    lock = load_json(path)
    analysis_python = lock.get("analysis_python", {})
    expected_packages = {
        value.split("==", 1)[0].lower(): value.split("==", 1)[1]
        for value in analysis_python.get("packages", [])
        if isinstance(value, str) and value.count("==") == 1
    }
    current_packages = {}
    for package in EXPECTED_ANALYSIS_PACKAGES:
        try:
            current_packages[package] = version(package)
        except PackageNotFoundError as error:
            raise SystemExit(
                f"frozen analysis package is missing: {package}"
            ) from error
    locked_python = analysis_python.get("path")
    if not isinstance(locked_python, str):
        raise SystemExit("analysis Python lock path is missing")
    locked_python_path = Path(locked_python).expanduser().resolve()
    running_python_path = Path(sys.executable).resolve()
    if (
        lock.get("schema_version") != 1
        or lock.get("release_heldout_opened") is not False
        or lock.get("public_verdict_enabled") is not False
        or analysis_python.get("version")
        != f"Python {platform.python_version()}"
        or locked_python_path != running_python_path
        or expected_packages != EXPECTED_ANALYSIS_PACKAGES
        or current_packages != EXPECTED_ANALYSIS_PACKAGES
        or lock.get("ffmpeg", {}).get("version") != ffmpeg_version
        or Path(lock.get("ffmpeg", {}).get("path", ""))
        .expanduser()
        .resolve()
        != ffmpeg
        or lock.get("ffprobe", {}).get("version") != ffprobe_version
        or Path(lock.get("ffprobe", {}).get("path", ""))
        .expanduser()
        .resolve()
        != ffprobe
        or lock.get("platform", {}).get("architecture")
        != platform.machine()
    ):
        raise SystemExit("frozen analysis environment lock differs")
    return lock, current_packages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquisition", type=Path, required=True)
    parser.add_argument("--corpus-plan", type=Path, required=True)
    parser.add_argument("--observed-evaluation", type=Path, required=True)
    parser.add_argument("--policy-equivalence", type=Path, required=True)
    parser.add_argument("--performance-report", type=Path, required=True)
    parser.add_argument("--predecessor-archive", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--runner-source", type=Path, required=True)
    parser.add_argument("--cargo-lock", type=Path, required=True)
    parser.add_argument("--dsp-cargo-toml", type=Path, required=True)
    parser.add_argument("--policy-module", type=Path, required=True)
    parser.add_argument("--stager", type=Path, required=True)
    parser.add_argument("--low-bandwidth-probe", type=Path, required=True)
    parser.add_argument("--external-runner", type=Path, required=True)
    parser.add_argument("--evaluator", type=Path, required=True)
    parser.add_argument("--environment-lock", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    paths = {
        name: value.expanduser().resolve()
        for name, value in {
            "acquisition": args.acquisition,
            "corpus_plan": args.corpus_plan,
            "observed_evaluation": args.observed_evaluation,
            "policy_equivalence": args.policy_equivalence,
            "performance_report": args.performance_report,
            "predecessor_archive": args.predecessor_archive,
            "runner": args.runner,
            "runner_source": args.runner_source,
            "cargo_lock": args.cargo_lock,
            "dsp_cargo_toml": args.dsp_cargo_toml,
            "policy_module": args.policy_module,
            "stager": args.stager,
            "low_bandwidth_probe": args.low_bandwidth_probe,
            "external_runner": args.external_runner,
            "evaluator": args.evaluator,
            "environment_lock": args.environment_lock,
        }.items()
    }
    acquisition = load_json(paths["acquisition"])
    corpus_plan = load_json(paths["corpus_plan"])
    observed = load_json(paths["observed_evaluation"])
    equivalence = load_json(paths["policy_equivalence"])
    performance = load_json(paths["performance_report"])
    policy = load_module(paths["policy_module"])
    stager = load_module(paths["stager"])
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
        or corpus_plan.get("state")
        != "planned_before_external_transfer_feature_opening"
        or corpus_plan.get("corpus", {}).get("source_count")
        != EXPECTED_SOURCE_COUNT
        or corpus_plan.get("corpus", {}).get("case_count")
        != EXPECTED_CASE_COUNT
        or corpus_plan.get("external_transfer_feature_scores_opened")
        is not False
        or corpus_plan.get("release_heldout_opened") is not False
        or corpus_plan.get("acquisition", {}).get("sha256")
        != sha256_file(paths["acquisition"])
        or corpus_plan.get("tool", {}).get("sha256")
        != sha256_file(paths["stager"])
        or observed.get("state")
        != "observed_development_policy_evaluation"
        or observed.get("development_gate", {}).get("passed") is not True
        or observed.get("candidate_frozen") is not False
        or observed.get("new_external_transfer_opened") is not False
        or observed.get("release_heldout_opened") is not False
        or observed.get("policy", {}).get("policy_id")
        != policy.POLICY_ID
        or observed.get("policy", {}).get("transform_profile")
        != policy.PROFILE
        or equivalence.get("state")
        != "observed_policy_module_equivalence_verified"
        or equivalence.get("passed") is not True
        or equivalence.get("case_count") != 1_634
        or equivalence.get("mismatch_count") != 0
        or equivalence.get("inputs", {})
        .get("policy_module", {})
        .get("sha256")
        != sha256_file(paths["policy_module"])
        or performance.get("method", {}).get("transform_grid_profile")
        != PROFILE
        or not math.isfinite(performance_p95)
        or performance_p95 > 10.0
        or performance.get("commitments", {}).get("runner_sha256")
        != sha256_file(paths["runner"])
        or policy.CANDIDATE_ID != CANDIDATE_ID
        or policy.PROFILE != PROFILE
        or sha256_file(paths["predecessor_archive"])
        != EXPECTED_PREDECESSOR_ARCHIVE_SHA256
    ):
        raise SystemExit("candidate freeze prerequisite differs")

    ffmpeg_path = Path(args.ffmpeg).expanduser().resolve()
    ffprobe_path = Path(args.ffprobe).expanduser().resolve()
    ffmpeg_version = subprocess.run(
        [str(ffmpeg_path), "-version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    ffprobe_version = subprocess.run(
        [str(ffprobe_path), "-version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    _, analysis_packages = validate_environment_lock(
        paths["environment_lock"],
        ffmpeg=ffmpeg_path,
        ffprobe=ffprobe_path,
        ffmpeg_version=ffmpeg_version,
        ffprobe_version=ffprobe_version,
    )
    required_encoders = [
        "aac",
        "aac_at",
        "flac",
        "libmp3lame",
        "libopus",
        "vorbis",
    ]
    encoder_output = subprocess.run(
        [str(ffmpeg_path), "-hide_banner", "-encoders"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    available_encoders = {
        fields[1]
        for line in encoder_output.splitlines()
        if len(fields := line.split()) >= 2
    }
    missing_encoders = sorted(
        set(required_encoders) - available_encoders
    )
    if missing_encoders:
        raise SystemExit(
            "frozen FFmpeg build lacks required encoders: "
            + ", ".join(missing_encoders)
        )
    ffmpeg_plan_capability = stager.validate_ffmpeg_plan_capabilities(
        str(ffmpeg_path),
        corpus_plan,
    )
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

    files = {
        name: committed_file(path)
        for name, path in paths.items()
    }
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": (
            "audio-integrity-multicodec-explainable-research-20260731-001"
        ),
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
            "transformation_inventory_sha256": corpus_plan[
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
            "benchmark_runner_path": files["runner"]["path"],
            "benchmark_runner_sha256": files["runner"]["sha256"],
            "benchmark_runner_source_path": str(
                paths["runner_source"]
            ),
            "benchmark_runner_source_sha256": sha256_file(
                paths["runner_source"]
            ),
            "policy_module_path": files["policy_module"]["path"],
            "policy_module_sha256": files["policy_module"]["sha256"],
            "stager_path": files["stager"]["path"],
            "stager_sha256": files["stager"]["sha256"],
            "low_bandwidth_probe_path": files[
                "low_bandwidth_probe"
            ]["path"],
            "low_bandwidth_probe_sha256": files[
                "low_bandwidth_probe"
            ]["sha256"],
            "external_runner_path": files["external_runner"]["path"],
            "external_runner_sha256": files["external_runner"]["sha256"],
            "evaluator_path": files["evaluator"]["path"],
            "evaluator_sha256": files["evaluator"]["sha256"],
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
                "The repository is intentionally dirty with the complete "
                "uncommitted audio-integrity implementation. Exact source "
                "files and the executed binary are archived separately; "
                "the binary SHA-256 is the execution identity."
            ),
        },
        "environment": {
            "lock": files["environment_lock"],
            "platform": platform.platform(),
            "analysis_python": {
                "path": str(Path(sys.executable).resolve()),
                "version": platform.python_version(),
                "packages": analysis_packages,
            },
            "ffmpeg_executable": committed_file(ffmpeg_path),
            "ffprobe_executable": committed_file(ffprobe_path),
            "ffmpeg_version": ffmpeg_version,
            "ffprobe_version": ffprobe_version,
            "required_audio_encoders": required_encoders,
            "audio_encoder_inventory_sha256": hashlib.sha256(
                encoder_output.encode()
            ).hexdigest(),
            "ffmpeg_plan_capability": ffmpeg_plan_capability,
        },
        "evidence": {
            "observed_evaluation": files["observed_evaluation"],
            "policy_equivalence": files["policy_equivalence"],
            "performance_report": files["performance_report"],
            "performance_report_sha256": files[
                "performance_report"
            ]["sha256"],
            "predecessor_archive": files["predecessor_archive"],
        },
        "external_transfer_gate": {
            "maximum_tier_a_negative_false_positive_count": 0,
            "minimum_supported_recall_per_scoped_class": 0.90,
            "minimum_support_coverage_per_scoped_class": 0.75,
            "scoped_classes": sorted(SCOPED_CLASSES),
            "difficult_classes": sorted(DIFFICULT_CLASSES),
            "hard_negative_classes": sorted(NEGATIVE_CLASSES),
            "aac_invariant_source_group_count": 30,
            "maximum_aac_invariant_mismatch_source_groups": 0,
            "required_positive_reason_families": [
                "persistent_spectral_edge",
                "transform_frame_periodicity",
            ],
            "maximum_p95_runtime_overhead_percent": 10.0,
            "minimum_independent_source_groups": 150,
        },
        "memory_contract": {
            "no_new_full_spectrogram_sized_allocation": True,
            "basis": (
                "The two-grid probe decodes borrowed mono samples, retains "
                "bounded transform aggregates, and does not clone the shared "
                "full spectrogram. The paired process audit reports peak RSS."
            ),
            "observed_performance_p95_peak_rss_increase_percent": (
                performance["summary"][
                    "p95_peak_rss_increase_percent"
                ]
            ),
        },
        "one_use_rule": (
            "After any MUSDB18-HQ feature score is opened, this candidate "
            "may only pass or fail unchanged. A failed candidate consumes "
            "the corpus as observed evidence and cannot be retuned under "
            "this candidate ID."
        ),
        "warning": (
            "Even a passing external transfer does not enable the public "
            "verdict. The separate release-held-out gate remains unopened."
        ),
    }
    write_new_json(args.output, report)
    print(
        f"froze {CANDIDATE_ID} before {EXPECTED_CASE_COUNT} "
        "external-transfer feature scores"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
