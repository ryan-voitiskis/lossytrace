#!/usr/bin/env python3
"""Commit exact observed equivalence of development and frozen v29 policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path


EQUIVALENT_KEYS = (
    "observed_metrics",
    "invariance",
    "case_results",
    "development_screen",
    "inventory",
    "transform_only_runtime",
)


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: expected JSON object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--development-policy", type=Path, required=True)
    parser.add_argument("--frozen-policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = {
        name: value.expanduser().resolve()
        for name, value in vars(args).items()
        if name != "output"
    }
    output = args.output.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit(f"refusing to replace output: {output}")
    development = load(paths["development"])
    frozen = load(paths["frozen"])
    mismatches = [
        key
        for key in EQUIVALENT_KEYS
        if development.get(key) != frozen.get(key)
    ]
    if (
        development.get("inventory", {}).get("case_count") != 3404
        or frozen.get("inventory", {}).get("case_count") != 3404
        or not development.get("development_screen", {}).get("passed")
        or not frozen.get("development_screen", {}).get("passed")
    ):
        raise SystemExit("observed replay inventory differs")
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "state": "observed_frozen_policy_replay_verified",
        "candidate_frozen": False,
        "external_transfer_feature_scores_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "case_count": 3404,
        "compared_keys": list(EQUIVALENT_KEYS),
        "mismatch_count": len(mismatches),
        "mismatch_keys": mismatches,
        "passed": not mismatches,
        "inputs": {
            name: {
                "path": str(path),
                "sha256": sha256(path),
            }
            for name, path in paths.items()
        },
        "warning": (
            "This proves implementation equivalence on already observed "
            "development evidence. It is not external validation."
        ),
    }
    if mismatches:
        raise SystemExit(f"frozen replay mismatches: {mismatches}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=output.parent,
        delete=False,
    ) as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
        temporary = Path(target.name)
    temporary.replace(output)
    print("verified exact frozen-policy replay over 3404 observed cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
