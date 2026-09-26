#!/usr/bin/env python3
"""Run retained A0-A4 or R1/R2 controls on v2 mechanism development."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import audio_integrity_v2_baseline_common as common


SCHEMA_VERSION = 1
ADAPTER_ID = "lossytrace-v2-explainable-control-adapter-20260803-001"
RUN_ID = "lossytrace-v2-explainable-controls-20260803-001"
EXACT_HYBRID = "exact_hybrid_a0_through_a4"
CODEC_PROJECTION = "codec_projection_r1_r2"
CONTROLS = {EXACT_HYBRID, CODEC_PROJECTION}
EXPECTED_SELECTED_CASE_COUNT = 6_032
EXPECTED_NEGATIVE_CASE_COUNT = 4_665
EXPECTED_MP3_POSITIVE_CASE_COUNT = 1_367
EXPECTED_UNIQUE_PCM_COUNT = 4_090
EXPECTED_PCM_WRAPPER_REPRESENTATIVE_COUNT = 5_895
EXPECTED_MULTI_WRAPPER_PCM_COUNT = 1_391
MAXIMUM_WORKERS = 6
UPSTREAM_CHECKPOINT_COMMIT = "aae2392cb404393249d14cfb875422eb4156db3e"

EXACT_SCORE_FIELDS = {
    "A0": "a0_replay_selected_small_fraction_1e4",
    "A1": "a1_phase_zero_subband_relative_small_fraction_1e2",
    "A2": "a2_phase_zero_time_median_small_fraction_1e2",
    "A3": "a3_phase_stable_small_fraction_1e2",
    "A4": "a4_content_guarded_small_fraction_1e2",
}
PROJECTION_SCORE_FIELDS = {
    "R1": "r1_cycle_residual_retention",
    "R2": "r2_residual_directional_recurrence",
}

ROOT = Path(__file__).resolve().parents[1]


def load_legacy_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load frozen helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LEGACY_EXACT = load_legacy_module(
    "lossytrace_v2_frozen_exact_hybrid_runner",
    ROOT / "scripts" / "run-audio-integrity-exact-hybrid-ablation.py",
)
LEGACY_PROJECTION = load_legacy_module(
    "lossytrace_v2_frozen_codec_projection_runner",
    ROOT / "scripts" / "run-audio-integrity-codec-projection.py",
)


def select_scope(
    cases: list[dict[str, Any]], *, enforce_frozen_inventory: bool = True
) -> list[dict[str, Any]]:
    selected = [
        row
        for row in cases
        if row.get("expectation") == "negative"
        or (
            row.get("expectation") == "controlled_positive"
            and row.get("codec_family") == "mp3"
        )
    ]
    selected.sort(key=lambda row: row["case_id"])
    if enforce_frozen_inventory:
        counts = (
            len(selected),
            sum(row["expectation"] == "negative" for row in selected),
            sum(row["expectation"] == "controlled_positive" for row in selected),
        )
        if counts != (
            EXPECTED_SELECTED_CASE_COUNT,
            EXPECTED_NEGATIVE_CASE_COUNT,
            EXPECTED_MP3_POSITIVE_CASE_COUNT,
        ):
            raise ValueError(f"explainable-control selected inventory differs: {counts}")
    return selected


def scoped_representatives(
    cases: list[dict[str, Any]], *, enforce_frozen_inventory: bool = True
) -> list[dict[str, Any]]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for row in cases:
        key = (row["_analysis_pcm_sha256"], row["lossless_wrapper_id"])
        previous = selected.get(key)
        if previous is None or row["case_id"] < previous["case_id"]:
            selected[key] = row
    output = sorted(selected.values(), key=lambda row: row["case_id"])
    if enforce_frozen_inventory:
        if len(output) != EXPECTED_PCM_WRAPPER_REPRESENTATIVE_COUNT:
            raise ValueError("explainable-control PCM/wrapper inventory differs")
        if len({row["audio_sha256"] for row in output}) != len(output):
            raise ValueError("explainable-control artifact representatives are not unique")
    return output


def resolve_executable(value: str | Path) -> Path:
    candidate = Path(value).expanduser()
    if candidate.parent != Path("."):
        resolved = candidate.resolve()
    else:
        located = shutil.which(str(value))
        if located is None:
            raise ValueError(f"executable is missing: {value}")
        resolved = Path(located).resolve()
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise ValueError(f"executable is not runnable: {resolved}")
    return resolved


def command_output(arguments: list[str]) -> str:
    completed = subprocess.run(
        arguments,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if completed.returncode:
        raise ValueError(
            f"command failed ({completed.returncode}): {completed.stdout.strip()}"
        )
    return completed.stdout


def exact_tool_binding(ffmpeg_value: str) -> tuple[dict[str, Any], Path]:
    ffmpeg = resolve_executable(ffmpeg_value)
    version = command_output([str(ffmpeg), "-version"])
    return (
        {
            "ffmpeg": {
                "basename": ffmpeg.name,
                "sha256": common.sha256_file(ffmpeg),
                "version_output_sha256": hashlib.sha256(version.encode()).hexdigest(),
            }
        },
        ffmpeg,
    )


def repository_state() -> str:
    commit = command_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).strip()
    if len(commit) != 40:
        raise ValueError("repository commit identity is invalid")
    dirty = command_output(
        [
            "git",
            "-C",
            str(ROOT),
            "status",
            "--porcelain",
            "--untracked-files=no",
        ]
    ).strip()
    if dirty:
        raise ValueError("tracked worktree must be clean before control execution")
    ancestry = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "merge-base",
            "--is-ancestor",
            UPSTREAM_CHECKPOINT_COMMIT,
            commit,
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if ancestry.returncode != 0:
        raise ValueError("adapter upstream checkpoint is not an ancestor of HEAD")
    return commit


def validate_plan_and_inputs(
    *,
    adapter_plan_path: Path,
    parent_plan_path: Path,
    analysis_manifest_path: Path,
    constructor_manifest_path: Path,
    feature_report_path: Path,
    runner_path: Path,
    analyzer_path: Path,
) -> tuple[dict[str, Any], dict[str, str]]:
    adapter = common.load_object(adapter_plan_path)
    parent = common.load_object(parent_plan_path)
    if (
        adapter.get("schema_version") != 1
        or adapter.get("adapter_id") != ADAPTER_ID
        or adapter.get("state")
        != "frozen_before_explainable_control_scores_opened"
        or adapter.get("evidence_partition") != common.MECHANISM_PARTITION
        or adapter.get("encoder_transfer_scores_opened") is not False
        or adapter.get("external_transfer_scores_opened") is not False
        or adapter.get("public_verdict_enabled") is not False
        or adapter.get("upstream_checkpoint_commit") != UPSTREAM_CHECKPOINT_COMMIT
        or parent.get("plan_id") != common.PLAN_ID
        or parent.get("state")
        != "mechanism_development_baselines_frozen_before_waveform_decode"
        or parent.get("encoder_transfer_scores_opened") is not False
        or parent.get("external_transfer_scores_opened") is not False
        or parent.get("public_verdict_enabled") is not False
    ):
        raise ValueError("explainable-control adapter plan state differs")
    bindings = adapter.get("bindings", {})
    paths = (
        (parent_plan_path, "parent_development_baseline_plan_sha256"),
        (analysis_manifest_path, "private_analysis_manifest_sha256"),
        (constructor_manifest_path, "private_constructor_manifest_sha256"),
        (feature_report_path, "private_feature_v0_report_sha256"),
        (Path(common.__file__).resolve(), "common_module_sha256"),
        (runner_path, "adapter_runner_sha256"),
        (analyzer_path, "adapter_analyzer_sha256"),
        (
            ROOT / "scripts" / "run-audio-integrity-exact-hybrid-ablation.py",
            "frozen_exact_hybrid_helper_sha256",
        ),
        (
            ROOT / "scripts" / "run-audio-integrity-codec-projection.py",
            "frozen_codec_projection_helper_sha256",
        ),
        (
            ROOT / "research" / "exact-transform" / "ablation-v1" / "src" / "main.rs",
            "exact_hybrid_oracle_source_sha256",
        ),
        (
            ROOT / "research" / "exact-transform" / "ablation-v1" / "Cargo.toml",
            "exact_hybrid_cargo_toml_sha256",
        ),
        (
            ROOT / "research" / "exact-transform" / "ablation-v1" / "Cargo.lock",
            "exact_hybrid_cargo_lock_sha256",
        ),
        (
            ROOT / "research" / "codec-projection" / "oracle-v1" / "src" / "main.rs",
            "codec_projection_oracle_source_sha256",
        ),
        (
            ROOT / "research" / "codec-projection" / "oracle-v1" / "Cargo.toml",
            "codec_projection_cargo_toml_sha256",
        ),
        (
            ROOT / "research" / "codec-projection" / "oracle-v1" / "Cargo.lock",
            "codec_projection_cargo_lock_sha256",
        ),
        (
            ROOT / "research" / "codec-projection" / "oracle-v1" / "config.json",
            "codec_projection_config_sha256",
        ),
    )
    observed: dict[str, str] = {}
    for path, key in paths:
        if not path.is_file():
            raise ValueError(f"bound adapter input is absent: {key}")
        digest = common.sha256_file(path)
        if bindings.get(key) != digest:
            raise ValueError(f"bound adapter input differs: {key}")
        observed[key] = digest
    parent_bindings = parent.get("bindings", {})
    for adapter_key, parent_key in (
        ("private_analysis_manifest_sha256", "private_analysis_manifest_sha256"),
        ("private_constructor_manifest_sha256", "private_constructor_manifest_sha256"),
        ("common_module_sha256", "common_module_sha256"),
        ("exact_hybrid_oracle_source_sha256", "exact_hybrid_oracle_source_sha256"),
        ("codec_projection_oracle_source_sha256", "codec_projection_oracle_source_sha256"),
        ("codec_projection_config_sha256", "codec_projection_config_sha256"),
    ):
        if bindings.get(adapter_key) != parent_bindings.get(parent_key):
            raise ValueError(f"adapter-to-parent binding differs: {adapter_key}")
    inventory = adapter.get("scope", {})
    if inventory != {
        "controlled_mp3_positive_case_count": EXPECTED_MP3_POSITIVE_CASE_COUNT,
        "multi_wrapper_pcm_count": EXPECTED_MULTI_WRAPPER_PCM_COUNT,
        "negative_case_count": EXPECTED_NEGATIVE_CASE_COUNT,
        "pcm_wrapper_representative_count": EXPECTED_PCM_WRAPPER_REPRESENTATIVE_COUNT,
        "selected_factorial_case_count": EXPECTED_SELECTED_CASE_COUNT,
        "source_group_count": common.EXPECTED_SOURCE_GROUP_COUNT,
        "unique_analysis_pcm_count": EXPECTED_UNIQUE_PCM_COUNT,
    }:
        raise ValueError("adapter scope commitment differs")
    return adapter, observed


def validate_feature_report(report: dict[str, Any], cases: list[dict[str, Any]]) -> None:
    rows = report.get("case_results")
    if (
        report.get("schema_version") != 1
        or report.get("plan_id") != common.PLAN_ID
        or report.get("state")
        != "mechanism_development_fixed_baseline_private_result"
        or report.get("baseline") != "lossytrace_feature_v0_descriptive"
        or report.get("feature_version") != 0
        or report.get("encoder_transfer_scores_opened") is not False
        or report.get("external_transfer_scores_opened") is not False
        or report.get("public_verdict_enabled") is not False
        or not isinstance(rows, list)
        or len(rows) != common.EXPECTED_CASE_COUNT
    ):
        raise ValueError("private feature-v0 input state differs")
    if {row.get("case_id") for row in rows} != {row["case_id"] for row in cases}:
        raise ValueError("private feature-v0 case inventory differs")


def validate_optional_unit_score(value: object, label: str) -> float | None:
    if value is None:
        return None
    if (
        not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError(f"{label} is not a finite unit-interval score")
    return float(value)


def normalized_exact_measurement(case_id: str, probe: dict[str, Any]) -> tuple[dict[str, Any], float]:
    probe = dict(LEGACY_EXACT.validate_probe(case_id, probe))
    elapsed = probe.pop("elapsed_ms", None)
    if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError(f"{case_id}: exact-hybrid timing is invalid")
    aggregate = probe.get("aggregate")
    if not isinstance(aggregate, dict):
        raise ValueError(f"{case_id}: exact-hybrid aggregate is absent")
    scores = {
        name: validate_optional_unit_score(aggregate.get(field), f"{case_id}: {name}")
        for name, field in EXACT_SCORE_FIELDS.items()
    }
    probe.pop("case_id", None)
    return (
        {
            "schema_version": 1,
            "state": "v2_exact_hybrid_control_measurement",
            "control": EXACT_HYBRID,
            "support": {name: value is not None for name, value in scores.items()},
            "scores": scores,
            "probe_without_identity_or_timing": probe,
        },
        float(elapsed),
    )


def unsupported_exact_measurement() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "state": "v2_exact_hybrid_control_measurement",
        "control": EXACT_HYBRID,
        "support": {name: False for name in EXACT_SCORE_FIELDS},
        "scores": {name: None for name in EXACT_SCORE_FIELDS},
        "unsupported_reason": "no_supported_exact_hybrid_granules_after_fixed_5_second_start",
        "probe_without_identity_or_timing": None,
    }


def normalized_projection_measurement(
    case_id: str, probe: dict[str, Any], algorithm: str
) -> dict[str, Any]:
    probe = dict(LEGACY_PROJECTION.validate_measurement(case_id, probe, algorithm))
    supported = probe["support"]["supported"]
    raw_scores = probe.get("scores") if supported else None
    scores = {
        name: validate_optional_unit_score(
            raw_scores.get(field) if isinstance(raw_scores, dict) else None,
            f"{case_id}: {name}",
        )
        for name, field in PROJECTION_SCORE_FIELDS.items()
    }
    probe.pop("case_id", None)
    return {
        "schema_version": 1,
        "state": "v2_codec_projection_control_measurement",
        "control": CODEC_PROJECTION,
        "support": {name: supported for name in PROJECTION_SCORE_FIELDS},
        "scores": scores,
        "probe_without_identity_or_timing": probe,
    }


def validate_normalized_measurement(control: str, measurement: object) -> dict[str, Any]:
    if not isinstance(measurement, dict):
        raise ValueError("normalized control measurement is invalid")
    fields = EXACT_SCORE_FIELDS if control == EXACT_HYBRID else PROJECTION_SCORE_FIELDS
    state = (
        "v2_exact_hybrid_control_measurement"
        if control == EXACT_HYBRID
        else "v2_codec_projection_control_measurement"
    )
    support = measurement.get("support")
    scores = measurement.get("scores")
    if (
        measurement.get("schema_version") != 1
        or measurement.get("state") != state
        or measurement.get("control") != control
        or not isinstance(support, dict)
        or not isinstance(scores, dict)
        or set(support) != set(fields)
        or set(scores) != set(fields)
    ):
        raise ValueError("normalized control measurement contract differs")
    for name in fields:
        if not isinstance(support[name], bool):
            raise ValueError(f"{name}: normalized support is invalid")
        value = validate_optional_unit_score(scores[name], name)
        if support[name] != (value is not None):
            raise ValueError(f"{name}: score and support disagree")
    return measurement


def run_exact(
    *, case_id: str, source: Path, oracle: Path, ffmpeg: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.monotonic()
    decoder = subprocess.Popen(
        [
            str(ffmpeg),
            "-v",
            "error",
            "-ss",
            str(LEGACY_EXACT.START_SECONDS),
            "-t",
            str(LEGACY_EXACT.DURATION_SECONDS),
            "-i",
            str(source),
            "-map_metadata",
            "-1",
            "-ac",
            "1",
            "-ar",
            "44100",
            "-c:a",
            "pcm_f32le",
            "-f",
            "f32le",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert decoder.stdout is not None
    probe = subprocess.run(
        [str(oracle), case_id],
        stdin=decoder.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    decoder.stdout.close()
    decoder_stderr = decoder.stderr.read() if decoder.stderr else b""
    decoder_returncode = decoder.wait()
    if decoder_returncode:
        raise ValueError(
            f"{case_id}: FFmpeg failed ({decoder_returncode}): "
            f"{decoder_stderr.decode(errors='replace').strip()}"
        )
    if probe.returncode:
        message = probe.stderr.decode(errors="replace").strip()
        if "no supported exact-hybrid granules" not in message:
            raise ValueError(
                f"{case_id}: exact-hybrid oracle failed ({probe.returncode}): {message}"
            )
        measurement = unsupported_exact_measurement()
        oracle_elapsed = None
    else:
        try:
            decoded = json.loads(probe.stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"{case_id}: exact-hybrid JSON is invalid: {error}") from error
        measurement, oracle_elapsed = normalized_exact_measurement(case_id, decoded)
    timing = {
        "schema_version": 1,
        "control": EXACT_HYBRID,
        "case_id": case_id,
        "wall_elapsed_ms": (time.monotonic() - started) * 1_000.0,
        "oracle_elapsed_ms": oracle_elapsed,
    }
    return validate_normalized_measurement(EXACT_HYBRID, measurement), timing


def run_projection(
    *,
    case_id: str,
    source: Path,
    oracle: Path,
    config_path: Path,
    ffmpeg: Path,
    timing_path: Path,
    algorithm: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    completed = subprocess.run(
        [
            str(oracle),
            case_id,
            str(config_path),
            str(ffmpeg),
            str(source),
            str(timing_path),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode:
        raise ValueError(
            f"{case_id}: codec-projection oracle failed ({completed.returncode}): "
            f"{completed.stderr.strip()}"
        )
    try:
        probe = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"{case_id}: codec-projection JSON is invalid: {error}") from error
    if not timing_path.is_file():
        raise ValueError(f"{case_id}: codec-projection timing is absent")
    timing = LEGACY_PROJECTION.validate_timing(
        case_id, common.load_object(timing_path)
    )
    measurement = normalized_projection_measurement(case_id, probe, algorithm)
    return validate_normalized_measurement(CODEC_PROJECTION, measurement), timing


def checkpoint_path(root: Path, audio_sha256: str) -> Path:
    if len(audio_sha256) != 64:
        raise ValueError("artifact hash is invalid")
    return root / audio_sha256[:2] / f"{audio_sha256}.json"


def run_representative(
    *,
    control: str,
    case: dict[str, Any],
    audio_root: Path,
    oracle: Path,
    ffmpeg: Path,
    config_path: Path | None,
    algorithm: str | None,
    run_binding_sha256: str,
    partial_root: Path,
    timing_root: Path,
) -> tuple[dict[str, Any], bool]:
    audio_sha256 = case["audio_sha256"]
    partial_path = checkpoint_path(partial_root, audio_sha256)
    timing_path = checkpoint_path(timing_root, audio_sha256)
    commitment = {
        "run_binding_sha256": run_binding_sha256,
        "control": control,
        "case_id": case["case_id"],
        "audio_sha256": audio_sha256,
        "analysis_pcm_sha256": case["_analysis_pcm_sha256"],
        "lossless_wrapper_id": case["lossless_wrapper_id"],
    }
    if partial_path.is_symlink() or timing_path.is_symlink():
        raise ValueError(f"{case['case_id']}: checkpoint path must not be a symlink")
    if partial_path.exists():
        partial = common.load_object(partial_path)
        if partial.get("schema_version") != 1 or partial.get("commitment") != commitment:
            raise ValueError(f"{case['case_id']}: partial commitment differs")
        measurement = validate_normalized_measurement(control, partial.get("measurement"))
        return {**commitment, "measurement": measurement}, True
    if timing_path.exists():
        # Timing is deliberately non-authoritative. A restart may occur after an
        # oracle wrote timing but before the atomic measurement checkpoint. Drop
        # only that bound generated timing row and repeat the measurement.
        timing_path.unlink()
    source = common.resolve_beneath(audio_root, case["relative_path"])
    if not source.is_file() or common.sha256_file(source) != audio_sha256:
        raise ValueError(f"{case['case_id']}: artifact hash or path differs")
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    if control == EXACT_HYBRID:
        measurement, timing = run_exact(
            case_id=case["case_id"], source=source, oracle=oracle, ffmpeg=ffmpeg
        )
        common.write_new(timing_path, timing)
    else:
        if config_path is None or algorithm is None:
            raise ValueError("codec-projection configuration is absent")
        measurement, _ = run_projection(
            case_id=case["case_id"],
            source=source,
            oracle=oracle,
            config_path=config_path,
            ffmpeg=ffmpeg,
            timing_path=timing_path,
            algorithm=algorithm,
        )
    partial = {
        "schema_version": 1,
        "commitment": commitment,
        "measurement": measurement,
    }
    common.write_new(partial_path, partial)
    return {**commitment, "measurement": measurement}, False


def assert_wrapper_invariance(
    rows: list[dict[str, Any]], *, enforce_frozen_inventory: bool = True
) -> dict[str, Any]:
    by_pcm: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_pcm.setdefault(row["analysis_pcm_sha256"], []).append(row)
    multi_wrapper = 0
    for pcm_sha256, pcm_rows in by_pcm.items():
        wrappers = {row["lossless_wrapper_id"] for row in pcm_rows}
        if len(wrappers) < 2:
            continue
        multi_wrapper += 1
        first = pcm_rows[0]["measurement"]
        if any(row["measurement"] != first for row in pcm_rows[1:]):
            raise ValueError(f"wrapper invariance failed for PCM {pcm_sha256}")
    if enforce_frozen_inventory and (
        len(by_pcm) != EXPECTED_UNIQUE_PCM_COUNT
        or len(rows) != EXPECTED_PCM_WRAPPER_REPRESENTATIVE_COUNT
        or multi_wrapper != EXPECTED_MULTI_WRAPPER_PCM_COUNT
    ):
        raise ValueError("scoped wrapper-invariance inventory differs")
    return {
        "unique_analysis_pcm_count": len(by_pcm),
        "multi_wrapper_pcm_count": multi_wrapper,
        "pcm_wrapper_representative_count": len(rows),
        "exact_wrapper_invariance_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", required=True, choices=sorted(CONTROLS))
    parser.add_argument("--adapter-plan", required=True, type=Path)
    parser.add_argument("--parent-plan", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--constructor-manifest", required=True, type=Path)
    parser.add_argument("--feature-v0-report", required=True, type=Path)
    parser.add_argument("--audio-root", required=True, type=Path)
    parser.add_argument("--oracle", required=True, type=Path)
    parser.add_argument("--partial-directory", required=True, type=Path)
    parser.add_argument("--timing-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--analyzer", required=True, type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--lame", default="lame")
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    try:
        if not 1 <= args.jobs <= MAXIMUM_WORKERS:
            raise ValueError(f"--jobs must be between 1 and {MAXIMUM_WORKERS}")
        runner_path = Path(__file__).resolve()
        adapter_plan_path = args.adapter_plan.expanduser().resolve()
        parent_plan_path = args.parent_plan.expanduser().resolve()
        manifest_path = args.manifest.expanduser().resolve()
        constructor_path = args.constructor_manifest.expanduser().resolve()
        feature_path = args.feature_v0_report.expanduser().resolve()
        analyzer_path = args.analyzer.expanduser().resolve()
        audio_root = args.audio_root.expanduser().resolve()
        oracle = args.oracle.expanduser().resolve()
        output = args.output.expanduser().resolve()
        partial_root = args.partial_directory.expanduser().resolve() / args.control
        timing_root = args.timing_directory.expanduser().resolve() / args.control
        if output.exists() or output.is_symlink():
            raise ValueError(f"refusing to replace existing output: {output}")
        if not audio_root.is_dir() or not oracle.is_file():
            raise ValueError("audio root or oracle binary is absent")
        adapter, input_hashes = validate_plan_and_inputs(
            adapter_plan_path=adapter_plan_path,
            parent_plan_path=parent_plan_path,
            analysis_manifest_path=manifest_path,
            constructor_manifest_path=constructor_path,
            feature_report_path=feature_path,
            runner_path=runner_path,
            analyzer_path=analyzer_path,
        )
        cases = common.load_development_cases(
            common.load_object(manifest_path), common.load_object(constructor_path)
        )
        validate_feature_report(common.load_object(feature_path), cases)
        selected = select_scope(cases)
        representatives = scoped_representatives(selected)
        commit = repository_state()
        if args.control == EXACT_HYBRID:
            tool_bindings, ffmpeg = exact_tool_binding(args.ffmpeg)
            config_path = None
            algorithm = None
        else:
            tool_bindings, _, ffmpeg = LEGACY_PROJECTION.tool_bindings(
                args.ffmpeg, args.lame
            )
            config_path = (
                ROOT / "research" / "codec-projection" / "oracle-v1" / "config.json"
            ).resolve()
            config = LEGACY_PROJECTION.load_and_validate_config(config_path)
            algorithm = config["algorithm"]
        oracle_sha256 = common.sha256_file(oracle)
        binding = {
            "adapter_id": ADAPTER_ID,
            "control": args.control,
            "implementation_commit_sha1": commit,
            "input_hashes": input_hashes,
            "oracle_binary_sha256": oracle_sha256,
            "tool_bindings": tool_bindings,
            "scope": adapter["scope"],
        }
        run_binding_sha256 = common.canonical_sha256(
            b"lossytrace-v2-explainable-control-run-binding-v1\0", binding
        )
        completed = 0
        resumed = 0
        results: list[dict[str, Any]] = []

        def submit(case: dict[str, Any]) -> tuple[dict[str, Any], bool]:
            return run_representative(
                control=args.control,
                case=case,
                audio_root=audio_root,
                oracle=oracle,
                ffmpeg=ffmpeg,
                config_path=config_path,
                algorithm=algorithm,
                run_binding_sha256=run_binding_sha256,
                partial_root=partial_root,
                timing_root=timing_root,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            future_rows = {executor.submit(submit, case): case for case in representatives}
            for future in concurrent.futures.as_completed(future_rows):
                row, was_resumed = future.result()
                results.append(row)
                completed += 1
                resumed += was_resumed
                print(
                    f"[{completed:04d}/{len(representatives):04d}] "
                    f"{'resumed' if was_resumed else 'measured'}",
                    file=os.sys.stderr,
                    flush=True,
                )
        results.sort(key=lambda row: row["case_id"])
        wrapper_invariance = assert_wrapper_invariance(results)
        report = {
            "schema_version": SCHEMA_VERSION,
            "run_id": RUN_ID,
            "adapter_id": ADAPTER_ID,
            "state": "mechanism_development_explainable_control_private_result",
            "control": args.control,
            "evidence_partition": common.MECHANISM_PARTITION,
            "feature_version": 0,
            "scores_opened": True,
            "thresholds_fitted": False,
            "independent_validation": False,
            "encoder_transfer_scores_opened": False,
            "external_transfer_scores_opened": False,
            "public_verdict_enabled": False,
            "run_binding": binding,
            "run_binding_sha256": run_binding_sha256,
            "inventory": adapter["scope"],
            "wrapper_invariance": wrapper_invariance,
            "artifact_results": results,
        }
        common.write_new(output, report)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(
        json.dumps(
            {
                "control": args.control,
                "measured_representative_count": len(results) - resumed,
                "resumed_representative_count": resumed,
                "private_report_sha256": common.sha256_file(output),
                "wrapper_invariance_passed": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
