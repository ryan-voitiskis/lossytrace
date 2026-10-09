from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import music_library_pilot_nuisance_audit as m


class AuditTests(unittest.TestCase):
    def test_exact_matrix(self):
        keys = m.expected_keys()
        self.assertEqual(len(keys), 2016)
        self.assertEqual(len({k[0] for k in keys}), 48)
        self.assertIn(('library-23', 'aac-256', 'resample'), keys)
        self.assertIn(('synthetic-00', 'baseline', 'identity'), keys)

    def test_fixed_replay_sample(self):
        retained = {k for k in m.expected_keys() if m.retained_key(k)}
        self.assertEqual(len(retained), 24)
        self.assertEqual({k[0] for k in retained}, {'library-00', 'synthetic-00'})
        self.assertEqual({k[1] for k in retained}, {'baseline', 'mp3-192'})
        self.assertEqual(len({k[2] for k in retained}), 6)


if __name__ == '__main__': unittest.main()
