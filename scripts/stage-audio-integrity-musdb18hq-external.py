#!/usr/bin/env python3
"""Plan, stage, and verify the retained MUSDB18-HQ transfer corpus.

The plan command reads only completed source provenance and creates no
controlled audio. The stage command refuses to run until an exact candidate,
tool set, corpus plan, and evaluation gate have been frozen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


SCHEMA_VERSION = 1
RUN_ID = "audio-integrity-musdb18hq-external-transfer-20260731-001"
CORPUS_ID = "audio-integrity-musdb18hq-controlled-20260731-001"
CORPUS_VERSION = 1
CANDIDATE_ID = "conservative-two-grid-edge-v28-musdb-transfer-v1"
PROFILE = "conservative-two-grid-v28"
EXPECTED_SOURCE_RUN_ID = (
    "audio-integrity-musdb18hq-external-transfer-20260731-001"
)
EXPECTED_SOURCE_COUNT = 150
INVARIANT_SOURCE_COUNT = 30
DEFAULT_MINIMUM_FREE_BYTES = 15 * 1024 * 1024 * 1024
CORPUS_TERMS = (
    "MUSDB18-HQ educational/non-commercial local research evidence only; "
    "do not ship or redistribute source or derived audio."
)
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
READ_BYTES = 1024 * 1024


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(READ_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_json(path: Path, value: dict) -> None:
    path = path.expanduser().resolve()
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


def write_new_json(path: Path, value: dict) -> None:
    path = path.expanduser().resolve()
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace output: {path}")
    replace_json(path, value)


def write_or_verify_json(path: Path, value: dict) -> None:
    if path.exists():
        if load_json(path) != value:
            raise SystemExit(f"existing finalized metadata differs: {path}")
        return
    write_new_json(path, value)


def resolve_beneath(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    if path != root and root not in path.parents:
        raise SystemExit(f"path escapes root: {relative_path}")
    return path


def validate_acquisition(path: Path) -> tuple[dict, Path]:
    state_path = path.expanduser().resolve()
    state = load_json(state_path)
    completed = state.get("completed")
    if (
        state.get("schema_version") != 1
        or state.get("run_id") != EXPECTED_SOURCE_RUN_ID
        or state.get("state") != "acquisition_complete"
        or state.get("feature_scores_opened") is not False
        or state.get("release_heldout_opened") is not False
        or not isinstance(completed, list)
        or len(completed) != EXPECTED_SOURCE_COUNT
        or state.get("completed_count") != EXPECTED_SOURCE_COUNT
        or state.get("source_output_inventory_sha256")
        != canonical_sha256(completed)
    ):
        raise SystemExit("completed source acquisition contract differs")
    source_root = state_path.parent
    seen: set[str] = set()
    for record in completed:
        source_id = record.get("source_id")
        relative_path = record.get("relative_path")
        if (
            not isinstance(source_id, str)
            or not SAFE_ID.fullmatch(source_id)
            or source_id in seen
            or not isinstance(relative_path, str)
        ):
            raise SystemExit("source acquisition inventory is malformed")
        seen.add(source_id)
        source = resolve_beneath(source_root, relative_path)
        if (
            not source.is_file()
            or source.is_symlink()
            or source.stat().st_size != record.get("output_bytes")
            or sha256_file(source) != record.get("output_sha256")
        ):
            raise SystemExit(f"{source_id}: retained source differs")
    return state, source_root


def case(
    source_id: str,
    suffix: str,
    *,
    class_name: str,
    expectation: str,
    extension: str,
) -> dict:
    case_id = f"{source_id}-{suffix}"
    return {
        "case_id": case_id,
        "source_group": source_id,
        "partition_group": source_id,
        "split": "held_out",
        "provenance_tier": "tier_a_confirmed_pcm",
        "class": class_name,
        "expectation": expectation,
        "relative_path": f"audio/{case_id}{extension}",
    }


def output(case_value: dict, *, kind: str, post_filter: str | None = None) -> dict:
    return {
        "case": case_value,
        "output_kind": kind,
        "post_filter": post_filter,
    }


def build_plan(acquisition_path: Path, acquisition: dict) -> dict:
    completed = sorted(
        acquisition["completed"],
        key=lambda record: record["source_id"],
    )
    invariant_sources = {
        record["source_id"]
        for record in sorted(
            completed,
            key=lambda record: hashlib.sha256(
                (
                    record["source_id"]
                    + ":"
                    + record["output_sha256"]
                ).encode()
            ).hexdigest(),
        )[:INVARIANT_SOURCE_COUNT]
    }
    cases: list[dict] = []
    groups: list[dict] = []

    for record in completed:
        source_id = record["source_id"]
        source_relative_path = record["relative_path"]

        reference = case(
            source_id,
            "pcm-reference-wav16",
            class_name="musdb_pcm_reference_wav16",
            expectation="negative",
            extension=".wav",
        )
        lowpass_16 = case(
            source_id,
            "pcm-sharp-lowpass-16000-flac16",
            class_name="musdb_pcm_sharp_lowpass_16000_flac16",
            expectation="negative",
            extension=".flac",
        )
        lowpass_19 = case(
            source_id,
            "pcm-lowpass-19000-flac16",
            class_name="musdb_pcm_lowpass_19000_flac16",
            expectation="negative",
            extension=".flac",
        )
        resample = case(
            source_id,
            "pcm-resample-32000-44100-flac16",
            class_name="musdb_pcm_resample_32000_44100_flac16",
            expectation="negative",
            extension=".flac",
        )
        for value in (reference, lowpass_16, lowpass_19, resample):
            cases.append(value)
        groups.extend(
            [
                {
                    "group_id": f"{source_id}-pcm-reference",
                    "source_id": source_id,
                    "source_relative_path": source_relative_path,
                    "operation": "lossless_hardlink",
                    "outputs": [output(reference, kind="wav16")],
                },
                {
                    "group_id": f"{source_id}-pcm-sharp-lowpass-16000",
                    "source_id": source_id,
                    "source_relative_path": source_relative_path,
                    "operation": "pcm_filter",
                    "pre_filter": (
                        "lowpass=f=16000:p=2,"
                        "lowpass=f=16000:p=2,"
                        "lowpass=f=16000:p=2,"
                        "lowpass=f=16000:p=2"
                    ),
                    "outputs": [output(lowpass_16, kind="flac16")],
                },
                {
                    "group_id": f"{source_id}-pcm-lowpass-19000",
                    "source_id": source_id,
                    "source_relative_path": source_relative_path,
                    "operation": "pcm_filter",
                    "pre_filter": "lowpass=f=19000:p=2",
                    "outputs": [output(lowpass_19, kind="flac16")],
                },
                {
                    "group_id": f"{source_id}-pcm-resample-32000-44100",
                    "source_id": source_id,
                    "source_relative_path": source_relative_path,
                    "operation": "pcm_filter",
                    "pre_filter": (
                        "aresample=32000:resampler=swr,"
                        "aresample=44100:resampler=swr"
                    ),
                    "outputs": [output(resample, kind="flac16")],
                },
            ]
        )

        aac_128 = case(
            source_id,
            "aac-lc-128-to-flac16",
            class_name="musdb_aac_lc_128_to_flac16",
            expectation="controlled_positive",
            extension=".flac",
        )
        aac_outputs = [output(aac_128, kind="flac16")]
        cases.append(aac_128)
        if source_id in invariant_sources:
            invariant_specs = [
                (
                    "aac-lc-128-gain-minus3db-to-flac16",
                    "musdb_aac_lc_128_gain_minus3db_to_flac16",
                    ".flac",
                    "flac16",
                    "volume=-3dB",
                ),
                (
                    "aac-lc-128-trim-137-to-flac16",
                    "musdb_aac_lc_128_trim_137_to_flac16",
                    ".flac",
                    "flac16",
                    "atrim=start_sample=137",
                ),
                (
                    "aac-lc-128-to-wav16",
                    "musdb_aac_lc_128_to_wav16",
                    ".wav",
                    "wav16",
                    None,
                ),
                (
                    "aac-lc-128-to-aiff24",
                    "musdb_aac_lc_128_to_aiff24",
                    ".aiff",
                    "aiff24",
                    None,
                ),
            ]
            for (
                suffix,
                class_name,
                extension,
                kind,
                post_filter,
            ) in invariant_specs:
                value = case(
                    source_id,
                    suffix,
                    class_name=class_name,
                    expectation="controlled_positive",
                    extension=extension,
                )
                cases.append(value)
                aac_outputs.append(
                    output(
                        value,
                        kind=kind,
                        post_filter=post_filter,
                    )
                )
        groups.append(
            {
                "group_id": f"{source_id}-aac-lc-128",
                "source_id": source_id,
                "source_relative_path": source_relative_path,
                "operation": "lossy_round_trip",
                "intermediate_extension": ".m4a",
                "encoder": "aac",
                "encoder_arguments": [
                    "-profile:a",
                    "aac_low",
                    "-b:a",
                    "128k",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                ],
                "outputs": aac_outputs,
            }
        )

        lossy_specs = [
            (
                "aac-at-128",
                "aac-at-128-to-flac16",
                "musdb_aac_at_128_to_flac16",
                ".m4a",
                "aac_at",
                [
                    "-aac_at_mode",
                    "cbr",
                    "-b:a",
                    "128k",
                    "-aac_at_quality",
                    "2",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                ],
            ),
            (
                "mp3-128",
                "mp3-128-to-flac16",
                "musdb_mp3_128_to_flac16",
                ".mp3",
                "libmp3lame",
                ["-b:a", "128k", "-ar", "44100", "-ac", "2"],
            ),
            (
                "vorbis-native-q3",
                "vorbis-native-q3-to-flac16",
                "musdb_vorbis_native_q3_to_flac16",
                ".ogg",
                "vorbis",
                [
                    "-strict",
                    "-2",
                    "-q:a",
                    "3",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                ],
            ),
            (
                "aac-lc-192",
                "aac-lc-192-to-flac16",
                "musdb_aac_lc_192_to_flac16",
                ".m4a",
                "aac",
                [
                    "-profile:a",
                    "aac_low",
                    "-b:a",
                    "192k",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                ],
            ),
            (
                "mp3-320",
                "mp3-320-to-flac16",
                "musdb_mp3_320_to_flac16",
                ".mp3",
                "libmp3lame",
                ["-b:a", "320k", "-ar", "44100", "-ac", "2"],
            ),
            (
                "opus-96",
                "opus-96-to-flac16",
                "musdb_opus_96_to_flac16",
                ".opus",
                "libopus",
                [
                    "-b:a",
                    "96k",
                    "-vbr",
                    "on",
                    "-compression_level",
                    "10",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                ],
            ),
        ]
        for (
            group_suffix,
            case_suffix,
            class_name,
            intermediate_extension,
            encoder,
            encoder_arguments,
        ) in lossy_specs:
            value = case(
                source_id,
                case_suffix,
                class_name=class_name,
                expectation="controlled_positive",
                extension=".flac",
            )
            cases.append(value)
            groups.append(
                {
                    "group_id": f"{source_id}-{group_suffix}",
                    "source_id": source_id,
                    "source_relative_path": source_relative_path,
                    "operation": "lossy_round_trip",
                    "intermediate_extension": intermediate_extension,
                    "encoder": encoder,
                    "encoder_arguments": encoder_arguments,
                    "outputs": [output(value, kind="flac16")],
                }
            )

    cases.sort(key=lambda value: value["case_id"])
    groups.sort(key=lambda value: value["group_id"])
    manifest = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "corpus_version": CORPUS_VERSION,
        "usage_terms": CORPUS_TERMS,
        "audio_root_env": "LOSSYTRACE_RESEARCH_MUSDB18HQ_ROOT",
        "repetitions": 1,
        "analysis_max_seconds": 30,
        "cases": cases,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": RUN_ID,
        "state": "planned_before_external_transfer_feature_opening",
        "candidate_frozen": False,
        "external_transfer_feature_scores_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "acquisition": {
            "path": str(acquisition_path),
            "sha256": sha256_file(acquisition_path),
            "source_output_inventory_sha256": acquisition[
                "source_output_inventory_sha256"
            ],
            "source_count": len(completed),
        },
        "corpus": {
            "corpus_id": CORPUS_ID,
            "corpus_version": CORPUS_VERSION,
            "terms": CORPUS_TERMS,
            "source_count": len(completed),
            "case_count": len(cases),
            "group_count": len(groups),
            "invariant_source_count": len(invariant_sources),
            "invariant_source_ids": sorted(invariant_sources),
            "class_counts": dict(
                sorted(Counter(value["class"] for value in cases).items())
            ),
            "negative_count": sum(
                value["expectation"] == "negative" for value in cases
            ),
            "controlled_positive_count": sum(
                value["expectation"] == "controlled_positive"
                for value in cases
            ),
        },
        "manifest": manifest,
        "transformation_groups": groups,
        "transformation_inventory_sha256": canonical_sha256(groups),
        "tool": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
    }


def command_plan(args: argparse.Namespace) -> int:
    acquisition_path = args.acquisition.expanduser().resolve()
    acquisition, _ = validate_acquisition(acquisition_path)
    plan = build_plan(acquisition_path, acquisition)
    if (
        plan["corpus"]["case_count"] != 1_770
        or plan["corpus"]["negative_count"] != 600
        or plan["corpus"]["controlled_positive_count"] != 1_170
        or plan["corpus"]["group_count"] != 1_650
    ):
        raise SystemExit("planned corpus inventory differs")
    write_new_json(args.output, plan)
    print(
        f"planned {plan['corpus']['case_count']} cases from "
        f"{plan['corpus']['source_count']} sources without opening features"
    )
    return 0


def validate_plan(plan_path: Path) -> tuple[dict, dict, Path]:
    plan = load_json(plan_path)
    acquisition_path = Path(plan.get("acquisition", {}).get("path", ""))
    acquisition, source_root = validate_acquisition(acquisition_path)
    rebuilt = build_plan(acquisition_path, acquisition)
    for volatile in ("created_at",):
        rebuilt.pop(volatile, None)
        plan_copy = dict(plan)
        plan_copy.pop(volatile, None)
        plan = plan_copy
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("run_id") != RUN_ID
        or plan.get("state")
        != "planned_before_external_transfer_feature_opening"
        or plan.get("external_transfer_feature_scores_opened") is not False
        or plan.get("release_heldout_opened") is not False
        or plan != rebuilt
    ):
        raise SystemExit("corpus plan contract differs")
    return load_json(plan_path), acquisition, source_root


def validate_precommit(
    path: Path,
    *,
    plan_path: Path,
    plan: dict,
) -> dict:
    precommit = load_json(path)
    tools = precommit.get("tools", {})
    corpus_plan = precommit.get("corpus_plan", {})
    if (
        precommit.get("schema_version") != 1
        or precommit.get("state") != "frozen_before_external_transfer"
        or precommit.get("candidate_id") != CANDIDATE_ID
        or precommit.get("candidate_frozen") is not True
        or precommit.get("external_transfer_feature_scores_opened") is not False
        or precommit.get("release_heldout_opened") is not False
        or precommit.get("public_verdict_enabled") is not False
        or precommit.get("feature_version") != 0
        or precommit.get("transform_profile") != PROFILE
        or corpus_plan.get("sha256") != sha256_file(plan_path)
        or corpus_plan.get("transformation_inventory_sha256")
        != plan["transformation_inventory_sha256"]
        or tools.get("stager_sha256")
        != sha256_file(Path(__file__).resolve())
    ):
        raise SystemExit("frozen candidate/stager contract differs")
    return precommit


def ffmpeg_base(ffmpeg: str, source: Path) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-n",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-map_metadata",
        "-1",
        "-vn",
    ]


def output_arguments(kind: str) -> list[str]:
    if kind == "flac16":
        return ["-c:a", "flac", "-sample_fmt", "s16"]
    if kind == "wav16":
        return ["-c:a", "pcm_s16le"]
    if kind == "aiff24":
        return ["-c:a", "pcm_s24be"]
    raise SystemExit(f"unknown lossless output kind: {kind}")


def sanitized(command: list[str], roots: list[Path]) -> list[str]:
    result = list(command)
    replacements = [
        (str(root), f"<ROOT_{index}>")
        for index, root in enumerate(roots, start=1)
    ]
    for index, part in enumerate(result):
        for source, replacement in replacements:
            part = part.replace(source, replacement)
        result[index] = part
    return result


def run_command(command: list[str]) -> None:
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode:
        raise SystemExit(
            f"command failed ({completed.returncode}): "
            f"{completed.stderr.strip()}"
        )


def probe_audio(ffprobe: str, path: Path) -> dict:
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            (
                "stream=codec_name,sample_rate,channels,bits_per_raw_sample,"
                "duration"
            ),
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(completed.stdout)
    streams = value.get("streams")
    if not isinstance(streams, list) or len(streams) != 1:
        raise SystemExit(f"{path}: expected exactly one audio stream")
    stream = streams[0]
    return {
        key: stream.get(key)
        for key in (
            "codec_name",
            "sample_rate",
            "channels",
            "bits_per_raw_sample",
            "duration",
        )
    }


def expected_codec(kind: str) -> str:
    return {
        "flac16": "flac",
        "wav16": "pcm_s16le",
        "aiff24": "pcm_s24be",
    }[kind]


def validate_ffmpeg_plan_capabilities(
    ffmpeg: str,
    plan: dict,
) -> dict:
    filters = sorted(
        {
            group["pre_filter"]
            for group in plan["transformation_groups"]
            if group["operation"] == "pcm_filter"
        }
    )
    encoder_recipes = sorted(
        {
            (
                group["encoder"],
                tuple(group["encoder_arguments"]),
            )
            for group in plan["transformation_groups"]
            if group["operation"] == "lossy_round_trip"
        }
    )
    probes = []
    for filter_value in filters:
        command = [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            "0.1",
            "-af",
            filter_value,
            "-f",
            "null",
            "-",
        ]
        run_command(command)
        probes.append(
            {
                "kind": "pcm_filter",
                "filter": filter_value,
            }
        )
    for encoder, arguments in encoder_recipes:
        command = [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            "0.1",
            "-c:a",
            encoder,
            *arguments,
            "-f",
            "null",
            "-",
        ]
        run_command(command)
        probes.append(
            {
                "kind": "lossy_encoder",
                "encoder": encoder,
                "arguments": list(arguments),
            }
        )
    return {
        "schema_version": 1,
        "probe_count": len(probes),
        "probes": probes,
        "inventory_sha256": canonical_sha256(probes),
    }


def clean_unjournaled_partials(
    partial_root: Path,
    group: dict,
    state: dict,
) -> None:
    candidates = [
        partial_root
        / (
            output_value["case"]["case_id"]
            + ".partial"
            + Path(output_value["case"]["relative_path"]).suffix
        )
        for output_value in group["outputs"]
    ]
    if group["operation"] == "lossy_round_trip":
        candidates.append(
            partial_root
            / (
                group["group_id"]
                + ".partial"
                + group["intermediate_extension"]
            )
        )
    removed = []
    for candidate in candidates:
        if candidate.exists() or candidate.is_symlink():
            if candidate.is_dir():
                raise SystemExit(
                    f"refusing unexpected partial directory: {candidate}"
                )
            removed.append(
                {
                    "path": candidate.name,
                    "bytes": candidate.stat().st_size,
                    "sha256": sha256_file(candidate),
                }
            )
            candidate.unlink()
    if removed:
        state.setdefault("recovery_cleanups", []).append(
            {
                "at": datetime.now(UTC).isoformat(),
                "group_id": group["group_id"],
                "reason": "unjournaled_reproducible_partial",
                "removed": removed,
            }
        )


def group_paths(
    root: Path,
    partial_root: Path,
    group: dict,
) -> list[tuple[dict, Path, Path]]:
    values = []
    for output_value in group["outputs"]:
        case_value = output_value["case"]
        final = resolve_beneath(root, case_value["relative_path"])
        partial = (
            partial_root
            / (
                case_value["case_id"]
                + ".partial"
                + Path(case_value["relative_path"]).suffix
            )
        )
        values.append((output_value, partial, final))
    return values


def verify_group_record(root: Path, record: dict) -> None:
    for output_record in record["outputs"]:
        path = resolve_beneath(root, output_record["relative_path"])
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != output_record["bytes"]
            or sha256_file(path) != output_record["sha256"]
        ):
            raise SystemExit(
                f"{output_record['case_id']}: retained output differs"
            )


def verify_completed_group_contract(
    root: Path,
    group: dict,
    record: dict,
) -> None:
    if (
        record.get("group_id") != group["group_id"]
        or record.get("source_id") != group["source_id"]
        or record.get("source_relative_path")
        != group["source_relative_path"]
        or record.get("plan_group_sha256") != canonical_sha256(group)
        or {
            output_record.get("case_id")
            for output_record in record.get("outputs", [])
        }
        != {
            output_value["case"]["case_id"]
            for output_value in group["outputs"]
        }
    ):
        raise SystemExit(
            f"{group['group_id']}: completed group contract differs"
        )
    verify_group_record(root, record)


def remove_committed_journal(
    *,
    root: Path,
    partial_root: Path,
    state_path: Path,
    state: dict,
    group: dict,
    record: dict,
) -> None:
    journal_path = partial_root / f"{group['group_id']}.journal.json"
    if not journal_path.exists():
        return
    journal_bytes = journal_path.stat().st_size
    journal_sha256 = sha256_file(journal_path)
    if load_json(journal_path).get("record") != record:
        raise SystemExit(
            f"{group['group_id']}: committed journal differs"
        )
    verify_completed_group_contract(root, group, record)
    for _, partial, _ in group_paths(root, partial_root, group):
        if partial.exists() or partial.is_symlink():
            raise SystemExit(
                f"{group['group_id']}: committed partial output remains"
            )
    intermediate = record.get("intermediate")
    if intermediate is not None:
        intermediate_path = partial_root / intermediate["partial_name"]
        if intermediate_path.exists() or intermediate_path.is_symlink():
            raise SystemExit(
                f"{group['group_id']}: committed lossy intermediate remains"
            )
    cleanup = {
        "group_id": group["group_id"],
        "reason": "committed_journal_after_state_checkpoint",
        "removed": [
            {
                "path": journal_path.name,
                "bytes": journal_bytes,
                "sha256": journal_sha256,
            }
        ],
    }
    matching = [
        value
        for value in state.setdefault("recovery_cleanups", [])
        if value.get("group_id") == group["group_id"]
        and value.get("reason")
        == "committed_journal_after_state_checkpoint"
    ]
    if matching:
        if len(matching) != 1 or {
            key: matching[0].get(key) for key in cleanup
        } != cleanup:
            raise SystemExit(
                f"{group['group_id']}: committed-journal cleanup differs"
            )
    else:
        cleanup["at"] = datetime.now(UTC).isoformat()
        state["recovery_cleanups"].append(cleanup)
        state["updated_at"] = cleanup["at"]
        replace_json(state_path, state)
    journal_path.unlink()


def recover_journal(
    *,
    root: Path,
    state_path: Path,
    state: dict,
    group: dict,
    journal_path: Path,
    partial_root: Path,
) -> None:
    journal = load_json(journal_path)
    record = journal.get("record")
    if (
        not isinstance(record, dict)
        or record.get("group_id") != group["group_id"]
        or record.get("plan_group_sha256") != canonical_sha256(group)
    ):
        raise SystemExit(f"{group['group_id']}: pending journal differs")
    by_case = {
        output_record["case_id"]: output_record
        for output_record in record["outputs"]
    }
    for output_value, partial, final in group_paths(
        root,
        partial_root,
        group,
    ):
        expected = by_case[output_value["case"]["case_id"]]
        present = [path for path in (partial, final) if path.exists()]
        if len(present) != 1:
            raise SystemExit(
                f"{expected['case_id']}: pending output state is ambiguous"
            )
        path = present[0]
        if (
            path.stat().st_size != expected["bytes"]
            or sha256_file(path) != expected["sha256"]
        ):
            raise SystemExit(f"{expected['case_id']}: pending output differs")
        if path == partial:
            partial.replace(final)
    intermediate = record.get("intermediate")
    if intermediate is not None:
        intermediate_path = partial_root / intermediate["partial_name"]
        if intermediate_path.exists():
            if (
                intermediate_path.stat().st_size != intermediate["bytes"]
                or sha256_file(intermediate_path) != intermediate["sha256"]
            ):
                raise SystemExit(
                    f"{group['group_id']}: pending intermediate differs"
                )
            intermediate_path.unlink()
    verify_group_record(root, record)
    state["completed"].append(record)
    state["completed_group_count"] = len(state["completed"])
    state["updated_at"] = datetime.now(UTC).isoformat()
    replace_json(state_path, state)
    journal_path.unlink()


def process_group(
    *,
    root: Path,
    source_root: Path,
    partial_root: Path,
    state_path: Path,
    state: dict,
    group: dict,
    ffmpeg: str,
    ffprobe: str,
) -> None:
    group_id = group["group_id"]
    source = resolve_beneath(source_root, group["source_relative_path"])
    outputs = group_paths(root, partial_root, group)
    journal_path = partial_root / f"{group_id}.journal.json"
    if journal_path.exists():
        recover_journal(
            root=root,
            state_path=state_path,
            state=state,
            group=group,
            journal_path=journal_path,
            partial_root=partial_root,
        )
        return
    cleanup_count = len(state.get("recovery_cleanups", []))
    clean_unjournaled_partials(partial_root, group, state)
    if len(state.get("recovery_cleanups", [])) != cleanup_count:
        state["updated_at"] = datetime.now(UTC).isoformat()
        replace_json(state_path, state)
    for _, _, final in outputs:
        if final.exists() or final.is_symlink():
            raise SystemExit(f"untracked final output exists: {final}")
        final.parent.mkdir(parents=True, exist_ok=True)

    commands: list[list[str]] = []
    intermediate_record = None
    if group["operation"] == "lossless_hardlink":
        if len(outputs) != 1:
            raise SystemExit(f"{group_id}: hardlink group must have one output")
        os.link(source, outputs[0][1])
    elif group["operation"] == "pcm_filter":
        if len(outputs) != 1:
            raise SystemExit(f"{group_id}: PCM filter must have one output")
        output_value, partial, _ = outputs[0]
        command = ffmpeg_base(ffmpeg, source)
        command.extend(["-af", group["pre_filter"]])
        command.extend(output_arguments(output_value["output_kind"]))
        command.append(str(partial))
        run_command(command)
        commands.append(sanitized(command, [source_root, root]))
    elif group["operation"] == "lossy_round_trip":
        intermediate = (
            partial_root
            / (
                group_id
                + ".partial"
                + group["intermediate_extension"]
            )
        )
        encode = ffmpeg_base(ffmpeg, source)
        encode.extend(["-c:a", group["encoder"]])
        encode.extend(group["encoder_arguments"])
        encode.append(str(intermediate))
        run_command(encode)
        commands.append(sanitized(encode, [source_root, root]))
        intermediate_record = {
            "partial_name": intermediate.name,
            "sha256": sha256_file(intermediate),
            "bytes": intermediate.stat().st_size,
        }
        for output_value, partial, _ in outputs:
            decode = ffmpeg_base(ffmpeg, intermediate)
            post_filter = output_value.get("post_filter")
            if post_filter:
                decode.extend(["-af", post_filter])
            decode.extend(output_arguments(output_value["output_kind"]))
            decode.append(str(partial))
            run_command(decode)
            commands.append(sanitized(decode, [source_root, root]))
    else:
        raise SystemExit(f"{group_id}: unknown operation")

    output_records = []
    for output_value, partial, _ in outputs:
        probe = probe_audio(ffprobe, partial)
        if probe["codec_name"] != expected_codec(
            output_value["output_kind"]
        ):
            raise SystemExit(
                f"{output_value['case']['case_id']}: output codec differs"
            )
        output_records.append(
            {
                "case_id": output_value["case"]["case_id"],
                "class": output_value["case"]["class"],
                "expectation": output_value["case"]["expectation"],
                "relative_path": output_value["case"]["relative_path"],
                "sha256": sha256_file(partial),
                "bytes": partial.stat().st_size,
                "probe": probe,
            }
        )
    record = {
        "group_id": group_id,
        "source_id": group["source_id"],
        "source_relative_path": group["source_relative_path"],
        "source_sha256": sha256_file(source),
        "plan_group_sha256": canonical_sha256(group),
        "operation": group["operation"],
        "commands": commands,
        "intermediate": intermediate_record,
        "outputs": output_records,
    }
    write_new_json(journal_path, {"record": record})
    for _, partial, final in outputs:
        partial.replace(final)
    if intermediate_record is not None:
        intermediate_path = partial_root / intermediate_record["partial_name"]
        intermediate_path.unlink()
    verify_group_record(root, record)
    state["completed"].append(record)
    state["completed_group_count"] = len(state["completed"])
    state["updated_at"] = datetime.now(UTC).isoformat()
    replace_json(state_path, state)
    journal_path.unlink()


def create_or_load_state(
    *,
    root: Path,
    plan_path: Path,
    precommit_path: Path,
    ffmpeg_version: str,
    ffprobe_version: str,
) -> tuple[Path, dict]:
    state_path = root / "staging-state.json"
    if state_path.exists():
        state = load_json(state_path)
        if (
            state.get("schema_version") != SCHEMA_VERSION
            or state.get("run_id") != RUN_ID
            or state.get("state")
            not in {
                "staging_in_progress",
                "paused_at_disk_reserve",
                "staging_complete",
            }
            or state.get("plan_sha256") != sha256_file(plan_path)
            or state.get("candidate_precommit_sha256")
            != sha256_file(precommit_path)
            or state.get("ffmpeg_version") != ffmpeg_version
            or state.get("ffprobe_version") != ffprobe_version
            or state.get("external_transfer_feature_scores_opened")
            is not False
            or state.get("release_heldout_opened") is not False
            or state.get("public_verdict_enabled") is not False
            or not isinstance(state.get("completed"), list)
            or state.get("completed_group_count")
            != len(state.get("completed", []))
            or not isinstance(state.get("recovery_cleanups"), list)
        ):
            raise SystemExit("existing staging state contract differs")
        return state_path, state
    if root.exists() and any(root.iterdir()):
        raise SystemExit(f"refusing non-empty corpus root: {root}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "audio").mkdir()
    (root / ".partial").mkdir()
    state = {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        "state": "staging_in_progress",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "plan_path": str(plan_path),
        "plan_sha256": sha256_file(plan_path),
        "candidate_precommit_path": str(precommit_path),
        "candidate_precommit_sha256": sha256_file(precommit_path),
        "ffmpeg_version": ffmpeg_version,
        "ffprobe_version": ffprobe_version,
        "external_transfer_feature_scores_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "completed_group_count": 0,
        "completed": [],
        "recovery_cleanups": [],
    }
    replace_json(state_path, state)
    return state_path, state


def finalize(
    *,
    root: Path,
    plan_path: Path,
    plan: dict,
    precommit_path: Path,
    state_path: Path,
    state: dict,
) -> None:
    if "finalization_started_at" not in state:
        state["finalization_started_at"] = datetime.now(UTC).isoformat()
        state["updated_at"] = state["finalization_started_at"]
        replace_json(state_path, state)
    completed = state["completed"]
    provenance_by_group = {
        record["group_id"]: record for record in completed
    }
    if len(provenance_by_group) != len(plan["transformation_groups"]):
        raise SystemExit("completed provenance group inventory differs")
    fingerprints = {}
    for record in completed:
        for output_record in record["outputs"]:
            case_id = output_record["case_id"]
            if case_id in fingerprints:
                raise SystemExit(f"duplicate finalized case: {case_id}")
            fingerprints[case_id] = output_record["sha256"]
    if set(fingerprints) != {
        value["case_id"] for value in plan["manifest"]["cases"]
    }:
        raise SystemExit("finalized case inventory differs")

    plan_copy = load_json(plan_path)
    precommit_copy = load_json(precommit_path)
    manifest = plan["manifest"]
    fingerprint_report = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "corpus_version": CORPUS_VERSION,
        "case_sha256": dict(sorted(fingerprints.items())),
    }
    provenance = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "corpus_id": CORPUS_ID,
        "plan_sha256": sha256_file(plan_path),
        "candidate_precommit_sha256": sha256_file(precommit_path),
        "ffmpeg_version": state["ffmpeg_version"],
        "ffprobe_version": state["ffprobe_version"],
        "lossy_intermediates_retained": False,
        "groups": completed,
        "recovery_cleanups": state["recovery_cleanups"],
    }
    write_or_verify_json(root / "corpus-plan.json", plan_copy)
    write_or_verify_json(
        root / "candidate-precommit.json",
        precommit_copy,
    )
    write_or_verify_json(root / "manifest.json", manifest)
    write_or_verify_json(root / "fingerprints.json", fingerprint_report)
    write_or_verify_json(root / "provenance-ledger.json", provenance)

    metadata_files = [
        "candidate-precommit.json",
        "corpus-plan.json",
        "fingerprints.json",
        "manifest.json",
        "provenance-ledger.json",
    ]
    metadata_inventory = [
        {
            "relative_path": name,
            "sha256": sha256_file(root / name),
            "bytes": (root / name).stat().st_size,
        }
        for name in metadata_files
    ]
    audio_inventory = sorted(
        (
            {
                "case_id": output_record["case_id"],
                "relative_path": output_record["relative_path"],
                "sha256": output_record["sha256"],
                "bytes": output_record["bytes"],
            }
            for record in completed
            for output_record in record["outputs"]
        ),
        key=lambda value: value["case_id"],
    )
    seal = {
        "schema_version": 1,
        "created_at": state["finalization_started_at"],
        "run_id": RUN_ID,
        "state": "retained_controlled_corpus_complete",
        "corpus_id": CORPUS_ID,
        "source_count": plan["corpus"]["source_count"],
        "case_count": len(audio_inventory),
        "class_counts": plan["corpus"]["class_counts"],
        "negative_count": plan["corpus"]["negative_count"],
        "controlled_positive_count": plan["corpus"][
            "controlled_positive_count"
        ],
        "external_transfer_feature_scores_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "lossy_intermediates_retained": False,
        "terms": plan["corpus"]["terms"],
        "retention": (
            "Retain source acquisition, final lossless audio, manifests, "
            "fingerprints, provenance, precommit, and seal for future "
            "versions. Temporary lossy intermediates are reproducible and "
            "were removed after their hashes were committed."
        ),
        "metadata_inventory": metadata_inventory,
        "audio_inventory": audio_inventory,
        "integrity_sha256": canonical_sha256(
            {
                "metadata_inventory": metadata_inventory,
                "audio_inventory": audio_inventory,
            }
        ),
    }
    write_or_verify_json(root / "seal.json", seal)
    state["state"] = "staging_complete"
    state["completed_at"] = datetime.now(UTC).isoformat()
    state["updated_at"] = state["completed_at"]
    state["seal_sha256"] = sha256_file(root / "seal.json")
    replace_json(state_path, state)


def command_stage(args: argparse.Namespace) -> int:
    plan_path = args.plan.expanduser().resolve()
    plan, _, source_root = validate_plan(plan_path)
    precommit_path = args.precommit.expanduser().resolve()
    precommit = validate_precommit(
        precommit_path,
        plan_path=plan_path,
        plan=plan,
    )
    root = args.root.expanduser().resolve()
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
    required_encoders = set(
        precommit.get("environment", {}).get(
            "required_audio_encoders",
            [],
        )
    )
    capability_report = validate_ffmpeg_plan_capabilities(
        str(ffmpeg_path),
        plan,
    )
    if (
        precommit.get("environment", {}).get("ffmpeg_version")
        != ffmpeg_version
        or precommit.get("environment", {}).get("ffprobe_version")
        != ffprobe_version
        or precommit.get("environment", {})
        .get("ffmpeg_executable", {})
        .get("sha256")
        != sha256_file(ffmpeg_path)
        or precommit.get("environment", {})
        .get("ffprobe_executable", {})
        .get("sha256")
        != sha256_file(ffprobe_path)
        or precommit.get("environment", {}).get(
            "audio_encoder_inventory_sha256"
        )
        != hashlib.sha256(encoder_output.encode()).hexdigest()
        or precommit.get("environment", {}).get(
            "ffmpeg_plan_capability"
        )
        != capability_report
        or not required_encoders
        or not required_encoders.issubset(available_encoders)
    ):
        raise SystemExit("frozen FFmpeg/encoder environment differs")
    state_path, state = create_or_load_state(
        root=root,
        plan_path=plan_path,
        precommit_path=precommit_path,
        ffmpeg_version=ffmpeg_version,
        ffprobe_version=ffprobe_version,
    )
    if state.get("state") == "staging_complete":
        print("staging already complete; verifying retained corpus")
        return command_verify(argparse.Namespace(root=root))
    completed_by_id = {
        record["group_id"]: record for record in state["completed"]
    }
    if len(completed_by_id) != len(state["completed"]):
        raise SystemExit("duplicate completed staging group IDs")
    groups = plan["transformation_groups"]
    new_groups = 0
    partial_root = root / ".partial"
    for index, group in enumerate(groups, start=1):
        group_id = group["group_id"]
        if group_id in completed_by_id:
            record = completed_by_id[group_id]
            verify_completed_group_contract(root, group, record)
            remove_committed_journal(
                root=root,
                partial_root=partial_root,
                state_path=state_path,
                state=state,
                group=group,
                record=record,
            )
            print(
                f"[{index:04d}/{len(groups):04d}] {group_id} verified existing",
                flush=True,
            )
            continue
        if args.max_new_groups is not None and new_groups >= args.max_new_groups:
            break
        source = resolve_beneath(
            source_root,
            group["source_relative_path"],
        )
        conservative_bytes = source.stat().st_size * max(
            2,
            2 * len(group["outputs"]),
        )
        free_bytes = shutil.disk_usage(root).free
        if free_bytes - conservative_bytes < args.minimum_free_bytes:
            state["state"] = "paused_at_disk_reserve"
            state["updated_at"] = datetime.now(UTC).isoformat()
            state["free_bytes"] = free_bytes
            state["next_group_estimated_maximum_bytes"] = (
                conservative_bytes
            )
            replace_json(state_path, state)
            print(
                f"paused before {group_id}: preserving "
                f"{args.minimum_free_bytes} byte free-space reserve"
            )
            return 0
        process_group(
            root=root,
            source_root=source_root,
            partial_root=partial_root,
            state_path=state_path,
            state=state,
            group=group,
            ffmpeg=str(ffmpeg_path),
            ffprobe=str(ffprobe_path),
        )
        completed_by_id[group_id] = state["completed"][-1]
        new_groups += 1
        print(
            f"[{index:04d}/{len(groups):04d}] {group_id} staged and verified",
            flush=True,
        )
    if len(state["completed"]) != len(groups):
        state["state"] = "staging_in_progress"
        state["updated_at"] = datetime.now(UTC).isoformat()
        replace_json(state_path, state)
        print(
            f"paused after {len(state['completed'])}/{len(groups)} groups"
        )
        return 0
    if any(partial_root.iterdir()):
        raise SystemExit("staging partial files remain before finalization")
    finalize(
        root=root,
        plan_path=plan_path,
        plan=plan,
        precommit_path=precommit_path,
        state_path=state_path,
        state=state,
    )
    print(
        f"completed and sealed {plan['corpus']['case_count']} retained cases"
    )
    return 0


def command_verify(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    state = load_json(root / "staging-state.json")
    seal = load_json(root / "seal.json")
    manifest = load_json(root / "manifest.json")
    fingerprints = load_json(root / "fingerprints.json")
    provenance = load_json(root / "provenance-ledger.json")
    plan = load_json(root / "corpus-plan.json")
    precommit = load_json(root / "candidate-precommit.json")
    if (
        state.get("state") != "staging_complete"
        or state.get("seal_sha256") != sha256_file(root / "seal.json")
        or seal.get("state") != "retained_controlled_corpus_complete"
        or seal.get("case_count") != 1_770
        or seal.get("source_count") != 150
        or seal.get("external_transfer_feature_scores_opened") is not False
        or seal.get("release_heldout_opened") is not False
        or seal.get("public_verdict_enabled") is not False
        or manifest != plan.get("manifest")
        or precommit.get("candidate_id") != CANDIDATE_ID
        or fingerprints.get("case_sha256") is None
        or provenance.get("lossy_intermediates_retained") is not False
    ):
        raise SystemExit("retained corpus contract differs")
    expected_top_level = {
        ".partial",
        "audio",
        "candidate-precommit.json",
        "corpus-plan.json",
        "fingerprints.json",
        "manifest.json",
        "provenance-ledger.json",
        "seal.json",
        "staging-state.json",
    }
    actual_top_level = {path.name for path in root.iterdir()}
    if actual_top_level != expected_top_level:
        raise SystemExit("retained corpus top-level inventory differs")
    audio_entries = list((root / "audio").iterdir())
    if any(
        not path.is_file() or path.is_symlink()
        for path in audio_entries
    ):
        raise SystemExit("retained audio directory has non-file entries")
    expected_files = {
        value["relative_path"] for value in seal["audio_inventory"]
    }
    actual_files = {
        path.relative_to(root).as_posix()
        for path in audio_entries
    }
    if actual_files != expected_files:
        raise SystemExit("retained audio file inventory differs")
    for value in seal["metadata_inventory"]:
        path = resolve_beneath(root, value["relative_path"])
        if (
            path.stat().st_size != value["bytes"]
            or sha256_file(path) != value["sha256"]
        ):
            raise SystemExit(
                f"{value['relative_path']}: metadata differs"
            )
    for value in seal["audio_inventory"]:
        path = resolve_beneath(root, value["relative_path"])
        if (
            path.is_symlink()
            or path.stat().st_size != value["bytes"]
            or sha256_file(path) != value["sha256"]
            or fingerprints["case_sha256"].get(value["case_id"])
            != value["sha256"]
        ):
            raise SystemExit(f"{value['case_id']}: audio differs")
    partial_root = root / ".partial"
    if not partial_root.is_dir() or any(partial_root.iterdir()):
        raise SystemExit("retained corpus has unexpected partial files")
    integrity = canonical_sha256(
        {
            "metadata_inventory": seal["metadata_inventory"],
            "audio_inventory": seal["audio_inventory"],
        }
    )
    if integrity != seal["integrity_sha256"]:
        raise SystemExit("retained corpus integrity commitment differs")
    print(
        f"verified {seal['case_count']} retained cases; "
        f"seal SHA-256 {sha256_file(root / 'seal.json')}"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan")
    plan.add_argument("--acquisition", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    plan.set_defaults(handler=command_plan)

    stage = commands.add_parser("stage")
    stage.add_argument("--plan", type=Path, required=True)
    stage.add_argument("--precommit", type=Path, required=True)
    stage.add_argument("--root", type=Path, required=True)
    stage.add_argument("--ffmpeg", default="ffmpeg")
    stage.add_argument("--ffprobe", default="ffprobe")
    stage.add_argument(
        "--minimum-free-bytes",
        type=int,
        default=DEFAULT_MINIMUM_FREE_BYTES,
    )
    stage.add_argument("--max-new-groups", type=int)
    stage.set_defaults(handler=command_stage)

    verify = commands.add_parser("verify")
    verify.add_argument("--root", type=Path, required=True)
    verify.set_defaults(handler=command_verify)
    return root


def main() -> int:
    args = parser().parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
