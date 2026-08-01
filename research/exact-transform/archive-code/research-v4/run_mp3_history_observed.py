#!/usr/bin/env python3
"""Run the exact MP3 hybrid-transform history probe on consumed audio."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path


SELECTED_CLASSES = {
    "musdb_pcm_reference_wav16",
    "musdb_pcm_sharp_lowpass_16000_flac16",
    "musdb_pcm_lowpass_19000_flac16",
    "musdb_pcm_resample_32000_44100_flac16",
    "musdb_mp3_128_to_flac16",
    "musdb_mp3_320_to_flac16",
    "musdb_aac_at_128_to_flac16",
    "musdb_aac_lc_128_to_flac16",
    "musdb_opus_96_to_flac16",
    "musdb_vorbis_native_q3_to_flac16",
}
START_SECONDS = 5
DURATION_SECONDS = 20


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


def selected_groups(cases: list[dict], count: int) -> list[str]:
    groups = sorted({case["source_group"] for case in cases})
    if count > len(groups):
        raise SystemExit("--source-groups exceeds corpus inventory")
    if count == 1:
        return [groups[len(groups) // 2]]
    indices = [
        round(position * (len(groups) - 1) / (count - 1))
        for position in range(count)
    ]
    return [groups[index] for index in indices]


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
        or measured.get("algorithm")
        != "iso11172_3_polyphase_analysis_plus_long_hybrid_mdct"
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
    parser.add_argument("--source-groups", type=int, default=24)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        raise SystemExit("--jobs must be in 1..=8")
    if not 1 <= args.source_groups <= 150:
        raise SystemExit("--source-groups must be in 1..=150")

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

    groups = selected_groups(cases, args.source_groups)
    selected = [
        case
        for case in cases
        if case["source_group"] in groups
        and case["class"] in SELECTED_CLASSES
    ]
    expected = args.source_groups * len(SELECTED_CLASSES)
    if len(selected) != expected:
        raise SystemExit(
            f"selected inventory differs: expected {expected}, "
            f"found {len(selected)}"
        )
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
                f"[{index:03d}/{len(selected):03d}] {result['case_id']}",
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
            "Exploratory measurements on consumed MUSDB evidence. No "
            "threshold is frozen and these results are not gate evidence."
        ),
        "measurement": {
            "start_seconds": START_SECONDS,
            "duration_seconds": DURATION_SECONDS,
            "sample_rate_hz": 44_100,
            "analysis_channel_count": 1,
            "ffmpeg_version": ffmpeg_version,
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
        "selected_classes": sorted(SELECTED_CLASSES),
        "source_groups": groups,
        "case_count": len(results),
        "results": sorted(results, key=lambda row: row["case_id"]),
    }
    write_atomic(output, report)
    print(
        json.dumps(
            {
                "output": str(output),
                "sha256": sha256_file(output),
                "source_group_count": len(groups),
                "case_count": len(results),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
