"""Offline byte-level qualification of the seeded renderer on one generated score."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import soundfile as sf

import music_library_pilot_convert as codec
from music_library_pilot_nuisance import quantize

WORKER = Path(__file__).with_name("music_verdict_beepbox_fixture.mjs")
SEED = 20261123


def render(package, rate, seed):
    run = subprocess.run(["node", WORKER, package, str(rate), str(seed)],
                         check=True, capture_output=True)
    receipt = json.loads(run.stderr)
    raw = run.stdout
    if (len(raw) != rate * 32 * 8 or hashlib.sha256(raw).hexdigest() != receipt["f32le_sha256"]
            or receipt["seed"] != seed or receipt["rate"] != rate or receipt["random_draws"] <= 0):
        raise ValueError("inconsistent render receipt")
    samples = np.frombuffer(raw, dtype="<f4").reshape(-1, 2)
    if not np.isfinite(samples).all():
        raise ValueError("non-finite render")
    return samples, receipt


def check_files(samples, folder, rate, bits):
    pcm, clipped = quantize(samples.astype(np.float64), bits)
    if clipped:
        raise ValueError("unexpected quantizer clipping")
    wrappers = {}
    for extension in ("wav", "flac"):
        path = folder / f"fixture-{rate}-{bits}.{extension}"
        codec.from_pcm(pcm, path, rate, bits, flac=extension == "flac")
        if codec.decode(path, bits) != pcm:
            raise ValueError("FFmpeg decoded different PCM")
        with sf.SoundFile(path) as stream:
            if (stream.frames, stream.channels, stream.samplerate, stream.subtype) != (
                    len(samples), 2, rate, f"PCM_{bits}"):
                raise ValueError("incorrect wrapped PCM format")
            # libsndfile left-aligns both supported depths in the int32 result.
            expected = np.rint(samples.astype(np.float64) * 2**(bits - 1)).astype(np.int32)
            if not np.array_equal(stream.read(dtype="int32") >> (32 - bits), expected):
                raise ValueError("libsndfile sample readback mismatch")
        wrappers[extension] = codec.sha(path)
    return dict(bits=bits, pcm_sha256=hashlib.sha256(pcm).hexdigest(), wrappers=wrappers)


def check_rate(package, folder, rate):
    samples, receipt = render(package, rate, SEED)
    replay, repeat_receipt = render(package, rate, SEED)
    if repeat_receipt != receipt or samples.tobytes() != replay.tobytes():
        raise ValueError("fresh-process same-seed replay differed")
    different, other_receipt = render(package, rate, SEED + 1)
    sections = []
    for index, name in enumerate(receipt["timbres"]):
        section = slice(index * 4 * rate, (index + 1) * 4 * rate)
        a, b = samples[section], different[section]
        rms = float(np.sqrt(np.mean(a.astype(np.float64)**2)))
        changes = int(np.count_nonzero(np.any(a != b, axis=1)))
        if rms == 0 or (name == "chip" and changes) or (name == "noise" and not changes):
            raise ValueError(f"unexpected seed control or inactive section for {name}")
        sections.append(dict(instrument=name, rms=rms, changed_frames_with_other_seed=changes))
    return dict(render=receipt, alternate_seed_render=other_receipt, sections=sections,
                files=[check_files(samples, folder, rate, bits) for bits in (16, 24)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path, help="a new output directory")
    args = parser.parse_args()
    args.output.mkdir()
    results = [check_rate(args.package, args.output, rate) for rate in (44100, 48000)]
    report = dict(scope="single generated score, no model use", same_seed_byte_replay=True,
                  numpy=np.__version__, soundfile=sf.__version__, libsndfile=sf.__libsndfile_version__,
                  ffmpeg=codec.run([codec.FFMPEG, "-version"]).decode().splitlines()[0],
                  code_sha256={p.name: codec.sha(p) for p in (
                      WORKER, Path(__file__), Path(codec.__file__),
                      Path(__file__).with_name("music_library_pilot_nuisance.py"))},
                  results=results)
    codec.save(args.output / "render-check.json", report)


if __name__ == "__main__":
    main()
