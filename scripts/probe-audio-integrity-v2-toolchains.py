#!/usr/bin/env python3
"""Run deterministic synthetic plumbing probes for v2 codec toolchains.

The configuration may contain private executable paths. The aggregate report
contains only declared public identities, hashes, sanitized command templates,
and synthetic output hashes. It is plumbing evidence, never benchmark evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any


REPORT_SCHEMA_VERSION = 1
CONFIG_SCHEMA_VERSION = 1
PROBE_GENERATOR_ID = "integer-lcg-multiband-pcm-v1"
SHA256_LENGTH = 64
PUBLIC_TOOL_FIELDS = (
    "tool_id",
    "implementation",
    "version",
    "license",
    "source_revision",
    "source_tree_sha1",
    "license_sha256",
    "build_recipe",
    "operating_system_binding",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def validate_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != SHA256_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def generate_probe_wave(
    path: Path, *, sample_rate_hz: int, frame_count: int, channel_count: int = 2
) -> None:
    """Write deterministic, integer-only PCM with broadband and sparse energy."""
    if sample_rate_hz < 8000 or frame_count < 1 or channel_count not in (1, 2):
        raise ValueError(
            "probe WAV requires mono or stereo, a valid rate, and positive frames"
        )
    states = [0x13579BDF, 0x2468ACE1]
    packed = bytearray()
    impulse_period = max(1, sample_rate_hz // 7)
    for frame in range(frame_count):
        for channel in range(channel_count):
            states[channel] = (1664525 * states[channel] + 1013904223) & 0xFFFFFFFF
            noise = ((states[channel] >> 16) & 0xFFFF) - 32768
            saw_period = 257 + channel * 112
            saw = ((frame * (37 + channel * 16)) % saw_period) * 65535 // saw_period - 32768
            square_period = 89 + channel * 60
            square = 32767 if (frame // square_period) % 2 == 0 else -32768
            impulse = 9000 if (frame + channel * 31) % impulse_period == 0 else 0
            value = noise // 7 + saw // 5 + square // 9 + impulse
            value = max(-32768, min(32767, value))
            packed.extend(struct.pack("<h", value))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channel_count)
        output.setsampwidth(2)
        output.setframerate(sample_rate_hz)
        output.writeframes(bytes(packed))


def wave_pcm_info(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as source:
        channel_count = source.getnchannels()
        sample_width_bytes = source.getsampwidth()
        sample_rate_hz = source.getframerate()
        frame_count = source.getnframes()
        pcm = source.readframes(frame_count)
    return {
        "channel_count": channel_count,
        "sample_width_bytes": sample_width_bytes,
        "sample_rate_hz": sample_rate_hz,
        "frame_count": frame_count,
        "pcm_sha256": sha256_bytes(pcm),
        "wave_sha256": sha256_file(path),
    }


def expand_command(
    template: list[Any], *, tool: str, input_path: Path, output_path: Path
) -> list[str]:
    if not template or not all(isinstance(argument, str) for argument in template):
        raise ValueError("command must be a nonempty list of strings")
    values = {
        "tool": tool,
        "input": str(input_path),
        "output": str(output_path),
    }
    try:
        command = [argument.format(**values) for argument in template]
    except KeyError as error:
        raise ValueError(f"unsupported command placeholder: {error}") from error
    if command[0] != tool:
        raise ValueError("command must invoke {tool} directly")
    return command


def public_command(template: list[Any], tool_id: str) -> list[str]:
    return expand_command(
        template,
        tool=f"<TOOL:{tool_id}>",
        input_path=Path("<INPUT>"),
        output_path=Path("<OUTPUT>"),
    )


def command_sha256(template: list[Any], tool_id: str) -> str:
    canonical = json.dumps(
        public_command(template, tool_id), separators=(",", ":"), ensure_ascii=True
    ).encode()
    return sha256_bytes(canonical)


def process_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "LC_ALL": "C",
            "LANG": "C",
            "TZ": "UTC",
            "SOURCE_DATE_EPOCH": "0",
        }
    )
    return environment


def run_process(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=process_environment(),
        timeout=timeout_seconds,
    )


def require_success(
    completed: subprocess.CompletedProcess[str], *, label: str
) -> None:
    if completed.returncode:
        detail = completed.stderr.strip()[-500:]
        raise ValueError(f"{label} failed with exit {completed.returncode}: {detail}")


def bind_tools(config: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    rows = config.get("tools")
    if not isinstance(rows, list) or not rows:
        raise ValueError("tools must be a nonempty list")
    bound: dict[str, dict[str, Any]] = {}
    public_rows = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"tools[{index}] must be an object")
        tool_id = row.get("tool_id")
        if not isinstance(tool_id, str) or not tool_id or tool_id in bound:
            raise ValueError(f"tools[{index}] has a missing or duplicate tool_id")
        path_value = row.get("path")
        if not isinstance(path_value, str):
            raise ValueError(f"tool {tool_id} path must be a string")
        path = Path(path_value).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"tool {tool_id} does not exist: {path}")
        expected = validate_sha256(row.get("binary_sha256"), f"tool {tool_id} binary_sha256")
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f"tool {tool_id} binary hash differs")
        components = []
        component_rows = row.get("components", [])
        if not isinstance(component_rows, list):
            raise ValueError(f"tool {tool_id} components must be a list")
        for component_index, component in enumerate(component_rows):
            if not isinstance(component, dict):
                raise ValueError(f"tool {tool_id} component {component_index} must be an object")
            component_id = component.get("component_id")
            component_path_value = component.get("path")
            if not isinstance(component_id, str) or not component_id:
                raise ValueError(f"tool {tool_id} component has invalid component_id")
            if not isinstance(component_path_value, str):
                raise ValueError(f"tool {tool_id} component {component_id} path must be a string")
            component_path = Path(component_path_value).expanduser().resolve()
            component_expected = validate_sha256(
                component.get("sha256"), f"tool {tool_id} component {component_id} sha256"
            )
            if not component_path.is_file() or sha256_file(component_path) != component_expected:
                raise ValueError(f"tool {tool_id} component {component_id} hash differs")
            components.append({"component_id": component_id, "sha256": component_expected})
        public = {field: row[field] for field in PUBLIC_TOOL_FIELDS if field in row}
        public["binary_sha256"] = expected
        public["components"] = components
        bound[tool_id] = {**row, "resolved_path": path}
        public_rows.append(public)
    return bound, public_rows


def probe_bitstream(ffprobe: Path, path: Path, timeout_seconds: int) -> dict[str, Any]:
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_name,profile,sample_rate,channels,channel_layout,bit_rate:format=format_name",
        "-of",
        "json",
        str(path),
    ]
    completed = run_process(command, timeout_seconds)
    require_success(completed, label="ffprobe")
    value = json.loads(completed.stdout)
    streams = value.get("streams")
    if not isinstance(streams, list) or len(streams) != 1:
        raise ValueError("ffprobe did not return exactly one audio stream")
    stream = streams[0]
    format_row = value.get("format", {})
    return {
        "codec_name": stream.get("codec_name"),
        "profile": stream.get("profile"),
        "sample_rate_hz": int(stream["sample_rate"]),
        "channel_count": int(stream["channels"]),
        "channel_layout": stream.get("channel_layout"),
        "stream_bit_rate": (
            int(stream["bit_rate"]) if str(stream.get("bit_rate", "")).isdigit() else None
        ),
        "format_name": format_row.get("format_name"),
    }


def validate_bitstream_expectation(row: dict[str, Any], observed: dict[str, Any]) -> None:
    expected = {
        "codec_name": row.get("expected_codec_name"),
        "sample_rate_hz": row.get("expected_sample_rate_hz"),
        "channel_count": row.get("expected_channel_count", 2),
    }
    for field, value in expected.items():
        if observed.get(field) != value:
            raise ValueError(
                f"encoder {row.get('encoder_id')} expected {field}={value!r}, "
                f"observed {observed.get(field)!r}"
            )
    expected_profile = row.get("expected_profile")
    if expected_profile is not None and observed.get("profile") != expected_profile:
        raise ValueError(
            f"encoder {row.get('encoder_id')} expected profile={expected_profile!r}, "
            f"observed {observed.get('profile')!r}"
        )


def run_encoder_probes(
    config: dict[str, Any],
    tools: dict[str, dict[str, Any]],
    inputs: dict[str, Path],
    ffprobe: Path,
    work: Path,
    timeout_seconds: int,
) -> tuple[list[dict[str, Any]], dict[str, tuple[dict[str, Any], Path]]]:
    rows = config.get("encoders")
    if not isinstance(rows, list) or not rows:
        raise ValueError("encoders must be a nonempty list")
    reports = []
    outputs: dict[str, tuple[dict[str, Any], Path]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("encoder row must be an object")
        encoder_id = row.get("encoder_id")
        codec_family = row.get("codec_family")
        tool_id = row.get("tool_id")
        input_id = row.get("input_id")
        extension = row.get("output_extension")
        if (
            not isinstance(encoder_id, str)
            or encoder_id in outputs
            or not isinstance(codec_family, str)
            or tool_id not in tools
            or input_id not in inputs
            or not isinstance(extension, str)
            or not extension.startswith(".")
        ):
            raise ValueError(f"invalid encoder row: {encoder_id!r}")
        tool_path = tools[tool_id]["resolved_path"]
        binding_tool_ids = row.get("binding_tool_ids", [tool_id])
        if (
            not isinstance(binding_tool_ids, list)
            or not binding_tool_ids
            or any(binding_tool_id not in tools for binding_tool_id in binding_tool_ids)
        ):
            raise ValueError(f"encoder {encoder_id} has invalid binding_tool_ids")
        encoded_paths = []
        for run_index in (1, 2):
            output = work / f"{encoder_id}-run{run_index}{extension}"
            command = expand_command(
                row.get("command"),
                tool=str(tool_path),
                input_path=inputs[input_id],
                output_path=output,
            )
            completed = run_process(command, timeout_seconds)
            require_success(completed, label=f"encoder {encoder_id} run {run_index}")
            if not output.is_file() or output.stat().st_size == 0:
                raise ValueError(f"encoder {encoder_id} produced no output")
            encoded_paths.append(output)
        first_hash = sha256_file(encoded_paths[0])
        if sha256_file(encoded_paths[1]) != first_hash:
            raise ValueError(f"encoder {encoder_id} output is not byte-deterministic")
        observed = probe_bitstream(ffprobe, encoded_paths[0], timeout_seconds)
        validate_bitstream_expectation(row, observed)
        report = {
            "encoder_id": encoder_id,
            "codec_family": codec_family,
            "lineage_id": row.get("lineage_id"),
            "tool_id": tool_id,
            "binding_tool_ids": binding_tool_ids,
            "input_id": input_id,
            "command": public_command(row.get("command"), tool_id),
            "command_sha256": command_sha256(row.get("command"), tool_id),
            "byte_deterministic_across_two_runs": True,
            "bitstream_sha256": first_hash,
            "byte_count": encoded_paths[0].stat().st_size,
            "observed": observed,
        }
        reports.append(report)
        outputs[encoder_id] = (row, encoded_paths[0])
    return reports, outputs


def run_decoder_probes(
    config: dict[str, Any],
    tools: dict[str, dict[str, Any]],
    encoder_outputs: dict[str, tuple[dict[str, Any], Path]],
    work: Path,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    rows = config.get("decoders")
    if not isinstance(rows, list) or not rows:
        raise ValueError("decoders must be a nonempty list")
    reports = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("decoder row must be an object")
        decoder_id = row.get("decoder_id")
        tool_id = row.get("tool_id")
        codec_families = row.get("codec_families")
        if (
            not isinstance(decoder_id, str)
            or tool_id not in tools
            or not isinstance(codec_families, list)
            or not codec_families
        ):
            raise ValueError(f"invalid decoder row: {decoder_id!r}")
        tool_path = tools[tool_id]["resolved_path"]
        for encoder_id, (encoder, encoded_path) in encoder_outputs.items():
            if encoder.get("codec_family") not in codec_families:
                continue
            wave_infos = []
            for run_index in (1, 2):
                output = work / f"{decoder_id}-{encoder_id}-run{run_index}.wav"
                command = expand_command(
                    row.get("command"),
                    tool=str(tool_path),
                    input_path=encoded_path,
                    output_path=output,
                )
                completed = run_process(command, timeout_seconds)
                require_success(
                    completed,
                    label=f"decoder {decoder_id} on {encoder_id} run {run_index}",
                )
                if not output.is_file() or output.stat().st_size == 0:
                    raise ValueError(f"decoder {decoder_id} produced no output")
                wave_infos.append(wave_pcm_info(output))
            if wave_infos[0]["pcm_sha256"] != wave_infos[1]["pcm_sha256"]:
                raise ValueError(f"decoder {decoder_id} on {encoder_id} is not PCM-deterministic")
            reports.append(
                {
                    "decoder_id": decoder_id,
                    "tool_id": tool_id,
                    "encoder_id": encoder_id,
                    "codec_family": encoder.get("codec_family"),
                    "command": public_command(row.get("command"), tool_id),
                    "command_sha256": command_sha256(row.get("command"), tool_id),
                    "pcm_deterministic_across_two_runs": True,
                    "wave_container_deterministic_across_two_runs": (
                        wave_infos[0]["wave_sha256"] == wave_infos[1]["wave_sha256"]
                    ),
                    "observed": wave_infos[0],
                }
            )
    return reports


def summarize_cross_decoder_outputs(
    decoder_reports: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in decoder_reports:
        grouped.setdefault(row["encoder_id"], []).append(row)
    summaries = []
    for encoder_id, rows in sorted(grouped.items()):
        pcm_hashes = {row["observed"]["pcm_sha256"] for row in rows}
        frame_counts = {row["observed"]["frame_count"] for row in rows}
        summaries.append(
            {
                "encoder_id": encoder_id,
                "decoder_count": len(rows),
                "exact_pcm_equivalent_across_decoders": len(pcm_hashes) == 1,
                "frame_count_equivalent_across_decoders": len(frame_counts) == 1,
            }
        )
    return summaries


def sanitized_failure(value: str, sensitive: list[str]) -> str:
    sanitized = value
    for item in sorted(sensitive, key=len, reverse=True):
        if item:
            sanitized = sanitized.replace(item, "<PRIVATE>")
    return sanitized.strip()


def run_capability_rejections(
    config: dict[str, Any],
    tools: dict[str, dict[str, Any]],
    inputs: dict[str, Path],
    work: Path,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    rows = config.get("expected_capability_rejections", [])
    if not isinstance(rows, list):
        raise ValueError("expected_capability_rejections must be a list")
    reports = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("capability rejection row must be an object")
        probe_id = row.get("probe_id")
        tool_id = row.get("tool_id")
        input_id = row.get("input_id")
        extension = row.get("output_extension")
        if (
            not isinstance(probe_id, str)
            or tool_id not in tools
            or input_id not in inputs
            or not isinstance(extension, str)
        ):
            raise ValueError(f"invalid capability rejection row: {probe_id!r}")
        tool_path = tools[tool_id]["resolved_path"]
        failure_hashes = []
        return_codes = []
        for run_index in (1, 2):
            output = work / f"{probe_id}-run{run_index}{extension}"
            command = expand_command(
                row.get("command"),
                tool=str(tool_path),
                input_path=inputs[input_id],
                output_path=output,
            )
            completed = run_process(command, timeout_seconds)
            if completed.returncode == 0 or (output.exists() and output.stat().st_size):
                raise ValueError(f"capability rejection {probe_id} unexpectedly succeeded")
            sensitive = [str(tool_path), str(inputs[input_id]), str(output), str(work)]
            failure = sanitized_failure(completed.stderr, sensitive)
            return_codes.append(completed.returncode)
            failure_hashes.append(sha256_bytes(failure.encode()))
        if return_codes[0] != return_codes[1] or failure_hashes[0] != failure_hashes[1]:
            raise ValueError(f"capability rejection {probe_id} was not reproducible")
        reports.append(
            {
                "probe_id": probe_id,
                "tool_id": tool_id,
                "input_id": input_id,
                "command": public_command(row.get("command"), tool_id),
                "command_sha256": command_sha256(row.get("command"), tool_id),
                "observed_outcome": "rejected_without_output",
                "return_code": return_codes[0],
                "sanitized_stderr_sha256": failure_hashes[0],
                "reproducible_across_two_runs": True,
            }
        )
    return reports


def assert_path_free(report: dict[str, Any], sensitive: list[str]) -> None:
    serialized = json.dumps(report, sort_keys=True)
    leaked = [value for value in sensitive if value and value in serialized]
    if leaked:
        raise ValueError("aggregate report contains a private path")


def run_probe(config: dict[str, Any], work_root: Path) -> dict[str, Any]:
    if config.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise ValueError(f"config schema_version must equal {CONFIG_SCHEMA_VERSION}")
    probe_id = config.get("probe_id")
    if not isinstance(probe_id, str) or not probe_id:
        raise ValueError("probe_id must be a nonempty string")
    timeout_seconds = config.get("timeout_seconds", 60)
    if not isinstance(timeout_seconds, int) or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    tools, public_tools = bind_tools(config)
    ffprobe_tool_id = config.get("ffprobe_tool_id")
    if ffprobe_tool_id not in tools:
        raise ValueError("ffprobe_tool_id must reference a bound tool")
    input_rows = config.get("inputs")
    if not isinstance(input_rows, list) or not input_rows:
        raise ValueError("inputs must be a nonempty list")

    work_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lossytrace-v2-tool-probe-", dir=work_root) as name:
        work = Path(name)
        inputs: dict[str, Path] = {}
        public_inputs = []
        for row in input_rows:
            if not isinstance(row, dict):
                raise ValueError("input row must be an object")
            input_id = row.get("input_id")
            sample_rate_hz = row.get("sample_rate_hz")
            frame_count = row.get("frame_count")
            channel_count = row.get("channel_count", 2)
            if (
                not isinstance(input_id, str)
                or input_id in inputs
                or not isinstance(sample_rate_hz, int)
                or not isinstance(frame_count, int)
                or channel_count not in (1, 2)
            ):
                raise ValueError(f"invalid input row: {input_id!r}")
            path = work / f"{input_id}.wav"
            generate_probe_wave(
                path,
                sample_rate_hz=sample_rate_hz,
                frame_count=frame_count,
                channel_count=channel_count,
            )
            inputs[input_id] = path
            public_inputs.append(
                {
                    "input_id": input_id,
                    "generator_id": PROBE_GENERATOR_ID,
                    **wave_pcm_info(path),
                }
            )

        encoder_reports, encoder_outputs = run_encoder_probes(
            config,
            tools,
            inputs,
            tools[ffprobe_tool_id]["resolved_path"],
            work,
            timeout_seconds,
        )
        decoder_reports = run_decoder_probes(
            config, tools, encoder_outputs, work, timeout_seconds
        )
        cross_decoder_reports = summarize_cross_decoder_outputs(decoder_reports)
        rejection_reports = run_capability_rejections(
            config, tools, inputs, work, timeout_seconds
        )
        report = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "probe_id": probe_id,
            "state": "synthetic_plumbing_evidence_only",
            "benchmark_audio_generated": False,
            "synthetic_probe_audio_generated": True,
            "scores_opened": False,
            "selection_authorized": False,
            "paths_redacted": True,
            "environment": config.get("public_environment"),
            "tools": public_tools,
            "inputs": public_inputs,
            "encoders": encoder_reports,
            "decoders": decoder_reports,
            "cross_decoder_summary": cross_decoder_reports,
            "expected_capability_rejections": rejection_reports,
            "summary": {
                "encoder_probe_count": len(encoder_reports),
                "decoder_path_probe_count": len(decoder_reports),
                "expected_capability_rejection_count": len(rejection_reports),
                "cross_decoder_exact_pcm_disagreement_count": sum(
                    not row["exact_pcm_equivalent_across_decoders"]
                    for row in cross_decoder_reports
                ),
                "all_required_encoder_bitstreams_deterministic": True,
                "all_required_decoder_pcm_outputs_deterministic": True,
            },
        }
        sensitive = ["/Users/", "\\Users\\", str(work_root), str(work)] + [
            str(row["resolved_path"]) for row in tools.values()
        ]
        assert_path_free(report, sensitive)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run_probe(load_object(args.config), args.work_root.expanduser().resolve())
    write_json_atomic(args.output.expanduser().resolve(), report)
    print(
        f"probed {report['summary']['encoder_probe_count']} encoders and "
        f"{report['summary']['decoder_path_probe_count']} decoder paths"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
