import hashlib
import importlib.util
import io
import json
import math
import struct
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_source_trait_sparse_tonal_exact_member_confirmation.py"
SPEC = importlib.util.spec_from_file_location("sparse_tonal_exact_confirmation", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def wav_bytes(channels: list[list[int]], bits: int, sample_rate: int = 44100) -> bytes:
    channel_count = len(channels)
    frame_count = len(channels[0])
    width = bits // 8
    payload = bytearray()
    for frame in range(frame_count):
        for channel in channels:
            value = channel[frame]
            if width == 2:
                payload.extend(int(value).to_bytes(2, "little", signed=True))
            else:
                if value < 0:
                    value += 1 << 24
                payload.extend(int(value).to_bytes(3, "little"))
    block_align = channel_count * width
    fmt = struct.pack("<HHIIHH", 1, channel_count, sample_rate, sample_rate * block_align, block_align, bits)
    padded_payload = bytes(payload) + (b"\0" if len(payload) & 1 else b"")
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(payload)) + padded_payload
    return b"RIFF" + struct.pack("<I", len(body)) + body


def sparse_noise(frame_count: int) -> list[int]:
    values = [0] * frame_count
    state = 0x12345678
    for index in range(frame_count // 10):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        values[index] = ((state >> 8) & 0xFFFF) - 32768
    return values


def continuous_tone(frame_count: int) -> list[int]:
    return [round(20000 * math.sin(2 * math.pi * 441 * index / 44100)) for index in range(frame_count)]


class SparseTonalExactMemberConfirmationTest(unittest.TestCase):
    def test_committed_plan_is_valid(self) -> None:
        plan = MODULE.load_json(MODULE.PLAN_PATH)
        self.assertEqual([], MODULE.validate_plan(plan))

    def test_pcm_parser_supports_signed_16_and_24_bit(self) -> None:
        for bits in (16, 24):
            maximum = (1 << (bits - 1)) - 1
            minimum = -(1 << (bits - 1))
            encoded = wav_bytes([[minimum, -1, 0, 1, maximum]], bits)
            facts, channels, pcm = MODULE.parse_integer_pcm_wav(encoded)
            self.assertEqual(bits, facts["bits_per_sample"])
            self.assertEqual([[minimum, -1, 0, 1, maximum]], channels)
            self.assertEqual(5 * bits // 8, len(pcm))

    def test_two_private_replays_and_public_redaction(self) -> None:
        frame_count = 44100
        sparse = sparse_noise(frame_count)
        tone = continuous_tone(frame_count)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            freesound = root / "provider-original.wav"
            freesound.write_bytes(wav_bytes([sparse, sparse], 24))
            archive_path = root / "TinySOL.tar.gz"
            member_path = "./Winds/Oboe/ordinario/Ob-ord-D#4-mf-N-N.wav"
            member_payload = wav_bytes([tone], 16)
            with tarfile.open(archive_path, "w:gz") as archive:
                info = tarfile.TarInfo(member_path)
                info.size = len(member_payload)
                info.mtime = 0
                archive.addfile(info, io.BytesIO(member_payload))
            prior = MODULE.TINYSOL_ARCHIVE_SHA256
            MODULE.TINYSOL_ARCHIVE_SHA256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            try:
                private = root / "private"
                public = root / "public.json"
                report = MODULE.run(
                    MODULE.load_json(MODULE.PLAN_PATH),
                    MODULE.PLAN_PATH,
                    freesound,
                    archive_path,
                    private,
                    public,
                )
            finally:
                MODULE.TINYSOL_ARCHIVE_SHA256 = prior
            self.assertTrue(report["decision"]["all_exact_member_descriptor_confirmations_passed"])
            self.assertEqual(
                (private / "private-replay-a.json").read_bytes(),
                (private / "private-replay-b.json").read_bytes(),
            )
            self.assertTrue((private / "source-attribution.json").is_file())
            public_text = public.read_text()
            self.assertNotIn(str(root), public_text)
            self.assertNotIn("encoded_sha256", public_text)
            self.assertNotIn("pcm_sha256", public_text)
            parsed = json.loads(public_text)
            self.assertFalse(parsed["execution"]["decoded_or_derived_pcm_retained"])


if __name__ == "__main__":
    unittest.main()
