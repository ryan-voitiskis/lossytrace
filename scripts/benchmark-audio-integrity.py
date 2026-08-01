#!/usr/bin/env python3
"""Prepare and run the private audio-integrity measurement benchmark."""

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
import sys
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = Path(__file__).resolve()
BENCHMARK_DIR = ROOT / "benchmarks/audio-integrity-v1"
DEFAULT_MANIFEST = BENCHMARK_DIR / "manifest.json"
EXAMPLE_MANIFEST = BENCHMARK_DIR / "manifest.example.json"
EXPECTED_FEATURE_VERSION = 0
ALLOWED_SPLITS = {"development", "held_out"}
ALLOWED_TIERS = {
    "tier_a_confirmed_pcm",
    "tier_b_trusted",
    "tier_c_unknown",
    "synthetic",
}
ALLOWED_EXPECTATIONS = {
    "negative",
    "controlled_positive",
    "blind_case_study",
    "invariant_only",
}
RATIO_FIELDS = {
    "median_active_bin_fraction",
    "spectral_edge_persistence",
    "spectral_hole_ratio",
    "isolated_hole_ratio",
    "band_rupture_score",
    "transform_alignment_score",
    "transform_alignment_small_coefficient_fraction",
}


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def write_atomic(path: Path, value: dict) -> None:
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audio_root(manifest: dict, explicit: str | None) -> Path:
    value = explicit or os.environ.get(manifest["audio_root_env"])
    if not value:
        raise SystemExit(
            f"set {manifest['audio_root_env']} or pass --audio-root"
        )
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"audio root does not exist: {root}")
    return root


