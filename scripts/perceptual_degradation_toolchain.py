#!/usr/bin/env python3
"""Bind and probe score-free decoder/resampler views for the perceptual oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FFMPEG_TOOL_ID = "ffmpeg_8_1_2_1"
FFMPEG_SHA256 = "1332dc2de372bade9a8a63da0d6cdfab9de97fcefbae707bcc0b0506e1203327"
FFPROBE_TOOL_ID = "ffprobe_8_1_2_1"
FFPROBE_SHA256 = "4322275c1c2ac6ba15c695b288788bc1204e75211b3d5c030e5812c82a6dff73"
SOURCE_RATE_HZ = 44100
TARGET_RATE_HZ = 48000
CHANNEL_COUNT = 2
FIXTURE_SECONDS = 2
MINIMUM_FREE_DISK_GIB = 15
RESAMPLE_FILTER = (
    "aresample=48000:osf=dbl:resampler=swr:filter_size=64:phase_shift=10:"
    "linear_interp=0:exact_rational=1:cutoff=0.95:filter_type=kaiser:"
    "kaiser_beta=9:dither_method=none"
)
DECODE_TEMPLATE = [
    f"<TOOL:{FFMPEG_TOOL_ID}>",
    "-hide_banner",
    "-loglevel",
    "error",
    "-nostdin",
    "-fflags",
    "+bitexact",
    "-i",
    "<INPUT>",
    "-map",
    "0:a:0",
    "-c:a",
    "pcm_f64le",
    "-f",
    "f64le",
    "-fflags",
    "+bitexact",
    "pipe:1",
]
RESAMPLE_TEMPLATE = [
    *DECODE_TEMPLATE[: DECODE_TEMPLATE.index("-c:a")],
    "-af",
    RESAMPLE_FILTER,
    *DECODE_TEMPLATE[DECODE_TEMPLATE.index("-c:a") :],
]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def process_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {"LC_ALL": "C", "LANG": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "0"}
    )
    return environment


def resolve_bound_executable(value: str, expected_sha256: str) -> Path:
    candidate = shutil.which(value)
    if candidate is None:
        raise ValueError(f"required executable is unavailable: {value}")
    path = Path(candidate).resolve()
    observed = sha256_file(path)
    if observed != expected_sha256:
        raise ValueError(
            f"executable binding differs for {path.name}: expected {expected_sha256}, observed {observed}"
        )
    return path


def _write_fixture(path: Path) -> str:
    encoded = bytearray()
    for frame in range(SOURCE_RATE_HZ * FIXTURE_SECONDS):
        time = frame / SOURCE_RATE_HZ
        envelope = 0.25 + 0.75 * ((frame // 509) % 11) / 10
        left = envelope * (
            0.62 * math.sin(2 * math.pi * 997 * time)
            + 0.38 * math.sin(2 * math.pi * 7331 * time + 0.1)
        )
        right = envelope * (
            0.57 * math.sin(2 * math.pi * 1423 * time + 0.3)
            + 0.43 * math.sin(2 * math.pi * 11003 * time + 0.2)
        )
        encoded.extend(
            struct.pack(
                "<hh",
                max(-32768, min(32767, round(left * 28000))),
                max(-32768, min(32767, round(right * 28000))),
            )
        )
    with wave.open(str(path), "wb") as output:
        output.setnchannels(CHANNEL_COUNT)
        output.setsampwidth(2)
        output.setframerate(SOURCE_RATE_HZ)
        output.writeframes(bytes(encoded))
    return sha256_bytes(bytes(encoded))


def _wrap_fixture_as_flac(ffmpeg: Path, wave_path: Path, flac_path: Path) -> None:
    subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-fflags",
            "+bitexact",
            "-i",
            str(wave_path),
            "-map",
            "0:a:0",
            "-c:a",
            "flac",
            "-compression_level",
            "5",
            "-flags:a",
            "+bitexact",
            "-fflags",
            "+bitexact",
            str(flac_path),
        ],
        check=True,
        capture_output=True,
        env=process_environment(),
    )


def _command(template: list[str], tool: Path, source: Path) -> list[str]:
    return [str(tool) if token.startswith("<TOOL:") else str(source) if token == "<INPUT>" else token for token in template]


def _run_bytes(command: list[str]) -> bytes:
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        env=process_environment(),
    )
    if completed.stderr:
        raise ValueError("bound FFmpeg wrote unexpected stderr")
    return completed.stdout


def _probe_stream(ffprobe: Path, source: Path) -> dict[str, Any]:
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate,channels,channel_layout",
        "-of",
        "json",
        str(source),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=process_environment(),
    )
    parsed = json.loads(completed.stdout)
    streams = parsed.get("streams", [])
    if len(streams) != 1:
        raise ValueError("synthetic fixture audio stream count differs")
    return streams[0]


def probe(ffmpeg_value: str = "ffmpeg", ffprobe_value: str = "ffprobe") -> dict[str, Any]:
    if shutil.disk_usage(ROOT).free < MINIMUM_FREE_DISK_GIB * 1024**3:
        raise ValueError("free disk reserve is below 15 GiB")
    ffmpeg = resolve_bound_executable(ffmpeg_value, FFMPEG_SHA256)
    ffprobe = resolve_bound_executable(ffprobe_value, FFPROBE_SHA256)
    ffmpeg_version = subprocess.run(
        [str(ffmpeg), "-version"],
        check=True,
        capture_output=True,
        text=True,
        env=process_environment(),
    ).stdout
    ffprobe_version = subprocess.run(
        [str(ffprobe), "-version"],
        check=True,
        capture_output=True,
        text=True,
        env=process_environment(),
    ).stdout
    with tempfile.TemporaryDirectory(prefix="lossytrace-perceptual-toolchain-") as temporary:
        wave_path = Path(temporary) / "fixture.wav"
        fixture_path = Path(temporary) / "fixture.flac"
        pcm_sha256 = _write_fixture(wave_path)
        _wrap_fixture_as_flac(ffmpeg, wave_path, fixture_path)
        stream = _probe_stream(ffprobe, fixture_path)
        native_first = _run_bytes(_command(DECODE_TEMPLATE, ffmpeg, fixture_path))
        native_second = _run_bytes(_command(DECODE_TEMPLATE, ffmpeg, fixture_path))
        resampled_first = _run_bytes(_command(RESAMPLE_TEMPLATE, ffmpeg, fixture_path))
        resampled_second = _run_bytes(_command(RESAMPLE_TEMPLATE, ffmpeg, fixture_path))

    expected_native_bytes = SOURCE_RATE_HZ * FIXTURE_SECONDS * CHANNEL_COUNT * 8
    if native_first != native_second or len(native_first) != expected_native_bytes:
        raise ValueError("native float64 decoder replay differs")
    if resampled_first != resampled_second or len(resampled_first) % (CHANNEL_COUNT * 8):
        raise ValueError("48 kHz float64 resampler replay differs")
    resampled_frames = len(resampled_first) // (CHANNEL_COUNT * 8)
    if resampled_frames != TARGET_RATE_HZ * FIXTURE_SECONDS:
        raise ValueError("48 kHz resampler frame count differs")
    expected_stream = {
        "sample_rate": str(SOURCE_RATE_HZ),
        "channels": CHANNEL_COUNT,
        "channel_layout": "stereo",
    }
    if stream != expected_stream:
        raise ValueError(f"synthetic fixture stream metadata differs: {stream}")

    return {
        "schema_version": 1,
        "record_kind": "perceptual_degradation_audio_view_probe",
        "state": "score_free_decoder_and_resampler_replay_passed",
        "perceptual_metric_executed": False,
        "retained_audio_accessed": False,
        "scores_opened": False,
        "sealed_labels_opened": False,
        "public_verdict_enabled": False,
        "disk_reserve_gib_required": MINIMUM_FREE_DISK_GIB,
        "tools": {
            FFMPEG_TOOL_ID: {
                "binary_sha256": FFMPEG_SHA256,
                "version_output_sha256": sha256_bytes(ffmpeg_version.encode()),
            },
            FFPROBE_TOOL_ID: {
                "binary_sha256": FFPROBE_SHA256,
                "version_output_sha256": sha256_bytes(ffprobe_version.encode()),
            },
        },
        "fixture": {
            "container": "flac",
            "sample_rate_hz": SOURCE_RATE_HZ,
            "channel_count": CHANNEL_COUNT,
            "channel_map": ["L", "R"],
            "frames": SOURCE_RATE_HZ * FIXTURE_SECONDS,
            "pcm_sha256": pcm_sha256,
        },
        "native_view": {
            "command": DECODE_TEMPLATE,
            "sample_rate_hz": SOURCE_RATE_HZ,
            "channel_count": CHANNEL_COUNT,
            "frames": SOURCE_RATE_HZ * FIXTURE_SECONDS,
            "f64le_sha256": sha256_bytes(native_first),
            "complete_replays": 2,
            "byte_identical": True,
        },
        "visqol_48k_view": {
            "command": RESAMPLE_TEMPLATE,
            "sample_rate_hz": TARGET_RATE_HZ,
            "channel_count": CHANNEL_COUNT,
            "frames": resampled_frames,
            "f64le_sha256": sha256_bytes(resampled_first),
            "complete_replays": 2,
            "byte_identical": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = probe(args.ffmpeg, args.ffprobe)
    encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"wrote score-free audio-view probe to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
