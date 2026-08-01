#!/usr/bin/env python3
"""Measure the frozen low-bandwidth support contract with safe resume."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import math
import platform
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np


SAMPLE_RATE = 48_000
FFT_SIZE = 2_048
HOP_SIZE = 1_024
LOW_EDGE_START_HZ = 4_000.0
LOW_EDGE_END_HZ = 10_000.0
EDGE_WINDOW_HZ = 300.0
MINIMUM_EDGE_DROP_DB = 6.0
EDGE_AGREEMENT_HZ = 300.0
CANDIDATE_ID = "conservative-two-grid-edge-v28-musdb-transfer-v1"
PROFILE = "conservative-two-grid-v28"
SAFE_CASE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(
        "audio_integrity_conservative_policy",
        path,
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import policy module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def validate_contract(
    *,
    manifest_path: Path,
    manifest: dict,
    fingerprints_path: Path,
    fingerprints: dict,
    precommit_path: Path,
    precommit: dict,
    policy_path: Path,
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
        or tools.get("low_bandwidth_probe_sha256")
        != sha256_file(Path(__file__).resolve())
        or tools.get("policy_module_sha256")
        != sha256_file(policy_path)
        or manifest != plan.get("manifest")
        or fingerprints.get("corpus_id") != manifest.get("corpus_id")
        or set(fingerprints.get("case_sha256", {}))
        != {case["case_id"] for case in manifest.get("cases", [])}
        or any(
            case.get("split") != "held_out"
            for case in manifest.get("cases", [])
        )
    ):
        raise SystemExit("frozen support-measurement contract differs")
    if len(manifest["cases"]) != 1_770:
        raise SystemExit("external-transfer case inventory differs")
    retained_plan = manifest_path.parent / "corpus-plan.json"
    retained_precommit = manifest_path.parent / "candidate-precommit.json"
    if (
        not retained_plan.is_file()
        or load_json(retained_plan) != plan
        or not retained_precommit.is_file()
        or load_json(retained_precommit) != precommit
        or sha256_file(fingerprints_path)
        != sha256_file(manifest_path.parent / "fingerprints.json")
    ):
        raise SystemExit("retained corpus commitments differ")


def declared_sample_rate(ffprobe: str, source: Path) -> int:
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=sample_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(completed.stdout.strip())


def decode_reference(ffmpeg: str, source: Path) -> np.ndarray:
    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-t",
            "30",
            "-map_metadata",
            "-1",
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "pcm_f32le",
            "-f",
            "f32le",
            "pipe:1",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    samples = np.frombuffer(completed.stdout, dtype="<f4").copy()
    if not np.all(np.isfinite(samples)):
        raise ValueError("decoded samples are non-finite")
    return samples


def band_power_share(
    power: np.ndarray,
    frequencies: np.ndarray,
    start_hz: float,
    end_hz: float,
) -> float:
    selected = (frequencies >= start_hz) & (frequencies < end_hz)
    return float(
        np.sum(power[:, selected])
        / max(float(np.sum(power)), 1e-30)
    )


def persistent_low_edge(
    power: np.ndarray,
    frequencies: np.ndarray,
) -> dict:
    bin_hz = SAMPLE_RATE / FFT_SIZE
    window_bins = max(3, round(EDGE_WINDOW_HZ / bin_hz))
    search_bins = np.flatnonzero(
        (frequencies >= LOW_EDGE_START_HZ)
        & (frequencies < LOW_EDGE_END_HZ)
    )
    search_bins = search_bins[
        (search_bins >= window_bins)
        & (search_bins + window_bins < power.shape[1])
    ]
    prefix = np.pad(
        np.cumsum(power, axis=1),
        ((0, 0), (1, 0)),
    )
    below = (
        prefix[:, search_bins]
        - prefix[:, search_bins - window_bins]
    ) / window_bins
    above = (
        prefix[:, search_bins + window_bins]
        - prefix[:, search_bins]
    ) / window_bins
    peak = np.max(power, axis=1, keepdims=True)
    floor = np.maximum(peak * 1e-12, 1e-30)
    drops = 10.0 * np.log10((below + floor) / (above + floor))
    drops[below < peak * 1e-6] = -math.inf
    best_indices = np.argmax(drops, axis=1)
    best_drops = drops[np.arange(drops.shape[0]), best_indices]
    valid = np.isfinite(best_drops) & (
        best_drops >= MINIMUM_EDGE_DROP_DB
    )
    if not np.any(valid):
        return {
            "low_edge_candidate_frame_count": 0,
            "low_edge_hz": None,
            "low_edge_drop_db": None,
            "low_edge_persistence": 0.0,
            "low_edge_spread_hz": None,
        }
    frame_frequencies = frequencies[search_bins[best_indices[valid]]]
    frame_drops = best_drops[valid]
    center_hz = float(np.median(frame_frequencies))
    agreeing = np.abs(frame_frequencies - center_hz) <= (
        EDGE_AGREEMENT_HZ
    )
    if not np.any(agreeing):
        agreeing[np.argmin(np.abs(frame_frequencies - center_hz))] = True
    agreeing_frequencies = frame_frequencies[agreeing]
    agreeing_drops = frame_drops[agreeing]
    return {
        "low_edge_candidate_frame_count": int(np.sum(valid)),
        "low_edge_hz": float(np.median(agreeing_frequencies)),
        "low_edge_drop_db": float(np.median(agreeing_drops)),
        "low_edge_persistence": float(
            np.sum(agreeing) / power.shape[0]
        ),
        "low_edge_spread_hz": float(
            np.quantile(agreeing_frequencies, 0.75)
            - np.quantile(agreeing_frequencies, 0.25)
        ),
    }


def measure(samples: np.ndarray, declared_sample_rate_hz: int) -> dict:
    frames = np.lib.stride_tricks.sliding_window_view(
        samples,
        FFT_SIZE,
    )[::HOP_SIZE]
    if frames.shape[0] < 32:
        return {
            "declared_sample_rate_hz": declared_sample_rate_hz,
            "supported": False,
            "support_reason": "too_few_frames",
        }
    window = np.hanning(FFT_SIZE).astype(np.float32)
    spectrum = np.fft.rfft(frames * window, axis=1)
    power = np.square(np.abs(spectrum))
    frame_power = np.sum(power, axis=1)
    active = frame_power >= max(
        float(np.max(frame_power)) * 1e-5,
        1e-20,
    )
    power = power[active]
    if power.shape[0] < 32:
        return {
            "declared_sample_rate_hz": declared_sample_rate_hz,
            "analyzed_frame_count": int(frames.shape[0]),
            "active_frame_count": int(power.shape[0]),
            "supported": False,
            "support_reason": "too_few_active_frames",
        }
    frequencies = np.fft.rfftfreq(FFT_SIZE, 1.0 / SAMPLE_RATE)
    result = {
        "declared_sample_rate_hz": declared_sample_rate_hz,
        "analysis_sample_rate_hz": SAMPLE_RATE,
        "analyzed_frame_count": int(frames.shape[0]),
        "active_frame_count": int(power.shape[0]),
        "power_share_0_8khz": band_power_share(
            power,
            frequencies,
            0.0,
            8_000.0,
        ),
        "power_share_10_20khz": band_power_share(
            power,
            frequencies,
            10_000.0,
            20_000.0,
        ),
        "power_share_12_20khz": band_power_share(
            power,
            frequencies,
            12_000.0,
            20_000.0,
        ),
        "supported": True,
    }
    result.update(persistent_low_edge(power, frequencies))
    return result


def run_case(
    *,
    case: dict,
    audio_root: Path,
    expected_sha256: str,
    precommit_sha256: str,
    tool_sha256: str,
    partial_root: Path,
    ffmpeg: str,
    ffprobe: str,
) -> tuple[str, bool]:
    case_id = case["case_id"]
    partial = partial_root / f"{case_id}.json"
    if partial.exists():
        existing = load_json(partial)
        if (
            existing.get("case_id") != case_id
            or existing.get("audio_sha256") != expected_sha256
            or existing.get("candidate_precommit_sha256")
            != precommit_sha256
            or existing.get("tool_sha256") != tool_sha256
        ):
            raise RuntimeError(f"{case_id}: support partial differs")
        return case_id, False
    source = resolve_beneath(audio_root, case["relative_path"])
    if sha256_file(source) != expected_sha256:
        raise RuntimeError(f"{case_id}: audio fingerprint differs")
    features = measure(
        decode_reference(ffmpeg, source),
        declared_sample_rate(ffprobe, source),
    )
    write_atomic(
        partial,
        {
            "case_id": case_id,
            "source_group": case["source_group"],
            "class": case["class"],
            "expectation": case["expectation"],
            "audio_sha256": expected_sha256,
            "candidate_precommit_sha256": precommit_sha256,
            "tool_sha256": tool_sha256,
            "features": features,
        },
    )
    return case_id, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--fingerprints", type=Path, required=True)
    parser.add_argument("--precommit", type=Path, required=True)
    parser.add_argument("--policy-module", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        raise SystemExit("--jobs must be in 1..=8")
    output = args.output.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit(f"refusing to replace report: {output}")
    manifest_path = args.manifest.expanduser().resolve()
    fingerprints_path = args.fingerprints.expanduser().resolve()
    precommit_path = args.precommit.expanduser().resolve()
    policy_path = args.policy_module.expanduser().resolve()
    audio_root = args.audio_root.expanduser().resolve()
    manifest = load_json(manifest_path)
    fingerprints = load_json(fingerprints_path)
    precommit = load_json(precommit_path)
    policy = load_module(policy_path)
    if policy.CANDIDATE_ID != CANDIDATE_ID:
        raise SystemExit("policy module candidate differs")
    validate_contract(
        manifest_path=manifest_path,
        manifest=manifest,
        fingerprints_path=fingerprints_path,
        fingerprints=fingerprints,
        precommit_path=precommit_path,
        precommit=precommit,
        policy_path=policy_path,
    )
    ffmpeg_path = Path(args.ffmpeg).expanduser().resolve()
    ffprobe_path = Path(args.ffprobe).expanduser().resolve()
    ffmpeg_version = subprocess.run(
        [str(ffmpeg_path), "-version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    ffprobe_version = subprocess.run(
        [str(ffprobe_path), "-version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    expected_packages = precommit.get("environment", {}).get(
        "analysis_python",
        {},
    ).get("packages", {})
    current_packages = {}
    if not isinstance(expected_packages, dict) or not expected_packages:
        raise SystemExit("frozen analysis package inventory is missing")
    for package in expected_packages:
        try:
            current_packages[package] = version(package)
        except PackageNotFoundError as error:
            raise SystemExit(
                f"frozen analysis package is missing: {package}"
            ) from error
    if (
        precommit.get("environment", {}).get("ffmpeg_version")
        != ffmpeg_version
        or precommit.get("environment", {}).get("ffprobe_version")
        != ffprobe_version
        or precommit.get("environment", {})
        .get("ffmpeg_executable", {})
        .get("sha256")
        != sha256_file(ffmpeg_path)
        or precommit.get("environment", {})
        .get("ffprobe_executable", {})
        .get("sha256")
        != sha256_file(ffprobe_path)
        or precommit.get("environment", {})
        .get("analysis_python", {})
        .get("path")
        != str(Path(sys.executable).resolve())
        or precommit.get("environment", {})
        .get("analysis_python", {})
        .get("version")
        != platform.python_version()
        or current_packages != expected_packages
    ):
        raise SystemExit("frozen analysis environment differs")
    precommit_sha256 = sha256_file(precommit_path)
    tool_sha256 = sha256_file(Path(__file__).resolve())
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
        "tool_sha256": tool_sha256,
        "policy_module_sha256": sha256_file(policy_path),
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
    }
    if opening_path.exists():
        existing = load_json(opening_path)
        for key, value in opening.items():
            if key != "opened_at" and existing.get(key) != value:
                raise SystemExit(
                    "external-transfer support opening record differs"
                )
        opening = existing
    else:
        write_atomic(opening_path, opening)
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
                expected_sha256=fingerprints["case_sha256"][
                    case["case_id"]
                ],
                precommit_sha256=precommit_sha256,
                tool_sha256=tool_sha256,
                partial_root=partial_root,
                ffmpeg=str(ffmpeg_path),
                ffprobe=str(ffprobe_path),
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
        if (
            row.get("audio_sha256")
            != fingerprints["case_sha256"][case["case_id"]]
            or row.get("candidate_precommit_sha256")
            != precommit_sha256
            or row.get("tool_sha256") != tool_sha256
        ):
            raise SystemExit(f"{case['case_id']}: final partial differs")
        rows.append(row)
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": "frozen_external_transfer_support_measurement",
        "candidate_id": CANDIDATE_ID,
        "candidate_frozen": True,
        "external_transfer_feature_scores_opened": True,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "method_id": "low-bandwidth-support-discovery-v0",
        "opening": opening,
        "candidate_precommit": {
            "path": str(precommit_path),
            "sha256": precommit_sha256,
        },
        "policy_module": {
            "path": str(policy_path),
            "sha256": sha256_file(policy_path),
        },
        "manifest": {
            "path": str(manifest_path),
            "sha256": sha256_file(manifest_path),
        },
        "fingerprints": {
            "path": str(fingerprints_path),
            "sha256": sha256_file(fingerprints_path),
        },
        "tool": {
            "path": str(Path(__file__).resolve()),
            "sha256": tool_sha256,
            "partial_root": str(partial_root),
            "jobs": args.jobs,
        },
        "ffmpeg_version": ffmpeg_version,
        "ffprobe_version": ffprobe_version,
        "case_count": len(rows),
        "cases": rows,
    }
    write_atomic(output, report)
    print(f"wrote {len(rows)} frozen support measurements to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
