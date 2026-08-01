#!/usr/bin/env python3
"""Stage and inventory a private audio-integrity development corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path

SUPPORTED_EXTENSIONS = {".aif", ".aiff", ".flac", ".wav"}
LOSSLESS_CODECS = {
    "flac",
    "pcm_s16be",
    "pcm_s16le",
    "pcm_s24be",
    "pcm_s24le",
    "pcm_s32be",
    "pcm_s32le",
}


def now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_stream(source) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


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


def safe_existing_corpus_root(value: str | Path, run_id: str) -> Path:
    root = Path(value).expanduser().resolve()
    forbidden = {
        Path("/").resolve(),
        Path.home().resolve(),
        Path("/private/tmp").resolve(),
        Path("/tmp").resolve(),
    }
    allowed_names = {run_id, f"reklaw-{run_id}"}
    if root in forbidden or root.name not in allowed_names or not root.is_dir():
        raise SystemExit(f"refusing unsafe corpus root: {root}")
    return root


def resolve_new_root(value: str) -> Path:
    root = Path(value).expanduser().resolve()
    forbidden = {
        Path("/").resolve(),
        Path.home().resolve(),
        Path("/private/tmp").resolve(),
        Path("/tmp").resolve(),
    }
    if root in forbidden:
        raise SystemExit(f"refusing unsafe audio root: {root}")
    if root.exists():
        raise SystemExit(f"audio root already exists: {root}")
    if not root.parent.is_dir():
        raise SystemExit(f"audio root parent does not exist: {root.parent}")
    return root


def verify_original_sources(ledger: dict) -> list[str]:
    failures = []
    for source in ledger["sources"]:
        path = Path(source["original_path"])
        if not path.is_file():
            failures.append(f"{source['source_group']}: source missing")
            continue
        if path.stat().st_size != source["bytes"]:
            failures.append(f"{source['source_group']}: source size changed")
            continue
        if sha256_file(path) != source["sha256"]:
            failures.append(f"{source['source_group']}: source hash changed")
    return failures


def ffprobe(path: Path, binary: str) -> dict:
    completed = subprocess.run(
        [
            binary,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            (
                "stream=codec_name,sample_rate,channels,bits_per_sample,"
                "bits_per_raw_sample:format=duration"
            ),
            "-of",
            "json",
            str(path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    value = json.loads(completed.stdout)
    streams = value.get("streams", [])
    if len(streams) != 1:
        raise ValueError("expected exactly one selected audio stream")
    stream = streams[0]
    duration = float(value.get("format", {}).get("duration", 0))
    return {
        "codec_name": stream.get("codec_name"),
        "sample_rate_hz": int(stream.get("sample_rate", 0)),
        "channel_count": int(stream.get("channels", 0)),
        "bits_per_sample": int(
            stream.get("bits_per_raw_sample")
            or stream.get("bits_per_sample")
            or 0
        ),
        "duration_seconds": duration,
    }


def artist_key(path: Path) -> str:
    artist, separator, _ = path.stem.partition(" - ")
    return (artist if separator else path.stem).casefold()


def candidate_paths(source_dirs: list[Path], seed: int) -> list[Path]:
    paths = sorted(
        {
            path.resolve()
            for source_dir in source_dirs
            for path in source_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        }
    )
    random.Random(seed).shuffle(paths)
    return paths


def output_recipe(
    case_id: str,
    source_path: str,
    output_path: str,
    codec: str,
    *,
    encoder: str | None = None,
    bitrate: str | None = None,
    quality: int | None = None,
    pre_filters: list[str] | None = None,
    post_filters: list[str] | None = None,
    bits: int = 24,
    channel_count: int | None = None,
) -> dict:
    recipe: dict = {
        "case_id": case_id,
        "source_relative_path": source_path,
        "output_relative_path": output_path,
        "intermediate_codec": codec,
        "output_bits_per_sample": bits,
    }
    if encoder is not None:
        recipe["encoder"] = encoder
    if bitrate is not None:
        recipe["bitrate"] = bitrate
    if quality is not None:
        recipe["quality"] = quality
    if pre_filters:
        recipe["pre_filters"] = pre_filters
    if post_filters:
        recipe["post_filters"] = post_filters
    if channel_count is not None:
        recipe["channel_count"] = channel_count
    return recipe


def add_variant(
    cases: list[dict],
    recipes: list[dict],
    *,
    source_group: str,
    source_path: str,
    suffix: str,
    class_name: str,
    expectation: str,
    output_extension: str,
    codec: str,
    encoder: str | None = None,
    bitrate: str | None = None,
    quality: int | None = None,
    pre_filters: list[str] | None = None,
    post_filters: list[str] | None = None,
    bits: int = 24,
    channel_count: int | None = None,
) -> None:
    case_id = f"{source_group}-{suffix}"
    output_path = f"generated/{case_id}.{output_extension}"
    cases.append(
        {
            "case_id": case_id,
            "source_group": source_group,
            "relative_path": output_path,
            "provenance_tier": "tier_b_trusted",
            "split": "development",
            "class": class_name,
            "expectation": expectation,
        }
    )
    recipes.append(
        output_recipe(
            case_id,
            source_path,
            output_path,
            codec,
            encoder=encoder,
            bitrate=bitrate,
            quality=quality,
            pre_filters=pre_filters,
            post_filters=post_filters,
            bits=bits,
            channel_count=channel_count,
        )
    )


def add_variants(
    cases: list[dict],
    recipes: list[dict],
    source_group: str,
    source_path: str,
) -> None:
    shared = {
        "cases": cases,
        "recipes": recipes,
        "source_group": source_group,
        "source_path": source_path,
    }
    add_variant(
        **shared,
        suffix="lowpass-15700-wav24",
        class_name="lowpass_only_pcm",
        expectation="negative",
        output_extension="wav",
        codec="pcm",
        pre_filters=["lowpass=f=15700:p=2"],
    )
    add_variant(
        **shared,
        suffix="gain-minus6-flac24",
        class_name="gain_only_pcm",
        expectation="negative",
        output_extension="flac",
        codec="pcm",
        pre_filters=["volume=-6dB"],
    )
    add_variant(
        **shared,
        suffix="trim-250ms-aiff24",
        class_name="trim_only_pcm",
        expectation="negative",
        output_extension="aiff",
        codec="pcm",
        pre_filters=["atrim=start=0.25", "asetpts=PTS-STARTPTS"],
    )
    add_variant(
        **shared,
        suffix="dither16-wav16",
        class_name="dither_16_pcm",
        expectation="negative",
        output_extension="wav",
        codec="pcm",
        post_filters=["aresample=osf=s16:dither_method=triangular"],
        bits=16,
    )
    add_variant(
        **shared,
        suffix="mp3-128-wav24",
        class_name="mp3_128",
        expectation="controlled_positive",
        output_extension="wav",
        codec="mp3",
        encoder="libmp3lame",
        bitrate="128k",
    )
    add_variant(
        **shared,
        suffix="mp3-320-flac24",
        class_name="mp3_320",
        expectation="controlled_positive",
        output_extension="flac",
        codec="mp3",
        encoder="libmp3lame",
        bitrate="320k",
    )
    add_variant(
        **shared,
        suffix="aac-128-aiff16",
        class_name="aac_lc_128",
        expectation="controlled_positive",
        output_extension="aiff",
        codec="aac",
        encoder="aac",
        bitrate="128k",
        bits=16,
    )
    add_variant(
        **shared,
        suffix="aac-256-flac24",
        class_name="aac_lc_256",
        expectation="controlled_positive",
        output_extension="flac",
        codec="aac",
        encoder="aac",
        bitrate="256k",
    )
    add_variant(
        **shared,
        suffix="opus-96-wav16",
        class_name="opus_96",
        expectation="controlled_positive",
        output_extension="wav",
        codec="opus",
        encoder="libopus",
        bitrate="96k",
        bits=16,
    )
    add_variant(
        **shared,
        suffix="opus-160-aiff24",
        class_name="opus_160",
        expectation="controlled_positive",
        output_extension="aiff",
        codec="opus",
        encoder="libopus",
        bitrate="160k",
    )
    add_variant(
        **shared,
        suffix="vorbis-q3-flac16",
        class_name="vorbis_q3",
        expectation="controlled_positive",
        output_extension="flac",
        codec="vorbis",
        encoder="vorbis",
        quality=3,
        bits=16,
        channel_count=2,
    )
    add_variant(
        **shared,
        suffix="vorbis-q5-wav24",
        class_name="vorbis_q5",
        expectation="controlled_positive",
        output_extension="wav",
        codec="vorbis",
        encoder="vorbis",
        quality=5,
        channel_count=2,
    )


def add_codec_holdout_variants(
    cases: list[dict],
    recipes: list[dict],
    source_group: str,
    source_path: str,
) -> None:
    shared = {
        "cases": cases,
        "recipes": recipes,
        "source_group": source_group,
        "source_path": source_path,
        "expectation": "controlled_positive",
        "output_extension": "flac",
        "bits": 24,
    }
    for suffix, class_name, codec, options in (
        ("mp3-96-flac24", "mp3_96", "mp3", {"bitrate": "96k"}),
        ("mp3-192-flac24", "mp3_192", "mp3", {"bitrate": "192k"}),
        (
            "mp3-vbr-q2-flac24",
            "mp3_vbr_q2",
            "mp3",
            {"quality": 2},
        ),
        ("aac-96-flac24", "aac_lc_96", "aac", {"bitrate": "96k"}),
        ("aac-192-flac24", "aac_lc_192", "aac", {"bitrate": "192k"}),
        ("aac-320-flac24", "aac_lc_320", "aac", {"bitrate": "320k"}),
        ("opus-64-flac24", "opus_64", "opus", {"bitrate": "64k"}),
        ("opus-128-flac24", "opus_128", "opus", {"bitrate": "128k"}),
        ("opus-192-flac24", "opus_192", "opus", {"bitrate": "192k"}),
        (
            "vorbis-q1-flac24",
            "vorbis_q1",
            "vorbis",
            {"quality": 1, "channel_count": 2},
        ),
        (
            "vorbis-q7-flac24",
            "vorbis_q7",
            "vorbis",
            {"quality": 7, "channel_count": 2},
        ),
    ):
        encoder = {
            "aac": "aac",
            "mp3": "libmp3lame",
            "opus": "libopus",
            "vorbis": "vorbis",
        }[codec]
        add_variant(
            **shared,
            suffix=suffix,
            class_name=class_name,
            codec=codec,
            encoder=encoder,
            **options,
        )


def redacted_excerpt_command(
    command: list[str],
    *,
    parent_root: Path,
    output_root: Path,
) -> list[str]:
    return [
        part.replace(str(parent_root), "<PARENT_CORPUS>").replace(
            str(output_root),
            "<AUDIO_ROOT>",
        )
        for part in command
    ]


def untouched_development_cases(manifest: dict) -> list[dict]:
    cases = sorted(
        (
            case
            for case in manifest.get("cases", [])
            if case.get("class") == "untouched_lossless"
            and case.get("split") == "development"
            and case.get("expectation") == "negative"
        ),
        key=lambda case: case.get("source_group", ""),
    )
    if not cases:
        raise SystemExit(
            "source manifest contains no negative development "
            "untouched_lossless cases"
        )
    source_groups = [case.get("source_group") for case in cases]
    if any(
        not isinstance(source_group, str) or not source_group
        for source_group in source_groups
    ):
        raise SystemExit("untouched source case has no source_group")
    if len(source_groups) != len(set(source_groups)):
        raise SystemExit(
            "source manifest contains multiple untouched cases for a source group"
        )
    if any(
        not isinstance(case.get("relative_path"), str)
        or not case["relative_path"]
        for case in cases
    ):
        raise SystemExit("untouched source case has no relative_path")
    return cases


def redacted_control_command(
    command: list[str],
    *,
    source_root: Path,
    output_root: Path,
) -> list[str]:
    return [
        part.replace(str(source_root), "<SOURCE_CORPUS>").replace(
            str(output_root),
            "<AUDIO_ROOT>",
        )
        for part in command
    ]


def command_resample_controls(args: argparse.Namespace) -> int:
    if args.target_sample_rate <= 0:
        raise SystemExit("target sample rate must be positive")
    if args.analysis_max_seconds <= 0:
        raise SystemExit("analysis duration must be positive")
    if not 1 <= args.repetitions <= 20:
        raise SystemExit("repetitions must be in 1..=20")

    root = resolve_new_root(args.audio_root)
    source_root = Path(args.source_audio_root).expanduser().resolve()
    if not source_root.is_dir():
        raise SystemExit(f"source audio root does not exist: {source_root}")
    source_manifest_path = Path(args.source_manifest).expanduser().resolve()
    source_manifest = json.loads(
        source_manifest_path.read_text(encoding="utf-8")
    )
    originals = untouched_development_cases(source_manifest)

    resolved_sources: list[tuple[dict, Path]] = []
    for case in originals:
        source = (source_root / case["relative_path"]).resolve()
        if not source.is_relative_to(source_root):
            raise SystemExit(
                f"source path escapes corpus root: {case['relative_path']}"
            )
        if not source.is_file():
            raise SystemExit(f"source audio is missing: {source}")
        resolved_sources.append((case, source))

    root.mkdir(mode=0o700)
    generated_root = root / "generated"
    generated_root.mkdir()
    ledger_path = root / "run-ledger.json"
    manifest_path = root / "manifest.json"
    ffmpeg_version = subprocess.run(
        [args.ffmpeg, "-version"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()[0]
    ffprobe_version = subprocess.run(
        [args.ffprobe, "-version"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()[0]
    ledger = {
        "schema_version": 1,
        "run_id": args.run_id,
        "state": "staging_resample_controls",
        "created_at": now(),
        "cleanup_target": str(root),
        "source_audio_root_at_staging": str(source_root),
        "source_manifest_path_at_staging": str(source_manifest_path),
        "source_manifest_sha256": sha256_file(source_manifest_path),
        "target_sample_rate_hz": args.target_sample_rate,
        "output_codec": "pcm_s24le",
        "analysis_max_seconds": args.analysis_max_seconds,
        "ffmpeg_version": ffmpeg_version,
        "ffprobe_version": ffprobe_version,
        "sources": [],
        "commands": [],
    }
    write_atomic(ledger_path, ledger)

    cases: list[dict] = []
    for index, (original, source) in enumerate(resolved_sources, 1):
        source_group = original["source_group"]
        source_bytes = source.stat().st_size
        source_sha256 = sha256_file(source)
        output_relative_path = f"generated/control-{index:03}.wav"
        output = root / output_relative_path
        command = [
            args.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-n",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-t",
            str(args.analysis_max_seconds),
            "-ar",
            str(args.target_sample_rate),
            "-c:a",
            "pcm_s24le",
            str(output),
        ]
        print(
            f"[control {index:03}/{len(resolved_sources)}] {source_group}",
            file=sys.stderr,
        )
        subprocess.run(command, check=True)
        if (
            source.stat().st_size != source_bytes
            or sha256_file(source) != source_sha256
        ):
            raise SystemExit(
                f"source audio changed while creating control: {source_group}"
            )
        output_probe = ffprobe(output, args.ffprobe)
        if (
            output_probe["codec_name"] != "pcm_s24le"
            or output_probe["sample_rate_hz"] != args.target_sample_rate
        ):
            raise SystemExit(
                f"generated control has unexpected format: {source_group}"
            )

        case = {
            "case_id": f"pcm-control-{index:03}",
            "source_group": source_group,
            "relative_path": output_relative_path,
            "provenance_tier": original["provenance_tier"],
            "split": "development",
            "class": f"resample_{args.target_sample_rate}_pcm",
            "expectation": "negative",
            "source_case_id": original["case_id"],
        }
        if "partition_group" in original:
            case["partition_group"] = original["partition_group"]
        cases.append(case)
        ledger["commands"].append(
            redacted_control_command(
                command,
                source_root=source_root,
                output_root=root,
            )
        )
        ledger["sources"].append(
            {
                "source_group": source_group,
                "source_case_id": original["case_id"],
                "source_relative_path": original["relative_path"],
                "source_bytes": source_bytes,
                "source_sha256": source_sha256,
                "output_relative_path": output_relative_path,
                "output_bytes": output.stat().st_size,
                "output_sha256": sha256_file(output),
                "output_probe": output_probe,
            }
        )
        write_atomic(ledger_path, ledger)

    manifest = {
        "schema_version": 1,
        "corpus_id": args.run_id,
        "corpus_version": 1,
        "audio_root_env": "LOSSYTRACE_RESEARCH_ROOT",
        "analysis_max_seconds": args.analysis_max_seconds,
        "repetitions": args.repetitions,
        "cases": cases,
    }
    write_atomic(manifest_path, manifest)
    ledger["state"] = "resample_controls_staged"
    ledger["completed_at"] = now()
    ledger["manifest_relative_path"] = manifest_path.name
    ledger["manifest_sha256"] = sha256_file(manifest_path)
    ledger["case_count"] = len(cases)
    ledger["output_bytes"] = sum(
        source["output_bytes"] for source in ledger["sources"]
    )
    ledger["free_bytes_after_staging"] = shutil.disk_usage(root).free
    write_atomic(ledger_path, ledger)

    if args.pointer:
        write_atomic(
            args.pointer.expanduser().resolve(),
            {
                "schema_version": 1,
                "run_id": args.run_id,
                "created_at": ledger["created_at"],
                "state": ledger["state"],
                "audio_root": str(root),
                "manifest": str(manifest_path),
                "ledger": str(ledger_path),
                "cleanup_target": str(root),
                "source_manifest_sha256": ledger["source_manifest_sha256"],
            },
        )
    print(
        f"staged {len(cases)} PCM-only {args.target_sample_rate} Hz controls "
        f"under {root}"
    )
    return 0


def command_codec_holdout(args: argparse.Namespace) -> int:
    root = resolve_new_root(args.audio_root)
    parent_root = Path(args.parent_audio_root).expanduser().resolve()
    if not parent_root.is_dir():
        raise SystemExit(f"parent audio root does not exist: {parent_root}")
    parent_manifest_path = Path(args.parent_manifest).expanduser().resolve()
    parent_ledger_path = Path(args.parent_ledger).expanduser().resolve()
    parent_manifest = json.loads(
        parent_manifest_path.read_text(encoding="utf-8")
    )
    parent_ledger = json.loads(parent_ledger_path.read_text(encoding="utf-8"))
    if parent_ledger.get("run_id") != args.parent_run_id:
        raise SystemExit("parent ledger run ID differs from --parent-run-id")
    if args.excerpt_start_seconds < 0 or args.excerpt_duration_seconds <= 0:
        raise SystemExit("excerpt start must be non-negative and duration positive")

    originals = sorted(
        (
            case
            for case in parent_manifest["cases"]
            if case["class"] == "untouched_lossless"
        ),
        key=lambda case: case["source_group"],
    )
    parent_sources = {
        source["source_group"]: source for source in parent_ledger["sources"]
    }
    if not originals:
        raise SystemExit("parent manifest contains no untouched sources")
    if {case["source_group"] for case in originals} != set(parent_sources):
        raise SystemExit("parent manifest and ledger source groups differ")

    root.mkdir(mode=0o700)
    source_root = root / "sources"
    source_root.mkdir()
    ledger_path = root / "run-ledger.json"
    ffmpeg_version = subprocess.run(
        [args.ffmpeg, "-version"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()[0]
    ledger = {
        "schema_version": 1,
        "run_id": args.run_id,
        "state": "staging_codec_holdout",
        "created_at": now(),
        "cleanup_target": str(root),
        "parent_run_id": args.parent_run_id,
        "parent_audio_root_at_staging": str(parent_root),
        "parent_manifest_sha256": sha256_file(parent_manifest_path),
        "parent_ledger_sha256": sha256_file(parent_ledger_path),
        "ffmpeg_version": ffmpeg_version,
        "excerpt_start_seconds": args.excerpt_start_seconds,
        "excerpt_duration_seconds": args.excerpt_duration_seconds,
        "sources": [],
        "excerpt_commands": [],
    }
    write_atomic(ledger_path, ledger)

    for index, original in enumerate(originals, 1):
        source_group = original["source_group"]
        source_record = parent_sources[source_group]
        parent_source = (
            parent_root / original["relative_path"]
        ).resolve()
        if not parent_source.is_relative_to(parent_root):
            raise SystemExit(f"parent source escapes root: {parent_source}")
        if not parent_source.is_file():
            raise SystemExit(f"parent source is missing: {parent_source}")
        if sha256_file(parent_source) != source_record["sha256"]:
            raise SystemExit(f"parent source hash differs: {source_group}")

        relative_path = f"sources/{source_group}-excerpt.flac"
        output = root / relative_path
        command = [
            args.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-n",
            "-ss",
            str(args.excerpt_start_seconds),
            "-t",
            str(args.excerpt_duration_seconds),
            "-i",
            str(parent_source),
            "-map",
            "0:a:0",
            "-c:a",
            "flac",
            "-sample_fmt",
            "s32",
            "-bits_per_raw_sample",
            "24",
            str(output),
        ]
        print(
            f"[excerpt {index:02}/{len(originals)}] {source_group}",
            file=sys.stderr,
        )
        subprocess.run(command, check=True)
        ledger["excerpt_commands"].append(
            redacted_excerpt_command(
                command,
                parent_root=parent_root,
                output_root=root,
            )
        )
        ledger["sources"].append(
            {
                "source_group": source_group,
                "original_path": source_record["original_path"],
                "bytes": source_record["bytes"],
                "sha256": source_record["sha256"],
                "probe": source_record["probe"],
                "parent_staged_relative_path": original["relative_path"],
                "staged_relative_path": relative_path,
                "staged_bytes": output.stat().st_size,
                "staged_sha256": sha256_file(output),
            }
        )
        write_atomic(ledger_path, ledger)

    cases: list[dict] = []
    recipes: list[dict] = []
    for source in ledger["sources"]:
        source_group = source["source_group"]
        source_path = source["staged_relative_path"]
        cases.append(
            {
                "case_id": f"{source_group}-holdout-original",
                "source_group": source_group,
                "relative_path": source_path,
                "provenance_tier": "tier_b_trusted",
                "split": "development",
                "class": "untouched_lossless_excerpt",
                "expectation": "negative",
            }
        )
        add_codec_holdout_variants(
            cases,
            recipes,
            source_group,
            source_path,
        )

    manifest = {
        "schema_version": 1,
        "corpus_id": args.run_id,
        "corpus_version": 1,
        "audio_root_env": "LOSSYTRACE_RESEARCH_ROOT",
        "analysis_max_seconds": args.excerpt_duration_seconds,
        "repetitions": 1,
        "cases": cases,
        "recipes": recipes,
    }
    manifest_path = root / "manifest.json"
    write_atomic(manifest_path, manifest)
    ledger["state"] = "codec_holdout_staged"
    ledger["completed_at"] = now()
    ledger["manifest_relative_path"] = manifest_path.name
    ledger["case_count"] = len(cases)
    ledger["recipe_count"] = len(recipes)
    ledger["source_bytes"] = sum(
        source["staged_bytes"] for source in ledger["sources"]
    )
    ledger["free_bytes_after_staging"] = shutil.disk_usage(root).free
    write_atomic(ledger_path, ledger)

    if args.pointer:
        write_atomic(
            args.pointer.expanduser().resolve(),
            {
                "schema_version": 1,
                "run_id": args.run_id,
                "created_at": ledger["created_at"],
                "state": ledger["state"],
                "audio_root": str(root),
                "manifest": str(manifest_path),
                "cleanup_target": str(root),
                "parent_run_id": args.parent_run_id,
            },
        )
    print(
        f"staged {len(ledger['sources'])} lossless excerpts and "
        f"{len(cases)} settings-holdout cases under {root}"
    )
    return 0


def command_stage(args: argparse.Namespace) -> int:
    root = resolve_new_root(args.audio_root)
    source_dirs = [Path(value).expanduser().resolve() for value in args.source_dir]
    for source_dir in source_dirs:
        if not source_dir.is_dir():
            raise SystemExit(f"source directory does not exist: {source_dir}")

    root.mkdir()
    source_root = root / "sources"
    source_root.mkdir()
    run_state_path = root / "run-ledger.json"
    ledger = {
        "schema_version": 1,
        "run_id": args.run_id,
        "state": "staging",
        "created_at": now(),
        "cleanup_target": str(root),
        "source_directories": [str(path) for path in source_dirs],
        "requested_source_count": args.count,
        "selection_seed": args.seed,
        "sources": [],
        "rejections": [],
    }
    write_atomic(run_state_path, ledger)

    selected_artists: set[str] = set()
    for candidate in candidate_paths(source_dirs, args.seed):
        if len(ledger["sources"]) >= args.count:
            break
        artist = artist_key(candidate)
        if artist in selected_artists:
            ledger["rejections"].append(
                {"path": str(candidate), "reason": "artist_already_selected"}
            )
            continue
        try:
            probe = ffprobe(candidate, args.ffprobe)
        except (ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
            ledger["rejections"].append(
                {"path": str(candidate), "reason": f"ffprobe_failed: {error}"}
            )
            continue
        reason = None
        if probe["codec_name"] not in LOSSLESS_CODECS:
            reason = f"codec_not_supported: {probe['codec_name']}"
        elif probe["sample_rate_hz"] < args.min_sample_rate:
            reason = f"sample_rate_below_minimum: {probe['sample_rate_hz']}"
        elif probe["channel_count"] != 2:
            reason = f"channel_count_not_stereo: {probe['channel_count']}"
        elif probe["duration_seconds"] < args.min_duration:
            reason = f"duration_below_minimum: {probe['duration_seconds']}"
        elif probe["duration_seconds"] > args.max_duration:
            reason = f"duration_above_maximum: {probe['duration_seconds']}"
        if reason:
            ledger["rejections"].append(
                {"path": str(candidate), "reason": reason}
            )
            continue

        number = len(ledger["sources"]) + 1
        source_group = f"dev-{number:03}"
        relative_path = f"sources/{source_group}{candidate.suffix.lower()}"
        staged = root / relative_path
        source_hash = sha256_file(candidate)
        shutil.copy2(candidate, staged)
        staged_hash = sha256_file(staged)
        if source_hash != staged_hash:
            raise SystemExit(f"copy fingerprint mismatch: {candidate}")
        ledger["sources"].append(
            {
                "source_group": source_group,
                "original_path": str(candidate),
                "staged_relative_path": relative_path,
                "bytes": staged.stat().st_size,
                "sha256": staged_hash,
                "probe": probe,
            }
        )
        selected_artists.add(artist)
        write_atomic(run_state_path, ledger)

    if len(ledger["sources"]) != args.count:
        ledger["state"] = "incomplete"
        ledger["completed_at"] = now()
        write_atomic(run_state_path, ledger)
        raise SystemExit(
            f"selected {len(ledger['sources'])} usable independent artists; "
            f"{args.count} required"
        )

    cases: list[dict] = []
    recipes: list[dict] = []
    for source in ledger["sources"]:
        source_group = source["source_group"]
        source_path = source["staged_relative_path"]
        cases.append(
            {
                "case_id": f"{source_group}-original",
                "source_group": source_group,
                "relative_path": source_path,
                "provenance_tier": "tier_b_trusted",
                "split": "development",
                "class": "untouched_lossless",
                "expectation": "negative",
            }
        )
        add_variants(cases, recipes, source_group, source_path)

    manifest = {
        "schema_version": 1,
        "corpus_id": args.run_id,
        "corpus_version": 1,
        "audio_root_env": "LOSSYTRACE_RESEARCH_ROOT",
        "analysis_max_seconds": args.analysis_max_seconds,
        "repetitions": args.repetitions,
        "cases": cases,
        "recipes": recipes,
    }
    manifest_path = root / "manifest.json"
    write_atomic(manifest_path, manifest)
    ledger["state"] = "staged"
    ledger["completed_at"] = now()
    ledger["manifest_relative_path"] = manifest_path.relative_to(root).as_posix()
    ledger["case_count"] = len(cases)
    ledger["recipe_count"] = len(recipes)
    ledger["source_bytes"] = sum(source["bytes"] for source in ledger["sources"])
    ledger["free_bytes_after_staging"] = shutil.disk_usage(root).free
    write_atomic(run_state_path, ledger)

    if args.pointer:
        write_atomic(
            args.pointer.expanduser().resolve(),
            {
                "schema_version": 1,
                "run_id": args.run_id,
                "created_at": ledger["created_at"],
                "audio_root": str(root),
                "manifest": str(manifest_path),
                "cleanup_target": str(root),
            },
        )
    print(
        f"staged {len(ledger['sources'])} sources and {len(cases)} cases "
        f"under {root}"
    )
    return 0


def command_snapshot(args: argparse.Namespace) -> int:
    root = Path(args.audio_root).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"audio root does not exist: {root}")
    manifests = [
        json.loads(
            Path(value).expanduser().resolve().read_text(encoding="utf-8")
        )
        for value in args.manifest
    ]
    output = Path(args.output).expanduser().resolve()
    planned_audio = {
        case["relative_path"]
        for manifest in manifests
        for case in manifest["cases"]
    }
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == output:
            continue
        relative = path.relative_to(root).as_posix()
        files.append(
            {
                "relative_path": relative,
                "bytes": path.stat().st_size,
                "kind": (
                    "planned_audio"
                    if relative in planned_audio
                    else "control"
                    if path.parent == root and path.suffix == ".json"
                    else "unexpected"
                ),
            }
        )
    present = {item["relative_path"] for item in files}
    inventory = {
        "schema_version": 1,
        "created_at": now(),
        "audio_root": str(root),
        "cleanup_target": str(root),
        "inventory_self_excluded": True,
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "planned_audio_count": len(planned_audio),
        "missing_planned_audio": sorted(planned_audio - present),
        "unexpected_paths": sorted(
            item["relative_path"]
            for item in files
            if item["kind"] == "unexpected"
        ),
        "files": files,
    }
    write_atomic(output, inventory)
    if args.ledger:
        ledger_path = Path(args.ledger).expanduser().resolve()
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        if args.state:
            ledger["state"] = args.state
        ledger["latest_artifact_inventory"] = output.name
        ledger.pop("retained_bytes", None)
        ledger.pop("retained_file_count", None)
        ledger["retained_bytes_excluding_inventory"] = inventory["total_bytes"]
        ledger["retained_file_count_excluding_inventory"] = inventory[
            "file_count"
        ]
        ledger["missing_planned_audio_count"] = len(
            inventory["missing_planned_audio"]
        )
        ledger["unexpected_path_count"] = len(inventory["unexpected_paths"])
        ledger["inventory_updated_at"] = now()
        write_atomic(ledger_path, ledger)
    if args.pointer:
        pointer_path = args.pointer.expanduser().resolve()
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        retained_files = [path for path in root.rglob("*") if path.is_file()]
        pointer["state"] = args.state or pointer.get("state")
        pointer["retained_bytes"] = sum(
            path.stat().st_size for path in retained_files
        )
        pointer["retained_file_count"] = len(retained_files)
        pointer["artifact_inventory"] = str(output)
        pointer["missing_planned_audio_count"] = len(
            inventory["missing_planned_audio"]
        )
        pointer["unexpected_path_count"] = len(inventory["unexpected_paths"])
        pointer["updated_at"] = now()
        write_atomic(pointer_path, pointer)
    print(
        f"snapshotted {len(files)} files ({inventory['total_bytes']} bytes); "
        f"missing={len(inventory['missing_planned_audio'])} "
        f"unexpected={len(inventory['unexpected_paths'])}"
    )
    return 0


def command_window(args: argparse.Namespace) -> int:
    source = Path(args.manifest).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"manifest does not exist: {source}")
    if output.exists():
        raise SystemExit(f"derived manifest already exists: {output}")
    if args.analysis_max_seconds <= 0:
        raise SystemExit("analysis window must be greater than zero")
    manifest = json.loads(source.read_text(encoding="utf-8"))
    manifest["corpus_id"] = (
        f"{manifest['corpus_id']}-window-{args.analysis_max_seconds:g}s"
    )
    manifest["analysis_max_seconds"] = args.analysis_max_seconds
    write_atomic(output, manifest)

    ledger_path = Path(args.ledger).expanduser().resolve()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["analysis_manifests"] = {
        "full_track": source.name,
        f"window_{args.analysis_max_seconds:g}s": output.name,
    }
    ledger["active_analysis_manifest"] = output.name
    ledger["analysis_manifest_updated_at"] = now()
    write_atomic(ledger_path, ledger)

    if args.pointer:
        pointer = json.loads(
            args.pointer.expanduser().resolve().read_text(encoding="utf-8")
        )
        pointer["manifest"] = str(output)
        pointer["full_track_manifest"] = str(source)
        pointer["updated_at"] = now()
        write_atomic(args.pointer.expanduser().resolve(), pointer)
    print(
        f"derived {args.analysis_max_seconds:g}s manifest at {output}; "
        f"preserved full-track manifest at {source}"
    )
    return 0


def command_sharp_lowpass(args: argparse.Namespace) -> int:
    source = Path(args.manifest).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"manifest does not exist: {source}")
    if output.exists():
        raise SystemExit(f"sharp-lowpass manifest already exists: {output}")
    manifest = json.loads(source.read_text(encoding="utf-8"))
    originals = [
        case
        for case in manifest["cases"]
        if case["class"] == "untouched_lossless"
    ]
    cases = []
    recipes = []
    for original in originals:
        source_group = original["source_group"]
        case_id = f"{source_group}-sharp-lowpass-15700-wav24"
        output_path = f"generated/{case_id}.wav"
        cases.append(
            {
                "case_id": case_id,
                "source_group": source_group,
                "relative_path": output_path,
                "provenance_tier": original["provenance_tier"],
                "split": "development",
                "class": "sharp_lowpass_only_pcm",
                "expectation": "negative",
            }
        )
        recipes.append(
            output_recipe(
                case_id,
                original["relative_path"],
                output_path,
                "pcm",
                pre_filters=[
                    (
                        "firequalizer="
                        "gain='if(lt(f,15700),0,-80)':"
                        "delay=0.1:accuracy=1:zero_phase=on"
                    )
                ],
            )
        )
    auxiliary = {
        "schema_version": manifest["schema_version"],
        "corpus_id": f"{manifest['corpus_id']}-sharp-lowpass",
        "corpus_version": manifest["corpus_version"],
        "audio_root_env": manifest["audio_root_env"],
        "analysis_max_seconds": args.analysis_max_seconds,
        "repetitions": args.repetitions,
        "cases": cases,
        "recipes": recipes,
    }
    write_atomic(output, auxiliary)

    ledger_path = Path(args.ledger).expanduser().resolve()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    auxiliary_manifests = ledger.setdefault("auxiliary_manifests", {})
    auxiliary_manifests["sharp_lowpass"] = output.name
    ledger["auxiliary_manifest_updated_at"] = now()
    write_atomic(ledger_path, ledger)
    print(f"wrote {len(cases)} sharp-lowpass cases to {output}")
    return 0


def command_subset(args: argparse.Namespace) -> int:
    sources = [
        json.loads(
            Path(value).expanduser().resolve().read_text(encoding="utf-8")
        )
        for value in args.manifest
    ]
    source_groups = sorted(
        {
            case["source_group"]
            for manifest in sources
            for case in manifest["cases"]
        }
    )
    random.Random(args.seed).shuffle(source_groups)
    selected = set(source_groups[: args.source_count])
    cases = [
        case
        for manifest in sources
        for case in manifest["cases"]
        if case["source_group"] in selected
    ]
    recipes = [
        recipe
        for manifest in sources
        for recipe in manifest.get("recipes", [])
        if recipe["case_id"] in {case["case_id"] for case in cases}
    ]
    case_ids = [case["case_id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise SystemExit("subset manifests contain duplicate case IDs")
    if len(selected) != args.source_count:
        raise SystemExit(
            f"requested {args.source_count} source groups, found "
            f"{len(source_groups)}"
        )
    subset = {
        "schema_version": sources[0]["schema_version"],
        "corpus_id": (
            f"{sources[0]['corpus_id']}-research-{args.source_count}x"
            f"{args.analysis_max_seconds:g}s"
        ),
        "corpus_version": sources[0]["corpus_version"],
        "audio_root_env": sources[0]["audio_root_env"],
        "analysis_max_seconds": args.analysis_max_seconds,
        "repetitions": args.repetitions,
        "cases": cases,
        "recipes": recipes,
    }
    output = args.output.expanduser().resolve()
    if output.exists():
        raise SystemExit(f"subset manifest already exists: {output}")
    write_atomic(output, subset)
    print(
        f"wrote {len(cases)} cases from {len(selected)} source groups to "
        f"{output}"
    )
    return 0


def command_verify_sources(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger).expanduser().resolve()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    failures = verify_original_sources(ledger)
    if failures:
        print("source verification failed:")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    print(f"verified {len(ledger['sources'])} original source hashes unchanged")
    return 0


def write_integrity_manifest(
    root: Path,
    run_id: str,
    name: str,
) -> Path:
    output = root / name
    if output.exists():
        raise SystemExit(f"integrity manifest already exists: {output}")
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        files.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": now(),
        "integrity_manifest_self_excluded": True,
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "files": files,
    }
    write_atomic(output, manifest)
    return output


def write_corpus_integrity_manifest(root: Path, run_id: str) -> Path:
    return write_integrity_manifest(
        root,
        run_id,
        "corpus-integrity.json",
    )


def verify_archive(archive: Path, record: dict, zstd_binary: str) -> list[str]:
    failures = []
    integrity_name = record.get(
        "integrity_manifest_name",
        "corpus-integrity.json",
    )
    if not archive.is_file():
        return [f"archive missing: {archive}"]
    if archive.stat().st_size != record["archive_bytes"]:
        failures.append("archive size differs from archive record")
    if sha256_file(archive) != record["archive_sha256"]:
        failures.append("archive SHA-256 differs from archive record")
    if failures:
        return failures

    decompressor = subprocess.Popen(
        [zstd_binary, "-dc", str(archive)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if decompressor.stdout is None or decompressor.stderr is None:
        decompressor.kill()
        return ["failed to open archive decompressor pipes"]

    actual: dict[str, dict] = {}
    integrity_bytes: bytes | None = None
    try:
        with tarfile.open(fileobj=decompressor.stdout, mode="r|") as archive_tar:
            for member in archive_tar:
                if not member.isfile():
                    continue
                relative = member.name.removeprefix("./")
                extracted = archive_tar.extractfile(member)
                if extracted is None:
                    failures.append(f"could not read archived file: {relative}")
                    continue
                if relative == integrity_name:
                    integrity_bytes = extracted.read()
                    actual[relative] = {
                        "bytes": len(integrity_bytes),
                        "sha256": hashlib.sha256(integrity_bytes).hexdigest(),
                    }
                else:
                    actual[relative] = {
                        "bytes": member.size,
                        "sha256": sha256_stream(extracted),
                    }
    except (tarfile.TarError, OSError) as error:
        failures.append(f"could not stream archive: {error}")
    finally:
        decompressor.stdout.close()
    stderr = decompressor.stderr.read().decode("utf-8", errors="replace")
    return_code = decompressor.wait()
    if return_code != 0:
        failures.append(
            f"zstd decompression failed with status {return_code}: "
            f"{stderr.strip()}"
        )
    if failures:
        return failures
    if integrity_bytes is None:
        return [f"archive does not contain {integrity_name}"]
    if (
        actual[integrity_name]["sha256"]
        != record["integrity_manifest_sha256"]
    ):
        return ["integrity manifest SHA-256 differs from archive record"]

    try:
        integrity = json.loads(integrity_bytes)
    except json.JSONDecodeError as error:
        return [f"invalid archived integrity manifest: {error}"]
    if integrity.get("run_id") != record["run_id"]:
        failures.append("integrity manifest run ID differs from archive record")
    expected = {
        item["relative_path"]: {
            "bytes": item["bytes"],
            "sha256": item["sha256"],
        }
        for item in integrity["files"]
    }
    expected_paths = set(expected) | {integrity_name}
    actual_paths = set(actual)
    for relative in sorted(set(expected) & actual_paths):
        if expected[relative] != actual[relative]:
            failures.append(f"archived content differs: {relative}")
    for relative in sorted(expected_paths - actual_paths):
        failures.append(f"archived file missing: {relative}")
    for relative in sorted(actual_paths - expected_paths):
        failures.append(f"unexpected archived file: {relative}")
    if len(actual) != record["archived_file_count"]:
        failures.append("archived file count differs from archive record")
    return failures


def verify_corpus_integrity(
    root: Path,
    run_id: str,
    integrity_name: str = "corpus-integrity.json",
) -> list[str]:
    failures = []
    integrity_path = root / integrity_name
    if not integrity_path.is_file():
        return ["restored corpus does not contain corpus-integrity.json"]
    integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    if integrity.get("run_id") != run_id:
        failures.append("restored integrity manifest run ID differs")
    expected = {
        item["relative_path"]: item for item in integrity.get("files", [])
    }
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    expected_paths = set(expected) | {integrity_name}
    for relative in sorted(expected_paths - actual_paths):
        failures.append(f"restored file missing: {relative}")
    for relative in sorted(actual_paths - expected_paths):
        failures.append(f"unexpected restored file: {relative}")
    if failures:
        return failures
    for relative, item in sorted(expected.items()):
        path = root / relative
        if path.stat().st_size != item["bytes"]:
            failures.append(f"restored file size differs: {relative}")
        elif sha256_file(path) != item["sha256"]:
            failures.append(f"restored file SHA-256 differs: {relative}")
    return failures


def command_archive(args: argparse.Namespace) -> int:
    pointer_path = args.pointer.expanduser().resolve()
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    run_id = pointer["run_id"]
    root = safe_existing_corpus_root(pointer["cleanup_target"], run_id)
    if Path(pointer["audio_root"]).expanduser().resolve() != root:
        raise SystemExit("pointer audio root differs from cleanup target")

    ledger_path = root / "run-ledger.json"
    inventory_path = root / "artifact-inventory.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if ledger.get("run_id") != run_id:
        raise SystemExit("ledger run ID differs from pointer")
    if inventory.get("cleanup_target") != str(root):
        raise SystemExit("inventory cleanup target differs from pointer")
    if inventory["missing_planned_audio"] or inventory["unexpected_paths"]:
        raise SystemExit("corpus inventory is incomplete or has unexpected files")

    source_failures = verify_original_sources(ledger)
    if source_failures:
        raise SystemExit("\n".join(source_failures))

    destination = args.destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.chmod(0o700)
    archive = destination / f"{run_id}.tar.zst"
    record_path = destination / f"{run_id}.archive.json"
    temporary_archive = destination / f".{run_id}.tar.zst.incomplete"
    for path in (archive, record_path, temporary_archive):
        if path.exists():
            raise SystemExit(f"archive output already exists: {path}")

    integrity_path = write_corpus_integrity_manifest(root, run_id)
    tar_process = subprocess.Popen(
        [args.tar, "-cf", "-", "-C", str(root), "."],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "COPYFILE_DISABLE": "1"},
    )
    if tar_process.stdout is None or tar_process.stderr is None:
        tar_process.kill()
        raise SystemExit("failed to open tar process pipes")
    zstd_process = subprocess.Popen(
        [
            args.zstd,
            f"-{args.compression_level}",
            "-T0",
            "--no-progress",
            "-o",
            str(temporary_archive),
        ],
        stdin=tar_process.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    tar_process.stdout.close()
    _, zstd_stderr = zstd_process.communicate()
    tar_stderr = tar_process.stderr.read()
    tar_return_code = tar_process.wait()
    if tar_return_code != 0 or zstd_process.returncode != 0:
        temporary_archive.unlink(missing_ok=True)
        raise SystemExit(
            "archive creation failed: "
            f"tar={tar_return_code} {tar_stderr.decode(errors='replace').strip()} "
            f"zstd={zstd_process.returncode} "
            f"{zstd_stderr.decode(errors='replace').strip()}"
        )
    temporary_archive.replace(archive)
    archive.chmod(0o600)

    integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    record = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": now(),
        "archive_format": "tar+zstd",
        "archive_path": str(archive),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": sha256_file(archive),
        "archived_file_count": integrity["file_count"] + 1,
        "archived_uncompressed_bytes": (
            integrity["total_bytes"] + integrity_path.stat().st_size
        ),
        "integrity_manifest_sha256": sha256_file(integrity_path),
        "source_root_at_archive_time": str(root),
        "source_removed_after_verification": False,
    }
    write_atomic(record_path, record)
    record_path.chmod(0o600)

    failures = verify_archive(archive, record, args.zstd)
    if failures:
        raise SystemExit(
            "archive verification failed:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )
    record["verified_at"] = now()
    write_atomic(record_path, record)
    record_path.chmod(0o600)

    pointer["state"] = "archived_verified"
    pointer["archive_path"] = str(archive)
    pointer["archive_record"] = str(record_path)
    pointer["archive_bytes"] = record["archive_bytes"]
    pointer["archive_sha256"] = record["archive_sha256"]
    pointer["updated_at"] = now()
    write_atomic(pointer_path, pointer)
    print(
        f"archived and verified {record['archived_file_count']} files at "
        f"{archive} ({record['archive_bytes']} bytes)"
    )
    return 0


def command_verify_archive(args: argparse.Namespace) -> int:
    record_path = args.record.expanduser().resolve()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    archive = Path(record["archive_path"]).expanduser().resolve()
    failures = verify_archive(archive, record, args.zstd)
    if failures:
        print("archive verification failed:")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    print(
        f"verified {record['archived_file_count']} archived files and "
        f"{record['archive_bytes']} compressed bytes"
    )
    return 0


def command_restore_archive(args: argparse.Namespace) -> int:
    record_path = args.record.expanduser().resolve()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    archive = Path(record["archive_path"]).expanduser().resolve()
    integrity_name = record.get(
        "integrity_manifest_name",
        "corpus-integrity.json",
    )
    failures = verify_archive(archive, record, args.zstd)
    if failures:
        raise SystemExit(
            "archive verification failed:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )

    destination = Path(args.destination).expanduser().resolve()
    if destination.exists():
        raise SystemExit(f"restore destination already exists: {destination}")
    if not destination.parent.is_dir():
        raise SystemExit(
            f"restore destination parent does not exist: {destination.parent}"
        )
    temporary = destination.parent / f".{destination.name}.restoring"
    if temporary.exists():
        raise SystemExit(f"temporary restore path already exists: {temporary}")
    temporary.mkdir(mode=0o700)

    decompressor = subprocess.Popen(
        [args.zstd, "-dc", str(archive)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if decompressor.stdout is None or decompressor.stderr is None:
        decompressor.kill()
        raise SystemExit("failed to open archive decompressor pipes")
    tar_process = subprocess.Popen(
        [args.tar, "-xf", "-", "-C", str(temporary)],
        stdin=decompressor.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "COPYFILE_DISABLE": "1"},
    )
    decompressor.stdout.close()
    _, tar_stderr = tar_process.communicate()
    zstd_stderr = decompressor.stderr.read()
    zstd_return_code = decompressor.wait()
    if tar_process.returncode != 0 or zstd_return_code != 0:
        shutil.rmtree(temporary)
        raise SystemExit(
            "archive restore failed: "
            f"tar={tar_process.returncode} "
            f"{tar_stderr.decode(errors='replace').strip()} "
            f"zstd={zstd_return_code} "
            f"{zstd_stderr.decode(errors='replace').strip()}"
        )

    failures = verify_corpus_integrity(
        temporary,
        record["run_id"],
        integrity_name,
    )
    if failures:
        shutil.rmtree(temporary)
        raise SystemExit(
            "restored corpus verification failed:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )
    temporary.replace(destination)

    if args.pointer:
        pointer_path = args.pointer.expanduser().resolve()
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        if pointer.get("run_id") != record["run_id"]:
            raise SystemExit("pointer run ID differs from archive record")
        pointer["state"] = "restored_from_verified_archive"
        pointer["cleanup_target"] = str(destination)
        if integrity_name == "artifact-integrity.json":
            pointer["source_root"] = str(destination)
        else:
            pointer["audio_root"] = str(destination)
            pointer["artifact_inventory"] = str(
                destination / "artifact-inventory.json"
            )
            pointer["manifest"] = str(destination / "manifest-90s.json")
            pointer["full_track_manifest"] = str(destination / "manifest.json")
        pointer["updated_at"] = now()
        write_atomic(pointer_path, pointer)
    print(
        f"restored and verified {record['archived_file_count']} files at "
        f"{destination}"
    )
    return 0


def command_prune_archived_source(args: argparse.Namespace) -> int:
    pointer_path = args.pointer.expanduser().resolve()
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    run_id = pointer["run_id"]
    if args.confirm_run_id != run_id:
        raise SystemExit("confirmation run ID differs from pointer")
    allowed_states = {
        "archived_verified",
        "restored_from_verified_archive",
    }
    if pointer.get("state") not in allowed_states:
        raise SystemExit("pointer is not in a verified removable state")

    root = safe_existing_corpus_root(pointer["cleanup_target"], run_id)
    record_path = Path(pointer["archive_record"]).expanduser().resolve()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record.get("run_id") != run_id:
        raise SystemExit("archive record run ID differs from pointer")
    archive = Path(record["archive_path"]).expanduser().resolve()
    failures = verify_archive(archive, record, args.zstd)
    if failures:
        raise SystemExit(
            "archive verification failed:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )
    failures = verify_corpus_integrity(root, run_id)
    if failures:
        raise SystemExit(
            "local corpus integrity verification failed:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )

    ledger = json.loads((root / "run-ledger.json").read_text(encoding="utf-8"))
    source_failures = verify_original_sources(ledger)
    if source_failures:
        raise SystemExit(
            "original source verification failed:\n"
            + "\n".join(f"- {failure}" for failure in source_failures)
        )
    inventory = json.loads(
        (root / "artifact-inventory.json").read_text(encoding="utf-8")
    )
    if inventory["missing_planned_audio"] or inventory["unexpected_paths"]:
        raise SystemExit("corpus inventory is incomplete or has unexpected files")

    shutil.rmtree(root)
    if root.exists():
        raise SystemExit(f"corpus root still exists after removal: {root}")

    record["source_removed_after_verification"] = True
    record["source_removed_at"] = now()
    write_atomic(record_path, record)
    record_path.chmod(0o600)
    pointer["state"] = "archived_source_removed"
    pointer["audio_root"] = None
    pointer["retained_bytes"] = record["archive_bytes"]
    pointer["retained_file_count"] = record["archived_file_count"]
    pointer["removed_cleanup_target"] = str(root)
    pointer["cleanup_target"] = None
    pointer["updated_at"] = now()
    write_atomic(pointer_path, pointer)
    print(
        f"removed verified redundant source tree {root}; "
        f"retained archive {archive}"
    )
    return 0


def safe_research_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve()
    expected = (Path.cwd() / ".tmp/audio-integrity/research").resolve()
    if root != expected or not root.is_dir():
        raise SystemExit(
            "refusing research root outside the exact repository scratch path: "
            f"{root}"
        )
    return root


def command_archive_research(args: argparse.Namespace) -> int:
    root = safe_research_root(args.source_root)
    integrity_name = "artifact-integrity.json"
    destination = args.destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.chmod(0o700)
    archive = destination / f"{args.run_id}.tar.zst"
    record_path = destination / f"{args.run_id}.archive.json"
    temporary_archive = destination / f".{args.run_id}.tar.zst.incomplete"
    for path in (archive, record_path, temporary_archive):
        if path.exists():
            raise SystemExit(f"archive output already exists: {path}")

    integrity_path = write_integrity_manifest(
        root,
        args.run_id,
        integrity_name,
    )
    tar_process = subprocess.Popen(
        [args.tar, "-cf", "-", "-C", str(root), "."],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "COPYFILE_DISABLE": "1"},
    )
    if tar_process.stdout is None or tar_process.stderr is None:
        tar_process.kill()
        raise SystemExit("failed to open tar process pipes")
    zstd_process = subprocess.Popen(
        [
            args.zstd,
            f"-{args.compression_level}",
            "-T0",
            "--no-progress",
            "-o",
            str(temporary_archive),
        ],
        stdin=tar_process.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    tar_process.stdout.close()
    _, zstd_stderr = zstd_process.communicate()
    tar_stderr = tar_process.stderr.read()
    tar_return_code = tar_process.wait()
    if tar_return_code != 0 or zstd_process.returncode != 0:
        temporary_archive.unlink(missing_ok=True)
        raise SystemExit(
            "research archive creation failed: "
            f"tar={tar_return_code} "
            f"{tar_stderr.decode(errors='replace').strip()} "
            f"zstd={zstd_process.returncode} "
            f"{zstd_stderr.decode(errors='replace').strip()}"
        )
    temporary_archive.replace(archive)
    archive.chmod(0o600)

    integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    record = {
        "schema_version": 1,
        "run_id": args.run_id,
        "created_at": now(),
        "archive_format": "tar+zstd",
        "archive_path": str(archive),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": sha256_file(archive),
        "archived_file_count": integrity["file_count"] + 1,
        "archived_uncompressed_bytes": (
            integrity["total_bytes"] + integrity_path.stat().st_size
        ),
        "integrity_manifest_name": integrity_name,
        "integrity_manifest_sha256": sha256_file(integrity_path),
        "source_root_at_archive_time": str(root),
        "source_removed_after_verification": False,
    }
    write_atomic(record_path, record)
    record_path.chmod(0o600)
    failures = verify_archive(archive, record, args.zstd)
    if failures:
        raise SystemExit(
            "research archive verification failed:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )
    record["verified_at"] = now()
    write_atomic(record_path, record)
    record_path.chmod(0o600)

    pointer_path = args.pointer.expanduser().resolve()
    write_atomic(
        pointer_path,
        {
            "schema_version": 1,
            "run_id": args.run_id,
            "state": "archived_verified",
            "source_root": str(root),
            "cleanup_target": str(root),
            "archive_path": str(archive),
            "archive_record": str(record_path),
            "archive_bytes": record["archive_bytes"],
            "archive_sha256": record["archive_sha256"],
            "archived_file_count": record["archived_file_count"],
            "updated_at": now(),
        },
    )
    print(
        f"archived and verified {record['archived_file_count']} research "
        f"artifacts at {archive} ({record['archive_bytes']} bytes)"
    )
    return 0


def command_prune_archived_research(args: argparse.Namespace) -> int:
    pointer_path = args.pointer.expanduser().resolve()
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer.get("run_id") != args.confirm_run_id:
        raise SystemExit("confirmation run ID differs from research pointer")
    if pointer.get("state") not in {
        "archived_verified",
        "restored_from_verified_archive",
    }:
        raise SystemExit("research pointer is not in a verified removable state")
    root = safe_research_root(pointer["cleanup_target"])
    record_path = Path(pointer["archive_record"]).expanduser().resolve()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record.get("run_id") != args.confirm_run_id:
        raise SystemExit("archive record run ID differs from confirmation")
    if Path(record["source_root_at_archive_time"]).resolve() != root:
        raise SystemExit("archive record source root differs from cleanup target")
    archive = Path(record["archive_path"]).expanduser().resolve()
    failures = verify_archive(archive, record, args.zstd)
    if failures:
        raise SystemExit(
            "research archive verification failed:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )
    integrity_path = root / record["integrity_manifest_name"]
    if sha256_file(integrity_path) != record["integrity_manifest_sha256"]:
        raise SystemExit(
            "local research integrity manifest differs from archive record"
        )
    failures = verify_corpus_integrity(
        root,
        record["run_id"],
        record["integrity_manifest_name"],
    )
    if failures:
        raise SystemExit(
            "research source verification failed:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )

    shutil.rmtree(root)
    if root.exists():
        raise SystemExit(f"research root still exists after removal: {root}")
    record["source_removed_after_verification"] = True
    record["source_removed_at"] = now()
    write_atomic(record_path, record)
    record_path.chmod(0o600)
    pointer["state"] = "archived_source_removed"
    pointer["source_root"] = None
    pointer["cleanup_target"] = None
    pointer["removed_cleanup_target"] = str(root)
    pointer["updated_at"] = now()
    write_atomic(pointer_path, pointer)
    print(
        f"removed verified redundant research tree {root}; "
        f"retained archive {archive}"
    )
    return 0


def command_prune_reproducible_scratch(args: argparse.Namespace) -> int:
    root = Path(args.scratch_root).expanduser().resolve()
    raw_root = Path(args.scratch_root).expanduser()
    if (
        raw_root.is_symlink()
        or root.parent != Path("/private/tmp")
        or root.name != args.confirm_name
        or not root.name.startswith("lossytrace-research-vamp-eval.")
        or not root.is_dir()
    ):
        raise SystemExit(f"refusing unsafe scratch target: {root}")
    pointer = json.loads(
        args.research_pointer.expanduser().resolve().read_text(encoding="utf-8")
    )
    if pointer.get("state") != "archived_source_removed":
        raise SystemExit("research artifacts are not archived and pruned")
    archive = Path(pointer["archive_path"]).expanduser().resolve()
    record = Path(pointer["archive_record"]).expanduser().resolve()
    if not archive.is_file() or not record.is_file():
        raise SystemExit("research archive or archive record is missing")

    files = [path for path in root.rglob("*") if path.is_file()]
    total_bytes = sum(path.stat().st_size for path in files)
    shutil.rmtree(root)
    if root.exists():
        raise SystemExit(f"scratch root still exists after removal: {root}")
    print(
        f"removed {len(files)} reproducible scratch files "
        f"({total_bytes} bytes) from {root}"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    stage = commands.add_parser("stage")
    stage.add_argument("--audio-root", required=True)
    stage.add_argument("--run-id", required=True)
    stage.add_argument("--source-dir", action="append", required=True)
    stage.add_argument("--count", type=int, default=40)
    stage.add_argument("--seed", type=int, default=20260730)
    stage.add_argument("--ffprobe", default="ffprobe")
    stage.add_argument("--min-duration", type=float, default=120)
    stage.add_argument("--max-duration", type=float, default=720)
    stage.add_argument("--min-sample-rate", type=int, default=44_100)
    stage.add_argument("--analysis-max-seconds", type=float, default=0)
    stage.add_argument("--repetitions", type=int, default=1)
    stage.add_argument("--pointer", type=Path)
    stage.set_defaults(function=command_stage)

    codec_holdout = commands.add_parser("codec-holdout")
    codec_holdout.add_argument("--audio-root", required=True)
    codec_holdout.add_argument("--run-id", required=True)
    codec_holdout.add_argument("--parent-audio-root", required=True)
    codec_holdout.add_argument("--parent-manifest", required=True)
    codec_holdout.add_argument("--parent-ledger", required=True)
    codec_holdout.add_argument("--parent-run-id", required=True)
    codec_holdout.add_argument("--excerpt-start-seconds", type=float, default=30)
    codec_holdout.add_argument(
        "--excerpt-duration-seconds",
        type=float,
        default=45,
    )
    codec_holdout.add_argument("--ffmpeg", default="ffmpeg")
    codec_holdout.add_argument("--pointer", type=Path)
    codec_holdout.set_defaults(function=command_codec_holdout)

    resample_controls = commands.add_parser("resample-controls")
    resample_controls.add_argument("--audio-root", required=True)
    resample_controls.add_argument("--run-id", required=True)
    resample_controls.add_argument("--source-audio-root", required=True)
    resample_controls.add_argument("--source-manifest", required=True)
    resample_controls.add_argument(
        "--target-sample-rate",
        type=int,
        default=48_000,
    )
    resample_controls.add_argument(
        "--analysis-max-seconds",
        type=float,
        default=90,
    )
    resample_controls.add_argument("--repetitions", type=int, default=1)
    resample_controls.add_argument("--ffmpeg", default="ffmpeg")
    resample_controls.add_argument("--ffprobe", default="ffprobe")
    resample_controls.add_argument("--pointer", type=Path)
    resample_controls.set_defaults(function=command_resample_controls)

    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("--audio-root", required=True)
    snapshot.add_argument("--manifest", action="append", required=True)
    snapshot.add_argument("--output", required=True)
    snapshot.add_argument("--ledger")
    snapshot.add_argument("--state")
    snapshot.add_argument("--pointer", type=Path)
    snapshot.set_defaults(function=command_snapshot)

    window = commands.add_parser("window")
    window.add_argument("--manifest", required=True)
    window.add_argument("--output", required=True)
    window.add_argument("--ledger", required=True)
    window.add_argument("--analysis-max-seconds", type=float, required=True)
    window.add_argument("--pointer", type=Path)
    window.set_defaults(function=command_window)

    sharp_lowpass = commands.add_parser("sharp-lowpass")
    sharp_lowpass.add_argument("--manifest", required=True)
    sharp_lowpass.add_argument("--output", required=True)
    sharp_lowpass.add_argument("--ledger", required=True)
    sharp_lowpass.add_argument(
        "--analysis-max-seconds", type=float, default=90
    )
    sharp_lowpass.add_argument("--repetitions", type=int, default=1)
    sharp_lowpass.set_defaults(function=command_sharp_lowpass)

    subset = commands.add_parser("subset")
    subset.add_argument("--manifest", action="append", required=True)
    subset.add_argument("--output", type=Path, required=True)
    subset.add_argument("--source-count", type=int, required=True)
    subset.add_argument("--analysis-max-seconds", type=float, required=True)
    subset.add_argument("--repetitions", type=int, default=1)
    subset.add_argument("--seed", type=int, default=20260730)
    subset.set_defaults(function=command_subset)

    verify_sources = commands.add_parser("verify-sources")
    verify_sources.add_argument("--ledger", required=True)
    verify_sources.set_defaults(function=command_verify_sources)

    archive = commands.add_parser("archive")
    archive.add_argument("--pointer", type=Path, required=True)
    archive.add_argument("--destination", type=Path, required=True)
    archive.add_argument("--tar", default="tar")
    archive.add_argument("--zstd", default="zstd")
    archive.add_argument("--compression-level", type=int, default=10)
    archive.set_defaults(function=command_archive)

    verify_archive_command = commands.add_parser("verify-archive")
    verify_archive_command.add_argument("--record", type=Path, required=True)
    verify_archive_command.add_argument("--zstd", default="zstd")
    verify_archive_command.set_defaults(function=command_verify_archive)

    restore = commands.add_parser("restore-archive")
    restore.add_argument("--record", type=Path, required=True)
    restore.add_argument("--destination", required=True)
    restore.add_argument("--pointer", type=Path)
    restore.add_argument("--tar", default="tar")
    restore.add_argument("--zstd", default="zstd")
    restore.set_defaults(function=command_restore_archive)

    prune = commands.add_parser("prune-archived-source")
    prune.add_argument("--pointer", type=Path, required=True)
    prune.add_argument("--confirm-run-id", required=True)
    prune.add_argument("--zstd", default="zstd")
    prune.set_defaults(function=command_prune_archived_source)

    archive_research = commands.add_parser("archive-research")
    archive_research.add_argument("--source-root", required=True)
    archive_research.add_argument("--run-id", required=True)
    archive_research.add_argument("--pointer", type=Path, required=True)
    archive_research.add_argument("--destination", type=Path, required=True)
    archive_research.add_argument("--tar", default="tar")
    archive_research.add_argument("--zstd", default="zstd")
    archive_research.add_argument("--compression-level", type=int, default=10)
    archive_research.set_defaults(function=command_archive_research)

    prune_research = commands.add_parser("prune-archived-research")
    prune_research.add_argument("--pointer", type=Path, required=True)
    prune_research.add_argument("--confirm-run-id", required=True)
    prune_research.add_argument("--zstd", default="zstd")
    prune_research.set_defaults(function=command_prune_archived_research)

    prune_scratch = commands.add_parser("prune-reproducible-scratch")
    prune_scratch.add_argument("--scratch-root", required=True)
    prune_scratch.add_argument("--confirm-name", required=True)
    prune_scratch.add_argument(
        "--research-pointer",
        type=Path,
        required=True,
    )
    prune_scratch.set_defaults(function=command_prune_reproducible_scratch)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.function(args)


if __name__ == "__main__":
    raise SystemExit(main())
