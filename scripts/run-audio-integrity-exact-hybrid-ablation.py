#!/usr/bin/env python3
"""Run the preregistered exact-hybrid probe on observed development audio."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path


START_SECONDS = 5
DURATION_SECONDS = 20
ALGORITHM = "iso11172_3_polyphase_analysis_plus_long_hybrid_mdct"
DEFAULT_POSITIVE_CLASS_REGEX = r"(?:mp3_128|.*_mp3_128_to_flac16)"
EXPECTED_PHASE_OFFSETS = [0, 72, 144, 216, 288, 360, 432, 504]
SAFE_CASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


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


def write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def index_unique(rows: list[dict], label: str) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for row in rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not SAFE_CASE_ID.fullmatch(case_id):
            raise ValueError(f"{label}: case_id is missing or unsafe")
        if case_id in indexed:
            raise ValueError(f"{label}: duplicate case_id {case_id}")
        indexed[case_id] = row
    return indexed


def validate_inputs(manifest: dict, baseline: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    if (
        manifest.get("schema_version") != 1
        or manifest.get("evidence_partition") != "observed_development"
        or manifest.get("holdout_scores_opened") is not False
    ):
        raise ValueError("manifest is not sealed observed development evidence")
    gate = baseline.get("gate_disposition")
    if (
        baseline.get("schema_version") != 1
        or baseline.get("feature_version") != 0
        or not isinstance(gate, dict)
        or gate.get("likely_lossy_derived_enabled") is not False
    ):
        raise ValueError("baseline report is not verdict-free feature version 0")
    cases = manifest.get("cases")
    rows = baseline.get("results")
    if not isinstance(cases, list) or not isinstance(rows, list):
        raise ValueError("manifest cases and baseline results must be arrays")
    cases_by_id = index_unique(cases, "manifest")
    baseline_by_id = index_unique(rows, "baseline")
    if cases_by_id.keys() != baseline_by_id.keys():
        raise ValueError("manifest and baseline case inventories differ")
    return cases_by_id, baseline_by_id


def select_cases(cases: list[dict], positive_class: re.Pattern[str]) -> list[dict]:
    selected = [
        case
        for case in cases
        if case.get("expectation") == "negative"
        or (
            case.get("expectation") == "controlled_positive"
            and isinstance(case.get("class"), str)
            and positive_class.fullmatch(case["class"])
        )
    ]
    if not selected:
        raise ValueError("ablation selection is empty")
    return sorted(selected, key=lambda case: case["case_id"])


def validate_probe(case_id: str, measured: object) -> dict:
    if (
        not isinstance(measured, dict)
        or measured.get("schema_version") != 2
        or measured.get("feature_version") != 0
        or measured.get("case_id") != case_id
        or measured.get("algorithm") != ALGORITHM
        or measured.get("public_verdict_enabled") is not False
        or measured.get("phase_offsets_samples") != EXPECTED_PHASE_OFFSETS
    ):
        raise ValueError(f"{case_id}: probe contract differs")
    return measured


def run_case(
    *,
    case: dict,
    baseline_row: dict,
    source: Path,
    runner: Path,
    commitments: dict,
    partial: Path,
    ffmpeg: str,
) -> dict:
    baseline_runner = baseline_row.get("runner")
    if not isinstance(baseline_runner, dict):
        raise ValueError(f"{case['case_id']}: baseline runner is missing")
    expected_audio_sha256 = baseline_runner.get("audio_sha256")
    if not isinstance(expected_audio_sha256, str) or len(expected_audio_sha256) != 64:
        raise ValueError(f"{case['case_id']}: baseline audio hash is invalid")
    trace = baseline_runner.get("compression_trace")
    if not isinstance(trace, dict):
        raise ValueError(f"{case['case_id']}: baseline compression trace is missing")
    expected_edge = {
        "spectral_edge_drop_db": trace.get("spectral_edge_drop_db"),
        "spectral_edge_persistence": trace.get("spectral_edge_persistence"),
    }
    commitment = {
        **commitments,
        "case_id": case["case_id"],
        "audio_sha256": expected_audio_sha256,
    }
    if partial.is_symlink():
        raise ValueError(f"{case['case_id']}: partial must not be a symlink")
    if partial.exists():
        result = load_object(partial)
        if any(result.get(key) != value for key, value in commitment.items()):
            raise ValueError(f"{case['case_id']}: partial commitment differs")
        for field in (
            "source_group",
            "source_domain",
            "class",
            "expectation",
            "provenance_tier",
        ):
            if result.get(field) != case.get(field):
                raise ValueError(f"{case['case_id']}: partial {field} differs")
        if result.get("baseline_edge") != expected_edge:
            raise ValueError(f"{case['case_id']}: partial baseline edge differs")
        validate_probe(case["case_id"], result.get("probe"))
        return result
    if sha256_file(source) != expected_audio_sha256:
        raise ValueError(f"{case['case_id']}: audio hash differs from baseline")

    decoder = subprocess.Popen(
        [
            ffmpeg,
            "-v",
            "error",
            "-ss",
            str(START_SECONDS),
            "-t",
            str(DURATION_SECONDS),
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
        [str(runner), case["case_id"]],
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
            f"{case['case_id']}: FFmpeg failed ({decoder_returncode}): "
            f"{decoder_stderr.decode(errors='replace').strip()}"
        )
    if probe.returncode:
        raise ValueError(
            f"{case['case_id']}: probe failed ({probe.returncode}): "
            f"{probe.stderr.decode(errors='replace').strip()}"
        )
    try:
        measured = json.loads(probe.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"{case['case_id']}: probe JSON is invalid: {error}") from error
    measured = validate_probe(case["case_id"], measured)
    result = {
        **commitment,
        "source_group": case["source_group"],
        "source_domain": case["source_domain"],
        "class": case["class"],
        "expectation": case["expectation"],
        "provenance_tier": case["provenance_tier"],
        "baseline_edge": expected_edge,
        "probe": measured,
    }
    write_atomic(partial, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--baseline-report", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--positive-class-regex", default=DEFAULT_POSITIVE_CLASS_REGEX
    )
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    try:
        if args.jobs != 1:
            raise ValueError("the preregistered ablation requires --jobs 1")
        try:
            positive_class = re.compile(args.positive_class_regex)
        except re.error as error:
            raise ValueError(f"invalid positive class regex: {error}") from error
        manifest_path = args.manifest.expanduser().resolve()
        baseline_path = args.baseline_report.expanduser().resolve()
        corpus_root = args.corpus_root.expanduser().resolve()
        runner = args.runner.expanduser().resolve()
        output = args.output.expanduser().resolve()
        harness = Path(__file__).resolve()
        if output.exists() or output.is_symlink():
            raise ValueError(f"refusing to replace report: {output}")
        for path in (manifest_path, baseline_path, runner, harness):
            if not path.is_file():
                raise ValueError(f"required file is missing: {path}")
        if not corpus_root.is_dir():
            raise ValueError(f"corpus root is missing: {corpus_root}")
        manifest = load_object(manifest_path)
        baseline = load_object(baseline_path)
        cases_by_id, baseline_by_id = validate_inputs(manifest, baseline)
        selected = select_cases(list(cases_by_id.values()), positive_class)
        commitments = {
            "manifest_sha256": sha256_file(manifest_path),
            "baseline_report_sha256": sha256_file(baseline_path),
            "runner_sha256": sha256_file(runner),
            "harness_sha256": sha256_file(harness),
        }
        partial_root = Path(f"{output}.partial")
        partial_root.mkdir(parents=True, exist_ok=True)

        def submit(case: dict) -> dict:
            source = (corpus_root / case["relative_path"]).resolve()
            if not source.is_relative_to(corpus_root) or not source.is_file():
                raise ValueError(f"{case['case_id']}: audio path is missing or unsafe")
            return run_case(
                case=case,
                baseline_row=baseline_by_id[case["case_id"]],
                source=source,
                runner=runner,
                commitments=commitments,
                partial=partial_root / f"{case['case_id']}.json",
                ffmpeg=args.ffmpeg,
            )

        results = []
        for index, case in enumerate(selected, 1):
            result = submit(case)
            results.append(result)
            print(f"[{index:04d}/{len(selected):04d}] {result['case_id']}", flush=True)
        ffmpeg_version = subprocess.run(
            [args.ffmpeg, "-version"], check=True, text=True, capture_output=True
        ).stdout.splitlines()[0]
        report = {
            "schema_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "state": "observed_development_exact_hybrid_ablation",
            "feature_version": 0,
            "candidate_frozen": False,
            "independent_validation": False,
            "future_codec_only_opened": False,
            "release_heldout_opened": False,
            "public_verdict_enabled": False,
            "warning": (
                "Consumed development measurements only. No result authorizes a "
                "lossy-source, authenticity, or provenance verdict."
            ),
            "selection": {
                "negative_expectation": "negative",
                "positive_class_fullmatch_regex": args.positive_class_regex,
                "case_count": len(results),
                "source_group_count": len({row["source_group"] for row in results}),
            },
            "measurement": {
                "start_seconds": START_SECONDS,
                "duration_seconds": DURATION_SECONDS,
                "sample_rate_hz": 44_100,
                "channel_count": 1,
                "ffmpeg_version": ffmpeg_version,
            },
            "inputs": {
                **commitments,
                "manifest_path": str(manifest_path),
                "baseline_report_path": str(baseline_path),
                "corpus_root": str(corpus_root),
                "runner_path": str(runner),
            },
            "results": sorted(results, key=lambda row: row["case_id"]),
        }
        write_atomic(output, report)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(
        json.dumps(
            {
                "case_count": len(report["results"]),
                "output": str(output),
                "sha256": sha256_file(output),
                "source_group_count": report["selection"]["source_group_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
