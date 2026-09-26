#!/usr/bin/env python3
"""Run exact Cannam or feature-v0 baselines on v2 mechanism development."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
from pathlib import Path
from typing import Any

import audio_integrity_v2_baseline_common as common


SCHEMA_VERSION = 1
RUN_ID = "lossytrace-v2-fixed-baselines-20260802-001"
CANNAM_BASELINE = "cannam_published_fixed_rule"
FEATURE_BASELINE = "lossytrace_feature_v0_descriptive"
BASELINES = {CANNAM_BASELINE, FEATURE_BASELINE}
PLUGIN_KEY = "vamp-lossy-encoding-detector:lossydetector:cf"
WINDOW_THRESHOLD = 0.5
FILE_THRESHOLD = 0.25
PROBABILITY_LINE = re.compile(
    r"^\s*[0-9]+\.[0-9]+:\s+"
    r"([-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?)"
    r"\s+(?:Original|Lossy)\s*$"
)


def validate_plan(
    plan: dict[str, Any],
    *,
    baseline: str,
    plan_path: Path,
    manifest_path: Path,
    constructor_path: Path,
    runner_path: Path,
    host_path: Path | None,
    plugin_path: Path | None,
    measurement_binary: Path | None,
) -> dict[str, str]:
    if (
        plan.get("schema_version") != 1
        or plan.get("plan_id") != common.PLAN_ID
        or plan.get("state")
        != "mechanism_development_baselines_frozen_before_waveform_decode"
        or plan.get("authorized_evidence_partition") != common.MECHANISM_PARTITION
        or plan.get("encoder_transfer_scores_opened") is not False
        or plan.get("external_transfer_scores_opened") is not False
        or plan.get("public_verdict_enabled") is not False
        or baseline not in BASELINES
    ):
        raise ValueError("development-baseline plan state differs")
    bindings = plan.get("bindings", {})
    checks = [
        (plan_path, "plan", None),
        (manifest_path, "analysis_manifest", "private_analysis_manifest_sha256"),
        (
            constructor_path,
            "constructor_manifest",
            "private_constructor_manifest_sha256",
        ),
        (runner_path, "runner", "fixed_baseline_runner_sha256"),
        (
            Path(common.__file__).resolve(),
            "common module",
            "common_module_sha256",
        ),
    ]
    if baseline == CANNAM_BASELINE:
        checks.extend(
            [
                (host_path, "Vamp host", "cannam_host_sha256"),
                (plugin_path, "Cannam plugin", "cannam_plugin_sha256"),
            ]
        )
        method = plan.get("baselines", {}).get(CANNAM_BASELINE, {})
        if (
            method.get("plugin_key") != PLUGIN_KEY
            or method.get("repository_revision")
            != "7a70bd8d15e68b0b1942a9d3deac6ad4d8293b8b"
            or method.get("window_threshold") != WINDOW_THRESHOLD
            or method.get("file_positive_fraction_threshold") != FILE_THRESHOLD
            or method.get("thresholds_retuned") is not False
        ):
            raise ValueError("Cannam fixed method differs")
    else:
        checks.append(
            (
                measurement_binary,
                "measurement binary",
                "feature_v0_binary_sha256",
            )
        )
        method = plan.get("baselines", {}).get(FEATURE_BASELINE, {})
        if (
            method.get("feature_version") != 0
            or method.get("classifier_enabled") is not False
            or method.get("analysis_max_seconds") != 0
        ):
            raise ValueError("feature-v0 method differs")

    hashes: dict[str, str] = {"plan_sha256": common.sha256_file(plan_path)}
    for path, label, key in checks[1:]:
        if path is None or not path.is_file():
            raise ValueError(f"{label} is absent")
        digest = common.sha256_file(path)
        if bindings.get(key) != digest:
            raise ValueError(f"{label} binding differs")
        hashes[f"{label.lower().replace(' ', '_')}_sha256"] = digest
    return hashes


def parse_cannam(output: str) -> dict[str, Any]:
    probabilities = [
        float(match.group(1))
        for line in output.splitlines()
        if (match := PROBABILITY_LINE.match(line))
    ]
    if not probabilities or any(
        not math.isfinite(value) or not 0.0 <= value <= 1.0
        for value in probabilities
    ):
        raise ValueError("Cannam detector returned no valid window outputs")
    ordered = sorted(probabilities)
    p90_position = 0.9 * (len(ordered) - 1)
    p90_lower = math.floor(p90_position)
    p90_upper = math.ceil(p90_position)
    p90 = ordered[p90_lower] + (ordered[p90_upper] - ordered[p90_lower]) * (
        p90_position - p90_lower
    )
    positive_fraction = sum(
        value >= WINDOW_THRESHOLD for value in probabilities
    ) / len(probabilities)
    return {
        "window_count": len(probabilities),
        "window_score_mean": statistics.fmean(probabilities),
        "window_score_median": statistics.median(probabilities),
        "window_score_p90": p90,
        "positive_window_fraction": positive_fraction,
        "fixed_binary_label": positive_fraction >= FILE_THRESHOLD,
    }


def run_cannam(
    audio_path: Path, host_path: Path, plugin_directory: Path
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["VAMP_PATH"] = str(plugin_directory)
    completed = subprocess.run(
        [str(host_path), PLUGIN_KEY, str(audio_path)],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    if completed.returncode:
        message = completed.stderr.strip().replace(str(audio_path), "<AUDIO>")
        raise ValueError(f"Cannam detector failed: {message}")
    return parse_cannam(completed.stdout)


def run_feature_v0(audio_path: Path, binary: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [str(binary), "analyze", str(audio_path), "--max-seconds", "0"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        message = completed.stderr.strip().replace(str(audio_path), "<AUDIO>")
        raise ValueError(f"feature-v0 measurement failed: {message}")
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("feature-v0 measurement returned invalid JSON") from error
    features = report.get("compression_trace")
    if (
        report.get("schema_version") != 1
        or report.get("state") != "experimental_measurements_only"
        or report.get("public_verdict_enabled") is not False
        or report.get("truncated_by_limit") is not False
        or not isinstance(features, dict)
        or features.get("feature_version") != 0
    ):
        raise ValueError("feature-v0 measurement contract differs")
    return {
        "analyzed_sample_count": report["analyzed_sample_count"],
        "analyzed_duration_seconds": report["analyzed_duration_seconds"],
        "sample_rate_hz": report["source_facts"]["sample_rate_hz"],
        "channel_count": report["source_facts"]["channel_count"],
        "features": features,
    }


def validate_result(baseline: str, result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("partial result is not an object")
    if baseline == CANNAM_BASELINE:
        required = {
            "window_count",
            "window_score_mean",
            "window_score_median",
            "window_score_p90",
            "positive_window_fraction",
            "fixed_binary_label",
        }
        if set(result) != required or not isinstance(result["window_count"], int):
            raise ValueError("Cannam partial fields differ")
        if result["window_count"] <= 0 or any(
            not isinstance(result[field], (int, float))
            or not math.isfinite(result[field])
            or not 0.0 <= result[field] <= 1.0
            for field in required - {"window_count", "fixed_binary_label"}
        ):
            raise ValueError("Cannam partial values are invalid")
        if (
            not isinstance(result["fixed_binary_label"], bool)
            or result["fixed_binary_label"]
            != (result["positive_window_fraction"] >= FILE_THRESHOLD)
        ):
            raise ValueError("Cannam fixed decision differs")
    else:
        if (
            set(result)
            != {
                "analyzed_sample_count",
                "analyzed_duration_seconds",
                "sample_rate_hz",
                "channel_count",
                "features",
            }
            or not isinstance(result.get("features"), dict)
            or result["features"].get("feature_version") != 0
        ):
            raise ValueError("feature-v0 partial fields differ")
    return result


def partial_path(directory: Path, audio_sha256: str) -> Path:
    return directory / audio_sha256[:2] / f"{audio_sha256}.json"


def score_or_resume(
    *,
    index: int,
    total: int,
    case: dict[str, Any],
    baseline: str,
    root: Path,
    run_binding_sha256: str,
    partial_directory: Path,
    host_path: Path | None,
    plugin_directory: Path | None,
    measurement_binary: Path | None,
) -> dict[str, Any]:
    audio_path = common.resolve_beneath(root, case["relative_path"])
    if not audio_path.is_file() or audio_path.is_symlink():
        raise ValueError(f"artifact is missing or unsafe: {case['case_id']}")
    audio_sha256 = common.sha256_file(audio_path)
    if audio_sha256 != case["audio_sha256"]:
        raise ValueError(f"artifact hash differs: {case['case_id']}")
    checkpoint_path = partial_path(partial_directory, audio_sha256)
    if checkpoint_path.exists():
        partial = common.load_object(checkpoint_path)
        if (
            partial.get("schema_version") != SCHEMA_VERSION
            or partial.get("run_binding_sha256") != run_binding_sha256
            or partial.get("baseline") != baseline
            or partial.get("audio_sha256") != audio_sha256
            or partial.get("analysis_pcm_sha256")
            != case["_analysis_pcm_sha256"]
            or partial.get("lossless_wrapper_id") != case["lossless_wrapper_id"]
        ):
            raise ValueError(f"partial binding differs: {case['case_id']}")
        result = validate_result(baseline, partial.get("result"))
        print(f"[{index:04d}/{total:04d}] resumed", file=os.sys.stderr)
        return {**partial, "result": result}

    print(f"[{index:04d}/{total:04d}] measuring", file=os.sys.stderr)
    if baseline == CANNAM_BASELINE:
        assert host_path is not None and plugin_directory is not None
        result = run_cannam(audio_path, host_path, plugin_directory)
    else:
        assert measurement_binary is not None
        result = run_feature_v0(audio_path, measurement_binary)
    partial = {
        "schema_version": SCHEMA_VERSION,
        "run_binding_sha256": run_binding_sha256,
        "baseline": baseline,
        "audio_sha256": audio_sha256,
        "analysis_pcm_sha256": case["_analysis_pcm_sha256"],
        "lossless_wrapper_id": case["lossless_wrapper_id"],
        "result": validate_result(baseline, result),
    }
    common.write_new(checkpoint_path, partial)
    return partial


def assert_wrapper_invariance(
    baseline: str, partials: list[dict[str, Any]]
) -> dict[str, int | bool]:
    by_pcm: dict[str, list[dict[str, Any]]] = {}
    for partial in partials:
        by_pcm.setdefault(partial["analysis_pcm_sha256"], []).append(partial)
    multi_wrapper = 0
    for pcm_sha256, rows in by_pcm.items():
        wrappers = {row["lossless_wrapper_id"] for row in rows}
        if len(wrappers) < 2:
            continue
        multi_wrapper += 1
        if baseline == CANNAM_BASELINE:
            values = [row["result"] for row in rows]
        else:
            values = [
                {
                    "analyzed_sample_count": row["result"]["analyzed_sample_count"],
                    "analyzed_duration_seconds": row["result"][
                        "analyzed_duration_seconds"
                    ],
                    "sample_rate_hz": row["result"]["sample_rate_hz"],
                    "channel_count": row["result"]["channel_count"],
                    "features": row["result"]["features"],
                }
                for row in rows
            ]
        if any(value != values[0] for value in values[1:]):
            raise ValueError(f"wrapper invariance failed for PCM {pcm_sha256}")
    return {
        "unique_analysis_pcm_count": len(by_pcm),
        "multi_wrapper_pcm_count": multi_wrapper,
        "pcm_wrapper_representative_count": len(partials),
        "exact_wrapper_invariance_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, choices=sorted(BASELINES))
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--constructor-manifest", required=True, type=Path)
    parser.add_argument("--audio-root", required=True, type=Path)
    parser.add_argument("--partial-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--host", type=Path)
    parser.add_argument("--plugin", type=Path)
    parser.add_argument("--measurement-binary", type=Path)
    args = parser.parse_args()

    runner_path = Path(__file__).resolve()
    plan_path = args.plan.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    constructor_path = args.constructor_manifest.expanduser().resolve()
    root = args.audio_root.expanduser().resolve()
    host_path = args.host.expanduser().resolve() if args.host else None
    plugin_path = args.plugin.expanduser().resolve() if args.plugin else None
    measurement_binary = (
        args.measurement_binary.expanduser().resolve()
        if args.measurement_binary
        else None
    )
    if not root.is_dir() or root.is_symlink():
        raise SystemExit("benchmark audio root is absent or unsafe")
    if args.baseline == CANNAM_BASELINE and (
        host_path is None or plugin_path is None
    ):
        raise SystemExit("Cannam baseline requires --host and --plugin")
    if args.baseline == FEATURE_BASELINE and measurement_binary is None:
        raise SystemExit("feature-v0 baseline requires --measurement-binary")

    try:
        plan = common.load_object(plan_path)
        input_hashes = validate_plan(
            plan,
            baseline=args.baseline,
            plan_path=plan_path,
            manifest_path=manifest_path,
            constructor_path=constructor_path,
            runner_path=runner_path,
            host_path=host_path,
            plugin_path=plugin_path,
            measurement_binary=measurement_binary,
        )
        cases = common.load_development_cases(
            common.load_object(manifest_path), common.load_object(constructor_path)
        )
        representatives = common.representatives_by_pcm_and_wrapper(cases)
        run_binding = {
            "run_id": RUN_ID,
            "baseline": args.baseline,
            "input_hashes": input_hashes,
            "case_count": len(cases),
            "representative_count": len(representatives),
        }
        run_binding_sha256 = common.canonical_sha256(
            b"lossytrace-v2-fixed-baseline-run\0", run_binding
        )
        partials = [
            score_or_resume(
                index=index,
                total=len(representatives),
                case=case,
                baseline=args.baseline,
                root=root,
                run_binding_sha256=run_binding_sha256,
                partial_directory=args.partial_directory.expanduser().resolve(),
                host_path=host_path,
                plugin_directory=plugin_path.parent if plugin_path else None,
                measurement_binary=measurement_binary,
            )
            for index, case in enumerate(representatives, 1)
        ]
        invariance = assert_wrapper_invariance(args.baseline, partials)
        by_audio = {row["audio_sha256"]: row["result"] for row in partials}
        if len(by_audio) != len(partials):
            raise ValueError("artifact result identities are not unique")
        case_results = []
        for case in cases:
            result = by_audio.get(case["audio_sha256"])
            if result is None:
                raise ValueError(f"case has no artifact result: {case['case_id']}")
            case_results.append(
                {
                    "case_id": case["case_id"],
                    "reference_case_id": case.get("reference_case_id"),
                    "source_group": case["source_group"],
                    "partition_group": case["partition_group"],
                    "source_domain": case["source_domain"],
                    "expectation": case["expectation"],
                    "history_class": case["history_class"],
                    "codec_family": case.get("codec_family"),
                    "encoder_lineage_id": case.get("encoder_lineage_id"),
                    "encoder_setting_id": case.get("encoder_setting_id"),
                    "post_transform_ids": case.get("post_transform_ids", []),
                    "lossless_wrapper_id": case["lossless_wrapper_id"],
                    "audio_sha256": case["audio_sha256"],
                    "analysis_pcm_sha256": case["_analysis_pcm_sha256"],
                    "result": result,
                }
            )
        report = {
            "schema_version": SCHEMA_VERSION,
            "run_id": RUN_ID,
            "plan_id": common.PLAN_ID,
            "state": "mechanism_development_fixed_baseline_private_result",
            "baseline": args.baseline,
            "evidence_partition": common.MECHANISM_PARTITION,
            "feature_version": 0,
            "scores_opened": True,
            "encoder_transfer_scores_opened": False,
            "external_transfer_scores_opened": False,
            "public_verdict_enabled": False,
            "thresholds_retuned": False,
            "run_binding": run_binding,
            "run_binding_sha256": run_binding_sha256,
            "wrapper_invariance": invariance,
            "case_results": case_results,
        }
        common.write_new(args.output.expanduser().resolve(), report)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(
        f"completed {args.baseline} for {len(cases)} development cases; "
        f"encoder and external transfer remain sealed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
