"""Exercise one full case matrix per split on newly generated signals only."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import resource
import shutil
import sys
import time

import numpy as np
import torch

import music_library_pilot_convert as codec
from music_library_pilot_nuisance import process, quantize
from music_verdict_calibration import CASES, CONDITIONS, STATES
from music_verdict_candidate import analysis_intervals, build_candidate
from music_verdict_pcm_inputs import FileQuartet, PCMCase
from music_verdict_training import fit_core


def construct(root, partition, rate, bits, seed):
    folder = root / partition
    folder.mkdir()
    frames = 30 * rate
    rng = np.random.default_rng(seed)
    t = np.arange(frames, dtype=np.float64) / rate
    phase = t * (180. if partition == "train" else 337.)
    wave = .16 * np.sin(2 * np.pi * (phase + np.sin(phase * .17)))
    samples = np.stack((wave, np.roll(wave, 8)), axis=1) + .003 * rng.normal(size=(frames, 2))
    raw, _ = quantize(samples, bits)
    original = folder / "source.wav"
    codec.from_pcm(raw, original, rate, bits)
    products = {}
    encoded_files = {}
    for state in STATES:
        pcm = raw
        if state != "baseline":
            family, kbps = state.split("-")
            path = folder / (state + (".mp3" if family == "mp3" else ".m4a"))
            codec.encode(original, path, family, int(kbps))
            codec.validate_stream(path, rate, family)
            pcm, tail = codec.trim(codec.decode(path, bits), bits, frames)
            encoded_files[state] = dict(name=path.name, sha256=codec.sha(path), trailing_frames_removed=tail)
        for condition in CONDITIONS:
            audio, output_bits, _ = process(pcm, bits, rate, condition, seed)
            path = folder / f"{state}-{condition}.flac"
            codec.from_pcm(audio, path, rate, output_bits, flac=True)
            if codec.decode(path, output_bits) != audio:
                raise ValueError("generated PCM readback mismatch")
            products[state, condition] = PCMCase(
                partition, partition, partition, state, condition, path, codec.sha(path),
                rate, 2, output_bits, frames,
            )
    receipt = [asdict(case) | {"path": case.path.name} for case in products.values()]
    codec.save(folder / "construction.json", dict(source_sha256=codec.sha(original),
                                                  encoded_files=encoded_files, cases=receipt))
    return products


def run(root):
    drive = Path("/Volumes/schwarz")
    if (platform.system() != "Darwin" or not drive.is_mount()
            or root.resolve().parent != drive / "lossytrace/validation"
            or shutil.disk_usage(drive).free < 2 * 1024**3):
        raise ValueError("a new run directory on mounted schwarz with fixture headroom is required")
    root.mkdir()
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    train = construct(root, "train", 48000, 24, 20261124)
    selection = construct(root, "selection", 44100, 16, 20261125)
    if set(train) != set(CASES) or set(selection) != set(CASES):
        raise ValueError("incomplete generated matrix")
    crops = analysis_intervals(30 * 48000, 48000)
    quartets = []
    for state in STATES[1:]:
        for condition in CONDITIONS:
            first, _ = crops[len(quartets) % len(crops)]
            quartets.append(FileQuartet(train["baseline", "identity"], train[state, "identity"],
                                        train["baseline", condition], train[state, condition], first))
    files = [case.selection_file() for case in selection.values()]
    model = build_candidate()
    initial = {k: v.clone() for k, v in model.state_dict().items()}
    print("Construction verified. Running one synthetic epoch.", flush=True)
    started = time.perf_counter()
    fit = fit_core(model, quartets, files, epochs=1)
    elapsed = time.perf_counter() - started
    if fit["optimizer_steps"] != 3 or fit["selected_epoch"] != 1:
        raise ValueError("unexpected optimizer or selection accounting")
    if not any(not torch.equal(v, initial[k]) for k, v in model.state_dict().items()):
        raise ValueError("expected a synthetic optimizer update")
    for case in (*train.values(), *selection.values()):
        if codec.sha(case.path) != case.sha256:
            raise ValueError("generated input changed")
    summary = dict(
        scope="one synthetic mechanics epoch; no scientific model or public verdict",
        python=platform.python_version(), torch=torch.__version__, platform=platform.platform(),
        ffmpeg=codec.run([codec.FFMPEG, "-version"]).decode().splitlines()[0],
        train_files=len(train), selection_files=len(files), train_quartets=len(quartets),
        selection_windows=sum(len(s.windows) for s in files), selected_epoch=fit["selected_epoch"],
        optimizer_steps=fit["optimizer_steps"], last_accumulation_quartets=fit["history"][0]["last_accumulation_quartets"],
        fit_seconds=elapsed, peak_process_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        input_hashes_preserved=True, checkpoint_saved=False, intraop_threads=4, interop_threads=1,
        construction_sha256={p: codec.sha(root / p / "construction.json") for p in ("train", "selection")},
        code_sha256={name: codec.sha(Path(__file__).with_name(name)) for name in (
            "music_verdict_streaming_smoke.py", "music_verdict_pcm_inputs.py", "music_verdict_training.py",
            "music_verdict_candidate.py", "music_verdict_calibration.py",
            "music_library_pilot_convert.py", "music_library_pilot_nuisance.py")},
    )
    codec.save(root / "smoke.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    run(Path(sys.argv[1]))
