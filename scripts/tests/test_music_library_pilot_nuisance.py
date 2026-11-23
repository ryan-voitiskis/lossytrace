from pathlib import Path
import sys
import unittest
from unittest.mock import patch

try:
    import numpy as np
except ModuleNotFoundError as exc:
    if exc.name != 'numpy': raise
    np = None
if np is not None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import music_library_pilot_nuisance as m


@unittest.skipIf(np is None, 'requires isolated synthetic-requirements research environment')
class NuisanceTests(unittest.TestCase):
    def test_integer_roundtrip_including_limits(self):
        for bits in (16, 24):
            limit = 2**(bits-1)
            values = np.array([[-limit, limit-1], [-1, 0], [1, -20]], dtype=np.float64)/limit
            raw, clipped = m.quantize(values, bits)
            np.testing.assert_array_equal(m.pcm_samples(raw, bits), values)
            self.assertEqual(clipped, 0)

    def test_saturating_quantizer_counts_channel_samples(self):
        raw, clipped = m.quantize(np.array([[-2., 2.], [0., 0.]]), 16)
        self.assertEqual(clipped, 2)
        np.testing.assert_array_equal(m.pcm_samples(raw, 16)[0], [-1., 32767/32768])

    def test_ties_to_even(self):
        raw, _ = m.quantize(np.array([[0.5, 1.5], [-0.5, -1.5]])/32768, 16)
        np.testing.assert_array_equal(m.pcm_samples(raw, 16)*32768, [[0, 2], [0, -2]])

    def test_dither_seed_and_bounds(self):
        samples = np.zeros((10000, 2))
        a, clipped = m.quantize(samples, 16, 1)
        self.assertEqual(a, m.quantize(samples, 16, 1)[0])
        self.assertNotEqual(a, m.quantize(samples, 16, 2)[0])
        self.assertEqual(clipped, 0)
        self.assertEqual(set(np.unique(m.pcm_samples(a, 16)*32768)), {-1, 0, 1})

    def test_invalid_pcm_and_samples(self):
        for raw, bits in ((b'123', 16), (b'1234', 24), (b'', 32)):
            with self.assertRaises(ValueError): m.pcm_samples(raw, bits)
        for samples in (np.zeros((3, 1)), np.array([[np.nan, 0]])):
            with self.assertRaises(ValueError): m.quantize(samples, 16)

    def test_resampling_native_return_and_no_implicit_dither(self):
        for rate, other in ((44100, 48000), (48000, 44100)):
            chain = m.filter_chain('resample', rate)
            self.assertTrue(chain.startswith(f'aresample={other}:'))
            self.assertIn(f',aresample={rate}:', chain)
            self.assertEqual(chain.count('dither_method=0'), 2)
        with self.assertRaises(ValueError): m.filter_chain('gain', 32000)
        with self.assertRaises(ValueError): m.filter_chain('other', 44100)

    def test_identity_and_length_guard(self):
        samples = np.array([[0.25, -0.25], [0., 0.]])
        raw, _ = m.quantize(samples, 24)
        with patch.object(m.c, 'ff', return_value=samples.astype('<f8').tobytes()):
            result, bits, _ = m.process(raw, 24, 44100, 'identity', 1)
            self.assertEqual(result, raw); self.assertEqual(bits, 24)
        with patch.object(m.c, 'ff', return_value=b''):
            with self.assertRaises(ValueError): m.process(raw, 24, 44100, 'resample', 1)

    def test_mono_roundtrip_limits_and_declared_shape(self):
        for bits in (16, 24):
            limit = 2**(bits-1)
            samples = np.array([[-limit], [-1], [0], [1], [limit-1]], dtype=np.float64) / limit
            raw, clipped = m.quantize(samples, bits, channels=1)
            self.assertEqual(clipped, 0)
            np.testing.assert_array_equal(m.pcm_samples(raw, bits, channels=1), samples)
            with self.assertRaises(ValueError):
                m.quantize(np.zeros((3, 2)), bits, channels=1)

    def test_only_declared_resampling_can_trim_up_to_two_final_frames(self):
        samples = np.array([[0.25], [-0.25]])
        raw, _ = m.quantize(samples, 24, channels=1)
        for extra in (1, 2):
            returned = np.vstack((samples, np.full((extra, 1), 0.75))).astype('<f8').tobytes()
            with patch.object(m.c, 'ff', return_value=returned):
                result, bits, receipt = m.process(raw, 24, 48000, 'resample', 1, channels=1,
                                                  match_resampled_length=True)
                self.assertEqual((result, bits, receipt['trailing_resampler_frames_removed']), (raw, 24, extra))
                with self.assertRaises(ValueError):
                    m.process(raw, 24, 48000, 'identity', 1, channels=1, match_resampled_length=True)
                with self.assertRaises(ValueError):
                    m.process(raw, 24, 48000, 'resample', 1, channels=1)
        for bad_count in (1, 5):
            with patch.object(m.c, 'ff', return_value=bytes(8 * bad_count)), self.assertRaises(ValueError):
                m.process(raw, 24, 48000, 'resample', 1, channels=1, match_resampled_length=True)

    def test_interaction_difference_and_missingness(self):
        self.assertEqual(m.difference(4, 2), 2)
        self.assertIsNone(m.difference(None, 2))
        self.assertIsNone(m.difference(2, None))

    def test_factorial_summary(self):
        rows = []
        for case in m.CASES:
            for condition in m.CONDITIONS:
                value = 0.1 + (0.2 if case != 'baseline' else 0) + (0.1 if condition != 'identity' else 0)
                if case != 'baseline' and condition != 'identity': value += 0.05
                rows.append({'source_id': 'synthetic-00', 'case': case, 'condition': condition,
                             'origin': 'controlled_synthesis_no_lossy_stage',
                             'report': {'compression_trace': {f: value for f in m.m.FEATURES}},
                             'audio_retained': False, 'identity_measurements_exact': condition == 'identity',
                             'processing': {'clipped_channel_samples': 0}})
        summary = m.summarize(rows)
        f = summary['strata']['controlled_synthesis_no_lossy_stage']['gain']['codecs']['mp3-128']['spectral_hole_ratio']
        self.assertAlmostEqual(f['codec_delta']['median_delta'], 0.25)
        self.assertAlmostEqual(f['interaction_delta']['median_delta'], 0.05)
        self.assertEqual(summary['identity_feature_objects_exact'], 7)
        for invalid in (rows[:-1], rows+[rows[0]]):
            with self.assertRaises(ValueError): m.summarize(invalid)


if __name__ == '__main__': unittest.main()
