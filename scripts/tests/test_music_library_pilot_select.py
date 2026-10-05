import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'music_library_pilot_select.py'
SPEC = importlib.util.spec_from_file_location('pilot_select', PATH)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def row(path, artist, source='a', **tags):
    return {'path': path, 'source_bucket': source, 'history_status': 'unknown',
            'clean_negative_eligible': False,
            'metadata': {'path': path, 'format': 'flac',
                         'tags': {'artist': artist, 'title': path, **tags}}}


class SelectionTests(unittest.TestCase):
    def test_repeat_and_order_invariance(self):
        es = [row('x', 'X'), row('y', 'Y'), row('z', 'Z')]
        self.assertEqual(module.select({'entries': es}, {'a': 2}),
                         module.select({'entries': es[::-1]}, {'a': 2}))

    def test_shared_artist_cannot_supply_two(self):
        with self.assertRaises(ValueError):
            module.select({'entries': [row('x', 'X'), row('y', ' x ')]}, {'a': 2})

    def test_secondary_credit_transitive_bridge_outside_candidates(self):
        es = [row('x', 'X'), row('y', 'Y', 'b'),
              row('bridge', 'X', 'outside', remixer='Y')]
        with self.assertRaises(ValueError):
            module.select({'entries': es}, {'a': 1, 'b': 1})

    def test_generic_album_artist_does_not_join_everything(self):
        es = [row('x', 'X', album_artist='Various Artists'),
              row('y', 'Y', album_artist='Various Artists')]
        self.assertEqual(len(module.select({'entries': es}, {'a': 2})['selected']), 2)

    def test_both_wav_layers_contribute(self):
        a = row('x', 'X')
        a['metadata'].update(format='wav', riff_info={'artist': 'Y'})
        with self.assertRaises(ValueError):
            module.select({'entries': [a, row('y', 'Y')]}, {'a': 2})

    def test_shared_release_key(self):
        keys = module.relationships({'tags': {'artist': 'X', 'album': 'Album', 'album_artist': 'Band'}})
        self.assertIn(('release', 'band', 'album'), keys)

    def test_work_variants(self):
        a = module.relationships({'tags': {'artist': 'X', 'title': 'Song (Club Remix)'}})
        b = module.relationships({'tags': {'artist': 'X', 'title': 'Song'}})
        self.assertIn(('work', 'x', 'song'), a & b)

    def test_unknown_history_never_promoted(self):
        es = [row('x', 'X')]
        r = module.select({'entries': es}, {'a': 1})
        self.assertEqual(r['selected'][0]['history_status'], 'unknown')
        self.assertFalse(r['audio_construction_ready'])
        es[0]['clean_negative_eligible'] = True
        with self.assertRaises(ValueError):
            module.select({'entries': es}, {'a': 1})

    def test_failures_not_candidates(self):
        a = row('x', 'X'); a['metadata']['error'] = 'unreadable'
        with self.assertRaises(ValueError):
            module.select({'entries': [a]}, {'a': 1})

    def test_path_mismatch_and_duplicate_rejected(self):
        a = row('x', 'X')
        with self.assertRaises(ValueError):
            module.select({'entries': [a, a]}, {'a': 1})
        a['metadata']['path'] = 'elsewhere'
        with self.assertRaises(ValueError):
            module.select({'entries': [a]}, {'a': 1})

    def test_two_quotas_have_distinct_components(self):
        es = [row('x', 'X'), row('y', 'Y', 'b')]
        r = module.select({'entries': es}, {'a': 1, 'b': 1})
        self.assertEqual(len({x['metadata_component_id'] for x in r['selected']}), 2)

    def test_bad_tags_and_quotas_rejected(self):
        with self.assertRaises(ValueError):
            module.normalized(['X'])
        for quota in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                module.select({'entries': [row('x', 'X')]}, {'a': quota})


if __name__ == '__main__':
    unittest.main()
