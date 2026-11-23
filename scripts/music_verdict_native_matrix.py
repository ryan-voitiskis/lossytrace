"""Offline construction/readback of known synthetic mono sources on non-integral-second grids."""
import argparse
from collections import Counter
from dataclasses import fields
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf
import torch

import music_library_pilot_convert as codec
from music_library_pilot_nuisance import filter_chain, pcm_samples, quantize
from music_verdict_beepbox_authored import local_lag
from music_verdict_calibration import CASES
from music_verdict_construction import construct_primary
from music_verdict_pcm_inputs import FileQuartet, PCMCase


def make_source(path, rate, bits):
    extra = 1 if rate == 44100 else 123
    t = np.arange(30 * rate + extra, dtype=np.float64) / rate
    rng = np.random.default_rng(20261124 + rate + bits)
    signal = (.24 * np.sin(2 * np.pi * (135 * t + 13 * t**2)) + .06 * np.sin(2*np.pi*7193*t)
              + .021 * rng.normal(size=len(t)))[:, None]
    raw, clipped = quantize(signal, bits, channels=1)
    if clipped:
        raise ValueError("fixture clipped")
    codec.from_pcm(raw, path, rate, bits, channels=1)


def readback(folder, original, base_recipe):
    manifest = json.loads((folder / "construction.json").read_bytes())
    records = manifest["cases"]
    if [(r["state"], r["condition"]) for r in records] != list(CASES):
        raise ValueError("case matrix mismatch")
    if manifest["source_sha256"] != codec.sha(original) or manifest["base_file_sha256"] != codec.sha(folder/"base.wav"):
        raise ValueError("input binding mismatch")
    rate = records[0]["rate"]
    with sf.SoundFile(original) as f:
        frames = f.frames
        bits = int(f.subtype[4:])
        direct = f.read(dtype="int32") >> (32 - bits)
    with sf.SoundFile(folder / "base.wav") as f:
        base = f.read(dtype="int32") >> (32 - bits)
    expected = direct if base_recipe == "identity" else np.rint(direct * 10**(-6/20)).astype(np.int32)
    if not np.array_equal(base, expected):
        raise ValueError("pre-encode gain or direct PCM changed")
    data = {}
    trim_counts = []
    worst_lag = 0
    identity_samples = None
    checked_offsets = 0
    for r in records:
        path = folder / r["path"]
        with sf.SoundFile(path) as f:
            if (f.frames, f.channels, f.samplerate, f.subtype) != (frames, 1, rate, f"PCM_{r['bits']}"):
                raise ValueError("independent format readback failed")
            decoded = f.read(dtype="int32") >> (32 - r["bits"])
        raw = codec.decode(path, r["bits"])
        integer = np.ldexp(pcm_samples(raw, r["bits"], channels=1)[:, 0], r["bits"]-1)
        if (not np.array_equal(integer, decoded) or codec.sha(path) != r["sha256"]
                or hashlib.sha256(raw).hexdigest() != r["pcm_sha256"]):
            raise ValueError("sample-by-sample readback failed")
        if r["condition"] == "identity":
            identity_samples = decoded
            if r["state"] == "baseline":
                if not np.array_equal(decoded, base):
                    raise ValueError("identity baseline differs from encoder input")
            else:
                for start in (rate, frames//2, frames-rate):
                    peak = local_lag(base, decoded, start)
                    worst_lag = max(worst_lag, abs(peak["lag_frames"]))
                    checked_offsets += 1
        if r["condition"] == "gain":
            if not np.array_equal(decoded, np.rint(identity_samples * 10**(-6/20))):
                raise ValueError("post-encode gain differs from sample-domain reference")
        if r["condition"] == "resample":
            for start in (rate, frames//2, frames-rate):
                peak = local_lag(identity_samples, decoded, start)
                worst_lag = max(worst_lag, abs(peak["lag_frames"]))
                checked_offsets += 1
            trim_counts.append(r["processing"]["trailing_resampler_frames_removed"])
        case = PCMCase(**{f.name: (path if f.name == "path" else r[f.name]) for f in fields(PCMCase)})
        data[r["state"],r["condition"]] = case
    quartet = FileQuartet(data["baseline","identity"], data["aac-256","identity"],
                          data["baseline","lowpass16k"], data["aac-256","lowpass16k"], rate)
    features = quartet.features
    if features.shape[:2] != (4, 3) or torch.count_nonzero(features[:,1]) or worst_lag:
        raise ValueError("unexpected mono side channel or alignment shift")
    return dict(rate=rate, bits=bits, frames=frames, precondition=base_recipe, cases=len(records),
                alignment_checks=checked_offsets, worst_absolute_lag_frames=worst_lag,
                resampling_tail_frames=sorted(set(trim_counts)),
                base_pcm_sha256=manifest["base_pcm_sha256"], manifest_sha256=codec.sha(folder/"construction.json"),
                packet_kbps={k:round(v["mean_packet_bits_per_second"]/1000, 2)
                             for k,v in manifest["encodes"].items()})


def resampling_rounding(rate, period):
    counts = Counter()
    for extra in range(period):
        frames = rate + extra
        raw = codec.ff(["-f", "f64le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0",
                        "-af", filter_chain("resample", rate), "-c:a", "pcm_f64le",
                        "-f", "f64le", "pipe:1"], bytes(8 * frames))
        counts[len(raw) // 8 - frames] += 1
    if not set(counts) <= {0, 1, 2}:
        raise ValueError("unexpected resampler endpoint rounding")
    return dict(sorted(counts.items()))


def run(out):
    drive = Path("/Volumes/schwarz")
    if (not drive.is_mount() or out.resolve().parent != drive/"lossytrace/validation"
            or shutil.disk_usage(drive).free < 3*1024**3):
        raise ValueError("expected a fresh schwarz run directory with fixture headroom")
    out.mkdir()
    torch.set_num_threads(2)
    results = []
    for rate in (44100, 48000):
        for bits in (16, 24):
            label = f"{rate}-{bits}"
            path = out/(label+".wav")
            make_source(path, rate, bits)
            recipes = ["identity", "gain"] if (rate, bits) == (48000, 24) else ["identity"]
            for recipe in recipes:
                dest = out/(label+"-"+recipe)
                construct_primary(path, codec.sha(path), dest, group=label, source_id=label, partition="train",
                                  seed=20260927, precondition=recipe)
                results.append(readback(dest, path, recipe))
                print(label, recipe, "verified", flush=True)
    codec.save(out/"summary.json", dict(scope="generated mono fixtures only; zero model fits or scores",
               cases=sum(v["cases"] for v in results), results=results,
               rounding_excess_counts={r:resampling_rounding(r, period) for r, period in ((44100,147),(48000,160))},
               ffmpeg=codec.toolchain()["ffmpeg_version"].splitlines()[0],
               libsndfile=sf.__libsndfile_version__, numpy=np.__version__, torch=torch.__version__,
               code_sha256={name:codec.sha(Path(__file__).with_name(name)) for name in (
                   "music_verdict_native_matrix.py","music_verdict_construction.py","music_library_pilot_convert.py",
                   "music_library_pilot_nuisance.py","music_verdict_pcm_inputs.py","music_verdict_beepbox_authored.py")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
