#!/usr/bin/env python3
"""Run a frozen audio-integrity external transfer with safe resume."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path


CANDIDATE_ID = "conservative-two-grid-edge-v28-musdb-transfer-v1"
PROFILE = "conservative-two-grid-v28"
SAFE_CASE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_atomic(path: Path, value: dict, *, replace: bool = True) -> None:
    if not replace and (path.exists() or path.is_symlink()):
        raise SystemExit(f"refusing to replace output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def resolve_beneath(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    if root not in path.parents or not path.is_file():
        raise SystemExit(f"invalid audio path: {relative_path}")
    return path


def quantile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    position = proportion * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def validate_contract(
    *,
    manifest_path: Path,
    manifest: dict,
    fingerprints_path: Path,
    fingerprints: dict,
    precommit_path: Path,
    precommit: dict,
    runner: Path,
) -> None:
    corpus_plan = precommit.get("corpus_plan", {})
    tools = precommit.get("tools", {})
    plan_path = Path(corpus_plan.get("path", "")).expanduser().resolve()
    plan = load_json(plan_path)
    if (
        precommit.get("schema_version") != 1
        or precommit.get("state") != "frozen_before_external_transfer"
        or precommit.get("candidate_id") != CANDIDATE_ID
        or precommit.get("candidate_frozen") is not True
        or precommit.get("external_transfer_feature_scores_opened") is not False
        or precommit.get("release_heldout_opened") is not False
        or precommit.get("public_verdict_enabled") is not False
        or precommit.get("feature_version") != 0
        or precommit.get("transform_profile") != PROFILE
        or corpus_plan.get("sha256") != sha256_file(plan_path)
        or tools.get("external_runner_sha256")
        != sha256_file(Path(__file__).resolve())
        or tools.get("benchmark_runner_sha256") != sha256_file(runner)
        or manifest != plan.get("manifest")
        or fingerprints.get("corpus_id") != manifest.get("corpus_id")
        or set(fingerprints.get("case_sha256", {}))
        != {case["case_id"] for case in manifest.get("cases", [])}
        or any(
            case.get("split") != "held_out"
            for case in manifest.get("cases", [])
        )
        or len(manifest.get("cases", [])) != 1_770
    ):
        raise SystemExit("frozen external-runner contract differs")
    if (
        load_json(manifest_path.parent / "corpus-plan.json") != plan
        or load_json(manifest_path.parent / "candidate-precommit.json")
        != precommit
        or sha256_file(fingerprints_path)
        != sha256_file(manifest_path.parent / "fingerprints.json")
    ):
        raise SystemExit("retained corpus commitments differ")


def validate_runner_result(
    result: dict,
    *,
    case_id: str,
    audio_sha256: str,
) -> None:
    compression = result.get("compression_trace")
    transform = result.get("transform_grid_probe")
    if (
        result.get("schema_version") != 1
        or result.get("case_id") != case_id
        or result.get("audio_sha256") != audio_sha256
        or result.get("feature_version") != 0
        or not isinstance(compression, dict)
        or result.get("research_transform_grid_enabled") is not True
        or result.get("research_transform_grid_profile") != PROFILE
        or not isinstance(transform, dict)
        or not isinstance(transform.get("mp3_long_sine"), dict)
        or not isinstance(transform.get("long_vorbis"), dict)
        or transform.get("opus_long_celt") is not None
        or transform.get("opus_short_celt") is not None
    ):
        raise ValueError(f"{case_id}: benchmark runner contract differs")


def run_case(
    *,
    case: dict,
    audio_root: Path,
    audio_sha256: str,
    runner: Path,
    runner_sha256: str,
    precommit_sha256: str,
    harness_sha256: str,
    partial_root: Path,
) -> tuple[str, bool]:
    case_id = case["case_id"]
    partial = partial_root / f"{case_id}.json"
    if partial.exists():
        row = load_json(partial)
        if (
            row.get("case_id") != case_id
            or row.get("audio_sha256") != audio_sha256
            or row.get("runner_sha256") != runner_sha256
            or row.get("candidate_precommit_sha256")
            != precommit_sha256
            or row.get("harness_sha256") != harness_sha256
        ):
            raise RuntimeError(f"{case_id}: benchmark partial differs")
        validate_runner_result(
            row["runner"],
            case_id=case_id,
            audio_sha256=audio_sha256,
        )
        return case_id, False
    source = resolve_beneath(audio_root, case["relative_path"])
    if sha256_file(source) != audio_sha256:
        raise RuntimeError(f"{case_id}: audio fingerprint differs")
    environment = os.environ.copy()
    environment["LOSSYTRACE_RESEARCH_TRANSFORM_GRID_PROFILE"] = PROFILE
    completed = subprocess.run(
        [
            str(runner),
            case_id,
            str(source),
            "30",
            "1",
            "feature-version=0",
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    if completed.returncode:
        raise RuntimeError(
            f"{case_id}: runner failed ({completed.returncode}): "
            f"{completed.stderr.strip()}"
        )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"{case_id}: invalid benchmark JSON: {error}"
        ) from error
    validate_runner_result(
        result,
        case_id=case_id,
        audio_sha256=audio_sha256,
    )
    write_atomic(
        partial,
        {
            "case_id": case_id,
            "source_group": case["source_group"],
            "partition_group": case["partition_group"],
            "class": case["class"],
            "expectation": case["expectation"],
            "split": case["split"],
            "provenance_tier": case["provenance_tier"],
            "audio_sha256": audio_sha256,
            "runner_sha256": runner_sha256,
            "candidate_precommit_sha256": precommit_sha256,
            "harness_sha256": harness_sha256,
            "runner": result,
        },
    )
    return case_id, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--fingerprints", type=Path, required=True)
    parser.add_argument("--precommit", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        raise SystemExit("--jobs must be in 1..=8")
    output = args.output.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit(f"refusing to replace report: {output}")
    manifest_path = args.manifest.expanduser().resolve()
    fingerprints_path = args.fingerprints.expanduser().resolve()
    precommit_path = args.precommit.expanduser().resolve()
    runner = args.runner.expanduser().resolve()
    audio_root = args.audio_root.expanduser().resolve()
    manifest = load_json(manifest_path)
    fingerprints = load_json(fingerprints_path)
    precommit = load_json(precommit_path)
    validate_contract(
        manifest_path=manifest_path,
        manifest=manifest,
        fingerprints_path=fingerprints_path,
        fingerprints=fingerprints,
        precommit_path=precommit_path,
        precommit=precommit,
        runner=runner,
    )
    runner_sha256 = sha256_file(runner)
    precommit_sha256 = sha256_file(precommit_path)
    harness_sha256 = sha256_file(Path(__file__).resolve())
    partial_root = Path(f"{output}.partial")
    partial_root.mkdir(parents=True, exist_ok=True)
    opening_path = partial_root / "external-transfer-opening.json"
    opening = {
        "schema_version": 1,
        "state": "external_transfer_feature_scores_opened",
        "opened_at": datetime.now(UTC).isoformat(),
        "candidate_id": CANDIDATE_ID,
        "candidate_precommit_sha256": precommit_sha256,
        "manifest_sha256": sha256_file(manifest_path),
        "fingerprints_sha256": sha256_file(fingerprints_path),
        "runner_sha256": runner_sha256,
        "harness_sha256": harness_sha256,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
    }
    if opening_path.exists():
        existing = load_json(opening_path)
        for key, value in opening.items():
            if key != "opened_at" and existing.get(key) != value:
                raise SystemExit("external-transfer opening record differs")
        opening = existing
    else:
        write_atomic(opening_path, opening, replace=False)

    cases = manifest["cases"]
    finished = 0
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.jobs
    ) as pool:
        futures = [
            pool.submit(
                run_case,
                case=case,
                audio_root=audio_root,
                audio_sha256=fingerprints["case_sha256"][
                    case["case_id"]
                ],
                runner=runner,
                runner_sha256=runner_sha256,
                precommit_sha256=precommit_sha256,
                harness_sha256=harness_sha256,
                partial_root=partial_root,
            )
            for case in cases
        ]
        for future in concurrent.futures.as_completed(futures):
            case_id, measured = future.result()
            finished += 1
            print(
                f"[{finished:04d}/{len(cases):04d}] {case_id} "
                f"{'measured' if measured else 'resumed'}",
                flush=True,
            )

    rows = []
    for case in sorted(cases, key=lambda value: value["case_id"]):
        row = load_json(partial_root / f"{case['case_id']}.json")
        validate_runner_result(
            row["runner"],
            case_id=case["case_id"],
            audio_sha256=fingerprints["case_sha256"][case["case_id"]],
        )
        if (
            row.get("runner_sha256") != runner_sha256
            or row.get("candidate_precommit_sha256")
            != precommit_sha256
            or row.get("harness_sha256") != harness_sha256
        ):
            raise SystemExit(f"{case['case_id']}: final partial differs")
        rows.append(row)
    transform_ms = [
        float(row["runner"]["research_transform_grid_elapsed_ms"])
        for row in rows
    ]
    total_overhead = [
        float(row["runner"]["research_total_runtime_overhead_percent"])
        for row in rows
    ]
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": "frozen_external_transfer_measurement_complete",
        "candidate_id": CANDIDATE_ID,
        "candidate_frozen": True,
        "external_transfer_feature_scores_opened": True,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "profile": PROFILE,
        "opening": opening,
        "candidate_precommit": {
            "path": str(precommit_path),
            "sha256": precommit_sha256,
        },
        "manifest": {
            "path": str(manifest_path),
            "sha256": sha256_file(manifest_path),
        },
        "fingerprints": {
            "path": str(fingerprints_path),
            "sha256": sha256_file(fingerprints_path),
        },
        "runner": {
            "path": str(runner),
            "sha256": runner_sha256,
        },
        "harness": {
            "path": str(Path(__file__).resolve()),
            "sha256": harness_sha256,
            "partial_root": str(partial_root),
            "jobs": args.jobs,
        },
        "case_count": len(rows),
        "diagnostic_runtime": {
            "warning": (
                "Concurrent per-case runner timings are diagnostic only; "
                "the frozen paired isolated-process performance report is "
                "the runtime gate evidence."
            ),
            "transform_median_ms": statistics.median(transform_ms),
            "transform_p95_ms": quantile(transform_ms, 0.95),
            "total_overhead_median_percent": statistics.median(
                total_overhead
            ),
            "total_overhead_p95_percent": quantile(
                total_overhead,
                0.95,
            ),
        },
        "results": rows,
    }
    write_atomic(output, report, replace=False)
    print(f"wrote {len(rows)} frozen external-transfer measurements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
