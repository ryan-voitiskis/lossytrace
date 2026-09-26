#!/usr/bin/env python3
"""Stage and verify a compact public Tier A development-negative corpus."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))
from audio_integrity_relocation import cleanup_target_matches

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = (
    ROOT
    / "benchmarks/audio-integrity-v1/public-tier-a-sources.json"
)
DEFAULT_POINTER = ROOT / ".tmp/audio-integrity/public-negatives-active.json"
MINIMUM_FREE_RESERVE_BYTES = 15 * 1024**3
SOURCE_ORDER = (
    "guitarset-mono-mic-2019",
    "vocalset-2018",
    "groove-midi-audio-1.0.0",
    "choralebricks-audio-2025",
)
EXPECTED_PARTITIONS = {
    "guitarset-mono-mic-2019": {f"player-{number:02}" for number in range(6)},
    "vocalset-2018": {
        *(f"female-{number}" for number in range(1, 10)),
        *(f"male-{number}" for number in range(1, 12)),
    },
    "groove-midi-audio-1.0.0": {
        "drummer-1",
        "drummer-3",
        "drummer-4",
        "drummer-5",
        "drummer-6",
        "drummer-7",
        "drummer-8",
        "drummer-9",
        "drummer-10",
    },
    "choralebricks-audio-2025": {
        "instrument-as",
        "instrument-bar",
        "instrument-bcl",
        "instrument-bs",
        "instrument-cl",
        "instrument-eh",
        "instrument-fh",
        "instrument-fho",
        "instrument-fl",
        "instrument-ob",
        "instrument-tb",
        "instrument-tba",
        "instrument-tp",
    },
}
DATASET_SLUGS = {
    "guitarset-mono-mic-2019": "guitarset",
    "vocalset-2018": "vocalset",
    "groove-midi-audio-1.0.0": "groove",
    "choralebricks-audio-2025": "choralebricks",
}


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
    if path.exists():
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


def copy_private(source: Path, destination: Path) -> None:
    if destination.exists():
        raise SystemExit(f"refusing to replace file: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copyfile(source, destination)
    destination.chmod(0o600)


def validate_member(info: zipfile.ZipInfo) -> None:
    member = PurePosixPath(info.filename)
    if (
        member.is_absolute()
        or ".." in member.parts
        or "\\" in info.filename
        or not info.filename
    ):
        raise SystemExit(f"unsafe ZIP member name: {info.filename!r}")
    if info.is_dir():
        raise SystemExit(f"selected ZIP member is a directory: {info.filename}")
    unix_mode = info.external_attr >> 16
    file_type = stat.S_IFMT(unix_mode)
    if file_type not in {0, stat.S_IFREG}:
        raise SystemExit(
            f"selected ZIP member is not a regular file: {info.filename}"
        )
    if info.flag_bits & 0x1:
        raise SystemExit(f"selected ZIP member is encrypted: {info.filename}")
    if info.file_size <= 0:
        raise SystemExit(f"selected ZIP member is empty: {info.filename}")


def choose_largest(
    grouped: dict[str, list[zipfile.ZipInfo]],
) -> dict[str, zipfile.ZipInfo]:
    return {
        group: sorted(
            candidates,
            key=lambda candidate: (-candidate.file_size, candidate.filename),
        )[0]
        for group, candidates in sorted(grouped.items())
    }


def assert_expected_partitions(
    source_id: str,
    selected: dict[str, zipfile.ZipInfo],
) -> None:
    expected = EXPECTED_PARTITIONS[source_id]
    actual = set(selected)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise SystemExit(
            f"{source_id}: selected partitions differ; "
            f"missing={missing}, extra={extra}"
        )


def select_guitarset(
    archive: zipfile.ZipFile,
) -> dict[str, zipfile.ZipInfo]:
    grouped: dict[str, list[zipfile.ZipInfo]] = defaultdict(list)
    pattern = re.compile(r"^(?P<player>\d{2})_[^/]+_mic\.wav$")
    for info in archive.infolist():
        match = pattern.fullmatch(info.filename)
        if match:
            grouped[f"player-{match.group('player')}"].append(info)
    selected = choose_largest(grouped)
    assert_expected_partitions("guitarset-mono-mic-2019", selected)
    return selected


def select_vocalset(
    archive: zipfile.ZipFile,
) -> dict[str, zipfile.ZipInfo]:
    grouped: dict[str, list[zipfile.ZipInfo]] = defaultdict(list)
    pattern = re.compile(
        r"^FULL/(?P<gender>female|male)(?P<number>\d+)/.+\.wav$"
    )
    for info in archive.infolist():
        match = pattern.fullmatch(info.filename)
        if match:
            partition = (
                f"{match.group('gender')}-{int(match.group('number'))}"
            )
            grouped[partition].append(info)
    selected = choose_largest(grouped)
    assert_expected_partitions("vocalset-2018", selected)
    return selected


def select_groove(
    archive: zipfile.ZipFile,
) -> dict[str, zipfile.ZipInfo]:
    try:
        metadata = archive.read("groove/info.csv").decode("utf-8-sig")
    except KeyError as error:
        raise SystemExit("Groove archive has no groove/info.csv") from error
    members = {info.filename: info for info in archive.infolist()}
    grouped: dict[str, list[tuple[float, zipfile.ZipInfo]]] = defaultdict(list)
    for row in csv.DictReader(io.StringIO(metadata)):
        drummer = row.get("drummer", "")
        audio_filename = row.get("audio_filename", "")
        try:
            duration = float(row.get("duration", ""))
        except ValueError:
            continue
        member = members.get(f"groove/{audio_filename}")
        match = re.fullmatch(r"drummer(?P<number>\d+)", drummer)
        if (
            not audio_filename.lower().endswith(".wav")
            or member is None
            or member.is_dir()
            or match is None
            or not math.isfinite(duration)
            or duration <= 0
        ):
            continue
        grouped[f"drummer-{int(match.group('number'))}"].append(
            (duration, member)
        )
    selected = {
        partition: sorted(
            candidates,
            key=lambda candidate: (-candidate[0], candidate[1].filename),
        )[0][1]
        for partition, candidates in sorted(grouped.items())
    }
    assert_expected_partitions("groove-midi-audio-1.0.0", selected)
    return selected


def select_choralebricks(
    archive: zipfile.ZipFile,
) -> dict[str, zipfile.ZipInfo]:
    grouped: dict[str, list[zipfile.ZipInfo]] = defaultdict(list)
    pattern = re.compile(r"^\d+_(?P<instrument>[a-z]+)\.wav$")
    for info in archive.infolist():
        if "/tracks/" not in info.filename:
            continue
        match = pattern.fullmatch(PurePosixPath(info.filename).name)
        if match:
            grouped[f"instrument-{match.group('instrument')}"].append(info)
    selected = choose_largest(grouped)
    assert_expected_partitions("choralebricks-audio-2025", selected)
    return selected


SELECTORS = {
    "guitarset-mono-mic-2019": select_guitarset,
    "vocalset-2018": select_vocalset,
    "groove-midi-audio-1.0.0": select_groove,
    "choralebricks-audio-2025": select_choralebricks,
}


def validate_inputs(
    registry_path: Path,
    fetch_record_path: Path,
) -> tuple[dict, dict, dict[str, dict]]:
    registry = load_json(registry_path)
    fetch_record = load_json(fetch_record_path)
    if registry.get("schema_version") != 1:
        raise SystemExit("source registry schema_version must be 1")
    if fetch_record.get("schema_version") != 1:
        raise SystemExit("fetch record schema_version must be 1")
    if fetch_record.get("registry_id") != registry.get("registry_id"):
        raise SystemExit("fetch record registry ID differs")
    if fetch_record.get("registry_sha256") != sha256_file(registry_path):
        raise SystemExit("fetch record registry SHA-256 differs")
    registry_sources = {
        source["source_id"]: source for source in registry.get("sources", [])
    }
    fetched_sources = {
        source["source_id"]: source
        for source in fetch_record.get("sources", [])
    }
    if set(registry_sources) != set(SOURCE_ORDER):
        raise SystemExit("source registry differs from the approved source set")
    if set(fetched_sources) != set(SOURCE_ORDER):
        raise SystemExit("fetch record differs from the approved source set")
    for source_id in SOURCE_ORDER:
        source = registry_sources[source_id]
        fetched = fetched_sources[source_id]
        path = Path(fetched["artifact_path"]).expanduser().resolve()
        if path.is_symlink() or not path.is_file():
            raise SystemExit(f"source artifact is not a regular file: {path}")
        artifact = source["artifact"]
        if path.name != artifact["filename"]:
            raise SystemExit(f"{source_id}: source artifact filename differs")
        if path.stat().st_size != artifact["bytes"]:
            raise SystemExit(f"{source_id}: source artifact byte count differs")
        if fetched.get("bytes") != artifact["bytes"]:
            raise SystemExit(f"{source_id}: fetch-record byte count differs")
        actual_sha256 = sha256_file(path)
        if actual_sha256 != fetched.get("sha256"):
            raise SystemExit(f"{source_id}: source artifact SHA-256 differs")
    return registry, fetch_record, fetched_sources


def probe_pcm(path: Path, ffprobe: str) -> dict:
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
    if not isinstance(codec, str) or not codec.startswith("pcm_"):
        raise SystemExit(f"{path}: selected WAV is not PCM ({codec!r})")
    format_value = result.get("format", {})
    duration = float(format_value.get("duration", "nan"))
    if not math.isfinite(duration) or duration <= 0:
        raise SystemExit(f"{path}: selected WAV duration is invalid")
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


def ffprobe_version(ffprobe: str) -> str:
    completed = subprocess.run(
        [ffprobe, "-version"],
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.splitlines()[0]


def extract_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    destination: Path,
) -> None:
    validate_member(info)
    if destination.exists():
        raise SystemExit(f"refusing to replace extracted audio: {destination}")
    with archive.open(info) as source, tempfile.NamedTemporaryFile(
        "wb",
        dir=destination.parent,
        delete=False,
    ) as output:
        shutil.copyfileobj(source, output, length=1024 * 1024)
        temporary = Path(output.name)
    if temporary.stat().st_size != info.file_size:
        temporary.unlink()
        raise SystemExit(f"extracted byte count differs: {info.filename}")
    temporary.chmod(0o600)
    temporary.replace(destination)
    destination.chmod(0o600)


def integrity_entries(root: Path, exclusions: set[str]) -> list[dict]:
    entries = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in exclusions:
            continue
        entries.append(
            {
                "relative_path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return entries


def write_integrity(root: Path, run_id: str) -> Path:
    path = root / "integrity.json"
    entries = integrity_entries(root, {"integrity.json", "seal.json"})
    write_private_json(
        path,
        {
            "schema_version": 1,
            "run_id": run_id,
            "created_at": now(),
            "self_excluded": True,
            "seal_excluded": True,
            "files": entries,
        },
    )
    return path


def stage(args: argparse.Namespace) -> int:
    registry_path = args.registry.expanduser().resolve()
    fetch_record_path = args.fetch_record.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    pointer = args.pointer.expanduser().resolve()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.run_id):
        raise SystemExit("--run-id contains unsafe characters")
    if destination.exists() or destination.is_symlink():
        raise SystemExit(f"destination already exists: {destination}")
    if pointer.exists() or pointer.is_symlink():
        raise SystemExit(f"pointer already exists: {pointer}")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.parent.chmod(0o700)
    staging = destination.parent / f".{destination.name}.{args.run_id}.staging"
    if staging.exists() or staging.is_symlink():
        raise SystemExit(f"staging destination already exists: {staging}")

    registry, fetch_record, fetched_sources = validate_inputs(
        registry_path,
        fetch_record_path,
    )
    selections: list[dict] = []
    for source_id in SOURCE_ORDER:
        source = next(
            item for item in registry["sources"] if item["source_id"] == source_id
        )
        artifact_path = Path(
            fetched_sources[source_id]["artifact_path"]
        ).expanduser().resolve()
        with zipfile.ZipFile(artifact_path) as archive:
            selected = SELECTORS[source_id](archive)
            for partition, info in sorted(selected.items()):
                validate_member(info)
                selections.append(
                    {
                        "source_id": source_id,
                        "source": source,
                        "artifact_path": artifact_path,
                        "partition": partition,
                        "member_name": info.filename,
                        "member_bytes": info.file_size,
                        "member_compressed_bytes": info.compress_size,
                        "member_crc32": f"{info.CRC:08x}",
                    }
                )
    if len(selections) != 48:
        raise SystemExit(f"expected 48 selected partitions, got {len(selections)}")
    expected_bytes = sum(item["member_bytes"] for item in selections)
    free_bytes = shutil.disk_usage(destination.parent).free
    if free_bytes - expected_bytes < args.minimum_free_reserve_bytes:
        raise SystemExit(
            f"staging requires {expected_bytes} bytes but would leave less than "
            f"the {args.minimum_free_reserve_bytes}-byte free-space reserve"
        )

    staging.mkdir(mode=0o700)
    audio_dir = staging / "audio"
    provenance_dir = staging / "provenance"
    audio_dir.mkdir(mode=0o700)
    provenance_dir.mkdir(mode=0o700)
    try:
        copy_private(registry_path, provenance_dir / "source-registry.json")
        copy_private(fetch_record_path, provenance_dir / "fetch-record.json")
        cases = []
        ledger_cases = []
        fingerprints: dict[str, str] = {}
        version = ffprobe_version(args.ffprobe)
        grouped_by_artifact: dict[Path, list[dict]] = defaultdict(list)
        for selection in selections:
            grouped_by_artifact[selection["artifact_path"]].append(selection)
        completed = 0
        for artifact_path, artifact_selections in grouped_by_artifact.items():
            with zipfile.ZipFile(artifact_path) as archive:
                members = {info.filename: info for info in archive.infolist()}
                for selection in artifact_selections:
                    source_id = selection["source_id"]
                    slug = DATASET_SLUGS[source_id]
                    partition = selection["partition"]
                    case_id = f"public-{slug}-{partition}"
                    relative_path = f"audio/{case_id}.wav"
                    output = staging / relative_path
                    info = members.get(selection["member_name"])
                    if info is None:
                        raise SystemExit(
                            f"selected member disappeared: "
                            f"{selection['member_name']}"
                        )
                    extract_member(archive, info, output)
                    audio_sha256 = sha256_file(output)
                    probe = probe_pcm(output, args.ffprobe)
                    fingerprints[case_id] = audio_sha256
                    source_group = f"tier-a-{slug}-{partition}"
                    cases.append(
                        {
                            "case_id": case_id,
                            "source_group": source_group,
                            "partition_group": source_group,
                            "relative_path": relative_path,
                            "provenance_tier": "tier_a_confirmed_pcm",
                            "split": "development",
                            "class": f"public_{slug}_confirmed_pcm",
                            "expectation": "negative",
                        }
                    )
                    ledger_cases.append(
                        {
                            "case_id": case_id,
                            "source_group": source_group,
                            "partition_group": source_group,
                            "source_id": source_id,
                            "source_title": selection["source"]["title"],
                            "source_version": selection["source"]["version"],
                            "license": selection["source"]["license"],
                            "official_page_url": selection["source"][
                                "official_page_url"
                            ],
                            "provider_metadata_url": selection["source"][
                                "provider_metadata_url"
                            ],
                            "release_role": selection["source"]["release_role"],
                            "ground_truth_basis": selection["source"][
                                "ground_truth_basis"
                            ],
                            "partition_basis": selection["source"][
                                "partition_basis"
                            ],
                            "limitations": selection["source"]["limitations"],
                            "selection_policy": (
                                "one deterministic longest or largest released "
                                "PCM master per independent partition"
                            ),
                            "archive_sha256": fetched_sources[source_id]["sha256"],
                            "archive_member": selection["member_name"],
                            "archive_member_bytes": info.file_size,
                            "archive_member_compressed_bytes": info.compress_size,
                            "archive_member_crc32": f"{info.CRC:08x}",
                            "relative_path": relative_path,
                            "audio_sha256": audio_sha256,
                            "probe": probe,
                        }
                    )
                    completed += 1
                    print(
                        f"[{completed:02}/{len(selections)}] "
                        f"{case_id}: {probe['duration_seconds']:.1f}s"
                    )
        cases.sort(key=lambda case: case["case_id"])
        ledger_cases.sort(key=lambda case: case["case_id"])
        manifest = {
            "schema_version": 1,
            "corpus_id": args.corpus_id,
            "corpus_version": 1,
            "audio_root_env": (
                "REKLAWDBOX_AUDIO_INTEGRITY_PUBLIC_NEGATIVE_ROOT"
            ),
            "analysis_max_seconds": args.analysis_max_seconds,
            "repetitions": 1,
            "cases": cases,
        }
        manifest_path = staging / "manifest.json"
        fingerprints_path = staging / "fingerprints.json"
        write_private_json(manifest_path, manifest)
        write_private_json(
            fingerprints_path,
            {
                "schema_version": 1,
                "corpus_id": args.corpus_id,
                "corpus_version": 1,
                "case_sha256": dict(sorted(fingerprints.items())),
            },
        )
        ledger_path = staging / "provenance-ledger.json"
        write_private_json(
            ledger_path,
            {
                "schema_version": 1,
                "run_id": args.run_id,
                "corpus_id": args.corpus_id,
                "created_at": now(),
                "purpose": (
                    "development hard-negative expansion only; not the final "
                    "disjoint 150-partition release set"
                ),
                "selection_policy_version": 1,
                "source_registry_id": registry["registry_id"],
                "source_registry_sha256": sha256_file(registry_path),
                "source_registry_snapshot": (
                    "provenance/source-registry.json"
                ),
                "fetch_id": fetch_record["fetch_id"],
                "fetch_record_sha256": sha256_file(fetch_record_path),
                "fetch_record_snapshot": "provenance/fetch-record.json",
                "staging_tool_sha256": sha256_file(Path(__file__).resolve()),
                "ffprobe_version": version,
                "analysis_max_seconds": args.analysis_max_seconds,
                "case_count": len(ledger_cases),
                "partition_count": len(
                    {case["partition_group"] for case in ledger_cases}
                ),
                "cases": ledger_cases,
            },
        )
        integrity_path = write_integrity(staging, args.run_id)
        write_private_json(
            staging / "seal.json",
            {
                "schema_version": 1,
                "run_id": args.run_id,
                "corpus_id": args.corpus_id,
                "created_at": now(),
                "state": "sealed_development_corpus",
                "split": "development",
                "held_out_labels_present": False,
                "case_count": len(cases),
                "partition_count": len(cases),
                "integrity_manifest": "integrity.json",
                "integrity_manifest_sha256": sha256_file(integrity_path),
                "exact_cleanup_target": str(destination),
                "reproducible_from": {
                    "source_registry_sha256": sha256_file(registry_path),
                    "fetch_record_sha256": sha256_file(fetch_record_path),
                    "staging_tool_sha256": sha256_file(
                        Path(__file__).resolve()
                    ),
                },
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
                "exact_cleanup_target": str(destination),
            },
        )
    except BaseException:
        if staging.exists() and staging.is_dir() and not staging.is_symlink():
            shutil.rmtree(staging)
        raise
    print(
        f"sealed {len(selections)} public development-negative partitions at "
        f"{destination}"
    )
    return 0


def verify(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise SystemExit(f"corpus root is not a regular directory: {root}")
    seal_path = root / "seal.json"
    integrity_path = root / "integrity.json"
    seal = load_json(seal_path)
    integrity = load_json(integrity_path)
    failures = []
    if seal.get("state") != "sealed_development_corpus":
        failures.append("seal state differs")
    if not cleanup_target_matches(root, seal.get("exact_cleanup_target")):
        failures.append("seal cleanup target differs")
    if sha256_file(integrity_path) != seal.get("integrity_manifest_sha256"):
        failures.append("integrity manifest SHA-256 differs")
    if integrity.get("run_id") != seal.get("run_id"):
        failures.append("integrity run ID differs")
    expected_files = set()
    for entry in integrity.get("files", []):
        relative = entry.get("relative_path")
        if (
            not isinstance(relative, str)
            or PurePosixPath(relative).is_absolute()
            or ".." in PurePosixPath(relative).parts
        ):
            failures.append(f"invalid integrity path: {relative!r}")
            continue
        expected_files.add(relative)
        path = root / relative
        if not path.is_file() or path.is_symlink():
            failures.append(f"integrity file missing: {relative}")
            continue
        if path.stat().st_size != entry.get("bytes"):
            failures.append(f"byte count differs: {relative}")
        elif sha256_file(path) != entry.get("sha256"):
            failures.append(f"SHA-256 differs: {relative}")
    actual_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    allowed_files = expected_files | {"integrity.json", "seal.json"}
    if actual_files != allowed_files:
        failures.append(
            "corpus file set differs: "
            f"missing={sorted(allowed_files - actual_files)}, "
            f"extra={sorted(actual_files - allowed_files)}"
        )
    manifest = load_json(root / "manifest.json")
    fingerprints = load_json(root / "fingerprints.json")
    case_ids = {case["case_id"] for case in manifest.get("cases", [])}
    fingerprint_ids = set(fingerprints.get("case_sha256", {}))
    if case_ids != fingerprint_ids:
        failures.append("manifest and fingerprint case IDs differ")
    if len(case_ids) != seal.get("case_count"):
        failures.append("sealed case count differs")
    if failures:
        raise SystemExit(
            "public-negative corpus verification failed:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )
    if not getattr(args, "quiet", False):
        print(
            f"verified sealed public-negative corpus: {len(case_ids)} cases at "
            f"{root}"
        )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    stage_command = commands.add_parser("stage")
    stage_command.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    stage_command.add_argument("--fetch-record", type=Path, required=True)
    stage_command.add_argument("--destination", type=Path, required=True)
    stage_command.add_argument("--pointer", type=Path, default=DEFAULT_POINTER)
    stage_command.add_argument("--run-id", required=True)
    stage_command.add_argument("--corpus-id", required=True)
    stage_command.add_argument("--analysis-max-seconds", type=float, default=90)
    stage_command.add_argument("--ffprobe", default="ffprobe")
    stage_command.add_argument(
        "--minimum-free-reserve-bytes",
        type=int,
        default=MINIMUM_FREE_RESERVE_BYTES,
    )
    stage_command.set_defaults(function=stage)
    verify_command = commands.add_parser("verify")
    verify_command.add_argument("--root", type=Path, required=True)
    verify_command.set_defaults(function=verify)
    return result


if __name__ == "__main__":
    parsed = parser().parse_args()
    if getattr(parsed, "analysis_max_seconds", 0) < 0:
        raise SystemExit("--analysis-max-seconds must be non-negative")
    if getattr(parsed, "minimum_free_reserve_bytes", 0) < 0:
        raise SystemExit("--minimum-free-reserve-bytes must be non-negative")
    raise SystemExit(parsed.function(parsed))
