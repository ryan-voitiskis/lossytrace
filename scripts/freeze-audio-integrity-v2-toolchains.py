#!/usr/bin/env python3
"""Freeze and replay the exact factorial-v2 codec and PCM toolchain.

The ``prepare`` command derives a path-free, executable freeze from the already
frozen factor levels and the earlier synthetic tool inventory. The ``probe``
command accepts private executable locations, verifies every binary/component
hash, and emits path-free synthetic evidence. Neither command reads benchmark
audio, assigns source groups, computes mechanism features, or opens scores.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
BASE_PROBE_PATH = ROOT / "scripts" / "probe-audio-integrity-v2-toolchains.py"
BASE_SPEC = importlib.util.spec_from_file_location("v2_base_tool_probe", BASE_PROBE_PATH)
if BASE_SPEC is None or BASE_SPEC.loader is None:
    raise RuntimeError(f"cannot import base toolchain probe: {BASE_PROBE_PATH}")
BASE = importlib.util.module_from_spec(BASE_SPEC)
BASE_SPEC.loader.exec_module(BASE)


SCHEMA_VERSION = 1
FREEZE_ID = "lossytrace-v2-toolchain-bindings-20260802-002"
PROBE_ID = "lossytrace-v2-factor-toolchain-probe-20260802-002"
EXPECTED_FACTOR_ID = "lossytrace-v2-factor-levels-20260802-001"
EXPECTED_FACTOR_COMMIT = "52470b2d0e279d002b8516a7d4f862c93133ac8b"
EXPECTED_PRIOR_EVIDENCE_SHA256 = (
    "fb497f37ade1a6db5e3d87a0f957f6c2e72433c4091679f098ab6ce07b8b8c8d"
)
MINIMUM_FREE_RESERVE_BYTES = 15 * 1024**3
TOOL_TOKEN_PREFIX = "<TOOL:"
INPUT_TOKEN = "<INPUT>"
OUTPUT_TOKEN = "<OUTPUT>"
CHANNELS = (("mono", 1), ("stereo", 2))
CODEC_DETAILS = {
    "mp3": {"codec_name": "mp3", "extension": ".mp3", "profile": None},
    "aac_lc": {"codec_name": "aac", "extension": ".m4a", "profile": "LC"},
    "opus": {"codec_name": "opus", "extension": ".opus", "profile": None},
    "vorbis": {"codec_name": "vorbis", "extension": ".ogg", "profile": None},
}
ENCODER_TO_TOOL = {
    "mp3_lame_4_0": "lame_cli_4_0",
    "mp3_shine_ab5e352": "shineenc_3_1_1_ab5e352",
    "mp3_bladeenc_a2d06ec": "bladeenc_0_94_2_a2d06ec",
    "aac_ffmpeg_native_8_1_2": "ffmpeg_8_1_2_1",
    "aac_apple_audiotoolbox_25g72": "ffmpeg_8_1_2_1",
    "aac_fdk_2_0_3": "fdkaac_1_0_8_fdk_2_0_3",
    "opus_libopus_1_6_1": "opusenc_0_2_2_libopus_1_6_1",
    "opus_ffmpeg_native_8_1_2": "ffmpeg_8_1_2_1",
    "vorbis_libvorbis_1_3_7": "oggenc_1_4_3_libvorbis_1_3_7",
    "vorbis_ffmpeg_native_8_1_2": "ffmpeg_8_1_2_1",
}
DECODER_TO_TOOL = {
    "ffmpeg_native_audio_8_1_2": "ffmpeg_8_1_2_1",
    "apple_audiotoolbox_25g72": "apple_afconvert_macos_26_6_25g72",
    "mpg123_1_33_6": "mpg123_1_33_6",
    "opusdec_0_2_2_libopus_1_6_1": "opusdec_0_2_2_libopus_1_6_1",
    "oggdec_1_4_3_libvorbis_1_3_7": "oggdec_1_4_3_libvorbis_1_3_7",
}
DECODER_COMMANDS = {
    "ffmpeg_native_audio_8_1_2": [
        "<TOOL:ffmpeg_8_1_2_1>",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-fflags",
        "+bitexact",
        "-i",
        INPUT_TOKEN,
        "-map",
        "0:a:0",
        "-c:a",
        "pcm_s16le",
        "-fflags",
        "+bitexact",
        OUTPUT_TOKEN,
    ],
    "apple_audiotoolbox_25g72": [
        "<TOOL:apple_afconvert_macos_26_6_25g72>",
        INPUT_TOKEN,
        OUTPUT_TOKEN,
        "-f",
        "WAVE",
        "-d",
        "LEI16",
    ],
    "mpg123_1_33_6": [
        "<TOOL:mpg123_1_33_6>",
        "-q",
        "-w",
        OUTPUT_TOKEN,
        INPUT_TOKEN,
    ],
    "opusdec_0_2_2_libopus_1_6_1": [
        "<TOOL:opusdec_0_2_2_libopus_1_6_1>",
        "--quiet",
        INPUT_TOKEN,
        OUTPUT_TOKEN,
    ],
    "oggdec_1_4_3_libvorbis_1_3_7": [
        "<TOOL:oggdec_1_4_3_libvorbis_1_3_7>",
        "-Q",
        "-o",
        OUTPUT_TOKEN,
        INPUT_TOKEN,
    ],
}
ANALYSIS_DECODER_COMMAND = [
    "<TOOL:ffmpeg_8_1_2_1>",
    "-hide_banner",
    "-loglevel",
    "error",
    "-y",
    "-fflags",
    "+bitexact",
    "-i",
    INPUT_TOKEN,
    "-map",
    "0:a:0",
    "-c:a",
    "pcm_s16le",
    "-f",
    "s16le",
    "-fflags",
    "+bitexact",
    OUTPUT_TOKEN,
]
LOWPASS_SECTION_Q = (
    "0.5097955791041592",
    "0.6013448869350453",
    "0.8999762231364156",
    "2.5629154477415064",
)
SPECTRAL_FREQUENCIES_HZ = {
    44_100: (
        1_000,
        4_000,
        8_000,
        12_000,
        14_000,
        15_000,
        15_500,
        16_000,
        16_500,
        17_000,
        17_500,
        18_000,
        18_500,
        19_000,
        19_500,
        20_000,
        20_500,
        21_000,
    ),
    48_000: (
        1_000,
        4_000,
        8_000,
        12_000,
        14_000,
        15_000,
        15_500,
        16_000,
        16_500,
        17_000,
        17_500,
        18_000,
        18_500,
        19_000,
        19_500,
        20_000,
        20_500,
        21_000,
        22_000,
        23_000,
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def tool_token(tool_id: str) -> str:
    return f"{TOOL_TOKEN_PREFIX}{tool_id}>"


def parse_rate(value: str) -> int:
    if value.endswith("k") and value[:-1].isdigit():
        return int(value[:-1])
    raise ValueError(f"unsupported bitrate value: {value}")


def common_ffmpeg_input(tool_id: str) -> list[str]:
    return [
        tool_token(tool_id),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-fflags",
        "+bitexact",
        "-i",
        INPUT_TOKEN,
        "-map",
        "0:a:0",
    ]


def encoder_command(template: dict[str, Any], channel_count: int) -> list[str]:
    encoder_id = template["encoder_id"]
    bitrate_or_quality = template["bitrate_or_quality"]
    if channel_count not in (1, 2):
        raise ValueError("encoder command channel count must be mono or stereo")
    tool_id = ENCODER_TO_TOOL[encoder_id]
    tool = tool_token(tool_id)

    if encoder_id == "mp3_lame_4_0":
        mode = "m" if channel_count == 1 else "j"
        if template["rate_control"] == "vbr":
            return [
                tool,
                "--silent",
                "-V",
                "2",
                "-m",
                mode,
                "--resample",
                "44.1",
                INPUT_TOKEN,
                OUTPUT_TOKEN,
            ]
        command = [
            tool,
            "--silent",
            "--cbr",
            "-b",
            str(parse_rate(bitrate_or_quality)),
            "-m",
            mode,
            "--resample",
            "44.1",
        ]
        if template["encoder_lowpass"]["mode"] == "fixed":
            command.extend(["--lowpass", "16"])
        return [*command, INPUT_TOKEN, OUTPUT_TOKEN]

    if encoder_id == "mp3_shine_ab5e352":
        command = [tool, "-q", "-b", str(parse_rate(bitrate_or_quality))]
        if channel_count == 1:
            command.append("-m")
        return [*command, INPUT_TOKEN, OUTPUT_TOKEN]

    if encoder_id == "mp3_bladeenc_a2d06ec":
        command = [tool, "-quiet", "-nocfg", INPUT_TOKEN, OUTPUT_TOKEN]
        command.append(f"-{parse_rate(bitrate_or_quality)}")
        if channel_count == 1:
            command.append("-mono")
        return command

    if encoder_id in {
        "aac_ffmpeg_native_8_1_2",
        "aac_apple_audiotoolbox_25g72",
    }:
        command = common_ffmpeg_input(tool_id)
        command.extend(["-ac:a", str(channel_count), "-ar:a", "44100"])
        if encoder_id == "aac_ffmpeg_native_8_1_2":
            command.extend(["-c:a", "aac", "-profile:a", "aac_low"])
        else:
            command.extend(["-c:a", "aac_at", "-aac_at_mode", "cbr"])
        command.extend(["-b:a", bitrate_or_quality])
        if template["encoder_lowpass"]["mode"] == "fixed":
            command.extend(["-cutoff", str(template["encoder_lowpass"]["hz"])])
        command.extend(["-flags:a", "+bitexact", "-fflags", "+bitexact", OUTPUT_TOKEN])
        return command

    if encoder_id == "aac_fdk_2_0_3":
        return [
            tool,
            "--silent",
            "--no-timestamp",
            "-p",
            "2",
            "-m",
            "0",
            "-b",
            str(parse_rate(bitrate_or_quality) * 1000),
            "-o",
            OUTPUT_TOKEN,
            INPUT_TOKEN,
        ]

    if encoder_id == "opus_libopus_1_6_1":
        return [
            tool,
            "--quiet",
            "--serial",
            "1953",
            "--hard-cbr",
            "--bitrate",
            str(parse_rate(bitrate_or_quality)),
            "--framesize",
            str(template["frame_duration_ms"]),
            INPUT_TOKEN,
            OUTPUT_TOKEN,
        ]

    if encoder_id == "opus_ffmpeg_native_8_1_2":
        return [
            *common_ffmpeg_input(tool_id),
            "-ac:a",
            str(channel_count),
            "-ar:a",
            "48000",
            "-strict",
            "experimental",
            "-c:a",
            "opus",
            "-b:a",
            bitrate_or_quality,
            "-flags:a",
            "+bitexact",
            "-fflags",
            "+bitexact",
            "-serial_offset",
            "1953",
            OUTPUT_TOKEN,
        ]

    quality = bitrate_or_quality.removeprefix("q")
    if encoder_id == "vorbis_libvorbis_1_3_7":
        return [tool, "-Q", "--serial", "1954", "-q", quality, "-o", OUTPUT_TOKEN, INPUT_TOKEN]
    if encoder_id == "vorbis_ffmpeg_native_8_1_2":
        return [
            *common_ffmpeg_input(tool_id),
            "-ac:a",
            str(channel_count),
            "-ar:a",
            "44100",
            "-strict",
            "experimental",
            "-c:a",
            "vorbis",
            "-q:a",
            quality,
            "-flags:a",
            "+bitexact",
            "-fflags",
            "+bitexact",
            "-serial_offset",
            "1954",
            OUTPUT_TOKEN,
        ]
    raise ValueError(f"no command binding for encoder {encoder_id}")


def lowpass_filter_graph() -> str:
    return ",".join(
        "lowpass=f=16000:t=q:w="
        f"{quality}:p=2:a=tdii:r=f64:n=0"
        for quality in LOWPASS_SECTION_Q
    )


def resample_filter_graph(target_sample_rate_hz: int) -> str:
    common = (
        "resampler=swr:filter_size=64:phase_shift=10:linear_interp=0:"
        "exact_rational=1:cutoff=0.95:filter_type=kaiser:kaiser_beta=9:"
        "dither_method=none"
    )
    return f"aresample=32000:osf=s32:{common},aresample={target_sample_rate_hz}:osf=s16:{common}"


def ffmpeg_wave_transform_command(filter_graph: str) -> list[str]:
    return [
        *common_ffmpeg_input("ffmpeg_8_1_2_1"),
        "-af",
        filter_graph,
        "-c:a",
        "pcm_s16le",
        "-fflags",
        "+bitexact",
        OUTPUT_TOKEN,
    ]


def wrapper_command(wrapper_id: str) -> list[str]:
    codec_args = {
        "flac16": ["-c:a", "flac", "-sample_fmt", "s16"],
        "wav16": ["-c:a", "pcm_s16le"],
        "aiff16": ["-c:a", "pcm_s16be"],
    }[wrapper_id]
    return [
        *common_ffmpeg_input("ffmpeg_8_1_2_1"),
        *codec_args,
        "-fflags",
        "+bitexact",
        OUTPUT_TOKEN,
    ]


def exact_transform_bindings(factor: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for transform in factor["pcm_transform_levels"]:
        transform_id = transform["transform_id"]
        binding: dict[str, Any] = {
            "transform_id": transform_id,
            "family": transform["family"],
            "parameters": transform["parameters"],
        }
        if transform_id == "identity":
            binding["implementation"] = "byte-exact signed-s16le PCM identity"
        elif transform_id == "gain-minus6db-q31":
            binding["implementation"] = (
                "For each signed sample x, round x*1076291389/2^31 to nearest "
                "with ties to even, then saturate to signed 16-bit."
            )
        elif transform_id == "trim-head-250ms":
            binding["implementation"] = (
                "Remove exactly sample_rate_hz*250/1000 leading frames; reject "
                "inputs below the frozen minimum."
            )
        elif transform_id == "prepend-digital-silence-500ms":
            binding["implementation"] = (
                "Prepend exactly sample_rate_hz*500/1000 zero-valued frames."
            )
        elif transform_id == "duration-prefix-3s":
            binding["implementation"] = (
                "Retain exactly the first sample_rate_hz*3 frames; reject inputs "
                "below the frozen minimum."
            )
        elif transform_id == "lowpass-16k-cascade8":
            binding.update(
                {
                    "implementation": (
                        "FFmpeg f64 transposed-direct-form-II cascade of four "
                        "two-pole lowpass sections forming an eighth-order "
                        "Butterworth response, followed by deterministic s16 output."
                    ),
                    "section_q_in_processing_order": list(LOWPASS_SECTION_Q),
                    "command": ffmpeg_wave_transform_command(lowpass_filter_graph()),
                }
            )
        elif transform_id == "resample-roundtrip-32k":
            binding.update(
                {
                    "implementation": (
                        "FFmpeg SWResampler 64-tap Kaiser sinc, exact-rational "
                        "phases, no interpolation, cutoff 0.95, beta 9, and no dither."
                    ),
                    "commands_by_target_sample_rate_hz": {
                        str(rate): ffmpeg_wave_transform_command(
                            resample_filter_graph(rate)
                        )
                        for rate in (44_100, 48_000)
                    },
                }
            )
        elif transform_id == "requantize-12bit-tpdf":
            binding["implementation"] = (
                "Read two unsigned 16-bit big-endian values a,b per sample from "
                "SHA-256 counter blocks keyed by UTF-8(seed_prefix || group_id || "
                "NUL || transform_id || NUL || uint64be(counter)). Add exact noise "
                "(a-b)*8/65535, round the result to the nearest multiple of 16 "
                "with ties to even, and saturate to signed 16-bit. This triangular "
                "noise has one 12-bit LSB peak-to-peak."
            )
        elif transform_id == "alternate-channel-topology":
            binding["implementation"] = (
                "Mono duplicates exactly to two channels; stereo becomes mono by "
                "rounding (left+right)/2 to nearest with ties to even."
            )
        elif transform_id == "lossless-wrapper-rewrite":
            binding["implementation"] = (
                "Encode the unchanged signed-s16le PCM into a different frozen "
                "lossless wrapper and require exact analysis-decoder PCM equality."
            )
        else:
            raise ValueError(f"no transform binding for {transform_id}")
        rows.append(binding)
    return rows


def build_manifest(
    factor: dict[str, Any], prior_evidence: dict[str, Any], factor_path: Path, prior_path: Path
) -> dict[str, Any]:
    if factor.get("factor_freeze_id") != EXPECTED_FACTOR_ID:
        raise ValueError("unexpected factor freeze")
    if factor.get("source_allocation_checkpoint_commit") != "7f73bbb0c04e5930a2539b0eac75f9d42daac64a":
        raise ValueError("unexpected source-allocation checkpoint")
    if sha256_file(prior_path) != EXPECTED_PRIOR_EVIDENCE_SHA256:
        raise ValueError("prior toolchain evidence hash differs")
    tool_rows = prior_evidence.get("tools")
    if not isinstance(tool_rows, list):
        raise ValueError("prior tool evidence has no tool bindings")
    available_tools = {row.get("tool_id") for row in tool_rows}
    required_tools = set(ENCODER_TO_TOOL.values()) | set(DECODER_TO_TOOL.values()) | {
        "ffprobe_8_1_2_1"
    }
    if not required_tools <= available_tools:
        raise ValueError("prior evidence lacks a required tool")

    settings = []
    for template in factor["codec_setting_templates"]:
        codec = CODEC_DETAILS[template["codec_family"]]
        for channel_id, channel_count in CHANNELS:
            setting_id = f"{template['template_id']}--{channel_id}"
            tool_id = ENCODER_TO_TOOL[template["encoder_id"]]
            binding_tool_ids = [tool_id]
            if template["encoder_id"].startswith("aac_apple_"):
                binding_tool_ids.append("apple_afconvert_macos_26_6_25g72")
            settings.append(
                {
                    "expanded_setting_id": setting_id,
                    "template_id": template["template_id"],
                    "evidence_partition": template["evidence_partition"],
                    "codec_family": template["codec_family"],
                    "encoder_id": template["encoder_id"],
                    "lineage_id": template["lineage_id"],
                    "tool_id": tool_id,
                    "binding_tool_ids": binding_tool_ids,
                    "channel_treatment_id": channel_id,
                    "expected_channel_count": channel_count,
                    "expected_sample_rate_hz": template["sample_rate_hz"],
                    "expected_codec_name": codec["codec_name"],
                    "expected_profile": codec["profile"],
                    "output_extension": codec["extension"],
                    "rate_control": template["rate_control"],
                    "bitrate_or_quality": template["bitrate_or_quality"],
                    "nominal_encoder_lowpass": template["encoder_lowpass"],
                    "frame_duration_ms": template.get("frame_duration_ms"),
                    "anchor": template.get("anchor", False),
                    "input_id": f"synthetic-{template['sample_rate_hz']}-{channel_id}",
                    "command": encoder_command(template, channel_count),
                }
            )

    decoders = []
    for level in factor["history_decoder_levels"]:
        decoder_id = level["history_decoder_id"]
        decoders.append(
            {
                "history_decoder_id": decoder_id,
                "tool_id": DECODER_TO_TOOL[decoder_id],
                "codec_families": level["codec_families"],
                "role": level["role"],
                "command": DECODER_COMMANDS[decoder_id],
            }
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "toolchain_freeze_id": FREEZE_ID,
        "state": "exact_toolchain_recipe_frozen_before_expanded_setting_replay",
        "factor_binding": {
            "factor_freeze_id": factor["factor_freeze_id"],
            "path": "benchmarks/audio-integrity-v2/factor-levels.json",
            "sha256": sha256_file(factor_path),
            "checkpoint_commit": EXPECTED_FACTOR_COMMIT,
        },
        "prior_toolchain_evidence_binding": {
            "path": "research/toolchains/evidence/observed-20260802-001-aggregate.json",
            "sha256": EXPECTED_PRIOR_EVIDENCE_SHA256,
            "probe_id": prior_evidence["probe_id"],
        },
        "public_state": {
            "evidence_schema_version": 1,
            "feature_version": 0,
            "public_verdict_enabled": False,
        },
        "benchmark_audio_generated": False,
        "source_groups_assigned": False,
        "scores_opened": False,
        "selection_authorized": False,
        "complete_replay_observed": False,
        "tool_bindings": tool_rows,
        "probe_inputs": [
            {
                "input_id": f"synthetic-{rate}-{channel_id}",
                "sample_rate_hz": rate,
                "channel_count": channel_count,
                "frame_count": rate * 3,
                "generator_id": BASE.PROBE_GENERATOR_ID,
            }
            for rate in (44_100, 48_000)
            for channel_id, channel_count in CHANNELS
        ],
        "expanded_encoder_settings": settings,
        "history_decoder_bindings": decoders,
        "analysis_decoder_binding": {
            "analysis_decoder_id": "canonical_lossless_pcm_decoder",
            "implementation": "FFmpeg native audio decode to headerless signed-s16le",
            "tool_id": "ffmpeg_8_1_2_1",
            "command": ANALYSIS_DECODER_COMMAND,
            "wrapper_scope": ["flac16", "wav16", "aiff16"],
        },
        "encoder_bandwidth_observation": {
            "measurement_id": "segmented-tone-retained-band-edge-v1",
            "claim_boundary": (
                "A coarse decoded spectral-retention observation, not an exact "
                "psychoacoustic filter cutoff and not provenance evidence."
            ),
            "frequencies_hz_by_sample_rate": {
                str(rate): list(frequencies)
                for rate, frequencies in SPECTRAL_FREQUENCIES_HZ.items()
            },
            "segment_milliseconds": 400,
            "leading_and_trailing_silence_milliseconds": 500,
            "measurement_window_milliseconds": [150, 250],
            "sine_peak_sample": 12000,
            "normalization_frequencies_hz": [1000, 4000, 8000],
            "retained_threshold_relative_db": -6.0,
            "retained_edge_rule": (
                "Highest probed tone whose decoded RMS, normalized by the median "
                "1/4/8 kHz RMS, is at least -6 dB."
            ),
            "decoder_id": "canonical_lossless_pcm_decoder",
        },
        "pcm_transform_bindings": exact_transform_bindings(factor),
        "wrapper_bindings": [
            {
                "wrapper_id": row["wrapper_id"],
                "container": row["container"],
                "tool_id": "ffmpeg_8_1_2_1",
                "command": wrapper_command(row["wrapper_id"]),
            }
            for row in factor["wrapper_levels"]
        ],
        "public_decoder_equivalence_boundary": {
            "implementation": "LossyTrace feature-version-0 Symphonia 0.5 decoder",
            "source_checkpoint_commit": EXPECTED_FACTOR_COMMIT,
            "cargo_lock_path": "Cargo.lock",
            "cargo_lock_sha256": sha256_file(ROOT / "Cargo.lock"),
            "prior_observed_evidence": (
                "The 2026-08-01 14-group, seven-domain container audit found exact "
                "feature equality across all 56 FLAC/WAV/AIFF triplets."
            ),
            "fresh_synthetic_equivalence_required_before_baseline_scoring": True,
            "fresh_probe_deferred_reason": (
                "No frozen public binary exists at this recipe checkpoint; bind and "
                "run one after the toolchain result commit and before scoring."
            ),
        },
        "replay_contract": {
            "complete_replay_count": 2,
            "reports_must_be_byte_identical": True,
            "encoder_runs_per_setting_within_replay": 2,
            "decoder_runs_per_compatible_path_within_replay": 2,
            "transform_runs_per_input_within_replay": 2,
            "expected_expanded_setting_count": 48,
            "expected_history_decoder_path_count": 132,
            "expected_transform_input_path_count": 40,
            "expected_wrapper_encode_path_count": 12,
            "expected_wrapper_analysis_decode_path_count": 12,
            "maximum_parallel_workers": 1,
            "minimum_free_space_reserve_bytes": MINIMUM_FREE_RESERVE_BYTES,
        },
        "stop_conditions": [
            "A binary, linked component, factor file, or prior-evidence hash differs.",
            "A frozen command cannot realize its nominal codec/profile/rate/channel level.",
            "An encoded setting is not byte-deterministic across two executions.",
            "A compatible decoder path is not PCM-deterministic across two executions.",
            "A deterministic transform differs across two executions.",
            "FLAC, WAV, and AIFF do not decode to the exact input signed-s16le PCM.",
            "The two complete public reports differ byte-for-byte.",
            "Projected or observed free space falls below the 15 GiB reserve.",
        ],
        "authorized_next_step": (
            "Run two complete single-worker synthetic replays and commit only their "
            "path-free aggregate if byte-identical. Do not assign sources, generate "
            "benchmark cases, compute mechanism features, or open scores."
        ),
    }
    validate_manifest(manifest, factor)
    return manifest


def validate_public_command(command: Any, expected_tool_id: str) -> None:
    if not isinstance(command, list) or not command or not all(
        isinstance(part, str) for part in command
    ):
        raise ValueError("command must be a nonempty list of strings")
    if command[0] != tool_token(expected_tool_id):
        raise ValueError(f"command does not invoke {expected_tool_id}")
    if command.count(INPUT_TOKEN) != 1 or command.count(OUTPUT_TOKEN) != 1:
        raise ValueError("command must contain exactly one input and output token")
    if any("/Users/" in part or "\\Users\\" in part for part in command):
        raise ValueError("command contains a private path")


def validate_manifest(manifest: dict[str, Any], factor: dict[str, Any]) -> None:
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("toolchain_freeze_id") != FREEZE_ID
        or manifest.get("state")
        != "exact_toolchain_recipe_frozen_before_expanded_setting_replay"
        or manifest.get("benchmark_audio_generated") is not False
        or manifest.get("source_groups_assigned") is not False
        or manifest.get("scores_opened") is not False
        or manifest.get("selection_authorized") is not False
        or manifest.get("complete_replay_observed") is not False
        or manifest.get("public_state", {}).get("public_verdict_enabled") is not False
    ):
        raise ValueError("manifest state boundary differs")
    if manifest.get("factor_binding", {}).get("factor_freeze_id") != factor.get(
        "factor_freeze_id"
    ):
        raise ValueError("factor binding differs")

    settings = manifest.get("expanded_encoder_settings")
    if not isinstance(settings, list) or len(settings) != 48:
        raise ValueError("exactly 48 expanded settings are required")
    setting_ids = {row.get("expanded_setting_id") for row in settings}
    expected_ids = {
        f"{template['template_id']}--{channel_id}"
        for template in factor["codec_setting_templates"]
        for channel_id, _ in CHANNELS
    }
    if setting_ids != expected_ids:
        raise ValueError("expanded setting ids differ from the factor freeze")
    for row in settings:
        validate_public_command(row.get("command"), row["tool_id"])
        if row["expected_channel_count"] not in (1, 2):
            raise ValueError("invalid setting channel count")

    decoders = manifest.get("history_decoder_bindings")
    if not isinstance(decoders, list) or len(decoders) != 5:
        raise ValueError("exactly five history decoder bindings are required")
    for row in decoders:
        validate_public_command(row.get("command"), row["tool_id"])
    analysis = manifest.get("analysis_decoder_binding", {})
    validate_public_command(analysis.get("command"), analysis.get("tool_id"))

    transforms = manifest.get("pcm_transform_bindings")
    if not isinstance(transforms, list) or {
        row.get("transform_id") for row in transforms
    } != {row["transform_id"] for row in factor["pcm_transform_levels"]}:
        raise ValueError("transform bindings differ from the factor freeze")
    if len([row for row in transforms if row["transform_id"] != "identity"]) != 9:
        raise ValueError("exactly nine nonidentity transform bindings are required")
    wrappers = manifest.get("wrapper_bindings")
    if not isinstance(wrappers, list) or {row.get("wrapper_id") for row in wrappers} != {
        "flac16",
        "wav16",
        "aiff16",
    }:
        raise ValueError("wrapper bindings differ")
    for row in wrappers:
        validate_public_command(row.get("command"), row["tool_id"])

    decoder_path_count = sum(
        1
        for setting in settings
        for decoder in decoders
        if setting["codec_family"] in decoder["codec_families"]
    )
    if decoder_path_count != 132:
        raise ValueError(f"expected 132 decoder paths, found {decoder_path_count}")
    serialized = json.dumps(manifest, sort_keys=True)
    if "/Users/" in serialized or "\\Users\\" in serialized:
        raise ValueError("manifest contains a private path")


def private_template(command: list[str], tool_id: str) -> list[str]:
    converted = []
    for part in command:
        if part == tool_token(tool_id):
            converted.append("{tool}")
        elif part == INPUT_TOKEN:
            converted.append("{input}")
        elif part == OUTPUT_TOKEN:
            converted.append("{output}")
        else:
            converted.append(part)
    return converted


def bind_private_tools(
    manifest: dict[str, Any], private_paths: dict[str, Any]
) -> list[dict[str, Any]]:
    path_rows = private_paths.get("tools")
    if private_paths.get("schema_version") != 1 or not isinstance(path_rows, dict):
        raise ValueError("private tool-path file must have schema version 1 and tools")
    bound = []
    for public in manifest["tool_bindings"]:
        tool_id = public["tool_id"]
        path_row = path_rows.get(tool_id)
        if not isinstance(path_row, dict) or not isinstance(path_row.get("path"), str):
            raise ValueError(f"private path missing for tool {tool_id}")
        component_paths = path_row.get("components", {})
        if not isinstance(component_paths, dict):
            raise ValueError(f"private components invalid for tool {tool_id}")
        components = []
        for component in public.get("components", []):
            component_id = component["component_id"]
            component_path = component_paths.get(component_id)
            if not isinstance(component_path, str):
                raise ValueError(f"private path missing for component {component_id}")
            components.append({**component, "path": component_path})
        bound.append({**public, "path": path_row["path"], "components": components})
    return bound


def build_base_probe_config(
    manifest: dict[str, Any], private_paths: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "probe_id": PROBE_ID,
        "timeout_seconds": 120,
        "ffprobe_tool_id": "ffprobe_8_1_2_1",
        "public_environment": {
            "architecture": "arm64",
            "operating_system": "macOS 26.6",
            "operating_system_build": "25G72",
            "build_parallelism": 1,
        },
        "tools": bind_private_tools(manifest, private_paths),
        "inputs": manifest["probe_inputs"],
        "encoders": [
            {
                "encoder_id": row["expanded_setting_id"],
                "codec_family": row["codec_family"],
                "lineage_id": row["lineage_id"],
                "tool_id": row["tool_id"],
                "binding_tool_ids": row["binding_tool_ids"],
                "input_id": row["input_id"],
                "output_extension": row["output_extension"],
                "expected_codec_name": row["expected_codec_name"],
                "expected_profile": row["expected_profile"],
                "expected_sample_rate_hz": row["expected_sample_rate_hz"],
                "expected_channel_count": row["expected_channel_count"],
                "command": private_template(row["command"], row["tool_id"]),
            }
            for row in manifest["expanded_encoder_settings"]
        ],
        "decoders": [
            {
                "decoder_id": row["history_decoder_id"],
                "tool_id": row["tool_id"],
                "codec_families": row["codec_families"],
                "command": private_template(row["command"], row["tool_id"]),
            }
            for row in manifest["history_decoder_bindings"]
        ],
        "expected_capability_rejections": [],
    }


def check_free_space(location: Path) -> None:
    location.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(location).free < MINIMUM_FREE_RESERVE_BYTES:
        raise ValueError("free space is below the frozen 15 GiB reserve")


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


def read_wave(path: Path) -> tuple[int, int, list[int]]:
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        sample_rate = source.getframerate()
        sample_width = source.getsampwidth()
        frames = source.getnframes()
        data = source.readframes(frames)
    if channels not in (1, 2) or sample_width != 2:
        raise ValueError("expected mono/stereo signed-16 WAV")
    samples = list(struct.unpack(f"<{len(data) // 2}h", data))
    return sample_rate, channels, samples


def write_wave(path: Path, sample_rate: int, channels: int, samples: Iterable[int]) -> None:
    values = list(samples)
    if channels not in (1, 2) or len(values) % channels:
        raise ValueError("invalid signed-16 PCM shape")
    data = struct.pack(f"<{len(values)}h", *values)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(data)


def sha256_counter_bytes(seed: bytes) -> Iterable[int]:
    counter = 0
    while True:
        block = hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()
        yield from block
        counter += 1


def apply_python_transform(
    transform_id: str,
    *,
    sample_rate: int,
    channels: int,
    samples: list[int],
    group_id: str,
) -> tuple[int, list[int]]:
    if transform_id == "identity":
        return channels, samples.copy()
    if transform_id == "gain-minus6db-q31":
        coefficient = 1_076_291_389
        return channels, [
            saturate_s16(round_ratio_ties_even(sample * coefficient, 1 << 31))
            for sample in samples
        ]
    if transform_id == "trim-head-250ms":
        trim_frames = sample_rate * 250 // 1000
        return channels, samples[trim_frames * channels :]
    if transform_id == "prepend-digital-silence-500ms":
        silence_frames = sample_rate * 500 // 1000
        return channels, [0] * (silence_frames * channels) + samples
    if transform_id == "duration-prefix-3s":
        frame_count = sample_rate * 3
        return channels, samples[: frame_count * channels]
    if transform_id == "alternate-channel-topology":
        if channels == 1:
            return 2, [value for sample in samples for value in (sample, sample)]
        mono = [
            round_ratio_ties_even(samples[index] + samples[index + 1], 2)
            for index in range(0, len(samples), 2)
        ]
        return 1, mono
    if transform_id == "requantize-12bit-tpdf":
        prefix = "lossytrace-v2-tpdf-seed-20260802\0"
        seed = f"{prefix}{group_id}\0{transform_id}\0".encode()
        stream = iter(sha256_counter_bytes(seed))
        output = []
        denominator = 2 * 65_535 * 16
        for sample in samples:
            a = (next(stream) << 8) | next(stream)
            b = (next(stream) << 8) | next(stream)
            numerator = sample * 2 * 65_535 + (a - b) * 16
            quantized = round_ratio_ties_even(numerator, denominator) * 16
            output.append(saturate_s16(quantized))
        return channels, output
    raise ValueError(f"transform {transform_id} is not implemented in Python")


def run_public_command(
    command: list[str],
    *,
    tool_paths: dict[str, Path],
    input_path: Path,
    output_path: Path,
    timeout_seconds: int = 120,
) -> None:
    expanded = []
    for part in command:
        if part.startswith(TOOL_TOKEN_PREFIX) and part.endswith(">"):
            tool_id = part[len(TOOL_TOKEN_PREFIX) : -1]
            expanded.append(str(tool_paths[tool_id]))
        elif part == INPUT_TOKEN:
            expanded.append(str(input_path))
        elif part == OUTPUT_TOKEN:
            expanded.append(str(output_path))
        else:
            expanded.append(part)
    completed = subprocess.run(
        expanded,
        capture_output=True,
        text=True,
        env=BASE.process_environment(),
        timeout=timeout_seconds,
    )
    if completed.returncode:
        raise ValueError(
            f"synthetic command failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()[-500:]}"
        )
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise ValueError("synthetic command produced no output")


def generate_segmented_tone_wave(
    path: Path, *, sample_rate: int, channels: int, frequencies: tuple[int, ...]
) -> None:
    segment_frames = sample_rate * 400 // 1000
    padding_frames = sample_rate * 500 // 1000
    samples = [0] * (padding_frames * channels)
    peak = 12_000
    for frequency in frequencies:
        for frame in range(segment_frames):
            phase = 2.0 * math.pi * frequency * frame / sample_rate
            for channel in range(channels):
                offset = channel * math.pi / 2.0
                samples.append(round(peak * math.sin(phase + offset)))
    samples.extend([0] * (padding_frames * channels))
    write_wave(path, sample_rate, channels, samples)


def rms_window(
    samples: list[int], channels: int, start_frame: int, end_frame: int
) -> float:
    selected = []
    for frame in range(start_frame, end_frame):
        offset = frame * channels
        if offset + channels > len(samples):
            break
        selected.extend(samples[offset : offset + channels])
    if not selected:
        raise ValueError("spectral observation window is outside decoded PCM")
    return math.sqrt(sum(value * value for value in selected) / len(selected))


def median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def run_bandwidth_observations(
    manifest: dict[str, Any],
    tool_paths: dict[str, Path],
    work: Path,
) -> list[dict[str, Any]]:
    inputs: dict[tuple[int, int], Path] = {}
    for sample_rate, frequencies in SPECTRAL_FREQUENCIES_HZ.items():
        for _, channels in CHANNELS:
            path = work / f"bandwidth-{sample_rate}-{channels}ch.wav"
            generate_segmented_tone_wave(
                path,
                sample_rate=sample_rate,
                channels=channels,
                frequencies=frequencies,
            )
            inputs[(sample_rate, channels)] = path

    rows = []
    for setting in manifest["expanded_encoder_settings"]:
        sample_rate = setting["expected_sample_rate_hz"]
        channels = setting["expected_channel_count"]
        frequencies = SPECTRAL_FREQUENCIES_HZ[sample_rate]
        encoded = work / f"bandwidth-{setting['expanded_setting_id']}{setting['output_extension']}"
        decoded = work / f"bandwidth-{setting['expanded_setting_id']}.wav"
        run_public_command(
            setting["command"],
            tool_paths=tool_paths,
            input_path=inputs[(sample_rate, channels)],
            output_path=encoded,
        )
        ffmpeg_decode = DECODER_COMMANDS["ffmpeg_native_audio_8_1_2"]
        run_public_command(
            ffmpeg_decode,
            tool_paths=tool_paths,
            input_path=encoded,
            output_path=decoded,
        )
        observed_rate, observed_channels, samples = read_wave(decoded)
        if observed_rate != sample_rate or observed_channels != channels:
            raise ValueError("bandwidth decode format differs from setting")
        segment_frames = sample_rate * 400 // 1000
        padding_frames = sample_rate * 500 // 1000
        window_start = sample_rate * 150 // 1000
        window_end = sample_rate * 250 // 1000
        rms_values = []
        for index, frequency in enumerate(frequencies):
            start = padding_frames + index * segment_frames + window_start
            end = padding_frames + index * segment_frames + window_end
            rms_values.append((frequency, rms_window(samples, channels, start, end)))
        baseline = median([rms for frequency, rms in rms_values if frequency in (1000, 4000, 8000)])
        if baseline <= 0:
            raise ValueError("bandwidth observation baseline has no energy")
        levels = [
            {
                "frequency_hz": frequency,
                "relative_rms_db": round(20.0 * math.log10(max(rms, 1e-12) / baseline), 6),
            }
            for frequency, rms in rms_values
        ]
        retained = [
            row["frequency_hz"] for row in levels if row["relative_rms_db"] >= -6.0
        ]
        rows.append(
            {
                "expanded_setting_id": setting["expanded_setting_id"],
                "measurement_id": "segmented-tone-retained-band-edge-v1",
                "encoded_sha256": sha256_file(encoded),
                "decoded_pcm_sha256": BASE.wave_pcm_info(decoded)["pcm_sha256"],
                "relative_levels": levels,
                "retained_band_edge_lower_bound_hz_at_minus6db": max(retained) if retained else None,
                "claim_boundary": "coarse decoded retention edge, not exact encoder cutoff",
            }
        )
    return rows


def transform_command_for(
    manifest: dict[str, Any], transform_id: str, sample_rate: int
) -> list[str]:
    row = next(
        item for item in manifest["pcm_transform_bindings"] if item["transform_id"] == transform_id
    )
    if transform_id == "lowpass-16k-cascade8":
        return row["command"]
    if transform_id == "resample-roundtrip-32k":
        return row["commands_by_target_sample_rate_hz"][str(sample_rate)]
    raise ValueError(f"transform {transform_id} has no external command")


def run_transform_golden_probes(
    manifest: dict[str, Any], tool_paths: dict[str, Path], work: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    input_rows = []
    transform_rows = []
    pure_ids = {
        "identity",
        "gain-minus6db-q31",
        "trim-head-250ms",
        "prepend-digital-silence-500ms",
        "duration-prefix-3s",
        "requantize-12bit-tpdf",
        "alternate-channel-topology",
    }
    external_ids = {"lowpass-16k-cascade8", "resample-roundtrip-32k"}
    for sample_rate in (44_100, 48_000):
        for channel_id, channels in CHANNELS:
            input_id = f"synthetic-{sample_rate}-{channel_id}"
            source = work / f"transform-{input_id}.wav"
            BASE.generate_probe_wave(
                source,
                sample_rate_hz=sample_rate,
                frame_count=sample_rate * 4,
                channel_count=channels,
            )
            input_rows.append({"input_id": input_id, **BASE.wave_pcm_info(source)})
            for transform_id in sorted(pure_ids | external_ids):
                outputs = []
                for run_index in (1, 2):
                    output = work / f"{input_id}-{transform_id}-run{run_index}.wav"
                    if transform_id in pure_ids:
                        rate, input_channels, samples = read_wave(source)
                        output_channels, transformed = apply_python_transform(
                            transform_id,
                            sample_rate=rate,
                            channels=input_channels,
                            samples=samples,
                            group_id="synthetic-toolchain-golden",
                        )
                        write_wave(output, rate, output_channels, transformed)
                    else:
                        run_public_command(
                            transform_command_for(manifest, transform_id, sample_rate),
                            tool_paths=tool_paths,
                            input_path=source,
                            output_path=output,
                        )
                    outputs.append(BASE.wave_pcm_info(output))
                if outputs[0] != outputs[1]:
                    raise ValueError(f"transform {transform_id} is not deterministic")
                transform_rows.append(
                    {
                        "input_id": input_id,
                        "transform_id": transform_id,
                        "deterministic_across_two_runs": True,
                        "observed": outputs[0],
                    }
                )
    return input_rows, transform_rows


def wrapper_extension(wrapper_id: str) -> str:
    return {"flac16": ".flac", "wav16": ".wav", "aiff16": ".aiff"}[wrapper_id]


def run_wrapper_golden_probes(
    manifest: dict[str, Any], tool_paths: dict[str, Path], work: Path
) -> list[dict[str, Any]]:
    rows = []
    for sample_rate in (44_100, 48_000):
        for channel_id, channels in CHANNELS:
            input_id = f"synthetic-{sample_rate}-{channel_id}"
            source = work / f"wrapper-{input_id}.wav"
            BASE.generate_probe_wave(
                source,
                sample_rate_hz=sample_rate,
                frame_count=sample_rate * 3,
                channel_count=channels,
            )
            source_pcm_hash = BASE.wave_pcm_info(source)["pcm_sha256"]
            decoded_hashes = []
            for wrapper in manifest["wrapper_bindings"]:
                wrapper_id = wrapper["wrapper_id"]
                encoded_hashes = []
                decoded_pcm_hashes = []
                for run_index in (1, 2):
                    encoded = work / (
                        f"{input_id}-{wrapper_id}-run{run_index}{wrapper_extension(wrapper_id)}"
                    )
                    decoded = work / f"{input_id}-{wrapper_id}-run{run_index}.s16le"
                    run_public_command(
                        wrapper["command"],
                        tool_paths=tool_paths,
                        input_path=source,
                        output_path=encoded,
                    )
                    run_public_command(
                        manifest["analysis_decoder_binding"]["command"],
                        tool_paths=tool_paths,
                        input_path=encoded,
                        output_path=decoded,
                    )
                    encoded_hashes.append(sha256_file(encoded))
                    decoded_pcm_hashes.append(sha256_file(decoded))
                if len(set(encoded_hashes)) != 1 or len(set(decoded_pcm_hashes)) != 1:
                    raise ValueError(f"wrapper {wrapper_id} is not deterministic")
                if decoded_pcm_hashes[0] != source_pcm_hash:
                    raise ValueError(f"wrapper {wrapper_id} changed decoded PCM")
                decoded_hashes.append(decoded_pcm_hashes[0])
                rows.append(
                    {
                        "input_id": input_id,
                        "wrapper_id": wrapper_id,
                        "encoded_sha256": encoded_hashes[0],
                        "analysis_decoded_pcm_sha256": decoded_pcm_hashes[0],
                        "encoded_deterministic_across_two_runs": True,
                        "decoded_pcm_deterministic_across_two_runs": True,
                        "decoded_pcm_exactly_matches_input": True,
                    }
                )
            if len(set(decoded_hashes)) != 1:
                raise ValueError("lossless wrappers differ in decoded PCM")
    return rows


def run_probe(
    manifest: dict[str, Any],
    factor: dict[str, Any],
    private_paths: dict[str, Any],
    work_root: Path,
) -> dict[str, Any]:
    validate_manifest(manifest, factor)
    check_free_space(work_root)
    base_config = build_base_probe_config(manifest, private_paths)
    bound, _ = BASE.bind_tools(base_config)
    tool_paths = {tool_id: row["resolved_path"] for tool_id, row in bound.items()}
    with tempfile.TemporaryDirectory(prefix="lossytrace-v2-factor-freeze-", dir=work_root) as name:
        work = Path(name)
        plumbing = BASE.run_probe(base_config, work)
        if plumbing["summary"]["encoder_probe_count"] != 48:
            raise ValueError("expanded encoder probe count differs")
        if plumbing["summary"]["decoder_path_probe_count"] != 132:
            raise ValueError("history decoder path count differs")
        check_free_space(work_root)
        bandwidth = run_bandwidth_observations(manifest, tool_paths, work)
        check_free_space(work_root)
        transform_inputs, transforms = run_transform_golden_probes(
            manifest, tool_paths, work
        )
        wrappers = run_wrapper_golden_probes(manifest, tool_paths, work)

    report = {
        "schema_version": SCHEMA_VERSION,
        "probe_id": PROBE_ID,
        "state": "exact_factor_toolchain_synthetic_evidence_only",
        "toolchain_freeze_binding": {
            "toolchain_freeze_id": manifest["toolchain_freeze_id"],
            "canonical_json_sha256": sha256_json(manifest),
        },
        "factor_binding": manifest["factor_binding"],
        "benchmark_audio_generated": False,
        "source_groups_assigned": False,
        "scores_opened": False,
        "selection_authorized": False,
        "public_verdict_enabled": False,
        "paths_redacted": True,
        "implementation_bindings": {
            "factor_toolchain_probe_sha256": sha256_file(Path(__file__).resolve()),
            "base_toolchain_probe_sha256": sha256_file(BASE_PROBE_PATH),
            "python_version": sys.version.splitlines()[0],
        },
        "plumbing": plumbing,
        "encoder_bandwidth_observations": bandwidth,
        "transform_inputs": transform_inputs,
        "transform_golden_outputs": transforms,
        "wrapper_golden_outputs": wrappers,
        "public_decoder_equivalence": {
            "fresh_synthetic_probe_completed": False,
            "required_before_baseline_scoring": True,
            "prior_observed_container_audit_retained": True,
        },
        "summary": {
            "expanded_setting_count": len(plumbing["encoders"]),
            "history_decoder_path_count": len(plumbing["decoders"]),
            "cross_decoder_exact_pcm_disagreement_count": plumbing["summary"][
                "cross_decoder_exact_pcm_disagreement_count"
            ],
            "bandwidth_observation_count": len(bandwidth),
            "transform_input_count": len(transform_inputs),
            "transform_path_count": len(transforms),
            "wrapper_encode_path_count": len(wrappers),
            "all_encoder_bitstreams_deterministic": True,
            "all_history_decoder_outputs_deterministic": True,
            "all_transform_outputs_deterministic": True,
            "all_lossless_wrappers_decode_to_exact_input_pcm": True,
        },
        "authorized_next_step": (
            "After two byte-identical complete reports and a committed result, "
            "bind and run fresh public-decoder wrapper equivalence before baseline "
            "scoring, then freeze the fractional assignment."
        ),
    }
    sensitive = ["/Users/", "\\Users\\", str(work_root)] + [
        str(path) for path in tool_paths.values()
    ]
    BASE.assert_path_free(report, sensitive)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--factor", required=True, type=Path)
    prepare.add_argument("--prior-evidence", required=True, type=Path)
    prepare.add_argument("--output", required=True, type=Path)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--factor", required=True, type=Path)
    validate.add_argument("--manifest", required=True, type=Path)

    probe = subparsers.add_parser("probe")
    probe.add_argument("--factor", required=True, type=Path)
    probe.add_argument("--manifest", required=True, type=Path)
    probe.add_argument("--private-tool-paths", required=True, type=Path)
    probe.add_argument("--work-root", required=True, type=Path)
    probe.add_argument("--output", required=True, type=Path)

    args = parser.parse_args()
    factor_path = args.factor.expanduser().resolve()
    factor = load_object(factor_path)
    if args.command == "prepare":
        prior_path = args.prior_evidence.expanduser().resolve()
        manifest = build_manifest(
            factor, load_object(prior_path), factor_path, prior_path
        )
        write_json_atomic(args.output.expanduser().resolve(), manifest)
        print(
            f"froze {len(manifest['expanded_encoder_settings'])} settings and "
            f"{len(manifest['history_decoder_bindings'])} decoder implementations"
        )
        return 0
    manifest = load_object(args.manifest.expanduser().resolve())
    if args.command == "validate":
        validate_manifest(manifest, factor)
        print("toolchain freeze is valid")
        return 0
    report = run_probe(
        manifest,
        factor,
        load_object(args.private_tool_paths.expanduser().resolve()),
        args.work_root.expanduser().resolve(),
    )
    write_json_atomic(args.output.expanduser().resolve(), report)
    print(
        f"probed {report['summary']['expanded_setting_count']} settings and "
        f"{report['summary']['history_decoder_path_count']} decoder paths"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
