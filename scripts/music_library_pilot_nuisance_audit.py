#!/usr/bin/env python3
"""Read back a completed nuisance run and replay its prospectively fixed sample."""
import argparse
import hashlib
import json
from pathlib import Path

import music_library_pilot_convert as c
import music_library_pilot_measure as m
import music_library_pilot_nuisance as n


def expected_keys():
    return {(f'{kind}-{i:02}', case, condition)
            for kind in ('library', 'synthetic') for i in range(24)
            for case in n.CASES for condition in n.CONDITIONS}


def retained_key(key):
    sid, case, _ = key
    return sid in ('library-00', 'synthetic-00') and case in ('baseline', 'mp3-192')


def audit(plan_path, directory, replay_directory):
    plan = json.loads(plan_path.read_text()); n.verify_plan(plan)
    summary_path = directory/'summary.json'
    summary = json.loads(summary_path.read_text())
    if summary['plan_sha256'] != c.sha(plan_path) or summary['reports'] != 2016:
        raise ValueError('matching completed run required')
    keys = expected_keys(); rows = []; hashes = []
    root = Path(plan['input_directory'])
    source_manifest = json.loads((root/'manifest.json').read_text())
    sources = {}
    for source in source_manifest['sources']:
        path = root/source['id']/'manifest.json'
        if c.sha(path) != source['manifest_sha256']: raise ValueError('source manifest changed')
        sources[source['id']] = json.loads(path.read_text())
    for key in sorted(keys):
        sid, case, condition = key
        stem = f'{sid}-{case}-{condition}'
        path = directory/f'{stem}.json'
        row = json.loads(path.read_text())
        if (row['source_id'], row['case'], row['condition']) != key:
            raise ValueError('case identity mismatch')
        source = sources[sid]['source']
        if row['origin'] != source['origin'] or row['component'] != source['component']:
            raise ValueError('source label mismatch')
        if row['output_bits'] != (16 if condition == 'dither16' else source['bits']):
            raise ValueError('output depth mismatch')
        index = int(sid.rsplit('-', 1)[1]) + (24 if sid.startswith('synthetic-') else 0)
        if row['seed'] != 20261010+index or row['processing']['filter'] != n.filter_chain(condition, source['rate']):
            raise ValueError('processing specification mismatch')
        if row['audio_retained'] != retained_key(key): raise ValueError('retention matrix mismatch')
        m.check_report(row['report'], row['wav_sha256'], source['rate'])
        if row['report']['source_facts']['declared_bits_per_sample'] != row['output_bits']:
            raise ValueError('report depth mismatch')
        if condition == 'identity' and row['identity_measurements_exact'] is not True:
            raise ValueError('identity failure')
        if row['audio_retained']:
            wav = directory/f'{stem}.wav'
            if c.sha(wav) != row['wav_sha256'] or hashlib.sha256(c.decode(wav, row['output_bits'])).hexdigest() != row['pcm_sha256']:
                raise ValueError('retained audio mismatch')
        elif (directory/f'{stem}.wav').exists():
            raise ValueError('unexpected retained scratch audio')
        hashes.append({'file': path.name, 'sha256': c.sha(path)}); rows.append(row)
    if any(summary[k] != v for k, v in n.summarize(rows).items()):
        raise ValueError('saved aggregate does not reproduce')
    # All 336 previously constructed inputs, including those not in the replay sample.
    checked = 0
    for sid, metadata in sources.items():
        for case in metadata['cases']:
            name = 'baseline.wav' if case['case'] == 'baseline' else case['decoded_file']
            expected = case['files'][0]['sha256'] if case['case'] == 'baseline' else case['decoded_sha256']
            if c.sha(root/sid/name) != expected: raise ValueError('original derived input changed')
            checked += 1
    c.storage_guard(reserve=512*1024**2); c.private_output(replay_directory)
    replays = []
    for row in rows:
        key = row['source_id'], row['case'], row['condition']
        if not retained_key(key): continue
        sid, case, condition = key; source = sources[sid]['source']
        name = 'baseline.wav' if case == 'baseline' else f'{case}.flac'
        raw = c.decode(root/sid/name, source['bits'])
        transformed, depth, processing = n.process(raw, source['bits'], source['rate'], condition, row['seed'])
        c.storage_guard(reserve=512*1024**2)
        target = replay_directory/f'{sid}-{case}-{condition}.wav'
        c.from_pcm(transformed, target, source['rate'], depth)
        exact = (hashlib.sha256(transformed).hexdigest() == row['pcm_sha256']
                 and c.sha(target) == row['wav_sha256'] and processing == row['processing'])
        replays.append({'file': target.name, 'exact': exact, 'sha256': c.sha(target)})
        print(json.dumps({'sample_replays': len(replays), 'exact': exact}), flush=True)
    n.verify_plan(plan); c.storage_guard(0)
    result = {'plan_sha256': c.sha(plan_path), 'summary_sha256': c.sha(summary_path),
              'audit_runner_sha256': c.sha(Path(__file__)), 'report_hashes': hashes,
              'reports_verified': len(rows), 'input_hashes_preserved': checked,
              'aggregate_recomputed_exactly': True, 'sample_replays': replays,
              'all_replays_exact': all(r['exact'] for r in replays), 'classifier_scores': False}
    c.save(replay_directory/'audit.json', result)
    if len(replays) != 24 or not result['all_replays_exact']:
        raise ValueError('fixed sample replay failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--replay-directory', required=True, type=Path)
    args = parser.parse_args()
    audit(args.plan, args.directory, args.replay_directory)
