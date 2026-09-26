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
SCRIPT = ROOT / "scripts" / "audit-audio-integrity-v2-ravdess.py"
SPEC = importlib.util.spec_from_file_location("ravdess_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def pcm_wave(seed: int) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(48000)
        target.writeframes(bytes([seed, 0, seed + 1, 0]))
    return output.getvalue()


class RavdessAuditTest(unittest.TestCase):
    def make_inputs(self, root: Path) -> tuple[Path, Path, Path]:
        speech = root / "speech.zip"
        song = root / "song.zip"
        with zipfile.ZipFile(speech, "w") as target:
            target.writestr("Actor_01/03-01-01-01-01-01-01.wav", pcm_wave(1))
            target.writestr("Actor_02/03-01-01-01-01-01-02.wav", pcm_wave(3))
        with zipfile.ZipFile(song, "w") as target:
            target.writestr("Actor_01/03-02-01-01-01-01-01.wav", pcm_wave(5))
        artifacts = []
        for kind, path, channel in (
            ("speech", speech, "01"),
            ("song", song, "02"),
        ):
            artifacts.append(
                {
                    "kind": kind,
                    "channel_id": channel,
                    "filename": path.name,
                    "bytes": path.stat().st_size,
                    "provider_checksum": "md5:"
                    + hashlib.md5(
                        path.read_bytes(), usedforsecurity=False
                    ).hexdigest(),
                }
            )
        rules = root / "rules.json"
        rules.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "state": "source_identity_rules_not_allocation",
                    "source_id": "ravdess_audio_1_0_0",
                    "record_id": 1188976,
                    "record_version": "1.0.0",
                    "audio_generated": False,
                    "scores_opened": False,
                    "selection_authorized": False,
                    "artifacts": artifacts,
                    "expected": {
                        "actor_count": 2,
                        "source_group_count": 2,
                        "missing_song_actor_ids": ["02"],
                        "speech_file_count": 2,
                        "song_file_count": 1,
                        "speech_files_per_actor": 1,
                        "song_files_per_present_actor": 1,
                    },
                }
            ),
            encoding="utf-8",
        )
        return speech, song, rules

    def test_audit_groups_channels_by_actor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            speech, song, rules = self.make_inputs(Path(directory))
            report = MODULE.audit(speech, song, rules)
            self.assertEqual(3, report["observed"]["total_audio_file_count"])
            self.assertEqual(2, report["observed"]["actor_count"])
            self.assertEqual(
                {"speech": 1, "song+speech": 1},
                report["observed"]["actor_channel_profile_counts"],
            )
            self.assertEqual(
                2, report["conservative_reference_boundary"]["eligible_actor_count"]
            )
            self.assertEqual(
                [], report["observed"]["duplicate_pcm_archive_member_groups"]
            )
            self.assertEqual([], report["observed"]["non_mono_archive_member_ids"])
            self.assertTrue(report["paths_redacted"])
            self.assertFalse(report["selection_authorized"])

    def test_directory_actor_must_match_filename_actor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            speech, song, rules = self.make_inputs(Path(directory))
            with zipfile.ZipFile(speech, "w") as target:
                target.writestr("Actor_01/03-01-01-01-01-01-02.wav", pcm_wave(1))
            rule_value = json.loads(rules.read_text(encoding="utf-8"))
            speech_rule = next(
                row for row in rule_value["artifacts"] if row["kind"] == "speech"
            )
            speech_rule["bytes"] = speech.stat().st_size
            speech_rule["provider_checksum"] = "md5:" + hashlib.md5(
                speech.read_bytes(), usedforsecurity=False
            ).hexdigest()
            rules.write_text(json.dumps(rule_value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "actor identities differ"):
                MODULE.audit(speech, song, rules)

    def test_archive_provider_binding_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            speech, song, rules = self.make_inputs(Path(directory))
            rule_value = json.loads(rules.read_text(encoding="utf-8"))
            rule_value["artifacts"][0]["provider_checksum"] = "md5:" + "0" * 32
            rules.write_text(json.dumps(rule_value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "archive binding differs"):
                MODULE.audit(speech, song, rules)


if __name__ == "__main__":
    unittest.main()
