#!/usr/bin/env python3
"""Generate small deterministic 48 kHz PCM fixtures for ViSQOL replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import wave
from pathlib import Path
from typing import Callable


SAMPLE_RATE_HZ = 48_000
CHANNEL_COUNT = 2
SAMPLE_WIDTH_BYTES = 2
DURATION_SECONDS = 8
FRAME_COUNT = SAMPLE_RATE_HZ * DURATION_SECONDS
FADE_FRAMES = SAMPLE_RATE_HZ // 4
MINIMUM_FREE_DISK_GIB = 15
FILE_NAMES = (
    "synthetic-reference.wav",
    "synthetic-bandwidth-loss.wav",
    "synthetic-tonal-noise.wav",
    "synthetic-transient-smear.wav",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _triangle(frame: int, period: int, amplitude: int, offset: int = 0) -> int:
    phase = (frame + offset) % period
    distance = phase if phase <= period // 2 else period - phase
    return (4 * amplitude * distance) // period - amplitude


def _square(frame: int, period: int, amplitude: int, offset: int = 0) -> int:
    return amplitude if (frame + offset) % period < period // 2 else -amplitude


def _fade(sample: int, frame: int) -> int:
    edge = min(frame, FRAME_COUNT - 1 - frame, FADE_FRAMES)
    if edge >= FADE_FRAMES:
        return sample
    return sample * max(0, edge) // FADE_FRAMES


def _reference_components(frame: int, channel: int) -> tuple[int, int, int]:
    offset = channel * 3
    low = _triangle(frame, 128, 7_400, offset) + _triangle(
        frame, 32, 3_600, offset
    )
    high = _triangle(frame, 8, 2_200, offset) + _triangle(
        frame, 4, 1_300, offset
    )
    local = frame % 12_000
    transient = (7_200 * (240 - local) // 240) if local < 240 else 0
    if channel == 1 and (frame // 12_000) % 2:
        transient = -transient
    return low, high, transient


def _reference(frame: int, channel: int) -> int:
    low, high, transient = _reference_components(frame, channel)
    return _fade(low + high + transient, frame)


def _bandwidth_loss(frame: int, channel: int) -> int:
    low, _, _ = _reference_components(frame, channel)
    return _fade(low, frame)


def _tonal_noise(frame: int, channel: int) -> int:
    gate = 1 if frame % 9_600 < 4_800 else 0
    added = gate * _square(frame, 7, 2_900, channel)
    return _fade(_reference(frame, channel) + added, frame)


def _transient_smear(frame: int, channel: int) -> int:
    low, high, _ = _reference_components(frame, channel)
    local = frame % 12_000
    distance = abs(local - 240)
    smear = (3_800 * (720 - distance) // 720) if distance < 720 else 0
    if channel == 1 and (frame // 12_000) % 2:
        smear = -smear
    return _fade(low + high + smear, frame)


def _write_wave(path: Path, sampler: Callable[[int, int], int]) -> None:
    encoded = bytearray()
    for frame in range(FRAME_COUNT):
        for channel in range(CHANNEL_COUNT):
            sample = max(-32_768, min(32_767, sampler(frame, channel)))
            encoded.extend(struct.pack("<h", sample))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(CHANNEL_COUNT)
        output.setsampwidth(SAMPLE_WIDTH_BYTES)
        output.setframerate(SAMPLE_RATE_HZ)
        output.writeframes(encoded)


def generate(output_dir: Path) -> dict[str, object]:
    estimated_bytes = len(FILE_NAMES) * FRAME_COUNT * CHANNEL_COUNT * SAMPLE_WIDTH_BYTES
    free_bytes = shutil.disk_usage(output_dir.parent).free
    if free_bytes - estimated_bytes < MINIMUM_FREE_DISK_GIB * 1024**3:
        raise ValueError("fixture generation would cross the 15 GiB disk reserve")
    output_dir.mkdir(parents=True, exist_ok=True)
    samplers = {
        "synthetic-reference.wav": _reference,
        "synthetic-bandwidth-loss.wav": _bandwidth_loss,
        "synthetic-tonal-noise.wav": _tonal_noise,
        "synthetic-transient-smear.wav": _transient_smear,
    }
    files = {}
    for name, sampler in samplers.items():
        path = output_dir / name
        if path.exists() or path.is_symlink():
            raise ValueError(f"refusing to replace fixture: {name}")
        _write_wave(path, sampler)
        files[name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return {
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "channel_count": CHANNEL_COUNT,
        "channel_map": "L_R",
        "sample_width_bits": SAMPLE_WIDTH_BYTES * 8,
        "duration_seconds": DURATION_SECONDS,
        "frames": FRAME_COUNT,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "schema_version": 1,
        "state": "synthetic_pcm_generated_without_metric_scores",
        "fixture_generation": generate(args.output_dir),
        "perceptual_metric_executed": False,
        "retained_audio_accessed": False,
        "scores_opened": False,
        "public_verdict_enabled": False,
        "paths_included": False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
