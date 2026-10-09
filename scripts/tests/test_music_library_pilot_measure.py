import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import music_library_pilot_measure as m


class MeasurementTests(unittest.TestCase):
    def test_signed_pairs_and_missingness(self):
        result = m.paired_summary([1, 3, 2, None, 5, None], [2, 1, 2, 4, None, None])
        self.assertEqual(result['both_present'], 3)
        self.assertEqual(result['median_delta'], 0)
        self.assertEqual(result['min_delta'], -2)
        self.assertEqual(result['max_delta'], 1)
        for key in ('positive_deltas', 'negative_deltas', 'zero_deltas', 'became_missing', 'became_present'):
            self.assertEqual(result[key], 1)

    def test_no_observations_not_zero(self):
        self.assertIsNone(m.paired_summary([None], [2])['median_delta'])

    def test_bad_pair_lengths(self):
        for a, b in (([], []), ([1], [1, 2])):
            with self.assertRaises(ValueError): m.paired_summary(a, b)

    def report(self):
        features = {f: None for f in m.FEATURES}
        features.update(feature_version=0, analyzed_frame_count=1, active_frame_count=0,
                        high_band_supported_frame_count=0, active_duration_seconds=0)
        return {'schema_version': 1, 'state': 'experimental_measurements_only',
                'public_verdict_enabled': False, 'input_sha256': 'hash',
                'analyzed_sample_count': 120*44100, 'analyzed_duration_seconds': 120,
                'truncated_by_limit': False, 'source_facts': {'sample_rate_hz': 44100, 'channel_count': 2},
                'compression_trace': features}

    def test_report_scope(self):
        original = self.report()
        m.check_report(original, 'hash', 44100)
        for field, value in [('public_verdict_enabled', True), ('input_sha256', 'other'),
                             ('analyzed_sample_count', 3), ('truncated_by_limit', True)]:
            report = copy.deepcopy(original); report[field] = value
            with self.assertRaises(ValueError): m.check_report(report, 'hash', 44100)

    def test_invalid_feature_rejected(self):
        report = self.report(); report['compression_trace']['spectral_hole_ratio'] = float('nan')
        with self.assertRaises(ValueError): m.check_report(report, 'hash', 44100)

    def test_scoped_files(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self.assertEqual(m.contained_file(directory, 'x.wav'), directory/'x.wav')
            for name in ('../x.wav', '/tmp/x.wav', '.', '..'):
                with self.assertRaises(ValueError): m.contained_file(directory, name)
            (directory/'link').symlink_to(directory/'missing')
            with self.assertRaises(ValueError): m.contained_file(directory, 'link')


if __name__ == '__main__': unittest.main()
