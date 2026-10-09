import copy
from pathlib import Path
import sys
import tempfile
import unittest

try:
    import numpy
except ModuleNotFoundError as exc:
    if exc.name != 'numpy': raise
    numpy = None
if numpy is not None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import music_library_pilot_measure as m


@unittest.skipIf(numpy is None, 'requires isolated synthetic-requirements research environment')
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

    def test_summary_keeps_strata_and_wrapper_mismatches(self):
        rows = []
        files = ['baseline.wav', 'baseline.flac', 'mp3-128.flac', 'mp3-192.flac',
                 'mp3-320.flac', 'aac-128.flac', 'aac-192.flac', 'aac-256.flac']
        for index, origin in enumerate(('unknown_history', 'controlled_synthesis_no_lossy_stage')):
            for name in files:
                report = self.report()
                report['compression_trace']['spectral_hole_ratio'] = (
                    0.5 if name == 'baseline.wav' or (name == 'baseline.flac' and index == 0) else 0.75)
                rows.append({'source_id': str(index), 'origin': origin, 'file': name,
                             'report': report, 'seconds': len(rows)+1})
        result = m.summarize(rows)
        self.assertEqual(result['wrapper_pairs'], 2)
        self.assertEqual(result['wrapper_feature_objects_exact'], 1)
        for origin in ('unknown_history', 'controlled_synthesis_no_lossy_stage'):
            stats = result['paired_feature_deltas'][origin]['aac-192']['spectral_hole_ratio']
            self.assertEqual(stats['pairs'], 1)
            self.assertEqual(stats['median_delta'], 0.25)
        self.assertEqual(result['timing']['median_seconds'], 8.5)
        self.assertEqual(result['timing']['p95_nearest_rank_seconds'], 16)


if __name__ == '__main__': unittest.main()
