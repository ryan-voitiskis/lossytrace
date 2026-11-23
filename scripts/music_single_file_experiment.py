"""Run the fixed November synthetic single-file experiment offline."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import torch
from torch.nn import functional as F

import music_library_pilot_convert as codec
from music_library_pilot_cnn_recipes import STATES, cnn_scores, fit_cnn, load_inputs
from music_library_pilot_synthesis import write_wav
from music_verdict_candidate import frontend

RECIPES = ("detuned_saw", "fm_reed", "pulse_lead", "mallet", "vibrato_strings", "noise_resonator")
STARTS = (0, 5, 10, 16, 22, 28)
PILOT = Path(".tmp/music-verdict-v1")
PLAN = Path("research/music-library-pilot-v1/single-file-plan-20261123.md")


def voice(recipe, freq, t, bright, rng, rate):
    phase = 2 * np.pi * t * freq
    harmonics = range(1, 14 if bright else 4)
    if recipe == "detuned_saw":
        return sum((np.sin(h*phase) + np.sin(h*phase*1.004))/h for h in harmonics)
    if recipe == "fm_reed":
        return np.sin(phase + (3.7 if bright else .7)*np.sin(2*phase + .3*np.sin(phase)))
    if recipe == "pulse_lead":
        return sum(np.sin(h*np.pi*.31)*np.cos(h*phase)/h for h in harmonics)
    if recipe == "mallet":
        return sum(np.sin(r*phase)*np.exp(-t*r*.6)/r**(.5 if bright else 2)
                   for r in (1, 2.76, 5.4, 8.93))
    if recipe == "vibrato_strings":
        mod = phase + .12*np.sin(2*np.pi*5.5*t)
        return sum(np.sin(h*mod)/h**(.9 if bright else 2) for h in harmonics)
    if recipe == "noise_resonator":
        bins = np.fft.rfftfreq(len(t), 1/rate)
        response = sum(np.exp(-.5*((bins - h*freq)/(8+2*h))**2)/h for h in harmonics)
        return np.fft.irfft(np.fft.rfft(rng.normal(size=len(t)))*response, n=len(t))
    raise ValueError(recipe)


def render(recipe, cell):
    rng = np.random.default_rng(20261123 + 100*RECIPES.index(recipe) + cell)
    rate = (44100, 48000)[cell.bit_count() % 2]
    attack, sustain, bright, dense = [bool(cell & (1 << b)) for b in range(4)]
    duration = 1.45 if sustain else .36
    t = np.arange(round(rate*duration))/rate
    envelope = np.minimum(1, t/(.12 if attack else .003)) * np.exp(-2*t/duration)
    envelope *= np.minimum(1, (duration-t)/.04)
    mix = np.zeros((32*rate, 2))
    root = int(rng.integers(47, 58))
    for k, start in enumerate(np.arange(.08, 32, .22 if dense else .66)):
        midi = root + (0, 5, 7, 3)[int(start//4)%4] + rng.choice((0, 3, 7, 12, 15))
        if k % 4 == 0:
            midi -= 12
        signal = voice(recipe, 440*2**((midi-69)/12), t, bright, rng, rate)*envelope
        pan = rng.uniform(.15, 1.42)
        first = round(start*rate)
        dest = mix[first:first+len(t)]
        dest += signal[:len(dest), None]*np.array([np.cos(pan), np.sin(pan)])
    mix[-rate//5:] *= np.linspace(1, 0, rate//5)[:, None]
    return rate, np.rint(mix * (24575 / np.max(np.abs(mix)))).astype("<i2")


def features(raw, rate):
    pcm = np.frombuffer(raw, dtype="<i2").reshape(-1, 2)
    if len(pcm) != 32*rate:
        raise ValueError("unexpected PCM length")
    clips = np.stack([pcm[s*rate:(s+4)*rate].T for s in STARTS])
    return F.adaptive_avg_pool2d(frontend(torch.from_numpy(clips).float()/32768, rate), (128, 32))


def construct(job):
    root, recipe, cell = job
    folder = root / recipe / str(cell)
    folder.mkdir(parents=True)
    rate, pcm = render(recipe, cell)
    baseline = folder / "baseline.wav"
    write_wav(baseline, pcm, rate)
    raw = pcm.tobytes()
    if codec.decode(baseline, 16) != raw:
        raise ValueError("baseline readback mismatch")
    records = []
    for state in STATES:
        path = baseline
        padding = 0
        if state != "baseline":
            family, bitrate = state.split("-")
            path = folder / (state + (".mp3" if family == "mp3" else ".m4a"))
            codec.encode(baseline, path, family, int(bitrate))
            codec.validate_stream(path, rate, family)
            raw, padding = codec.trim(codec.decode(path, 16), 16, len(pcm))
        records.append(dict(state=state, file=path.name, file_hash=codec.sha(path),
                            pcm_hash=hashlib.sha256(raw).hexdigest(), trimmed_frames=padding))
    codec.save(folder / "inputs.json", dict(rate=rate, records=records))
    return folder, rate, records


def make_scores(root, recipes, models):
    rows = []
    jobs = [(root, recipe, cell) for recipe in recipes for cell in range(16)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for folder, rate, records in pool.map(construct, jobs):
            for rec in records:
                path = folder/rec["file"]
                raw, padding = codec.trim(codec.decode(path, 16), 16, 32*rate)
                if padding != rec["trimmed_frames"] or hashlib.sha256(raw).hexdigest() != rec["pcm_hash"]:
                    raise ValueError("codec readback mismatch")
                x = features(raw, rate)
                with torch.inference_mode():
                    scores = {k: m(x).double().mean().item() for k, m in models.items()}
                rows.append(dict(recipe=folder.parent.name, cell=int(folder.name), state=rec["state"], **scores))
            if folder.name == "15":
                print("Scored", folder.parent.name, flush=True)
    return rows


def thresholds(rows, model):
    hi = max(r[model] for r in rows if r["state"] == "baseline")
    lo = float(np.quantile([r[model] for r in rows if r["state"] != "baseline"], .05, method="lower"))
    if lo > hi:
        lo = hi = (lo+hi)/2
    return dict(lower=lo, upper=hi)


def summarize(rows, model, limits):
    cells = {s: dict(flag=0, no_evidence=0, abstain=0) for s in STATES}
    for row in rows:
        score = row[model]
        decision = "flag" if score > limits["upper"] else "no_evidence" if score < limits["lower"] else "abstain"
        cells[row["state"]][decision] += 1
    clean = cells["baseline"]
    n = sum(clean.values())
    encoded = [cells[s] for s in STATES[1:]]
    if not n or any(sum(v.values()) != n for v in encoded):
        raise ValueError("incomplete case matrix")
    return dict(by_state=cells, clean_false_alerts=clean["flag"], clean_sources=n,
                detection=sum(v["flag"] for v in encoded)/(6*n),
                balanced_coverage=1-(clean["abstain"]/n + sum(v["abstain"] for v in encoded)/(6*n))/2)


def run(root, output):
    if not Path("/Volumes/schwarz").is_mount() or root.resolve().parent != Path("/Volumes/schwarz/lossytrace"):
        raise ValueError("new run directory on schwarz required")
    if shutil.disk_usage(root.parent).free < 100*1024**3 or output.exists():
        raise ValueError("insufficient disk reserve or output already exists")
    root.mkdir()
    torch.set_num_threads(3)
    torch.use_deterministic_algorithms(True)
    inputs = (PILOT/"library-variants-20261005-001", PILOT/"library-nuisance-measurements-20261010-001")
    images, _ = load_inputs(*inputs)
    models = {k: fit_cnn(images, range(24), ranking_weight=w) for k,w in (("baseline",0),("ranking",.5))}
    del images
    for k, m in models.items():
        torch.save(m.state_dict(), root/(k+".pt"))
    cal = make_scores(root, RECIPES[:2], models)
    limits = {k: thresholds(cal,k) for k in models}
    codec.save(root/"calibration-scores.json", cal)
    codec.save(root/"locked-thresholds.json", limits)
    test = make_scores(root, RECIPES[2:], models)
    codec.save(root/"evaluation-scores.json", test)
    stats = {k: summarize(test,k,limits[k]) for k in models}
    a,b = stats["baseline"],stats["ranking"]
    win = (b["clean_false_alerts"] < a["clean_false_alerts"] and
           b["detection"] >= max(.5,a["detection"]-.05) and
           b["balanced_coverage"] >= max(.6,a["balanced_coverage"]-.05))
    library,_ = load_inputs(*inputs, origin="library")
    transfer = {}
    for k,m in models.items():
        scores = cnn_scores(m, library, library.keys())
        transfer[k] = {s: sum(scores[i,c] > scores[i,0] for i in range(24)) for c,s in enumerate(STATES) if c}
    codec.save(output, dict(plan_sha256=codec.sha(PLAN), runner_sha256=codec.sha(Path(__file__)),
                            torch_version=torch.__version__, numpy_version=np.__version__,
                            ffmpeg_version=codec.run([codec.FFMPEG,"-version"]).decode().splitlines()[0],
                            thresholds=limits, calibration_cases=len(cal), evaluation_cases=len(test),
                            overall=stats, by_recipe={r:{k:summarize([v for v in test if v["recipe"]==r],k,limits[k])
                            for k in models} for r in RECIPES[2:]}, library_higher_out_of_24=transfer,
                            ranking_met_pilot_criteria=win, evidence_directory=str(root)))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    run(args.root,args.output)
