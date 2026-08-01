#!/usr/bin/env python3
"""Run the retained AAC quantization probe on the consumed v29 transfer set."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BASE_PATH = ROOT / "scripts" / "evaluate-audio-integrity-aac-quantization.py"
SPEC = importlib.util.spec_from_file_location(
    "audio_integrity_aac_quantization_base",
    BASE_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise SystemExit(f"cannot load quantization runner: {BASE_PATH}")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    return value


def write_atomic(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace report: {path}")
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--gate-evaluation", type=Path, required=True)
    parser.add_argument("--sampling-count", type=int, choices=[8, 16], default=8)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    runner = args.runner.expanduser().resolve()
    corpus_root = args.corpus_root.expanduser().resolve()
    evaluation_path = args.gate_evaluation.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not runner.is_file() or runner.is_symlink():
        raise SystemExit(f"invalid runner: {runner}")
    if not 1 <= args.jobs <= 16:
        raise SystemExit("--jobs must be in 1..=16")
    evaluation = load_json(evaluation_path)
    if (
        evaluation.get("state") != "one_use_external_transfer_evaluated"
        or evaluation.get("disposition")
        != "candidate_rejected_external_transfer_consumed"
        or evaluation.get("external_transfer_consumed") is not True
        or evaluation.get("release_heldout_opened") is not False
        or evaluation.get("public_verdict_enabled") is not False
    ):
        raise SystemExit("v29 gate is not a consumed rejected transfer set")

    manifest_path = corpus_root / "manifest.json"
    fingerprints_path = corpus_root / "fingerprints.json"
    seal_path = corpus_root / "seal.json"
    manifest = load_json(manifest_path)
    fingerprint_report = load_json(fingerprints_path)
    seal = load_json(seal_path)
    cases = manifest.get("cases")
    fingerprints = fingerprint_report.get("case_sha256")
    if (
        seal.get("state") != "retained_controlled_corpus_complete"
        or seal.get("external_transfer_feature_scores_opened") is not False
        or seal.get("release_heldout_opened") is not False
        or seal.get("public_verdict_enabled") is not False
        or not isinstance(cases, list)
        or not isinstance(fingerprints, dict)
        or fingerprint_report.get("corpus_id") != manifest.get("corpus_id")
        or set(fingerprints)
        != {case.get("case_id") for case in cases}
        or any(case.get("split") != "held_out" for case in cases)
    ):
        raise SystemExit("retained independent corpus contract differs")
    commitment = {
        "root": str(corpus_root),
        "corpus_id": manifest.get("corpus_id"),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "fingerprints_path": str(fingerprints_path),
        "fingerprints_sha256": sha256_file(fingerprints_path),
        "seal_path": str(seal_path),
        "seal_sha256": sha256_file(seal_path),
        "case_count": len(cases),
        "analysis_max_seconds": manifest["analysis_max_seconds"],
        "evaluation_kind": "consumed_external_transfer_development",
    }
    if (
        evaluation.get("inventory", {}).get("case_count") != len(cases)
        or commitment["manifest_sha256"]
        != evaluation.get("inputs", {}).get("manifest", {}).get("sha256")
        or commitment["fingerprints_sha256"]
        != evaluation.get("inputs", {}).get("fingerprints", {}).get("sha256")
    ):
        raise SystemExit("consumed gate evaluation and corpus differ")

    partial_root = Path(f"{output}.partial")
    partial_root.mkdir(parents=True, exist_ok=True)
    runner_sha256 = sha256_file(runner)
    maximum_seconds = commitment["analysis_max_seconds"]

    def measure(case: dict) -> tuple[str, dict]:
        case_id = case["case_id"]
        partial = partial_root / f"{case_id}.json"
        if partial.is_file() and not partial.is_symlink():
            row = load_json(partial)
            if (
                row.get("case_id") == case_id
                and row.get("audio_sha256") == fingerprints[case_id]
                and row.get("runner_sha256") == runner_sha256
                and row.get("sampling_count") == args.sampling_count
            ):
                return case_id, row
            raise SystemExit(f"{partial}: resumable row differs")
        audio = BASE.resolve_beneath(corpus_root, case["relative_path"])
        probe = BASE.run_probe(
            runner,
            case=case,
            audio=audio,
            maximum_seconds=maximum_seconds,
            timeout_seconds=args.timeout_seconds,
            sampling_count=args.sampling_count,
        )
        if probe.get("audio_sha256") != fingerprints[case_id]:
            raise SystemExit(f"{case_id}: retained audio fingerprint differs")
        row = {
            "case_id": case_id,
            "class": case["class"],
            "expectation": case["expectation"],
            "source_group": case["source_group"],
            "partition_group": case.get(
                "partition_group",
                case["source_group"],
            ),
            "provenance_tier": case.get("provenance_tier"),
            "audio_sha256": fingerprints[case_id],
            "runner_sha256": runner_sha256,
            "sampling_count": args.sampling_count,
            **probe,
        }
        write_atomic(partial, row)
        return case_id, row

    ordered_cases = sorted(cases, key=lambda case: case["case_id"])
    rows_by_id: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.jobs,
    ) as executor:
        futures = {
            executor.submit(measure, case): case["case_id"]
            for case in ordered_cases
        }
        for index, future in enumerate(
            concurrent.futures.as_completed(futures),
            1,
        ):
            case_id, row = future.result()
            rows_by_id[case_id] = row
            print(
                f"[{index:04}/{len(ordered_cases):04}] {case_id}",
                flush=True,
            )

    rows = [rows_by_id[case["case_id"]] for case in ordered_cases]
    threshold = BASE.SAMPLING_THRESHOLDS[args.sampling_count]
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": "consumed_external_transfer_development_research",
        "public_verdict_enabled": False,
        "release_heldout_opened": False,
        "source_gate": {
            "path": str(evaluation_path),
            "sha256": sha256_file(evaluation_path),
            "disposition": evaluation["disposition"],
        },
        "input_commitment": commitment,
        "runner": {
            "path": str(runner),
            "sha256": runner_sha256,
        },
        "harness": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
            "base_path": str(BASE_PATH),
            "base_sha256": sha256_file(BASE_PATH),
        },
        "sampling": {
            "audio_window_count": args.sampling_count,
            "scale_factor_hypothesis_count": args.sampling_count,
            "published_threshold_exclusive": threshold,
        },
        "summary": BASE.summarize(rows, threshold),
        "case_count": len(rows),
        "cases": rows,
    }
    write_atomic(output, report)
    fixed = report["summary"]["fixed_reference"]
    strict = report["summary"]["strict_zero_observed_false_positive"]
    print(
        f"wrote {len(rows)} consumed cases; "
        f"fixed FP={fixed['false_positives']}/{fixed['negative_count']} "
        f"TP={fixed['true_positives']}/{fixed['positive_count']}; "
        f"strict TP={strict['true_positives']}/{strict['positive_count']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
