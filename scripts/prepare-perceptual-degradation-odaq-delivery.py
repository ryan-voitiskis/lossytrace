#!/usr/bin/env python3
"""Prepare and synthetically verify canonical ODAQ browser-delivery WAVs.

This module intentionally has no live-corpus command. A separately committed
successor authorization must provide any future private retained-audio runner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/odaq-reference-delivery-preparation-plan.json"
PCM_SUBFORMAT_GUID = bytes.fromhex("0100000000001000800000aa00389b71")
FLOAT_SUBFORMAT_GUID = bytes.fromhex("0300000000001000800000aa00389b71")
INT32_SCALE = 1 << 31


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _chunks(value: bytes) -> list[tuple[bytes, bytes]]:
    if len(value) < 12 or value[:4] != b"RIFF" or value[8:12] != b"WAVE":
        raise ValueError("input is not RIFF/WAVE")
    if struct.unpack_from("<I", value, 4)[0] + 8 != len(value):
        raise ValueError("input RIFF length differs")
    chunks: list[tuple[bytes, bytes]] = []
    offset = 12
    while offset + 8 <= len(value):
        chunk_id = value[offset : offset + 4]
        chunk_bytes = struct.unpack_from("<I", value, offset + 4)[0]
        start = offset + 8
        end = start + chunk_bytes
        if end > len(value):
            raise ValueError("input WAV chunk exceeds RIFF length")
        chunks.append((chunk_id, value[start:end]))
        offset = end + (chunk_bytes & 1)
    if offset != len(value):
        raise ValueError("input WAV chunk padding differs")
    return chunks


def parse_delivery_input(value: bytes) -> dict[str, Any]:
    chunks = _chunks(value)
    formats = [payload for chunk_id, payload in chunks if chunk_id == b"fmt "]
    payloads = [payload for chunk_id, payload in chunks if chunk_id == b"data"]
    facts = [payload for chunk_id, payload in chunks if chunk_id == b"fact"]
    if len(formats) != 1 or len(payloads) != 1:
        raise ValueError("input requires exactly one format and data chunk")
    fmt = formats[0]
    if len(fmt) not in {16, 18, 40}:
        raise ValueError("input WAV format chunk differs")
    audio_format, channels, sample_rate, byte_rate, block_align, bits = (
        struct.unpack_from("<HHIIHH", fmt)
    )
    container_encoding = "riff_wave"
    if audio_format == 0xFFFE:
        if len(fmt) != 40:
            raise ValueError("input extensible WAV format chunk differs")
        extension_bytes, valid_bits, channel_mask = struct.unpack_from("<HHI", fmt, 16)
        if extension_bytes != 22 or valid_bits != bits or channel_mask != 0:
            raise ValueError("input extensible WAV fields differ")
        subtype = fmt[24:40]
        if subtype == PCM_SUBFORMAT_GUID:
            audio_format = 1
        elif subtype == FLOAT_SUBFORMAT_GUID:
            audio_format = 3
        else:
            raise ValueError("input extensible WAV subtype is unsupported")
        container_encoding = "wave_format_extensible"
    elif len(fmt) == 18 and struct.unpack_from("<H", fmt, 16)[0] != 0:
        raise ValueError("input WAV format extension is unsupported")
    if channels != 2 or sample_rate != 48_000:
        raise ValueError("input must remain 48 kHz stereo")
    if audio_format == 1 and bits == 24:
        input_encoding = "signed_integer_pcm"
        output_bits = 24
    elif audio_format == 3 and bits == 32:
        input_encoding = "ieee_float_pcm"
        output_bits = 32
    else:
        raise ValueError("input encoding is outside the frozen conversion scope")
    expected_align = channels * (bits // 8)
    if block_align != expected_align or byte_rate != sample_rate * expected_align:
        raise ValueError("input byte geometry differs")
    data = payloads[0]
    if not data or len(data) % block_align:
        raise ValueError("input PCM payload is empty or misaligned")
    frames = len(data) // block_align
    if input_encoding == "ieee_float_pcm":
        if len(facts) != 1 or len(facts[0]) != 4:
            raise ValueError("float input requires one exact fact chunk")
        if struct.unpack_from("<I", facts[0])[0] != frames:
            raise ValueError("float input fact frame count differs")
    elif facts:
        raise ValueError("integer input fact chunk is unexpected")
    return {
        "container_encoding": container_encoding,
        "sample_encoding": input_encoding,
        "sample_rate_hz": sample_rate,
        "channel_count": channels,
        "input_bit_depth": bits,
        "output_bit_depth": output_bits,
        "frame_count": frames,
        "data": data,
    }


def quantize_float32_to_int32(payload: bytes) -> bytes:
    output = bytearray(len(payload))
    for offset in range(0, len(payload), 4):
        sample = struct.unpack_from("<f", payload, offset)[0]
        if not math.isfinite(sample) or not -1.0 <= sample < 1.0:
            raise ValueError("float input contains a non-finite or out-of-range sample")
        integer = round(sample * INT32_SCALE)
        if not -(1 << 31) <= integer < (1 << 31):
            raise ValueError("float-to-integer quantization overflowed")
        struct.pack_into("<i", output, offset, integer)
    return bytes(output)


def canonical_pcm_wav(*, payload: bytes, sample_rate: int, channels: int, bits: int) -> bytes:
    block_align = channels * (bits // 8)
    fmt = struct.pack(
        "<HHIIHH",
        1,
        channels,
        sample_rate,
        sample_rate * block_align,
        block_align,
        bits,
    )
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", len(payload)) + payload
    if len(payload) & 1:
        body += b"\0"
    return b"RIFF" + struct.pack("<I", len(body)) + body


def project_delivery_wav(value: bytes) -> tuple[bytes, dict[str, Any]]:
    parsed = parse_delivery_input(value)
    payload = parsed["data"]
    operation = "container_canonicalization_payload_unchanged"
    if parsed["sample_encoding"] == "ieee_float_pcm":
        payload = quantize_float32_to_int32(payload)
        operation = "deterministic_float32_to_signed_int32_nearest_ties_to_even"
    output = canonical_pcm_wav(
        payload=payload,
        sample_rate=parsed["sample_rate_hz"],
        channels=parsed["channel_count"],
        bits=parsed["output_bit_depth"],
    )
    return output, {
        "operation": operation,
        "input_container_encoding": parsed["container_encoding"],
        "input_sample_encoding": parsed["sample_encoding"],
        "input_bit_depth": parsed["input_bit_depth"],
        "output_container_encoding": "riff_wave",
        "output_sample_encoding": "signed_integer_pcm",
        "output_bit_depth": parsed["output_bit_depth"],
        "sample_rate_hz": parsed["sample_rate_hz"],
        "channel_count": parsed["channel_count"],
        "frame_count": parsed["frame_count"],
        "dither_applied": False,
        "gain_applied": False,
        "normalization_applied": False,
        "resampling_applied": False,
        "channel_transform_applied": False,
        "output_sha256": sha256_bytes(output),
    }


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema version differs")
    if plan.get("state") != "synthetic_delivery_projection_verified_live_corpus_execution_unauthorized":
        errors.append("preparation state differs")
    bindings = plan.get("bindings", {})
    if set(bindings) != {
        "acquisition_result",
        "attribution_audit",
        "private_lossless_delivery",
        "projection_implementation",
        "projection_tests",
    }:
        errors.append("preparation binding set differs")
    for binding_id, binding in bindings.items():
        relative = Path(str(binding.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"invalid repository-relative binding: {binding_id}")
            continue
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing bound file: {binding_id}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash differs: {binding_id}")
    scope = plan.get("projection_scope", {})
    expected_scope = {
        "source_sample_rate_hz": 48_000,
        "source_channel_count": 2,
        "float_reference_count": 7,
        "extensible_integer_reference_count": 9,
        "float_output_bit_depth": 32,
        "integer_output_bit_depth": 24,
        "output_container": "canonical_riff_wave_format_tag_1",
        "float_rounding": "nearest_ties_to_even",
        "reject_non_finite_float": True,
        "reject_float_below_negative_one": True,
        "reject_float_at_or_above_positive_one": True,
        "dither_applied": False,
        "gain_applied": False,
        "normalization_applied": False,
        "resampling_applied": False,
        "channel_transform_applied": False,
    }
    if scope != expected_scope:
        errors.append("projection scope differs")
    access = plan.get("access_boundary", {})
    if access.get("synthetic_fixture_generation_authorized") is not True:
        errors.append("synthetic fixture authorization differs")
    for key in (
        "retained_reference_access_authorized",
        "retained_reference_conversion_authorized",
        "processed_condition_access_authorized",
        "listening_score_access_authorized",
        "stimulus_generation_authorized",
        "perceptual_metric_execution_authorized",
        "listener_response_collection_authorized",
        "sealed_evidence_access_authorized",
    ):
        if access.get(key) is not False:
            errors.append(f"access boundary must remain false: {key}")
    playback = plan.get("playback_gate", {})
    if playback.get("required_session_sample_rate_hz") != 48_000:
        errors.append("playback session rate differs")
    if playback.get("observed_interface_sample_rate_hz") != 96_000:
        errors.append("observed interface rate differs")
    if playback.get("sample_rate_match_qualified") is not False:
        errors.append("sample-rate match was prematurely qualified")
    if playback.get("physical_playback_qualified") is not False:
        errors.append("physical playback was prematurely qualified")
    if plan.get("authorized_next_step") != (
        "Commit a separate authorization before any retained reference is read or projected. "
        "Then create a private path-bound manifest, attach the frozen attribution records, "
        "verify two byte-identical projections, and perform the 48 kHz channel and conservative-level qualification without collecting ratings."
    ):
        errors.append("authorized next step differs")
    if "/Users/" in json.dumps(plan, sort_keys=True):
        errors.append("preparation plan must not contain a private absolute path")
    return errors


def command_synthetic() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        value = canonical_pcm_wav(
            payload=struct.pack("<8f", -1.0, -0.5, -2.0**-32, -0.0, 0.0, 2.0**-32, 0.5, 1.0 - 2.0**-24),
            sample_rate=48_000,
            channels=2,
            bits=32,
        )
        fmt_payload = struct.pack("<HHIIHHH", 3, 2, 48_000, 384_000, 8, 32, 0)
        data = _chunks(value)[1][1]
        fact = struct.pack("<I", 4)
        body = b"WAVE" + b"fmt " + struct.pack("<I", 18) + fmt_payload
        body += b"fact" + struct.pack("<I", 4) + fact
        body += b"data" + struct.pack("<I", len(data)) + data
        source = b"RIFF" + struct.pack("<I", len(body)) + body
        first, first_record = project_delivery_wav(source)
        second, second_record = project_delivery_wav(source)
        (root / "first.wav").write_bytes(first)
        (root / "second.wav").write_bytes(second)
        if first != second or first_record != second_record:
            raise ValueError("synthetic projections differ")
    print(json.dumps({
        "output_sha256": sha256_bytes(first),
        "status": "synthetic_projection_byte_identical",
        "temporary_outputs_retained": False,
    }, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    validate = subcommands.add_parser("validate-plan")
    validate.add_argument("--plan", type=Path, default=PLAN)
    subcommands.add_parser("synthetic")
    args = parser.parse_args()
    if args.command == "synthetic":
        return command_synthetic()
    errors = validate_plan(load_json(args.plan))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(json.dumps({"plan": str(args.plan.relative_to(ROOT)), "status": "synthetic_only_preparation_valid"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
