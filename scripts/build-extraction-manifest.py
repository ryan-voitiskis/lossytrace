#!/usr/bin/env python3
"""Record the checksum-backed Reklawdbox-to-LossyTrace extraction boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(source_root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(source_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def source_mappings(source_root: Path) -> list[tuple[str, str, str]]:
    mappings = [
        (".gitignore", ".gitignore", "adapted repository exclusions"),
        ("Cargo.lock", "Cargo.lock", "regenerated standalone dependency lock"),
        ("clippy.toml", "clippy.toml", "copied research lint policy"),
        (
            "docs/tmp/audio-integrity-lossy-source-detection-plan.md",
            "docs/research/original-reklawdbox-plan.md",
            "copied historical plan",
        ),
        (
            "stratum-dsp/Cargo.toml",
            "Cargo.toml",
            "adapted standalone package metadata and dependencies",
        ),
        (
            "stratum-dsp/src/features/compression_trace.rs",
            "src/compression_trace.rs",
            "copied measurement implementation; standalone pipeline test adapted",
        ),
        (
            "stratum-dsp/src/config.rs",
            "src/lib.rs",
            "standalone analysis configuration extracted",
        ),
        (
            "stratum-dsp/src/analysis/result.rs",
            "src/lib.rs",
            "standalone evidence result extracted",
        ),
        (
            "stratum-dsp/src/features/mod.rs",
            "src/lib.rs",
            "standalone module boundary extracted",
        ),
        (
            "stratum-dsp/src/lib.rs",
            "src/lib.rs",
            "shared-STFT integration replaced by standalone pipeline",
        ),
        (
            "stratum-dsp/src/analysis/confidence.rs",
            "src/lib.rs",
            "Reklawdbox compatibility plumbing removed",
        ),
    ]
    for source in sorted((source_root / "stratum-dsp/examples").glob("audio_integrity*.rs")):
        mappings.append(
            (
                source.relative_to(source_root).as_posix(),
                f"examples/{source.name}",
                "package and environment names adapted",
            )
        )
    for source in sorted(
        (source_root / "stratum-dsp/benchmarks/audio-integrity-v1").glob("*")
    ):
        if source.is_file():
            mappings.append(
                (
                    source.relative_to(source_root).as_posix(),
                    f"benchmarks/audio-integrity-v1/{source.name}",
                    "repository paths adapted" if source.suffix == ".md" else "copied",
                )
            )
    script_names = {
        source.name
        for pattern in ("*audio-integrity*.py", "audio_integrity*.py")
        for source in (source_root / "scripts").glob(pattern)
    }
    script_names.add("evaluate-vamp-lossy-detector.py")
    for name in sorted(script_names):
        mappings.append(
            (
                f"scripts/{name}",
                f"scripts/{name}",
                "package, benchmark, environment, and temporary paths adapted",
            )
        )
    for source in sorted(
        (source_root / "scripts/tests").glob("test_audio_integrity*.py")
    ):
        mappings.append(
            (
                source.relative_to(source_root).as_posix(),
                f"scripts/tests/{source.name}",
                "package and environment names adapted",
            )
        )
    return mappings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--destination-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--retained-inventory", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs/extraction-manifest.json",
    )
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    destination_root = args.destination_root.resolve()
    records = []
    for source_name, destination_name, relationship in source_mappings(source_root):
        source = source_root / source_name
        destination = destination_root / destination_name
        if not source.is_file():
            raise SystemExit(f"missing source file: {source_name}")
        if not destination.is_file():
            raise SystemExit(f"missing destination file: {destination_name}")
        source_digest = sha256(source)
        destination_digest = sha256(destination)
        records.append(
            {
                "origin": "reklawdbox_worktree",
                "source": source_name,
                "destination": destination_name,
                "source_sha256": source_digest,
                "destination_sha256": destination_digest,
                "exact_copy": source_digest == destination_digest,
                "relationship": relationship,
            }
        )

    archive_root = (
        destination_root
        / "research/exact-transform/archive-code/research-v4"
    )
    archive_records = []
    for destination in sorted(archive_root.rglob("*")):
        if (
            not destination.is_file()
            or "target" in destination.parts
            or "__pycache__" in destination.parts
            or destination.suffix == ".pyc"
        ):
            continue
        archive_records.append(
            {
                "origin": "exact_transform_archive_source_subset",
                "destination": destination.relative_to(destination_root).as_posix(),
                "destination_sha256": sha256(destination),
            }
        )

    status_lines = git(source_root, "status", "--short").splitlines()
    payload = {
        "schema_version": 1,
        "created_at": args.created_at,
        "source_repository": "reklawdbox",
        "source_commit": git(source_root, "rev-parse", "HEAD"),
        "source_worktree_dirty": bool(status_lines),
        "scope_note": "Only audio-integrity changes are mapped; unrelated Reklawdbox work is excluded.",
        "migrated_files": records,
        "archive_source_subset": {
            "archive_name": args.archive.name,
            "archive_sha256": sha256(args.archive),
            "verified_archive_file_count": 14_093,
            "files": archive_records,
        },
        "retained_corpora": {
            "inventory_name": args.retained_inventory.name,
            "inventory_sha256": sha256(args.retained_inventory),
            "case_count": 5_560,
            "verified_commitment_count": 40,
            "stored_outside_git": True,
        },
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    checksum_name = args.output.resolve().relative_to(destination_root).as_posix()
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        f"{hashlib.sha256(encoded).hexdigest()}  {checksum_name}\n",
        encoding="utf-8",
    )
    print(
        f"recorded {len(records)} Reklawdbox files and {len(archive_records)} archive-source files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