def resolve_beneath(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise SystemExit(f"path escapes audio root: {relative_path}")
    return path


def validate_manifest(manifest: dict) -> list[str]:
    failures: list[str] = []
    if manifest.get("schema_version") != 1:
        failures.append("schema_version must be 1")
    if not manifest.get("corpus_id"):
        failures.append("corpus_id is required")
    if not isinstance(manifest.get("corpus_version"), int):
        failures.append("corpus_version must be an integer")
    if not manifest.get("audio_root_env"):
        failures.append("audio_root_env is required")
    repetitions = manifest.get("repetitions")
    if not isinstance(repetitions, int) or not 1 <= repetitions <= 20:
        failures.append("repetitions must be an integer in 1..=20")
    max_seconds = manifest.get("analysis_max_seconds")
    if (
        not isinstance(max_seconds, (int, float))
        or not math.isfinite(max_seconds)
        or max_seconds < 0
    ):
        failures.append(
            "analysis_max_seconds must be finite and non-negative; 0 means full"
        )

    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        failures.append("cases must be a non-empty array")
        return failures
    seen_ids: set[str] = set()
    source_splits: dict[str, set[str]] = defaultdict(set)
    partition_splits: dict[str, set[str]] = defaultdict(set)
    for index, case in enumerate(cases):
        prefix = f"cases[{index}]"
        if not isinstance(case, dict):
            failures.append(f"{prefix} must be an object")
            continue
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            failures.append(f"{prefix}.case_id is required")
        elif case_id in seen_ids:
            failures.append(f"duplicate case_id: {case_id}")
        else:
            seen_ids.add(case_id)
        for field in ("source_group", "relative_path", "class"):
            if not isinstance(case.get(field), str) or not case[field]:
                failures.append(f"{prefix}.{field} is required")
        if case.get("split") not in ALLOWED_SPLITS:
            failures.append(
                f"{prefix}.split must be one of {sorted(ALLOWED_SPLITS)}"
            )
        if case.get("provenance_tier") not in ALLOWED_TIERS:
            failures.append(
                f"{prefix}.provenance_tier must be one of "
                f"{sorted(ALLOWED_TIERS)}"
            )
        if case.get("expectation") not in ALLOWED_EXPECTATIONS:
            failures.append(
                f"{prefix}.expectation must be one of "
                f"{sorted(ALLOWED_EXPECTATIONS)}"
            )
        source_group = case.get("source_group")
        partition_group = case.get("partition_group")
        if partition_group is not None and (
            not isinstance(partition_group, str) or not partition_group
        ):
            failures.append(
                f"{prefix}.partition_group must be a non-empty string"
            )
        split = case.get("split")
        if isinstance(source_group, str) and split in ALLOWED_SPLITS:
            source_splits[source_group].add(split)
        if isinstance(partition_group, str) and split in ALLOWED_SPLITS:
            partition_splits[partition_group].add(split)
    for source_group, splits in source_splits.items():
        if len(splits) > 1:
            failures.append(
                f"source_group {source_group!r} crosses splits: {sorted(splits)}"
            )
    for partition_group, splits in partition_splits.items():
        if len(splits) > 1:
            failures.append(
                f"partition_group {partition_group!r} crosses splits: "
                f"{sorted(splits)}"
            )
    return failures


def command_validate(args: argparse.Namespace) -> int:
    manifest = load(args.manifest)
    failures = validate_manifest(manifest)
    if failures:
        print("manifest validation failed:", file=sys.stderr)
        print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
        return 1
    cases = manifest["cases"]
    source_groups = {case["source_group"] for case in cases}
    held_out = {
        case["source_group"]
        for case in cases
        if case["split"] == "held_out"
    }
    print(
        f"manifest valid: {len(cases)} cases, "
        f"{len(source_groups)} source groups, {len(held_out)} held-out groups"
    )
    return 0


def manifest_and_root(args: argparse.Namespace) -> tuple[dict, Path]:
    manifest = load(args.manifest)
    failures = validate_manifest(manifest)
    if failures:
        raise SystemExit(
            "manifest validation failed:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )
    return manifest, audio_root(manifest, args.audio_root)


def collect_fingerprints(manifest: dict, root: Path) -> dict:
    fingerprints: dict[str, str] = {}
    missing: list[str] = []
    for case in manifest["cases"]:
        path = resolve_beneath(root, case["relative_path"])
        if not path.is_file():
            missing.append(f"{case['case_id']}: {path}")
            continue
        fingerprints[case["case_id"]] = sha256_file(path)
    if missing:
        raise SystemExit(
            "benchmark audio is incomplete:\n"
            + "\n".join(f"- {item}" for item in missing)
        )
    return {
        "schema_version": 1,
        "corpus_id": manifest["corpus_id"],
        "corpus_version": manifest["corpus_version"],
        "case_sha256": fingerprints,
    }


def command_fingerprint(args: argparse.Namespace) -> int:
    manifest, root = manifest_and_root(args)
    fingerprints = collect_fingerprints(manifest, root)
    write_atomic(args.output, fingerprints)
    print(
        f"wrote {len(fingerprints['case_sha256'])} fingerprints to {args.output}"
    )
    return 0


def validate_measurements(result: dict) -> list[str]:
    failures: list[str] = []
    if result.get("schema_version") != 1:
        failures.append("runner schema_version must be 1")
    if result.get("feature_version") != EXPECTED_FEATURE_VERSION:
        failures.append(
            f"feature_version must be {EXPECTED_FEATURE_VERSION}"
        )
    features = result.get("compression_trace")
    if not isinstance(features, dict):
        return failures + ["compression_trace must be an object"]
    for field, value in features.items():
        if value is None or isinstance(value, int):
            continue
        if not isinstance(value, float) or not math.isfinite(value):
            failures.append(f"compression_trace.{field} must be finite")
        elif field in RATIO_FIELDS and not 0 <= value <= 1:
            failures.append(f"compression_trace.{field} must be in [0, 1]")
        elif value < 0:
            failures.append(f"compression_trace.{field} must be non-negative")
    return failures


def quantile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = proportion * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def distributions(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["class"]].append(row)
    output: dict[str, dict] = {}
    feature_fields = (
        "median_active_bin_fraction",
        "spectral_edge_hz",
        "spectral_edge_drop_db",
        "spectral_edge_persistence",
        "spectral_edge_spread_hz",
        "spectral_hole_ratio",
        "isolated_hole_ratio",
        "band_rupture_score",
        "transform_alignment_score",
        "transform_alignment_small_coefficient_fraction",
    )
    for class_name, class_rows in sorted(grouped.items()):
        feature_summary: dict[str, dict] = {}
        for field in feature_fields:
            values = [
                row["runner"]["compression_trace"][field]
                for row in class_rows
                if row["runner"]["compression_trace"].get(field) is not None
            ]
            feature_summary[field] = {
                "measured": len(values),
                "median": statistics.median(values) if values else None,
                "p05": quantile(values, 0.05),
                "p95": quantile(values, 0.95),
            }
        output[class_name] = {
            "cases": len(class_rows),
            "features": feature_summary,
        }
    return output


def run_benchmark_case(
    index: int,
    total: int,
    case: dict,
    *,
    binary: Path,
    root: Path,
    analysis_max_seconds: float,
    repetitions: int,
    current_fingerprints: dict[str, str],
) -> tuple[dict | None, list[str]]:
    print(
        f"[{index:03}/{total}] {case['case_id']}",
        file=sys.stderr,
    )
    path = resolve_beneath(root, case["relative_path"])
    completed = subprocess.run(
        [
            str(binary),
            case["case_id"],
            str(path),
            str(analysis_max_seconds),
            str(repetitions),
            f"feature-version={EXPECTED_FEATURE_VERSION}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        return None, [f"{case['case_id']}: {completed.stderr.strip()}"]
    try:
        runner = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        return None, [f"{case['case_id']}: invalid runner JSON: {error}"]
    case_failures = validate_measurements(runner)
    if runner.get("case_id") != case["case_id"]:
        case_failures.append("runner case_id mismatch")
    if runner.get("audio_sha256") != current_fingerprints[case["case_id"]]:
        case_failures.append("runner audio fingerprint mismatch")
    row = {
        "case_id": case["case_id"],
        "source_group": case["source_group"],
        "split": case["split"],
        "provenance_tier": case["provenance_tier"],
        "class": case["class"],
        "expectation": case["expectation"],
        "runner": runner,
    }
    if "partition_group" in case:
        row["partition_group"] = case["partition_group"]
    return row, [
        f"{case['case_id']}: {failure}" for failure in case_failures
    ]


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


def measure_case_peak_rss(
    *,
    time_binary: Path,
    system: str,
    binary: Path,
    case: dict,
    path: Path,
    analysis_max_seconds: float,
    prototype_enabled: bool,
    expected_fingerprint: str,
) -> int:
    time_arguments = ["-l"] if system == "Darwin" else ["-v"]
    mode = "prototype" if prototype_enabled else "baseline"
    completed = subprocess.run(
        [
            str(time_binary),
            *time_arguments,
            str(binary),
            case["case_id"],
            str(path),
            str(analysis_max_seconds),
            "1",
            f"feature-version={EXPECTED_FEATURE_VERSION}",
            f"memory-mode={mode}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise SystemExit(
            f"{case['case_id']} {mode} memory run failed: "
            f"{completed.stderr.strip()}"
        )
    try:
        runner = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SystemExit(
            f"{case['case_id']} {mode} memory run returned invalid JSON: {error}"
        ) from error
    if (
        runner.get("schema_version") != 1
        or runner.get("case_id") != case["case_id"]
        or runner.get("audio_sha256") != expected_fingerprint
        or runner.get("prototype_enabled") is not prototype_enabled
        or runner.get("compression_trace_measured") is not prototype_enabled
        or runner.get("feature_version") != EXPECTED_FEATURE_VERSION
    ):
        raise SystemExit(
            f"{case['case_id']} {mode} memory runner contract differs"
        )
    return parse_peak_rss(completed.stderr, system)


def command_memory(args: argparse.Namespace) -> int:
    manifest, root = manifest_and_root(args)
    manifest_path = args.manifest.expanduser().resolve()
    fingerprints_path = args.fingerprints.expanduser().resolve()
    if args.output.exists():
        raise SystemExit(f"refusing to replace memory report: {args.output}")
    expected = load(fingerprints_path).get("case_sha256")
    current = collect_fingerprints(manifest, root)["case_sha256"]
    if expected != current:
        raise SystemExit(
            "corpus fingerprints differ; memory evidence requires the sealed "
            "fingerprints"
        )
    system = platform.system()
    if system not in {"Darwin", "Linux"}:
        raise SystemExit("memory measurement supports Darwin and Linux only")
    time_binary = args.time_binary.expanduser().resolve()
    if not time_binary.is_file():
        raise SystemExit(f"time binary does not exist: {time_binary}")
    binary = (
        args.binary
        or ROOT / "target/release/examples/audio_integrity_benchmark"
    ).expanduser().resolve()
    if not args.no_build:
        subprocess.run(
            [
                "cargo",
                "build",
                "--release",
                "-p",
                "lossytrace",
                "--example",
                "audio_integrity_benchmark",
            ],
            cwd=ROOT,
            check=True,
        )
    if not binary.is_file():
        raise SystemExit(f"benchmark runner does not exist: {binary}")

    observations = []
    cases = manifest["cases"]
    for index, case in enumerate(cases, 1):
        print(
            f"[memory {index:03}/{len(cases)}] {case['case_id']}",
            file=sys.stderr,
        )
        path = resolve_beneath(root, case["relative_path"])
        baseline = measure_case_peak_rss(
            time_binary=time_binary,
            system=system,
            binary=binary,
            case=case,
            path=path,
            analysis_max_seconds=manifest["analysis_max_seconds"],
            prototype_enabled=False,
            expected_fingerprint=current[case["case_id"]],
        )
        prototype = measure_case_peak_rss(
            time_binary=time_binary,
            system=system,
            binary=binary,
            case=case,
            path=path,
            analysis_max_seconds=manifest["analysis_max_seconds"],
            prototype_enabled=True,
            expected_fingerprint=current[case["case_id"]],
        )
        observations.append(
            {
                "case_id": case["case_id"],
                "baseline_peak_rss_bytes": baseline,
                "prototype_peak_rss_bytes": prototype,
            }
        )
    baseline_peak = max(
        observation["baseline_peak_rss_bytes"]
        for observation in observations
    )
    prototype_peak = max(
        observation["prototype_peak_rss_bytes"]
        for observation in observations
    )
    write_atomic(
        args.output,
        {
            "schema_version": 1,
            "corpus_id": manifest["corpus_id"],
            "corpus_version": manifest["corpus_version"],
            "manifest_sha256": sha256_file(manifest_path),
            "fingerprints_sha256": sha256_file(fingerprints_path),
            "feature_version": EXPECTED_FEATURE_VERSION,
            "analysis_max_seconds": manifest["analysis_max_seconds"],
            "case_count": len(cases),
            "case_ids": sorted(case["case_id"] for case in cases),
            "measurement_method": (
                f"{time_binary} {'-l' if system == 'Darwin' else '-v'}; "
                "one isolated baseline process and one isolated prototype "
                "process per case; maximum across the complete corpus"
            ),
            "platform": system,
            "runner_sha256": sha256_file(binary),
            "harness_sha256": sha256_file(SCRIPT_PATH),
            "baseline_peak_rss_bytes": baseline_peak,
            "prototype_peak_rss_bytes": prototype_peak,
            "observations": observations,
        },
    )
    print(
        f"wrote complete-corpus peak RSS report for {len(cases)} cases "
        f"to {args.output}"
    )
    return 0


def command_run(args: argparse.Namespace) -> int:
    manifest, root = manifest_and_root(args)
    if not 1 <= args.jobs <= 8:
        raise SystemExit("--jobs must be in 1..=8")
    expected_fingerprints = (
        load(args.fingerprints)["case_sha256"] if args.fingerprints else None
    )
    current_fingerprints = collect_fingerprints(manifest, root)["case_sha256"]
    if (
        expected_fingerprints is not None
        and expected_fingerprints != current_fingerprints
    ):
        raise SystemExit(
            "corpus fingerprints differ; regenerate and review fingerprints "
            "instead of silently benchmarking changed inputs"
        )

    binary = (
        args.binary
        or ROOT / "target/release/examples/audio_integrity_benchmark"
    ).expanduser().resolve()
    if not args.no_build:
        subprocess.run(
            [
                "cargo",
                "build",
                "--release",
                "-p",
                "lossytrace",
                "--example",
                "audio_integrity_benchmark",
            ],
            cwd=ROOT,
            check=True,
        )
    if not binary.is_file():
        raise SystemExit(f"benchmark runner does not exist: {binary}")

    rows: list[dict] = []
    failures: list[str] = []
    cases = manifest["cases"]
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = [
            executor.submit(
                run_benchmark_case,
                index,
                len(cases),
                case,
                binary=binary,
                root=root,
                analysis_max_seconds=manifest["analysis_max_seconds"],
                repetitions=manifest["repetitions"],
                current_fingerprints=current_fingerprints,
            )
            for index, case in enumerate(cases, 1)
        ]
        for future in futures:
            row, case_failures = future.result()
            failures.extend(case_failures)
            if row is not None:
                rows.append(row)

    overhead = [
        row["runner"]["runtime_overhead_percent"] for row in rows
    ]
    output = {
        "schema_version": 1,
        "corpus_id": manifest["corpus_id"],
        "corpus_version": manifest["corpus_version"],
        "feature_version": EXPECTED_FEATURE_VERSION,
        "runner_sha256": sha256_file(binary),
        "harness_sha256": sha256_file(SCRIPT_PATH),
        "analysis_max_seconds": manifest["analysis_max_seconds"],
        "repetitions": manifest["repetitions"],
        "gate_disposition": {
            "state": "not_evaluated",
            "likely_lossy_derived_enabled": False,
            "reason": (
                "Prototype measurements are uncalibrated; no frozen policy or "
                "held-out release evaluation exists."
            ),
        },
        "runtime": {
            "cases": len(overhead),
            "jobs": args.jobs,
            "overhead_median_percent": (
                statistics.median(overhead) if overhead else None
            ),
            "overhead_p95_percent": quantile(overhead, 0.95),
        },
        "distributions_by_class": distributions(rows),
        "results": rows,
    }
    write_atomic(args.output, output)
    if failures:
        print("benchmark run failed:", file=sys.stderr)
        print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
        return 1
    print(f"wrote {len(rows)} results to {args.output}")
    return 0


def ffmpeg_output_options(recipe: dict, output_path: Path) -> list[str]:
    bits = recipe.get("output_bits_per_sample", 24)
    extension = output_path.suffix.lower()
    if extension == ".wav":
        return ["-c:a", "pcm_s16le" if bits == 16 else "pcm_s24le"]
    if extension in {".aif", ".aiff"}:
        return ["-c:a", "pcm_s16be" if bits == 16 else "pcm_s24be"]
    if extension == ".flac":
        if bits == 16:
            return ["-c:a", "flac", "-sample_fmt", "s16"]
        return [
            "-c:a",
            "flac",
            "-sample_fmt",
            "s32",
            "-bits_per_raw_sample",
            "24",
        ]
    raise SystemExit(
        f"{recipe['case_id']}: output must be WAV, AIFF, or FLAC"
    )


def sanitized_command(command: list[str], root: Path) -> list[str]:
    root_text = str(root)
    return [part.replace(root_text, "<AUDIO_ROOT>") for part in command]


def run_ffmpeg(command: list[str], root: Path, record: list[list[str]]) -> None:
    record.append(sanitized_command(command, root))
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        raise SystemExit(
            f"FFmpeg command failed with exit code {error.returncode}: "
            f"{' '.join(sanitized_command(command, root))}"
        ) from error


def command_prepare(args: argparse.Namespace) -> int:
    manifest, root = manifest_and_root(args)
    recipes = manifest.get("recipes", [])
    if not recipes:
        raise SystemExit("manifest contains no recipes")
    ffmpeg_version = subprocess.run(
        [args.ffmpeg, "-version"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()[0]
    commands: list[list[str]] = []
    collision_mode = "-y" if args.overwrite else "-n"
    with tempfile.TemporaryDirectory(prefix="lossytrace-research-") as temp:
        temp_root = Path(temp)
        for recipe in recipes:
            case_id = recipe["case_id"]
            source = resolve_beneath(root, recipe["source_relative_path"])
            output = resolve_beneath(root, recipe["output_relative_path"])
            if not source.is_file():
                raise SystemExit(f"{case_id}: source does not exist: {source}")
            output.parent.mkdir(parents=True, exist_ok=True)
            pre_filters = recipe.get("pre_filters", [])
            post_filters = recipe.get("post_filters", [])
            codec = recipe.get("intermediate_codec", "pcm")
            common = [
                args.ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                collision_mode,
                "-i",
                str(source),
                "-map",
                "0:a:0",
            ]
            sample_rate = recipe.get("sample_rate_hz")
            channel_count = recipe.get("channel_count")
            if channel_count:
                common.extend(["-ac", str(channel_count)])
            if codec == "pcm":
                command = common
                pcm_filters = pre_filters + post_filters
                if pcm_filters:
                    command.extend(["-af", ",".join(pcm_filters)])
                if sample_rate:
                    command.extend(["-ar", str(sample_rate)])
                command.extend(ffmpeg_output_options(recipe, output))
                command.append(str(output))
                run_ffmpeg(command, root, commands)
                continue

            if pre_filters:
                common.extend(["-af", ",".join(pre_filters)])
            if sample_rate:
                common.extend(["-ar", str(sample_rate)])
            suffix_by_codec = {
                "mp3": ".mp3",
                "aac": ".m4a",
                "vorbis": ".ogg",
                "opus": ".opus",
            }
            encoder_by_codec = {
                "mp3": "libmp3lame",
                "aac": "aac",
                "vorbis": "libvorbis",
                "opus": "libopus",
            }
            if codec not in suffix_by_codec:
                raise SystemExit(f"{case_id}: unsupported codec {codec!r}")
            intermediate = temp_root / f"{case_id}{suffix_by_codec[codec]}"
            encoder = recipe.get("encoder", encoder_by_codec[codec])
            encode = common + [
                "-c:a",
                encoder,
            ]
            if encoder in {"vorbis", "opus"}:
                encode.extend(["-strict", "experimental"])
            if "bitrate" in recipe:
                encode.extend(["-b:a", str(recipe["bitrate"])])
            if "quality" in recipe:
                encode.extend(["-q:a", str(recipe["quality"])])
            encode.append(str(intermediate))
            run_ffmpeg(encode, root, commands)

            decode = [
                args.ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                collision_mode,
                "-i",
                str(intermediate),
                "-map",
                "0:a:0",
            ]
            if post_filters:
                decode.extend(["-af", ",".join(post_filters)])
            if sample_rate:
                decode.extend(["-ar", str(sample_rate)])
            decode.extend(ffmpeg_output_options(recipe, output))
            decode.append(str(output))
            run_ffmpeg(decode, root, commands)

    write_atomic(
        args.record,
        {
            "schema_version": 1,
            "ffmpeg_version": ffmpeg_version,
            "commands": commands,
        },
    )
    print(f"prepared {len(recipes)} cases; command record: {args.record}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"private manifest (start from {EXAMPLE_MANIFEST})",
    )
    commands = root.add_subparsers(dest="command", required=True)

    validate_parser = commands.add_parser("validate")
    validate_parser.set_defaults(function=command_validate)

    fingerprint_parser = commands.add_parser("fingerprint")
    fingerprint_parser.add_argument("--audio-root")
    fingerprint_parser.add_argument("--output", type=Path, required=True)
    fingerprint_parser.set_defaults(function=command_fingerprint)

    run_parser = commands.add_parser("run")
    run_parser.add_argument("--audio-root")
    run_parser.add_argument("--fingerprints", type=Path)
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--binary", type=Path)
    run_parser.add_argument("--no-build", action="store_true")
    run_parser.add_argument("--jobs", type=int, default=1)
    run_parser.set_defaults(function=command_run)

    memory_parser = commands.add_parser("memory")
    memory_parser.add_argument("--audio-root")
    memory_parser.add_argument("--fingerprints", type=Path, required=True)
    memory_parser.add_argument("--output", type=Path, required=True)
    memory_parser.add_argument("--binary", type=Path)
    memory_parser.add_argument("--no-build", action="store_true")
    memory_parser.add_argument(
        "--time-binary",
        type=Path,
        default=Path("/usr/bin/time"),
    )
    memory_parser.set_defaults(function=command_memory)

    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--audio-root")
    prepare_parser.add_argument("--ffmpeg", default="ffmpeg")
    prepare_parser.add_argument("--record", type=Path, required=True)
    prepare_parser.add_argument("--overwrite", action="store_true")
    prepare_parser.set_defaults(function=command_prepare)
    return root


if __name__ == "__main__":
    arguments = parser().parse_args()
    raise SystemExit(arguments.function(arguments))
