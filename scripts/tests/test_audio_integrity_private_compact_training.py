import importlib.util
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "stage-audio-integrity-private-compact-training.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audio_integrity_private_compact_training",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PrivateCompactTrainingTests(unittest.TestCase):
    def test_safe_member_name_normalizes_dot_prefix_and_rejects_escape(self):
        self.assertEqual(
            MODULE.safe_member_name("./generated/case.wav"),
            "generated/case.wav",
        )
        with self.assertRaisesRegex(SystemExit, "unsafe"):
            MODULE.safe_member_name("../outside.wav")
        with self.assertRaisesRegex(SystemExit, "unsafe"):
            MODULE.safe_member_name("/absolute.wav")

    def test_read_archive_member_streams_zstd_tar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tar_path = root / "source.tar"
            archive_path = root / "source.tar.zst"
            encoded = json.dumps({"schema_version": 1}).encode()
            with tarfile.open(tar_path, "w") as archive:
                root_member = tarfile.TarInfo(".")
                root_member.type = tarfile.DIRTYPE
                archive.addfile(root_member)
                member = tarfile.TarInfo("./manifest.json")
                member.size = len(encoded)
                archive.addfile(member, io.BytesIO(encoded))
            subprocess.run(
                [
                    "zstd",
                    "-q",
                    "-o",
                    str(archive_path),
                    str(tar_path),
                ],
                check=True,
            )
            result = MODULE.read_archive_member(
                archive_path,
                "manifest.json",
                zstd="zstd",
            )
        self.assertEqual(result, encoded)

    def test_source_metadata_validation_is_counted_and_sorted(self):
        manifest = {
            "cases": [
                {
                    "case_id": "positive",
                    "class": "mp3",
                    "expectation": "controlled_positive",
                    "relative_path": "generated/positive.wav",
                    "source_group": "dev-001",
                    "split": "development",
                },
                {
                    "case_id": "negative",
                    "class": "pcm",
                    "expectation": "negative",
                    "relative_path": "generated/negative.wav",
                    "source_group": "dev-001",
                    "split": "development",
                },
            ]
        }
        fingerprints = {
            "case_sha256": {
                "negative": "a" * 64,
                "positive": "b" * 64,
            }
        }
        with (
            mock.patch.object(MODULE, "EXPECTED_CASE_COUNT", 2),
            mock.patch.object(MODULE, "EXPECTED_SOURCE_GROUP_COUNT", 1),
            mock.patch.object(MODULE, "EXPECTED_NEGATIVE_COUNT", 1),
            mock.patch.object(MODULE, "EXPECTED_POSITIVE_COUNT", 1),
        ):
            cases = MODULE.validate_source_metadata(
                manifest,
                fingerprints,
            )
        self.assertEqual(
            [case["case_id"] for case in cases],
            ["negative", "positive"],
        )

    def test_compact_member_produces_requested_flac_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wav"
            output = root / "output.flac"
            with wave.open(str(source), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16_000)
                audio.writeframes(b"\0\0" * 32_000)
            probe = MODULE.compact_member(
                source_path=source,
                output_path=output,
                duration_seconds=1.0,
                ffmpeg="ffmpeg",
                ffprobe="ffprobe",
            )
        self.assertEqual(probe["codec_name"], "flac")
        self.assertAlmostEqual(probe["duration_seconds"], 1.0, places=2)
        self.assertEqual(probe["sample_rate"], 16_000)


if __name__ == "__main__":
    unittest.main()
