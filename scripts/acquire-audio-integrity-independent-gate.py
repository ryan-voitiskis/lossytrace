#!/usr/bin/env python3
"""Plan, acquire, and verify a compact independent PCM gate corpus.

This tool reads only provider metadata and PCM containers. It never runs the
audio-integrity feature runner or opens candidate scores.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import struct
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
import zlib
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath


SCHEMA_VERSION = 1
RUN_ID = "audio-integrity-independent-pcm-gate-20260731-001"
SELECTION_SEED = "reklawdbox-independent-pcm-gate-v1"
MAESTRO_METADATA_URL = (
    "https://storage.googleapis.com/magentadata/datasets/maestro/"
    "v3.0.0/maestro-v3.0.0.json"
)
MAESTRO_ARCHIVE_URL = (
    "https://storage.googleapis.com/magentadata/datasets/maestro/"
    "v3.0.0/maestro-v3.0.0.zip"
)
MAESTRO_ARCHIVE_BYTES = 108_445_099_632
MAESTRO_ARCHIVE_SHA256_CLAIM = (
    "6680fea5be2339ea15091a249fbd70e49551246ddbd5ca50f1b2352c08c95291"
)
MAESTRO_EXPECTED_YEARS = (
    2004,
    2006,
    2008,
    2009,
    2011,
    2013,
    2014,
    2017,
    2018,
)
MAESTRO_SELECTIONS_PER_YEAR = 2
MAESTRO_MINIMUM_DURATION_SECONDS = 120.0
MAESTRO_MAXIMUM_DURATION_SECONDS = 300.0
DEMAND_API_URL = "https://zenodo.org/api/records/1227121"
DEMAND_RECORD_ID = 1_227_121
DEMAND_EXPECTED_ENVIRONMENTS = 18
DEFAULT_EXCERPT_SECONDS = 30.0
DEFAULT_BLOCK_BYTES = 4 * 1024 * 1024
DEFAULT_CACHE_BLOCKS = 8
DEFAULT_MINIMUM_FREE_BYTES = 15 * 1024 * 1024 * 1024
READ_BYTES = 1024 * 1024
CONTENT_RANGE = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(READ_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return sha256_bytes(encoded)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: top-level JSON must be an object")
    return value


def replace_json(path: Path, value: dict) -> None:
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


def write_new_json(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace output: {path}")
    replace_json(path, value)


def fetch_bytes(url: str) -> tuple[bytes, object, str]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept-Encoding": "identity",
            "User-Agent": "lossytrace-research/0",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read(), response.headers, response.geturl()


class HTTPRangeReader(io.RawIOBase):
    """Seekable read-only HTTP object backed by bounded Range requests."""

    def __init__(
        self,
        url: str,
        *,
        expected_size: int | None,
        block_bytes: int,
        cache_blocks: int,
        retries: int = 4,
    ) -> None:
        super().__init__()
        self.requested_url = url
        self.block_bytes = block_bytes
        self.cache_blocks = cache_blocks
        self.retries = retries
        self.position = 0
        self.cache: OrderedDict[int, bytes] = OrderedDict()
        self.request_count = 0
        self.response_bytes = 0
        probe, headers, final_url = self._request_range(0, 0)
        match = CONTENT_RANGE.match(headers.get("Content-Range", ""))
        if len(probe) != 1 or match is None:
            raise OSError("server did not honor a one-byte Range probe")
        self.length = int(match.group(3))
        if expected_size is not None and self.length != expected_size:
            raise OSError(
                f"remote size {self.length} differs from {expected_size}"
            )
        self.final_url = final_url
        self.etag = headers.get("ETag")
        self.last_modified = headers.get("Last-Modified")

    def _request_range(
        self,
        start: int,
        end: int,
    ) -> tuple[bytes, object, str]:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            request = urllib.request.Request(
                self.requested_url,
                headers={
                    "Range": f"bytes={start}-{end}",
                    "Accept-Encoding": "identity",
                    "User-Agent": (
                        "lossytrace-research/0"
                    ),
                },
            )
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=120,
                ) as response:
                    if response.status != 206:
                        raise OSError(
                            f"expected HTTP 206, got {response.status}"
                        )
                    payload = response.read()
                    match = CONTENT_RANGE.match(
                        response.headers.get("Content-Range", "")
                    )
                    if (
                        match is None
                        or int(match.group(1)) != start
                        or int(match.group(2)) != end
                        or len(payload) != end - start + 1
                    ):
                        raise OSError("unexpected Range response")
                    self.request_count += 1
                    self.response_bytes += len(payload)
                    return payload, response.headers, response.geturl()
            except (
                OSError,
                TimeoutError,
                urllib.error.URLError,
            ) as error:
                last_error = error
                if attempt + 1 < self.retries:
                    time.sleep(0.5 * (2**attempt))
        assert last_error is not None
        raise OSError(
            f"Range request {start}-{end} failed: {last_error}"
        ) from last_error

    def _block(self, index: int) -> bytes:
        cached = self.cache.pop(index, None)
        if cached is not None:
            self.cache[index] = cached
            return cached
        start = index * self.block_bytes
        if start >= self.length:
            return b""
        end = min(start + self.block_bytes, self.length) - 1
        payload, _, _ = self._request_range(start, end)
        self.cache[index] = payload
        while len(self.cache) > self.cache_blocks:
            self.cache.popitem(last=False)
        return payload

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        if whence == os.SEEK_SET:
            target = offset
        elif whence == os.SEEK_CUR:
            target = self.position + offset
        elif whence == os.SEEK_END:
            target = self.length + offset
        else:
            raise ValueError(f"unsupported whence: {whence}")
        if target < 0:
            raise ValueError("negative seek position")
        self.position = min(target, self.length)
        return self.position

    def read(self, size: int = -1) -> bytes:
        if self.position >= self.length:
            return b""
        if size is None or size < 0:
            size = self.length - self.position
        size = min(size, self.length - self.position)
        output = bytearray()
        while len(output) < size:
            index = self.position // self.block_bytes
            offset = self.position % self.block_bytes
            block = self._block(index)
            take = min(size - len(output), len(block) - offset)
            if take <= 0:
                break
            output.extend(block[offset : offset + take])
            self.position += take
        return bytes(output)

    def readinto(self, buffer) -> int:
        payload = self.read(len(buffer))
        buffer[: len(payload)] = payload
        return len(payload)

    def stats(self) -> dict:
        return {
            "request_count": self.request_count,
            "response_bytes": self.response_bytes,
            "block_bytes": self.block_bytes,
            "cache_blocks": self.cache_blocks,
        }


def open_remote(
    url: str,
    expected_size: int | None,
    args: argparse.Namespace,
) -> HTTPRangeReader:
    return HTTPRangeReader(
        url,
        expected_size=expected_size,
        block_bytes=args.block_bytes,
        cache_blocks=args.cache_blocks,
    )


def safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(
        name
        and not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in name
    )


def zip_record(info: zipfile.ZipInfo) -> dict:
    if not safe_member_name(info.filename):
        raise SystemExit(f"unsafe ZIP member path: {info.filename!r}")
    return {
        "member_name": info.filename,
        "zip_crc32": f"{info.CRC:08x}",
        "compressed_bytes": info.compress_size,
        "uncompressed_bytes": info.file_size,
        "compression_method": info.compress_type,
        "header_offset": info.header_offset,
    }


def maestro_rows(metadata: dict) -> list[dict]:
    required = {
        "canonical_composer",
        "canonical_title",
        "split",
        "year",
        "audio_filename",
        "duration",
    }
    if not required <= set(metadata):
        raise SystemExit("MAESTRO metadata columns differ")
    keys = set(metadata["audio_filename"])
    if any(set(metadata[column]) != keys for column in required):
        raise SystemExit("MAESTRO metadata column keys differ")
    return [
        {column: metadata[column][key] for column in required}
        for key in sorted(keys, key=int)
    ]


def select_maestro(rows: list[dict]) -> list[dict]:
    selected = []
    for year in MAESTRO_EXPECTED_YEARS:
        eligible = [
            row
            for row in rows
            if int(row["year"]) == year
            and MAESTRO_MINIMUM_DURATION_SECONDS
            <= float(row["duration"])
            <= MAESTRO_MAXIMUM_DURATION_SECONDS
            and "mp3" not in str(row["audio_filename"]).lower()
        ]
        ordered = sorted(
            eligible,
            key=lambda row: hashlib.sha256(
                (
                    SELECTION_SEED
                    + "\0"
                    + str(row["audio_filename"])
                ).encode()
            ).hexdigest(),
        )
        if len(ordered) < MAESTRO_SELECTIONS_PER_YEAR:
            raise SystemExit(f"insufficient MAESTRO rows for {year}")
        selected.extend(ordered[:MAESTRO_SELECTIONS_PER_YEAR])
    return selected


def command_plan(args: argparse.Namespace) -> int:
    metadata_bytes, metadata_headers, metadata_final_url = fetch_bytes(
        MAESTRO_METADATA_URL
    )
    metadata = json.loads(metadata_bytes)
    if not isinstance(metadata, dict):
        raise SystemExit("MAESTRO metadata is not an object")
    selected = select_maestro(maestro_rows(metadata))
    maestro_remote = open_remote(
        MAESTRO_ARCHIVE_URL,
        MAESTRO_ARCHIVE_BYTES,
        args,
    )
    with zipfile.ZipFile(maestro_remote) as archive:
        infos = {info.filename: info for info in archive.infolist()}
        maestro_members = []
        year_indices: dict[int, int] = {}
        for row in selected:
            year = int(row["year"])
            year_indices[year] = year_indices.get(year, 0) + 1
            member_name = (
                "maestro-v3.0.0/" + str(row["audio_filename"])
            )
            info = infos.get(member_name)
            if info is None or info.is_dir():
                raise SystemExit(f"missing MAESTRO member: {member_name}")
            source_id = (
                f"independent-maestro-{year}-"
                f"{year_indices[year]:02d}"
            )
            maestro_members.append(
                {
                    "source_id": source_id,
                    "provider": "maestro-v3.0.0",
                    "provider_domain": "music-piano",
                    "archive_url": MAESTRO_ARCHIVE_URL,
                    "archive_bytes": MAESTRO_ARCHIVE_BYTES,
                    "duration_seconds_from_metadata": float(
                        row["duration"]
                    ),
                    "canonical_composer": row["canonical_composer"],
                    "canonical_title": row["canonical_title"],
                    "provider_split": row["split"],
                    "performance_year": year,
                    **zip_record(info),
                }
            )

    demand_bytes, demand_headers, demand_final_url = fetch_bytes(
        DEMAND_API_URL
    )
    demand = json.loads(demand_bytes)
    if (
        not isinstance(demand, dict)
        or demand.get("id") != DEMAND_RECORD_ID
    ):
        raise SystemExit("DEMAND provider record differs")
    demand_files = sorted(
        (
            value
            for value in demand.get("files", [])
            if str(value.get("key", "")).endswith("_48k.zip")
        ),
        key=lambda value: value["key"],
    )
    if len(demand_files) != DEMAND_EXPECTED_ENVIRONMENTS:
        raise SystemExit(
            f"expected {DEMAND_EXPECTED_ENVIRONMENTS} DEMAND files, "
            f"found {len(demand_files)}"
        )
    demand_members = []
    demand_probe_bytes = 0
    for value in demand_files:
        key = value["key"]
        environment = key.removesuffix("_48k.zip").lower()
        url = value["links"]["self"]
        remote = open_remote(url, int(value["size"]), args)
        with zipfile.ZipFile(remote) as archive:
            candidates = [
                info
                for info in archive.infolist()
                if info.filename.lower().endswith("/ch01.wav")
                and not info.is_dir()
            ]
            if len(candidates) != 1:
                raise SystemExit(
                    f"{key}: expected one ch01 WAV, found "
                    f"{len(candidates)}"
                )
            info = candidates[0]
        demand_probe_bytes += remote.response_bytes
        demand_members.append(
            {
                "source_id": f"independent-demand-{environment}",
                "provider": "demand-v1.0",
                "provider_domain": "environmental-noise",
                "environment": environment,
                "archive_key": key,
                "archive_url": url,
                "archive_bytes": int(value["size"]),
                "archive_checksum_claim": value["checksum"],
                **zip_record(info),
            }
        )

    members = sorted(
        maestro_members + demand_members,
        key=lambda value: value["source_id"],
    )
    if (
        len(members)
        != len(MAESTRO_EXPECTED_YEARS)
        * MAESTRO_SELECTIONS_PER_YEAR
        + DEMAND_EXPECTED_ENVIRONMENTS
        or len({member["source_id"] for member in members})
        != len(members)
        or not all(SAFE_ID.fullmatch(member["source_id"]) for member in members)
    ):
        raise SystemExit("independent source inventory differs")
    plan = {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        "state": "planned_without_audio_extraction",
        "created_at": datetime.now(UTC).isoformat(),
        "feature_scores_opened": False,
        "release_heldout_opened": False,
        "public_verdict_enabled": False,
        "selection_seed": SELECTION_SEED,
        "tool": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "providers": {
            "maestro": {
                "official_page": (
                    "https://magenta.tensorflow.org/datasets/maestro"
                ),
                "version": "3.0.0",
                "terms": "CC BY-NC-SA 4.0; local research only",
                "pcm_claim": (
                    "uncompressed 44.1-48 kHz 16-bit stereo PCM"
                ),
                "metadata_requested_url": MAESTRO_METADATA_URL,
                "metadata_final_url": metadata_final_url,
                "metadata_sha256": sha256_bytes(metadata_bytes),
                "metadata_etag": metadata_headers.get("ETag"),
                "archive_requested_url": MAESTRO_ARCHIVE_URL,
                "archive_final_url": maestro_remote.final_url,
                "archive_bytes": maestro_remote.length,
                "archive_sha256_provider_claim": (
                    MAESTRO_ARCHIVE_SHA256_CLAIM
                ),
                "archive_sha256_locally_verified": False,
                "selection": {
                    "years": list(MAESTRO_EXPECTED_YEARS),
                    "per_year": MAESTRO_SELECTIONS_PER_YEAR,
                    "duration_seconds_inclusive": [
                        MAESTRO_MINIMUM_DURATION_SECONDS,
                        MAESTRO_MAXIMUM_DURATION_SECONDS,
                    ],
                    "excluded_filename_tokens_case_insensitive": [
                        "mp3"
                    ],
                    "rank": (
                        "ascending SHA-256 of selection seed, NUL, and "
                        "audio filename"
                    ),
                },
                "range_probe": maestro_remote.stats(),
            },
            "demand": {
                "official_record": (
                    "https://zenodo.org/records/1227121"
                ),
                "doi": "10.5281/zenodo.1227121",
                "terms": "CC BY-SA 3.0; local research only",
                "pcm_claim": (
                    "real-world 16-channel WAV recordings at 48 kHz"
                ),
                "api_requested_url": DEMAND_API_URL,
                "api_final_url": demand_final_url,
                "api_sha256": sha256_bytes(demand_bytes),
                "api_etag": demand_headers.get("ETag"),
                "selection": (
                    "ch01.wav from every provider-listed *_48k.zip"
                ),
                "range_probe_response_bytes": demand_probe_bytes,
            },
        },
        "source_count": len(members),
        "provider_counts": {
            "maestro-v3.0.0": len(maestro_members),
            "demand-v1.0": len(demand_members),
        },
        "member_inventory_sha256": canonical_sha256(members),
        "members": members,
    }
    write_new_json(args.output.expanduser().resolve(), plan)
    print(
        f"planned {len(members)} PCM sources; "
        f"downloaded {maestro_remote.response_bytes + demand_probe_bytes} "
        "Range bytes"
    )
    return 0


class MemberDigest:
    def __init__(self) -> None:
        self.sha256 = hashlib.sha256()
        self.crc32 = 0
        self.bytes = 0

    def update(self, payload: bytes) -> None:
        self.sha256.update(payload)
        self.crc32 = zlib.crc32(payload, self.crc32)
        self.bytes += len(payload)


def read_exact(source, count: int, digest: MemberDigest) -> bytes:
    output = bytearray()
    while len(output) < count:
        chunk = source.read(count - len(output))
        if not chunk:
            raise OSError(
                f"unexpected EOF after {len(output)}/{count} bytes"
            )
        digest.update(chunk)
        output.extend(chunk)
    return bytes(output)


def extract_central_wav_excerpt(
    *,
    source,
    info: zipfile.ZipInfo,
    destination: Path,
    excerpt_seconds: float,
) -> dict:
    digest = MemberDigest()
    prefix = bytearray(read_exact(source, 12, digest))
    if prefix[:4] != b"RIFF" or prefix[8:12] != b"WAVE":
        raise OSError(f"{info.filename}: expected RIFF/WAVE")
    fmt_payload = None
    data_size = None
    data_size_offset = None
    while data_size is None:
        header = read_exact(source, 8, digest)
        chunk_id = header[:4]
        chunk_size = struct.unpack_from("<I", header, 4)[0]
        prefix.extend(header)
        if chunk_id == b"data":
            data_size = chunk_size
            data_size_offset = len(prefix) - 4
            break
        payload = read_exact(
            source,
            chunk_size + (chunk_size & 1),
            digest,
        )
        prefix.extend(payload)
        if chunk_id == b"fmt ":
            fmt_payload = payload[:chunk_size]
    if fmt_payload is None or len(fmt_payload) < 16:
        raise OSError(f"{info.filename}: missing PCM fmt chunk")
    (
        format_tag,
        channels,
        sample_rate_hz,
        byte_rate,
        block_align,
        bits_per_sample,
    ) = struct.unpack_from("<HHIIHH", fmt_payload)
    if (
        format_tag not in {1, 0xFFFE}
        or channels <= 0
        or sample_rate_hz < 44_100
        or bits_per_sample != 16
        or block_align != channels * 2
        or data_size % block_align
    ):
        raise OSError(f"{info.filename}: unsupported PCM WAV facts")
    total_frames = data_size // block_align
    excerpt_frames = min(
        total_frames,
        round(excerpt_seconds * sample_rate_hz),
    )
    start_frame = (total_frames - excerpt_frames) // 2
    start_byte = start_frame * block_align
    excerpt_bytes = excerpt_frames * block_align
    end_byte = start_byte + excerpt_bytes
    assert data_size_offset is not None
    struct.pack_into("<I", prefix, data_size_offset, excerpt_bytes)
    struct.pack_into("<I", prefix, 4, len(prefix) - 8 + excerpt_bytes)

    written = 0
    position = 0
    with destination.open("xb") as output:
        output.write(prefix)
        remaining = data_size
        while remaining:
            chunk = source.read(min(READ_BYTES, remaining))
            if not chunk:
                raise OSError(f"{info.filename}: truncated data")
            digest.update(chunk)
            chunk_end = position + len(chunk)
            begin = max(position, start_byte)
            end = min(chunk_end, end_byte)
            if begin < end:
                output.write(
                    chunk[begin - position : end - position]
                )
                written += end - begin
            position = chunk_end
            remaining -= len(chunk)
        if data_size & 1:
            read_exact(source, 1, digest)
        for chunk in iter(lambda: source.read(READ_BYTES), b""):
            digest.update(chunk)
    if (
        written != excerpt_bytes
        or digest.bytes != info.file_size
        or f"{digest.crc32 & 0xFFFFFFFF:08x}"
        != f"{info.CRC:08x}"
    ):
        raise OSError(f"{info.filename}: member verification differs")
    return {
        "member_sha256": digest.sha256.hexdigest(),
        "member_crc32": f"{digest.crc32 & 0xFFFFFFFF:08x}",
        "member_bytes": digest.bytes,
        "format_tag": format_tag,
        "channels": channels,
        "sample_rate_hz": sample_rate_hz,
        "byte_rate": byte_rate,
        "block_align": block_align,
        "bits_per_sample": bits_per_sample,
        "source_frame_count": total_frames,
        "excerpt_start_frame": start_frame,
        "excerpt_frame_count": excerpt_frames,
        "excerpt_seconds": excerpt_frames / sample_rate_hz,
        "output_sha256": sha256_file(destination),
        "output_bytes": destination.stat().st_size,
    }


def validate_plan(plan: dict) -> None:
    members = plan.get("members")
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("run_id") != RUN_ID
        or plan.get("state") != "planned_without_audio_extraction"
        or plan.get("feature_scores_opened") is not False
        or plan.get("release_heldout_opened") is not False
        or plan.get("public_verdict_enabled") is not False
        or not isinstance(members, list)
        or plan.get("source_count") != len(members)
        or plan.get("member_inventory_sha256")
        != canonical_sha256(members)
        or plan.get("tool", {}).get("sha256")
        != sha256_file(Path(__file__).resolve())
    ):
        raise SystemExit("source plan contract differs")


def resolve_beneath(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    if path != root and root not in path.parents:
        raise SystemExit(f"path escapes root: {relative_path}")
    return path


def verify_record(root: Path, record: dict) -> None:
    path = resolve_beneath(root, record["relative_path"])
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size != record["output_bytes"]
        or sha256_file(path) != record["output_sha256"]
    ):
        raise SystemExit(f"{record['source_id']}: retained source differs")


def command_acquire(args: argparse.Namespace) -> int:
    plan_path = args.plan.expanduser().resolve()
    plan = load_json(plan_path)
    validate_plan(plan)
    root = args.root.expanduser().resolve()
    state_path = root / "acquisition.json"
    embedded_plan_path = root / "provenance" / "source-plan.json"
    if state_path.exists():
        state = load_json(state_path)
        if (
            state.get("run_id") != RUN_ID
            or state.get("plan_sha256") != sha256_file(plan_path)
            or state.get("excerpt_seconds_requested")
            != args.excerpt_seconds
        ):
            raise SystemExit("existing acquisition state differs")
    else:
        if root.exists() and any(root.iterdir()):
            raise SystemExit("refusing non-empty root without state")
        (root / "sources").mkdir(parents=True)
        (root / ".partial").mkdir()
        embedded_plan_path.parent.mkdir()
        shutil.copyfile(plan_path, embedded_plan_path)
        state = {
            "schema_version": SCHEMA_VERSION,
            "run_id": RUN_ID,
            "state": "acquisition_in_progress",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "plan_path": str(plan_path),
            "embedded_plan_relative_path": (
                "provenance/source-plan.json"
            ),
            "plan_sha256": sha256_file(plan_path),
            "excerpt_seconds_requested": args.excerpt_seconds,
            "minimum_free_bytes": args.minimum_free_bytes,
            "feature_scores_opened": False,
            "release_heldout_opened": False,
            "public_verdict_enabled": False,
            "completed": [],
        }
        replace_json(state_path, state)
    if (
        not embedded_plan_path.is_file()
        or sha256_file(embedded_plan_path) != state["plan_sha256"]
    ):
        raise SystemExit("embedded source plan differs")
    completed = {
        record["source_id"]: record for record in state["completed"]
    }
    for record in completed.values():
        verify_record(root, record)

    members = plan["members"]
    for number, member in enumerate(members, 1):
        source_id = member["source_id"]
        if source_id in completed:
            print(f"[{number:02}/{len(members):02}] {source_id} verified")
            continue
        free = shutil.disk_usage(root).free
        if free < args.minimum_free_bytes + member["uncompressed_bytes"]:
            raise SystemExit(
                f"{source_id}: free-space reserve would be crossed"
            )
        partial = root / ".partial" / f"{source_id}.wav.partial"
        destination = root / "sources" / f"{source_id}.wav"
        if partial.exists() or destination.exists():
            raise SystemExit(f"{source_id}: unjournaled output exists")
        print(f"[{number:02}/{len(members):02}] {source_id} acquiring")
        remote = open_remote(
            member["archive_url"],
            member["archive_bytes"],
            args,
        )
        with zipfile.ZipFile(remote) as archive:
            info = archive.getinfo(member["member_name"])
            if zip_record(info) != {
                key: member[key]
                for key in (
                    "member_name",
                    "zip_crc32",
                    "compressed_bytes",
                    "uncompressed_bytes",
                    "compression_method",
                    "header_offset",
                )
            }:
                raise SystemExit(f"{source_id}: ZIP member differs")
            with archive.open(info) as source:
                facts = extract_central_wav_excerpt(
                    source=source,
                    info=info,
                    destination=partial,
                    excerpt_seconds=args.excerpt_seconds,
                )
        partial.replace(destination)
        record = {
            "source_id": source_id,
            "provider": member["provider"],
            "provider_domain": member["provider_domain"],
            "relative_path": f"sources/{source_id}.wav",
            "archive_url": member["archive_url"],
            "archive_bytes": member["archive_bytes"],
            "member_name": member["member_name"],
            "zip_crc32": member["zip_crc32"],
            **facts,
            "range_transfer": remote.stats(),
        }
        state["completed"].append(record)
        state["updated_at"] = datetime.now(UTC).isoformat()
        state["completed_count"] = len(state["completed"])
        replace_json(state_path, state)
        completed[source_id] = record

    ordered = sorted(
        state["completed"],
        key=lambda value: value["source_id"],
    )
    if len(ordered) != len(members):
        raise SystemExit("completed source count differs")
    state["completed"] = ordered
    state["completed_count"] = len(ordered)
    state["state"] = "acquisition_complete"
    state["completed_at"] = datetime.now(UTC).isoformat()
    state["updated_at"] = state["completed_at"]
    state["source_output_inventory_sha256"] = canonical_sha256(ordered)
    state["retained_audio_bytes"] = sum(
        record["output_bytes"] for record in ordered
    )
    state["network_range_response_bytes"] = sum(
        record["range_transfer"]["response_bytes"] for record in ordered
    )
    replace_json(state_path, state)
    print(
        f"acquired and verified {len(ordered)} PCM excerpts; "
        f"retained {state['retained_audio_bytes']} bytes"
    )
    return 0


def command_verify(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    state = load_json(root / "acquisition.json")
    records = state.get("completed")
    plan_path = root / state.get(
        "embedded_plan_relative_path",
        "invalid",
    )
    if (
        state.get("run_id") != RUN_ID
        or state.get("state") != "acquisition_complete"
        or state.get("feature_scores_opened") is not False
        or state.get("release_heldout_opened") is not False
        or not isinstance(records, list)
        or state.get("completed_count") != len(records)
        or state.get("source_output_inventory_sha256")
        != canonical_sha256(records)
        or not plan_path.is_file()
        or sha256_file(plan_path) != state.get("plan_sha256")
    ):
        raise SystemExit("completed acquisition contract differs")
    for record in records:
        verify_record(root, record)
    actual_bytes = sum(record["output_bytes"] for record in records)
    if actual_bytes != state.get("retained_audio_bytes"):
        raise SystemExit("retained byte count differs")
    print(
        f"verified {len(records)} PCM excerpts and {actual_bytes} bytes; "
        f"inventory {state['source_output_inventory_sha256']}"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--block-bytes",
        type=int,
        default=DEFAULT_BLOCK_BYTES,
    )
    result.add_argument(
        "--cache-blocks",
        type=int,
        default=DEFAULT_CACHE_BLOCKS,
    )
    commands = result.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--output", type=Path, required=True)
    plan.set_defaults(function=command_plan)
    acquire = commands.add_parser("acquire")
    acquire.add_argument("--plan", type=Path, required=True)
    acquire.add_argument("--root", type=Path, required=True)
    acquire.add_argument(
        "--excerpt-seconds",
        type=float,
        default=DEFAULT_EXCERPT_SECONDS,
    )
    acquire.add_argument(
        "--minimum-free-bytes",
        type=int,
        default=DEFAULT_MINIMUM_FREE_BYTES,
    )
    acquire.set_defaults(function=command_acquire)
    verify = commands.add_parser("verify")
    verify.add_argument("--root", type=Path, required=True)
    verify.set_defaults(function=command_verify)
    return result


def main() -> int:
    args = parser().parse_args()
    if args.block_bytes <= 0 or args.cache_blocks <= 0:
        raise SystemExit("Range cache settings must be positive")
    return args.function(args)


if __name__ == "__main__":
    raise SystemExit(main())
