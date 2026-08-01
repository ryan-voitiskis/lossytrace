"""Verify a corpus cleanup target across an explicitly recorded relocation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_relocation_record(record_path: Path, corpus_root: Path) -> dict | None:
    try:
        with record_path.open(encoding="utf-8") as source:
            record = json.load(source)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        return None
    if record.get("operation") != "same-filesystem-directory-rename":
        return None
    source_path = record.get("source")
    destination_path = record.get("destination")
    if not isinstance(source_path, str) or not Path(source_path).is_absolute():
        return None
    if not isinstance(destination_path, str) or not Path(destination_path).is_absolute():
        return None
    if Path(destination_path).resolve() != corpus_root:
        return None
    verification = record.get("verification")
    if not isinstance(verification, dict):
        return None
    if verification.get("device_and_inode_before") != verification.get(
        "device_and_inode_after"
    ):
        return None
    retained = verification.get("retained_inventory")
    if not isinstance(retained, dict):
        return None
    inventory_name = retained.get("file")
    inventory_sha256 = retained.get("sha256_before_and_after")
    if (
        not isinstance(inventory_name, str)
        or Path(inventory_name).name != inventory_name
        or not isinstance(inventory_sha256, str)
    ):
        return None
    inventory_path = corpus_root / inventory_name
    if not inventory_path.is_file() or sha256_file(inventory_path) != inventory_sha256:
        return None
    return record


def cleanup_target_matches(root: Path, recorded_target: object) -> bool:
    """Accept an exact target or the same relative target after a verified rename."""

    root = root.resolve()
    if not isinstance(recorded_target, str):
        return False
    if recorded_target == str(root):
        return True
    recorded_path = Path(recorded_target)
    if not recorded_path.is_absolute():
        return False

    for corpus_root in (root, *root.parents):
        for record_path in sorted(corpus_root.glob("relocation-*.json"), reverse=True):
            record = valid_relocation_record(record_path, corpus_root)
            if record is None:
                continue
            try:
                relative = recorded_path.relative_to(Path(record["source"]))
            except ValueError:
                continue
            if (corpus_root / relative).resolve() == root:
                return True
    return False
