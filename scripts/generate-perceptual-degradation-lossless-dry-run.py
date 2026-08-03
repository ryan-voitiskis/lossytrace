#!/usr/bin/env python3
"""Generate one bounded private PCM-WAV qualification fixture and delivery map."""

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


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_RATE_HZ = 48000
DURATION_SECONDS = 4
CHANNEL_COUNT = 2
BIT_DEPTH = 16
STIMULUS_ID = "stimulus-private-dryrun-0001"
MANIFEST_ID = "manifest-private-dryrun-0001"


def _inside_repo(path: Path) -> bool:
    try:
        path.relative_to(ROOT)
    except ValueError:
        return False
    return True


def _sample(frame: int, channel: int) -> int:
    time = frame / SAMPLE_RATE_HZ
    primary = 220 if channel == 0 else 330
    overtone = 660 if channel == 0 else 990
    pulse = 1.0 if int(time * 4) % 2 == channel else 0.35
    value = pulse * (
        0.19 * math.sin(2 * math.pi * primary * time)
        + 0.055 * math.sin(2 * math.pi * overtone * time + channel * 0.31)
    )
    return max(-32768, min(32767, round(value * 32767)))


def generate(output_dir: Path) -> dict[str, object]:
    destination = output_dir.resolve(strict=True)
    if _inside_repo(destination):
        raise ValueError("dry-run output directory must remain outside the repository")
    if not destination.is_dir():
        raise ValueError("dry-run output destination must be a directory")
    audio_path = destination / "qualification.wav"
    map_path = destination / "delivery-map.json"
    if audio_path.exists() or map_path.exists():
        raise ValueError("dry-run outputs already exist")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix="qualification-", suffix=".wav.tmp", dir=destination
    )
    os.close(descriptor)
    temporary_audio = Path(temporary_name)
    try:
        with wave.open(str(temporary_audio), "wb") as output:
            output.setnchannels(CHANNEL_COUNT)
            output.setsampwidth(BIT_DEPTH // 8)
            output.setframerate(SAMPLE_RATE_HZ)
            for start in range(0, SAMPLE_RATE_HZ * DURATION_SECONDS, 1024):
                end = min(start + 1024, SAMPLE_RATE_HZ * DURATION_SECONDS)
                payload = bytearray()
                for frame in range(start, end):
                    payload.extend(
                        struct.pack(
                            "<hh", _sample(frame, 0), _sample(frame, 1)
                        )
                    )
                output.writeframesraw(payload)
        temporary_audio.replace(audio_path)
    finally:
        temporary_audio.unlink(missing_ok=True)

    audio_sha256 = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    delivery_map = {
        "schema_version": 1,
        "state": "private_lossless_delivery_qualification_only",
        "manifest_id": MANIFEST_ID,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "human_collection_authorized": False,
        "stimuli": [
            {
                "stimulus_id": STIMULUS_ID,
                "private_audio_path": str(audio_path),
                "private_audio_sha256": audio_sha256,
                "container": "wav",
                "sample_rate_hz": SAMPLE_RATE_HZ,
                "channel_count": CHANNEL_COUNT,
                "bit_depth": BIT_DEPTH,
            }
        ],
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
        "state": "ephemeral_lossless_qualification_fixture_generated",
        "manifest_id": MANIFEST_ID,
        "stimulus_id": STIMULUS_ID,
        "audio_sha256": audio_sha256,
        "audio_byte_length": audio_path.stat().st_size,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "channel_count": CHANNEL_COUNT,
        "bit_depth": BIT_DEPTH,
        "duration_seconds": DURATION_SECONDS,
        "private_path_printed": False,
        "human_collection_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = generate(args.output_dir)
    except OSError:
        parser.error("private dry-run outputs could not be created")
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
