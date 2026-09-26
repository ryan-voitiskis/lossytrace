from __future__ import annotations

import importlib.util
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run-perceptual-degradation-odaq-delivery.py"
SPEC = importlib.util.spec_from_file_location("odaq_delivery_runner", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def chunk(chunk_id: bytes, payload: bytes) -> bytes:
    padding = b"\0" if len(payload) & 1 else b""
    return chunk_id + struct.pack("<I", len(payload)) + payload + padding


def wave(chunks: list[bytes]) -> bytes:
    body = b"WAVE" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def float_wave() -> bytes:
    samples = [-1.0, -0.5, 0.5, 1.0 - 2.0**-24]
    data = struct.pack("<4f", *samples)
    fmt = struct.pack("<HHIIHHH", 3, 2, 48_000, 384_000, 8, 32, 0)
    return wave(
        [
            chunk(b"fmt ", fmt),
            chunk(b"fact", struct.pack("<I", 2)),
            chunk(b"data", data),
        ]
    )


def extensible_s24_wave() -> bytes:
    data = bytes.fromhex("000000ffffff123456abcdef")
    fmt = struct.pack("<HHIIHHHHI", 0xFFFE, 2, 48_000, 288_000, 6, 24, 22, 24, 0)
    fmt += MODULE.PROJECT.PCM_SUBFORMAT_GUID
    return wave([chunk(b"fmt ", fmt), chunk(b"data", data)])


def fixture(root: Path) -> tuple[list[dict], dict, dict]:
    (root / "sources").mkdir(parents=True)
    (root / ".partial").mkdir()
    values = [float_wave(), extensible_s24_wave()]
    identities = [
        ("folder-float", "source-float", "odaq-ref-float", "licence-float"),
        ("folder-int", "source-int", "odaq-ref-int", "licence-int"),
    ]
    completed = []
    for value, (folder_id, source_id, opaque_id, licence_id) in zip(values, identities):
        path = root / "sources" / f"{opaque_id}.wav"
        path.write_bytes(value)
        completed.append(
            {
                "folder_id": folder_id,
                "source_id": source_id,
                "opaque_reference_id": opaque_id,
                "relative_path": f"sources/{opaque_id}.wav",
                "sha256": MODULE.sha256_bytes(value),
                "crc32": "00000000",
                "byte_length": len(value),
                "pcm_geometry": MODULE.ACQUIRE.wav_facts(path),
                "licence_record_ids": [licence_id],
            }
        )
    inventory_sha = MODULE.ACQUIRE.completed_inventory_sha256(completed)
    state = {
        "schema_version": 1,
        "state": "reference_acquisition_complete",
        "minimum_free_bytes": MODULE.MINIMUM_FREE_BYTES,
        "processed_condition_opened": False,
        "listening_score_opened": False,
        "metric_score_opened": False,
        "completed": completed,
        "completed_count": 2,
        "retained_audio_bytes": sum(item["byte_length"] for item in completed),
        "completed_inventory_sha256": inventory_sha,
    }
    (root / "acquisition.json").write_text(json.dumps(state), encoding="utf-8")
    audit = {
        "licence_records": [
            {
                "licence_record_id": licence_id,
                "attribution_notice_ready": True,
                "source_id": source_id,
                "title": f"title-{source_id}",
                "creator": f"creator-{source_id}",
                "licence_url": "https://creativecommons.org/licenses/by/4.0/",
            }
            for _, source_id, _, licence_id in identities
        ],
        "dependency_licence_records": [],
        "listening_groups": [
            {
                "folder_id": folder_id,
                "source_id": source_id,
                "licence_record_ids": [licence_id],
            }
            for folder_id, source_id, _, licence_id in identities
        ],
    }
    expected = {
        "reference_count": 2,
        "retained_audio_bytes": state["retained_audio_bytes"],
        "completed_inventory_sha256": inventory_sha,
        "sample_rate_hz": 48_000,
        "channel_count": 2,
        "float32_reference_count": 1,
        "extensible_s24_reference_count": 1,
    }
    return completed, audit, expected


class OdaqDeliveryRunnerTest(unittest.TestCase):
    def test_committed_authorization_is_valid_and_narrow(self) -> None:
        authorization, digest = MODULE.committed_authorization()
        self.assertEqual(64, len(digest))
        scope = authorization["authorization_scope"]
        self.assertTrue(scope["retained_reference_projection_authorized"])
        self.assertTrue(scope["two_fresh_private_replays_authorized"])
        self.assertTrue(scope["attribution_attachment_authorized"])
        for key in (
            "provider_processed_condition_access_authorized",
            "provider_listening_score_access_authorized",
            "perceptual_metric_execution_authorized",
            "degradation_rating_collection_authorized",
            "listener_response_collection_authorized",
            "sealed_evidence_access_authorized",
            "public_verdict_authorized",
        ):
            self.assertFalse(scope[key])

    def test_synthetic_inventory_validates_and_two_replays_are_identical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "retained"
            completed, audit, expected = fixture(source_root)
            validated = MODULE.validate_source_inventory(source_root, expected, audit)
            self.assertEqual(completed, validated)
            authorization, authorization_sha = MODULE.committed_authorization()
            replay_states = []
            for name in ("replay-a", "replay-b"):
                replay_states.append(
                    MODULE.run_replay(
                        source_root=source_root,
                        replay_root=root / name,
                        records=validated,
                        authorization=authorization,
                        authorization_sha256=authorization_sha,
                        audit=audit,
                        resume=False,
                        disk_free=lambda _: MODULE.MINIMUM_FREE_BYTES + 1024**2,
                    )
                )
            self.assertEqual(replay_states[0]["completed"], replay_states[1]["completed"])
            self.assertEqual(
                replay_states[0]["output_inventory_sha256"],
                replay_states[1]["output_inventory_sha256"],
            )
            self.assertEqual(
                (root / "replay-a" / "attribution.json").read_bytes(),
                (root / "replay-b" / "attribution.json").read_bytes(),
            )
            self.assertEqual(
                2,
                len(json.loads((root / "replay-a" / "attribution.json").read_text())["licence_records"]),
            )
            operations = {item["operation"] for item in replay_states[0]["completed"]}
            self.assertEqual(
                {
                    "container_canonicalization_payload_unchanged",
                    "deterministic_float32_to_signed_int32_nearest_ties_to_even",
                },
                operations,
            )

    def test_completed_replay_resumes_without_rewriting_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "retained"
            completed, audit, expected = fixture(source_root)
            records = MODULE.validate_source_inventory(source_root, expected, audit)
            authorization, authorization_sha = MODULE.committed_authorization()
            replay_root = root / "replay"
            first = MODULE.run_replay(
                source_root=source_root,
                replay_root=replay_root,
                records=records,
                authorization=authorization,
                authorization_sha256=authorization_sha,
                audit=audit,
                resume=False,
                disk_free=lambda _: MODULE.MINIMUM_FREE_BYTES + 1024**2,
            )
            before = {
                item["relative_path"]: (replay_root / item["relative_path"]).read_bytes()
                for item in first["completed"]
            }
            second = MODULE.run_replay(
                source_root=source_root,
                replay_root=replay_root,
                records=records,
                authorization=authorization,
                authorization_sha256=authorization_sha,
                audit=audit,
                resume=True,
                disk_free=lambda _: MODULE.MINIMUM_FREE_BYTES + 1024**2,
            )
            self.assertEqual(first, second)
            self.assertEqual(
                before,
                {
                    item["relative_path"]: (replay_root / item["relative_path"]).read_bytes()
                    for item in second["completed"]
                },
            )

    def test_disk_reserve_fails_before_audio_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "retained"
            completed, audit, expected = fixture(source_root)
            records = MODULE.validate_source_inventory(source_root, expected, audit)
            authorization, authorization_sha = MODULE.committed_authorization()
            replay_root = root / "replay"
            with self.assertRaisesRegex(ValueError, "15 GiB disk reserve"):
                MODULE.run_replay(
                    source_root=source_root,
                    replay_root=replay_root,
                    records=records,
                    authorization=authorization,
                    authorization_sha256=authorization_sha,
                    audit=audit,
                    resume=False,
                    disk_free=lambda _: MODULE.MINIMUM_FREE_BYTES,
                )
            self.assertEqual([], list((replay_root / "sources").iterdir()))

    def test_inventory_fails_closed_on_access_boundary_or_attribution_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source_root = Path(temporary) / "retained"
            _, audit, expected = fixture(source_root)
            state_path = source_root / "acquisition.json"
            state = MODULE.load_json(state_path)
            state["processed_condition_opened"] = True
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "processed_condition_opened"):
                MODULE.validate_source_inventory(source_root, expected, audit)
            state["processed_condition_opened"] = False
            state_path.write_text(json.dumps(state), encoding="utf-8")
            audit["listening_groups"][0]["licence_record_ids"] = ["different"]
            with self.assertRaisesRegex(ValueError, "attribution binding"):
                MODULE.validate_source_inventory(source_root, expected, audit)

    def test_runner_contains_no_private_path_or_collection_surface(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("Application Support", source)
        self.assertNotIn("/Users/", source)
        self.assertNotIn("decodeAudioData", source)
        self.assertNotIn("degradation_rating", source)


if __name__ == "__main__":
    unittest.main()
