#!/usr/bin/env python3
"""Deterministic source-to-paired-s16 preconditioning for audio-integrity v2."""

from __future__ import annotations

import hashlib
import math
import os
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import BinaryIO


EXCERPT_OFFSET_PREFIX = "lossytrace-v2-reference-excerpt-offset-20260802\0"
MAXIMUM_EXCERPT_SECONDS = 12
SUPPORTED_CHANNEL_TREATMENTS = {"mono": 1, "stereo": 2}


def process_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {"LC_ALL": "C", "LANG": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "0"}
    )
    return environment


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def round_ratio_ties_even(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    doubled = remainder * 2
    if doubled > denominator or (doubled == denominator and quotient % 2 == 1):
        quotient += 1
    return sign * quotient


def saturate_s16(value: int) -> int:
    return max(-32768, min(32767, value))


def quantize_f64_to_s16(value: float) -> int:
    if not math.isfinite(value):
        raise ValueError("decoded sample is not finite")
    numerator, denominator = value.as_integer_ratio()
    return saturate_s16(round_ratio_ties_even(numerator * 32768, denominator))


def identity_hashed_excerpt_bounds(
    *,
    group_id: str,
    member_id: str,
    provider_start_frame: int,
    provider_end_frame_exclusive: int,
    native_sample_rate_hz: int,
) -> tuple[int, int]:
    if (
        not group_id
        or not member_id
        or provider_start_frame < 0
        or provider_end_frame_exclusive <= provider_start_frame
        or native_sample_rate_hz < 1
    ):
        raise ValueError("excerpt identity or provider window differs")
    maximum_frames = MAXIMUM_EXCERPT_SECONDS * native_sample_rate_hz
    available_frames = provider_end_frame_exclusive - provider_start_frame
    if available_frames <= maximum_frames:
        return provider_start_frame, provider_end_frame_exclusive
    available_native_frame_starts = available_frames - maximum_frames
    payload = (
        EXCERPT_OFFSET_PREFIX.encode()
        + group_id.encode()
        + b"\0"
        + member_id.encode()
    )
    rank = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    start = provider_start_frame + rank % (available_native_frame_starts + 1)
    return start, start + maximum_frames


def resample_filter(target_sample_rate_hz: int) -> str:
    if target_sample_rate_hz not in (44100, 48000):
        raise ValueError("target sample rate differs")
    return (
        f"aresample={target_sample_rate_hz}:osf=dbl:resampler=swr:"
        "filter_size=64:phase_shift=10:linear_interp=0:exact_rational=1:"
        "cutoff=0.95:filter_type=kaiser:kaiser_beta=9:dither_method=none"
    )


def preconditioning_filter_graph(
    *,
    excerpt_start_frame: int,
    excerpt_end_frame_exclusive: int,
    native_channel_count: int,
    native_sample_rate_hz: int,
    channel_treatment_id: str,
    target_sample_rate_hz: int,
) -> str:
    output_channels = SUPPORTED_CHANNEL_TREATMENTS.get(channel_treatment_id)
    if (
        native_channel_count not in (1, 2)
        or output_channels is None
        or native_sample_rate_hz < 1
        or excerpt_start_frame < 0
        or excerpt_end_frame_exclusive <= excerpt_start_frame
    ):
        raise ValueError("preconditioning factor differs")
    filters = [
        (
            f"atrim=start_sample={excerpt_start_frame}:"
            f"end_sample={excerpt_end_frame_exclusive}"
        ),
        "asetpts=PTS-STARTPTS",
        "aformat=sample_fmts=dbl",
    ]
    if native_channel_count == 2 and output_channels == 1:
        filters.append("pan=mono|c0=0.5*c0+0.5*c1")
    elif native_channel_count == 1 and output_channels == 2:
        filters.append("pan=stereo|c0=c0|c1=c0")
    if native_sample_rate_hz != target_sample_rate_hz:
        filters.append(resample_filter(target_sample_rate_hz))
    return ",".join(filters)


def ffmpeg_preconditioning_command(
    *, ffmpeg: Path, input_path: Path, filter_graph: str
) -> list[str]:
    return [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-fflags",
        "+bitexact",
        "-i",
        str(input_path),
        "-map",
        "0:a:0",
        "-af",
        filter_graph,
        "-c:a",
        "pcm_f64le",
        "-f",
        "f64le",
        "-fflags",
        "+bitexact",
        "pipe:1",
    ]


def _convert_f64_stream_to_wave(
    source: BinaryIO,
    output_path: Path,
    *,
    sample_rate_hz: int,
    channel_count: int,
) -> tuple[int, str]:
    pcm_digest = hashlib.sha256()
    sample_count = 0
    remainder = b""
    with wave.open(str(output_path), "wb") as output:
        output.setnchannels(channel_count)
        output.setsampwidth(2)
        output.setframerate(sample_rate_hz)
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            data = remainder + chunk
            complete = len(data) - len(data) % 8
            remainder = data[complete:]
            if not complete:
                continue
            values = struct.unpack(f"<{complete // 8}d", data[:complete])
            quantized = [quantize_f64_to_s16(value) for value in values]
            encoded = struct.pack(f"<{len(quantized)}h", *quantized)
            output.writeframesraw(encoded)
            pcm_digest.update(encoded)
            sample_count += len(quantized)
    if remainder or sample_count == 0 or sample_count % channel_count:
        raise ValueError("preconditioned f64 stream shape differs")
    return sample_count // channel_count, pcm_digest.hexdigest()


def precondition_to_wave(
    *,
    ffmpeg: Path,
    input_path: Path,
    output_path: Path,
    group_id: str,
    member_id: str,
    provider_start_frame: int,
    provider_end_frame_exclusive: int,
    native_sample_rate_hz: int,
    native_channel_count: int,
    channel_treatment_id: str,
    target_sample_rate_hz: int,
) -> dict[str, int | str]:
    excerpt_start, excerpt_end = identity_hashed_excerpt_bounds(
        group_id=group_id,
        member_id=member_id,
        provider_start_frame=provider_start_frame,
        provider_end_frame_exclusive=provider_end_frame_exclusive,
        native_sample_rate_hz=native_sample_rate_hz,
    )
    filter_graph = preconditioning_filter_graph(
        excerpt_start_frame=excerpt_start,
        excerpt_end_frame_exclusive=excerpt_end,
        native_channel_count=native_channel_count,
        native_sample_rate_hz=native_sample_rate_hz,
        channel_treatment_id=channel_treatment_id,
        target_sample_rate_hz=target_sample_rate_hz,
    )
    command = ffmpeg_preconditioning_command(
        ffmpeg=ffmpeg, input_path=input_path, filter_graph=filter_graph
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile() as error_output:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=error_output,
            env=process_environment(),
        )
        if process.stdout is None:
            process.kill()
            raise RuntimeError("FFmpeg stdout pipe is absent")
        try:
            frame_count, pcm_sha256 = _convert_f64_stream_to_wave(
                process.stdout,
                output_path,
                sample_rate_hz=target_sample_rate_hz,
                channel_count=SUPPORTED_CHANNEL_TREATMENTS[channel_treatment_id],
            )
        except BaseException:
            process.kill()
            process.wait()
            output_path.unlink(missing_ok=True)
            raise
        finally:
            process.stdout.close()
        return_code = process.wait(timeout=120)
        if return_code:
            error_output.seek(0)
            detail = error_output.read().decode(errors="replace").strip()[-500:]
            output_path.unlink(missing_ok=True)
            raise ValueError(
                f"FFmpeg preconditioning failed with exit {return_code}: {detail}"
            )
    return {
        "excerpt_start_native_frame": excerpt_start,
        "excerpt_end_native_frame_exclusive": excerpt_end,
        "output_sample_rate_hz": target_sample_rate_hz,
        "output_channel_count": SUPPORTED_CHANNEL_TREATMENTS[channel_treatment_id],
        "output_frame_count": frame_count,
        "pcm_sha256": pcm_sha256,
        "wave_sha256": sha256_file(output_path),
    }
