#!/usr/bin/env python3
"""Bounded synthetic CLI qualification; never a detector-accuracy evaluation."""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import wave


MODEL_SHA256 = "ca86c67b4035485a9c1a3b3120b4a555cb7af87b4dd28837c46b297f82c48e7d"
FFMPEG_SHA256 = "c8173e9755795978bce8e104f8d7044fabe7d6d84044aba37d3648c6f4e4e1a8"
LOCK_SHA256 = "16f15838f36ff3b6218cf3584083e5da3457c645172012a0baf5b62397a4e8e2"
SOURCE_HASHES = {
    "src/audio.rs": "df471f1b8c7065c3df0e64901d1d87f853c8a210a9526862a6d572f010cedce3",
    "src/lib.rs": "bb1ffe8a083715095d41483ac4b83078f9bc5bc47966ec294ff75510fdadaa03",
    "src/main.rs": "95ba083cc5007b8478306959337e9c156923c326cee95acc387cd9c097a440a7",
    "src/model.rs": "61adbfc7d2732a5b72544bc466a741dd4c738de2e6256c00a07cf463b77df2af",
    "src/spectrogram.rs": "1ac54119523bd5dfb7cd57a037abdd572ebe1dfdeed802d7b9dfadcab153636f",
    "Cargo.lock": LOCK_SHA256,
    "Cargo.toml": "36c9169446d8fe94cc67928f8978f049e53532a9430f11e13931998b4197ac0e",
    "build.rs": "cc49c284cdf65065a2cf96049287554c12c052f23ed70ab6c4f11b54d1ce0af5",
    "model/model.onnx": MODEL_SHA256,
}
# id, sample rate, channel count, half-seconds, expected rejection substring
CASES = (
    ("wrapper_wav", 44100, 1, 6, None),
    ("wrapper_aiff", 44100, 1, 6, None),
    ("wrapper_flac", 44100, 1, 6, None),
    ("exact_window", 48000, 2, 29, None),
    ("offset_window", 48000, 2, 30, None),
    ("six_windows", 48000, 2, 40, None),
    ("rate_96k", 96000, 2, 6, None),
    ("rate_192k", 192000, 2, 6, None),
    ("minimum", 8000, 1, 4, None),
    ("too_short", 44100, 1, 2, "shorter than the 2-second minimum"),
    ("multichannel", 44100, 6, 6, "6 channels; only mono and stereo"),
    ("low_rate", 4000, 1, 6, "4000 Hz sample rate is outside"),
)
FAMILIES = {"mp3", "ffmpeg_aac", "vorbis", "opus", "wma", "mp2", "musepack"}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def pcm(frames: int, channels: int) -> bytes:
    state = 1
    samples = array.array("h")
    for _ in range(frames * channels):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        samples.append((state >> 18) - 8192)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


def write_wav(path: Path, rate: int, channels: int, half_seconds: int) -> bytes:
    data = pcm(rate * half_seconds // 2, channels)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(data)
    return data


def number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def normalize(stdout: str, path: Path) -> dict:
    value = json.loads(stdout)
    if not isinstance(value, dict) or set(value) != {
        "transcode_probability", "verdict", "encoder", "bitrate_kbps", "path"
    }:
        raise ValueError("unexpected CLI schema")
    if value.pop("path") != str(path):
        raise ValueError("output identity mismatch")
    score = value["transcode_probability"]
    if not number(score) or not 0 <= score <= 1:
        raise ValueError("non-finite or out-of-range score")
    if score < 0.5:
        if value["verdict"] != "clean" or value["encoder"] is not None or value["bitrate_kbps"] is not None:
            raise ValueError("invalid below-threshold fields")
    elif (value["verdict"] != "transcode" or value["encoder"] not in FAMILIES
          or not number(value["bitrate_kbps"]) or value["bitrate_kbps"] <= 0):
        raise ValueError("invalid above-threshold fields")
    return value


def invoke(command: list[str], timeout: float) -> dict:
    start = time.monotonic()
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout.decode("utf-8", errors="replace"),
            "stderr": result.stderr.decode("utf-8", errors="replace"),
            "timeout": False,
            "elapsed_seconds": time.monotonic() - start,
        }
    except subprocess.TimeoutExpired as error:
        return {
            "returncode": None,
            "stdout": (error.stdout or b"").decode("utf-8", errors="replace"),
            "stderr": (error.stderr or b"").decode("utf-8", errors="replace"),
            "timeout": True,
            "elapsed_seconds": time.monotonic() - start,
        }
    except OSError as error:
        return {"returncode": None, "stdout": "", "stderr": str(error),
                "timeout": False, "elapsed_seconds": time.monotonic() - start}


