#!/usr/bin/env python3
"""Measure research transform-grid wall-time and peak-memory cost."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_HARNESS = ROOT / "scripts/benchmark-audio-integrity.py"
FEATURE_VERSION = 0
SKIP_VARIABLE = "LOSSYTRACE_RESEARCH_SKIP_TRANSFORM_GRID"
PROFILE_VARIABLE = "LOSSYTRACE_RESEARCH_TRANSFORM_GRID_PROFILE"


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


def write_atomic(path: Path, value: dict) -> None:
    if path.exists():
        raise SystemExit(f"refusing to replace performance report: {path}")
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


def parse_peak_rss(stderr: str, system: str) -> int:
    if system == "Darwin":
        match = re.search(
            r"^\s*(\d+)\s+maximum resident set size\s*$",
            stderr,
            re.MULTILINE,
        )
        if match:
            return int(match.group(1))
    elif system == "Linux":
        match = re.search(
            r"^\s*Maximum resident set size \(kbytes\):\s*(\d+)\s*$",
            stderr,
            re.MULTILINE,
        )
        if match:
            return int(match.group(1)) * 1024
    raise SystemExit(
        f"could not parse peak RSS from /usr/bin/time output on {system}"
    )


def quantile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    position = proportion * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def resolve_beneath(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise SystemExit(f"path escapes audio root: {relative_path}")
    return path


def run_observation(
    *,
    time_binary: Path,
    system: str,
    binary: Path,
    case_id: str,
    audio_path: Path,
    audio_sha256: str,
    analysis_max_seconds: float,
    grid_enabled: bool,
    grid_profile: str,
) -> dict:
    time_arguments = ["-l"] if system == "Darwin" else ["-v"]
    environment = os.environ.copy()
    if grid_enabled:
        environment.pop(SKIP_VARIABLE, None)
    else:
        environment[SKIP_VARIABLE] = "1"
    environment[PROFILE_VARIABLE] = grid_profile
    command = [
        str(time_binary),
        *time_arguments,
        str(binary),
        case_id,
        str(audio_path),
        f"{analysis_max_seconds:g}",
        "1",
        f"feature-version={FEATURE_VERSION}",
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
    )
    wall_ms = (time.perf_counter() - started) * 1_000.0
    if completed.returncode:
        raise SystemExit(
            f"{case_id} grid_enabled={grid_enabled} failed: "
            f"{completed.stderr.strip()}"
        )
    try:
        runner = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SystemExit(
            f"{case_id}: performance runner returned invalid JSON: {error}"
        ) from error
    if (
        runner.get("case_id") != case_id
        or runner.get("audio_sha256") != audio_sha256
        or runner.get("feature_version") != FEATURE_VERSION
        or runner.get("research_transform_grid_enabled") is not grid_enabled
        or runner.get("research_transform_grid_profile")
        != (grid_profile if grid_enabled else None)
        or (runner.get("transform_grid_probe") is not None) is not grid_enabled
    ):
        raise SystemExit(f"{case_id}: performance runner contract differs")
    return {
        "grid_enabled": grid_enabled,
        "wall_time_ms": wall_ms,
        "peak_rss_bytes": parse_peak_rss(completed.stderr, system),
        "core_prototype_time_ms": runner["prototype_median_ms"],
        "decoded_duration_seconds": runner["decoded_duration_seconds"],
    }


def command(args: argparse.Namespace) -> int:
    if not 1 <= args.repetitions <= 10:
        raise SystemExit("--repetitions must be in 1..=10")
    manifest_path = args.manifest.expanduser().resolve()
    fingerprints_path = args.fingerprints.expanduser().resolve()
    root = args.audio_root.expanduser().resolve()
    binary = args.binary.expanduser().resolve()
    time_binary = args.time_binary.expanduser().resolve()
    for label, path in (
        ("manifest", manifest_path),
        ("fingerprints", fingerprints_path),
        ("binary", binary),
        ("time binary", time_binary),
    ):
        if path.is_symlink() or not path.is_file():
            raise SystemExit(f"{label} is not a regular file: {path}")
    if root.is_symlink() or not root.is_dir():
        raise SystemExit(f"audio root is not a regular directory: {root}")
    system = platform.system()
    if system not in {"Darwin", "Linux"}:
        raise SystemExit("performance measurement supports Darwin and Linux")
    manifest = load_json(manifest_path)
    fingerprints = load_json(fingerprints_path)
    cases = {case["case_id"]: case for case in manifest.get("cases", [])}
    requested = args.case_id or sorted(cases)
    unknown = sorted(set(requested) - set(cases))
    if unknown:
        raise SystemExit(f"unknown case IDs: {', '.join(unknown)}")
    if len(requested) != len(set(requested)):
        raise SystemExit("case IDs must not be repeated")
    expected_fingerprints = fingerprints.get("case_sha256", {})
    observations = []
    by_case = []
    for case_number, case_id in enumerate(requested, 1):
        case = cases[case_id]
        path = resolve_beneath(root, case["relative_path"])
        expected_sha256 = expected_fingerprints.get(case_id)
        if expected_sha256 != sha256_file(path):
            raise SystemExit(f"{case_id}: current audio SHA-256 differs")
        case_observations = []
        for repetition in range(args.repetitions):
            modes = (
                (False, True)
                if repetition % 2 == 0
                else (True, False)
            )
            for grid_enabled in modes:
                print(
                    f"[{case_number:02}/{len(requested):02}] {case_id} "
                    f"repetition={repetition + 1} "
                    f"grid_enabled={str(grid_enabled).lower()}"
                )
                observation = run_observation(
                    time_binary=time_binary,
                    system=system,
                    binary=binary,
                    case_id=case_id,
                    audio_path=path,
                    audio_sha256=expected_sha256,
                    analysis_max_seconds=manifest["analysis_max_seconds"],
                    grid_enabled=grid_enabled,
                    grid_profile=args.grid_profile,
                )
                observation["case_id"] = case_id
                observation["repetition"] = repetition + 1
                observations.append(observation)
                case_observations.append(observation)
        skipped = [
            observation
            for observation in case_observations
            if not observation["grid_enabled"]
        ]
        enabled = [
            observation
            for observation in case_observations
            if observation["grid_enabled"]
        ]
        skipped_wall = statistics.median(
            observation["wall_time_ms"] for observation in skipped
        )
        enabled_wall = statistics.median(
            observation["wall_time_ms"] for observation in enabled
        )
        skipped_rss = statistics.median(
            observation["peak_rss_bytes"] for observation in skipped
        )
        enabled_rss = statistics.median(
            observation["peak_rss_bytes"] for observation in enabled
        )
        by_case.append(
            {
                "case_id": case_id,
                "source_group": case["source_group"],
                "grid_skipped_median_wall_time_ms": skipped_wall,
                "grid_enabled_median_wall_time_ms": enabled_wall,
                "added_median_wall_time_ms": enabled_wall - skipped_wall,
                "wall_time_overhead_percent": (
                    (enabled_wall / skipped_wall - 1.0) * 100.0
                ),
                "grid_skipped_median_peak_rss_bytes": skipped_rss,
                "grid_enabled_median_peak_rss_bytes": enabled_rss,
                "peak_rss_increase_percent": (
                    (enabled_rss / skipped_rss - 1.0) * 100.0
                    if skipped_rss > 0
                    else 0.0
                ),
            }
        )
    wall_overheads = [
        case["wall_time_overhead_percent"] for case in by_case
    ]
    added_wall_times = [
        case["added_median_wall_time_ms"] for case in by_case
    ]
    rss_increases = [
        case["peak_rss_increase_percent"] for case in by_case
    ]
    report = {
        "schema_version": 1,
        "disposition": {
            "state": "research_only",
            "public_verdict_enabled": False,
            "reason": (
                "The transform-grid probe is not part of the timed public "
                "prototype and has not passed the release gate."
            ),
        },
        "method": {
            "measurement": (
                "isolated process wall clock and /usr/bin/time peak RSS, "
                "alternating grid-skipped and grid-enabled order"
            ),
            "repetitions_per_mode": args.repetitions,
            "system": system,
            "platform": platform.platform(),
            "analysis_max_seconds": manifest["analysis_max_seconds"],
            "skip_environment_variable": SKIP_VARIABLE,
            "profile_environment_variable": PROFILE_VARIABLE,
            "transform_grid_profile": args.grid_profile,
        },
        "commitments": {
            "manifest_sha256": sha256_file(manifest_path),
            "fingerprints_sha256": sha256_file(fingerprints_path),
            "runner_sha256": sha256_file(binary),
            "benchmark_harness_sha256": sha256_file(BENCHMARK_HARNESS),
            "measurement_script_sha256": sha256_file(
                Path(__file__).resolve()
            ),
            "feature_version": FEATURE_VERSION,
        },
        "case_count": len(by_case),
        "summary": {
            "median_added_wall_time_ms": statistics.median(
                added_wall_times
            ),
            "p95_added_wall_time_ms": quantile(added_wall_times, 0.95),
            "median_wall_time_overhead_percent": statistics.median(
                wall_overheads
            ),
            "p95_wall_time_overhead_percent": quantile(
                wall_overheads,
                0.95,
            ),
            "median_peak_rss_increase_percent": statistics.median(
                rss_increases
            ),
            "p95_peak_rss_increase_percent": quantile(
                rss_increases,
                0.95,
            ),
        },
        "by_case": by_case,
        "observations": observations,
    }
    write_atomic(args.output, report)
    print(f"wrote forensic performance report to {args.output}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--fingerprints", type=Path, required=True)
    result.add_argument("--audio-root", type=Path, required=True)
    result.add_argument("--binary", type=Path, required=True)
    result.add_argument("--time-binary", type=Path, default=Path("/usr/bin/time"))
    result.add_argument("--case-id", action="append")
    result.add_argument("--repetitions", type=int, default=3)
    result.add_argument(
        "--grid-profile",
        choices=(
            "verified-mp3-two-grid-v29",
            "conservative-two-grid-v28",
            "full",
            "stable-v15",
        ),
        default="full",
    )
    result.add_argument("--output", type=Path, required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
