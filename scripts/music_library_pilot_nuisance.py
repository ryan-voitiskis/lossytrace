#!/usr/bin/env python3
"""Matched pilot postprocessing with explicit PCM quantization; no learned scores."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

import music_library_pilot_convert as c
import music_library_pilot_measure as m

CONDITIONS = ('identity', 'gain', 'dither16', 'resample', 'lowpass16k', 'eq_dynamics')
CASES = ('baseline', 'mp3-128', 'mp3-192', 'mp3-320', 'aac-128', 'aac-192', 'aac-256')


def pcm_samples(raw, bits):
    if bits not in (16, 24) or len(raw) % (2*(bits//8)):
        raise ValueError('expected complete stereo 16/24-bit frames')
    if bits == 16:
        values = np.frombuffer(raw, dtype='<i2').astype(np.float64)
    else:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | b[:, 1] << 8 | b[:, 2] << 16
        values = ((v ^ 0x800000)-0x800000).astype(np.float64)
    return (values/2**(bits-1)).reshape(-1, 2)


def quantize(samples, bits, seed=None):
    if bits not in (16, 24) or samples.ndim != 2 or samples.shape[1] != 2 or not np.isfinite(samples).all():
        raise ValueError('expected finite stereo samples and supported depth')
    limit = 2**(bits-1)
    scaled = samples*limit
    if seed is not None:
        rng = np.random.Generator(np.random.PCG64(seed))
        scaled = scaled + rng.random(samples.shape)-rng.random(samples.shape)
    rounded = np.rint(scaled)
    clipped = int(np.count_nonzero((rounded < -limit) | (rounded > limit-1)))
    values = np.clip(rounded, -limit, limit-1).astype('<i4')
    raw = (values.astype('<i2').tobytes() if bits == 16 else
           values.view(np.uint8).reshape(-1, 4)[:, :3].copy().tobytes())
    return raw, clipped


def filter_chain(condition, rate):
    if rate not in (44100, 48000) or condition not in CONDITIONS:
        raise ValueError('unplanned rate or processing condition')
    if condition in ('identity', 'dither16'):
        return 'anull'
    if condition == 'gain':
        return 'volume=-6dB:precision=double'
    if condition == 'resample':
        other = 48000 if rate == 44100 else 44100
        options = ':resampler=swr:filter_size=64:phase_shift=10:linear_interp=0:exact_rational=1:cutoff=0.97:filter_type=kaiser:kaiser_beta=9:osf=dbl:tsf=dblp:dither_method=0'
        return f'aresample={other}{options},aresample={rate}{options}'
    if condition == 'lowpass16k':
        return 'lowpass=f=16000:p=2:t=q:w=0.7071067811865476:a=di:r=f64:n=0:b=0'
    return ('equalizer=f=1000:t=q:w=1:g=-3:a=di:r=f64:n=0:b=0,'
            'acompressor=level_in=1:mode=downward:threshold=0.125:ratio=2:attack=20:release=250:'
            'makeup=1:knee=2.8284271247461903:link=average:detection=rms:level_sc=1:mix=1')


def process(raw, bits, rate, condition, seed):
    samples = pcm_samples(raw, bits)
    chain = filter_chain(condition, rate)
    rendered = c.ff(['-f', 'f64le', '-ar', str(rate), '-ac', '2', '-i', 'pipe:0',
                     '-af', chain, '-threads', '1', '-c:a', 'pcm_f64le', '-f', 'f64le', 'pipe:1'],
                    samples.astype('<f8').tobytes())
    if len(rendered) != len(samples)*2*8:
        raise ValueError('processing changed frame count; never silently crop or pad')
    result = np.frombuffer(rendered, dtype='<f8').reshape(-1, 2)
    out_bits = 16 if condition == 'dither16' else bits
    output, clipped = quantize(result, out_bits, seed if condition == 'dither16' else None)
    if condition == 'identity' and output != raw:
        raise ValueError('uniform identity path changed PCM')
    return output, out_bits, {'filter': chain, 'clipped_channel_samples': clipped,
                             'peak_before_quantization': float(np.max(np.abs(result)))}


def smoke(output):
    c.storage_guard(); c.private_output(output)
    binding = c.toolchain()
    rows = []
    for rate in (44100, 48000):
        for bits in (16, 24):
            n = 3*rate; t = np.arange(n)/rate
            samples = np.column_stack((0.15*np.sin(2*np.pi*1000*t), 0.1*np.sin(2*np.pi*18000*t)))
            raw, _ = quantize(samples, bits)
            for condition in CONDITIONS:
                a, depth, info = process(raw, bits, rate, condition, 20261010)
                b, depth2, _ = process(raw, bits, rate, condition, 20261010)
                if a != b or depth != depth2 or len(a) != n*2*(depth//8):
                    raise ValueError('nonrepeatable processing')
                after = pcm_samples(a, depth)
                rms_ratio = np.sqrt(np.mean(after[rate:]**2, axis=0))/np.sqrt(np.mean(pcm_samples(raw, bits)[rate:]**2, axis=0))
                if condition == 'gain' and not np.allclose(rms_ratio, 10**(-6/20), atol=0.001):
                    raise ValueError('gain amplitude check failed')
                if condition == 'lowpass16k' and not rms_ratio[1] < 0.6:
                    raise ValueError('lowpass high-frequency attenuation check failed')
                rows.append({'rate': rate, 'input_bits': bits, 'condition': condition,
                             'output_bits': depth, 'pcm_sha256': hashlib.sha256(a).hexdigest(),
                             'rms_ratio': rms_ratio.tolist(), **info})
            # Alignment probe separate from phase-distorting IIR filters.
            impulse = np.zeros((n, 2)); point = rate; impulse[point] = 0.5
            raw, _ = quantize(impulse, bits)
            processed, depth, _ = process(raw, bits, rate, 'resample', 20261010)
            peak = np.argmax(np.abs(pcm_samples(processed, depth)), axis=0)
            if not np.all(peak == point):
                raise ValueError('resampling time-origin check failed')
    c.verify_toolchain(binding)
    c.save(output/'smoke.json', {'passed': True, 'cases': rows, 'runner_sha256': c.sha(Path(__file__)),
                                'resample_impulse_offsets_samples': [0]*8,
                                'toolchain': binding, 'python': sys.version, 'numpy': np.__version__})
    print(json.dumps({'smoke_cases': len(rows), 'passed': True}))


def verify_plan(plan):
    for item in plan['bound_files']:
        if c.sha(item['path']) != item['sha256']:
            raise ValueError('bound artifact changed')
    if c.sha(Path(__file__)) != plan['runner_sha256']:
        raise ValueError('runner changed')
    if sys.version.split()[0] != plan['python_version'] or np.__version__ != plan['numpy_version']:
        raise ValueError('numeric runtime changed')
    smoke_record = json.loads(Path(plan['smoke']).read_text())
    if not smoke_record['passed'] or smoke_record['runner_sha256'] != plan['runner_sha256']:
        raise ValueError('matching smoke required')
    c.verify_toolchain(smoke_record['toolchain'])


def run(plan_path, output):
    plan_hash = c.sha(plan_path); plan = json.loads(plan_path.read_text()); verify_plan(plan)
    root = Path(plan['input_directory']); previous = Path(plan['previous_measurements'])
    manifest = json.loads((root/'manifest.json').read_text())
    expected_ids = [f'{kind}-{i:02}' for kind in ('library', 'synthetic') for i in range(24)]
    if [s['id'] for s in manifest['sources']] != expected_ids:
        raise ValueError('fixed source matrix mismatch')
    c.storage_guard(); c.private_output(output)
    rows = []
    for source_index, source in enumerate(manifest['sources']):
        directory = root/source['id']; mp = directory/'manifest.json'
        if c.sha(mp) != source['manifest_sha256']:
            raise ValueError('source manifest changed')
        metadata = json.loads(mp.read_text()); rate = metadata['source']['rate']; bits = metadata['source']['bits']
        if [case['case'] for case in metadata['cases']] != list(CASES):
            raise ValueError('case matrix changed')
        for case in metadata['cases']:
            name = 'baseline.wav' if case['case'] == 'baseline' else case['decoded_file']
            expected_hash = case['files'][0]['sha256'] if case['case'] == 'baseline' else case['decoded_sha256']
            path = m.contained_file(directory, name)
            if c.sha(path) != expected_hash: raise ValueError('input hash mismatch')
            raw = c.decode(path, bits)
            if len(raw) != rate*120*2*(bits//8) or hashlib.sha256(raw).hexdigest() != case['pcm_sha256']:
                raise ValueError('input PCM mismatch')
            prior = json.loads((previous/f'{source["id"]}-{name}.json').read_text())['report']
            m.check_report(prior, expected_hash, rate)
            for condition in CONDITIONS:
                c.storage_guard(reserve=512*1024**2)
                transformed, depth, processing = process(raw, bits, rate, condition, 20261010+source_index)
                stem = f'{source["id"]}-{case["case"]}-{condition}'
                wav = output/f'{stem}.wav'
                c.from_pcm(transformed, wav, rate, depth)
                if c.decode(wav, depth) != transformed: raise ValueError('output PCM readback mismatch')
                digest = c.sha(wav)
                report = json.loads(subprocess.run([plan['binary'], 'analyze', str(wav), '--max-seconds', '0'],
                                                    check=True, capture_output=True, timeout=180).stdout)
                m.check_report(report, digest, rate)
                if c.sha(wav) != digest or report['source_facts']['declared_bits_per_sample'] != depth:
                    raise ValueError('output changed or wrong bit depth')
                same = report['compression_trace'] == prior['compression_trace'] if condition == 'identity' else None
                if condition == 'identity' and not same: raise ValueError('identity measurements changed')
                keep = source['id'] in ('library-00', 'synthetic-00') and case['case'] in ('baseline', 'mp3-192')
                row = {'source_id': source['id'], 'origin': metadata['source']['origin'],
                       'component': metadata['source']['component'], 'case': case['case'], 'condition': condition,
                       'seed': 20261010+source_index, 'output_bits': depth, 'processing': processing,
                       'pcm_sha256': hashlib.sha256(transformed).hexdigest(), 'wav_sha256': digest,
                       'audio_retained': keep, 'identity_measurements_exact': same, 'report': report}
                c.save(output/f'{stem}.json', row); rows.append(row)
                # Only this freshly generated, successfully read-back scratch WAV.
                # Fixed representative WAVs are retained; inputs are never removed.
                if not keep: wav.unlink()
            if c.sha(path) != expected_hash: raise ValueError('input changed during processing')
        print(json.dumps({'completed_sources': source_index+1, 'reports': len(rows)}), flush=True)
    verify_plan(plan)
    if c.sha(plan_path) != plan_hash: raise ValueError('plan changed during run')
    c.storage_guard(0)
    c.save(output/'summary.json', {'plan_sha256': plan_hash, 'reports': len(rows), **summarize(rows),
                                  'model_fits': 0, 'verdicts_generated': False})


def difference(a, b):
    return None if a is None or b is None else a-b


def summarize(rows):
    indexed = {(r['source_id'], r['case'], r['condition']): r for r in rows}
    sources = sorted({r['source_id'] for r in rows})
    if len(indexed) != len(rows) or len(rows) != len(sources)*len(CASES)*len(CONDITIONS):
        raise ValueError('duplicate or incomplete factorial matrix')
    def value(s, case, condition, feature):
        return indexed[s, case, condition]['report']['compression_trace'][feature]
    strata = {}
    for origin in sorted({r['origin'] for r in rows}):
        group = [s for s in sources if indexed[s, 'baseline', 'identity']['origin'] == origin]
        conditions = {}
        for condition in CONDITIONS:
            baseline = {f: m.paired_summary([value(s, 'baseline', 'identity', f) for s in group],
                                            [value(s, 'baseline', condition, f) for s in group]) for f in m.FEATURES}
            codecs = {}
            for case in CASES[1:]:
                codecs[case] = {}
                for f in m.FEATURES:
                    codec_delta = [difference(value(s, case, condition, f), value(s, 'baseline', condition, f)) for s in group]
                    original_delta = [difference(value(s, case, 'identity', f), value(s, 'baseline', 'identity', f)) for s in group]
                    codecs[case][f] = {'codec_delta': m.paired_summary([value(s, 'baseline', condition, f) for s in group],
                                                                                     [value(s, case, condition, f) for s in group]),
                                       'interaction_delta': m.paired_summary(original_delta, codec_delta)}
            conditions[condition] = {'baseline_processing_delta': baseline, 'codecs': codecs}
        strata[origin] = conditions
    return {'source_count': len(sources), 'identity_feature_objects_exact': sum(r['identity_measurements_exact'] is True for r in rows),
            'retained_wavs': sum(r['audio_retained'] for r in rows),
            'clipping': {cond: {'cases_with_clipping': sum(r['processing']['clipped_channel_samples'] > 0 for r in rows if r['condition'] == cond),
                                'clipped_channel_samples': sum(r['processing']['clipped_channel_samples'] for r in rows if r['condition'] == cond)} for cond in CONDITIONS},
            'strata': strata}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('smoke', 'run'))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--plan', type=Path)
    args = parser.parse_args()
    if args.mode == 'smoke': smoke(args.output)
    elif args.plan is None: parser.error('--plan required')
    else: run(args.plan, args.output)
