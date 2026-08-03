#!/usr/bin/env python3
"""Replay pinned ViSQOL on synthetic-only, score-freeze fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import perceptual_degradation_visqol_fixtures as fixtures


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def process_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {"LC_ALL": "C", "LANG": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "0"}
    )
    return environment


def _sanitize_result(value: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(value)
    for key in (
        "referenceFilepath",
        "degradedFilepath",
        "reference_filepath",
        "degraded_filepath",
    ):
        sanitized.pop(key, None)
    return sanitized


def _run_case(
    binary: Path,
    model: Path,
    reference: Path,
    degraded: Path,
    output: Path,
) -> dict[str, Any]:
    command = [
        str(binary),
        "--reference_file",
        str(reference),
        "--degraded_file",
        str(degraded),
        "--similarity_to_quality_model",
        str(model),
        "--output_debug",
        str(output),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=process_environment(),
    )
    if completed.stderr:
        raise ValueError("ViSQOL wrote unexpected stderr")
    if not output.is_file():
        raise ValueError("ViSQOL did not write the requested debug result")
    parsed = json.loads(output.read_text(encoding="utf-8"))
    sanitized = _sanitize_result(parsed)
    encoded = json.dumps(sanitized, sort_keys=True, separators=(",", ":")).encode()
    patches = sanitized.get("patchSims", sanitized.get("patch_sims", []))
    patch_similarity = [item["similarity"] for item in patches]
    return {
        "mos_lqo": sanitized["moslqo"],
        "similarity": sanitized["vnsim"],
        "band_similarity": sanitized["fvnsim"],
        "patch_similarity": patch_similarity,
        "patch_count": len(patches),
        "complete_result_sha256": sha256_bytes(encoded),
    }


def replay(binary: Path, model: Path, plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("state") != "visqol_synthetic_build_and_replay_frozen_before_scores":
        raise ValueError("ViSQOL synthetic replay plan state differs")
    if plan.get("authorization", {}).get("synthetic_fixture_execution") is not True:
        raise ValueError("synthetic fixture execution is not authorized")
    for key in (
        "public_or_retained_audio_execution",
        "human_listening_score_access",
        "retained_audio_access",
    ):
        if plan["authorization"].get(key) is not False:
            raise ValueError(f"authorization boundary differs: {key}")
    expected_model_sha256 = plan["visqol"]["audio_model_sha256"]
    if sha256_file(model) != expected_model_sha256:
        raise ValueError("ViSQOL audio model hash differs")
    binary_sha256 = sha256_file(binary)

    with tempfile.TemporaryDirectory(prefix="lossytrace-visqol-synthetic-") as temporary:
        root = Path(temporary)
        audio_dir = root / "audio"
        observed_fixtures = fixtures.generate(audio_dir)
        if observed_fixtures != plan["fixture_generation"]:
            raise ValueError("generated synthetic fixture binding differs")
        results = []
        for case in plan["synthetic_cases"]:
            reference = audio_dir / case["reference_file"]
            degraded = audio_dir / case["degraded_file"]
            first = _run_case(binary, model, reference, degraded, root / f"{case['case_id']}-a.json")
            second = _run_case(binary, model, reference, degraded, root / f"{case['case_id']}-b.json")
            if first != second:
                raise ValueError(f"ViSQOL replay differs for {case['case_id']}")
            results.append(
                {
                    "case_id": case["case_id"],
                    "complete_replays": 2,
                    "numeric_replay_identical": True,
                    **first,
                }
            )

    report = {
        "schema_version": 1,
        "record_kind": "visqol_synthetic_replay",
        "state": "visqol_synthetic_replay_passed_not_human_truth",
        "metric_family": "visqol_audio_v3_3_3",
        "source": {
            "repository": plan["visqol"]["repository"],
            "git_commit": plan["visqol"]["git_commit"],
            "git_tree": plan["visqol"]["git_tree"],
            "workspace_patch_sha256": plan["visqol"]["workspace_patch_sha256"],
        },
        "binary_sha256": binary_sha256,
        "audio_model_sha256": expected_model_sha256,
        "fixture_set_id": plan["fixture_set_id"],
        "fixture_generation_sha256": sha256_bytes(
            json.dumps(
                plan["fixture_generation"], sort_keys=True, separators=(",", ":")
            ).encode()
        ),
        "command": [
            "<VISQOL_BINARY>",
            "--reference_file",
            "<SYNTHETIC_REFERENCE>",
            "--degraded_file",
            "<SYNTHETIC_DEGRADED>",
            "--similarity_to_quality_model",
            "<BOUND_AUDIO_MODEL>",
            "--output_debug",
            "<EPHEMERAL_OUTPUT>",
        ],
        "results": results,
        "synthetic_metric_scores_opened": True,
        "human_listening_scores_opened": False,
        "retained_metric_scores_opened": False,
        "retained_audio_accessed": False,
        "public_or_provider_audio_accessed": False,
        "sealed_labels_opened": False,
        "existing_280_case_future_subset_opened": False,
        "synthetic_scores_are_human_truth": False,
        "threshold_selected": False,
        "cross_environment_replay_complete": False,
        "public_verdict_enabled": False,
        "paths_included": False,
    }
    if temporary in json.dumps(report):
        raise ValueError("temporary path leaked into ViSQOL replay report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--visqol", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    report = replay(args.visqol.resolve(), args.model.resolve(), plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
