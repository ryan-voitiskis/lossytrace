#!/usr/bin/env python3
"""Generate private, synthetic 48 kHz playback-qualification fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import struct
import tempfile
import wave
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_RATE_HZ = 48_000
CHANNEL_COUNT = 2
BIT_DEPTH = 16
CHANNEL_DURATION_SECONDS = 6
LEVEL_DURATION_SECONDS = 20
CHANNEL_PEAK_DBFS = -30.0
LEVEL_RMS_DBFS = -30.0
MANIFEST_ID = "manifest-playback-qualification-0001"


def _inside_repo(path: Path) -> bool:
    try:
        path.relative_to(ROOT)
    except ValueError:
        return False
    return True


def _pcm16(value: float) -> int:
    return max(-32768, min(32767, round(value * 32767)))


def _fade(frame: int, total_frames: int, fade_frames: int) -> float:
    if frame < fade_frames:
        return 0.5 - 0.5 * math.cos(math.pi * frame / fade_frames)
    remaining = total_frames - 1 - frame
    if remaining < fade_frames:
        return 0.5 - 0.5 * math.cos(math.pi * remaining / fade_frames)
    return 1.0


def _channel_sample(frame: int, channel: int) -> float:
    time = frame / SAMPLE_RATE_HZ
    amplitude = 10 ** (CHANNEL_PEAK_DBFS / 20)
    frequency = 440.0 if channel == 0 else 660.0
    total = SAMPLE_RATE_HZ * CHANNEL_DURATION_SECONDS
    return amplitude * _fade(frame, total, SAMPLE_RATE_HZ // 4) * math.sin(
        2 * math.pi * frequency * time
    )


def _level_sample(frame: int, _channel: int) -> float:
    time = frame / SAMPLE_RATE_HZ
    frequencies = (500.0, 1000.0, 2000.0)
    weights = (1.0, 2**-0.5, 0.5)
    phases = (0.0, 0.37, 1.11)
    raw_rms = math.sqrt(sum(weight * weight for weight in weights) / 2)
    scale = 10 ** (LEVEL_RMS_DBFS / 20) / raw_rms
    value = sum(
        weight * math.sin(2 * math.pi * frequency * time + phase)
        for frequency, weight, phase in zip(frequencies, weights, phases, strict=True)
    )
    total = SAMPLE_RATE_HZ * LEVEL_DURATION_SECONDS
    return scale * _fade(frame, total, SAMPLE_RATE_HZ // 2) * value


def _write_wav(
    destination: Path,
    duration_seconds: int,
    sample: Callable[[int, int], float],
) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f"{destination.stem}-", suffix=".wav.tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with wave.open(str(temporary), "wb") as output:
            output.setnchannels(CHANNEL_COUNT)
            output.setsampwidth(BIT_DEPTH // 8)
            output.setframerate(SAMPLE_RATE_HZ)
            total_frames = SAMPLE_RATE_HZ * duration_seconds
            for start in range(0, total_frames, 1024):
                payload = bytearray()
                for frame in range(start, min(start + 1024, total_frames)):
                    payload.extend(
                        struct.pack(
                            "<hh", _pcm16(sample(frame, 0)), _pcm16(sample(frame, 1))
                        )
                    )
                output.writeframesraw(payload)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(output_dir: Path) -> dict[str, object]:
    destination = output_dir.resolve(strict=True)
    if _inside_repo(destination) or not destination.is_dir():
        raise ValueError("qualification output must be an existing private directory")
    specifications = (
        (
            "channel-check-0001",
            destination / "channel-check.wav",
            CHANNEL_DURATION_SECONDS,
            _channel_sample,
        ),
        (
            "level-calibration-0001",
            destination / "level-calibration.wav",
            LEVEL_DURATION_SECONDS,
            _level_sample,
        ),
    )
    map_path = destination / "delivery-map.json"
    if map_path.exists() or any(path.exists() for _, path, _, _ in specifications):
        raise ValueError("qualification outputs already exist")
    rows = []
    for stimulus_id, path, duration, sample in specifications:
        _write_wav(path, duration, sample)
        rows.append(
            {
                "stimulus_id": stimulus_id,
                "private_audio_path": str(path),
                "private_audio_sha256": _sha256(path),
                "container": "wav",
                "sample_rate_hz": SAMPLE_RATE_HZ,
                "channel_count": CHANNEL_COUNT,
                "bit_depth": BIT_DEPTH,
            }
        )
    delivery_map = {
        "schema_version": 1,
        "state": "private_lossless_delivery_qualification_only",
        "manifest_id": MANIFEST_ID,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "human_collection_authorized": False,
        "stimuli": rows,
    }
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="delivery-map-", suffix=".json.tmp", dir=destination
    )
    os.close(descriptor)
    temporary_map = Path(temporary_name)
    try:
        temporary_map.write_text(
            json.dumps(delivery_map, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary_map.replace(map_path)
    finally:
        temporary_map.unlink(missing_ok=True)
    return {
        "schema_version": 1,
        "state": "synthetic_playback_qualification_generated",
        "manifest_id": MANIFEST_ID,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "channel_count": CHANNEL_COUNT,
        "bit_depth": BIT_DEPTH,
        "channel_duration_seconds": CHANNEL_DURATION_SECONDS,
        "channel_peak_dbfs": CHANNEL_PEAK_DBFS,
        "level_duration_seconds": LEVEL_DURATION_SECONDS,
        "level_steady_state_rms_dbfs": LEVEL_RMS_DBFS,
        "stimuli": [
            {
                "stimulus_id": row["stimulus_id"],
                "sha256": row["private_audio_sha256"],
                "byte_length": Path(row["private_audio_path"]).stat().st_size,
            }
            for row in rows
        ],
        "private_paths_printed": False,
        "human_collection_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = generate(args.output_dir)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
