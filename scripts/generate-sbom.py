#!/usr/bin/env python3
"""Generate a compact CycloneDX 1.5 SBOM from locked Cargo metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def cargo_metadata(root: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["cargo", "metadata", "--locked", "--format-version", "1"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def purl(package: dict[str, Any]) -> str:
    return f"pkg:cargo/{package['name']}@{package['version']}"


def component(package: dict[str, Any], root_id: str) -> dict[str, Any]:
    value: dict[str, Any] = {
        "type": "application" if package["id"] == root_id else "library",
        "bom-ref": purl(package),
        "name": package["name"],
        "version": package["version"],
        "purl": purl(package),
    }
    if package.get("license"):
        value["licenses"] = [{"expression": package["license"]}]
    if package.get("repository"):
        value["externalReferences"] = [
            {"type": "vcs", "url": package["repository"]}
        ]
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timestamp")
    args = parser.parse_args()
    root = args.root.resolve()
    metadata = cargo_metadata(root)
    root_package = next(
        package for package in metadata["packages"] if package["name"] == "lossytrace"
    )
    resolved_ids = {node["id"] for node in metadata["resolve"]["nodes"]}
    packages = sorted(
        (package for package in metadata["packages"] if package["id"] in resolved_ids),
        key=lambda package: (package["name"], package["version"], package["id"]),
    )
    id_to_ref = {package["id"]: purl(package) for package in packages}
    dependencies = []
    for node in sorted(metadata["resolve"]["nodes"], key=lambda value: value["id"]):
        if node["id"] not in id_to_ref:
            continue
        dependencies.append(
            {
                "ref": id_to_ref[node["id"]],
                "dependsOn": sorted(
                    id_to_ref[dependency]
                    for dependency in node["dependencies"]
                    if dependency in id_to_ref
                ),
            }
        )
    lock_digest = hashlib.sha256((root / "Cargo.lock").read_bytes()).hexdigest()
    serial = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"https://github.com/ryan-voitiskis/lossytrace/{root_package['version']}/{lock_digest}",
    )
    timestamp = args.timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    report = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "component": component(root_package, root_package["id"]),
            "properties": [
                {"name": "lossytrace:cargo-lock-sha256", "value": lock_digest}
            ],
        },
        "components": [
            component(package, root_package["id"])
            for package in packages
            if package["id"] != root_package["id"]
        ],
        "dependencies": dependencies,
    }
    encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(f"wrote {len(packages)} components to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
