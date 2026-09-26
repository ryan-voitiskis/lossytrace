#!/usr/bin/env python3
"""Verify and exercise an unpacked native release artifact on generated PCM."""
from __future__ import annotations

import argparse
import array
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import struct
import sys
import tarfile
import tempfile
import wave

# One second of generated mono 44.1 kHz PCM16 silence, encoded losslessly with
# libFLAC 1.5.0: --no-padding --no-seektable --stdout -. No recorded audio.
SILENT_FLAC = "ZkxhQwAAACIQABAAAAAAAAAACsRA8AAArEQAAAAAAAAAAAAAAAAAAAAAhAAAKCAAAAByZWZlcmVuY2UgbGliRkxBQyAxLjUuMCAyMDI1MDIxMQAAAAD/+MkIAJUAAAAhvf/4yQgBkgAAAE3F//jJCAKbAAAA+U3/+MkIA5wAAACVNf/4yQgEiQAAABBY//jJCAWOAAAAfCD/+MkIBocAAADIqP/4yQgHgAAAAKTQ//jJCAitAAAAQnf/+MkICaoAAAAuD//4eQgKDEPUAAAAYxg="


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def inspect_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    names = [m.name for m in members]
    if len(set(names)) != len(names) or sum(m.size for m in members) > 1024 ** 3:
        raise ValueError("duplicate members or oversized bundle")
    for member in members:
        path = Path(member.name)
        if not member.name or str(path) == "." or not member.isfile() or path.is_absolute() or ".." in path.parts:
            raise ValueError("unsafe bundle member")
    for required in ("lossytrace", "build-info.json", "README.md", "inspection-guide.md", "release-notes.md",
                     "LICENSE-MIT", "LICENSE-APACHE", "THIRD_PARTY_NOTICES.md", "dependency-inventory.json", "licenses/MPL-2.0.txt",
                     "licenses/rust/COPYRIGHT-library.html"):
        if required not in names:
            raise ValueError("required bundle member absent: " + required)
    return members


