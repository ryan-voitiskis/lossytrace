from __future__ import annotations

import hashlib
import importlib.util
import io
import tarfile
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit-audio-integrity-v2-sonyc-backgrounds.py"
SPEC = importlib.util.spec_from_file_location("sonyc_backgrounds_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def integer_wave(seed: int) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(48000)
        target.writeframes(bytes([seed, 0, seed + 1, 0]))
    return output.getvalue()


def add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    archive.addfile(info, io.BytesIO(payload))


class SonycBackgroundsAuditTest(unittest.TestCase):
    def make_archive(self, path: Path, overlapping_sensor: bool = False) -> None:
        readme = b"After this selection process, we obtain 2 background clips.\n"
        with tarfile.open(path, "w:gz") as archive:
            add_bytes(archive, "SONYC-Backgrounds/README.md", readme)
            add_bytes(
                archive,
                "SONYC-Backgrounds/train/01_2017-01-02_03_00.wav",
                integer_wave(1),
            )
            second_sensor = "01" if overlapping_sensor else "02"
            add_bytes(
                archive,
                f"SONYC-Backgrounds/test/{second_sensor}_2017-02-03_04_00.wav",
                integer_wave(3),
            )

    def test_audit_binds_disjoint_sensor_groups(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.tar.gz"
            self.make_archive(path)
            provider_md5 = hashlib.md5(
                path.read_bytes(), usedforsecurity=False
            ).hexdigest()
            report = MODULE.audit(path, path.stat().st_size, provider_md5)
            self.assertEqual(2, report["observed"]["audio_file_count"])
            self.assertEqual(2, report["observed"]["sensor_count"])
            self.assertEqual(
                2, report["conservative_reference_boundary"]["eligible_sensor_count"]
            )
            self.assertEqual(
                0, report["reconciliation"]["observed_minus_readme_declared_clip_count"]
            )
            self.assertTrue(report["paths_redacted"])
            self.assertFalse(report["selection_authorized"])

    def test_sensor_must_not_span_provider_splits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.tar.gz"
            self.make_archive(path, overlapping_sensor=True)
            provider_md5 = hashlib.md5(
                path.read_bytes(), usedforsecurity=False
            ).hexdigest()
            with self.assertRaisesRegex(ValueError, "overlap provider splits"):
                MODULE.audit(path, path.stat().st_size, provider_md5)

    def test_provider_md5_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.tar.gz"
            self.make_archive(path)
            with self.assertRaisesRegex(ValueError, "MD5 differs"):
                MODULE.audit(path, path.stat().st_size, "0" * 32)


if __name__ == "__main__":
    unittest.main()
