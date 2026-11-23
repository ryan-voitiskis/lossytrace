"""Commit a qualified file's complete native sample sequence for the private source inventory."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import soundfile as sf


DOMAIN = b"lossytrace:music-verdict-v1:native-s32le:v1\0"


def identify(path, expected_sha256):
    with path.open("rb") as raw:
        if hashlib.file_digest(raw, "sha256").hexdigest() != expected_sha256:
            raise ValueError("source file commitment mismatch")
        raw.seek(0)
        with sf.SoundFile(raw) as stream:
            rate, channels, frames = stream.samplerate, stream.channels, stream.frames
            if (stream.format not in ("WAV", "WAVEX", "FLAC") or stream.subtype not in ("PCM_16", "PCM_24")
                    or rate not in (44100, 48000) or channels not in (1, 2) or frames < 1):
                raise ValueError("unsupported native format for study identity")
            # libsndfile left-aligns signed 16/24-bit integers in a 32-bit read.
            # Exact zero extension in the low-order bits unifies lossless depth promotion.
            digest = hashlib.sha256(DOMAIN + struct.pack("<IHQ", rate, channels, frames))
            count = 0
            for block in stream.blocks(blocksize=65536, dtype="int32", always_2d=True):
                digest.update(block.astype("<i4", copy=False).tobytes(order="C"))
                count += len(block)
            if count != frames:
                raise ValueError("incomplete native PCM decode")
        raw.seek(0)
        if hashlib.file_digest(raw, "sha256").hexdigest() != expected_sha256:
            raise ValueError("source changed while computing PCM identity")
    return dict(audio_sha256=expected_sha256, canonical_pcm_sha256=digest.hexdigest(),
                frames=frames, rate=rate, channels=channels)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("expected_sha256")
    args = parser.parse_args()
    print(json.dumps(identify(args.source, args.expected_sha256), indent=2))