def smoke(bundle: Path, expected_tag: str, expected_target: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="lossytrace-package-smoke-") as temporary:
        root = Path(temporary)
        with tarfile.open(bundle, "r:gz") as archive:
            members = inspect_members(archive)
            archive.extractall(root, members=members, filter="data")
        info = json.loads((root / "build-info.json").read_text())
        if info["tag"] != expected_tag or info["target"] != expected_target or info["version"] != expected_tag.removeprefix("v"):
            raise ValueError("artifact identity mismatch")
        binary = root / "lossytrace"
        if digest(binary) != info["binary_sha256"]:
            raise ValueError("binary checksum mismatch")
        inventory = json.loads((root / "dependency-inventory.json").read_text())
        covered = [entry for entry in inventory if entry["bundled_covered_source"]]
        for entry in covered:
            path = (root / entry["bundled_covered_source"]).resolve()
            path.relative_to(root.resolve())
            if digest(path) != entry["crate_sha256"]:
                raise ValueError("covered source checksum mismatch")
        for entry in inventory:
            if not entry["license"] or not entry["source_url"]:
                raise ValueError("dependency license/source absent")
            for notice in entry["notice_files"]:
                path = (root / notice).resolve()
                path.relative_to(root.resolve())
                if not path.is_file():
                    raise ValueError("dependency notice missing")
        if len(inventory) != info["dependency_count"] or len(covered) != info["covered_source_count"]:
            raise ValueError("dependency accounting differs")

        def cli(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run([str(binary), *args], capture_output=True, check=False, timeout=60)

        version = cli("--version")
        require(version.returncode == 0 and version.stdout.decode().strip() == f"lossytrace {info['version']}", "native version check failed")
        help_result = cli("--help")
        require(help_result.returncode == 0 and all(word in help_result.stdout for word in (b"analyze", b"explain")), "native help check failed")
        explained = cli("explain")
        require(explained.returncode == 0 and not explained.stderr, "native explain failed")
        require(explained.stdout == (root / "inspection-guide.md").read_bytes(), "embedded guide differs from bundled guide")
        samples = array.array("h")
        state = 1
        for _ in range(44100):
            state = (1664525 * state + 1013904223) & 0xffffffff
            samples.append((state >> 18) - 8192)
        if sys.byteorder != "little":
            samples.byteswap()
        fixture = root / "numeric.wav"
        with wave.open(str(fixture), "wb") as output:
            output.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
            output.writeframes(samples.tobytes())
        before = digest(fixture)
        outputs = [cli("analyze", str(fixture), "--max-seconds", "0.25") for _ in range(2)]
        require(all(out.returncode == 0 and not out.stderr for out in outputs), "native analysis failed")
        reports = [json.loads(out.stdout) for out in outputs]
        require(reports[0] == reports[1], "analysis replay differs")
        report = reports[0]
        require(set(report) == {"schema_version", "state", "public_verdict_enabled", "input_sha256",
                               "analyzed_sample_count", "analyzed_duration_seconds", "truncated_by_limit",
                               "source_facts", "compression_trace"}, "analysis schema fields differ")
        require(report["schema_version"] == 1 and report["state"] == "experimental_measurements_only", "analysis state differs")
        require(report["public_verdict_enabled"] is False and report["compression_trace"]["feature_version"] == 0, "verdict-free feature contract differs")
        require(report["input_sha256"] == before == digest(fixture), "input fingerprint differs")
        require(report["analyzed_sample_count"] == 11025 and report["truncated_by_limit"] is True, "duration limit differs")
        require(report["source_facts"]["sample_rate_hz"] == 44100 and report["source_facts"]["channel_count"] == 1, "source facts differ")
        # Same numeric PCM in AIFF, using a native-rate 80-bit extended header.
        raw = samples.tobytes()
        big_endian = b"".join(raw[i:i + 2][::-1] for i in range(0, len(raw), 2))
        comm = struct.pack(">hIh", 1, 44100, 16) + bytes.fromhex("400eac44000000000000")
        chunks = b"COMM" + struct.pack(">I", len(comm)) + comm
        sound = bytes(8) + big_endian
        chunks += b"SSND" + struct.pack(">I", len(sound)) + sound
        aiff = root / "numeric.aiff"
        aiff.write_bytes(b"FORM" + struct.pack(">I", len(chunks) + 4) + b"AIFF" + chunks)
        aiff_hash = digest(aiff)
        aiff_result = cli("analyze", str(aiff), "--max-seconds", "0.25")
        require(aiff_result.returncode == 0 and not aiff_result.stderr, "AIFF decode failed")
        aiff_report = json.loads(aiff_result.stdout)
        require(aiff_report["compression_trace"] == report["compression_trace"], "AIFF and WAV measurements differ")
        require(aiff_report["input_sha256"] == aiff_hash == digest(aiff), "AIFF input changed")
        flac = root / "silence.flac"
        flac.write_bytes(base64.b64decode(SILENT_FLAC))
        silence = root / "silence.wav"
        with wave.open(str(silence), "wb") as output:
            output.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
            output.writeframes(bytes(88200))
        silent_reports = []
        for path in (flac, silence):
            before_silence = digest(path)
            value = cli("analyze", str(path), "--max-seconds", "0.25")
            require(value.returncode == 0 and not value.stderr, "silence decode failed")
            parsed = json.loads(value.stdout)
            require(parsed["input_sha256"] == before_silence == digest(path), "silence input changed")
            require(parsed["analyzed_sample_count"] == 11025, "silence frame count differs")
            silent_reports.append(parsed)
        require(silent_reports[0]["compression_trace"] == silent_reports[1]["compression_trace"], "FLAC and WAV silence measurements differ")
        for args in (("analyze", str(root / "absent.wav")), ("analyze", str(fixture), "--max-seconds", "NaN"),
                     ("explain", str(fixture))):
            failed = cli(*args)
            require(failed.returncode != 0 and not failed.stdout, "invalid invocation did not fail safely")
        return {"schema_version": 1, "tag": expected_tag, "target": expected_target,
                "source_commit": info["source_commit"], "archive_sha256": digest(bundle),
                "binary_sha256": info["binary_sha256"], "native_execution_passed": True,
                "exact_generated_pcm_replay": True, "input_unchanged": True, "verdict_free_contract": True,
                "lossless_wrapper_checks": ["numeric_wav_aiff", "silence_wav_flac"],
                "failure_cases_passed": 3, "dependency_count": len(inventory), "covered_source_count": len(covered),
                "detector_accuracy_evaluated": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = smoke(args.bundle, args.tag, args.target)
    with args.output.open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
