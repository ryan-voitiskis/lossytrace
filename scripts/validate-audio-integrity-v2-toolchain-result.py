#!/usr/bin/env python3
"""Validate the path-free factorial-v2 exact-toolchain replay result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_REPORT_SHA256 = (
    "29ddfe00bb419aedcbdee8de530785f5981de279f2bd190f4a337ebbe8c3cc23"
)
EXPECTED_FACTOR_PROBE_SHA256 = (
    "21fa31de0b0783f05d55dcd8e78b8d0c39c12c358d88dc641cf88ad0f64ee78e"
)
EXPECTED_BASE_PROBE_SHA256 = (
    "ea6ae02980421c720a86093c8169d5de91c2f9d08a1ad4541f57adaa0df0403e"
)


def load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


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


def validate(
    report: dict[str, Any],
    manifest: dict[str, Any],
    factor: dict[str, Any],
    report_path: Path,
    repository_root: Path,
) -> list[str]:
    errors: list[str] = []
    expected_state = {
        "schema_version": 1,
        "probe_id": "lossytrace-v2-factor-toolchain-probe-20260802-004",
        "state": "exact_factor_toolchain_synthetic_evidence_only",
        "benchmark_audio_generated": False,
        "source_groups_assigned": False,
        "scores_opened": False,
        "selection_authorized": False,
        "public_verdict_enabled": False,
        "paths_redacted": True,
    }
    for field, expected in expected_state.items():
        if report.get(field) != expected:
            errors.append(f"report {field} differs")
    if sha256_file(report_path) != EXPECTED_REPORT_SHA256:
        errors.append("committed report hash differs")

    freeze_binding = report.get("toolchain_freeze_binding", {})
    if (
        freeze_binding.get("toolchain_freeze_id")
        != manifest.get("toolchain_freeze_id")
        or freeze_binding.get("canonical_json_sha256") != sha256_json(manifest)
    ):
        errors.append("toolchain manifest binding differs")
    if report.get("factor_binding") != manifest.get("factor_binding") or (
        manifest.get("factor_binding", {}).get("factor_freeze_id")
        != factor.get("factor_freeze_id")
    ):
        errors.append("factor binding differs")

    implementation = report.get("implementation_bindings", {})
    factor_probe_path = repository_root / "scripts/freeze-audio-integrity-v2-toolchains.py"
    base_probe_path = repository_root / "scripts/probe-audio-integrity-v2-toolchains.py"
    if (
        implementation.get("factor_toolchain_probe_sha256")
        != EXPECTED_FACTOR_PROBE_SHA256
        or implementation.get("factor_toolchain_probe_sha256")
        != sha256_file(factor_probe_path)
        or implementation.get("base_toolchain_probe_sha256")
        != EXPECTED_BASE_PROBE_SHA256
        or implementation.get("base_toolchain_probe_sha256")
        != sha256_file(base_probe_path)
    ):
        errors.append("probe implementation binding differs")

    plumbing = report.get("plumbing", {})
    if plumbing.get("tools") != manifest.get("tool_bindings"):
        errors.append("public tool bindings differ")
    settings = {
        row["expanded_setting_id"]: row
        for row in manifest.get("expanded_encoder_settings", [])
    }
    encoders = {
        row.get("encoder_id"): row for row in plumbing.get("encoders", [])
    }
    if set(encoders) != set(settings) or len(encoders) != 46:
        errors.append("expanded setting result identities differ")
    else:
        for setting_id, setting in settings.items():
            observed = encoders[setting_id]
            expected_fields = {
                "codec_family": setting["codec_family"],
                "lineage_id": setting["lineage_id"],
                "tool_id": setting["tool_id"],
                "binding_tool_ids": setting["binding_tool_ids"],
                "input_id": setting["input_id"],
                "command": setting["command"],
                "byte_deterministic_across_two_runs": True,
            }
            if any(observed.get(field) != value for field, value in expected_fields.items()):
                errors.append(f"encoder result differs for {setting_id}")
            stream = observed.get("observed", {})
            if (
                stream.get("codec_name") != setting["expected_codec_name"]
                or stream.get("sample_rate_hz") != setting["expected_sample_rate_hz"]
                or stream.get("channel_count") != setting["expected_channel_count"]
                or (
                    setting.get("expected_profile") is not None
                    and stream.get("profile") != setting["expected_profile"]
                )
            ):
                errors.append(f"encoder stream realization differs for {setting_id}")

    decoder_bindings = {
        row["history_decoder_id"]: row
        for row in manifest.get("history_decoder_bindings", [])
    }
    expected_decoder_pairs = {
        (decoder_id, setting_id)
        for decoder_id, decoder in decoder_bindings.items()
        for setting_id, setting in settings.items()
        if setting["codec_family"] in decoder["codec_families"]
    }
    decoder_rows = plumbing.get("decoders", [])
    observed_decoder_pairs = {
        (row.get("decoder_id"), row.get("encoder_id")) for row in decoder_rows
    }
    if len(decoder_rows) != 126 or observed_decoder_pairs != expected_decoder_pairs:
        errors.append("history decoder path identities differ")
    for row in decoder_rows:
        binding = decoder_bindings.get(row.get("decoder_id"), {})
        if (
            row.get("command") != binding.get("command")
            or row.get("pcm_deterministic_across_two_runs") is not True
            or row.get("wave_container_deterministic_across_two_runs") is not True
        ):
            errors.append(
                f"history decoder result differs for {row.get('decoder_id')} / "
                f"{row.get('encoder_id')}"
            )

    cross_rows = plumbing.get("cross_decoder_summary", [])
    if (
        len(cross_rows) != 46
        or {row.get("encoder_id") for row in cross_rows} != set(settings)
        or sum(row.get("exact_pcm_equivalent_across_decoders") is False for row in cross_rows)
        != report.get("summary", {}).get("cross_decoder_exact_pcm_disagreement_count")
    ):
        errors.append("cross-decoder summary differs")

    bandwidth_rows = report.get("encoder_bandwidth_observations", [])
    if (
        len(bandwidth_rows) != 46
        or {row.get("expanded_setting_id") for row in bandwidth_rows} != set(settings)
    ):
        errors.append("bandwidth observation identities differ")
    frequency_contract = manifest.get("encoder_bandwidth_observation", {}).get(
        "frequencies_hz_by_sample_rate", {}
    )
    for row in bandwidth_rows:
        setting = settings.get(row.get("expanded_setting_id"), {})
        expected_frequencies = frequency_contract.get(
            str(setting.get("expected_sample_rate_hz")), []
        )
        if (
            [level.get("frequency_hz") for level in row.get("relative_levels", [])]
            != expected_frequencies
            or row.get("claim_boundary")
            != "coarse decoded retention edge, not exact encoder cutoff"
        ):
            errors.append(
                f"bandwidth observation differs for {row.get('expanded_setting_id')}"
            )

    input_ids = {row.get("input_id") for row in report.get("transform_inputs", [])}
    ordinary_transform_ids = {
        row["transform_id"]
        for row in manifest.get("pcm_transform_bindings", [])
        if row["transform_id"] != "lossless-wrapper-rewrite"
    }
    transform_rows = report.get("transform_golden_outputs", [])
    if (
        len(input_ids) != 4
        or len(transform_rows) != 36
        or {(row.get("input_id"), row.get("transform_id")) for row in transform_rows}
        != {(input_id, transform_id) for input_id in input_ids for transform_id in ordinary_transform_ids}
        or any(row.get("deterministic_across_two_runs") is not True for row in transform_rows)
    ):
        errors.append("transform golden outputs differ")

    wrapper_ids = {row["wrapper_id"] for row in manifest.get("wrapper_bindings", [])}
    wrapper_rows = report.get("wrapper_golden_outputs", [])
    if (
        len(wrapper_rows) != 12
        or {(row.get("input_id"), row.get("wrapper_id")) for row in wrapper_rows}
        != {(input_id, wrapper_id) for input_id in input_ids for wrapper_id in wrapper_ids}
        or any(
            row.get("encoded_deterministic_across_two_runs") is not True
            or row.get("decoded_pcm_deterministic_across_two_runs") is not True
            or row.get("decoded_pcm_exactly_matches_input") is not True
            for row in wrapper_rows
        )
    ):
        errors.append("wrapper golden outputs differ")

    summary = report.get("summary", {})
    expected_summary = {
        "expanded_setting_count": 46,
        "history_decoder_path_count": 126,
        "bandwidth_observation_count": 46,
        "transform_input_count": 4,
        "transform_path_count": 36,
        "wrapper_encode_path_count": 12,
        "all_encoder_bitstreams_deterministic": True,
        "all_history_decoder_outputs_deterministic": True,
        "all_transform_outputs_deterministic": True,
        "all_lossless_wrappers_decode_to_exact_input_pcm": True,
    }
    if any(summary.get(field) != value for field, value in expected_summary.items()):
        errors.append("aggregate summary differs")
    if report.get("public_decoder_equivalence") != {
        "fresh_synthetic_probe_completed": False,
        "required_before_baseline_scoring": True,
        "prior_observed_container_audit_retained": True,
    }:
        errors.append("public decoder equivalence boundary differs")

    serialized = json.dumps(report, sort_keys=True)
    if any(token in serialized for token in ("/Users/", "Library/Application Support", "\\Users\\")):
        errors.append("report contains a private path")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument(
        "--manifest",
        default=Path("benchmarks/audio-integrity-v2/toolchain-bindings.json"),
        type=Path,
    )
    parser.add_argument(
        "--factor",
        default=Path("benchmarks/audio-integrity-v2/factor-levels.json"),
        type=Path,
    )
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    report_path = args.report.expanduser().resolve()
    errors = validate(
        load_object(report_path),
        load_object(args.manifest.expanduser().resolve()),
        load_object(args.factor.expanduser().resolve()),
        report_path,
        repository_root,
    )
    if errors:
        print("toolchain result validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("toolchain result valid: exact bindings, deterministic paths, verdict-free")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
