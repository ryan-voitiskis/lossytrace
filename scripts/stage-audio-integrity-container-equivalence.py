#!/usr/bin/env python3
"""Stage lossy originals and lossless wrappers for decoder/container equivalence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath


MINIMUM_FREE_RESERVE_BYTES = 15 * 1024**3
SELECTION_SEED = "lossytrace-container-equivalence-20260801-v1"
EXCLUDED_DOMAINS = {"public_tier_a_originals"}
REFERENCE_CLASS_PRIORITY = (
    "untouched_lossless",
    "public_pcm_excerpt_flac16",
    "public_nsynth_pcm_resample_48000_flac16",
    "sqam_pcm_reference_flac16",
    "musdb_pcm_reference_wav16",
    "independent_pcm_reference_wav16",
)
CODECS = (
    {
        "id": "mp3_128",
        "extension": ".mp3",
        "sample_rate_hz": 44100,
        "include_lossy_original_case": True,
        "original_omission_reason": None,
        "encoder_args": ["-c:a", "libmp3lame", "-b:a", "128k"],
    },
    {
        "id": "aac_lc_128",
        "extension": ".m4a",
        "sample_rate_hz": 44100,
        "include_lossy_original_case": True,
        "original_omission_reason": None,
        "encoder_args": ["-c:a", "aac", "-b:a", "128k"],
    },
    {
        "id": "opus_96",
        "extension": ".opus",
        "sample_rate_hz": 48000,
        "include_lossy_original_case": False,
        "original_omission_reason": (
            "lossytrace_feature_version_0_decoder_has_no_opus_codec"
        ),
        "encoder_args": ["-c:a", "libopus", "-b:a", "96k"],
    },
    {
        "id": "vorbis_native_q3",
        "extension": ".ogg",
        "sample_rate_hz": 44100,
        "include_lossy_original_case": True,
        "original_omission_reason": None,
        "encoder_args": ["-c:a", "vorbis", "-strict", "experimental", "-q:a", "3"],
    },
)
WRAPPERS = (
    {"id": "flac16", "extension": ".flac", "encoder_args": ["-c:a", "flac", "-sample_fmt", "s16"]},
    {"id": "wav16", "extension": ".wav", "encoder_args": ["-c:a", "pcm_s16le"]},
    {"id": "aiff16", "extension": ".aiff", "encoder_args": ["-c:a", "pcm_s16be"]},
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def reference_priority(class_name: str) -> int | None:
    if class_name.endswith("_confirmed_pcm"):
        return 1
    try:
        return REFERENCE_CLASS_PRIORITY.index(class_name)
    except ValueError:
        return None


def select_references(manifest: dict, groups_per_domain: int) -> list[dict]:
    if groups_per_domain < 1:
        raise ValueError("groups_per_domain must be positive")
    candidates: dict[tuple[str, str], list[tuple[int, dict]]] = {}
    for case in manifest.get("cases", []):
        if case.get("expectation") != "negative":
            continue
        source_domain = case.get("source_domain")
        source_group = case.get("source_group")
        class_name = case.get("class")
        if (
            not isinstance(source_domain, str)
            or source_domain in EXCLUDED_DOMAINS
            or not isinstance(source_group, str)
            or not isinstance(class_name, str)
        ):
            continue
        priority = reference_priority(class_name)
        if priority is None:
            continue
        candidates.setdefault((source_domain, source_group), []).append(
            (priority, case)
        )

    by_domain: dict[str, list[dict]] = {}
    for (source_domain, _), choices in candidates.items():
        by_domain.setdefault(source_domain, []).append(
            min(choices, key=lambda choice: (choice[0], choice[1]["case_id"]))[1]
        )
    selected = []
    for source_domain, domain_cases in sorted(by_domain.items()):
        ranked = sorted(
            domain_cases,
            key=lambda case: (
                hashlib.sha256(
                    f"{SELECTION_SEED}:{source_domain}:{case['source_group']}".encode()
                ).hexdigest(),
                case["source_group"],
            ),
        )
        selected.extend(ranked[:groups_per_domain])
    if not selected:
        raise ValueError("no eligible PCM references were found")
    return selected


def sanitize(command: list[str], corpus_root: Path, output_root: Path) -> list[str]:
    return [
        part.replace(str(corpus_root), "<CORPUS_ROOT>").replace(
            str(output_root), "<OUTPUT_ROOT>"
        )
        for part in command
    ]


def run_ffmpeg(command: list[str]) -> None:
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode:
        raise ValueError(f"FFmpeg failed: {completed.stderr.strip()}")


def check_free_space(path: Path) -> None:
    if shutil.disk_usage(path).free < MINIMUM_FREE_RESERVE_BYTES:
        raise ValueError("free space is below the 15 GiB reserve")


def encoder_probe_command(
    ffmpeg: str, encoder_args: list[str], sample_rate_hz: int, output: Path
) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000:sample_rate=44100:duration=0.1",
        "-ac",
        "2",
        "-ar",
        str(sample_rate_hz),
        *encoder_args,
        str(output),
    ]


def probe_encoder(
    ffmpeg: str, encoder_args: list[str], sample_rate_hz: int, extension: str
) -> None:
    with tempfile.TemporaryDirectory(prefix="lossytrace-encoder-probe-") as temporary:
        output = Path(temporary) / f"probe{extension}"
        command = encoder_probe_command(ffmpeg, encoder_args, sample_rate_hz, output)
        run_ffmpeg(command)
        if not output.is_file() or output.stat().st_size == 0:
            raise ValueError(f"encoder probe produced no {extension} output")


def stage(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.expanduser().resolve()
    corpus_root = args.corpus_root.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    if destination.exists():
        raise ValueError(f"refusing to replace destination: {destination}")
    if not corpus_root.is_dir():
        raise ValueError(f"corpus root does not exist: {corpus_root}")
    check_free_space(destination.parent)
    manifest = load_object(manifest_path)
    references = select_references(manifest, args.groups_per_domain)
    for codec in CODECS:
        probe_encoder(
            args.ffmpeg,
            codec["encoder_args"],
            codec["sample_rate_hz"],
            codec["extension"],
        )

    staging = destination.with_name(f"{destination.name}.partial-{os.getpid()}")
    staging.mkdir(parents=True)
    try:
        audio_root = staging / "audio"
        audio_root.mkdir()
        commands = []
        cases = []
        parents = []
        lossy_intermediates = []
        fingerprints = {}
        for reference_index, reference in enumerate(references, 1):
            source_relative = reference["relative_path"]
            source = (corpus_root / source_relative).resolve()
            if not source.is_relative_to(corpus_root) or not source.is_file():
                raise ValueError(f"reference source is missing or unsafe: {source_relative}")
            opaque_group = f"equivalence-source-{reference_index:03d}"
            parents.append(
                {
                    "opaque_source_group": opaque_group,
                    "source_domain": reference["source_domain"],
                    "source_sha256": sha256_file(source),
                }
            )
            for codec in CODECS:
                original_name = f"{opaque_group}-{codec['id']}-original{codec['extension']}"
                original = audio_root / original_name
                encode = [
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
                    "30",
                    "-ac",
                    "2",
                    "-ar",
                    str(codec["sample_rate_hz"]),
                    *codec["encoder_args"],
                    str(original),
                ]
                run_ffmpeg(encode)
                commands.append(sanitize(encode, corpus_root, staging))
                lossy_intermediates.append(
                    {
                        "opaque_source_group": opaque_group,
                        "codec_family": codec["id"],
                        "sha256": sha256_file(original),
                        "byte_count": original.stat().st_size,
                        "included_as_analysis_case": codec[
                            "include_lossy_original_case"
                        ],
                        "omission_reason": codec["original_omission_reason"],
                    }
                )
                variants = []
                if codec["include_lossy_original_case"]:
                    variants.append(("lossy_original", original_name, original))
                for wrapper in WRAPPERS:
                    wrapper_name = (
                        f"{opaque_group}-{codec['id']}-to-{wrapper['id']}"
                        f"{wrapper['extension']}"
                    )
                    wrapper_path = audio_root / wrapper_name
                    decode = [
                        args.ffmpeg,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-n",
                        "-i",
                        str(original),
                        "-map",
                        "0:a:0",
                        *wrapper["encoder_args"],
                        str(wrapper_path),
                    ]
                    run_ffmpeg(decode)
                    commands.append(sanitize(decode, corpus_root, staging))
                    variants.append((f"lossless_{wrapper['id']}", wrapper_name, wrapper_path))
                for container_role, file_name, path in variants:
                    case_id = file_name.rsplit(".", 1)[0]
                    cases.append(
                        {
                            "case_id": case_id,
                            "source_group": opaque_group,
                            "partition_group": opaque_group,
                            "relative_path": f"audio/{file_name}",
                            "provenance_tier": reference["provenance_tier"],
                            "split": "development",
                            "class": f"equivalence_{codec['id']}_{container_role}",
                            "expectation": "controlled_positive",
                            "source_domain": reference["source_domain"],
                            "codec_family": codec["id"],
                            "container_role": container_role,
                        }
                    )
                    fingerprints[case_id] = sha256_file(path)
                if not codec["include_lossy_original_case"]:
                    original.unlink()
        output_manifest = {
            "schema_version": 1,
            "corpus_id": "lossytrace-container-equivalence-20260801-001",
            "corpus_version": 1,
            "audio_root_env": "LOSSYTRACE_EQUIVALENCE_ROOT",
            "analysis_max_seconds": 30.0,
            "repetitions": 1,
            "evidence_partition": "observed_development",
            "holdout_scores_opened": False,
            "selection_seed": SELECTION_SEED,
            "lossy_original_analysis": {
                codec["id"]: {
                    "included": codec["include_lossy_original_case"],
                    "omission_reason": codec["original_omission_reason"],
                }
                for codec in CODECS
            },
            "cases": sorted(cases, key=lambda case: case["case_id"]),
        }
        write_json(staging / "manifest.json", output_manifest)
        write_json(
            staging / "fingerprints.json",
            {
                "schema_version": 1,
                "corpus_id": output_manifest["corpus_id"],
                "corpus_version": 1,
                "case_sha256": dict(sorted(fingerprints.items())),
            },
        )
        ffmpeg_version = subprocess.run(
            [args.ffmpeg, "-version"], check=True, text=True, capture_output=True
        ).stdout.splitlines()[0]
        write_json(
            staging / "provenance-ledger.json",
            {
                "schema_version": 1,
                "selection_seed": SELECTION_SEED,
                "observed_manifest_sha256": sha256_file(manifest_path),
                "ffmpeg_version": ffmpeg_version,
                "parents": parents,
                "lossy_intermediates": lossy_intermediates,
                "commands": commands,
                "generated_audio_cleanup_policy": "remove_after_aggregate_evidence_is_verified",
            },
        )
        write_json(
            staging / "seal.json",
            {
                "schema_version": 1,
                "state": "sealed_ephemeral_equivalence_corpus",
                "case_count": len(cases),
                "source_group_count": len(references),
                "manifest_sha256": sha256_file(staging / "manifest.json"),
                "fingerprints_sha256": sha256_file(staging / "fingerprints.json"),
                "provenance_ledger_sha256": sha256_file(staging / "provenance-ledger.json"),
                "holdout_scores_opened": False,
                "public_verdict_enabled": False,
            },
        )
        staging.replace(destination)
    except BaseException:
        if staging.is_dir() and not staging.is_symlink():
            shutil.rmtree(staging)
        raise
    print(
        f"staged {len(cases)} equivalence cases from {len(references)} "
        f"source groups at {destination}"
    )
    return 0


def verify(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"corpus root is not a regular directory: {root}")
    for file_name in (
        "seal.json",
        "manifest.json",
        "fingerprints.json",
        "provenance-ledger.json",
    ):
        path = root / file_name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"metadata file is missing or unsafe: {file_name}")
    seal = load_object(root / "seal.json")
    manifest = load_object(root / "manifest.json")
    fingerprints = load_object(root / "fingerprints.json")
    ledger_path = root / "provenance-ledger.json"
    if seal.get("state") != "sealed_ephemeral_equivalence_corpus":
        raise ValueError("seal state differs")
    for file_name, field in (
        ("manifest.json", "manifest_sha256"),
        ("fingerprints.json", "fingerprints_sha256"),
        ("provenance-ledger.json", "provenance_ledger_sha256"),
    ):
        if sha256_file(root / file_name) != seal.get(field):
            raise ValueError(f"{file_name} hash differs")
    cases = manifest.get("cases")
    expected = fingerprints.get("case_sha256")
    if not isinstance(cases, list) or not isinstance(expected, dict):
        raise ValueError("manifest or fingerprints contract differs")
    if len(cases) != seal.get("case_count"):
        raise ValueError("case count differs")
    case_ids = [case.get("case_id") for case in cases if isinstance(case, dict)]
    if (
        len(case_ids) != len(cases)
        or any(not isinstance(case_id, str) or not case_id for case_id in case_ids)
        or len(case_ids) != len(set(case_ids))
        or set(case_ids) != set(expected)
    ):
        raise ValueError("case and fingerprint inventories differ")
    expected_paths = set()
    for case in cases:
        relative = case.get("relative_path")
        pure = PurePosixPath(relative) if isinstance(relative, str) else None
        if pure is None or pure.is_absolute() or ".." in pure.parts:
            raise ValueError("unsafe case path")
        path = root / relative
        expected_paths.add(path.resolve())
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"case file is missing: {case.get('case_id')}")
        if sha256_file(path) != expected.get(case.get("case_id")):
            raise ValueError(f"case hash differs: {case.get('case_id')}")
    audio_entries = list((root / "audio").rglob("*"))
    if any(path.is_symlink() for path in audio_entries):
        raise ValueError("generated audio contains a symlink")
    actual_paths = {
        path.resolve()
        for path in audio_entries
        if path.is_file()
    }
    if actual_paths != expected_paths:
        raise ValueError("generated audio inventory differs")
    if not ledger_path.is_file():
        raise ValueError("provenance ledger is missing")
    print(f"verified {len(cases)} equivalence cases at {root}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    stage_parser = subparsers.add_parser("stage")
    stage_parser.add_argument("--manifest", type=Path, required=True)
    stage_parser.add_argument("--corpus-root", type=Path, required=True)
    stage_parser.add_argument("--destination", type=Path, required=True)
    stage_parser.add_argument("--groups-per-domain", type=int, default=2)
    stage_parser.add_argument("--ffmpeg", default="ffmpeg")
    stage_parser.set_defaults(function=stage)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--root", type=Path, required=True)
    verify_parser.set_defaults(function=verify)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return args.function(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    raise SystemExit(main())
