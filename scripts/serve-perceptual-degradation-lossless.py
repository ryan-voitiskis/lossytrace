#!/usr/bin/env python3
"""Serve hash-bound private PCM-WAV stimuli over loopback for qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "research" / "listening-player-lossless"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/lossless-wav.js": ("lossless-wav.js", "text/javascript; charset=utf-8"),
    "/player.js": ("player.js", "text/javascript; charset=utf-8"),
}
OPAQUE_ID = re.compile(r"^[a-z][a-z0-9-]{7,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_STIMULUS_BYTES = 32 * 1024 * 1024
MAX_STIMULI = 12


@dataclass(frozen=True)
class Stimulus:
    stimulus_id: str
    path: Path
    sha256: str
    byte_length: int
    sample_rate_hz: int
    channel_count: int
    bit_depth: int


@dataclass(frozen=True)
class DeliverySession:
    manifest_id: str
    sample_rate_hz: int
    stimuli: tuple[Stimulus, ...]

    def public_record(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "state": "private_lossless_delivery_qualification_only",
            "manifest_id": self.manifest_id,
            "sample_rate_hz": self.sample_rate_hz,
            "human_collection_authorized": False,
            "listener_response_collection_enabled": False,
            "metric_score_included": False,
            "condition_recipe_included": False,
            "private_path_included": False,
            "stimuli": [
                {
                    "stimulus_id": item.stimulus_id,
                    "private_audio_sha256": item.sha256,
                    "byte_length": item.byte_length,
                    "container": "wav",
                    "sample_rate_hz": item.sample_rate_hz,
                    "channel_count": item.channel_count,
                    "bit_depth": item.bit_depth,
                }
                for item in self.stimuli
            ],
        }


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _inside_repo(path: Path) -> bool:
    try:
        path.relative_to(ROOT)
    except ValueError:
        return False
    return True


def parse_pcm_wav(value: bytes) -> dict[str, int]:
    if len(value) < 44 or value[:4] != b"RIFF" or value[8:12] != b"WAVE":
        raise ValueError("audio is not a RIFF/WAVE file")
    if struct.unpack_from("<I", value, 4)[0] + 8 != len(value):
        raise ValueError("RIFF length differs")
    offset = 12
    format_record: tuple[int, int, int, int, int, int] | None = None
    data_length: int | None = None
    while offset + 8 <= len(value):
        chunk_id = value[offset : offset + 4]
        chunk_length = struct.unpack_from("<I", value, offset + 4)[0]
        start = offset + 8
        end = start + chunk_length
        if end > len(value):
            raise ValueError("WAV chunk exceeds file length")
        if chunk_id == b"fmt ":
            if format_record is not None or chunk_length < 16:
                raise ValueError("WAV format chunk differs")
            format_record = struct.unpack_from("<HHIIHH", value, start)
        elif chunk_id == b"data":
            if data_length is not None:
                raise ValueError("multiple WAV data chunks are unsupported")
            data_length = chunk_length
        offset = end + (chunk_length & 1)
    if offset != len(value) or format_record is None or data_length is None:
        raise ValueError("required WAV chunks are absent or malformed")
    audio_format, channels, sample_rate, byte_rate, block_align, bits = format_record
    if audio_format != 1:
        raise ValueError("only integer PCM WAV is supported")
    if channels not in {1, 2} or sample_rate not in {44100, 48000}:
        raise ValueError("WAV channel count or sample rate is unsupported")
    if bits not in {16, 24, 32}:
        raise ValueError("WAV bit depth is unsupported")
    expected_align = channels * (bits // 8)
    if block_align != expected_align or byte_rate != sample_rate * expected_align:
        raise ValueError("WAV byte geometry differs")
    if data_length == 0 or data_length % block_align:
        raise ValueError("WAV PCM payload is empty or misaligned")
    return {
        "sample_rate_hz": sample_rate,
        "channel_count": channels,
        "bit_depth": bits,
        "byte_length": len(value),
    }


def load_delivery_map(path: Path) -> DeliverySession:
    map_path = path.resolve(strict=True)
    if _inside_repo(map_path):
        raise ValueError("private delivery map must remain outside the repository")
    raw = json.loads(map_path.read_text(encoding="utf-8"))
    if set(raw) != {
        "schema_version",
        "state",
        "manifest_id",
        "sample_rate_hz",
        "human_collection_authorized",
        "stimuli",
    }:
        raise ValueError("private delivery map fields differ")
    if raw["schema_version"] != 1:
        raise ValueError("private delivery map schema version differs")
    if raw["state"] != "private_lossless_delivery_qualification_only":
        raise ValueError("private delivery map state differs")
    if raw["human_collection_authorized"] is not False:
        raise ValueError("human collection must remain unauthorized")
    if not OPAQUE_ID.fullmatch(raw.get("manifest_id", "")):
        raise ValueError("manifest identifier is not opaque")
    session_rate = raw.get("sample_rate_hz")
    if session_rate not in {44100, 48000}:
        raise ValueError("session sample rate is unsupported")
    rows = raw.get("stimuli")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_STIMULI:
        raise ValueError("private stimulus count is unsupported")

    stimuli = []
    identifiers = set()
    for row in rows:
        if set(row) != {
            "stimulus_id",
            "private_audio_path",
            "private_audio_sha256",
            "container",
            "sample_rate_hz",
            "channel_count",
            "bit_depth",
        }:
            raise ValueError("private stimulus fields differ")
        stimulus_id = row.get("stimulus_id", "")
        if not OPAQUE_ID.fullmatch(stimulus_id) or stimulus_id in identifiers:
            raise ValueError("private stimulus identifiers must be unique and opaque")
        identifiers.add(stimulus_id)
        expected_sha = row.get("private_audio_sha256", "")
        if not SHA256.fullmatch(expected_sha):
            raise ValueError(f"{stimulus_id}: SHA-256 binding differs")
        audio_value = row.get("private_audio_path")
        if not isinstance(audio_value, str) or not Path(audio_value).is_absolute():
            raise ValueError(f"{stimulus_id}: private audio path must be absolute")
        audio_path = Path(audio_value).resolve(strict=True)
        if _inside_repo(audio_path) or not audio_path.is_file():
            raise ValueError(f"{stimulus_id}: audio must be a private regular file")
        byte_length = audio_path.stat().st_size
        if not 44 <= byte_length <= MAX_STIMULUS_BYTES:
            raise ValueError(f"{stimulus_id}: audio byte length is unsupported")
        value = audio_path.read_bytes()
        if sha256_bytes(value) != expected_sha:
            raise ValueError(f"{stimulus_id}: audio SHA-256 differs")
        parsed = parse_pcm_wav(value)
        expected = {
            "sample_rate_hz": row.get("sample_rate_hz"),
            "channel_count": row.get("channel_count"),
            "bit_depth": row.get("bit_depth"),
            "byte_length": byte_length,
        }
        if row.get("container") != "wav" or parsed != expected:
            raise ValueError(f"{stimulus_id}: audio format binding differs")
        if parsed["sample_rate_hz"] != session_rate:
            raise ValueError(f"{stimulus_id}: unbound resampling would be required")
        stimuli.append(
            Stimulus(
                stimulus_id=stimulus_id,
                path=audio_path,
                sha256=expected_sha,
                byte_length=byte_length,
                sample_rate_hz=parsed["sample_rate_hz"],
                channel_count=parsed["channel_count"],
                bit_depth=parsed["bit_depth"],
            )
        )
    return DeliverySession(raw["manifest_id"], session_rate, tuple(stimuli))


def make_handler(session: DeliverySession) -> type[BaseHTTPRequestHandler]:
    by_id = {item.stimulus_id: item for item in session.stimuli}
    public_session = json.dumps(
        session.public_record(), sort_keys=True, separators=(",", ":")
    ).encode()

    class Handler(BaseHTTPRequestHandler):
        server_version = "LossyTraceQualification/1"

        def log_message(self, _format: str, *args: object) -> None:
            return

        def _headers(self, status: HTTPStatus, content_type: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()

        def _send(self, content_type: str, value: bytes) -> None:
            self._headers(HTTPStatus.OK, content_type, len(value))
            self.wfile.write(value)

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            parsed_url = urlsplit(self.path)
            if parsed_url.query or parsed_url.fragment:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            route = unquote(parsed_url.path)
            if route in STATIC_FILES:
                filename, content_type = STATIC_FILES[route]
                self._send(content_type, (APP_ROOT / filename).read_bytes())
                return
            if route == "/session.json":
                self._send("application/json", public_session)
                return
            match = re.fullmatch(r"/stimuli/([a-z][a-z0-9-]{7,63})\.wav", route)
            if match:
                stimulus = by_id.get(match.group(1))
                if stimulus is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                value = stimulus.path.read_bytes()
                if (
                    len(value) != stimulus.byte_length
                    or sha256_bytes(value) != stimulus.sha256
                ):
                    self.send_error(HTTPStatus.CONFLICT)
                    return
                self._send("audio/wav", value)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    return Handler


def create_server(session: DeliverySession, port: int = 0) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(session))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delivery-map", required=True, type=Path)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    try:
        session = load_delivery_map(args.delivery_map)
    except OSError:
        parser.error("private delivery map or audio could not be read")
    except json.JSONDecodeError:
        parser.error("private delivery map JSON is invalid")
    except ValueError as error:
        parser.error(str(error))
    server = create_server(session, args.port)
    host, port = server.server_address
    print(
        json.dumps(
            {
                "state": "private_lossless_delivery_qualification_only",
                "origin": f"http://{host}:{port}",
                "manifest_id": session.manifest_id,
                "private_path_printed": False,
                "human_collection_authorized": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
