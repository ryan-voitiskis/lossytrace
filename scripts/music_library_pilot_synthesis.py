#!/usr/bin/env python3
"""Controlled procedural music for exploratory codec-history work, not validation.

No sampled audio, plugins, network, learned generators or external assets.
Four shared synthesis families x six fixed seeds are not 24 independent studios.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import wave

import numpy as np

SEED = 20261005
COUNT = 24
DURATION = 120
FAMILIES = ('plucked_harmony', 'rhythmic_synth', 'sparse_bells', 'percussive_texture')
TEMPOS = (80, 96, 112, 128, 144, 160)
SCALE = (0, 2, 3, 5, 7, 8, 10)


def parameters(index):
    if type(index) is not int or not 0 <= index < COUNT:
        raise ValueError('index must be an integer in [0, 24)')
    return {'index': index, 'seed': SEED + index, 'family': FAMILIES[index // 6],
            'family_index': index // 6, 'bpm': TEMPOS[index % 6],
            'sample_rate': 44100 if index % 2 == 0 else 48000,
            'root_midi': 45 + index % 12,
            'peak_target': 0.65 * (10 ** (-24 / 20) if index % 6 == 5 else 1.0)}


def render(index, duration=DURATION):
    p = parameters(index)
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration) or not 0 < duration <= DURATION:
        raise ValueError('duration must be finite, positive and at most 120 seconds')
    sr = p['sample_rate']
    total = round(duration * sr)
    if total < 4:
        raise ValueError('at least four samples required')
    rng = np.random.Generator(np.random.PCG64(p['seed']))
    audio = np.zeros((total, 2), dtype=np.float64)
    beat = 60.0 / p['bpm']
    family = p['family_index']

    def event(start, length, midi, level, pan, kind):
        first = round(start * sr)
        if first >= total:
            return
        n = min(round(length * sr), total - first)
        t = np.arange(n, dtype=np.float64) / sr
        frequency = 440.0 * 2 ** ((midi - 69) / 12)
        if kind == 'kick':
            signal = np.sin(2*np.pi*(40*t + 4*(1-np.exp(-t/0.05)))) * np.exp(-t/0.12)
        elif kind == 'noise':
            noise = rng.standard_normal(n)
            signal = (noise - np.r_[0.0, noise[:-1]]) * np.exp(-t/0.06) * 0.18
        elif kind == 'bell':
            signal = sum(np.sin(2*np.pi*frequency*ratio*t) * np.exp(-t/(0.2 + 1.5/ratio))/ratio
                         for ratio in (1.0, 2.01, 3.97, 5.43) if frequency*ratio < 0.45*sr)
        else:
            harmonics = range(1, 13 if kind == 'bright' else 7)
            signal = sum(np.sin(2*np.pi*frequency*h*t) * np.exp(-t*(1.5 + 0.4*h))/h**1.4
                         for h in harmonics if frequency*h < 0.45*sr)
        ramp = min(round(0.005*sr), n//2)
        envelope = np.ones(n)
        if ramp:
            envelope[:ramp] = np.linspace(0, 1, ramp)
            envelope[-ramp:] = np.linspace(1, 0, ramp)
        signal = signal * envelope * level
        angle = (pan+1)*np.pi/4
        audio[first:first+n, 0] += signal * np.cos(angle)
        audio[first:first+n, 1] += signal * np.sin(angle)

    # A/B sections alternate every eight bars. Ending is faded, not padded.
    for b in range(math.ceil(duration / beat)):
        time = b * beat
        section = (b // 32) % 2
        chord = (0, 5, 3, 7)[(b//8) % 4]
        base = p['root_midi'] + chord
        if family != 2 and b % 2 == 0:
            event(time, 0.4, 36, 0.35, 0, 'kick')
        if family in (1, 3):
            event(time+beat/2, 0.22, 60, 0.2, (-1)**b*0.7, 'noise')
        if b % (4 if family == 2 else 2) == 0:
            event(time, min(3*beat, 2.5), base-12, 0.22, -0.15, 'soft')
        if family in (0, 1) and b % 4 == 0:
            for n, semitone in enumerate((0, 3, 7)):
                event(time+n*0.025, 3*beat, base+semitone+12, 0.13, (n-1)*0.55, 'soft')
        if family != 2 or b % 3 == 0:
            degree = int(rng.integers(0, len(SCALE)))
            midi = p['root_midi'] + 24 + SCALE[degree] + (12 if section else 0)
            kind = 'bell' if family in (0, 2) else 'bright'
            event(time + (beat/2 if family == 3 else 0), 1.8*beat, midi,
                  0.16 if family != 2 else 0.3, float(rng.uniform(-0.8, 0.8)), kind)
    fade = min(sr, total//2)
    audio[:fade] *= np.linspace(0, 1, fade)[:, None]
    audio[-fade:] *= np.linspace(1, 0, fade)[:, None]
    peak = float(np.max(np.abs(audio)))
    if not np.isfinite(audio).all() or peak <= 0:
        raise ValueError('invalid synthesis')
    audio *= p['peak_target'] / peak
    pcm = np.rint(audio * 32767).astype('<i2')
    return pcm, p


def write_wav(path, pcm, sr):
    if pcm.dtype != np.dtype('<i2') or pcm.ndim != 2 or pcm.shape[1] != 2:
        raise ValueError('stereo signed 16-bit PCM required')
    with path.open('xb') as raw:
        with wave.open(raw, 'wb') as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(sr)
            output.writeframes(pcm.tobytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan_bytes = args.plan.read_bytes()
    plan = json.loads(plan_bytes)
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if plan['synthesis']['script_sha256'] != script_hash:
        raise ValueError('generator does not match frozen plan')
    if np.__version__ != plan['synthesis']['numpy_version']:
        raise ValueError('NumPy does not match plan')
    if sys.version.split()[0] != plan['synthesis']['python_version']:
        raise ValueError('Python does not match plan')
    allowed = Path('.tmp/music-verdict-v1').resolve()
    if not args.output.resolve().is_relative_to(allowed):
        raise ValueError('output must be inside ignored pilot storage')
    required = COUNT * 48000 * DURATION * 4
    if shutil.disk_usage(allowed).free - required < 100 * 1024**3:
        raise ValueError('insufficient reserved free space')
    args.output.mkdir(exist_ok=False)
    records = []
    for index in range(COUNT):
        pcm, params = render(index)
        filename = f'synthetic-{index:02}.wav'
        path = args.output / filename
        write_wav(path, pcm, params['sample_rate'])
        with wave.open(str(path), 'rb') as actual:
            assert actual.getnframes() == DURATION * params['sample_rate']
            assert actual.readframes(actual.getnframes()) == pcm.tobytes()
        records.append({'file': filename, 'parameters': params,
                        'history_label': 'controlled_synthesis_no_lossy_stage',
                        'frames': len(pcm), 'channels': 2, 'bits_per_sample': 16,
                        'pcm_sha256': hashlib.sha256(pcm.tobytes()).hexdigest(),
                        'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        print(json.dumps({'generated': len(records), 'target': COUNT}), flush=True)
    manifest = {'schema_version': 1, 'study_id': 'music-library-pilot-v1',
                'plan_sha256': hashlib.sha256(plan_bytes).hexdigest(),
                'generator_sha256': script_hash, 'records': records,
                'scientific_independence_claim': False, 'model_scores_generated': False}
    with (args.output/'manifest.json').open('x') as f:
        json.dump(manifest, f, indent=2)
        f.write('\n')


if __name__ == '__main__':
    main()
