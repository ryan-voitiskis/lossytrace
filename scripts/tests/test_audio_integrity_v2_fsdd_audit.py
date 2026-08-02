from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
import wave
import zipfile
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit-audio-integrity-v2-fsdd.py"
SPEC = importlib.util.spec_from_file_location("fsdd_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


ROOT_PREFIX = "free-spoken-digit-dataset-1.0.10/"
PROVIDER_IDENTITY = {
    "method": "github_codeload_tag_commit_strong_etag",
    "tag": "v1.0.10",
    "commit_sha": "d6938f9bf1545aa66d8489fc9f1385a7abd64282",
    "etag": '"248f3f5caf01524ccd38bd74a1dac661854fd431de2abae9757c49b9fe1142f7"',
}


def pcm_wave(seed: int) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(8000)
        target.writeframes(bytes([seed, 0, seed + 1, 0]))
    return output.getvalue()


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class FsddAuditTest(unittest.TestCase):
    def make_inputs(self, root: Path, duplicate_pcm: bool = False) -> tuple[Path, Path]:
        archive = root / "fixture.zip"
        metadata = (
            "metadata = {'alice': {'gender': 'x', 'accent': 'x', "
            "'language': 'english'}}\n"
        ).encode()
        audio_members: list[tuple[str, bytes]] = []
        seed = 1
        for digit in (0, 1):
            for index in (0, 1):
                payload = pcm_wave(1 if duplicate_pcm else seed)
                seed += 2
                audio_members.append(
                    (f"recordings/{digit}_alice_{index}.wav", payload)
                )
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as target:
            target.writestr(ROOT_PREFIX, b"")
            target.writestr(ROOT_PREFIX + "recordings/", b"")
            target.writestr(ROOT_PREFIX + "metadata.py", metadata)
            for member_id, payload in audio_members:
                target.writestr(ROOT_PREFIX + member_id, payload)

        rules = root / "rules.json"
        rules.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "state": "source_identity_rules_not_allocation",
                    "source_id": "fsdd_v1_0_10",
                    "repository": "Jakobovski/free-spoken-digit-dataset",
                    "tag": "v1.0.10",
                    "audio_generated": False,
                    "scores_opened": False,
                    "selection_authorized": False,
                    "artifact": {
                        "filename": archive.name,
                        "bytes": archive.stat().st_size,
                        "local_sha256": MODULE.sha256_file(archive),
                        "provider_identity": PROVIDER_IDENTITY,
                    },
                    "expected": {
                        "archive_directory_member_ids": ["", "recordings"],
                        "archive_root_prefix": ROOT_PREFIX,
                        "audio_file_count": 4,
                        "audio_format": {
                            "bits_per_sample": 16,
                            "channel_count": 1,
                            "format_tag": 1,
                            "sample_format": "signed_integer_pcm",
                            "sample_rate_hz": 8000,
                        },
                        "digit_ids": [0, 1],
                        "files_per_digit_speaker": 2,
                        "index_ids": [0, 1],
                        "non_audio_regular_members": [
                            {
                                "bytes": len(metadata),
                                "path": "metadata.py",
                                "sha256": sha256(metadata),
                            }
                        ],
                        "processing_chain_member_ids": ["metadata.py"],
                        "regular_file_count": 5,
                        "source_group_count": 1,
                        "speaker_ids": ["alice"],
                    },
                }
            ),
            encoding="utf-8",
        )
        return archive, rules

    def update_archive_binding(self, archive: Path, rules: Path) -> None:
        value = json.loads(rules.read_text(encoding="utf-8"))
        value["artifact"]["bytes"] = archive.stat().st_size
        value["artifact"]["local_sha256"] = MODULE.sha256_file(archive)
        rules.write_text(json.dumps(value), encoding="utf-8")

    def test_audit_keeps_speaker_as_the_partition_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive, rules = self.make_inputs(Path(directory))
            report = MODULE.audit(archive, rules)
            self.assertEqual(4, report["observed"]["audio_file_count"])
            self.assertEqual(4, report["observed"]["distinct_pcm_digest_count"])
            self.assertEqual(
                1,
                report["conservative_reference_boundary"]["eligible_group_count"],
            )
            self.assertEqual(
                "repository speaker identifier",
                report["conservative_reference_boundary"][
                    "partition_grouping_unit"
                ],
            )
            self.assertTrue(report["archive_binding"]["zip_crc_verified"])
            self.assertFalse(report["selection_authorized"])

    def test_archive_binding_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive, rules = self.make_inputs(Path(directory))
            value = json.loads(rules.read_text(encoding="utf-8"))
            value["artifact"]["local_sha256"] = "0" * 64
            rules.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "artifact binding differs"):
                MODULE.audit(archive, rules)

    def test_duplicate_pcm_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive, rules = self.make_inputs(Path(directory), duplicate_pcm=True)
            with self.assertRaisesRegex(ValueError, "duplicate PCM payloads"):
                MODULE.audit(archive, rules)

    def test_speaker_metadata_must_match_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive, rules = self.make_inputs(Path(directory))
            replacement = Path(directory) / "replacement.zip"
            with zipfile.ZipFile(archive) as source, zipfile.ZipFile(
                replacement, "w", compression=zipfile.ZIP_DEFLATED
            ) as target:
                for info in source.infolist():
                    payload = source.read(info)
                    if info.filename == ROOT_PREFIX + "metadata.py":
                        payload = (
                            b"metadata = {'bob': {'gender': 'x', 'accent': 'x', "
                            b"'language': 'english'}}\n"
                        )
                    target.writestr(info.filename, payload)
            replacement.replace(archive)
            self.update_archive_binding(archive, rules)
            value = json.loads(rules.read_text(encoding="utf-8"))
            metadata = zipfile.ZipFile(archive).read(ROOT_PREFIX + "metadata.py")
            value["expected"]["non_audio_regular_members"][0]["bytes"] = len(
                metadata
            )
            value["expected"]["non_audio_regular_members"][0]["sha256"] = sha256(
                metadata
            )
            rules.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "metadata identities differ"):
                MODULE.audit(archive, rules)


if __name__ == "__main__":
    unittest.main()
