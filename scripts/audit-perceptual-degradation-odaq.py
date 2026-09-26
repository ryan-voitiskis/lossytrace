#!/usr/bin/env python3
"""Audit ODAQ provider metadata without downloading audio or opening scores."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter, OrderedDict
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO


ROOT = Path(__file__).resolve().parents[1]
RECORD_API_URL = "https://zenodo.org/api/records/10405774"
RECORD_ID = 10_405_774
RECORD_DOI = "10.5281/zenodo.10405774"
ARCHIVE_KEY = "ODAQ.zip"
ARCHIVE_BYTES = 1_048_071_792
ARCHIVE_CHECKSUM = "md5:9b4c1eba479ea698995798523eb80999"
LICENSE_MEMBER = "ODAQ/_detailed_license.csv"
DISCLAIMER_MEMBER = "ODAQ/_license_disclaimer.txt"
SCORE_MEMBER = "ODAQ/ODAQ_listening_test/ODAQ_results.csv"
LISTENING_PREFIX = "ODAQ/ODAQ_listening_test/"
DEFAULT_BLOCK_BYTES = 64 * 1024
DEFAULT_CACHE_BLOCKS = 4
MAX_RANGE_BYTES = 4 * 1024 * 1024
CONTENT_RANGE = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")
FOLDER_PATTERN = re.compile(r"^(?P<family>[A-Z]{2})_(?P<source>.+)$")
REQUIRED_LICENSE_COLUMNS = {
    "",
    "content",
    "original file name",
    "source",
    "author",
    "license",
    "original fs / depth",
    "original coding",
    "original format",
    "current format",
    "duration (s)",
    "notes",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(payload)


def safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(
        name
        and not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in name
    )


class HTTPRangeReader(io.RawIOBase):
    """Seekable HTTP reader with small, bounded, fail-closed Range requests."""

    def __init__(
        self,
        url: str,
        *,
        expected_size: int,
        block_bytes: int = DEFAULT_BLOCK_BYTES,
        cache_blocks: int = DEFAULT_CACHE_BLOCKS,
        maximum_response_bytes: int = MAX_RANGE_BYTES,
        retries: int = 4,
    ) -> None:
        super().__init__()
        if block_bytes <= 0 or cache_blocks <= 0 or maximum_response_bytes <= 0:
            raise ValueError("Range reader bounds must be positive")
        self.requested_url = url
        self.block_bytes = block_bytes
        self.cache_blocks = cache_blocks
        self.maximum_response_bytes = maximum_response_bytes
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
        if self.length != expected_size:
            raise OSError(
                f"remote size {self.length} differs from {expected_size}"
            )
        self.final_url = final_url
        self.etag = headers.get("ETag")
        self.last_modified = headers.get("Last-Modified")

    def _request_range(
        self, start: int, end: int
    ) -> tuple[bytes, Any, str]:
        requested_bytes = end - start + 1
        if requested_bytes <= 0 or requested_bytes > self.maximum_response_bytes:
            raise OSError("Range request exceeds the configured bound")
        if self.response_bytes + requested_bytes > self.maximum_response_bytes:
            raise OSError("cumulative Range responses exceed the configured bound")
        last_error: Exception | None = None
        for attempt in range(self.retries):
            request = urllib.request.Request(
                self.requested_url,
                headers={
                    "Accept-Encoding": "identity",
                    "Range": f"bytes={start}-{end}",
                    "User-Agent": "lossytrace-research/0",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    if response.status != 206:
                        raise OSError(f"expected HTTP 206, got {response.status}")
                    payload = response.read()
                    match = CONTENT_RANGE.match(
                        response.headers.get("Content-Range", "")
                    )
                    if (
                        match is None
                        or int(match.group(1)) != start
                        or int(match.group(2)) != end
                        or len(payload) != requested_bytes
                    ):
                        raise OSError("unexpected Range response")
                    self.request_count += 1
                    self.response_bytes += len(payload)
                    return payload, response.headers, response.geturl()
            except (OSError, TimeoutError, urllib.error.URLError) as error:
                last_error = error
                if attempt + 1 < self.retries:
                    time.sleep(0.5 * (2**attempt))
        assert last_error is not None
        raise OSError(f"Range request {start}-{end} failed: {last_error}") from last_error

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

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            position = offset
        elif whence == io.SEEK_CUR:
            position = self.position + offset
        elif whence == io.SEEK_END:
            position = self.length + offset
        else:
            raise ValueError("invalid seek mode")
        if position < 0:
            raise ValueError("negative seek position")
        self.position = position
        return position

    def readinto(self, target: bytearray | memoryview) -> int:
        if self.position >= self.length:
            return 0
        view = memoryview(target).cast("B")
        remaining = min(len(view), self.length - self.position)
        written = 0
        while written < remaining:
            block_index = self.position // self.block_bytes
            block_offset = self.position % self.block_bytes
            block = self._block(block_index)
            count = min(remaining - written, len(block) - block_offset)
            if count <= 0:
                break
            view[written : written + count] = block[block_offset : block_offset + count]
            written += count
            self.position += count
        return written

    def stats(self) -> dict[str, Any]:
        return {
            "accept_ranges_verified": True,
            "archive_payload_downloaded": False,
            "block_bytes": self.block_bytes,
            "cache_blocks": self.cache_blocks,
            "maximum_response_bytes": self.maximum_response_bytes,
            "request_count": self.request_count,
            "response_bytes": self.response_bytes,
        }


def fetch_record() -> dict[str, Any]:
    request = urllib.request.Request(
        RECORD_API_URL,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "lossytrace-research/0",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("Zenodo record is not an object")
    return value


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("id") != RECORD_ID or record.get("doi") != RECORD_DOI:
        raise ValueError("Zenodo record identity differs")
    files = [item for item in record.get("files", []) if item.get("key") == ARCHIVE_KEY]
    if len(files) != 1:
        raise ValueError("ODAQ archive binding differs")
    artifact = files[0]
    if artifact.get("size") != ARCHIVE_BYTES:
        raise ValueError("ODAQ archive byte size differs")
    if artifact.get("checksum") != ARCHIVE_CHECKSUM:
        raise ValueError("ODAQ archive checksum differs")
    content_url = artifact.get("links", {}).get("self")
    if not isinstance(content_url, str) or not content_url.startswith("https://"):
        raise ValueError("ODAQ archive content URL is unavailable")
    return {
        "content_url": content_url,
        "publication_date": record.get("metadata", {}).get("publication_date"),
        "title": record.get("metadata", {}).get("title"),
    }


def license_class(url: str) -> str:
    lowered = url.lower()
    if "creativecommons.org/licenses/by-nc/" in lowered:
        return "cc_by_nc"
    if "creativecommons.org/licenses/by/" in lowered:
        return "cc_by"
    if "creativecommons.org/publicdomain/zero/" in lowered:
        return "cc0"
    return "unknown"


def coding_class(value: str) -> str:
    normalized = value.strip().upper()
    if any(token in normalized for token in ("AAC", "MP3", "VORBIS", "OPUS", "WMA")):
        return "lossy"
    if normalized in {"PCM", "FLAC", "AIFF", "ALAC"}:
        return "uncoded_or_lossless"
    return "unknown"


def source_record(row: dict[str, str]) -> dict[str, Any]:
    source_file = row[""].strip()
    source_id = PurePosixPath(source_file).stem
    observed_license_class = license_class(row["license"].strip())
    observed_coding_class = coding_class(row["original coding"])
    reasons = []
    if observed_license_class not in {"cc_by", "cc0"}:
        reasons.append("licence_outside_cc_by_or_cc0_scope")
    if observed_coding_class == "lossy":
        reasons.append("original_source_was_lossy_coded")
    elif observed_coding_class == "unknown":
        reasons.append("original_coding_not_lossless_verified")
    return {
        "source_id": source_id,
        "content": row["content"].strip(),
        "license_url": row["license"].strip(),
        "license_class": observed_license_class,
        "original_coding": row["original coding"].strip(),
        "original_coding_class": observed_coding_class,
        "original_format": row["original format"].strip(),
        "current_format": row["current format"].strip(),
        "duration_seconds": float(row["duration (s)"].strip()),
        "clean_reference_eligible": not reasons,
        "exclusion_reasons": reasons,
    }


def zip_inventory(infos: list[zipfile.ZipInfo]) -> tuple[list[dict[str, Any]], str]:
    records = []
    for info in infos:
        if not safe_member_name(info.filename):
            raise ValueError(f"unsafe ZIP member path: {info.filename!r}")
        records.append(
            {
                "member_name": info.filename,
                "crc32": f"{info.CRC:08x}",
                "compressed_bytes": info.compress_size,
                "uncompressed_bytes": info.file_size,
                "compression_method": info.compress_type,
            }
        )
    return records, canonical_sha256(records)


def audit_archive(
    record: dict[str, Any],
    source: BinaryIO,
    *,
    range_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = validate_record(record)
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        inventory, inventory_sha256 = zip_inventory(infos)
        by_name = {info.filename: info for info in infos}
        required = {LICENSE_MEMBER, DISCLAIMER_MEMBER, SCORE_MEMBER}
        if not required <= set(by_name):
            raise ValueError("ODAQ required metadata members differ")
        license_payload = archive.read(LICENSE_MEMBER)
        disclaimer_payload = archive.read(DISCLAIMER_MEMBER)

    reader = csv.DictReader(
        io.StringIO(license_payload.decode("utf-8-sig")), delimiter=";"
    )
    if reader.fieldnames is None or set(reader.fieldnames) != REQUIRED_LICENSE_COLUMNS:
        raise ValueError("ODAQ detailed-license columns differ")
    rows = [
        row
        for row in reader
        if row.get("", "").strip().lower().endswith(".wav")
    ]
    sources = [source_record(row) for row in rows]
    by_source = {item["source_id"]: item for item in sources}
    if len(by_source) != len(sources):
        raise ValueError("ODAQ detailed-license source IDs are not unique")

    folders: dict[str, list[dict[str, Any]]] = {}
    for item in inventory:
        name = item["member_name"]
        if not name.startswith(LISTENING_PREFIX) or not name.lower().endswith(".wav"):
            continue
        relative = name[len(LISTENING_PREFIX) :]
        parts = PurePosixPath(relative).parts
        if len(parts) != 2:
            raise ValueError(f"unexpected listening WAV location: {name}")
        folders.setdefault(parts[0], []).append(item)

    listening_groups = []
    for folder_id, members in sorted(folders.items()):
        match = FOLDER_PATTERN.match(folder_id)
        if match is None:
            raise ValueError(f"unexpected listening folder ID: {folder_id}")
        source_id = match.group("source")
        source_metadata = by_source.get(source_id)
        if source_metadata is None:
            raise ValueError(f"missing licence row for listening source: {source_id}")
        reference_count = sum(
            PurePosixPath(item["member_name"]).name == "reference.wav"
            for item in members
        )
        if reference_count != 1:
            raise ValueError(f"listening group {folder_id} must have one reference")
        member_binding = [
            {
                "basename": PurePosixPath(item["member_name"]).name,
                "crc32": item["crc32"],
                "compressed_bytes": item["compressed_bytes"],
                "uncompressed_bytes": item["uncompressed_bytes"],
            }
            for item in sorted(members, key=lambda value: value["member_name"])
        ]
        listening_groups.append(
            {
                "folder_id": folder_id,
                "source_id": source_id,
                "artifact_family": match.group("family"),
                "license_class": source_metadata["license_class"],
                "clean_reference_eligible": source_metadata[
                    "clean_reference_eligible"
                ],
                "development_eligible": source_metadata[
                    "clean_reference_eligible"
                ],
                "exclusion_reasons": source_metadata["exclusion_reasons"],
                "wav_member_count": len(members),
                "wav_member_binding_sha256": canonical_sha256(member_binding),
            }
        )

    source_counts = Counter(item["license_class"] for item in sources)
    coding_counts = Counter(item["original_coding_class"] for item in sources)
    eligible_groups = [item for item in listening_groups if item["development_eligible"]]
    excluded_groups = [item for item in listening_groups if not item["development_eligible"]]
    report = {
        "schema_version": 1,
        "audit_id": "odaq-score-blind-provider-audit-20260803-001",
        "state": "provider_metadata_audited_audio_and_scores_unopened",
        "purpose": "published_development_only_not_codec_or_final_evidence",
        "provider": {
            "record_id": RECORD_ID,
            "doi": RECORD_DOI,
            "title": provider["title"],
            "publication_date": provider["publication_date"],
            "archive_key": ARCHIVE_KEY,
            "archive_bytes": ARCHIVE_BYTES,
            "archive_checksum": ARCHIVE_CHECKSUM,
        },
        "read_boundary": {
            "opened_archive_members": [DISCLAIMER_MEMBER, LICENSE_MEMBER],
            "score_member_present": SCORE_MEMBER in by_name,
            "score_member_opened": False,
            "audio_member_opened": False,
            "audio_downloaded": False,
        },
        "archive_inventory": {
            "member_count": len(inventory),
            "wav_member_count": sum(
                item["member_name"].lower().endswith(".wav") for item in inventory
            ),
            "canonical_sha256": inventory_sha256,
        },
        "metadata_bindings": {
            "detailed_license_sha256": sha256_bytes(license_payload),
            "license_disclaimer_sha256": sha256_bytes(disclaimer_payload),
        },
        "licence_policy": {
            "processed_audio_inherits_original_source_licence": True,
            "conservative_redistributable_scope": ["cc_by", "cc0"],
            "cc_by_nc_excluded_from_planned_subset": True,
            "unknown_licence_excluded": True,
        },
        "observed": {
            "detailed_license_source_count": len(sources),
            "source_license_class_counts": dict(sorted(source_counts.items())),
            "source_original_coding_class_counts": dict(
                sorted(coding_counts.items())
            ),
            "listening_group_count": len(listening_groups),
            "eligible_listening_group_count": len(eligible_groups),
            "excluded_listening_group_count": len(excluded_groups),
            "eligible_source_count": len(
                {item["source_id"] for item in eligible_groups}
            ),
        },
        "sources": sorted(sources, key=lambda item: item["source_id"]),
        "listening_groups": listening_groups,
        "range_access": range_stats
        or {
            "accept_ranges_verified": False,
            "archive_payload_downloaded": False,
            "fixture_only": True,
        },
        "paths_redacted": True,
        "metric_scores_opened": False,
        "listening_scores_opened": False,
        "selection_authorized": False,
    }
    return report


def acquisition_plan(audit: dict[str, Any], audit_sha256: str) -> dict[str, Any]:
    eligible = [
        item for item in audit["listening_groups"] if item["development_eligible"]
    ]
    excluded = [
        {
            "folder_id": item["folder_id"],
            "source_id": item["source_id"],
            "reasons": item["exclusion_reasons"],
        }
        for item in audit["listening_groups"]
        if not item["development_eligible"]
    ]
    return {
        "schema_version": 1,
        "plan_id": "odaq-public-development-acquisition-20260803-001",
        "state": "metadata_frozen_audio_acquisition_not_authorized",
        "purpose": "protocol_and_oracle_development_only_not_codec_or_final_evidence",
        "audit_binding": {
            "path": "research/toolchains/evidence/perceptual-degradation-odaq-score-blind-audit-20260803-001.json",
            "sha256": audit_sha256,
        },
        "provider_binding": audit["provider"],
        "access_boundary": {
            "audio_download_authorized": False,
            "listening_score_access_authorized": False,
            "perceptual_metric_execution_authorized": False,
            "retained_audio_access_authorized": False,
            "existing_280_case_future_subset_opened": False,
        },
        "selection": {
            "policy": "all_listening_groups_with_cc_by_or_cc0_and_lossless_or_uncoded_origin",
            "eligible_folder_ids": [item["folder_id"] for item in eligible],
            "eligible_source_ids": sorted({item["source_id"] for item in eligible}),
            "eligible_group_count": len(eligible),
            "eligible_source_count": len({item["source_id"] for item in eligible}),
            "excluded_groups": excluded,
        },
        "future_acquisition_requirements": [
            "Commit a separate authorization after confirming at least 15 GiB free disk.",
            "Stream only selected ZIP members and verify frozen CRC32 and size bindings.",
            "Do not extract or read ODAQ_results.csv until a separate score-opening authorization is committed.",
            "Do not run ViSQOL or the GstPEAQ proxy on acquired audio under this plan.",
            "Keep provider audio, derived files, caches, and listening scores out of Git.",
            "Treat ODAQ artifacts as simulated production artifacts, not actual codec encodes.",
        ],
        "minimum_free_disk_gib": 15,
        "maximum_sustained_workers": 6,
        "paths_redacted": True,
    }


def validate_frozen_evidence(
    audit: dict[str, Any], plan: dict[str, Any]
) -> list[str]:
    errors = []
    if audit.get("state") != "provider_metadata_audited_audio_and_scores_unopened":
        errors.append("ODAQ audit must remain score-blind")
    read_boundary = audit.get("read_boundary", {})
    for key in (
        "score_member_opened",
        "audio_member_opened",
        "audio_downloaded",
    ):
        if read_boundary.get(key) is not False:
            errors.append(f"read_boundary.{key} must remain false")
    if audit.get("metric_scores_opened") is not False:
        errors.append("metric scores must remain unopened")
    if audit.get("listening_scores_opened") is not False:
        errors.append("listening scores must remain unopened")
    if audit.get("selection_authorized") is not False:
        errors.append("ODAQ selection must remain unauthorized")

    if plan.get("state") != "metadata_frozen_audio_acquisition_not_authorized":
        errors.append("ODAQ acquisition plan must remain unauthorized")
    for key, value in plan.get("access_boundary", {}).items():
        if value is not False:
            errors.append(f"access_boundary.{key} must remain false")
    expected_folders = sorted(
        item["folder_id"]
        for item in audit.get("listening_groups", [])
        if item.get("development_eligible") is True
    )
    if plan.get("selection", {}).get("eligible_folder_ids") != expected_folders:
        errors.append("eligible folder selection differs from frozen audit")
    return errors


def write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise SystemExit(f"refusing to replace output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--plan-output", type=Path, required=True)
    parser.add_argument("--block-bytes", type=int, default=DEFAULT_BLOCK_BYTES)
    args = parser.parse_args()
    record = fetch_record()
    provider = validate_record(record)
    remote = HTTPRangeReader(
        provider["content_url"],
        expected_size=ARCHIVE_BYTES,
        block_bytes=args.block_bytes,
    )
    audit = audit_archive(record, remote, range_stats=remote.stats())
    audit["range_access"] = remote.stats()
    encoded = json.dumps(audit, indent=2, sort_keys=True) + "\n"
    write_json(args.audit_output, audit)
    plan = acquisition_plan(audit, sha256_bytes(encoded.encode()))
    errors = validate_frozen_evidence(audit, plan)
    if errors:
        raise SystemExit("; ".join(errors))
    write_json(args.plan_output, plan)
    print(
        json.dumps(
            {
                "audit_sha256": sha256_bytes(encoded.encode()),
                "eligible_group_count": plan["selection"][
                    "eligible_group_count"
                ],
                "range_request_count": audit["range_access"]["request_count"],
                "range_response_bytes": audit["range_access"]["response_bytes"],
                "status": "score_blind_audit_complete_audio_not_downloaded",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
