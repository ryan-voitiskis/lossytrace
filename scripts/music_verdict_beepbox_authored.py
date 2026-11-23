"""Construct and verify private codec-history variants from two published BeepBox scores."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import soundfile as sf

import music_library_pilot_convert as codec
from music_library_pilot_nuisance import quantize

WORKER = Path(__file__).with_suffix(".mjs")
RATE = 44100
TITLES = {
    "Confrontation": ("https://opengameart.org/content/four-original-midi-loops",
                      "https://creativecommons.org/publicdomain/zero/1.0/"),
    "radio city": ("https://opengameart.org/content/random-retro-ish-music-tracks",
                   "https://creativecommons.org/licenses/by/4.0/"),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def render(snapshot, title):
    result = subprocess.run(["node", WORKER, snapshot, title], check=True, capture_output=True)
    info = json.loads(result.stderr)
    if len(result.stdout) != info["frames"] * 8 or sha(result.stdout) != info["f32le_sha256"]:
        raise ValueError("inconsistent float render")
    return result.stdout, info


def check_wrapper(path, expected):
    with sf.SoundFile(path) as f:
        if (f.channels, f.samplerate, f.subtype, f.frames) != (2, RATE, "PCM_16", len(expected) // 4):
            raise ValueError("wrapper header mismatch")
        decoded = f.read(dtype="int16").astype("<i2").tobytes()
    if decoded != expected or codec.decode(path, 16) != expected:
        raise ValueError("wrapper differs from its input PCM")
    return dict(file_sha256=codec.sha(path), s16le_sha256=sha(expected))


def local_lag(reference, candidate, start, radius=2048, length=8192):
    """Normalized correlation over integral offsets; positive means candidate arrives later."""
    template = reference[start:start + length].astype(np.float64)
    search = candidate[start - radius:start + length + radius].astype(np.float64)
    template -= template.mean()
    window_sums = np.concatenate(([0.0], search.cumsum()))
    squares = np.concatenate(([0.0], (search * search).cumsum()))
    energy = squares[length:] - squares[:-length] - (window_sums[length:] - window_sums[:-length])**2 / length
    dots = np.correlate(search, template, "valid")
    scale = np.sqrt(np.maximum(0, energy) * np.dot(template, template))
    if not np.all(scale > 0):
        raise ValueError("silent or degenerate alignment window")
    coefficients = dots / scale
    peak = int(np.argmax(coefficients))
    return dict(start_frame=start, lag_frames=peak - radius, correlation=float(coefficients[peak]))


def construct(snapshot, output, title):
    folder = output / title.lower().replace(" ", "-")
    folder.mkdir()
    raw, info = render(snapshot, title)
    if render(snapshot, title) != (raw, info):
        raise ValueError("fresh render differs")
    samples = np.frombuffer(raw, dtype="<f4").reshape(-1, 2)
    pcm, clipped = quantize(samples.astype(np.float64), 16)
    frames = info["frames"]
    reference = np.frombuffer(pcm, dtype="<i2").reshape(-1, 2)[:, 0]
    url, license_url = TITLES[title]
    credit = (f"{title} by {info['author']}\n{url}\n{license_url}\n"
              "LossyTrace rendered one score pass in BeepBox 4.2.0 with fixed noise seed, "
              "converted to 16-bit PCM, and made codec round trips for private research.\n")
    (folder / "CREDITS.txt").write_text(credit)
    wav = folder / "direct.wav"
    direct = folder / "direct.flac"
    codec.from_pcm(pcm, wav, RATE, 16)
    codec.from_pcm(pcm, direct, RATE, 16, flac=True)
    originals = {p.name: check_wrapper(p, pcm) for p in (wav, direct)}
    variants = []
    for family, bitrate in codec.CASES:
        suffix = ".mp3" if family == "mp3" else ".m4a"
        stem = f"{family}-{bitrate}"
        intermediate = folder / (stem + suffix)
        codec.encode(wav, intermediate, family, bitrate)
        codec.validate_stream(intermediate, RATE, family)
        decoded = codec.decode(intermediate, 16)
        trimmed, tail = codec.trim(decoded, 16, frames)
        if trimmed == pcm:
            raise ValueError("round trip unexpectedly returned the original")
        path = folder / (stem + ".flac")
        codec.from_pcm(trimmed, path, RATE, 16, flac=True)
        record = check_wrapper(path, trimmed)
        channel = np.frombuffer(trimmed, dtype="<i2").reshape(-1, 2)[:, 0]
        anchors = (RATE, frames // 2, frames - RATE)
        variants.append(dict(family=family, kbps=bitrate, intermediate_sha256=codec.sha(intermediate),
                             decoded_s16le_sha256=sha(decoded), trailing_frames_removed=tail, **record,
                             alignment=[local_lag(reference, channel, f) for f in anchors]))
    return dict(render=info, submission=url, license=license_url, attribution_sha256=sha(credit.encode()),
                clipped_sample_values=clipped, originals=originals, variants=variants)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output", type=Path, help="new private directory")
    args = parser.parse_args()
    args.output.mkdir()
    results = [construct(args.snapshot, args.output, title) for title in TITLES]
    codec.save(args.output / "construction.json",
               dict(toolchain=codec.toolchain(), numpy=np.__version__, libsndfile=sf.__libsndfile_version__,
                    source_sha256={p.name: codec.sha(p) for p in (
                        Path(__file__), WORKER, Path(codec.__file__), WORKER.with_name("music_library_pilot_nuisance.py"))},
                    works=results))