def aggregate(records: list[dict], integrity: bool, wrappers_verified: bool) -> dict:
    inventory_ok = [(r["round"], r["case_id"], r["expected_rejection"]) for r in records] == [
        (round_number, case[0], case[4]) for round_number in (1, 2) for case in CASES
    ]
    eligible = [r for r in records if r["expected_rejection"] is None]
    rejects = [r for r in records if r["expected_rejection"] is not None]
    repeat = all(
        len(pair := [r for r in records if r["case_id"] == case[0]]) == 2
        and all(r["passed"] for r in pair)
        and pair[0].get("normalized") == pair[1].get("normalized")
        for case in CASES
    )
    wrapper_match = wrappers_verified and all(
        len(rows := [r for r in records if r["round"] == round_number
                     and r["case_id"].startswith("wrapper_")]) == 3
        and all(r["passed"] for r in rows)
        and all(r.get("normalized") == rows[0].get("normalized") for r in rows)
        for round_number in (1, 2)
    )
    complete = inventory_ok and all(r["passed"] for r in records)
    return {
        "schema_version": 1,
        "purpose": "synthetic_software_qualification_not_detection_accuracy",
        "source_commit": "28b72da94e596f81a0155797c32af11c6e0bfa17",
        "model_sha256": MODEL_SHA256,
        "planned_slots": 24,
        "accounted_slots": len(records),
        "inventory_order_matches": inventory_ok,
        "eligible_slots": len(eligible),
        "eligible_completed": sum(r["passed"] for r in eligible),
        "ineligible_slots": len(rejects),
        "expected_rejections": sum(r["passed"] for r in rejects),
        "timeouts": sum(r.get("timeout", False) for r in records),
        "not_started": sum(r.get("not_started", False) for r in records),
        "exact_replay_match": repeat,
        "wrapper_pcm_verified": wrappers_verified,
        "wrapper_score_match": wrapper_match,
        "inputs_and_tools_unchanged": integrity,
        "passed": complete and repeat and wrapper_match and integrity,
        "public_verdict_enabled": False,
        "detector_accuracy": None,
    }


