#!/usr/bin/env python3
"""Run the preregistered codec-projection oracle on observed evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path


SAFE_CASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
HEX_GIT_COMMIT = re.compile(r"[0-9a-f]{40}")
EXPECTED_NEGATIVE_CASES = 1_734
EXPECTED_POSITIVE_CASES = 527
EXPECTED_TOTAL_CASES = EXPECTED_NEGATIVE_CASES + EXPECTED_POSITIVE_CASES
EXPECTED_NEGATIVE_GROUPS = 597


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def write_atomic(path: Path, value: object) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing to replace symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as output:
        output.write(canonical_json(value))
        output.flush()
        os.fsync(output.fileno())
        temporary = Path(output.name)
    temporary.replace(path)


def write_new(path: Path, value: object) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"refusing to replace output: {path}")
    write_atomic(path, value)


def resolve_executable(value: str) -> Path:
    candidate = Path(value).expanduser()
    resolved = candidate.resolve() if candidate.parent != Path(".") else None
    if resolved is None or not resolved.is_file():
        located = shutil.which(value)
        if located is None:
            raise ValueError(f"executable is missing: {value}")
        resolved = Path(located).resolve()
    if not os.access(resolved, os.X_OK):
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


def linked_lame_binding(ffmpeg: Path) -> tuple[dict, dict]:
    if shutil.which("otool"):
        output = command_output(["otool", "-L", str(ffmpeg)])
        candidates = [
            line.strip().split(" (", 1)[0]
            for line in output.splitlines()[1:]
            if "libmp3lame" in line
        ]
        command = ["otool", "-L", "<FFMPEG>"]
    elif shutil.which("ldd"):
        output = command_output(["ldd", str(ffmpeg)])
        candidates = []
        for line in output.splitlines():
            if "libmp3lame" not in line:
                continue
            right = line.split("=>", 1)[-1].strip().split(" ", 1)[0]
            candidates.append(right)
        command = ["ldd", "<FFMPEG>"]
    else:
        raise ValueError("neither otool nor ldd is available to bind libmp3lame")
    unique = sorted(set(candidates))
    if len(unique) != 1:
        raise ValueError(f"expected one linked libmp3lame, found {unique!r}")
    library = Path(unique[0]).resolve()
    if not library.is_file():
        raise ValueError(f"linked libmp3lame is missing: {library}")
    public = {
        "basename": library.name,
        "sha256": sha256_file(library),
        "inspection_command_template": command,
    }
    private = {**public, "path": str(library)}
    return public, private


def tool_bindings(ffmpeg_value: str, lame_value: str) -> tuple[dict, dict, Path]:
    ffmpeg = resolve_executable(ffmpeg_value)
    lame = resolve_executable(lame_value)
    ffmpeg_version = command_output([str(ffmpeg), "-version"])
    lame_version = command_output([str(lame), "--version"])
    public_library, private_library = linked_lame_binding(ffmpeg)
    public = {
        "ffmpeg": {
            "basename": ffmpeg.name,
            "sha256": sha256_file(ffmpeg),
            "version_output": ffmpeg_version,
            "version_output_sha256": sha256_bytes(ffmpeg_version.encode()),
        },
        "lame_cli": {
            "basename": lame.name,
            "sha256": sha256_file(lame),
            "version_output": lame_version,
            "version_output_sha256": sha256_bytes(lame_version.encode()),
        },
        "linked_libmp3lame": public_library,
    }
    private = {
        "ffmpeg": {**public["ffmpeg"], "path": str(ffmpeg)},
        "lame_cli": {**public["lame_cli"], "path": str(lame)},
        "linked_libmp3lame": private_library,
    }
    return public, private, ffmpeg


def load_and_validate_config(path: Path) -> dict:
    config = load_object(path)
    selection = config.get("selection")
    projection = config.get("projection")
    if (
        config.get("schema_version") != 1
        or config.get("feature_version") != 0
        or config.get("public_verdict_enabled") is not False
        or config.get("algorithm") != "libmp3lame_cbr128_cycle_residual_v1"
        or not isinstance(selection, dict)
        or not isinstance(projection, dict)
        or selection.get("negative_expectation") != "negative"
        or selection.get("positive_expectation") != "controlled_positive"
        or selection.get("positive_class_exact") != "mp3_128"
        or selection.get("positive_class_suffix") != "_mp3_128_to_flac16"
        or not isinstance(projection.get("encode_args_after_input"), list)
        or not isinstance(projection.get("decode_args_after_input"), list)
    ):
        raise ValueError("codec-projection configuration contract differs")
    return config


def index_cases(rows: object, label: str) -> dict[str, dict]:
    if not isinstance(rows, list):
        raise ValueError(f"{label}: rows must be an array")
    indexed: dict[str, dict] = {}
    for row in rows:
        case_id = row.get("case_id") if isinstance(row, dict) else None
        if not isinstance(case_id, str) or not SAFE_CASE_ID.fullmatch(case_id):
            raise ValueError(f"{label}: missing or unsafe case_id")
        if case_id in indexed:
            raise ValueError(f"{label}: duplicate case_id {case_id}")
        indexed[case_id] = row
    return indexed


def validate_inputs(manifest: dict, baseline: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    baseline_gate = baseline.get("gate_disposition")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("evidence_partition") != "observed_development"
        or manifest.get("holdout_scores_opened") is not False
        or baseline.get("schema_version") != 1
        or baseline.get("feature_version") != 0
        or not isinstance(baseline_gate, dict)
        or baseline_gate.get("likely_lossy_derived_enabled") is not False
    ):
        raise ValueError("observed manifest or verdict-free baseline contract differs")
    cases = index_cases(manifest.get("cases"), "manifest")
    baseline_rows = index_cases(baseline.get("results"), "baseline")
    if cases.keys() != baseline_rows.keys():
        raise ValueError("manifest and baseline inventories differ")
    return cases, baseline_rows


def target_positive(case: dict, config: dict) -> bool:
    selection = config["selection"]
    class_name = case.get("class")
    return (
        case.get("expectation") == selection["positive_expectation"]
        and isinstance(class_name, str)
        and (
            class_name == selection["positive_class_exact"]
            or class_name.endswith(selection["positive_class_suffix"])
        )
    )


def select_cases(cases: list[dict], config: dict) -> list[dict]:
    selected = [
        case
        for case in cases
        if case.get("expectation") == config["selection"]["negative_expectation"]
        or target_positive(case, config)
    ]
    negative = [case for case in selected if case.get("expectation") == "negative"]
    positive = [case for case in selected if target_positive(case, config)]
    required_metadata = (
        "case_id",
        "relative_path",
        "source_group",
        "partition_group",
        "source_domain",
        "class",
        "expectation",
        "provenance_tier",
    )
    for case in selected:
        if any(
            not isinstance(case.get(field), str) or not case[field]
            for field in required_metadata
        ):
            raise ValueError(f"{case.get('case_id')}: selected case metadata is invalid")
    negative_groups = {case.get("source_group") for case in negative}
    if (
        len(selected) != EXPECTED_TOTAL_CASES
        or len(negative) != EXPECTED_NEGATIVE_CASES
        or len(positive) != EXPECTED_POSITIVE_CASES
        or len(negative_groups) != EXPECTED_NEGATIVE_GROUPS
    ):
        raise ValueError(
            "selected inventory differs: "
            f"total={len(selected)} negative={len(negative)} "
            f"positive={len(positive)} negative_groups={len(negative_groups)}"
        )
    return sorted(selected, key=lambda case: case["case_id"])


def audio_sha256(baseline_row: dict) -> str:
    runner = baseline_row.get("runner")
    value = runner.get("audio_sha256") if isinstance(runner, dict) else None
    if not isinstance(value, str) or not HEX_SHA256.fullmatch(value):
        raise ValueError(f"{baseline_row.get('case_id')}: invalid baseline audio hash")
    return value


def resolve_audio(corpus_root: Path, relative_path: object) -> Path:
    if not isinstance(relative_path, str):
        raise ValueError("relative audio path is missing")
    source = (corpus_root / relative_path).resolve()
    if not source.is_relative_to(corpus_root) or not source.is_file():
        raise ValueError(f"relative audio path is missing or unsafe: {relative_path}")
    return source


def validate_measurement(case_id: str, measurement: object, algorithm: str) -> dict:
    if (
        not isinstance(measurement, dict)
        or measurement.get("schema_version") != 1
        or measurement.get("state") != "codec_projection_raw_case_v1"
        or measurement.get("feature_version") != 0
        or measurement.get("public_verdict_enabled") is not False
        or measurement.get("case_id") != case_id
        or measurement.get("algorithm") != algorithm
        or not isinstance(measurement.get("projection_performed"), bool)
        or not isinstance(measurement.get("support"), dict)
        or not isinstance(measurement.get("blocks"), list)
    ):
        raise ValueError(f"{case_id}: oracle measurement contract differs")
    supported = measurement["support"].get("supported")
    scores = measurement.get("scores")
    blocks = measurement["blocks"]
    previous_index = -1
    for block in blocks:
        fields = (
            "signal_power",
            "first_residual_power",
            "second_residual_power",
            "r1_cycle_residual_retention",
            "r1_equivalent_db",
            "r2_residual_directional_recurrence",
        )
        index = block.get("block_index") if isinstance(block, dict) else None
        if not isinstance(index, int) or index <= previous_index:
            raise ValueError(f"{case_id}: block indices are invalid")
        previous_index = index
        if any(
            not isinstance(block.get(field), (int, float))
            or not math.isfinite(block[field])
            for field in fields
        ):
            raise ValueError(f"{case_id}: block measurement is invalid")
        first_power = float(block["first_residual_power"])
        second_power = float(block["second_residual_power"])
        if first_power <= 0.0 or second_power <= 0.0:
            raise ValueError(f"{case_id}: residual power is invalid")
        expected_r1 = second_power / (first_power + second_power)
        expected_db = 10.0 * math.log10(second_power / first_power)
        if not math.isclose(
            block["r1_cycle_residual_retention"], expected_r1, rel_tol=1.0e-14
        ) or not math.isclose(
            block["r1_equivalent_db"], expected_db, rel_tol=1.0e-14
        ):
            raise ValueError(f"{case_id}: block formula replay differs")
        if not 0.0 <= block["r2_residual_directional_recurrence"] <= 1.0:
            raise ValueError(f"{case_id}: block R2 is out of bounds")
    stored_block_count = measurement["support"].get(
        "supported_measurement_block_count"
    )
    if stored_block_count is not None and stored_block_count != len(blocks):
        raise ValueError(f"{case_id}: supported block count differs")
    if supported is True:
        if not isinstance(scores, dict):
            raise ValueError(f"{case_id}: supported measurement has no scores")
        if not blocks:
            raise ValueError(f"{case_id}: supported measurement has no blocks")
        if stored_block_count != len(blocks):
            raise ValueError(f"{case_id}: supported measurement block count is missing")
        for field in (
            "r1_cycle_residual_retention",
            "r2_residual_directional_recurrence",
        ):
            value = scores.get(field)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{case_id}: {field} is invalid")
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{case_id}: {field} is out of bounds")
        r1_values = [float(block["r1_cycle_residual_retention"]) for block in blocks]
        r1_db_values = [float(block["r1_equivalent_db"]) for block in blocks]
        r2_values = [
            float(block["r2_residual_directional_recurrence"]) for block in blocks
        ]
        expected_scores = {
            "r1_cycle_residual_retention": quantile(r1_values, 0.5),
            "r1_interquartile_range": quantile(r1_values, 0.75)
            - quantile(r1_values, 0.25),
            "r1_equivalent_db_median": quantile(r1_db_values, 0.5),
            "r2_residual_directional_recurrence": quantile(r2_values, 0.5),
            "r2_interquartile_range": quantile(r2_values, 0.75)
            - quantile(r2_values, 0.25),
        }
        for field, expected in expected_scores.items():
            observed = scores.get(field)
            if (
                not isinstance(observed, (int, float))
                or not math.isfinite(observed)
                or expected is None
                or not math.isclose(
                    observed, expected, rel_tol=1.0e-14, abs_tol=1.0e-15
                )
            ):
                raise ValueError(f"{case_id}: {field} aggregation replay differs")
    elif supported is False:
        if scores is not None:
            raise ValueError(f"{case_id}: unsupported measurement has scores")
    else:
        raise ValueError(f"{case_id}: support state is invalid")
    return measurement


def validate_timing(case_id: str, timing: object) -> dict:
    if (
        not isinstance(timing, dict)
        or timing.get("schema_version") != 1
        or timing.get("state") != "codec_projection_case_timing_v1"
        or timing.get("case_id") != case_id
        or not isinstance(timing.get("elapsed_ms"), (int, float))
        or not math.isfinite(timing["elapsed_ms"])
        or timing["elapsed_ms"] < 0
        or timing.get("ffmpeg_command_count") not in (1, 5)
    ):
        raise ValueError(f"{case_id}: timing contract differs")
    peak = timing.get("peak_resident_bytes")
    if peak is not None and (not isinstance(peak, int) or peak <= 0):
        raise ValueError(f"{case_id}: peak memory is invalid")
    return timing


def commitment_for(case: dict, expected_audio_sha256: str, global_commitments: dict) -> dict:
    return {
        **global_commitments,
        "case_id": case["case_id"],
        "audio_sha256": expected_audio_sha256,
        "source_group": case.get("source_group"),
        "partition_group": case.get("partition_group"),
        "source_domain": case.get("source_domain"),
        "class": case.get("class"),
        "expectation": case.get("expectation"),
        "provenance_tier": case.get("provenance_tier"),
    }


def validate_resumed_row(row: object, commitment: dict, algorithm: str) -> dict:
    if not isinstance(row, dict):
        raise ValueError(f"{commitment['case_id']}: resumed row is invalid")
    for field in (
        "case_id",
        "audio_sha256",
        "source_group",
        "partition_group",
        "source_domain",
        "class",
        "expectation",
        "provenance_tier",
    ):
        if row.get(field) != commitment[field]:
            raise ValueError(f"{commitment['case_id']}: resumed {field} differs")
    validate_measurement(commitment["case_id"], row.get("measurement"), algorithm)
    return row


def run_case(
    *,
    case: dict,
    baseline_row: dict,
    corpus_root: Path,
    oracle: Path,
    config_path: Path,
    ffmpeg: Path,
    global_commitments: dict,
    partial_path: Path,
    timing_path: Path,
    algorithm: str,
) -> tuple[dict, dict, bool]:
    case_id = case["case_id"]
    expected_audio_sha256 = audio_sha256(baseline_row)
    commitment = commitment_for(case, expected_audio_sha256, global_commitments)
    for path, label in ((partial_path, "partial"), (timing_path, "timing")):
        if path.is_symlink():
            raise ValueError(f"{case_id}: {label} must not be a symlink")
    if partial_path.exists():
        partial = load_object(partial_path)
        if partial.get("schema_version") != 1 or partial.get("commitment") != commitment:
            raise ValueError(f"{case_id}: partial commitment differs")
        row = validate_resumed_row(partial.get("row"), commitment, algorithm)
        if not timing_path.is_file():
            raise ValueError(f"{case_id}: resumed timing is missing")
        timing = validate_timing(case_id, load_object(timing_path))
        return row, timing, False
    if timing_path.exists():
        raise ValueError(f"{case_id}: timing exists without a committed partial")
    source = resolve_audio(corpus_root, case.get("relative_path"))
    if sha256_file(source) != expected_audio_sha256:
        raise ValueError(f"{case_id}: audio hash differs from baseline")
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
            f"{case_id}: oracle failed ({completed.returncode}): "
            f"{completed.stderr.strip()}"
        )
    try:
        measurement = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"{case_id}: oracle JSON is invalid: {error}") from error
    measurement = validate_measurement(case_id, measurement, algorithm)
    if not timing_path.is_file():
        raise ValueError(f"{case_id}: oracle did not write timing evidence")
    timing = validate_timing(case_id, load_object(timing_path))
    row = {
        "case_id": case_id,
        "audio_sha256": expected_audio_sha256,
        "source_group": case["source_group"],
        "partition_group": case["partition_group"],
        "source_domain": case["source_domain"],
        "class": case["class"],
        "expectation": case["expectation"],
        "provenance_tier": case["provenance_tier"],
        "measurement": measurement,
    }
    write_atomic(
        partial_path,
        {"schema_version": 1, "commitment": commitment, "row": row},
    )
    return row, timing, True


def quantile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = proportion * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def timing_summary(rows: list[dict]) -> dict:
    elapsed = [float(row["elapsed_ms"]) for row in rows]
    peaks = [row["peak_resident_bytes"] for row in rows if row["peak_resident_bytes"] is not None]
    return {
        "case_count": len(rows),
        "median_elapsed_ms": statistics.median(elapsed),
        "p95_elapsed_ms": quantile(elapsed, 0.95),
        "maximum_peak_resident_bytes": max(peaks) if peaks else None,
        "total_elapsed_ms": sum(elapsed),
    }


def repository_state(repository: Path) -> tuple[str, str]:
    commit = command_output(["git", "-C", str(repository), "rev-parse", "HEAD"]).strip()
    if not HEX_GIT_COMMIT.fullmatch(commit):
        raise ValueError("repository HEAD is invalid")
    status = command_output(["git", "-C", str(repository), "status", "--porcelain"])
    if status:
        raise ValueError("repository must be clean before a bound measurement run")
    branch = command_output(
        ["git", "-C", str(repository), "branch", "--show-current"]
    ).strip()
    if branch != "codex/codec-projection-feasibility":
        raise ValueError(f"unexpected measurement branch: {branch!r}")
    return commit, branch


def command_templates(config: dict) -> dict:
    canonical = config["canonical_pcm"]

    def ffmpeg_number(value: int | float) -> str:
        return format(value, ".15g")

    return {
        "source_decode": [
            "<FFMPEG>",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            ffmpeg_number(canonical["start_seconds"]),
            "-t",
            ffmpeg_number(canonical["duration_seconds"]),
            "-i",
            "<SOURCE_AUDIO>",
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-fflags",
            "+bitexact",
            "-flags:a",
            "+bitexact",
            "-ar",
            ffmpeg_number(canonical["sample_rate_hz"]),
            "-ac",
            ffmpeg_number(canonical["channel_count"]),
            "-c:a",
            "pcm_f32le",
            "-f",
            "f32le",
            "pipe:1",
        ],
        "projection_encode": [
            "<FFMPEG>",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "s16le",
            "-ar",
            ffmpeg_number(canonical["sample_rate_hz"]),
            "-ac",
            ffmpeg_number(canonical["channel_count"]),
            "-i",
            "<INPUT_S16LE>",
            *config["projection"]["encode_args_after_input"],
            "<OUTPUT_MP3>",
        ],
        "projection_decode": [
            "<FFMPEG>",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            "<INPUT_MP3>",
            *config["projection"]["decode_args_after_input"],
            "<OUTPUT_S16LE>",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--baseline-report", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--partial-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timing-output", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--lame", default="lame")
    parser.add_argument("--jobs", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.jobs != 1:
            raise ValueError("the preregistered run requires --jobs 1")
        harness = Path(__file__).resolve()
        repository = harness.parent.parent
        paths = {
            "manifest": args.manifest.expanduser().resolve(),
            "baseline": args.baseline_report.expanduser().resolve(),
            "corpus_root": args.corpus_root.expanduser().resolve(),
            "oracle": args.oracle.expanduser().resolve(),
            "config": args.config.expanduser().resolve(),
            "preregistration": args.preregistration.expanduser().resolve(),
            "partial_root": args.partial_root.expanduser().resolve(),
            "output": args.output.expanduser().resolve(),
            "timing_output": args.timing_output.expanduser().resolve(),
        }
        for name in ("manifest", "baseline", "oracle", "config", "preregistration"):
            if not paths[name].is_file():
                raise ValueError(f"required {name} is missing: {paths[name]}")
        if not paths["corpus_root"].is_dir():
            raise ValueError(f"corpus root is missing: {paths['corpus_root']}")
        if not os.access(paths["oracle"], os.X_OK):
            raise ValueError(f"oracle is not executable: {paths['oracle']}")
        for name in ("output", "timing_output"):
            if paths[name].exists() or paths[name].is_symlink():
                raise ValueError(f"refusing to replace {name}: {paths[name]}")
        if paths["partial_root"].is_symlink():
            raise ValueError("partial root must not be a symlink")
        paths["partial_root"].mkdir(parents=True, exist_ok=True)
        case_timing_root = paths["partial_root"] / "timing"
        if case_timing_root.is_symlink():
            raise ValueError("case timing root must not be a symlink")
        case_timing_root.mkdir(parents=True, exist_ok=True)

        config = load_and_validate_config(paths["config"])
        manifest = load_object(paths["manifest"])
        baseline = load_object(paths["baseline"])
        cases_by_id, baseline_by_id = validate_inputs(manifest, baseline)
        selected = select_cases(list(cases_by_id.values()), config)
        commit, branch = repository_state(repository)
        public_tools, private_tools, ffmpeg = tool_bindings(args.ffmpeg, args.lame)
        global_commitments = {
            "repository_commit": commit,
            "manifest_sha256": sha256_file(paths["manifest"]),
            "baseline_report_sha256": sha256_file(paths["baseline"]),
            "config_sha256": sha256_file(paths["config"]),
            "preregistration_sha256": sha256_file(paths["preregistration"]),
            "oracle_sha256": sha256_file(paths["oracle"]),
            "harness_sha256": sha256_file(harness),
            "ffmpeg_sha256": public_tools["ffmpeg"]["sha256"],
            "lame_cli_sha256": public_tools["lame_cli"]["sha256"],
            "linked_libmp3lame_sha256": public_tools["linked_libmp3lame"]["sha256"],
        }
        results: list[dict] = []
        timings: list[dict] = []
        for index, case in enumerate(selected, 1):
            row, timing, measured = run_case(
                case=case,
                baseline_row=baseline_by_id[case["case_id"]],
                corpus_root=paths["corpus_root"],
                oracle=paths["oracle"],
                config_path=paths["config"],
                ffmpeg=ffmpeg,
                global_commitments=global_commitments,
                partial_path=paths["partial_root"] / f"{case['case_id']}.json",
                timing_path=case_timing_root / f"{case['case_id']}.json",
                algorithm=config["algorithm"],
            )
            results.append(row)
            timings.append(timing)
            action = "measured" if measured else "resumed"
            support = row["measurement"]["support"]["reason"]
            print(
                f"[{index:04d}/{len(selected):04d}] {case['case_id']} "
                f"{action} {support}",
                flush=True,
            )
        raw_report = {
            "schema_version": 1,
            "state": "codec_projection_observed_raw_v1",
            "feature_version": 0,
            "candidate_frozen": False,
            "independent_validation": False,
            "future_codec_only_opened": False,
            "release_heldout_opened": False,
            "public_verdict_enabled": False,
            "warning": (
                "Consumed development evidence only. No result authorizes a "
                "lossy-source, authenticity, codec, or provenance verdict."
            ),
            "commitments": global_commitments,
            "tool_bindings": public_tools,
            "command_templates": command_templates(config),
            "selection": {
                "case_count": len(results),
                "negative_case_count": EXPECTED_NEGATIVE_CASES,
                "target_positive_case_count": EXPECTED_POSITIVE_CASES,
                "negative_source_group_count": EXPECTED_NEGATIVE_GROUPS,
            },
            "results": sorted(results, key=lambda row: row["case_id"]),
        }
        timing_report = {
            "schema_version": 1,
            "state": "codec_projection_observed_timing_v1",
            "created_at": datetime.now(UTC).isoformat(),
            "non_reproducibility_evidence": True,
            "raw_report_sha256": sha256_bytes(canonical_json(raw_report)),
            "repository": {
                "path": str(repository),
                "commit": commit,
                "branch": branch,
            },
            "private_paths": {name: str(path) for name, path in paths.items()},
            "tool_bindings": private_tools,
            "summary": timing_summary(timings),
            "results": sorted(timings, key=lambda row: row["case_id"]),
        }
        write_new(paths["output"], raw_report)
        write_new(paths["timing_output"], timing_report)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(
        json.dumps(
            {
                "case_count": len(raw_report["results"]),
                "output": str(paths["output"]),
                "sha256": sha256_file(paths["output"]),
                "timing_output": str(paths["timing_output"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
