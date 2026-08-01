#!/usr/bin/env python3
"""Fetch and verify approved public audio source packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = (
    ROOT
    / "benchmarks/audio-integrity-v1/public-tier-a-sources.json"
)
MINIMUM_FREE_RESERVE_BYTES = 15 * 1024**3


def now() -> str:
    return datetime.now(UTC).isoformat()


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


def provider_digest(path: Path, provider_checksum: str) -> str:
    try:
        algorithm, expected = provider_checksum.split(":", 1)
        digest = hashlib.new(algorithm)
    except (ValueError, TypeError) as error:
        raise SystemExit(
            f"unsupported provider checksum: {provider_checksum!r}"
        ) from error
    if len(expected) != digest.digest_size * 2:
        raise SystemExit(f"invalid provider checksum: {provider_checksum!r}")
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"{algorithm}:{digest.hexdigest()}"


def curl_resume_command(
    curl: str,
    partial: Path,
    url: str,
) -> list[str]:
    return [
        curl,
        "--fail",
        "--location",
        "--retry",
        "10",
        "--retry-delay",
        "2",
        "--retry-all-errors",
        "--continue-at",
        "-",
        "--output",
        str(partial),
        url,
    ]


def validate_registry(registry: dict) -> list[str]:
    failures = []
    if registry.get("schema_version") != 1:
        failures.append("schema_version must be 1")
    sources = registry.get("sources")
    if not isinstance(sources, list) or not sources:
        return failures + ["sources must be a non-empty array"]
    source_ids = []
    filenames = []
    for index, source in enumerate(sources):
        prefix = f"sources[{index}]"
        if not isinstance(source, dict):
            failures.append(f"{prefix} must be an object")
            continue
        for field in (
            "source_id",
            "title",
            "version",
            "official_page_url",
            "provider_metadata_url",
            "license",
            "release_role",
            "ground_truth_basis",
            "partition_basis",
            "limitations",
        ):
            if not isinstance(source.get(field), str) or not source[field]:
                failures.append(f"{prefix}.{field} is required")
        source_ids.append(source.get("source_id"))
        artifact = source.get("artifact")
        if not isinstance(artifact, dict):
            failures.append(f"{prefix}.artifact must be an object")
            continue
        filename = artifact.get("filename")
        if (
            not isinstance(filename, str)
            or not filename
            or Path(filename).name != filename
        ):
            failures.append(f"{prefix}.artifact.filename must be a basename")
        filenames.append(filename)
        if (
            not isinstance(artifact.get("url"), str)
            or not artifact["url"].startswith("https://")
        ):
            failures.append(f"{prefix}.artifact.url must use HTTPS")
        if (
            not isinstance(artifact.get("bytes"), int)
            or artifact["bytes"] <= 0
        ):
            failures.append(f"{prefix}.artifact.bytes must be positive")
        checksum = artifact.get("provider_checksum")
        if not isinstance(checksum, str) or ":" not in checksum:
            failures.append(
                f"{prefix}.artifact.provider_checksum is required"
            )
    if len(source_ids) != len(set(source_ids)):
        failures.append("source IDs are not unique")
    if len(filenames) != len(set(filenames)):
        failures.append("artifact filenames are not unique")
    return failures


def write_private_atomic(path: Path, value: dict) -> None:
    if path.exists():
        raise SystemExit(f"refusing to replace fetch record: {path}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def command(args: argparse.Namespace) -> int:
    registry_path = args.registry.expanduser().resolve()
    registry = load_json(registry_path)
    failures = validate_registry(registry)
    if failures:
        raise SystemExit(
            "public source registry is invalid:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )
    by_id = {source["source_id"]: source for source in registry["sources"]}
    requested = args.source or sorted(by_id)
    unknown = sorted(set(requested) - set(by_id))
    if unknown:
        raise SystemExit(f"unknown source IDs: {', '.join(unknown)}")
    if len(requested) != len(set(requested)):
        raise SystemExit("source IDs must not be repeated")

    destination = args.destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.chmod(0o700)
    record_path = args.record.expanduser().resolve()
    if record_path.exists():
        raise SystemExit(f"fetch record already exists: {record_path}")
    if args.minimum_free_reserve_bytes < 0:
        raise SystemExit("--minimum-free-reserve-bytes must be non-negative")

    remaining_bytes = 0
    for source_id in requested:
        artifact = by_id[source_id]["artifact"]
        final = destination / artifact["filename"]
        partial = destination / f".{artifact['filename']}.partial"
        if record_path in {final, partial}:
            raise SystemExit("fetch record must not replace an artifact")
        if final.is_symlink() or partial.is_symlink():
            raise SystemExit("artifact paths must not be symbolic links")
        if final.exists() and not final.is_file():
            raise SystemExit(f"artifact path is not a regular file: {final}")
        if partial.exists() and not partial.is_file():
            raise SystemExit(
                f"partial artifact path is not a regular file: {partial}"
            )
        if final.exists() and partial.exists():
            raise SystemExit(
                f"both final and partial artifacts exist: {final.name}"
            )
        if final.exists():
            continue
        partial_bytes = partial.stat().st_size if partial.exists() else 0
        if partial_bytes > artifact["bytes"]:
            raise SystemExit(f"partial download is oversized: {partial}")
        remaining_bytes += artifact["bytes"] - partial_bytes
    free_bytes = shutil.disk_usage(destination).free
    if free_bytes - remaining_bytes < args.minimum_free_reserve_bytes:
        raise SystemExit(
            f"fetch requires {remaining_bytes} more bytes but would leave less "
            f"than the {args.minimum_free_reserve_bytes}-byte free-space reserve"
        )

    fetched = []
    for source_id in requested:
        source = by_id[source_id]
        artifact = source["artifact"]
        final = destination / artifact["filename"]
        partial = destination / f".{artifact['filename']}.partial"
        reused = final.exists()
        if not reused:
            subprocess.run(
                curl_resume_command(
                    args.curl,
                    partial,
                    artifact["url"],
                ),
                check=True,
            )
            if partial.stat().st_size != artifact["bytes"]:
                raise SystemExit(
                    f"downloaded byte count differs for {artifact['filename']}"
                )
            actual_provider_digest = provider_digest(
                partial,
                artifact["provider_checksum"],
            )
            if actual_provider_digest != artifact["provider_checksum"]:
                raise SystemExit(
                    f"provider checksum differs for {artifact['filename']}"
                )
            partial.replace(final)
            final.chmod(0o600)
        if final.stat().st_size != artifact["bytes"]:
            raise SystemExit(
                f"retained byte count differs for {artifact['filename']}"
            )
        actual_provider_digest = provider_digest(
            final,
            artifact["provider_checksum"],
        )
        if actual_provider_digest != artifact["provider_checksum"]:
            raise SystemExit(
                f"retained provider checksum differs for {artifact['filename']}"
            )
        fetched.append(
            {
                "source_id": source_id,
                "title": source["title"],
                "version": source["version"],
                "license": source["license"],
                "release_role": source["release_role"],
                "official_page_url": source["official_page_url"],
                "provider_metadata_url": source["provider_metadata_url"],
                "ground_truth_basis": source["ground_truth_basis"],
                "partition_basis": source["partition_basis"],
                "limitations": source["limitations"],
                "artifact_path": str(final),
                "bytes": final.stat().st_size,
                "provider_checksum": actual_provider_digest,
                "sha256": sha256_file(final),
                "reused_verified_artifact": reused,
            }
        )
        print(
            f"verified {source_id}: {final.stat().st_size} bytes at {final}"
        )
    record = {
        "schema_version": 1,
        "fetch_id": args.fetch_id,
        "created_at": now(),
        "registry_id": registry["registry_id"],
        "registry_sha256": sha256_file(registry_path),
        "destination": str(destination),
        "free_space_reserve_bytes": args.minimum_free_reserve_bytes,
        "sources": fetched,
    }
    write_private_atomic(record_path, record)
    print(f"wrote verified public-source fetch record to {record_path}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    result.add_argument("--source", action="append")
    result.add_argument("--destination", type=Path, required=True)
    result.add_argument("--fetch-id", required=True)
    result.add_argument("--record", type=Path, required=True)
    result.add_argument("--curl", default="curl")
    result.add_argument(
        "--minimum-free-reserve-bytes",
        type=int,
        default=MINIMUM_FREE_RESERVE_BYTES,
    )
    return result


if __name__ == "__main__":
    raise SystemExit(command(parser().parse_args()))
