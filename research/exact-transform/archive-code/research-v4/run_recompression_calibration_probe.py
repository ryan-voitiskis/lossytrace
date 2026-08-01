#!/usr/bin/env python3
"""Probe whether codec recompression stability reveals prior lossy history.

This is a consumed-data, development-only experiment. It does not freeze a
candidate, open a new transfer corpus, or enable any public verdict.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from array import array
from datetime import UTC, datetime
from pathlib import Path


PROFILE = {
    "mp3": {
        "classes": {
            "musdb_pcm_reference_wav16",
            "musdb_mp3_128_to_flac16",
        },
        "suffix": ".mp3",
        "arguments": ["-c:a", "libmp3lame", "-b:a", "128k"],
    },
    "aac": {
        "classes": {
            "musdb_pcm_reference_wav16",
            "musdb_aac_at_128_to_flac16",
            "musdb_aac_lc_128_to_flac16",
        },
        "suffix": ".m4a",
        "arguments": ["-c:a", "aac", "-b:a", "128k"],
    },
}
SAMPLE_RATE = 44_100
START_SECONDS = 5
DURATION_SECONDS = 10


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


def run(command: list[str], *, stdout: bool = False) -> bytes:
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE if stdout else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): "
            f"{completed.stderr.decode(errors='replace').strip()}"
        )
    return completed.stdout if stdout else b""


def decode_f32(path: Path, *, excerpt: bool) -> array:
    command = ["ffmpeg", "-v", "error"]
    if excerpt:
        command.extend(["-ss", str(START_SECONDS), "-t", str(DURATION_SECONDS)])
    command.extend(
        [
            "-i",
            str(path),
            "-map_metadata",
            "-1",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "pcm_f32le",
            "-f",
            "f32le",
            "pipe:1",
        ]
    )
    values = array("f")
    values.frombytes(run(command, stdout=True))
    if sys.byteorder != "little":
        values.byteswap()
    return values


def comparison(left: array, right: array) -> dict:
    count = min(len(left), len(right))
    if count < SAMPLE_RATE * (DURATION_SECONDS - 1):
        raise RuntimeError(f"unexpected decoded length: {len(left)}, {len(right)}")
    left_power = 0.0
    right_power = 0.0
    cross = 0.0
    error_power = 0.0
    delta_left_power = 0.0
    delta_error_power = 0.0
    previous_left = float(left[0])
    previous_right = float(right[0])
    chunk_samples = SAMPLE_RATE
    chunk_signal = 0.0
    chunk_error = 0.0
    chunk_count = 0
    chunk_snrs = []
    for index in range(count):
        x = float(left[index])
        y = float(right[index])
        error = x - y
        left_power += x * x
        right_power += y * y
        cross += x * y
        error_power += error * error
        chunk_signal += x * x
        chunk_error += error * error
        chunk_count += 1
        if index:
            delta_left = x - previous_left
            delta_error = error - (previous_left - previous_right)
            delta_left_power += delta_left * delta_left
            delta_error_power += delta_error * delta_error
        previous_left = x
        previous_right = y
        if chunk_count == chunk_samples:
            chunk_snrs.append(
                10.0
                * math.log10(
                    max(chunk_signal, 1e-30) / max(chunk_error, 1e-30)
                )
            )
            chunk_signal = 0.0
            chunk_error = 0.0
            chunk_count = 0
    denominator = math.sqrt(max(left_power * right_power, 1e-30))
    snr = 10.0 * math.log10(
        max(left_power, 1e-30) / max(error_power, 1e-30)
    )
    delta_snr = 10.0 * math.log10(
        max(delta_left_power, 1e-30) / max(delta_error_power, 1e-30)
    )
    chunk_snrs.sort()
    middle = len(chunk_snrs) // 2
    chunk_median = (
        chunk_snrs[middle]
        if len(chunk_snrs) % 2
        else (chunk_snrs[middle - 1] + chunk_snrs[middle]) / 2.0
    )
    return {
        "compared_sample_count": count,
        "left_sample_count": len(left),
        "right_sample_count": len(right),
        "left_rms": math.sqrt(left_power / count),
        "right_rms": math.sqrt(right_power / count),
        "residual_rms": math.sqrt(error_power / count),
        "waveform_snr_db": snr,
        "first_difference_snr_db": delta_snr,
        "correlation": cross / denominator,
        "one_second_snr_minimum_db": min(chunk_snrs),
        "one_second_snr_median_db": chunk_median,
        "one_second_snr_maximum_db": max(chunk_snrs),
    }


def calibrate(
    case: dict,
    source: Path,
    codec: str,
    partial: Path,
    *,
    harness_sha256: str,
    manifest_sha256: str,
    fingerprints_sha256: str,
) -> dict:
    if partial.exists():
        return load_json(partial)
    profile = PROFILE[codec]
    with tempfile.TemporaryDirectory(prefix="reklaw-calibration-") as directory:
        work = Path(directory)
        first = work / f"first{profile['suffix']}"
        second = work / f"second{profile['suffix']}"
        first_command = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            str(START_SECONDS),
            "-t",
            str(DURATION_SECONDS),
            "-i",
            str(source),
            "-map_metadata",
            "-1",
            "-ac",
            "2",
            "-ar",
            str(SAMPLE_RATE),
            *profile["arguments"],
            str(first),
        ]
        second_command = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(first),
            "-map_metadata",
            "-1",
            "-ac",
            "2",
            "-ar",
            str(SAMPLE_RATE),
            *profile["arguments"],
            str(second),
        ]
        run(first_command)
        run(second_command)
        original_pcm = decode_f32(source, excerpt=True)
        first_pcm = decode_f32(first, excerpt=False)
        second_pcm = decode_f32(second, excerpt=False)
        first_comparison = comparison(original_pcm, first_pcm)
        second_comparison = comparison(first_pcm, second_pcm)
        result = {
            "case_id": case["case_id"],
            "class": case["class"],
            "expectation": case["expectation"],
            "source_group": case["source_group"],
            "codec_probe": codec,
            "audio_sha256": sha256_file(source),
            "harness_sha256": harness_sha256,
            "manifest_sha256": manifest_sha256,
            "fingerprints_sha256": fingerprints_sha256,
            "first_generation": first_comparison,
            "second_generation": second_comparison,
            "calibration": {
                "waveform_snr_delta_db": (
                    second_comparison["waveform_snr_db"]
                    - first_comparison["waveform_snr_db"]
                ),
                "waveform_error_power_ratio": (
                    10.0
                    ** (
                        (
                            first_comparison["waveform_snr_db"]
                            - second_comparison["waveform_snr_db"]
                        )
                        / 10.0
                    )
                ),
                "first_difference_snr_delta_db": (
                    second_comparison["first_difference_snr_db"]
                    - first_comparison["first_difference_snr_db"]
                ),
            },
        }
        write_atomic(partial, result)
        return result


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--fingerprints", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-groups", type=int, default=12)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        raise SystemExit("--jobs must be in 1..=8")
    if not 1 <= args.source_groups <= 30:
        raise SystemExit("--source-groups must be in 1..=30")

    output = args.output.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit(f"refusing to replace report: {output}")
    partial_root = Path(f"{output}.partial")
    partial_root.mkdir(parents=True, exist_ok=True)
    manifest_path = args.manifest.expanduser().resolve()
    fingerprints_path = args.fingerprints.expanduser().resolve()
    audio_root = args.audio_root.expanduser().resolve()
    manifest = load_json(manifest_path)
    fingerprints = load_json(fingerprints_path)
    harness_sha256 = sha256_file(Path(__file__).resolve())
    manifest_sha256 = sha256_file(manifest_path)
    fingerprints_sha256 = sha256_file(fingerprints_path)
    cases = manifest.get("cases")
    fingerprint_map = fingerprints.get("case_sha256")
    if (
        not isinstance(cases, list)
        or not isinstance(fingerprint_map, dict)
        or manifest.get("corpus_id") != fingerprints.get("corpus_id")
    ):
        raise SystemExit("manifest/fingerprint contract differs")

    groups = selected_groups(cases, args.source_groups)
    selected = []
    for case in cases:
        if case["source_group"] not in groups:
            continue
        for codec, profile in PROFILE.items():
            if case["class"] in profile["classes"]:
                selected.append((case, codec))
    expected = args.source_groups * 5
    if len(selected) != expected:
        raise SystemExit(
            f"selected inventory differs: expected {expected}, "
            f"found {len(selected)}"
        )

    def run_selected(item: tuple[dict, str]) -> dict:
        case, codec = item
        case_id = case["case_id"]
        relative = case["relative_path"]
        source = (audio_root / relative).resolve()
        if audio_root not in source.parents or not source.is_file():
            raise RuntimeError(f"{case_id}: invalid audio path")
        expected_sha = fingerprint_map.get(case_id)
        if not isinstance(expected_sha, str):
            raise RuntimeError(f"{case_id}: missing fingerprint")
        actual_sha = sha256_file(source)
        if actual_sha != expected_sha:
            raise RuntimeError(f"{case_id}: audio fingerprint differs")
        partial = partial_root / f"{case_id}--{codec}.json"
        result = calibrate(
            case,
            source,
            codec,
            partial,
            harness_sha256=harness_sha256,
            manifest_sha256=manifest_sha256,
            fingerprints_sha256=fingerprints_sha256,
        )
        if (
            result.get("case_id") != case_id
            or result.get("codec_probe") != codec
            or result.get("audio_sha256") != expected_sha
            or result.get("harness_sha256") != harness_sha256
            or result.get("manifest_sha256") != manifest_sha256
            or result.get("fingerprints_sha256") != fingerprints_sha256
        ):
            raise RuntimeError(f"{case_id}/{codec}: partial contract differs")
        return result

    results = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.jobs
    ) as executor:
        futures = {
            executor.submit(run_selected, item): item for item in selected
        }
        for index, future in enumerate(
            concurrent.futures.as_completed(futures), start=1
        ):
            result = future.result()
            results.append(result)
            print(
                f"[{index:03d}/{len(selected):03d}] "
                f"{result['case_id']} {result['codec_probe']}",
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
        "state": "consumed_development_recompression_calibration_probe",
        "candidate_frozen": False,
        "new_external_transfer_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "warning": (
            "Exploratory measurements on consumed MUSDB data. Results may "
            "only select or reject a future candidate; they are not gate "
            "evidence."
        ),
        "probe": {
            "sample_rate_hz": SAMPLE_RATE,
            "start_seconds": START_SECONDS,
            "duration_seconds": DURATION_SECONDS,
            "encoder_channel_count": 2,
            "analysis_channel_count": 1,
            "profiles": {
                codec: {
                    **profile,
                    "classes": sorted(profile["classes"]),
                }
                for codec, profile in PROFILE.items()
            },
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
            "harness": {
                "path": str(Path(__file__).resolve()),
                "sha256": harness_sha256,
            },
        },
        "source_groups": groups,
        "case_count": len({result["case_id"] for result in results}),
        "probe_count": len(results),
        "results": sorted(
            results, key=lambda row: (row["case_id"], row["codec_probe"])
        ),
    }
    write_atomic(output, report)
    print(
        json.dumps(
            {
                "output": str(output),
                "sha256": sha256_file(output),
                "source_group_count": len(groups),
                "case_count": report["case_count"],
                "probe_count": report["probe_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
