#!/usr/bin/env python3
"""Deterministic metadata-only exploratory selection, never clean-history labels.

Reads a private saved reklawdbox inventory, not music files. Shared credits and
work/release keys connect files across the entire inventory. These incomplete
metadata relationships are exclusion guards, not proven scientific independence.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata

SALT = 'music-library-pilot-v1-selection-20261005'
QUOTAS = {'bandcamp_user_reported': 12, 'beatport_user_reported': 12}
GENERIC = {'various artists', 'various', 'va', 'v.a.', 'unknown', 'unknown artist', 'none', 'n/a'}
CREDIT_FIELDS = ('artist', 'album_artist', 'composer', 'remixer')
VARIANT = re.compile(r'\s*[\(\[][^(\[)\]]*\b(?:remix|mix|edit|version|remaster(?:ed)?)\b[^)\]]*[\)\]]', re.I)


def normalized(value):
    if value is None:
        return ''
    if not isinstance(value, str):
        raise ValueError('tag text must be a string or null')
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def layers(row):
    return [row[k] for k in ('tags', 'id3v2', 'riff_info') if isinstance(row.get(k), dict)]


def relationships(row):
    keys = set()
    for tags in layers(row):
        for field in CREDIT_FIELDS:
            value = normalized(tags.get(field))
            if value and value not in GENERIC:
                keys.add(('credit', value))
        artist = normalized(tags.get('artist'))
        title = normalized(tags.get('title'))
        if artist and artist not in GENERIC and title:
            keys.add(('work', artist, normalized(VARIANT.sub('', title))))
        album = normalized(tags.get('album'))
        album_artist = normalized(tags.get('album_artist')) or artist
        if album and album not in GENERIC and album_artist and album_artist not in GENERIC:
            keys.add(('release', album_artist, album))
    return keys


def digest(*values):
    return hashlib.sha256(json.dumps([SALT, *values], ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def select(document, quotas=None):
    quotas = dict(QUOTAS if quotas is None else quotas)
    if not quotas or any(type(n) is not int or n < 1 for n in quotas.values()):
        raise ValueError('positive integer quotas required')
    entries = document.get('entries')
    if not isinstance(entries, list) or not entries:
        raise ValueError('nonempty inventory required')
    paths = [e.get('path') for e in entries]
    if any(not isinstance(p, str) or not p or '\x00' in p for p in paths) or len(set(paths)) != len(paths):
        raise ValueError('unique nonempty paths required')
    entries = sorted(entries, key=lambda e: e['path'])
    parents = list(range(len(entries)))

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    def join(i, j):
        a, b = root(i), root(j)
        parents[max(a, b)] = min(a, b)

    owners = {}
    for i, e in enumerate(entries):
        row = e.get('metadata')
        if not isinstance(row, dict) or row.get('path') != e['path']:
            raise ValueError('metadata path must match inventory path')
        if 'error' in row:
            continue
        for key in relationships(row):
            if key in owners:
                join(i, owners[key])
            else:
                owners[key] = i
    components = defaultdict(list)
    for i, e in enumerate(entries):
        components[root(i)].append(e['path'])
    ids = {i: digest('component', ps) for i, ps in components.items()}
    candidates = defaultdict(list)
    candidate_counts = Counter()
    for i, e in enumerate(entries):
        row = e['metadata']
        source = e.get('source_bucket')
        if source not in quotas or 'error' in row or row.get('format') not in ('wav', 'flac', 'aiff'):
            continue
        if e.get('history_status') != 'unknown' or e.get('clean_negative_eligible') is not False:
            raise ValueError('pilot originals must retain unknown history')
        if not any(normalized(t.get('artist')) not in GENERIC | {''} and normalized(t.get('title')) for t in layers(row)):
            continue
        component = ids[root(i)]
        candidates[source].append((digest('representative', e['path']), component, e))
        candidate_counts[source] += 1
    # Fixed source order: Bandcamp, then Beatport. No reranking by audio or scores.
    selected = []
    used = set()
    for source, count in quotas.items():
        selected_here = 0
        for _, component, e in sorted(candidates[source], key=lambda x: (x[0], x[2]['path'])):
            if component in used:
                continue
            used.add(component)
            selected.append({'path': e['path'], 'source_bucket': source,
                             'metadata_component_id': component,
                             'history_status': 'unknown', 'clean_negative_eligible': False})
            selected_here += 1
            if selected_here == count:
                break
        if selected_here != count:
            raise ValueError('insufficient metadata-separated candidates under fixed ordering')
    selected_ids = {s['metadata_component_id'] for s in selected}
    return {
        'schema_version': 1, 'study_id': 'music-library-pilot-v1',
        'selection_salt': SALT, 'quotas': quotas,
        'metadata_only': True, 'scientific_independence_verified': False,
        'technical_eligibility_verified': False, 'historical_overlap_verified': False,
        'audio_construction_ready': False,
        'inventory_files': len(entries), 'candidate_counts': dict(candidate_counts),
        'candidate_metadata_components': len({c for rows in candidates.values() for _, c, _ in rows}),
        'selected': selected,
        'related_inventory_paths': {ids[i]: ps for i, ps in components.items() if ids[i] in selected_ids},
        'limitations': [
            'Exact normalized credit strings are not resolved people; aliases, compound credits and uncredited personnel can be missed',
            'Both WAV tag layers contribute edges; conflicts are conservatively unioned, not repaired',
            'Generic artist credits do not connect otherwise unrelated recordings',
            'Title-variant removal is a conservative link heuristic, not a verified work identity',
            'Metadata matching is not audio-duplicate confirmation or historical source clearance',
            'Related paths are grouping references only, not additional selected audio inputs'
        ]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new private ignored JSON file')
    args = parser.parse_args()
    raw = args.inventory.read_bytes()
    result = select(json.loads(raw))
    result['inventory_sha256'] = hashlib.sha256(raw).hexdigest()
    with args.output.open('x') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps({'selected_files': len(result['selected']),
                      'selected_counts': dict(Counter(s['source_bucket'] for s in result['selected'])),
                      'candidate_metadata_components': result['candidate_metadata_components'],
                      'related_inventory_files': sum(map(len, result['related_inventory_paths'].values())),
                      'audio_construction_ready': False}))


if __name__ == '__main__':
    main()
