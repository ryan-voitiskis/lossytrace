#!/usr/bin/env python3
"""Stage and verify a disjoint NSynth sparse-domain training corpus."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import wave
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))
from audio_integrity_relocation import cleanup_target_matches

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = (
    ROOT
    / "benchmarks/audio-integrity-v1/"
    "public-sparse-training-sources.json"
)
DEFAULT_POINTER = (
    ROOT / ".tmp/audio-integrity/nsynth-train-sparse-active.json"
)
EXPECTED_SOURCE_IDS = {"nsynth-train-jsonwav-2017"}
STAGED_SOURCE_ID = "nsynth-train-jsonwav-2017"
NOTES_PER_INSTRUMENT = 8
DEFAULT_MAXIMUM_INSTRUMENTS = 200
SOURCE_SAMPLE_RATE = 16_000
SOURCE_CHANNELS = 1
SOURCE_SAMPLE_WIDTH = 2
MINIMUM_FREE_RESERVE_BYTES = 15 * 1024**3
DEFAULT_MAXIMUM_OUTPUT_BYTES = 8 * 1024**3
TRAINING_SOURCE_GROUP_PREFIX = "tier-b-nsynth-train-instrument-"
RETENTION_POLICY = "retain_for_future_versions"


def now() -> str:
    return datetime.now(UTC).isoformat()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def copy_private(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise SystemExit(f"refusing to replace file: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copyfile(source, destination)
    destination.chmod(0o600)


def validate_member(member: tarfile.TarInfo) -> None:
    path = PurePosixPath(member.name)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in member.name
        or not member.name
    ):
        raise SystemExit(f"unsafe TAR member name: {member.name!r}")
    if not member.isfile():
        raise SystemExit(f"selected TAR member is not regular: {member.name}")
    if member.size <= 0:
        raise SystemExit(f"selected TAR member is empty: {member.name}")


def extract_json_member(
    archive_path: Path,
) -> tuple[str, dict[str, dict]]:
    matches: list[tuple[str, bytes]] = []
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            if PurePosixPath(member.name).name != "examples.json":
                continue
            validate_member(member)
            source = archive.extractfile(member)
            if source is None:
                raise SystemExit(
                    f"could not read metadata member: {member.name}"
                )
            matches.append((member.name, source.read()))
    if len(matches) != 1:
        raise SystemExit(
            f"{archive_path}: expected one examples.json, got {len(matches)}"
        )
    member_name, encoded = matches[0]
    try:
        value = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SystemExit(
            f"{archive_path}: examples.json is invalid"
        ) from error
    if not isinstance(value, dict) or not value:
        raise SystemExit(f"{archive_path}: examples.json is empty")
    if not all(isinstance(item, dict) for item in value.values()):
        raise SystemExit(
            f"{archive_path}: examples.json rows must be objects"
        )
    return member_name, value


def select_notes(
    examples: dict[str, dict],
    count: int = NOTES_PER_INSTRUMENT,
) -> dict[int, list[dict]]:
    if count < 2:
        raise ValueError("note count must be at least two")
    grouped: dict[int, list[dict]] = {}
    identity: dict[int, tuple[str, str, str]] = {}
    for note_name, metadata in examples.items():
        if metadata.get("note_str") != note_name:
            raise SystemExit(f"{note_name}: note_str differs")
        try:
            instrument = int(metadata["instrument"])
            pitch = int(metadata["pitch"])
            velocity = int(metadata["velocity"])
        except (KeyError, TypeError, ValueError) as error:
            raise SystemExit(
                f"{note_name}: invalid instrument, pitch, or velocity"
            ) from error
        current_identity = (
            str(metadata.get("instrument_str", "")),
            str(metadata.get("instrument_family_str", "")),
            str(metadata.get("instrument_source_str", "")),
        )
        if any(not value for value in current_identity):
            raise SystemExit(f"{note_name}: instrument identity is incomplete")
        previous = identity.setdefault(instrument, current_identity)
        if previous != current_identity:
            raise SystemExit(
                f"instrument {instrument}: inconsistent identity metadata"
            )
        grouped.setdefault(instrument, []).append(
            {
                "note_name": note_name,
                "pitch": pitch,
                "velocity": velocity,
                "instrument": instrument,
                "instrument_str": current_identity[0],
                "instrument_family": current_identity[1],
                "instrument_source": current_identity[2],
                "qualities": sorted(
                    str(value)
                    for value in metadata.get("qualities_str", [])
                ),
            }
        )
    selected = {}
    for instrument, candidates in sorted(grouped.items()):
        ordered = sorted(
            candidates,
            key=lambda item: (
                item["pitch"],
                item["velocity"],
                item["note_name"],
            ),
        )
        if len(ordered) < count:
            raise SystemExit(
                f"instrument {instrument}: fewer than {count} notes"
            )
        indices = [
            round(index * (len(ordered) - 1) / (count - 1))
            for index in range(count)
        ]
        if len(indices) != len(set(indices)):
            raise RuntimeError(
                f"instrument {instrument}: note selection repeated an index"
            )
        selected[instrument] = [ordered[index] for index in indices]
    if not selected:
        raise SystemExit("NSynth metadata contains no instruments")
    return selected


def instrument_selection_key(instrument: int, seed: str) -> tuple[str, int]:
    digest = hashlib.sha256(f"{seed}\0{instrument}".encode()).hexdigest()
    return digest, instrument


def select_instrument_subset(
    selected: dict[int, list[dict]],
    maximum_instruments: int,
    *,
    seed: str,
) -> dict[int, list[dict]]:
    if maximum_instruments < 1:
        raise ValueError("maximum instrument count must be positive")
    if len(selected) <= maximum_instruments:
        return dict(sorted(selected.items()))
    by_stratum: dict[tuple[str, str], list[int]] = {}
    for instrument, notes in selected.items():
        identity = {
            (note["instrument_family"], note["instrument_source"])
            for note in notes
        }
        if len(identity) != 1:
            raise RuntimeError(
                f"instrument {instrument}: inconsistent family/source stratum"
            )
        stratum = next(iter(identity))
        by_stratum.setdefault(stratum, []).append(instrument)
    if len(by_stratum) > maximum_instruments:
        raise ValueError(
            "maximum instrument count is smaller than the family/source strata"
        )
    chosen = {
        min(
            instruments,
            key=lambda instrument: instrument_selection_key(
                instrument,
                f"{seed}\0{stratum[0]}\0{stratum[1]}",
            ),
        )
        for stratum, instruments in sorted(by_stratum.items())
    }
    remaining = sorted(
        set(selected) - chosen,
        key=lambda instrument: instrument_selection_key(instrument, seed),
    )
    chosen.update(remaining[: maximum_instruments - len(chosen)])
    if len(chosen) != maximum_instruments:
        raise RuntimeError("instrument subset has an unexpected size")
    return {
        instrument: selected[instrument]
        for instrument in sorted(chosen)
    }


def archive_audio_member(
    metadata_member: str,
    note_name: str,
) -> str:
    root = PurePosixPath(metadata_member).parent
    return (root / "audio" / f"{note_name}.wav").as_posix()


def read_pcm_wav(encoded: bytes, label: str) -> tuple[bytes, int]:
    try:
        with wave.open(io.BytesIO(encoded), "rb") as source:
            parameters = (
                source.getnchannels(),
                source.getsampwidth(),
                source.getframerate(),
                source.getcomptype(),
            )
            expected = (
                SOURCE_CHANNELS,
                SOURCE_SAMPLE_WIDTH,
                SOURCE_SAMPLE_RATE,
                "NONE",
            )
            if parameters != expected:
                raise SystemExit(
                    f"{label}: expected mono 16-bit 16 kHz PCM, "
                    f"got {parameters!r}"
                )
            frames = source.readframes(source.getnframes())
            frame_count = len(frames) // SOURCE_SAMPLE_WIDTH
            if frame_count <= 0:
                raise SystemExit(f"{label}: WAV contains no samples")
            if source.readframes(1):
                raise SystemExit(f"{label}: WAV contains unread trailing frames")
    except (EOFError, wave.Error) as error:
        raise SystemExit(f"{label}: invalid WAV") from error
    return frames, frame_count


def collect_selected_audio(
    archive_path: Path,
    metadata_member: str,
    selected: dict[int, list[dict]],
) -> dict[int, list[dict]]:
    by_member = {}
    for instrument, notes in selected.items():
        for order, note in enumerate(notes):
            member_name = archive_audio_member(
                metadata_member,
                note["note_name"],
            )
            if member_name in by_member:
                raise RuntimeError(f"selected member repeated: {member_name}")
            by_member[member_name] = (instrument, order, note)
    collected: dict[int, list[dict | None]] = {
        instrument: [None] * len(notes)
        for instrument, notes in selected.items()
    }
    with tarfile.open(archive_path, "r|gz") as archive:
        for member in archive:
            selection = by_member.get(member.name)
            if selection is None:
                continue
            validate_member(member)
            source = archive.extractfile(member)
            if source is None:
                raise SystemExit(
                    f"could not read selected audio member: {member.name}"
                )
            encoded = source.read()
            if len(encoded) != member.size:
                raise SystemExit(
                    f"{member.name}: extracted byte count differs"
                )
            frames, frame_count = read_pcm_wav(encoded, member.name)
            instrument, order, note = selection
            collected[instrument][order] = {
                **note,
                "archive_member": member.name,
                "archive_member_bytes": member.size,
                "archive_member_sha256": sha256_bytes(encoded),
                "pcm_frame_count": frame_count,
                "pcm_frames": frames,
            }
    missing = [
        note["note_name"]
        for instrument, notes in selected.items()
        for order, note in enumerate(notes)
        if collected[instrument][order] is None
    ]
    if missing:
        raise SystemExit(
            "selected audio members are missing: " + ", ".join(missing)
        )
    return {
        instrument: [item for item in notes if item is not None]
        for instrument, notes in collected.items()
    }


def write_montage_wav(
    path: Path,
    notes: list[dict],
    duration_seconds: float,
) -> int:
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("montage duration must be finite and positive")
    target_frames = round(duration_seconds * SOURCE_SAMPLE_RATE)
    available_frames = sum(note["pcm_frame_count"] for note in notes)
    if available_frames < target_frames:
        raise SystemExit(
            f"{path}: selected notes contain {available_frames} frames, "
            f"fewer than required {target_frames}"
        )
    remaining = target_frames
    with wave.open(str(path), "wb") as output:
        output.setnchannels(SOURCE_CHANNELS)
        output.setsampwidth(SOURCE_SAMPLE_WIDTH)
        output.setframerate(SOURCE_SAMPLE_RATE)
        for note in notes:
            frame_count = min(remaining, note["pcm_frame_count"])
            byte_count = frame_count * SOURCE_SAMPLE_WIDTH
            output.writeframesraw(note["pcm_frames"][:byte_count])
            remaining -= frame_count
            if remaining == 0:
                break
        output.writeframes(b"")
    if remaining:
        raise RuntimeError(f"{path}: montage writer ended early")
    path.chmod(0o600)
    return target_frames


def ffmpeg_version(ffmpeg: str) -> str:
    completed = subprocess.run(
        [ffmpeg, "-version"],
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.splitlines()[0]


def probe_audio(path: Path, ffprobe: str) -> dict:
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
    value = json.loads(completed.stdout)
    streams = [
        stream
        for stream in value.get("streams", [])
        if stream.get("codec_type") == "audio"
    ]
    if len(streams) != 1:
        raise SystemExit(f"{path}: expected exactly one audio stream")
    stream = streams[0]
    codec = stream.get("codec_name")
    if codec != "flac":
        raise SystemExit(f"{path}: expected FLAC output, got {codec!r}")
    duration = float(value.get("format", {}).get("duration", "nan"))
    if not math.isfinite(duration) or duration <= 0:
        raise SystemExit(f"{path}: duration is invalid")
    return {
        "codec_name": codec,
        "sample_fmt": stream.get("sample_fmt"),
        "sample_rate": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "bits_per_sample": int(stream.get("bits_per_sample") or 0),
        "bits_per_raw_sample": int(
            stream.get("bits_per_raw_sample") or 0
        ),
        "duration_seconds": duration,
        "format_name": value.get("format", {}).get("format_name"),
    }


def run_command(command: list[str], label: str) -> None:
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode:
        detail = completed.stderr.strip().splitlines()
        raise SystemExit(
            f"{label} failed:\n" + "\n".join(detail[-20:])
        )


def redacted_command(command: list[str], root: Path) -> list[str]:
    redacted = []
    for argument in command:
        try:
            path = Path(argument).resolve()
        except (OSError, RuntimeError):
            redacted.append(argument)
            continue
        if path.is_relative_to(root):
            redacted.append(
                "<CORPUS_ROOT>/"
                + path.relative_to(root).as_posix()
            )
        else:
            redacted.append(argument)
    return redacted


def recipes() -> list[dict]:
    return [
        {
            "suffix": "pcm-montage-16000-flac16",
            "class": "public_nsynth_pcm_montage_16000_flac16",
            "expectation": "negative",
            "kind": "pcm_reference",
        },
        {
            "suffix": "pcm-resample-48000-flac16",
            "class": "public_nsynth_pcm_resample_48000_flac16",
            "expectation": "negative",
            "kind": "pcm_resample",
        },
        {
            "suffix": "mp3-128-to-flac16",
            "class": "public_nsynth_mp3_128_to_flac16",
            "expectation": "controlled_positive",
            "kind": "lossy_round_trip",
            "extension": "mp3",
            "encode_arguments": ["-c:a", "libmp3lame", "-b:a", "128k"],
        },
        {
            "suffix": "aac-lc-128-to-flac16",
            "class": "public_nsynth_aac_lc_128_to_flac16",
            "expectation": "controlled_positive",
            "kind": "lossy_round_trip",
            "extension": "m4a",
            "encode_arguments": ["-c:a", "aac", "-b:a", "128k"],
        },
        {
            "suffix": "opus-96-to-flac16",
            "class": "public_nsynth_opus_96_to_flac16",
            "expectation": "controlled_positive",
            "kind": "lossy_round_trip",
            "extension": "opus",
            "encode_arguments": ["-c:a", "libopus", "-b:a", "96k"],
        },
        {
            "suffix": "vorbis-native-q3-to-flac16",
            "class": "public_nsynth_vorbis_native_q3_to_flac16",
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


def generate_variants(
    *,
    instrument: int,
    split: str,
    notes: list[dict],
    working_wav: Path,
    root: Path,
    ffmpeg: str,
    ffprobe: str,
) -> tuple[list[dict], dict]:
    generated = root / "generated"
    intermediates = root / "intermediates"
    base_id = f"public-nsynth-{split}-instrument-{instrument:04}"
    reference_path = (
        generated / f"{base_id}-pcm-montage-16000-flac16.flac"
    )
    reference_command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-n",
        "-i",
        str(working_wav),
        "-map",
        "0:a:0",
        "-vn",
        "-c:a",
        "flac",
        "-sample_fmt",
        "s16",
        str(reference_path),
    ]
    run_command(reference_command, f"{base_id} PCM reference")
    reference_sha256 = sha256_file(reference_path)
    reference_probe = probe_audio(reference_path, ffprobe)
    if (
        reference_probe["sample_rate"] != SOURCE_SAMPLE_RATE
        or reference_probe["channels"] != SOURCE_CHANNELS
    ):
        raise SystemExit(f"{base_id}: PCM reference format differs")
    source_group = f"tier-b-nsynth-{split}-instrument-{instrument:04}"
    output_cases = []
    variant_ledger = []
    for recipe in recipes():
        case_id = f"{base_id}-{recipe['suffix']}"
        output_path = generated / f"{case_id}.flac"
        commands: list[list[str]] = []
        intermediate = None
        if recipe["kind"] == "pcm_reference":
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
                "48000",
                "-ac",
                "2",
                "-c:a",
                "flac",
                "-sample_fmt",
                "s16",
                str(output_path),
            ]
            run_command(command, case_id)
            commands.append(command)
            audio_sha256 = sha256_file(output_path)
            probe = probe_audio(output_path, ffprobe)
        else:
            intermediate_path = (
                intermediates / f"{case_id}.{recipe['extension']}"
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
                "-ar",
                "48000",
                "-ac",
                "2",
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
            run_command(encode, f"{case_id} encode")
            run_command(decode, f"{case_id} decode")
            commands.extend((encode, decode))
            intermediate = {
                "bytes": intermediate_path.stat().st_size,
                "sha256": sha256_file(intermediate_path),
                "retained": False,
            }
            intermediate_path.unlink()
            audio_sha256 = sha256_file(output_path)
            probe = probe_audio(output_path, ffprobe)
        relative_path = output_path.relative_to(root).as_posix()
        output_cases.append(
            {
                "case_id": case_id,
                "source_group": source_group,
                "partition_group": source_group,
                "relative_path": relative_path,
                "provenance_tier": "tier_b_trusted",
                "split": "development",
                "class": recipe["class"],
                "expectation": recipe["expectation"],
            }
        )
        variant_ledger.append(
            {
                "case_id": case_id,
                "class": recipe["class"],
                "expectation": recipe["expectation"],
                "relative_path": relative_path,
                "audio_sha256": audio_sha256,
                "probe": probe,
                "commands": [
                    redacted_command(command, root)
                    for command in commands
                ],
                "intermediate": intermediate,
            }
        )
    ledger = {
        "instrument": instrument,
        "instrument_str": notes[0]["instrument_str"],
        "instrument_family": notes[0]["instrument_family"],
        "instrument_source": notes[0]["instrument_source"],
        "split": split,
        "source_group": source_group,
        "selected_notes": [
            {
                key: value
                for key, value in note.items()
                if key != "pcm_frames"
            }
            for note in notes
        ],
        "variants": variant_ledger,
    }
    return output_cases, ledger


def validate_inputs(
    registry_path: Path,
    fetch_record_path: Path,
) -> tuple[dict, dict, dict[str, tuple[dict, dict, Path]]]:
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
        item["source_id"]: item for item in registry.get("sources", [])
    }
    fetched_sources = {
        item["source_id"]: item
        for item in fetch_record.get("sources", [])
    }
    if set(registry_sources) != EXPECTED_SOURCE_IDS:
        raise SystemExit("source registry differs from approved NSynth splits")
    if set(fetched_sources) != EXPECTED_SOURCE_IDS:
        raise SystemExit("fetch record differs from approved NSynth splits")
    validated = {}
    for source_id in sorted(EXPECTED_SOURCE_IDS):
        source = registry_sources[source_id]
        fetched = fetched_sources[source_id]
        path = Path(fetched["artifact_path"]).expanduser().resolve()
        artifact = source["artifact"]
        if path.is_symlink() or not path.is_file():
            raise SystemExit(f"source artifact is not regular: {path}")
        if path.name != artifact["filename"]:
            raise SystemExit(f"{source_id}: artifact filename differs")
        if path.stat().st_size != artifact["bytes"]:
            raise SystemExit(f"{source_id}: artifact byte count differs")
        if sha256_file(path) != fetched.get("sha256"):
            raise SystemExit(f"{source_id}: artifact SHA-256 differs")
        validated[source_id] = (source, fetched, path)
    return registry, fetch_record, validated


def integrity_entries(root: Path) -> list[dict]:
    entries = []
    for path in sorted(
        candidate
        for candidate in root.rglob("*")
        if candidate.is_file()
    ):
        relative = path.relative_to(root).as_posix()
        if relative in {"integrity.json", "seal.json"}:
            continue
        entries.append(
            {
                "relative_path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return entries


def validate_case_metadata(
    cases: object,
    expected_hashes: object,
    seal: dict,
) -> list[str]:
    failures = []
    if not isinstance(cases, list) or not cases:
        return ["manifest cases must be a non-empty list"]
    if not isinstance(expected_hashes, dict):
        return ["fingerprint case map must be an object"]
    case_ids = []
    relative_paths = []
    expectations = []
    partitions = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            failures.append(f"manifest case {index} is not an object")
            continue
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            failures.append(f"manifest case {index} has no valid case ID")
            continue
        case_ids.append(case_id)
        relative = case.get("relative_path")
        path_value = (
            PurePosixPath(relative) if isinstance(relative, str) else None
        )
        if (
            path_value is None
            or path_value.is_absolute()
            or ".." in path_value.parts
            or not relative.startswith("generated/")
        ):
            failures.append(f"{case_id}: invalid audio path")
        else:
            relative_paths.append(relative)
        expectation = case.get("expectation")
        if expectation not in {"negative", "controlled_positive"}:
            failures.append(f"{case_id}: invalid expectation")
        else:
            expectations.append(expectation)
        source_group = case.get("source_group")
        partition_group = case.get("partition_group")
        if (
            not isinstance(source_group, str)
            or not source_group.startswith(TRAINING_SOURCE_GROUP_PREFIX)
        ):
            failures.append(f"{case_id}: source group differs")
        if partition_group != source_group:
            failures.append(f"{case_id}: partition group differs")
        elif isinstance(partition_group, str):
            partitions.add(partition_group)
        if case.get("split") != "development":
            failures.append(f"{case_id}: split differs")
        if case.get("provenance_tier") != "tier_b_trusted":
            failures.append(f"{case_id}: provenance tier differs")
    if len(case_ids) != len(set(case_ids)):
        failures.append("manifest contains duplicate case IDs")
    if len(relative_paths) != len(set(relative_paths)):
        failures.append("manifest contains duplicate audio paths")
    if set(case_ids) != set(expected_hashes):
        failures.append("manifest and fingerprint case IDs differ")
    for case_id, digest in expected_hashes.items():
        if (
            not isinstance(case_id, str)
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            failures.append(f"{case_id!r}: invalid fingerprint")
    if len(case_ids) != seal.get("case_count"):
        failures.append("sealed case count differs")
    if len(partitions) != seal.get("partition_count"):
        failures.append("sealed partition count differs")
    if expectations.count("negative") != seal.get("negative_count"):
        failures.append("sealed negative count differs")
    if expectations.count("controlled_positive") != seal.get(
        "controlled_positive_count"
    ):
        failures.append("sealed controlled-positive count differs")
    return failures


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
    if args.maximum_output_bytes <= 0:
        raise SystemExit("--maximum-output-bytes must be positive")
    if args.maximum_instruments < 1:
        raise SystemExit("--maximum-instruments must be positive")
    if args.minimum_free_reserve_bytes < 0:
        raise SystemExit("--minimum-free-reserve-bytes must be non-negative")
    if not 0 < args.montage_seconds <= NOTES_PER_INSTRUMENT * 4:
        raise SystemExit(
            f"--montage-seconds must be in (0, {NOTES_PER_INSTRUMENT * 4}]"
        )
    registry, fetch_record, sources = validate_inputs(
        registry_path,
        fetch_record_path,
    )
    metadata = {}
    all_instruments = set()
    for source_id, (_, _, archive_path) in sources.items():
        member_name, examples = extract_json_member(archive_path)
        available_instruments = {
            int(item["instrument"]) for item in examples.values()
        }
        selected = {}
        if source_id == STAGED_SOURCE_ID:
            selected = select_instrument_subset(
                select_notes(examples),
                args.maximum_instruments,
                seed=args.selection_seed,
            )
        all_instruments.update(selected)
        if "-train-" not in source_id:
            raise SystemExit(f"unexpected sparse training split: {source_id}")
        split = "train"
        metadata[source_id] = {
            "split": split,
            "metadata_member": member_name,
            "example_count": len(examples),
            "available_instrument_count": len(available_instruments),
            "selected": selected,
        }
    expected_case_count = len(all_instruments) * len(recipes())
    if not all_instruments:
        raise SystemExit("no instruments selected")
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
    for name in ("generated", "intermediates", "working", "provenance"):
        (staging / name).mkdir(mode=0o700)
    try:
        copy_private(
            registry_path,
            staging / "provenance/source-registry.json",
        )
        copy_private(
            fetch_record_path,
            staging / "provenance/fetch-record.json",
        )
        task_inputs = []
        source_ledger = []
        for source_id, (source, fetched, archive_path) in sources.items():
            item = metadata[source_id]
            collected = (
                collect_selected_audio(
                    archive_path,
                    item["metadata_member"],
                    item["selected"],
                )
                if item["selected"]
                else {}
            )
            source_ledger.append(
                {
                    "source_id": source_id,
                    "title": source["title"],
                    "version": source["version"],
                    "license": source["license"],
                    "official_page_url": source["official_page_url"],
                    "provider_metadata_url": source[
                        "provider_metadata_url"
                    ],
                    "release_role": source["release_role"],
                    "ground_truth_basis": source["ground_truth_basis"],
                    "partition_basis": source["partition_basis"],
                    "limitations": source["limitations"],
                    "archive_bytes": archive_path.stat().st_size,
                    "archive_provider_checksum": fetched[
                        "provider_checksum"
                    ],
                    "archive_sha256": fetched["sha256"],
                    "metadata_member": item["metadata_member"],
                    "example_count": item["example_count"],
                    "available_instrument_count": item[
                        "available_instrument_count"
                    ],
                    "selected_for_current_corpus": bool(collected),
                    "staged_instrument_count": len(collected),
                }
            )
            for instrument, notes in collected.items():
                working = (
                    staging
                    / "working"
                    / (
                        f"nsynth-{item['split']}-"
                        f"instrument-{instrument:04}.wav"
                    )
                )
                frame_count = write_montage_wav(
                    working,
                    notes,
                    args.montage_seconds,
                )
                task_inputs.append(
                    {
                        "instrument": instrument,
                        "split": item["split"],
                        "notes": notes,
                        "working_wav": working,
                        "montage_frame_count": frame_count,
                    }
                )
        tool_version = ffmpeg_version(args.ffmpeg)
        cases = []
        instrument_ledger = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.jobs
        ) as executor:
            futures = {
                executor.submit(
                    generate_variants,
                    instrument=item["instrument"],
                    split=item["split"],
                    notes=item["notes"],
                    working_wav=item["working_wav"],
                    root=staging,
                    ffmpeg=args.ffmpeg,
                    ffprobe=args.ffprobe,
                ): item
                for item in task_inputs
            }
            for completed, future in enumerate(
                concurrent.futures.as_completed(futures),
                1,
            ):
                item = futures[future]
                generated_cases, ledger = future.result()
                ledger["montage_frame_count"] = item[
                    "montage_frame_count"
                ]
                cases.extend(generated_cases)
                instrument_ledger.append(ledger)
                output_bytes = sum(
                    path.stat().st_size
                    for path in (staging / "generated").glob("*")
                    if path.is_file()
                )
                if output_bytes > args.maximum_output_bytes:
                    raise SystemExit(
                        "generated corpus exceeds --maximum-output-bytes"
                    )
                print(
                    f"[{completed:03}/{len(task_inputs)}] "
                    f"instrument {item['instrument']:04}"
                )
        shutil.rmtree(staging / "working")
        if any((staging / "intermediates").iterdir()):
            raise SystemExit("reproducible lossy intermediates remain")
        (staging / "intermediates").rmdir()
        cases.sort(key=lambda item: item["case_id"])
        instrument_ledger.sort(key=lambda item: item["instrument"])
        if len(cases) != expected_case_count:
            raise SystemExit(
                f"expected {expected_case_count} cases, got {len(cases)}"
            )
        fingerprints = {
            variant["case_id"]: variant["audio_sha256"]
            for instrument in instrument_ledger
            for variant in instrument["variants"]
        }
        if set(fingerprints) != {
            case["case_id"] for case in cases
        }:
            raise RuntimeError("ledger and manifest case IDs differ")
        manifest = {
            "schema_version": 1,
            "corpus_id": args.corpus_id,
            "corpus_version": 1,
            "audio_root_env": (
                "REKLAWDBOX_AUDIO_INTEGRITY_NSYNTH_SPARSE_TRAINING_ROOT"
            ),
            "analysis_max_seconds": args.montage_seconds,
            "repetitions": 1,
            "cases": cases,
        }
        write_private_json(staging / "manifest.json", manifest)
        write_private_json(
            staging / "fingerprints.json",
            {
                "schema_version": 1,
                "corpus_id": args.corpus_id,
                "corpus_version": 1,
                "case_sha256": dict(sorted(fingerprints.items())),
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
                    "development-only Tier B sparse-domain paired training; "
                    "not Tier A release evidence"
                ),
                "license": "CC BY 4.0",
                "source_registry_id": registry["registry_id"],
                "source_registry_sha256": sha256_file(registry_path),
                "source_registry_snapshot": (
                    "provenance/source-registry.json"
                ),
                "fetch_id": fetch_record["fetch_id"],
                "fetch_record_sha256": sha256_file(fetch_record_path),
                "fetch_record_snapshot": "provenance/fetch-record.json",
                "staging_tool_sha256": sha256_file(
                    Path(__file__).resolve()
                ),
                "ffmpeg_version": tool_version,
                "selection_policy": (
                    f"{NOTES_PER_INSTRUMENT} pitch/velocity-ordered notes "
                    "sampled at evenly spaced ranks for a deterministic "
                    f"family/source-stratified subset of {len(all_instruments)} "
                    "official train instrument IDs"
                ),
                "instrument_selection_seed": args.selection_seed,
                "montage_policy": (
                    "concatenate selected PCM frames in rank order and trim "
                    f"to {args.montage_seconds:g} seconds"
                ),
                "lossy_intermediates_retained": False,
                "retention_policy": RETENTION_POLICY,
                "case_count": len(cases),
                "instrument_partition_count": len(all_instruments),
                "sources": sorted(
                    source_ledger,
                    key=lambda item: item["source_id"],
                ),
                "instruments": instrument_ledger,
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
                "retention_policy": RETENTION_POLICY,
                "case_count": len(cases),
                "partition_count": len(all_instruments),
                "negative_count": sum(
                    case["expectation"] == "negative" for case in cases
                ),
                "controlled_positive_count": sum(
                    case["expectation"] == "controlled_positive"
                    for case in cases
                ),
                "integrity_manifest": "integrity.json",
                "integrity_manifest_sha256": sha256_file(integrity_path),
                "exact_cleanup_target": str(destination),
                "maximum_output_bytes": args.maximum_output_bytes,
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
                "retention_policy": RETENTION_POLICY,
            },
        )
    except BaseException:
        if staging.is_dir() and not staging.is_symlink():
            shutil.rmtree(staging)
        raise
    print(
        f"sealed {len(cases)} NSynth development cases across "
        f"{len(all_instruments)} instrument partitions at {destination}"
    )
    return 0


def verify(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise SystemExit(f"corpus root is not a regular directory: {root}")
    seal = load_json(root / "seal.json")
    integrity_path = root / "integrity.json"
    integrity = load_json(integrity_path)
    failures = []
    if seal.get("state") != "sealed_development_corpus":
        failures.append("seal state differs")
    if seal.get("provenance_tier") != "tier_b_trusted":
        failures.append("seal provenance tier differs")
    if seal.get("release_evidence") is not False:
        failures.append("seal must refuse release evidence")
    if seal.get("retention_policy") != RETENTION_POLICY:
        failures.append("seal retention policy differs")
    if not cleanup_target_matches(root, seal.get("exact_cleanup_target")):
        failures.append("seal cleanup target differs")
    if sha256_file(integrity_path) != seal.get(
        "integrity_manifest_sha256"
    ):
        failures.append("integrity manifest SHA-256 differs")
    expected_files = set()
    for entry in integrity.get("files", []):
        relative = entry.get("relative_path")
        path_value = PurePosixPath(relative) if isinstance(relative, str) else None
        if (
            path_value is None
            or path_value.is_absolute()
            or ".." in path_value.parts
        ):
            failures.append(f"invalid integrity path: {relative!r}")
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
    allowed_files = expected_files | {"integrity.json", "seal.json"}
    if actual_files != allowed_files:
        failures.append(
            "corpus file set differs: "
            f"missing={sorted(allowed_files - actual_files)}, "
            f"extra={sorted(actual_files - allowed_files)}"
        )
    manifest = load_json(root / "manifest.json")
    fingerprints = load_json(root / "fingerprints.json")
    cases = manifest.get("cases", [])
    expected_hashes = fingerprints.get("case_sha256", {})
    failures.extend(validate_case_metadata(cases, expected_hashes, seal))
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_id = case.get("case_id")
        relative = case.get("relative_path")
        if (
            not isinstance(relative, str)
            or PurePosixPath(relative).is_absolute()
            or ".." in PurePosixPath(relative).parts
        ):
            failures.append(f"{case_id}: invalid audio path")
            continue
        path = root / relative
        if path.is_symlink() or not path.is_file():
            failures.append(f"{case_id}: audio is missing")
        elif sha256_file(path) != expected_hashes.get(case_id):
            failures.append(f"{case_id}: audio SHA-256 differs")
    if failures:
        raise SystemExit(
            "NSynth sparse-training corpus verification failed:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )
    print(
        f"verified sealed NSynth sparse-training corpus: "
        f"{len(cases)} cases across "
        f"{len({case['partition_group'] for case in cases})} "
        f"partitions at {root}"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    stage_command = commands.add_parser("stage")
    stage_command.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
    )
    stage_command.add_argument("--fetch-record", type=Path, required=True)
    stage_command.add_argument("--destination", type=Path, required=True)
    stage_command.add_argument("--pointer", type=Path, default=DEFAULT_POINTER)
    stage_command.add_argument("--run-id", required=True)
    stage_command.add_argument("--corpus-id", required=True)
    stage_command.add_argument("--montage-seconds", type=float, default=30)
    stage_command.add_argument(
        "--maximum-instruments",
        type=int,
        default=DEFAULT_MAXIMUM_INSTRUMENTS,
    )
    stage_command.add_argument(
        "--selection-seed",
        default="audio-integrity-nsynth-train-20260731",
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
    if getattr(parsed, "jobs", 1) < 1:
        raise SystemExit("--jobs must be positive")
    raise SystemExit(parsed.function(parsed))
