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
SCRIPT = ROOT / "scripts" / "audit-audio-integrity-v2-satp.py"
SPEC = importlib.util.spec_from_file_location("satp_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def pcm_wave(seed: int, sample_width: int = 3) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(sample_width)
        target.setframerate(48000)
        target.writeframes(bytes([seed]) * (sample_width * 2 * 4))
    return output.getvalue()


class SatpAuditTest(unittest.TestCase):
    def make_inputs(self, root: Path) -> tuple[Path, Path, Path]:
        readme = root / "README.md"
        readme.write_text(
            "SATP Dataset v1.2 contains test data.\n\n"
            "## Table 1: Recording Information\n\n"
            "| **File Name.wav** | **Location** | **Latitude** | **Longitude** | **Date of the recording** |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| 1000 Hz - 16 dBFS peak 60 s | generated | N/A | N/A | N/A |\n"
            "| A | Place A | 1 | 2 | day 1 |\n"
            "| B | Place B | 1 | 2 | day 2 |\n"
            "| C | Place C | / | / | 2019 |\n\n"
            "## CHANGELOG\n\n### 2026-02-20 v1.5\n",
            encoding="utf-8",
        )
        archive = root / "audio.zip"
        with zipfile.ZipFile(archive, "w") as target:
            target.writestr("SATP WAV/1000 Hz -16 dBFS peak 60 s.wav", pcm_wave(1, 2))
            target.writestr("SATP WAV/A.wav", pcm_wave(2))
            target.writestr("SATP WAV/B.wav", pcm_wave(3))
            target.writestr("SATP WAV/C.wav", pcm_wave(4))
        readme_md5 = hashlib.md5(
            readme.read_bytes(), usedforsecurity=False
        ).hexdigest()
        audio_md5 = hashlib.md5(
            archive.read_bytes(), usedforsecurity=False
        ).hexdigest()
        rules = root / "rules.json"
        rules.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "state": "source_identity_rules_not_allocation",
                    "source_id": "satp_soundscapes_1_5",
                    "record_id": 18715282,
                    "record_version": "v1.5",
                    "audio_generated": False,
                    "scores_opened": False,
                    "selection_authorized": False,
                    "grouping_fields": ["latitude", "longitude"],
                    "readme_sha256": hashlib.sha256(readme.read_bytes()).hexdigest(),
                    "readme_provider_checksum": f"md5:{readme_md5}",
                    "audio_bytes": archive.stat().st_size,
                    "audio_provider_checksum": f"md5:{audio_md5}",
                    "calibration_readme_recording_ids": [
                        "1000 Hz - 16 dBFS peak 60 s"
                    ],
                    "calibration_archive_recording_ids": [
                        "1000 Hz -16 dBFS peak 60 s"
                    ],
                    "expected": {
                        "readme_table_row_count": 4,
                        "calibration_row_count": 1,
                        "recording_row_count": 3,
                        "duplicate_exact_coordinate_group_count": 1,
                        "source_group_count": 2,
                    },
                }
            ),
            encoding="utf-8",
        )
        return archive, readme, rules

    def test_audit_merges_exact_coordinate_groups(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive, readme, rules = self.make_inputs(Path(directory))
            report = MODULE.audit(archive, readme, rules)
            self.assertEqual(3, report["observed"]["reference_recording_count"])
            self.assertEqual(2, report["observed"]["exact_coordinate_group_count"])
            self.assertEqual(
                2, report["conservative_reference_boundary"]["eligible_group_count"]
            )
            self.assertTrue(
                report["reconciliation"]["readme_prose_version_differs_from_record"]
            )
            self.assertTrue(report["paths_redacted"])
            self.assertFalse(report["selection_authorized"])

    def test_readme_binding_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive, readme, rules = self.make_inputs(Path(directory))
            rule_value = json.loads(rules.read_text(encoding="utf-8"))
            rule_value["readme_sha256"] = "0" * 64
            rules.write_text(json.dumps(rule_value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "README binding differs"):
                MODULE.audit(archive, readme, rules)

    def test_archive_and_readme_id_sets_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive, readme, rules = self.make_inputs(Path(directory))
            with zipfile.ZipFile(archive, "a") as target:
                target.writestr("SATP WAV/D.wav", pcm_wave(5))
            rule_value = json.loads(rules.read_text(encoding="utf-8"))
            audio_md5 = hashlib.md5(
                archive.read_bytes(), usedforsecurity=False
            ).hexdigest()
            rule_value["audio_bytes"] = archive.stat().st_size
            rule_value["audio_provider_checksum"] = f"md5:{audio_md5}"
            rules.write_text(json.dumps(rule_value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "reference identities differ"):
                MODULE.audit(archive, readme, rules)


if __name__ == "__main__":
    unittest.main()
