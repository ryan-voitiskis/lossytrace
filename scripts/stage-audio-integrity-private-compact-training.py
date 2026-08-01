#!/usr/bin/env python3
"""Stream a verified private corpus archive into compact training audio."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POINTER = (
    ROOT / ".tmp/audio-integrity/private-compact-training-active.json"
)
EXPECTED_SOURCE_RUN_ID = "audio-integrity-dev-20260730-001"
EXPECTED_CASE_COUNT = 520
EXPECTED_SOURCE_GROUP_COUNT = 40
EXPECTED_NEGATIVE_COUNT = 200
EXPECTED_POSITIVE_COUNT = 320
MINIMUM_FREE_RESERVE_BYTES = 15 * 1024**3
DEFAULT_MAXIMUM_OUTPUT_BYTES = 8 * 1024**3


def now() -> str:
    return datetime.now(UTC).isoformat()


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


def write_private_json(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def write_private_bytes(path: Path, value: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        "wb",
        dir=path.parent,
        delete=False,
    ) as output:
        output.write(value)
        temporary = Path(output.name)
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def safe_member_name(value: str) -> str:
    path = PurePosixPath(value)
    if value.startswith("./"):
        path = PurePosixPath(value[2:])
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in value
        or not path.parts
    ):
        raise SystemExit(f"unsafe archive member name: {value!r}")
    return path.as_posix()


def validate_regular_member(member: tarfile.TarInfo) -> str:
    name = safe_member_name(member.name)
    if not member.isfile() or member.size <= 0:
        raise SystemExit(f"archive member is not non-empty regular: {name}")
    return name


def read_archive_member(
    archive_path: Path,
    member_name: str,
    *,
    zstd: str,
) -> bytes:
    process = subprocess.Popen(
        [zstd, "-dc", str(archive_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise SystemExit("failed to open zstd archive stream")
    result = None
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                if member.name.rstrip("/") == ".":
                    continue
                name = safe_member_name(member.name)
                if name != member_name:
                    continue
                validate_regular_member(member)
                source = archive.extractfile(member)
                if source is None:
                    raise SystemExit(
                        f"could not read archive member: {member_name}"
                    )
                result = source.read()
                if len(result) != member.size:
                    raise SystemExit(
                        f"archive member byte count differs: {member_name}"
                    )
                break
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
        _, stderr = process.communicate()
    if result is None:
        detail = stderr.decode(errors="replace").strip()
        raise SystemExit(
            f"archive member is missing: {member_name}"
            + (f"\n{detail}" if detail else "")
        )
    return result


def decode_json_member(encoded: bytes, name: str) -> dict:
    try:
        value = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"{name}: invalid JSON") from error
    if not isinstance(value, dict):
        raise SystemExit(f"{name}: top-level JSON must be an object")
    return value


def validate_source_metadata(
    manifest: dict,
    fingerprints: dict,
) -> list[dict]:
    cases = manifest.get("cases", [])
    if not isinstance(cases, list):
        raise SystemExit("source manifest cases must be a list")
    by_id = {}
    for source_case in cases:
        case = dict(source_case)
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise SystemExit("source case has no valid case_id")
        if case_id in by_id:
            raise SystemExit(f"source case ID repeats: {case_id}")
        if case.get("split") != "development":
            raise SystemExit(f"{case_id}: source case is not development")
        if case.get("expectation") not in {
            "negative",
            "controlled_positive",
        }:
            raise SystemExit(f"{case_id}: unsupported expectation")
        source_group = case.get("source_group")
        if not isinstance(source_group, str) or not source_group:
            raise SystemExit(f"{case_id}: missing source_group")
        relative_path = case.get("relative_path")
        if not isinstance(relative_path, str):
            raise SystemExit(f"{case_id}: missing relative_path")
        safe_member_name(relative_path)
        by_id[case_id] = case
    expected_hashes = fingerprints.get("case_sha256", {})
    if set(expected_hashes) != set(by_id):
        raise SystemExit("source fingerprints differ from manifest cases")
    observed = (
        len(cases),
        len({case["source_group"] for case in cases}),
        sum(case["expectation"] == "negative" for case in cases),
        sum(
            case["expectation"] == "controlled_positive"
            for case in cases
        ),
    )
    expected = (
        EXPECTED_CASE_COUNT,
        EXPECTED_SOURCE_GROUP_COUNT,
        EXPECTED_NEGATIVE_COUNT,
        EXPECTED_POSITIVE_COUNT,
    )
    if observed != expected:
        raise SystemExit(
            f"source case/group/negative/positive counts differ: {observed}"
        )
    return sorted(cases, key=lambda case: case["case_id"])


def ffmpeg_version(ffmpeg: str) -> str:
    completed = subprocess.run(
        [ffmpeg, "-version"],
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.splitlines()[0]


def compact_member(
    *,
    source_path: Path,
    output_path: Path,
    duration_seconds: float,
    ffmpeg: str,
    ffprobe: str,
) -> dict:
    command = [
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
        "-t",
        f"{duration_seconds:g}",
        "-c:a",
        "flac",
        str(output_path),
    ]
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode:
        raise SystemExit(
            f"compact encode failed:\n{completed.stderr.strip()}"
        )
    probe = subprocess.run(
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
            str(output_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    value = json.loads(probe.stdout)
    audio_streams = [
        stream
        for stream in value.get("streams", [])
        if stream.get("codec_type") == "audio"
    ]
    if len(audio_streams) != 1:
        raise SystemExit(f"{output_path}: expected one audio stream")
    stream = audio_streams[0]
    if stream.get("codec_name") != "flac":
        raise SystemExit(f"{output_path}: output is not FLAC")
    duration = float(value.get("format", {}).get("duration", "nan"))
    if not duration_seconds - 0.05 <= duration <= duration_seconds + 0.05:
        raise SystemExit(
            f"{output_path}: compact duration differs: {duration}"
        )
    output_path.chmod(0o600)
    return {
        "format_name": value.get("format", {}).get("format_name"),
        "codec_name": stream.get("codec_name"),
        "sample_fmt": stream.get("sample_fmt"),
        "sample_rate": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "bits_per_sample": int(stream.get("bits_per_sample") or 0),
        "bits_per_raw_sample": int(
            stream.get("bits_per_raw_sample") or 0
        ),
        "duration_seconds": duration,
    }


def integrity_entries(root: Path) -> list[dict]:
    result = []
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        relative = path.relative_to(root).as_posix()
        if relative in {"integrity.json", "seal.json"}:
            continue
        result.append(
            {
                "relative_path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return result


def validate_archive_record(record: dict, record_path: Path) -> Path:
    if record.get("schema_version") != 1:
        raise SystemExit("archive record schema_version must be 1")
    if record.get("run_id") != EXPECTED_SOURCE_RUN_ID:
        raise SystemExit("archive record run ID differs")
    if record.get("source_removed_after_verification") is not True:
        raise SystemExit("source archive has not completed verified cleanup")
    archive = Path(record.get("archive_path", "")).expanduser().resolve()
    if archive.is_symlink() or not archive.is_file():
        raise SystemExit(f"source archive is not regular: {archive}")
    if archive.stat().st_size != record.get("archive_bytes"):
        raise SystemExit("source archive byte count differs")
    if not record_path.parent.is_dir():
        raise SystemExit("archive record parent is missing")
    actual_sha256 = sha256_file(archive)
    if actual_sha256 != record.get("archive_sha256"):
        raise SystemExit("source archive SHA-256 differs")
    return archive


def stage(args: argparse.Namespace) -> int:
    record_path = args.record.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    pointer = args.pointer.expanduser().resolve()
    if destination.exists() or destination.is_symlink():
        raise SystemExit(f"destination already exists: {destination}")
    if pointer.exists() or pointer.is_symlink():
        raise SystemExit(f"pointer already exists: {pointer}")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.run_id):
        raise SystemExit("--run-id contains unsafe characters")
    if not 0 < args.duration_seconds <= 90:
        raise SystemExit("--duration-seconds must be in (0, 90]")
    if args.maximum_output_bytes <= 0:
        raise SystemExit("--maximum-output-bytes must be positive")
    if args.minimum_free_reserve_bytes < 0:
        raise SystemExit("--minimum-free-reserve-bytes must be non-negative")

    record = load_json(record_path)
    archive_path = validate_archive_record(record, record_path)
    metadata_names = (
        "manifest.json",
        "fingerprints.json",
        "run-ledger.json",
        "artifact-inventory.json",
    )
    metadata_bytes = {
        name: read_archive_member(
            archive_path,
            name,
            zstd=args.zstd,
        )
        for name in metadata_names
    }
    manifest = decode_json_member(
        metadata_bytes["manifest.json"],
        "manifest.json",
    )
    fingerprints = decode_json_member(
        metadata_bytes["fingerprints.json"],
        "fingerprints.json",
    )
    cases = validate_source_metadata(manifest, fingerprints)
    expected_hashes = fingerprints["case_sha256"]
    by_member = {
        safe_member_name(case["relative_path"]): case for case in cases
    }
    if len(by_member) != len(cases):
        raise SystemExit("multiple source cases share an archive member")

    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.parent.chmod(0o700)
    free_bytes = shutil.disk_usage(destination.parent).free
    if (
        free_bytes - args.maximum_output_bytes
        < args.minimum_free_reserve_bytes
    ):
        raise SystemExit(
            "maximum output allowance would violate free-space reserve"
        )
    staging = (
        destination.parent / f".{destination.name}.{args.run_id}.staging"
    )
    if staging.exists() or staging.is_symlink():
        raise SystemExit(f"staging path already exists: {staging}")
    staging.mkdir(mode=0o700)
    (staging / "generated").mkdir(mode=0o700)
    (staging / "working").mkdir(mode=0o700)
    (staging / "provenance").mkdir(mode=0o700)

    output_cases = []
    output_hashes = {}
    case_ledger = []
    found = set()
    process = None
    try:
        for name, encoded in metadata_bytes.items():
            write_private_bytes(
                staging / "provenance" / f"source-{name}",
                encoded,
            )
        write_private_bytes(
            staging / "provenance/source-archive-record.json",
            record_path.read_bytes(),
        )

        process = subprocess.Popen(
            [args.zstd, "-dc", str(archive_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if process.stdout is None or process.stderr is None:
            process.kill()
            raise SystemExit("failed to open source archive stream")
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                if member.name.rstrip("/") == ".":
                    continue
                member_name = safe_member_name(member.name)
                case = by_member.get(member_name)
                if case is None:
                    continue
                validate_regular_member(member)
                if member_name in found:
                    raise SystemExit(
                        f"source archive member repeats: {member_name}"
                    )
                source = archive.extractfile(member)
                if source is None:
                    raise SystemExit(
                        f"could not read source member: {member_name}"
                    )
                suffix = PurePosixPath(member_name).suffix or ".audio"
                working = (
                    staging
                    / "working"
                    / f"{case['case_id']}{suffix}"
                )
                digest = hashlib.sha256()
                byte_count = 0
                with working.open("wb") as output:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        output.write(chunk)
                        digest.update(chunk)
                        byte_count += len(chunk)
                if byte_count != member.size:
                    raise SystemExit(
                        f"{member_name}: extracted byte count differs"
                    )
                if digest.hexdigest() != expected_hashes[case["case_id"]]:
                    raise SystemExit(
                        f"{member_name}: source fingerprint differs"
                    )
                output_relative = f"generated/{case['case_id']}.flac"
                output_path = staging / output_relative
                probe = compact_member(
                    source_path=working,
                    output_path=output_path,
                    duration_seconds=args.duration_seconds,
                    ffmpeg=args.ffmpeg,
                    ffprobe=args.ffprobe,
                )
                working.unlink()
                output_sha256 = sha256_file(output_path)
                output_case = {
                    **case,
                    "partition_group": case["source_group"],
                    "relative_path": output_relative,
                }
                output_cases.append(output_case)
                output_hashes[case["case_id"]] = output_sha256
                case_ledger.append(
                    {
                        "case_id": case["case_id"],
                        "source_group": case["source_group"],
                        "class": case["class"],
                        "expectation": case["expectation"],
                        "source_archive_member": member_name,
                        "source_archive_member_bytes": member.size,
                        "source_archive_member_sha256": digest.hexdigest(),
                        "output_relative_path": output_relative,
                        "output_bytes": output_path.stat().st_size,
                        "output_sha256": output_sha256,
                        "output_probe": probe,
                    }
                )
                found.add(member_name)
                output_bytes = sum(
                    path.stat().st_size
                    for path in (staging / "generated").iterdir()
                    if path.is_file()
                )
                if output_bytes > args.maximum_output_bytes:
                    raise SystemExit(
                        "compact corpus exceeds --maximum-output-bytes"
                    )
                if len(found) % 20 == 0 or len(found) == len(cases):
                    print(f"[compact {len(found):03}/{len(cases)}]")
        process.stdout.close()
        stderr = process.stderr.read()
        return_code = process.wait()
        if return_code:
            raise SystemExit(
                "source archive stream failed: "
                + stderr.decode(errors="replace").strip()
            )
        missing = sorted(set(by_member) - found)
        if missing:
            raise SystemExit(
                f"source archive is missing selected members: {missing[:3]}"
            )
        (staging / "working").rmdir()
        output_cases.sort(key=lambda case: case["case_id"])
        case_ledger.sort(key=lambda case: case["case_id"])

        compact_manifest = {
            "schema_version": 1,
            "corpus_id": args.corpus_id,
            "corpus_version": 1,
            "audio_root_env": (
                "REKLAWDBOX_AUDIO_INTEGRITY_PRIVATE_COMPACT_TRAINING_ROOT"
            ),
            "analysis_max_seconds": args.duration_seconds,
            "repetitions": 1,
            "cases": output_cases,
        }
        write_private_json(
            staging / "manifest.json",
            compact_manifest,
        )
        write_private_json(
            staging / "fingerprints.json",
            {
                "schema_version": 1,
                "corpus_id": args.corpus_id,
                "corpus_version": 1,
                "case_sha256": dict(sorted(output_hashes.items())),
            },
        )
        write_private_json(
            staging / "provenance-ledger.json",
            {
                "schema_version": 1,
                "run_id": args.run_id,
                "corpus_id": args.corpus_id,
                "created_at": now(),
                "purpose": (
                    "compact development-only full-mix paired training; "
                    "not release evidence"
                ),
                "source_archive_run_id": record["run_id"],
                "source_archive_path": str(archive_path),
                "source_archive_bytes": record["archive_bytes"],
                "source_archive_sha256": record["archive_sha256"],
                "source_archive_record": (
                    "provenance/source-archive-record.json"
                ),
                "source_manifest_sha256": hashlib.sha256(
                    metadata_bytes["manifest.json"]
                ).hexdigest(),
                "source_fingerprints_sha256": hashlib.sha256(
                    metadata_bytes["fingerprints.json"]
                ).hexdigest(),
                "staging_tool_sha256": sha256_file(
                    Path(__file__).resolve()
                ),
                "ffmpeg_version": ffmpeg_version(args.ffmpeg),
                "compaction_policy": (
                    f"take the first {args.duration_seconds:g} seconds of "
                    "every source case and losslessly encode to FLAC without "
                    "changing sample rate or channel count"
                ),
                "case_count": len(output_cases),
                "source_group_count": len(
                    {case["source_group"] for case in output_cases}
                ),
                "cases": case_ledger,
            },
        )
        integrity_path = staging / "integrity.json"
        write_private_json(
            integrity_path,
            {
                "schema_version": 1,
                "run_id": args.run_id,
                "created_at": now(),
                "self_excluded": True,
                "seal_excluded": True,
                "files": integrity_entries(staging),
            },
        )
        write_private_json(
            staging / "seal.json",
            {
                "schema_version": 1,
                "run_id": args.run_id,
                "corpus_id": args.corpus_id,
                "created_at": now(),
                "state": "sealed_development_corpus",
                "split": "development",
                "provenance_tier": "tier_b_trusted",
                "held_out_labels_present": False,
                "release_evidence": False,
                "case_count": len(output_cases),
                "partition_count": len(
                    {case["partition_group"] for case in output_cases}
                ),
                "negative_count": sum(
                    case["expectation"] == "negative"
                    for case in output_cases
                ),
                "controlled_positive_count": sum(
                    case["expectation"] == "controlled_positive"
                    for case in output_cases
                ),
                "integrity_manifest": "integrity.json",
                "integrity_manifest_sha256": sha256_file(integrity_path),
                "exact_cleanup_target": str(destination),
                "retention_policy": "retain_for_future_versions",
                "maximum_output_bytes": args.maximum_output_bytes,
                "minimum_free_reserve_bytes": (
                    args.minimum_free_reserve_bytes
                ),
            },
        )
        staging.replace(destination)
        write_private_json(
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
                "retention_policy": "retain_for_future_versions",
            },
        )
    except BaseException:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        if staging.is_dir() and not staging.is_symlink():
            shutil.rmtree(staging)
        raise
    print(
        f"sealed {len(output_cases)} compact private training cases across "
        f"{len({case['source_group'] for case in output_cases})} groups "
        f"at {destination}"
    )
    return 0


def verify(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise SystemExit(f"corpus root is not regular: {root}")
    seal = load_json(root / "seal.json")
    integrity_path = root / "integrity.json"
    integrity = load_json(integrity_path)
    failures = []
    if seal.get("state") != "sealed_development_corpus":
        failures.append("seal state differs")
    if seal.get("release_evidence") is not False:
        failures.append("seal must refuse release evidence")
    if seal.get("retention_policy") != "retain_for_future_versions":
        failures.append("retention policy differs")
    if sha256_file(integrity_path) != seal.get(
        "integrity_manifest_sha256"
    ):
        failures.append("integrity manifest SHA-256 differs")
    expected_files = set()
    for entry in integrity.get("files", []):
        relative = entry.get("relative_path")
        try:
            normalized = safe_member_name(relative)
        except (SystemExit, TypeError):
            failures.append(f"invalid integrity path: {relative!r}")
            continue
        if normalized != relative:
            failures.append(f"non-normal integrity path: {relative!r}")
            continue
        expected_files.add(relative)
        path = root / relative
        if path.is_symlink() or not path.is_file():
            failures.append(f"integrity file missing: {relative}")
        elif path.stat().st_size != entry.get("bytes"):
            failures.append(f"byte count differs: {relative}")
        elif sha256_file(path) != entry.get("sha256"):
            failures.append(f"SHA-256 differs: {relative}")
    actual_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    allowed = expected_files | {"integrity.json", "seal.json"}
    if actual_files != allowed:
        failures.append("corpus file set differs")
    manifest = load_json(root / "manifest.json")
    fingerprints = load_json(root / "fingerprints.json")
    cases = manifest.get("cases", [])
    case_ids = {case.get("case_id") for case in cases}
    expected_hashes = fingerprints.get("case_sha256", {})
    if case_ids != set(expected_hashes):
        failures.append("manifest and fingerprints differ")
    for case in cases:
        relative = case.get("relative_path")
        path = root / relative if isinstance(relative, str) else root
        if path.is_symlink() or not path.is_file():
            failures.append(f"{case.get('case_id')}: audio missing")
        elif sha256_file(path) != expected_hashes.get(
            case.get("case_id")
        ):
            failures.append(f"{case.get('case_id')}: audio hash differs")
    if len(cases) != seal.get("case_count"):
        failures.append("sealed case count differs")
    if failures:
        raise SystemExit(
            "compact private training corpus verification failed:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )
    print(
        f"verified compact private training corpus: {len(cases)} cases "
        f"at {root}"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    stage_command = commands.add_parser("stage")
    stage_command.add_argument("--record", type=Path, required=True)
    stage_command.add_argument("--destination", type=Path, required=True)
    stage_command.add_argument("--pointer", type=Path, default=DEFAULT_POINTER)
    stage_command.add_argument("--run-id", required=True)
    stage_command.add_argument("--corpus-id", required=True)
    stage_command.add_argument("--duration-seconds", type=float, default=30)
    stage_command.add_argument("--ffmpeg", default="ffmpeg")
    stage_command.add_argument("--ffprobe", default="ffprobe")
    stage_command.add_argument("--zstd", default="zstd")
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
    raise SystemExit(parsed.function(parsed))