def run(args: argparse.Namespace) -> int:
    source, binary, ffmpeg, plan = (p.resolve(strict=True) for p in
                                     (args.source, args.binary, args.ffmpeg, args.plan))
    root = args.run_dir.absolute()
    if root.exists() or root.is_symlink():
        raise ValueError("run directory already exists; no automatic rerun")
    if shutil.disk_usage(root.parent).free < 15 * 1024**3:
        raise ValueError("15 GiB reserve unavailable")
    for relative, expected in SOURCE_HASHES.items():
        if digest(source / relative) != expected:
            raise ValueError(f"source/model mismatch: {relative}")
    if digest(binary) != args.binary_sha256 or digest(ffmpeg) != FFMPEG_SHA256:
        raise ValueError("binary/tool binding mismatch")
    root.mkdir(mode=0o700)
    start = time.monotonic()
    bindings = {
        "plan_sha256": digest(plan), "runner_sha256": digest(Path(__file__)),
        "binary_sha256": digest(binary), "ffmpeg_sha256": digest(ffmpeg),
        "source_hashes": SOURCE_HASHES, "python": sys.version,
        "platform": platform.platform(), "cases": CASES,
        "rounds": 2, "per_case_seconds": 60, "invocation_seconds": 1800,
    }
    save(root / "preflight.json", bindings)
    paths: dict[str, Path] = {}
    construction_logs = []
    wrapper_ok = False
    setup_error = None
    try:
        for case_id, rate, channels, half_seconds, _ in CASES:
            if case_id in ("wrapper_aiff", "wrapper_flac"):
                continue
            paths[case_id] = root / f"{case_id}.wav"
            write_wav(paths[case_id], rate, channels, half_seconds)
        expected_pcm = pcm(44100 * 3, 1)
        for case_id, suffix, codec in (("wrapper_aiff", "aiff", "pcm_s16be"),
                                       ("wrapper_flac", "flac", "flac")):
            path = root / f"{case_id}.{suffix}"
            command = [str(ffmpeg), "-nostdin", "-v", "error", "-n", "-i",
                       str(paths["wrapper_wav"]), "-map_metadata", "-1", "-c:a", codec, str(path)]
            result = invoke(command, 30)
            construction_logs.append(result)
            if result["returncode"] != 0:
                raise ValueError("wrapper construction failed")
            decoded = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-i", str(path),
                                      "-f", "s16le", "-c:a", "pcm_s16le", "pipe:1"],
                                     capture_output=True, timeout=30, check=True)
            if decoded.stdout != expected_pcm:
                raise ValueError("lossless wrapper changed PCM")
            paths[case_id] = path
        wrapper_ok = True
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        setup_error = str(error)
    input_hashes = {key: digest(path) for key, path in paths.items()}
    save(root / "inputs.json", {"sha256": input_hashes, "setup_error": setup_error,
                                "wrapper_pcm_verified": wrapper_ok,
                                "construction_logs": construction_logs})
    records = []
    for round_number in (1, 2):
        for case_id, _, _, _, rejection in CASES:
            record = {"round": round_number, "case_id": case_id,
                      "expected_rejection": rejection, "passed": False}
            remaining = 1800 - (time.monotonic() - start)
            if setup_error or remaining <= 0:
                record.update(not_started=True, error=setup_error or "invocation deadline")
            else:
                path = paths[case_id]
                result = invoke([str(binary), "--jobs", "1", "--threshold", "0.5",
                                 "-o", "jsonl", str(path)], min(60, remaining))
                record.update(result)
                if rejection is not None:
                    record["passed"] = (result["returncode"] not in (None, 0)
                                        and not result["stdout"].strip()
                                        and rejection in result["stderr"])
                elif result["returncode"] == 0 and not result["stderr"]:
                    try:
                        record["normalized"] = normalize(result["stdout"], path)
                        record["passed"] = True
                    except (ValueError, TypeError) as error:
                        record["error"] = str(error)
            records.append(record)
            save(root / "private-results.json", records)
            print(f"round={round_number} case={case_id} software_check={record['passed']}", flush=True)
    integrity = (all(digest(paths[key]) == expected for key, expected in input_hashes.items())
                 and all(digest(source / key) == value for key, value in SOURCE_HASHES.items())
                 and digest(binary) == bindings["binary_sha256"]
                 and digest(ffmpeg) == bindings["ffmpeg_sha256"]
                 and digest(plan) == bindings["plan_sha256"]
                 and digest(Path(__file__)) == bindings["runner_sha256"])
    result = aggregate(records, integrity, wrapper_ok)
    result.update(plan_sha256=bindings["plan_sha256"], runner_sha256=bindings["runner_sha256"],
                  binary_sha256=bindings["binary_sha256"])
    save(root / "aggregate.json", result)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "binary", "ffmpeg", "plan", "run-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--binary-sha256", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
