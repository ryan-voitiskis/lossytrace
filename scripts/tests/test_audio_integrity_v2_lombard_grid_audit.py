from __future__ import annotations

import importlib.util
import json
import struct
import tempfile
import unittest
import wave
import zipfile
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit-audio-integrity-v2-lombard-grid.py"
SPEC = importlib.util.spec_from_file_location("lombard_grid_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def integer_wave() -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(struct.pack("<4h", 0, 1, -1, 0))
    return output.getvalue()


def float_wave() -> bytes:
    samples = struct.pack("<4f", 0.0, 0.25, -0.25, 0.0)
    fmt = struct.pack("<HHIIHHH", 3, 1, 16000, 64000, 4, 32, 0)
    fact = struct.pack("<I", 4)
    body = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"fact" + struct.pack("<I", len(fact)) + fact
    body += b"data" + struct.pack("<I", len(samples)) + samples
    return b"RIFF" + struct.pack("<I", len(body) + 4) + b"WAVE" + body


class LombardGridAuditTest(unittest.TestCase):
    def test_wave_header_supports_integer_and_float_pcm(self) -> None:
        integer = MODULE.read_wave_header(BytesIO(integer_wave()))
        floating = MODULE.read_wave_header(BytesIO(float_wave()))
        self.assertEqual("signed_integer_pcm", integer["sample_format"])
        self.assertEqual(16, integer["bits_per_sample"])
        self.assertEqual("ieee_float_pcm", floating["sample_format"])
        self.assertEqual(32, floating["bits_per_sample"])
        self.assertEqual(4, floating["frame_count"])

    def test_audit_applies_conservative_reference_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio_path = root / "audio.zip"
            metadata_path = root / "metadata.zip"
            rows = [
                {"SPKR": "s2", "COND": "p", "UTTERANCE": "abc123", "STATUS": "CORRECT"},
                {"SPKR": "s2", "COND": "l", "UTTERANCE": "def456", "STATUS": "WRONG"},
                {"SPKR": "s3", "COND": "p", "UTTERANCE": "ghi789", "STATUS": "CORRECT"},
                {"SPKR": "s3", "COND": "p", "UTTERANCE": "ghi789", "STATUS": "CORRECT"},
            ]
            with zipfile.ZipFile(metadata_path, "w") as archive:
                archive.writestr("lombardgrid/json/s2.json", json.dumps(rows[:2]))
                archive.writestr("lombardgrid/json/s3.json", json.dumps(rows[2:]))
            with zipfile.ZipFile(audio_path, "w") as archive:
                archive.writestr("lombardgrid/audio/s2_p_abc123.wav", integer_wave())
                archive.writestr(
                    "lombardgrid/audio/s2_l_def456_WRONG_xyz789.wav", float_wave()
                )
                archive.writestr("lombardgrid/audio/s3_p_ghi789.wav", integer_wave())
                archive.writestr("lombardgrid/audio/s4_p_jkl012.wav", integer_wave())

            report = MODULE.audit(audio_path, metadata_path)
            boundary = report["conservative_reference_boundary"]
            self.assertEqual(1, boundary["eligible_audio_file_count"])
            self.assertEqual(1, boundary["eligible_talker_count"])
            self.assertEqual(1, boundary["excluded_noncanonical_filename_count"])
            self.assertEqual(2, boundary["excluded_ambiguous_or_unmapped_metadata_count"])
            self.assertEqual(1, report["reconciliation"]["wrong_suffix_audio_file_count"])
            self.assertEqual(2, len(report["observed"]["riff_formats"]))
            self.assertEqual(
                {"signed_integer_pcm": 2, "ieee_float_pcm+signed_integer_pcm": 1},
                report["observed"]["talker_sample_representation_profile_counts"],
            )
            self.assertTrue(report["paths_redacted"])
            self.assertFalse(report["selection_authorized"])


if __name__ == "__main__":
    unittest.main()
