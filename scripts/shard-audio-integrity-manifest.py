#!/usr/bin/env python3
"""Split a private benchmark manifest into deterministic source-group shards."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path


def load_object(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise ValueError(f"refusing to replace existing output: {path}")
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def assignment(source_group: str, shard_count: int) -> int:
    digest = hashlib.sha256(source_group.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def shard_manifest(manifest: dict, shard_count: int) -> list[dict]:
    if not 1 <= shard_count <= 256:
        raise ValueError("shard_count must be in 1..=256")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest cases must be a non-empty array")
    buckets: list[list[dict]] = [[] for _ in range(shard_count)]
    group_shards: dict[str, int] = {}
    seen_case_ids: set[str] = set()
    for case in cases:
        case_id = case.get("case_id")
        source_group = case.get("source_group")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("every case requires a case_id")
        if case_id in seen_case_ids:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen_case_ids.add(case_id)
        if not isinstance(source_group, str) or not source_group:
            raise ValueError(f"{case_id}: source_group is required")
        shard_index = assignment(source_group, shard_count)
        prior = group_shards.setdefault(source_group, shard_index)
        if prior != shard_index:
            raise AssertionError("source-group assignment changed")
        buckets[shard_index].append(case)
    if any(not bucket for bucket in buckets):
        raise ValueError("shard_count produced an empty shard; use fewer shards")

    output = []
    base_corpus_id = manifest.get("corpus_id")
    for shard_index, bucket in enumerate(buckets):
        value = {key: item for key, item in manifest.items() if key != "cases"}
        value["corpus_id"] = (
            f"{base_corpus_id}-shard-{shard_index + 1:03d}-of-{shard_count:03d}"
        )
        value["shard"] = {
            "schema_version": 1,
            "assignment": "sha256(source_group)-first-u64-big-endian-modulo",
            "index": shard_index,
            "number": shard_index + 1,
            "count": shard_count,
            "case_count": len(bucket),
            "source_group_count": len(
                {case["source_group"] for case in bucket}
            ),
        }
        value["cases"] = sorted(bucket, key=lambda case: case["case_id"])
        output.append(value)
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--shard-count", type=int, default=32)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_directory = args.output_directory.expanduser().resolve()
    try:
        if output_directory.exists():
            raise ValueError(
                f"refusing to use existing output directory: {output_directory}"
            )
        output_directory.mkdir(parents=True)
        shards = shard_manifest(
            load_object(args.manifest.expanduser().resolve()), args.shard_count
        )
        for index, shard in enumerate(shards, 1):
            write_new(output_directory / f"manifest-{index:03d}.json", shard)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(
        f"wrote {len(shards)} source-group-isolated shards containing "
        f"{sum(len(shard['cases']) for shard in shards)} cases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
