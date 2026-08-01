#!/usr/bin/env python3
"""Run the locked exact MP3 hybrid probe over selected consumed-corpus cases."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path


START_SECONDS = 5
DURATION_SECONDS = 20
ALGORITHM = "iso11172_3_polyphase_analysis_plus_long_hybrid_mdct"


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


def run_case(
    *,
    case: dict,
    source: Path,
    audio_sha256: str,
    runner: Path,
    runner_sha256: str,
    harness_sha256: str,
    manifest_sha256: str,
    fingerprints_sha256: str,
    partial: Path,
) -> dict:
    commitment = {
        "case_id": case["case_id"],
        "audio_sha256": audio_sha256,
        "runner_sha256": runner_sha256,
        "harness_sha256": harness_sha256,
        "manifest_sha256": manifest_sha256,
        "fingerprints_sha256": fingerprints_sha256,
    }
    if partial.exists():
        result = load_json(partial)
        if any(result.get(key) != value for key, value in commitment.items()):
            raise RuntimeError(f"{case['case_id']}: partial commitment differs")
        return result

    decoder = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            str(START_SECONDS),
            "-t",
            str(DURATION_SECONDS),
            "-i",
            str(source),
            "-map_metadata",
            "-1",
            "-ac",
            "1",
            "-ar",
            "44100",
            "-c:a",
            "pcm_f32le",
            "-f",
            "f32le",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert decoder.stdout is not None
    probe = subprocess.run(
        [str(runner), case["case_id"]],
        check=False,
        stdin=decoder.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )
    decoder.stdout.close()
    decoder_stderr = decoder.stderr.read() if decoder.stderr else b""
    decoder_returncode = decoder.wait()
    if decoder_returncode:
        raise RuntimeError(
            f"{case['case_id']}: ffmpeg failed ({decoder_returncode}): "
            f"{decoder_stderr.decode(errors='replace').strip()}"
        )
    if probe.returncode:
        raise RuntimeError(
            f"{case['case_id']}: probe failed ({probe.returncode}): "
            f"{probe.stderr.decode(errors='replace').strip()}"
        )
    try:
        measured = json.loads(probe.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"{case['case_id']}: invalid probe JSON: {error}"
        ) from error
    if (
        measured.get("schema_version") != 1
        or measured.get("case_id") != case["case_id"]
        or measured.get("algorithm") != ALGORITHM
    ):
        raise RuntimeError(f"{case['case_id']}: probe contract differs")
    result = {
        **commitment,
        "class": case["class"],
        "expectation": case["expectation"],
        "source_group": case["source_group"],
        "partition_group": case["partition_group"],
        "provenance_tier": case["provenance_tier"],
        "probe": measured,
    }
    write_atomic(partial, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--fingerprints", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--include-class-regex",
        default=".*",
        help="full-match regex for class names (default: all)",
    )
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        raise SystemExit("--jobs must be in 1..=8")
    try:
        include_class = re.compile(args.include_class_regex)
    except re.error as error:
        raise SystemExit(f"invalid --include-class-regex: {error}") from error

    output = args.output.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit(f"refusing to replace report: {output}")
    partial_root = Path(f"{output}.partial")
    partial_root.mkdir(parents=True, exist_ok=True)
    manifest_path = args.manifest.expanduser().resolve()
    fingerprints_path = args.fingerprints.expanduser().resolve()
    audio_root = args.audio_root.expanduser().resolve()
    runner = args.runner.expanduser().resolve()
    harness = Path(__file__).resolve()
    for required in (manifest_path, fingerprints_path, runner, harness):
        if not required.is_file():
            raise SystemExit(f"required file missing: {required}")
    manifest = load_json(manifest_path)
    fingerprints = load_json(fingerprints_path)
    cases = manifest.get("cases")
    fingerprint_map = fingerprints.get("case_sha256")
    if (
        not isinstance(cases, list)
        or not isinstance(fingerprint_map, dict)
        or manifest.get("corpus_id") != fingerprints.get("corpus_id")
    ):
        raise SystemExit("manifest/fingerprint contract differs")
    case_ids = [case.get("case_id") for case in cases]
    if (
        any(not isinstance(case_id, str) or not case_id for case_id in case_ids)
        or len(case_ids) != len(set(case_ids))
    ):
        raise SystemExit("manifest case IDs are missing or not unique")

    selected = [
        case for case in cases if include_class.fullmatch(case["class"])
    ]
    if not selected:
        raise SystemExit("class selection is empty")
    runner_sha256 = sha256_file(runner)
    harness_sha256 = sha256_file(harness)
    manifest_sha256 = sha256_file(manifest_path)
    fingerprints_sha256 = sha256_file(fingerprints_path)

    def submit(case: dict) -> dict:
        case_id = case["case_id"]
        source = (audio_root / case["relative_path"]).resolve()
        if audio_root not in source.parents or not source.is_file():
            raise RuntimeError(f"{case_id}: invalid audio path")
        audio_sha256 = fingerprint_map.get(case_id)
        if not isinstance(audio_sha256, str):
            raise RuntimeError(f"{case_id}: missing fingerprint")
        if sha256_file(source) != audio_sha256:
            raise RuntimeError(f"{case_id}: audio fingerprint differs")
        return run_case(
            case=case,
            source=source,
            audio_sha256=audio_sha256,
            runner=runner,
            runner_sha256=runner_sha256,
            harness_sha256=harness_sha256,
            manifest_sha256=manifest_sha256,
            fingerprints_sha256=fingerprints_sha256,
            partial=partial_root / f"{case_id}.json",
        )

    results = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.jobs
    ) as executor:
        futures = {
            executor.submit(submit, case): case for case in selected
        }
        for index, future in enumerate(
            concurrent.futures.as_completed(futures), start=1
        ):
            result = future.result()
            results.append(result)
            print(
                f"[{index:04d}/{len(selected):04d}] {result['case_id']}",
                flush=True,
            )

    ffmpeg_version = subprocess.run(
        ["ffmpeg", "-version"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.splitlines()[0]
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": "consumed_development_exact_mp3_hybrid_probe",
        "candidate_frozen": False,
        "new_external_transfer_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "warning": (
            "Measurements on consumed development evidence. This report is "
            "not fresh gate evidence and does not authorize a public verdict."
        ),
        "measurement": {
            "start_seconds": START_SECONDS,
            "duration_seconds": DURATION_SECONDS,
            "sample_rate_hz": 44_100,
            "analysis_channel_count": 1,
            "ffmpeg_version": ffmpeg_version,
        },
        "selection": {
            "include_class_fullmatch_regex": args.include_class_regex,
            "selected_classes": sorted({case["class"] for case in selected}),
            "source_groups": sorted(
                {case["source_group"] for case in selected}
            ),
        },
        "inputs": {
            "manifest": {
                "path": str(manifest_path),
                "sha256": manifest_sha256,
            },
            "fingerprints": {
                "path": str(fingerprints_path),
                "sha256": fingerprints_sha256,
            },
            "audio_root": str(audio_root),
            "runner": {
                "path": str(runner),
                "sha256": runner_sha256,
            },
            "harness": {
                "path": str(harness),
                "sha256": harness_sha256,
            },
        },
        "case_count": len(results),
        "results": sorted(results, key=lambda row: row["case_id"]),
    }
    write_atomic(output, report)
    print(
        json.dumps(
            {
                "output": str(output),
                "sha256": sha256_file(output),
                "source_group_count": len(report["selection"]["source_groups"]),
                "case_count": len(results),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
