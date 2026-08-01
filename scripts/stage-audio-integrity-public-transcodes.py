#!/usr/bin/env python3
"""Generate and seal public Tier A lossy-to-lossless development cases."""

from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_STAGER_PATH = (
    ROOT / "scripts/stage-audio-integrity-public-negatives.py"
)
DEFAULT_POINTER = ROOT / ".tmp/audio-integrity/public-transcodes-active.json"
MINIMUM_FREE_RESERVE_BYTES = 15 * 1024**3
DEFAULT_MAXIMUM_OUTPUT_BYTES = 5 * 1024**3


def load_public_stager():
    spec = importlib.util.spec_from_file_location(
        "audio_integrity_public_negative_stager",
        PUBLIC_STAGER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {PUBLIC_STAGER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PUBLIC = load_public_stager()


def ffmpeg_version(ffmpeg: str) -> str:
    completed = subprocess.run(
        [ffmpeg, "-version"],
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.splitlines()[0]


def probe_lossless(path: Path, ffprobe: str) -> dict:
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            (
                "format=format_name,duration:"
                "stream=index,codec_type,codec_name,sample_fmt,sample_rate,"
                "channels,bits_per_raw_sample,bits_per_sample"
            ),
            "-of",
            "json",
            str(path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    result = json.loads(completed.stdout)
    audio_streams = [
        stream
        for stream in result.get("streams", [])
        if stream.get("codec_type") == "audio"
    ]
    if len(audio_streams) != 1:
        raise SystemExit(f"{path}: expected exactly one audio stream")
    stream = audio_streams[0]
    codec = stream.get("codec_name")
    if codec != "flac" and (
        not isinstance(codec, str) or not codec.startswith("pcm_")
    ):
        raise SystemExit(
            f"{path}: generated output is not lossless ({codec!r})"
        )
    format_value = result.get("format", {})
    duration = float(format_value.get("duration", "nan"))
    if not math.isfinite(duration) or duration <= 0:
        raise SystemExit(f"{path}: generated output duration is invalid")
    return {
        "codec_name": codec,
        "sample_fmt": stream.get("sample_fmt"),
        "sample_rate": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "bits_per_sample": int(stream.get("bits_per_sample") or 0),
        "bits_per_raw_sample": int(stream.get("bits_per_raw_sample") or 0),
        "duration_seconds": duration,
        "format_name": format_value.get("format_name"),
    }


def excerpt_start(duration_seconds: float, excerpt_seconds: float) -> float:
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise SystemExit("source duration must be finite and positive")
    if not math.isfinite(excerpt_seconds) or excerpt_seconds <= 0:
        raise SystemExit("excerpt duration must be finite and positive")
    return max(0.0, (duration_seconds - excerpt_seconds) * 0.5)


def recipe_definitions() -> list[dict]:
    return [
        {
            "suffix": "pcm-excerpt-flac16",
            "class": "public_pcm_excerpt_flac16",
            "expectation": "negative",
            "kind": "pcm_reference",
        },
        {
            "suffix": "pcm-resample-48000-flac16",
            "class": "public_pcm_resample_48000_flac16",
            "expectation": "negative",
            "kind": "pcm_resample",
            "sample_rate": 48_000,
        },
        {
            "suffix": "mp3-128-to-flac16",
            "class": "public_mp3_128_to_flac16",
            "expectation": "controlled_positive",
            "kind": "lossy_round_trip",
            "extension": "mp3",
            "encode_arguments": ["-c:a", "libmp3lame", "-b:a", "128k"],
        },
        {
            "suffix": "aac-lc-128-to-flac16",
            "class": "public_aac_lc_128_to_flac16",
            "expectation": "controlled_positive",
            "kind": "lossy_round_trip",
            "extension": "m4a",
            "encode_arguments": ["-c:a", "aac", "-b:a", "128k"],
        },
        {
            "suffix": "opus-96-to-flac16",
            "class": "public_opus_96_to_flac16",
            "expectation": "controlled_positive",
            "kind": "lossy_round_trip",
            "extension": "opus",
            "encode_arguments": ["-c:a", "libopus", "-b:a", "96k"],
        },
        {
            "suffix": "vorbis-native-q3-to-flac16",
            "class": "public_vorbis_native_q3_to_flac16",
            "expectation": "controlled_positive",
            "kind": "lossy_round_trip",
            "extension": "ogg",
            "encode_arguments": [
                "-strict",
                "experimental",
                "-c:a",
                "vorbis",
                "-q:a",
                "3",
            ],
        },
    ]


def run_ffmpeg(command: list[str], label: str) -> None:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        detail = completed.stderr.strip().splitlines()
        raise SystemExit(
            f"{label} failed: "
            + "\n".join(detail[-20:])
        )


def redacted_command(
    command: list[str],
    *,
    parent_root: Path,
    output_root: Path,
) -> list[str]:
    values = []
    for argument in command:
        try:
            path = Path(argument).resolve()
        except (OSError, RuntimeError):
            values.append(argument)
            continue
        if path.is_relative_to(parent_root):
            values.append(
                "<PARENT_CORPUS>/"
                + path.relative_to(parent_root).as_posix()
            )
        elif path.is_relative_to(output_root):
            values.append(
                "<AUDIO_ROOT>/"
                + path.relative_to(output_root).as_posix()
            )
        else:
            values.append(argument)
    return values


def source_ledger_by_case(parent_root: Path) -> dict[str, dict]:
    ledger = PUBLIC.load_json(parent_root / "provenance-ledger.json")
    cases = {case["case_id"]: case for case in ledger.get("cases", [])}
    if not cases:
        raise SystemExit("parent provenance ledger has no cases")
    if len(cases) != len(ledger["cases"]):
        raise SystemExit("parent provenance ledger has duplicate case IDs")
    return cases


def generate_source_variants(
    *,
    source_case: dict,
    source_ledger: dict,
    parent_root: Path,
    output_root: Path,
    ffmpeg: str,
    ffprobe: str,
    excerpt_seconds: float,
) -> list[dict]:
    source_path = (
        parent_root / source_case["relative_path"]
    ).resolve()
    if not source_path.is_relative_to(parent_root):
        raise SystemExit(
            f"{source_case['case_id']}: parent audio path escapes root"
        )
    if source_path.is_symlink() or not source_path.is_file():
        raise SystemExit(
            f"{source_case['case_id']}: parent audio is not a regular file"
        )
    expected_sha256 = source_ledger["audio_sha256"]
    source_before_sha256 = PUBLIC.sha256_file(source_path)
    if source_before_sha256 != expected_sha256:
        raise SystemExit(
            f"{source_case['case_id']}: parent source SHA-256 differs"
        )
    start = excerpt_start(
        source_ledger["probe"]["duration_seconds"],
        excerpt_seconds,
    )
    generated_dir = output_root / "generated"
    intermediate_dir = output_root / "intermediates"
    base_id = source_case["case_id"]
    reference_id = f"{base_id}-pcm-excerpt-flac16"
    reference_path = generated_dir / f"{reference_id}.flac"
    reference_command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-n",
        "-i",
        str(source_path),
        "-map",
        "0:a:0",
        "-vn",
        "-ss",
        f"{start:.9f}",
        "-t",
        f"{excerpt_seconds:g}",
        "-ac",
        "2",
        "-c:a",
        "flac",
        "-sample_fmt",
        "s16",
        str(reference_path),
    ]
    run_ffmpeg(reference_command, reference_id)
    reference_sha256 = PUBLIC.sha256_file(reference_path)
    reference_probe = probe_lossless(reference_path, ffprobe)
    if reference_probe["channels"] != 2:
        raise SystemExit(f"{reference_id}: PCM reference is not stereo")
    results = []
    for recipe in recipe_definitions():
        case_id = f"{base_id}-{recipe['suffix']}"
        output_path = generated_dir / f"{case_id}.flac"
        commands = []
        if recipe["kind"] == "pcm_reference":
            if output_path != reference_path:
                raise RuntimeError("PCM reference path contract differs")
            commands.append(reference_command)
            audio_sha256 = reference_sha256
            probe = reference_probe
        elif recipe["kind"] == "pcm_resample":
            command = [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-n",
                "-i",
                str(reference_path),
                "-map",
                "0:a:0",
                "-vn",
                "-ar",
                str(recipe["sample_rate"]),
                "-c:a",
                "flac",
                "-sample_fmt",
                "s16",
                str(output_path),
            ]
            run_ffmpeg(command, case_id)
            commands.append(command)
            audio_sha256 = PUBLIC.sha256_file(output_path)
            probe = probe_lossless(output_path, ffprobe)
        else:
            intermediate_path = (
                intermediate_dir
                / f"{case_id}.{recipe['extension']}"
            )
            encode = [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-n",
                "-i",
                str(reference_path),
                "-map",
                "0:a:0",
                "-vn",
                *recipe["encode_arguments"],
                str(intermediate_path),
            ]
            decode = [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-n",
                "-i",
                str(intermediate_path),
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "flac",
                "-sample_fmt",
                "s16",
                str(output_path),
            ]
            run_ffmpeg(encode, f"{case_id} encode")
            run_ffmpeg(decode, f"{case_id} decode")
            commands.extend((encode, decode))
            intermediate_sha256 = PUBLIC.sha256_file(intermediate_path)
            intermediate_bytes = intermediate_path.stat().st_size
            intermediate_path.unlink()
            audio_sha256 = PUBLIC.sha256_file(output_path)
            probe = probe_lossless(output_path, ffprobe)
        result = {
            "case_id": case_id,
            "source_group": source_case["source_group"],
            "partition_group": source_case["partition_group"],
            "relative_path": output_path.relative_to(output_root).as_posix(),
            "provenance_tier": "tier_a_confirmed_pcm",
            "split": "development",
            "class": recipe["class"],
            "expectation": recipe["expectation"],
            "parent_case_id": source_case["case_id"],
            "parent_audio_sha256": expected_sha256,
            "source_before_sha256": source_before_sha256,
            "excerpt_start_seconds": start,
            "excerpt_requested_seconds": excerpt_seconds,
            "recipe_kind": recipe["kind"],
            "commands": [
                redacted_command(
                    command,
                    parent_root=parent_root,
                    output_root=output_root,
                )
                for command in commands
            ],
            "audio_sha256": audio_sha256,
            "audio_bytes": output_path.stat().st_size,
            "probe": probe,
        }
        if recipe["kind"] == "lossy_round_trip":
            result["lossy_intermediate"] = {
                "extension": recipe["extension"],
                "encode_arguments": recipe["encode_arguments"],
                "bytes": intermediate_bytes,
                "sha256": intermediate_sha256,
                "retained": False,
                "reproducible": True,
            }
        results.append(result)
    source_after_sha256 = PUBLIC.sha256_file(source_path)
    if source_after_sha256 != source_before_sha256:
        raise SystemExit(
            f"{source_case['case_id']}: parent source changed during staging"
        )
    for result in results:
        result["source_after_sha256"] = source_after_sha256
    return results


def validate_parent(parent_root: Path) -> tuple[dict, dict, dict[str, dict]]:
    PUBLIC.verify(argparse.Namespace(root=parent_root))
    manifest = PUBLIC.load_json(parent_root / "manifest.json")
    fingerprints = PUBLIC.load_json(parent_root / "fingerprints.json")
    if len(manifest.get("cases", [])) != 48:
        raise SystemExit("parent corpus must contain exactly 48 cases")
    if any(
        case.get("split") != "development"
        or case.get("expectation") != "negative"
        or case.get("provenance_tier") != "tier_a_confirmed_pcm"
        for case in manifest["cases"]
    ):
        raise SystemExit("parent corpus cases differ from Tier A development negatives")
    case_ids = {case["case_id"] for case in manifest["cases"]}
    if case_ids != set(fingerprints.get("case_sha256", {})):
        raise SystemExit("parent manifest and fingerprints differ")
    return manifest, fingerprints, source_ledger_by_case(parent_root)


def stage(args: argparse.Namespace) -> int:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.run_id):
        raise SystemExit("--run-id contains unsafe characters")
    if not 1 <= args.jobs <= 16:
        raise SystemExit("--jobs must be in 1..=16")
    if args.maximum_output_bytes <= 0:
        raise SystemExit("--maximum-output-bytes must be positive")
    if args.minimum_free_reserve_bytes < 0:
        raise SystemExit("--minimum-free-reserve-bytes must be non-negative")
    parent_root = args.parent_root.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    pointer = args.pointer.expanduser().resolve()
    if destination.exists() or destination.is_symlink():
        raise SystemExit(f"destination already exists: {destination}")
    if pointer.exists() or pointer.is_symlink():
        raise SystemExit(f"pointer already exists: {pointer}")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.parent.chmod(0o700)
    if (
        shutil.disk_usage(destination.parent).free
        - args.maximum_output_bytes
        < args.minimum_free_reserve_bytes
    ):
        raise SystemExit(
            "maximum output budget would violate the free-space reserve"
        )
    parent_manifest, parent_fingerprints, parent_ledger = validate_parent(
        parent_root
    )
    staging = (
        destination.parent
        / f".{destination.name}.{args.run_id}.staging"
    )
    if staging.exists() or staging.is_symlink():
        raise SystemExit(f"staging destination already exists: {staging}")
    staging.mkdir(mode=0o700)
    (staging / "generated").mkdir(mode=0o700)
    (staging / "intermediates").mkdir(mode=0o700)
    (staging / "provenance").mkdir(mode=0o700)
    try:
        snapshots = (
            "manifest.json",
            "fingerprints.json",
            "seal.json",
            "integrity.json",
            "provenance-ledger.json",
        )
        for name in snapshots:
            PUBLIC.copy_private(
                parent_root / name,
                staging / "provenance" / f"parent-{name}",
            )
        PUBLIC.copy_private(
            parent_root / "provenance/source-registry.json",
            staging / "provenance/source-registry.json",
        )
        PUBLIC.copy_private(
            parent_root / "provenance/fetch-record.json",
            staging / "provenance/fetch-record.json",
        )
        PUBLIC.copy_private(
            Path(__file__).resolve(),
            staging / "provenance/transcode-stager.py",
        )
        PUBLIC.copy_private(
            PUBLIC_STAGER_PATH,
            staging / "provenance/public-negative-stager.py",
        )
        source_cases = sorted(
            parent_manifest["cases"],
            key=lambda case: case["case_id"],
        )
        generated: list[dict] = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.jobs
        ) as executor:
            futures = {
                executor.submit(
                    generate_source_variants,
                    source_case=case,
                    source_ledger=parent_ledger[case["case_id"]],
                    parent_root=parent_root,
                    output_root=staging,
                    ffmpeg=args.ffmpeg,
                    ffprobe=args.ffprobe,
                    excerpt_seconds=args.excerpt_seconds,
                ): case["case_id"]
                for case in source_cases
            }
            for completed, future in enumerate(
                concurrent.futures.as_completed(futures),
                1,
            ):
                case_id = futures[future]
                variants = future.result()
                generated.extend(variants)
                print(
                    f"[{completed:02}/{len(futures)}] {case_id}: "
                    f"{len(variants)} variants"
                )
        intermediate_dir = staging / "intermediates"
        if any(intermediate_dir.iterdir()):
            raise SystemExit("lossy intermediate cleanup is incomplete")
        intermediate_dir.rmdir()
        generated.sort(key=lambda case: case["case_id"])
        actual_output_bytes = sum(
            (staging / case["relative_path"]).stat().st_size
            for case in generated
        )
        if actual_output_bytes > args.maximum_output_bytes:
            raise SystemExit(
                f"generated {actual_output_bytes} bytes, exceeding the "
                f"{args.maximum_output_bytes}-byte output budget"
            )
        manifest_cases = [
            {
                key: case[key]
                for key in (
                    "case_id",
                    "source_group",
                    "partition_group",
                    "relative_path",
                    "provenance_tier",
                    "split",
                    "class",
                    "expectation",
                )
            }
            for case in generated
        ]
        manifest = {
            "schema_version": 1,
            "corpus_id": args.corpus_id,
            "corpus_version": 1,
            "audio_root_env": (
                "REKLAWDBOX_AUDIO_INTEGRITY_PUBLIC_TRANSCODE_ROOT"
            ),
            "analysis_max_seconds": args.analysis_max_seconds,
            "repetitions": 1,
            "cases": manifest_cases,
        }
        fingerprints = {
            "schema_version": 1,
            "corpus_id": args.corpus_id,
            "corpus_version": 1,
            "case_sha256": {
                case["case_id"]: case["audio_sha256"]
                for case in generated
            },
        }
        PUBLIC.write_private_json(staging / "manifest.json", manifest)
        PUBLIC.write_private_json(
            staging / "fingerprints.json",
            fingerprints,
        )
        PUBLIC.write_private_json(
            staging / "provenance-ledger.json",
            {
                "schema_version": 1,
                "run_id": args.run_id,
                "corpus_id": args.corpus_id,
                "created_at": PUBLIC.now(),
                "purpose": (
                    "Tier A controlled lossy-to-lossless development corpus; "
                    "not held-out release evidence"
                ),
                "parent_root_at_staging": str(parent_root),
                "parent_manifest_sha256": PUBLIC.sha256_file(
                    parent_root / "manifest.json"
                ),
                "parent_fingerprints_sha256": PUBLIC.sha256_file(
                    parent_root / "fingerprints.json"
                ),
                "parent_seal_sha256": PUBLIC.sha256_file(
                    parent_root / "seal.json"
                ),
                "parent_integrity_sha256": PUBLIC.sha256_file(
                    parent_root / "integrity.json"
                ),
                "transcode_stager_sha256": PUBLIC.sha256_file(
                    Path(__file__).resolve()
                ),
                "public_negative_stager_sha256": PUBLIC.sha256_file(
                    PUBLIC_STAGER_PATH
                ),
                "ffmpeg_version": ffmpeg_version(args.ffmpeg),
                "ffprobe_version": PUBLIC.ffprobe_version(args.ffprobe),
                "excerpt_seconds": args.excerpt_seconds,
                "analysis_max_seconds": args.analysis_max_seconds,
                "source_partition_count": len(source_cases),
                "case_count": len(generated),
                "generated_audio_bytes": actual_output_bytes,
                "lossy_intermediates_retained": False,
                "lossy_intermediates_reproducible": True,
                "cases": generated,
            },
        )
        integrity_path = PUBLIC.write_integrity(staging, args.run_id)
        PUBLIC.write_private_json(
            staging / "seal.json",
            {
                "schema_version": 1,
                "run_id": args.run_id,
                "corpus_id": args.corpus_id,
                "created_at": PUBLIC.now(),
                "state": "sealed_development_corpus",
                "split": "development",
                "held_out_labels_present": False,
                "case_count": len(generated),
                "partition_count": len(source_cases),
                "integrity_manifest": "integrity.json",
                "integrity_manifest_sha256": PUBLIC.sha256_file(
                    integrity_path
                ),
                "exact_cleanup_target": str(destination),
                "generated_audio_bytes": actual_output_bytes,
                "reproducible_from": {
                    "parent_manifest_sha256": PUBLIC.sha256_file(
                        parent_root / "manifest.json"
                    ),
                    "parent_fingerprints_sha256": PUBLIC.sha256_file(
                        parent_root / "fingerprints.json"
                    ),
                    "transcode_stager_sha256": PUBLIC.sha256_file(
                        Path(__file__).resolve()
                    ),
                    "ffmpeg_version": ffmpeg_version(args.ffmpeg),
                },
            },
        )
        staging.replace(destination)
        PUBLIC.write_private_json(
            pointer,
            {
                "schema_version": 1,
                "run_id": args.run_id,
                "state": "sealed_development_corpus",
                "root": str(destination),
                "manifest": str(destination / "manifest.json"),
                "fingerprints": str(destination / "fingerprints.json"),
                "ledger": str(destination / "provenance-ledger.json"),
                "seal": str(destination / "seal.json"),
                "exact_cleanup_target": str(destination),
            },
        )
    except BaseException:
        if staging.exists() and staging.is_dir() and not staging.is_symlink():
            shutil.rmtree(staging)
        raise
    print(
        f"sealed {len(generated)} Tier A controlled cases from "
        f"{len(source_cases)} source partitions at {destination}"
    )
    return 0


def verify(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    PUBLIC.verify(argparse.Namespace(root=root, quiet=True))
    manifest = PUBLIC.load_json(root / "manifest.json")
    fingerprints = PUBLIC.load_json(root / "fingerprints.json")
    ledger = PUBLIC.load_json(root / "provenance-ledger.json")
    seal = PUBLIC.load_json(root / "seal.json")
    manifest_cases = {
        case["case_id"]: case for case in manifest.get("cases", [])
    }
    ledger_cases = {
        case["case_id"]: case for case in ledger.get("cases", [])
    }
    fingerprint_cases = fingerprints.get("case_sha256", {})
    failures = []
    if (
        len(manifest_cases) != len(manifest.get("cases", []))
        or len(ledger_cases) != len(ledger.get("cases", []))
    ):
        failures.append("duplicate case IDs")
    if set(manifest_cases) != set(ledger_cases):
        failures.append("manifest and provenance-ledger case IDs differ")
    if set(manifest_cases) != set(fingerprint_cases):
        failures.append("manifest and fingerprint case IDs differ")
    if ledger.get("run_id") != seal.get("run_id"):
        failures.append("provenance-ledger and seal run IDs differ")
    if ledger.get("case_count") != len(manifest_cases):
        failures.append("provenance-ledger case count differs")
    if ledger.get("source_partition_count") != seal.get("partition_count"):
        failures.append("sealed source partition count differs")
    if ledger.get("lossy_intermediates_retained") is not False:
        failures.append("lossy intermediates are not recorded as removed")
    if ledger.get("lossy_intermediates_reproducible") is not True:
        failures.append("lossy intermediates are not recorded as reproducible")
    for case_id, case in manifest_cases.items():
        provenance = ledger_cases.get(case_id, {})
        if case.get("provenance_tier") != "tier_a_confirmed_pcm":
            failures.append(f"{case_id}: provenance tier differs")
        if case.get("split") != "development":
            failures.append(f"{case_id}: split differs")
        if provenance.get("audio_sha256") != fingerprint_cases.get(case_id):
            failures.append(f"{case_id}: provenance fingerprint differs")
        intermediate = provenance.get("lossy_intermediate")
        if case.get("expectation") == "controlled_positive":
            if (
                not isinstance(intermediate, dict)
                or intermediate.get("retained") is not False
                or intermediate.get("reproducible") is not True
            ):
                failures.append(
                    f"{case_id}: lossy-intermediate cleanup record differs"
                )
        elif case.get("expectation") != "negative":
            failures.append(f"{case_id}: expectation differs")
    snapshot_checks = (
        (
            "provenance/parent-manifest.json",
            "parent_manifest_sha256",
        ),
        (
            "provenance/parent-fingerprints.json",
            "parent_fingerprints_sha256",
        ),
        (
            "provenance/transcode-stager.py",
            "transcode_stager_sha256",
        ),
        (
            "provenance/public-negative-stager.py",
            "public_negative_stager_sha256",
        ),
    )
    for relative_path, ledger_key in snapshot_checks:
        path = root / relative_path
        if (
            not path.is_file()
            or path.is_symlink()
            or PUBLIC.sha256_file(path) != ledger.get(ledger_key)
        ):
            failures.append(f"{relative_path}: provenance snapshot differs")
    intermediate_root = root / "intermediates"
    if intermediate_root.exists() or intermediate_root.is_symlink():
        failures.append("lossy intermediate directory is present")
    if failures:
        raise SystemExit(
            "public-transcode corpus verification failed:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )
    print(
        f"verified sealed public-transcode corpus: {len(manifest_cases)} cases "
        f"at {root}"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    stage_command = commands.add_parser("stage")
    stage_command.add_argument("--parent-root", type=Path, required=True)
    stage_command.add_argument("--destination", type=Path, required=True)
    stage_command.add_argument(
        "--pointer",
        type=Path,
        default=DEFAULT_POINTER,
    )
    stage_command.add_argument("--run-id", required=True)
    stage_command.add_argument("--corpus-id", required=True)
    stage_command.add_argument("--excerpt-seconds", type=float, default=90)
    stage_command.add_argument(
        "--analysis-max-seconds",
        type=float,
        default=90,
    )
    stage_command.add_argument("--jobs", type=int, default=4)
    stage_command.add_argument("--ffmpeg", default="ffmpeg")
    stage_command.add_argument("--ffprobe", default="ffprobe")
    stage_command.add_argument(
        "--minimum-free-reserve-bytes",
        type=int,
        default=MINIMUM_FREE_RESERVE_BYTES,
    )
    stage_command.add_argument(
        "--maximum-output-bytes",
        type=int,
        default=DEFAULT_MAXIMUM_OUTPUT_BYTES,
    )
    stage_command.set_defaults(function=stage)
    verify_command = commands.add_parser("verify")
    verify_command.add_argument("--root", type=Path, required=True)
    verify_command.set_defaults(function=verify)
    return result


if __name__ == "__main__":
    parsed = parser().parse_args()
    if (
        hasattr(parsed, "excerpt_seconds")
        and (
            not math.isfinite(parsed.excerpt_seconds)
            or parsed.excerpt_seconds <= 0
        )
    ):
        raise SystemExit("--excerpt-seconds must be finite and positive")
    if (
        hasattr(parsed, "analysis_max_seconds")
        and (
            not math.isfinite(parsed.analysis_max_seconds)
            or parsed.analysis_max_seconds < 0
        )
    ):
        raise SystemExit(
            "--analysis-max-seconds must be finite and non-negative"
        )
    raise SystemExit(parsed.function(parsed))
