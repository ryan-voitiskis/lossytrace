from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "serve-perceptual-degradation-lossless.py"
GENERATOR = ROOT / "scripts" / "generate-perceptual-degradation-lossless-dry-run.py"
VALIDATOR = ROOT / "scripts" / "validate-perceptual-degradation-lossless-delivery.py"
APP = ROOT / "research" / "listening-player-lossless"
PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "private-lossless-delivery-plan.json"
)
EVIDENCE = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-lossless-delivery-dry-run-observed-20260804-001.json"
)
SPEC = importlib.util.spec_from_file_location("lossless_delivery", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
GENERATOR_SPEC = importlib.util.spec_from_file_location(
    "lossless_delivery_generator", GENERATOR
)
assert GENERATOR_SPEC and GENERATOR_SPEC.loader
GENERATOR_MODULE = importlib.util.module_from_spec(GENERATOR_SPEC)
GENERATOR_SPEC.loader.exec_module(GENERATOR_MODULE)
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "lossless_delivery_validator", VALIDATOR
)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
VALIDATOR_MODULE = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR_MODULE)


def wav_bytes(
    *,
    sample_rate_hz: int = 48000,
    channel_count: int = 2,
    bit_depth: int = 16,
    samples: list[tuple[int, ...]] | None = None,
) -> bytes:
    values = samples or [(-32768, 32767), (0, -1), (16384, -16384)]
    if bit_depth != 16:
        raise ValueError("test helper currently emits 16-bit PCM")
    payload = b"".join(
        struct.pack("<" + "h" * channel_count, *frame) for frame in values
    )
    block_align = channel_count * (bit_depth // 8)
    fmt = struct.pack(
        "<HHIIHH",
        1,
        channel_count,
        sample_rate_hz,
        sample_rate_hz * block_align,
        block_align,
        bit_depth,
    )
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", len(body)) + body


def private_map(audio_path: Path, value: bytes) -> dict:
    return {
        "schema_version": 1,
        "state": "private_lossless_delivery_qualification_only",
        "manifest_id": "manifest-private-dryrun-0001",
        "sample_rate_hz": 48000,
        "human_collection_authorized": False,
        "stimuli": [
            {
                "stimulus_id": "stimulus-private-0001",
                "private_audio_path": str(audio_path.resolve()),
                "private_audio_sha256": hashlib.sha256(value).hexdigest(),
                "container": "wav",
                "sample_rate_hz": 48000,
                "channel_count": 2,
                "bit_depth": 16,
            }
        ],
    }


class ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for key in ("href", "src"):
            if values.get(key):
                self.references.append(values[key] or "")


class LosslessDeliveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp.name)
        self.audio = self.temp_root / "private.wav"
        self.value = wav_bytes()
        self.audio.write_bytes(self.value)
        self.map_path = self.temp_root / "private-map.json"
        self.mapping = private_map(self.audio, self.value)
        self.map_path.write_text(json.dumps(self.mapping), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_valid_map_stays_private_and_score_blind(self) -> None:
        session = MODULE.load_delivery_map(self.map_path)
        public = session.public_record()
        self.assertEqual("private_lossless_delivery_qualification_only", public["state"])
        for key in (
            "human_collection_authorized",
            "listener_response_collection_enabled",
            "metric_score_included",
            "condition_recipe_included",
            "private_path_included",
        ):
            self.assertFalse(public[key])
        serialized = json.dumps(public)
        self.assertNotIn(str(self.temp_root), serialized)
        self.assertNotIn("private_audio_path", serialized)
        self.assertEqual(hashlib.sha256(self.value).hexdigest(), public["stimuli"][0]["private_audio_sha256"])

    def test_committed_plan_and_browser_observation_are_valid(self) -> None:
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual([], VALIDATOR_MODULE.validate_evidence(evidence))
        self.assertEqual([], VALIDATOR_MODULE.validate_plan(plan))

    def test_validator_rejects_authorization_or_playback_overclaim(self) -> None:
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        plan["human_collection_authorized"] = True
        plan["completed"]["physical_playback_chain_frozen"] = True
        errors = VALIDATOR_MODULE.validate_plan(plan)
        self.assertIn("plan human_collection_authorized must remain false", errors)
        self.assertIn(
            "completed.physical_playback_chain_frozen must be false", errors
        )

        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        evidence["observed_checks"]["operator_audibility_confirmation_collected"] = True
        evidence["privacy_and_evidence_boundary"][
            "browser_automation_values_are_listening_truth"
        ] = True
        errors = VALIDATOR_MODULE.validate_evidence(evidence)
        self.assertIn(
            "observed_checks.operator_audibility_confirmation_collected must be false",
            errors,
        )
        self.assertIn(
            "privacy_and_evidence_boundary.browser_automation_values_are_listening_truth must be false",
            errors,
        )

    def test_ephemeral_generator_is_deterministic_and_server_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as first_value, tempfile.TemporaryDirectory() as second_value:
            first_root = Path(first_value)
            second_root = Path(second_value)
            first = GENERATOR_MODULE.generate(first_root)
            second = GENERATOR_MODULE.generate(second_root)
            self.assertEqual(first["audio_sha256"], second["audio_sha256"])
            self.assertEqual(first["audio_byte_length"], second["audio_byte_length"])
            self.assertFalse(first["private_path_printed"])
            self.assertFalse(first["human_collection_authorized"])
            first_session = MODULE.load_delivery_map(first_root / "delivery-map.json")
            second_session = MODULE.load_delivery_map(second_root / "delivery-map.json")
            self.assertEqual(first_session.public_record(), second_session.public_record())
            self.assertEqual(768044, first["audio_byte_length"])

    def test_hash_format_rate_and_authorization_mismatches_are_rejected(self) -> None:
        cases = []
        wrong_hash = copy.deepcopy(self.mapping)
        wrong_hash["stimuli"][0]["private_audio_sha256"] = "0" * 64
        cases.append((wrong_hash, "audio SHA-256 differs"))
        wrong_rate = copy.deepcopy(self.mapping)
        wrong_rate["sample_rate_hz"] = 44100
        cases.append((wrong_rate, "unbound resampling would be required"))
        authorized = copy.deepcopy(self.mapping)
        authorized["human_collection_authorized"] = True
        cases.append((authorized, "human collection must remain unauthorized"))
        wrong_container = copy.deepcopy(self.mapping)
        wrong_container["stimuli"][0]["container"] = "flac"
        cases.append((wrong_container, "audio format binding differs"))
        for index, (value, error) in enumerate(cases):
            path = self.temp_root / f"changed-{index}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                MODULE.load_delivery_map(path)

    def test_delivery_map_and_audio_must_remain_outside_repository(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", dir=ROOT, delete=True
        ) as handle:
            json.dump(self.mapping, handle)
            handle.flush()
            with self.assertRaisesRegex(ValueError, "outside the repository"):
                MODULE.load_delivery_map(Path(handle.name))

        outside_map = copy.deepcopy(self.mapping)
        outside_map["stimuli"][0]["private_audio_path"] = str(
            (APP / "index.html").resolve()
        )
        outside_map["stimuli"][0]["private_audio_sha256"] = hashlib.sha256(
            (APP / "index.html").read_bytes()
        ).hexdigest()
        path = self.temp_root / "repo-audio.json"
        path.write_text(json.dumps(outside_map), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "private regular file"):
            MODULE.load_delivery_map(path)

    def test_loopback_server_exposes_only_bound_bytes_and_no_write_route(self) -> None:
        session = MODULE.load_delivery_map(self.map_path)
        server = MODULE.create_server(session)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urllib.request.urlopen(origin + "/session.json") as response:
                public_bytes = response.read()
                self.assertEqual("no-store", response.headers["Cache-Control"])
                self.assertEqual("application/json", response.headers["Content-Type"])
            self.assertNotIn(str(self.temp_root).encode(), public_bytes)
            with urllib.request.urlopen(
                origin + "/stimuli/stimulus-private-0001.wav"
            ) as response:
                self.assertEqual("audio/wav", response.headers["Content-Type"])
                self.assertEqual(self.value, response.read())
            request = urllib.request.Request(origin + "/session.json", method="POST")
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            self.assertEqual(405, error.exception.code)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_server_rejects_file_changed_after_startup(self) -> None:
        session = MODULE.load_delivery_map(self.map_path)
        server = MODULE.create_server(session)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        self.audio.write_bytes(self.value + b"changed")
        try:
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(
                    origin + "/stimuli/stimulus-private-0001.wav"
                )
            self.assertEqual(409, error.exception.code)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_cli_redacts_missing_private_map_path(self) -> None:
        private_value = str(self.temp_root / "missing-sensitive-name.json")
        result = subprocess.run(
            ["python3", str(SCRIPT), "--delivery-map", private_value],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn(private_value, result.stderr)
        self.assertIn("could not be read", result.stderr)

    def test_static_player_is_local_qualification_only(self) -> None:
        parser = ReferenceParser()
        html = (APP / "index.html").read_text(encoding="utf-8")
        parser.feed(html)
        self.assertEqual(["style.css", "lossless-wav.js", "player.js"], parser.references)
        source = (APP / "player.js").read_text(encoding="utf-8")
        wav_source = (APP / "lossless-wav.js").read_text(encoding="utf-8")
        for token in (
            "decodeAudioData",
            "localStorage",
            "sessionStorage",
            "indexedDB",
            "getUserMedia",
            "MediaRecorder",
            "sendBeacon",
            "WebSocket",
            "XMLHttpRequest",
        ):
            self.assertNotIn(token, source + wav_source)
        self.assertNotIn("<form", html)
        self.assertIn("not a listening study", html.lower())

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_javascript_parser_verifies_pcm_and_rejects_format_mismatch(self) -> None:
        encoded = base64.b64encode(self.value).decode()
        script = r"""
const api = require(process.argv[1]);
const bytes = Buffer.from(process.argv[2], "base64");
const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
(async () => {
  const parsed = api.parsePcmWav(buffer, { sampleRateHz: 48000, channelCount: 2, bitDepth: 16 });
  let mismatch = false;
  try { api.parsePcmWav(buffer, { sampleRateHz: 44100 }); } catch (error) { mismatch = /binding differs/.test(error.message); }
  process.stdout.write(JSON.stringify({
    digest: await api.sha256Hex(buffer),
    sampleRateHz: parsed.sampleRateHz,
    channelCount: parsed.channelCount,
    bitDepth: parsed.bitDepth,
    frameCount: parsed.frameCount,
    firstLeft: parsed.channels[0][0],
    firstRight: parsed.channels[1][0],
    mismatch,
  }));
})().catch((error) => { process.stderr.write(error.stack); process.exit(1); });
"""
        result = subprocess.run(
            ["node", "-e", script, str(APP / "lossless-wav.js"), encoded],
            check=True,
            capture_output=True,
            text=True,
        )
        observed = json.loads(result.stdout)
        self.assertEqual(hashlib.sha256(self.value).hexdigest(), observed["digest"])
        self.assertEqual(48000, observed["sampleRateHz"])
        self.assertEqual(2, observed["channelCount"])
        self.assertEqual(16, observed["bitDepth"])
        self.assertEqual(3, observed["frameCount"])
        self.assertEqual(-1, observed["firstLeft"])
        self.assertAlmostEqual(32767 / 32768, observed["firstRight"], places=7)
        self.assertTrue(observed["mismatch"])

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_javascript_sources_parse(self) -> None:
        for path in (APP / "lossless-wav.js", APP / "player.js"):
            subprocess.run(
                ["node", "--check", str(path)],
                check=True,
                capture_output=True,
                text=True,
            )


if __name__ == "__main__":
    unittest.main()
