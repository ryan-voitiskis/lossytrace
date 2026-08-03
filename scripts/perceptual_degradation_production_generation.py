#!/usr/bin/env python3
"""Deterministic synthetic production and codec-generation control replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/production-generation-control-plan.json"
)
DEFAULT_EXECUTION_PLAN = (
    ROOT
    / "benchmarks/perceptual-degradation-v1/production-generation-execution-plan.json"
)
EXECUTION_BINDING_PATHS = {
    "recipe_plan": DEFAULT_PLAN,
    "recipe_plan_validator": (
        ROOT / "scripts/validate-perceptual-degradation-production-generation-plan.py"
    ),
    "recipe_plan_validator_tests": (
        ROOT / "scripts/tests/test_perceptual_degradation_production_generation_plan.py"
    ),
    "preregistration": (
        ROOT
        / "docs/research/perceptual-degradation-production-generation-control-preregistration-20260804.md"
    ),
    "implementation": Path(__file__).resolve(),
    "implementation_tests": (
        ROOT / "scripts/tests/test_perceptual_degradation_production_generation.py"
    ),
    "execution_plan_validator": (
        ROOT
        / "scripts/validate-perceptual-degradation-production-generation-execution-plan.py"
    ),
    "execution_plan_validator_tests": (
        ROOT
        / "scripts/tests/test_perceptual_degradation_production_generation_execution_plan.py"
    ),
}
TOOL_TOKEN_PREFIX = "<TOOL:"
INPUT_TOKEN = "<INPUT>"
OUTPUT_TOKEN = "<OUTPUT>"
TOOL_EXECUTABLES = {
    "ffmpeg_8_1_2_1": "ffmpeg",
    "lame_cli_4_0": "lame",
    "opusenc_0_2_2_libopus_1_6_1": "opusenc",
    "oggenc_1_4_3_libvorbis_1_3_7": "oggenc",
}
PRODUCTION_RECIPE_IDS = {
    "production-hard-clip-minus6dbfs-v1",
    "production-high-shelf-minus6db-nyquist-fir3-v1",
    "production-block-limiter-minus6dbfs-5ms-v1",
    "production-stereo-width-half-mid-side-v1",
}
EXECUTION_AUTHORITY = {
    "synthetic_execution_authorized": True,
    "actual_source_audio_authorized": False,
    "provider_audio_authorized": False,
    "perceptual_metric_execution_authorized": False,
    "human_collection_authorized": False,
    "sealed_evidence_access_authorized": False,
}
REPLAY_PROTOCOL = {
    "fresh_temporary_directories": True,
    "replay_count": 2,
    "byte_identical_reports_required": True,
    "path_free_reports_required": True,
    "timing_fields_forbidden": True,
    "retain_generated_audio": False,
    "minimum_free_disk_gib": 15,
}
RESAMPLE_FILTER_TEMPLATE = (
    "aresample={target}:osf=s16:resampler=swr:filter_size=64:phase_shift=10:"
    "linear_interp=0:exact_rational=1:cutoff=0.95:filter_type=kaiser:"
    "kaiser_beta=9:dither_method=none"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    return value


def round_ratio_ties_even(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    doubled = remainder * 2
    if doubled > denominator or (doubled == denominator and quotient % 2):
        quotient += 1
    return sign * quotient


def saturate_s16(value: int) -> int:
    return max(-32768, min(32767, value))


def pcm_bytes(samples: Iterable[int]) -> bytes:
    values = list(samples)
    if any(value < -32768 or value > 32767 for value in values):
        raise ValueError("sample is outside signed-16 range")
    return struct.pack(f"<{len(values)}h", *values)


def changed_frame_count(reference: list[int], candidate: list[int], channels: int) -> int:
    if channels not in (1, 2) or len(reference) != len(candidate):
        raise ValueError("PCM shape differs")
    if len(reference) % channels:
        raise ValueError("PCM is not frame aligned")
    return sum(
        reference[offset : offset + channels] != candidate[offset : offset + channels]
        for offset in range(0, len(reference), channels)
    )


def apply_production_control(
    recipe_id: str, sample_rate_hz: int, channels: int, samples: list[int]
) -> list[int]:
    if sample_rate_hz not in (44100, 48000):
        raise ValueError("sample rate differs")
    if channels not in (1, 2) or not samples or len(samples) % channels:
        raise ValueError("PCM shape differs")
    if any(value < -32768 or value > 32767 for value in samples):
        raise ValueError("sample is outside signed-16 range")

    if recipe_id == "production-hard-clip-minus6dbfs-v1":
        return [max(-16384, min(16384, value)) for value in samples]

    if recipe_id == "production-high-shelf-minus6db-nyquist-fir3-v1":
        frame_count = len(samples) // channels
        output: list[int] = []
        for frame in range(frame_count):
            prior = max(0, frame - 1)
            following = min(frame_count - 1, frame + 1)
            for channel in range(channels):
                value = round_ratio_ties_even(
                    samples[prior * channels + channel]
                    + 6 * samples[frame * channels + channel]
                    + samples[following * channels + channel],
                    8,
                )
                output.append(saturate_s16(value))
        return output

    if recipe_id == "production-block-limiter-minus6dbfs-5ms-v1":
        frame_count = len(samples) // channels
        block_frames = (sample_rate_hz + 199) // 200
        output = samples.copy()
        for start_frame in range(0, frame_count, block_frames):
            end_frame = min(frame_count, start_frame + block_frames)
            start = start_frame * channels
            end = end_frame * channels
            peak = max(abs(value) for value in samples[start:end])
            if peak <= 16384:
                continue
            for index in range(start, end):
                output[index] = saturate_s16(
                    round_ratio_ties_even(samples[index] * 16384, peak)
                )
        return output

    if recipe_id == "production-stereo-width-half-mid-side-v1":
        if channels != 2:
            raise ValueError("stereo-width control requires stereo")
        output = []
        for index in range(0, len(samples), 2):
            left, right = samples[index : index + 2]
            output.extend(
                (
                    saturate_s16(round_ratio_ties_even(3 * left + right, 4)),
                    saturate_s16(round_ratio_ties_even(left + 3 * right, 4)),
                )
            )
        return output

    raise ValueError(f"unknown production recipe: {recipe_id}")


def synthetic_samples(recipe_id: str, sample_rate_hz: int, seconds: int = 2) -> list[int]:
    if seconds < 1 or sample_rate_hz not in (44100, 48000):
        raise ValueError("synthetic fixture geometry differs")
    phase = int.from_bytes(hashlib.sha256(recipe_id.encode()).digest()[:4], "big")
    samples = []
    for frame in range(sample_rate_hz * seconds):
        saw_left = ((frame * 7919 + phase) % 65536) - 32768
        saw_right = ((frame * 6151 + phase // 3) % 65536) - 32768
        pulse = 26000 if (frame // max(1, sample_rate_hz // 20)) % 2 == 0 else -26000
        left = saturate_s16(round_ratio_ties_even(3 * saw_left + pulse, 4))
        right = saturate_s16(round_ratio_ties_even(3 * saw_right - pulse, 4))
        samples.extend((left, right))
    return samples


def write_wave(
    path: Path, sample_rate_hz: int, channels: int, samples: Iterable[int]
) -> None:
    payload = pcm_bytes(samples)
    if channels not in (1, 2) or len(payload) % (2 * channels):
        raise ValueError("WAV shape differs")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(sample_rate_hz)
        output.writeframes(payload)


def tool_paths(toolchain: dict[str, Any], required_tool_ids: set[str]) -> dict[str, Path]:
    bindings = {
        item.get("tool_id"): item for item in toolchain.get("tool_bindings", [])
    }
    resolved: dict[str, Path] = {}
    for tool_id in sorted(required_tool_ids):
        executable = TOOL_EXECUTABLES.get(tool_id)
        binding = bindings.get(tool_id)
        found = shutil.which(executable) if executable else None
        if binding is None or found is None:
            raise ValueError(f"required tool unavailable: {tool_id}")
        path = Path(found).resolve()
        if sha256_file(path) != binding.get("binary_sha256"):
            raise ValueError(f"required tool hash differs: {tool_id}")
        resolved[tool_id] = path
    return resolved


def expanded_command(
    command: list[str], tools: dict[str, Path], input_path: Path, output_path: Path
) -> list[str]:
    result = []
    for part in command:
        if part.startswith(TOOL_TOKEN_PREFIX) and part.endswith(">"):
            tool_id = part[len(TOOL_TOKEN_PREFIX) : -1]
            if tool_id not in tools:
                raise ValueError(f"unbound tool token: {tool_id}")
            result.append(str(tools[tool_id]))
        elif part == INPUT_TOKEN:
            result.append(str(input_path))
        elif part == OUTPUT_TOKEN:
            result.append(str(output_path))
        elif part.startswith("<") and part.endswith(">"):
            raise ValueError(f"unknown command token: {part}")
        else:
            result.append(part)
    return result


def process_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {"LC_ALL": "C", "LANG": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "0"}
    )
    return environment


def require_disk_reserve(path: Path, minimum_free_gib: int) -> None:
    if minimum_free_gib < 1:
        raise ValueError("minimum free disk threshold differs")
    if shutil.disk_usage(path).free < minimum_free_gib * 1024**3:
        raise ValueError(f"free disk is below {minimum_free_gib} GiB reserve")


def run_command(command: list[str]) -> None:
    completed = subprocess.run(
        command,
        capture_output=True,
        env=process_environment(),
        stdin=subprocess.DEVNULL,
        timeout=120,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.decode(errors="replace").strip()[-500:]
        raise ValueError(f"codec command failed with exit {completed.returncode}: {detail}")


def decode_stage(
    *,
    decoder_command: list[str],
    tools: dict[str, Path],
    bitstream_path: Path,
    raw_path: Path,
) -> bytes:
    run_command(expanded_command(decoder_command, tools, bitstream_path, raw_path))
    payload = raw_path.read_bytes()
    if not payload or len(payload) % 4:
        raise ValueError("decoded stereo signed-16 PCM shape differs")
    return payload


def resample_stage(
    *,
    ffmpeg: Path,
    input_path: Path,
    output_path: Path,
    source_rate_hz: int,
    target_rate_hz: int,
) -> bytes:
    if source_rate_hz not in (44100, 48000) or target_rate_hz not in (44100, 48000):
        raise ValueError("resampling rate differs")
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-fflags",
        "+bitexact",
        "-f",
        "s16le",
        "-ar",
        str(source_rate_hz),
        "-ac",
        "2",
        "-i",
        str(input_path),
        "-map",
        "0:a:0",
        "-af",
        RESAMPLE_FILTER_TEMPLATE.format(target=target_rate_hz),
        "-ar",
        str(target_rate_hz),
        "-ac",
        "2",
        "-c:a",
        "pcm_s16le",
        "-f",
        "s16le",
        "-fflags",
        "+bitexact",
        str(output_path),
    ]
    run_command(command)
    payload = output_path.read_bytes()
    if not payload or len(payload) % 4:
        raise ValueError("resampled stereo signed-16 PCM shape differs")
    return payload


def replay_production_case(
    recipe: dict[str, Any], support_threshold: float
) -> dict[str, Any]:
    recipe_id = recipe["recipe_id"]
    sample_rate_hz = 48000
    channels = 2
    samples = synthetic_samples(recipe_id, sample_rate_hz)
    output = apply_production_control(recipe_id, sample_rate_hz, channels, samples)
    changed = changed_frame_count(samples, output, channels)
    frame_count = len(samples) // channels
    fraction = changed / frame_count
    return {
        "recipe_id": recipe_id,
        "family": recipe["family"],
        "sample_rate_hz": sample_rate_hz,
        "channel_count": channels,
        "frame_count": frame_count,
        "input_pcm_sha256": sha256_bytes(pcm_bytes(samples)),
        "output_pcm_sha256": sha256_bytes(pcm_bytes(output)),
        "changed_frame_count": changed,
        "changed_frame_fraction": fraction,
        "support_passed": fraction >= support_threshold,
        "perceptual_truth_included": False,
    }


def replay_generation_case(
    recipe: dict[str, Any],
    settings: dict[str, dict[str, Any]],
    decoder_command: list[str],
    tools: dict[str, Path],
    root: Path,
) -> dict[str, Any]:
    recipe_id = recipe["recipe_id"]
    selected = [settings[setting_id] for setting_id in recipe["expanded_setting_ids"]]
    first_rate = selected[0]["expected_sample_rate_hz"]
    samples = synthetic_samples(recipe_id, first_rate)
    input_wave = root / "input.wav"
    write_wave(input_wave, first_rate, 2, samples)
    current_wave = input_wave
    current_pcm = pcm_bytes(samples)
    stages = []
    for index, setting in enumerate(selected, start=1):
        bitstream = root / f"generation-{index}{setting['output_extension']}"
        run_command(
            expanded_command(setting["command"], tools, current_wave, bitstream)
        )
        raw = root / f"generation-{index}.s16le"
        decoded = decode_stage(
            decoder_command=decoder_command,
            tools=tools,
            bitstream_path=bitstream,
            raw_path=raw,
        )
        next_setting = selected[index] if index < len(selected) else None
        next_rate = (
            next_setting["expected_sample_rate_hz"]
            if next_setting is not None
            else setting["expected_sample_rate_hz"]
        )
        transition_pcm = decoded
        resampling_applied = next_rate != setting["expected_sample_rate_hz"]
        if resampling_applied:
            resampled = root / f"generation-{index}-resampled.s16le"
            transition_pcm = resample_stage(
                ffmpeg=tools["ffmpeg_8_1_2_1"],
                input_path=raw,
                output_path=resampled,
                source_rate_hz=setting["expected_sample_rate_hz"],
                target_rate_hz=next_rate,
            )
        next_wave = root / f"generation-{index}.wav"
        decoded_samples = list(
            struct.unpack(f"<{len(transition_pcm) // 2}h", transition_pcm)
        )
        write_wave(
            next_wave,
            next_rate,
            setting["expected_channel_count"],
            decoded_samples,
        )
        stages.append(
            {
                "generation": index,
                "expanded_setting_id": setting["expanded_setting_id"],
                "codec_family": setting["codec_family"],
                "encoder_id": setting["encoder_id"],
                "tool_id": setting["tool_id"],
                "encoder_input_pcm_bytes": len(current_pcm),
                "encoder_input_pcm_sha256": sha256_bytes(current_pcm),
                "sample_rate_hz": setting["expected_sample_rate_hz"],
                "channel_count": setting["expected_channel_count"],
                "bitstream_bytes": bitstream.stat().st_size,
                "bitstream_sha256": sha256_file(bitstream),
                "decoded_pcm_bytes": len(decoded),
                "decoded_pcm_sha256": sha256_bytes(decoded),
                "decoded_frame_count": len(decoded) // (2 * setting["expected_channel_count"]),
                "next_generation_input": (
                    {
                        "resampling_applied": resampling_applied,
                        "sample_rate_hz": next_rate,
                        "pcm_bytes": len(transition_pcm),
                        "pcm_sha256": sha256_bytes(transition_pcm),
                        "frame_count": len(transition_pcm) // 4,
                    }
                    if next_setting is not None
                    else None
                ),
            }
        )
        current_wave = next_wave
        current_pcm = transition_pcm
    return {
        "recipe_id": recipe_id,
        "family": recipe["family"],
        "input_sample_rate_hz": first_rate,
        "input_channel_count": 2,
        "input_frame_count": len(samples) // 2,
        "input_pcm_sha256": sha256_bytes(pcm_bytes(samples)),
        "stages": stages,
        "perceptual_truth_included": False,
    }


def validate_execution_authority(
    plan_path: Path,
    execution_plan_path: Path,
    implementation_path: Path = Path(__file__).resolve(),
) -> dict[str, Any]:
    execution = load_json(execution_plan_path)
    if execution.get("state") != "synthetic_execution_authorized_actual_audio_forbidden":
        raise ValueError("synthetic execution authority differs")
    authority = execution.get("authority", {})
    if authority != EXECUTION_AUTHORITY:
        raise ValueError("execution authority differs")
    if execution.get("replay_protocol") != REPLAY_PROTOCOL:
        raise ValueError("replay protocol differs")
    bindings = execution.get("bindings", {})
    expected = EXECUTION_BINDING_PATHS | {
        "recipe_plan": plan_path,
        "implementation": implementation_path,
    }
    if set(bindings) != set(expected):
        raise ValueError("execution binding set differs")
    for binding_id, path in expected.items():
        binding = bindings.get(binding_id, {})
        if binding.get("path") != str(path.relative_to(ROOT)):
            raise ValueError(f"execution binding path differs: {binding_id}")
        if binding.get("sha256") != sha256_file(path):
            raise ValueError(f"execution binding hash differs: {binding_id}")
    recipe_plan = load_json(plan_path)
    expected_cases = {
        item["recipe_id"]
        for section in ("production_control_recipes", "codec_generation_recipes")
        for item in recipe_plan[section]
    }
    cases = execution.get("synthetic_cases", [])
    if len(cases) != 12 or set(cases) != expected_cases:
        raise ValueError("synthetic case set differs")
    decision = execution.get("decision", {})
    if decision.get("implementation_hash_frozen") is not True or any(
        decision.get(field) is not False
        for field in (
            "synthetic_execution_observed",
            "actual_audio_accessed",
            "stimuli_generated",
            "perceptual_metric_executed",
            "listener_response_collected",
        )
    ):
        raise ValueError("execution decision differs")
    return execution


def build_report(plan_path: Path, execution_plan_path: Path) -> dict[str, Any]:
    execution = validate_execution_authority(plan_path, execution_plan_path)
    require_disk_reserve(
        ROOT, execution["replay_protocol"]["minimum_free_disk_gib"]
    )
    plan = load_json(plan_path)
    production_recipes = plan.get("production_control_recipes", [])
    generation_recipes = plan.get("codec_generation_recipes", [])
    if {item.get("recipe_id") for item in production_recipes} != PRODUCTION_RECIPE_IDS:
        raise ValueError("production recipe set differs")
    if len(generation_recipes) != 8 or any(
        len(item.get("expanded_setting_ids", [])) != 2 for item in generation_recipes
    ):
        raise ValueError("codec generation recipe set differs")
    resampler = plan.get("codec_generation_execution", {}).get(
        "intermediate_resampler", {}
    )
    if (
        resampler.get("tool_id") != "ffmpeg_8_1_2_1"
        or resampler.get("filter_template") != RESAMPLE_FILTER_TEMPLATE
    ):
        raise ValueError("intermediate resampler binding differs")
    toolchain_binding = plan["bindings"]["v2_toolchain_bindings"]
    toolchain_path = ROOT / toolchain_binding["path"]
    if sha256_file(toolchain_path) != toolchain_binding["sha256"]:
        raise ValueError("toolchain binding differs")
    toolchain = load_json(toolchain_path)
    settings = {
        item["expanded_setting_id"]: item
        for item in toolchain["expanded_encoder_settings"]
    }
    required_settings = {
        setting_id
        for recipe in generation_recipes
        for setting_id in recipe["expanded_setting_ids"]
    }
    if not required_settings <= set(settings):
        raise ValueError("generation setting is absent from toolchain")
    required_tool_ids = {toolchain["analysis_decoder_binding"]["tool_id"]}
    required_tool_ids.update(settings[item]["tool_id"] for item in required_settings)
    tools = tool_paths(toolchain, required_tool_ids)
    production = [
        replay_production_case(
            recipe, plan["input_contract"]["minimum_changed_frame_fraction"]
        )
        for recipe in production_recipes
    ]
    with tempfile.TemporaryDirectory(prefix="lossytrace-pg-replay-") as temporary:
        temporary_root = Path(temporary)
        generations = []
        for recipe in generation_recipes:
            case_root = temporary_root / recipe["recipe_id"]
            case_root.mkdir()
            generations.append(
                replay_generation_case(
                    recipe,
                    settings,
                    toolchain["analysis_decoder_binding"]["command"],
                    tools,
                    case_root,
                )
            )
    tool_bindings = {
        item["tool_id"]: item
        for item in toolchain["tool_bindings"]
        if item.get("tool_id") in required_tool_ids
    }
    return {
        "schema_version": 1,
        "report_id": "perceptual-degradation-production-generation-synthetic-replay-20260804-001",
        "state": "synthetic_execution_observed_actual_audio_unopened",
        "bindings": {
            "recipe_plan_sha256": sha256_file(plan_path),
            "execution_plan_sha256": sha256_file(execution_plan_path),
            "implementation_sha256": sha256_file(Path(__file__).resolve()),
        },
        "authority": execution["authority"],
        "tools": [
            {
                "tool_id": tool_id,
                "binary_sha256": tool_bindings[tool_id]["binary_sha256"],
                "version": tool_bindings[tool_id]["version"],
            }
            for tool_id in sorted(required_tool_ids)
        ],
        "production_cases": production,
        "generation_cases": generations,
        "summary": {
            "synthetic_case_count": len(production) + len(generations),
            "production_case_count": len(production),
            "generation_case_count": len(generations),
            "production_support_pass_count": sum(
                item["support_passed"] for item in production
            ),
            "codec_family_count": len(
                {
                    stage["codec_family"]
                    for case in generations
                    for stage in case["stages"]
                }
            ),
            "perceptual_truth_included": False,
            "paths_included": False,
            "timing_included": False,
            "actual_audio_accessed": False,
            "metric_score_opened": False,
            "listener_response_collected": False,
            "minimum_free_disk_gib_enforced": REPLAY_PROTOCOL[
                "minimum_free_disk_gib"
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--execution-plan", type=Path, default=DEFAULT_EXECUTION_PLAN)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit(f"refusing to replace output: {args.output}")
    report = build_report(args.plan.resolve(), args.execution_plan.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output_sha256": sha256_file(args.output),
                "status": report["state"],
                "synthetic_case_count": report["summary"]["synthetic_case_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
