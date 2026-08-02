#!/usr/bin/env python3
"""Run the frozen Cannam Vamp detector on consumed private evidence."""

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


EXPECTED_REVISION = "7a70bd8d15e68b0b1942a9d3deac6ad4d8293b8b"
EXPECTED_SDK_REVISION = "44c2487763eb248a933e9eff9169cfadee375009"
EXPECTED_PLUGIN_KEY = "vamp-lossy-encoding-detector:lossydetector:cf"
WINDOW_THRESHOLD = 0.5
FILE_POSITIVE_FRACTION_THRESHOLD = 0.25
PROBABILITY_LINE = re.compile(
    r"^\s*[0-9]+\.[0-9]+:\s+"
    r"([-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?)"
    r"\s+(?:Original|Lossy)\s*$"
)
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def write_new(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"refusing to replace existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as output:
        json.dump(
            value,
            output,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def resolve_beneath(root: Path, relative: str) -> Path:
    root = root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"path escapes audio root: {relative}") from error
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def quantile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    position = proportion * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def parse_probabilities(output: str) -> list[float]:
    probabilities = [
        float(match.group(1))
        for line in output.splitlines()
        if (match := PROBABILITY_LINE.match(line))
    ]
    if not probabilities or any(
        not math.isfinite(value) or not 0.0 <= value <= 1.0
        for value in probabilities
    ):
        raise ValueError("detector returned no valid probabilities")
    return probabilities


def result_from_probabilities(
    case: dict, audio_sha256: str, probabilities: list[float]
) -> dict:
    positive_fraction = sum(
        value >= WINDOW_THRESHOLD for value in probabilities
    ) / len(probabilities)
    return {
        "case_id": case["case_id"],
        "source_group": case["source_group"],
        "partition_group": case.get("partition_group", case["source_group"]),
        "source_domain": case["source_domain"],
        "split": case["split"],
        "provenance_tier": case["provenance_tier"],
        "class": case["class"],
        "expectation": case["expectation"],
        "audio_sha256": audio_sha256,
        "window_count": len(probabilities),
        "lossy_probability_mean": statistics.fmean(probabilities),
        "lossy_probability_median": statistics.median(probabilities),
        "lossy_probability_p90": quantile(probabilities, 0.90),
        "positive_window_fraction": positive_fraction,
        "detector_binary_label": (
            positive_fraction >= FILE_POSITIVE_FRACTION_THRESHOLD
        ),
    }


def case_binding(case: dict, audio_sha256: str) -> str:
    fields = (
        "case_id",
        "source_group",
        "partition_group",
        "source_domain",
        "split",
        "provenance_tier",
        "class",
        "expectation",
        "relative_path",
    )
    return canonical_sha256(
        {
            **{field: case.get(field) for field in fields},
            "audio_sha256": audio_sha256,
        }
    )


def validate_result(result: object, case: dict, audio_sha256: str) -> dict:
    if not isinstance(result, dict):
        raise ValueError("partial result must be an object")
    expected_metadata = result_from_probabilities(case, audio_sha256, [0.0])
    for field in (
        "case_id",
        "source_group",
        "partition_group",
        "source_domain",
        "split",
        "provenance_tier",
        "class",
        "expectation",
        "audio_sha256",
    ):
        if result.get(field) != expected_metadata[field]:
            raise ValueError(f"partial result differs on {field}")
    probability_fields = (
        "lossy_probability_mean",
        "lossy_probability_median",
        "lossy_probability_p90",
        "positive_window_fraction",
    )
    if (
        not isinstance(result.get("window_count"), int)
        or result["window_count"] <= 0
        or any(
            not isinstance(result.get(field), (int, float))
            or not math.isfinite(result[field])
            or not 0.0 <= result[field] <= 1.0
            for field in probability_fields
        )
        or not isinstance(result.get("detector_binary_label"), bool)
        or result["detector_binary_label"]
        != (
            result["positive_window_fraction"]
            >= FILE_POSITIVE_FRACTION_THRESHOLD
        )
    ):
        raise ValueError("partial result measurements are invalid")
    return result


def partial_path(directory: Path, case_id: str) -> Path:
    return directory / f"{hashlib.sha256(case_id.encode()).hexdigest()}.json"


def evaluate_or_resume_case(
    index: int,
    total: int,
    case: dict,
    *,
    root: Path,
    host: Path,
    vamp_path: Path,
    plugin_key: str,
    run_binding: dict,
    partial_directory: Path,
) -> dict:
    audio_path = resolve_beneath(root, case["relative_path"])
    if not audio_path.is_file() or audio_path.is_symlink():
        raise ValueError(f"case {index}: audio is missing or not regular")
    audio_sha256 = sha256_file(audio_path)
    binding = case_binding(case, audio_sha256)
    checkpoint = partial_path(partial_directory, case["case_id"])
    if checkpoint.exists():
        partial = load(checkpoint)
        if (
            partial.get("schema_version") != 1
            or partial.get("run_binding") != run_binding
            or partial.get("case_binding_sha256") != binding
        ):
            raise ValueError(f"case {index}: existing partial binding differs")
        print(f"[{index:04}/{total}] resumed", file=os.sys.stderr)
        return validate_result(partial.get("result"), case, audio_sha256)

    print(f"[{index:04}/{total}] scoring", file=os.sys.stderr)
    environment = os.environ.copy()
    environment["VAMP_PATH"] = str(vamp_path)
    completed = subprocess.run(
        [str(host), plugin_key, str(audio_path)],
        text=True,
        capture_output=True,
        env=environment,
    )
    if completed.returncode:
        message = completed.stderr.strip().replace(str(audio_path), "<AUDIO>")
        raise ValueError(f"case {index}: detector failed: {message}")
    try:
        probabilities = parse_probabilities(completed.stdout)
    except ValueError as error:
        raise ValueError(f"case {index}: {error}") from error
    result = result_from_probabilities(case, audio_sha256, probabilities)
    write_new(
        checkpoint,
        {
            "schema_version": 1,
            "run_binding": run_binding,
            "case_binding_sha256": binding,
            "result": result,
        },
    )
    return result


def git_revision(repository: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise ValueError("could not resolve detector repository revision")
    return completed.stdout.strip()


def git_tracked_clean(repository: Path) -> bool:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "status",
            "--porcelain",
            "--untracked-files=no",
        ],
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise ValueError("could not inspect detector repository state")
    return not completed.stdout.strip()


def host_version(host: Path) -> str:
    completed = subprocess.run(
        [str(host), "-v"], text=True, capture_output=True
    )
    combined = (completed.stdout + "\n" + completed.stderr).strip().splitlines()
    if completed.returncode or not combined:
        raise ValueError("could not resolve Vamp host version")
    return " | ".join(line.strip() for line in combined if line.strip())


def validate_manifest(manifest: dict, allow_legacy: bool) -> list[dict]:
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest has no cases")
    if not allow_legacy and (
        manifest.get("evidence_partition") != "observed_development"
        or manifest.get("holdout_scores_opened") is not False
    ):
        raise ValueError("manifest is not consumed observed-development evidence")
    required = (
        "case_id",
        "source_group",
        "source_domain",
        "split",
        "provenance_tier",
        "class",
        "expectation",
        "relative_path",
    )
    identifiers = []
    for index, case in enumerate(cases, 1):
        if not isinstance(case, dict) or any(
            not isinstance(case.get(field), str) or not case[field]
            for field in required
        ):
            raise ValueError(f"manifest case {index} metadata is invalid")
        if allow_legacy and case.get("split") == "held_out":
            raise ValueError("legacy manifest contains a held-out case")
        identifiers.append(case["case_id"])
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("manifest case IDs are duplicated")
    return cases


def command(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.expanduser().resolve()
    root = args.audio_root.expanduser().resolve()
    host = args.host.expanduser().resolve()
    vamp_path = args.vamp_path.expanduser().resolve()
    repository = args.repository.expanduser().resolve()
    sdk_repository = args.plugin_sdk_repository.expanduser().resolve()
    plugin_binary = args.plugin_binary.expanduser().resolve()
    partial_directory = args.partial_directory.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    if output_path.exists() or output_path.is_symlink():
        raise SystemExit(f"refusing to replace existing output: {output_path}")
    for path, description in (
        (root, "audio root"),
        (vamp_path, "Vamp plugin path"),
        (repository, "detector repository"),
        (sdk_repository, "Vamp plugin SDK repository"),
    ):
        if not path.is_dir():
            raise SystemExit(f"{description} is not a directory")
    for path, description in ((host, "Vamp host"), (plugin_binary, "plugin binary")):
        if not path.is_file() or path.is_symlink():
            raise SystemExit(f"{description} does not exist or is not regular")
    if not 1 <= args.jobs <= 8:
        raise SystemExit("--jobs must be in 1..=8")
    if args.plugin_key != EXPECTED_PLUGIN_KEY:
        raise SystemExit("plugin key differs from the frozen preregistration")

    try:
        manifest = load(manifest_path)
        cases = validate_manifest(manifest, args.allow_legacy_development_manifest)
        manifest_sha256 = sha256_file(manifest_path)
        if (
            args.expected_manifest_sha256 is not None
            and manifest_sha256 != args.expected_manifest_sha256
        ):
            raise ValueError("manifest SHA-256 differs from the expected binding")
        revision = git_revision(repository)
        if revision != args.expected_revision:
            raise ValueError(
                f"detector revision differs: expected {args.expected_revision}, "
                f"found {revision}"
            )
        sdk_revision = git_revision(sdk_repository)
        if sdk_revision != args.expected_sdk_revision:
            raise ValueError(
                f"Vamp SDK revision differs: expected {args.expected_sdk_revision}, "
                f"found {sdk_revision}"
            )
        if not git_tracked_clean(repository) or not git_tracked_clean(sdk_repository):
            raise ValueError("detector or Vamp SDK tracked source is dirty")
        detector = {
            "name": "cannam/vamp-lossy-encoding-detector",
            "repository": "https://github.com/cannam/vamp-lossy-encoding-detector",
            "revision": revision,
            "plugin_sdk_revision": sdk_revision,
            "plugin_key": args.plugin_key,
            "host_sha256": sha256_file(host),
            "host_version": host_version(host),
            "plugin_binary_sha256": sha256_file(plugin_binary),
            "source_tracked_clean": True,
            "plugin_sdk_tracked_clean": True,
        }
        run_binding = {
            "manifest_sha256": manifest_sha256,
            "detector": detector,
            "decision_rule": {
                "window_threshold": WINDOW_THRESHOLD,
                "file_positive_fraction_threshold": (
                    FILE_POSITIVE_FRACTION_THRESHOLD
                ),
            },
        }
        partial_directory.mkdir(parents=True, exist_ok=True)
        rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = [
                executor.submit(
                    evaluate_or_resume_case,
                    index,
                    len(cases),
                    case,
                    root=root,
                    host=host,
                    vamp_path=vamp_path,
                    plugin_key=args.plugin_key,
                    run_binding=run_binding,
                    partial_directory=partial_directory,
                )
                for index, case in enumerate(cases, 1)
            ]
            for future in futures:
                rows.append(future.result())
        rows.sort(key=lambda row: row["case_id"])

        output = {
            "schema_version": 2,
            "state": "cannam_fixed_rule_raw_v2",
            "corpus_id": manifest["corpus_id"],
            "corpus_version": manifest["corpus_version"],
            "evidence_partition": "observed_development",
            "holdout_scores_opened": False,
            "thresholds_retuned": False,
            "manifest_sha256": manifest_sha256,
            "detector": detector,
            "decision_rule": run_binding["decision_rule"],
            "results": rows,
        }
        write_new(output_path, output)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(f"wrote {len(rows)} deterministic results to {output_path}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--audio-root", type=Path, required=True)
    result.add_argument("--host", type=Path, required=True)
    result.add_argument("--vamp-path", type=Path, required=True)
    result.add_argument("--repository", type=Path, required=True)
    result.add_argument("--plugin-sdk-repository", type=Path, required=True)
    result.add_argument("--plugin-binary", type=Path, required=True)
    result.add_argument("--partial-directory", type=Path, required=True)
    result.add_argument("--expected-revision", default=EXPECTED_REVISION)
    result.add_argument("--expected-sdk-revision", default=EXPECTED_SDK_REVISION)
    result.add_argument("--expected-manifest-sha256")
    result.add_argument("--plugin-key", default=EXPECTED_PLUGIN_KEY)
    result.add_argument("--allow-legacy-development-manifest", action="store_true")
    result.add_argument("--jobs", type=int, default=1)
    result.add_argument("--output", type=Path, required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
