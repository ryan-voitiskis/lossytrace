#!/usr/bin/env python3
"""Build or verify the exact-transform research tree integrity inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT_NAME = "exact-transform-research-artifact-integrity.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> list[dict]:
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == OUTPUT_NAME:
            continue
        relative = path.relative_to(root).as_posix()
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    return rows


def build(root: Path) -> int:
    output = root / OUTPUT_NAME
    if output.exists() or output.is_symlink():
        raise SystemExit(f"refusing to replace inventory: {output}")
    rows = inventory(root)
    document = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "artifact_id": "audio-integrity-exact-transform-research-v4",
        "purpose": (
            "Reproducibility evidence for v29 through v33 observed audio-"
            "integrity research, including rejected candidates and the "
            "explicit stop decision."
        ),
        "retention_policy": "retain_verified_private_archive",
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "feature_version": 0,
        "cache_schema_version": 21,
        "file_count": len(rows),
        "total_file_bytes": sum(row["bytes"] for row in rows),
        "files": rows,
        "important_outcomes": {
            "v29": "one-use independent gate rejected for support and recall",
            "v30": "AAC phase complement rejected for supported false positives",
            "v31": "MP3 frame diagnostic rejected for no incremental recall",
            "v32": (
                "zero supported-negative alerts but rejected for zero "
                "independent DEMAND MP3 and Apple AAC recall"
            ),
            "v33": (
                "zero supported-negative alerts and full DEMAND target recall "
                "but rejected for low MUSDB Apple recall and AAC invariance"
            ),
            "v32_v33_union": (
                "diagnostic recall and safety passed but eight SQAM invariance "
                "mismatches stopped the hand-built candidate sequence"
            ),
        },
        "cleanup_after_verified_archive": (
            "Completed per-case partial directories, logs, Python bytecode, "
            "and compiled research build outputs are reproducible and may be "
            "removed from the live tree only after the archive and an extracted "
            "copy both verify against this inventory."
        ),
    }
    output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "sha256": sha256(output),
                "file_count": len(rows),
                "total_file_bytes": document["total_file_bytes"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def verify(root: Path) -> int:
    output = root / OUTPUT_NAME
    document = json.loads(output.read_text(encoding="utf-8"))
    expected = {row["path"]: row for row in document["files"]}
    observed = {row["path"]: row for row in inventory(root)}
    failures = []
    for path in sorted(set(expected) | set(observed)):
        if path not in expected:
            failures.append(f"unexpected file: {path}")
        elif path not in observed:
            failures.append(f"missing file: {path}")
        elif expected[path] != observed[path]:
            failures.append(f"integrity mismatch: {path}")
    result = {
        "root": str(root),
        "inventory": str(output),
        "inventory_sha256": sha256(output),
        "expected_file_count": len(expected),
        "observed_file_count": len(observed),
        "failure_count": len(failures),
        "failures": failures[:20],
        "passed": not failures,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--root", type=Path, default=ROOT)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"research root missing: {root}")
    if args.command == "build":
        return build(root)
    return verify(root)


if __name__ == "__main__":
    raise SystemExit(main())
