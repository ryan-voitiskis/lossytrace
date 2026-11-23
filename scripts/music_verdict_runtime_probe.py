"""CPU and file-I/O preflight for the untrained candidate on generated PCM only."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time


RATES = (44_100, 48_000)
DURATION_SECONDS = 300
WARM_REPEATS = 3
THREADS = 4
EXTERNAL = Path("/Volumes/schwarz/lossytrace/validation")
CASES = tuple(itertools.product(RATES, (1, 2), (16, 24)))


def digest(file):
    with file.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def make_pair(folder, rate, channels, bits):
    import numpy as np
    import soundfile as sf

    paths = [folder / f"{rate}-{channels}-{bits}.{fmt}" for fmt in ("wav", "flac")]
    rng = np.random.default_rng(20260927 + rate + channels * 100 + bits)
    pcm_hash = hashlib.sha256()
    t = np.arange(rate, dtype=np.float64)[:, None] / rate
    ratios = np.array([1., 1.003][:channels])
    with sf.SoundFile(paths[0], "w", rate, channels, subtype=f"PCM_{bits}") as wav, \
            sf.SoundFile(paths[1], "w", rate, channels, subtype=f"PCM_{bits}") as flac:
        for second in range(DURATION_SECONDS):
            hz = (110., 146.832, 164.814, 123.471)[(second // 3) % 4]
            phase = (t + second) * (2 * np.pi * hz) * ratios
            signal = (.45 * np.sin(phase) + .12 * np.sin(phase * 3)) * np.exp(-1.5 * t)
            signal += .006 * rng.standard_normal(signal.shape)
            pcm = np.rint(signal * (2 ** (bits - 1) - 1)).astype(np.int32) << (32 - bits)
            pcm_hash.update(pcm.astype("<i4", copy=False).tobytes())
            wav.write(pcm)
            flac.write(pcm)

    result = []
    for path in paths:
        observed = hashlib.sha256()
        with sf.SoundFile(path) as src:
            if (src.frames, src.samplerate, src.channels, src.subtype) != (
                DURATION_SECONDS * rate, rate, channels, f"PCM_{bits}"
            ):
                raise ValueError("generated wrapper metadata mismatch")
            for block in src.blocks(blocksize=rate, dtype="int32", always_2d=True):
                observed.update(block.astype("<i4", copy=False).tobytes())
        if observed.digest() != pcm_hash.digest():
            raise ValueError("generated wrapper PCM mismatch")
        result.append(dict(file=path.name, bytes=path.stat().st_size, file_sha256=digest(path),
                           pcm_sha256=observed.hexdigest()))
    return result


def worker(path, file_sha256):
    import resource
    import numpy as np
    import soundfile as sf
    import torch
    from music_verdict_candidate import analysis_intervals, build_candidate, frontend, mean_window_logit

    torch.set_num_threads(THREADS)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    model = build_candidate().eval()
    for _ in range(1 + WARM_REPEATS):
        start = time.perf_counter()
        observed = digest(path)
        after_hash = time.perf_counter()
        if observed != file_sha256:
            raise ValueError("file commitment mismatch")
        read_seconds = frontend_seconds = model_seconds = 0.
        with torch.inference_mode(), sf.SoundFile(path) as stream:
            intervals = analysis_intervals(stream.frames, stream.samplerate)
            logits = []
            for first, end in intervals:
                before = time.perf_counter()
                stream.seek(first)
                pcm = stream.read(end - first, dtype="float32", always_2d=True)
                tensor = torch.from_numpy(np.ascontiguousarray(pcm.T)).unsqueeze(0)
                after_read = time.perf_counter()
                features = frontend(tensor, stream.samplerate)
                after_frontend = time.perf_counter()
                logits.append(model(features))
                after_model = time.perf_counter()
                read_seconds += after_read - before
                frontend_seconds += after_frontend - after_read
                model_seconds += after_model - after_frontend
            score = mean_window_logit(torch.cat(logits))
        elapsed = time.perf_counter() - start
        print(json.dumps(dict(seconds=elapsed, hash_seconds=after_hash - start,
                              read_seconds=read_seconds, frontend_seconds=frontend_seconds,
                              model_seconds=model_seconds, intervals=intervals, file_logit=score,
                              process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                              torch=torch.__version__, libsndfile=sf.__libsndfile_version__,
                              soundfile=sf.__version__, numpy=np.__version__)), flush=True)


def run(folder):
    if platform.system() != "Darwin" or not EXTERNAL.parents[1].is_mount() or folder.resolve().parent != EXTERNAL:
        raise ValueError("use a new run directory under the mounted schwarz validation directory on macOS")
    if shutil.disk_usage(EXTERNAL).free < 2 * 1024**3:
        raise ValueError("insufficient working space for fixtures")
    folder.mkdir()
    all_cases = []
    for rate, channels, bits in CASES:
        pair = make_pair(folder, rate, channels, bits)
        pair_score = None
        for fixture in pair:
            path = folder / fixture["file"]
            command = [sys.executable, "-B", __file__, "--worker", str(path), fixture["file_sha256"]]
            start = time.perf_counter()
            with subprocess.Popen(command, stdout=subprocess.PIPE, text=True) as child:
                first = child.stdout.readline()
                cold_seconds = time.perf_counter() - start
                remaining = list(child.stdout)
                if child.wait() or not first or len(remaining) != WARM_REPEATS:
                    raise RuntimeError(f"fixture worker failed for {path.name}")
            runs = [json.loads(line) for line in [first, *remaining]]
            score = runs[0]["file_logit"]
            if any(r["file_logit"] != score or r["intervals"] != runs[0]["intervals"] for r in runs):
                raise ValueError("repeatability failure")
            if pair_score is not None and pair_score != score:
                raise ValueError("equal-PCM wrapper disagreement")
            if len(runs[0]["intervals"]) != 24 or digest(path) != fixture["file_sha256"]:
                raise ValueError("incomplete interval coverage or modified input")
            pair_score = score
            record = dict(fixture=fixture, cold_to_first_result_seconds=cold_seconds, runs=runs)
            all_cases.append(record)
            save(folder / (path.name + ".json"), record)
            print(path.name, "warm median", round(statistics.median(r["seconds"] for r in runs[1:]), 3), flush=True)

    warm = [r for case in all_cases for r in case["runs"][1:]]
    measured = sorted(r["seconds"] for r in warm)
    summary = {
        "scope": "generated five-minute PCM only, deterministic untrained CNN, CPU, one window at a time",
        "processor": subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip(),
        "platform": platform.platform(), "python": platform.python_version(),
        "versions": {k: warm[0][k] for k in ("torch", "libsndfile", "soundfile", "numpy")},
        "intraop_threads": THREADS, "interop_threads": 1,
        "wrapper_pairs": len(CASES), "warm_count": len(warm), "warm_median_s": statistics.median(measured),
        "warm_nearest_rank_p95_s": measured[math.ceil(.95 * len(measured)) - 1],
        "largest_fresh_process_to_first_result_s": max(c["cold_to_first_result_seconds"] for c in all_cases),
        "peak_worker_rss_bytes": max(r["process_peak_rss_bytes"] for c in all_cases for r in c["runs"]),
        "warm_stage_median_s": {k: statistics.median(r[k] for r in warm)
                                for k in ("hash_seconds", "read_seconds", "frontend_seconds", "model_seconds")},
        "source_sha256": {n: digest(Path(__file__).with_name(n)) for n in
                          ("music_verdict_runtime_probe.py", "music_verdict_candidate.py")},
        "wrapper_equal_scores_and_pcm": True, "exact_repeats": True, "input_hashes_preserved": True,
    }
    save(folder / "summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("file_sha256", nargs="?")
    args = parser.parse_args()
    if args.worker:
        worker(args.output, args.file_sha256)
    else:
        run(args.output)
