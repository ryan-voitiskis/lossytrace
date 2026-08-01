#!/usr/bin/env python3
"""Evaluate an external Vamp lossy-encoding detector on a private manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROBABILITY_LINE = re.compile(
    r"^\s*[0-9]+\.[0-9]+:\s+"
    r"([-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?)"
    r"\s+(?:Original|Lossy)\s*$"
)


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


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


def resolve_beneath(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise SystemExit(f"path escapes audio root: {relative}") from error
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def quantile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    position = proportion * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def evaluate_case(
    index: int,
    total: int,
    case: dict,
    *,
    root: Path,
    host: Path,
    vamp_path: Path,
    plugin_key: str,
) -> dict:
    print(f"[{index:03}/{total}] {case['case_id']}", file=os.sys.stderr)
    audio_path = resolve_beneath(root, case["relative_path"])
    if not audio_path.is_file():
        raise RuntimeError(f"{case['case_id']}: missing audio: {audio_path}")
    environment = os.environ.copy()
    environment["VAMP_PATH"] = str(vamp_path)
    completed = subprocess.run(
        [str(host), plugin_key, str(audio_path)],
        text=True,
        capture_output=True,
        env=environment,
    )
    if completed.returncode:
        raise RuntimeError(
            f"{case['case_id']}: detector failed: {completed.stderr.strip()}"
        )
    probabilities = [
        float(match.group(1))
        for line in completed.stdout.splitlines()
        if (match := PROBABILITY_LINE.match(line))
    ]
    if not probabilities or any(
        not math.isfinite(value) or not 0.0 <= value <= 1.0
        for value in probabilities
    ):
        raise RuntimeError(
            f"{case['case_id']}: detector returned no valid probabilities"
        )
    positive_fraction = sum(value >= 0.5 for value in probabilities) / len(
        probabilities
    )
    return {
        "case_id": case["case_id"],
        "source_group": case["source_group"],
        "split": case["split"],
        "provenance_tier": case["provenance_tier"],
        "class": case["class"],
        "expectation": case["expectation"],
        "audio_sha256": sha256_file(audio_path),
        "window_count": len(probabilities),
        "lossy_probability_mean": statistics.fmean(probabilities),
        "lossy_probability_median": statistics.median(probabilities),
        "lossy_probability_p90": quantile(probabilities, 0.90),
        "positive_window_fraction": positive_fraction,
        "detector_binary_label": positive_fraction >= 0.25,
    }


def command(args: argparse.Namespace) -> int:
    manifest = load(args.manifest)
    root = args.audio_root.resolve()
    host = args.host.resolve()
    vamp_path = args.vamp_path.resolve()
    if not root.is_dir():
        raise SystemExit(f"audio root is not a directory: {root}")
    if not host.is_file():
        raise SystemExit(f"Vamp host does not exist: {host}")
    if not vamp_path.is_dir():
        raise SystemExit(f"Vamp plugin path is not a directory: {vamp_path}")
    if not 1 <= args.jobs <= 8:
        raise SystemExit("--jobs must be in 1..=8")

    cases = manifest.get("cases", [])
    if not cases:
        raise SystemExit("manifest has no cases")
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = [
            executor.submit(
                evaluate_case,
                index,
                len(cases),
                case,
                root=root,
                host=host,
                vamp_path=vamp_path,
                plugin_key=args.plugin_key,
            )
            for index, case in enumerate(cases, 1)
        ]
        for future in futures:
            rows.append(future.result())
    rows.sort(key=lambda row: row["case_id"])

    revision = subprocess.run(
        ["git", "-C", str(vamp_path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
    )
    output = {
        "schema_version": 1,
        "corpus_id": manifest["corpus_id"],
        "corpus_version": manifest["corpus_version"],
        "detector": {
            "name": "cannam/vamp-lossy-encoding-detector",
            "repository": "https://github.com/cannam/vamp-lossy-encoding-detector",
            "revision": (
                revision.stdout.strip() if revision.returncode == 0 else None
            ),
            "plugin_key": args.plugin_key,
            "host_sha256": sha256_file(host),
        },
        "results": rows,
    }
    write_atomic(args.output, output)
    print(f"wrote {len(rows)} results to {args.output}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--audio-root", type=Path, required=True)
    result.add_argument("--host", type=Path, required=True)
    result.add_argument("--vamp-path", type=Path, required=True)
    result.add_argument(
        "--plugin-key",
        default="vamp-lossy-encoding-detector:lossydetector:cf",
    )
    result.add_argument("--jobs", type=int, default=2)
    result.add_argument("--output", type=Path, required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
