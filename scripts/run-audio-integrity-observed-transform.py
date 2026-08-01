#!/usr/bin/env python3
"""Measure an observed audio corpus with a research transform profile.

This harness is development-only. It records that no candidate is frozen and
that neither a new transfer set nor the release-held-out set was opened.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path


SAFE_CASE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
SAFE_PROFILE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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


def write_atomic(path: Path, value: dict) -> None:
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


def validate_runner_result(
    result: dict,
    *,
    case_id: str,
    audio_sha256: str,
    profile: str,
) -> None:
    if (
        result.get("schema_version") != 1
        or result.get("case_id") != case_id
        or result.get("audio_sha256") != audio_sha256
        or result.get("research_transform_grid_profile") != profile
        or not isinstance(result.get("transform_grid_probe"), dict)
    ):
        raise ValueError(f"{case_id}: transform runner contract differs")


def run_case(
    *,
    case: dict,
    audio_root: Path,
    audio_sha256: str,
    runner: Path,
    runner_sha256: str,
    harness_sha256: str,
    manifest_sha256: str,
    fingerprints_sha256: str,
    profile: str,
    maximum_seconds: float,
    partial_root: Path,
) -> tuple[str, bool]:
    case_id = case["case_id"]
    partial = partial_root / f"{case_id}.json"
    commitment = {
        "case_id": case_id,
        "audio_sha256": audio_sha256,
        "runner_sha256": runner_sha256,
        "harness_sha256": harness_sha256,
        "manifest_sha256": manifest_sha256,
        "fingerprints_sha256": fingerprints_sha256,
        "profile": profile,
    }
    if partial.exists():
        row = load_json(partial)
        if any(row.get(key) != value for key, value in commitment.items()):
            raise RuntimeError(f"{case_id}: partial commitment differs")
        validate_runner_result(
            row["runner"],
            case_id=case_id,
            audio_sha256=audio_sha256,
            profile=profile,
        )
        return case_id, False

    source = resolve_beneath(audio_root, case["relative_path"])
    if sha256_file(source) != audio_sha256:
        raise RuntimeError(f"{case_id}: audio fingerprint differs")
    environment = os.environ.copy()
    environment["LOSSYTRACE_RESEARCH_TRANSFORM_GRID_PROFILE"] = profile
    completed = subprocess.run(
        [
            str(runner),
            case_id,
            str(source),
            str(maximum_seconds),
            "1",
            "feature-version=0",
            "research-mode=transform-only",
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
            f"{case_id}: invalid transform runner JSON: {error}"
        ) from error
    validate_runner_result(
        result,
        case_id=case_id,
        audio_sha256=audio_sha256,
        profile=profile,
    )
    write_atomic(
        partial,
        {
            **commitment,
            "source_group": case["source_group"],
            "partition_group": case["partition_group"],
            "class": case["class"],
            "expectation": case["expectation"],
            "split": case["split"],
            "provenance_tier": case["provenance_tier"],
            "runner": result,
        },
    )
    return case_id, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--fingerprints", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        raise SystemExit("--jobs must be in 1..=8")
    if not SAFE_PROFILE.fullmatch(args.profile):
        raise SystemExit("profile must be a lowercase hyphenated identifier")

    output = args.output.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit(f"refusing to replace report: {output}")
    partial_root = Path(f"{output}.partial")
    manifest_path = args.manifest.expanduser().resolve()
    fingerprints_path = args.fingerprints.expanduser().resolve()
    runner = args.runner.expanduser().resolve()
    audio_root = args.audio_root.expanduser().resolve()
    harness = Path(__file__).resolve()
    for required in (manifest_path, fingerprints_path, runner, harness):
        if not required.is_file():
            raise SystemExit(f"required file missing: {required}")

    manifest = load_json(manifest_path)
    fingerprints = load_json(fingerprints_path)
    cases = manifest.get("cases")
    fingerprint_map = fingerprints.get("case_sha256")
    maximum_seconds = manifest.get("analysis_max_seconds", 30)
    if (
        not isinstance(cases, list)
        or not cases
        or not isinstance(fingerprint_map, dict)
        or manifest.get("corpus_id") != fingerprints.get("corpus_id")
        or not isinstance(maximum_seconds, (int, float))
        or maximum_seconds <= 0
    ):
        raise SystemExit("manifest or fingerprints contract differs")

    required_case_keys = {
        "case_id",
        "relative_path",
        "source_group",
        "partition_group",
        "class",
        "expectation",
        "split",
        "provenance_tier",
    }
    case_ids = []
    for case in cases:
        if not isinstance(case, dict) or not required_case_keys <= set(case):
            raise SystemExit("malformed manifest case")
        case_id = case["case_id"]
        if not isinstance(case_id, str) or not SAFE_CASE_ID.fullmatch(case_id):
            raise SystemExit(f"invalid case ID: {case_id!r}")
        case_ids.append(case_id)
    if (
        len(case_ids) != len(set(case_ids))
        or set(case_ids) != set(fingerprint_map)
        or any(
            not isinstance(fingerprint_map[case_id], str)
            or not re.fullmatch(r"[0-9a-f]{64}", fingerprint_map[case_id])
            for case_id in case_ids
        )
    ):
        raise SystemExit("case and fingerprint inventories differ")

    manifest_sha256 = sha256_file(manifest_path)
    fingerprints_sha256 = sha256_file(fingerprints_path)
    runner_sha256 = sha256_file(runner)
    harness_sha256 = sha256_file(harness)
    partial_root.mkdir(parents=True, exist_ok=True)
    completed_count = 0
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.jobs
    ) as pool:
        futures = [
            pool.submit(
                run_case,
                case=case,
                audio_root=audio_root,
                audio_sha256=fingerprint_map[case["case_id"]],
                runner=runner,
                runner_sha256=runner_sha256,
                harness_sha256=harness_sha256,
                manifest_sha256=manifest_sha256,
                fingerprints_sha256=fingerprints_sha256,
                profile=args.profile,
                maximum_seconds=float(maximum_seconds),
                partial_root=partial_root,
            )
            for case in cases
        ]
        for future in concurrent.futures.as_completed(futures):
            case_id, measured = future.result()
            completed_count += 1
            action = "measured" if measured else "resumed"
            print(
                f"[{completed_count:04d}/{len(cases):04d}] "
                f"{case_id} {action}",
                flush=True,
            )

    results = []
    for case_id in sorted(case_ids):
        partial = partial_root / f"{case_id}.json"
        row = load_json(partial)
        if (
            row.get("profile") != args.profile
            or row.get("runner_sha256") != runner_sha256
            or row.get("harness_sha256") != harness_sha256
            or row.get("manifest_sha256") != manifest_sha256
            or row.get("fingerprints_sha256") != fingerprints_sha256
        ):
            raise SystemExit(f"{case_id}: final partial differs")
        results.append(row)

    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": "observed_development_research_measurement",
        "candidate_frozen": False,
        "new_external_transfer_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "profile": args.profile,
        "case_count": len(results),
        "source_group_count": len(
            {row["source_group"] for row in results}
        ),
        "inputs": {
            "manifest": {
                "path": str(manifest_path),
                "sha256": manifest_sha256,
            },
            "fingerprints": {
                "path": str(fingerprints_path),
                "sha256": fingerprints_sha256,
            },
            "audio_root": str(audio_root),
        },
        "runner": {
            "path": str(runner),
            "sha256": runner_sha256,
        },
        "harness": {
            "path": str(harness),
            "sha256": harness_sha256,
            "jobs": args.jobs,
            "partial_root": str(partial_root),
        },
        "results": results,
    }
    write_atomic(output, report)
    print(f"wrote {len(results)} results to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
