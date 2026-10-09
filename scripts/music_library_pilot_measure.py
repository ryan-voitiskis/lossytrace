#!/usr/bin/env python3
"""Bound descriptive pilot measurements, never fitting or provenance verdicts."""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import time

import music_library_pilot_convert as construction
from music_verdict_comparator import FEATURES, measurement_matrix


def paired_summary(before, after):
    if len(before) != len(after) or not before:
        raise ValueError('nonempty matched pairs required')
    deltas = [b-a for a, b in zip(before, after) if a is not None and b is not None]
    return {'pairs': len(before), 'both_present': len(deltas),
            'before_missing': sum(a is None for a in before),
            'after_missing': sum(b is None for b in after),
            'became_missing': sum(a is not None and b is None for a, b in zip(before, after)),
            'became_present': sum(a is None and b is not None for a, b in zip(before, after)),
            'positive_deltas': sum(d > 0 for d in deltas),
            'negative_deltas': sum(d < 0 for d in deltas),
            'zero_deltas': sum(d == 0 for d in deltas),
            'median_delta': statistics.median(deltas) if deltas else None,
            'min_delta': min(deltas) if deltas else None,
            'max_delta': max(deltas) if deltas else None}


def check_report(report, expected_hash, rate):
    if (report['schema_version'] != 1 or report['public_verdict_enabled'] is not False
            or report['state'] != 'experimental_measurements_only'
            or report['input_sha256'] != expected_hash
            or report['analyzed_sample_count'] != 120*rate
            or report['analyzed_duration_seconds'] != 120
            or report['truncated_by_limit'] is not False
            or report['source_facts']['sample_rate_hz'] != rate
            or report['source_facts']['channel_count'] != 2):
        raise ValueError('unexpected report provenance, scope or verdict state')
    measurement_matrix([report['compression_trace']])


def contained_file(directory, name):
    if Path(name).name != name or name in ('.', '..'):
        raise ValueError('expected local filename')
    p = directory/name
    if p.is_symlink() or not p.resolve().is_relative_to(directory.resolve()):
        raise ValueError('input escapes bound directory')
    return p


def measure(plan_path, output):
    plan = json.loads(plan_path.read_text())
    for item in plan['bound_files']:
        if construction.sha(item['path']) != item['sha256']:
            raise ValueError('analysis binding mismatch')
    if construction.sha(Path(__file__)) != plan['runner_sha256']:
        raise ValueError('runner binding mismatch')
    binary = Path(plan['binary']).resolve()
    root = Path(plan['input_directory'])
    manifest = json.loads((root/'manifest.json').read_text())
    expected_ids = [f'{kind}-{i:02}' for kind in ('library', 'synthetic') for i in range(24)]
    if [s['id'] for s in manifest['sources']] != expected_ids:
        raise ValueError('fixed source matrix mismatch')
    construction.storage_guard()
    construction.private_output(output)
    rows = []
    for source in manifest['sources']:
        directory = root/source['id']
        source_path = directory/'manifest.json'
        if construction.sha(source_path) != source['manifest_sha256']:
            raise ValueError('source manifest binding mismatch')
        metadata = json.loads(source_path.read_text())
        if [c['case'] for c in metadata['cases']] != ['baseline', 'mp3-128', 'mp3-192', 'mp3-320', 'aac-128', 'aac-192', 'aac-256']:
            raise ValueError('fixed case matrix mismatch')
        rate = metadata['source']['rate']
        for case in metadata['cases']:
            files = case['files'] if case['case'] == 'baseline' else [
                {'file': case['decoded_file'], 'sha256': case['decoded_sha256']}]
            if case['case'] == 'baseline' and [f['file'] for f in files] != ['baseline.wav', 'baseline.flac']:
                raise ValueError('wrapper pair missing')
            for item in files:
                construction.storage_guard()
                path = contained_file(directory, item['file'])
                if construction.sha(path) != item['sha256']:
                    raise ValueError('audio input hash mismatch')
                started = time.perf_counter()
                completed = subprocess.run([str(binary), 'analyze', str(path), '--max-seconds', '0'],
                                           capture_output=True, check=True, timeout=180)
                elapsed = time.perf_counter()-started
                report = json.loads(completed.stdout)
                check_report(report, item['sha256'], rate)
                if construction.sha(path) != item['sha256']:
                    raise ValueError('audio changed during analysis')
                row = {'source_id': source['id'], 'origin': metadata['source']['origin'],
                       'component': metadata['source']['component'], 'case': case['case'],
                       'file': item['file'], 'seconds': elapsed, 'report': report}
                construction.save(output/f'{source["id"]}-{item["file"]}.json', row)
                rows.append(row)
        print(json.dumps({'completed_sources': len(rows)//8, 'reports': len(rows)}), flush=True)
    # Recheck code/binary/controls after execution; no unnoticed mid-run drift.
    for item in plan['bound_files']:
        if construction.sha(item['path']) != item['sha256']:
            raise ValueError('analysis binding changed during run')
    if construction.sha(Path(__file__)) != plan['runner_sha256']:
        raise ValueError('runner changed during run')
    summary = summarize(rows)
    summary.update(plan_sha256=construction.sha(plan_path), reports=len(rows),
                   fitted_models=0, verdicts_generated=False, release_accuracy_estimate=False)
    construction.save(output/'summary.json', summary)


def summarize(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row['source_id'], {})[row['file']] = row
    exact = sum(g['baseline.wav']['report']['compression_trace'] ==
                g['baseline.flac']['report']['compression_trace'] for g in grouped.values())
    strata = {}
    for origin in sorted({r['origin'] for r in rows}):
        groups = [g for g in grouped.values() if g['baseline.wav']['origin'] == origin]
        cases = {}
        for case in ('mp3-128', 'mp3-192', 'mp3-320', 'aac-128', 'aac-192', 'aac-256'):
            cases[case] = {feature: paired_summary(
                [g['baseline.wav']['report']['compression_trace'][feature] for g in groups],
                [g[f'{case}.flac']['report']['compression_trace'][feature] for g in groups])
                for feature in FEATURES}
        strata[origin] = cases
    times = sorted(r['seconds'] for r in rows)
    return {'wrapper_pairs': len(grouped), 'wrapper_feature_objects_exact': exact,
            'paired_feature_deltas': strata,
            'timing': {'calls': len(times), 'median_seconds': statistics.median(times),
                       'p95_nearest_rank_seconds': times[(95*len(times)+99)//100-1],
                       'max_seconds': max(times),
                       'scope': 'Sequential observed inspector timings, not controlled cold-cache or verdict runtime'}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    measure(args.plan, args.output)
