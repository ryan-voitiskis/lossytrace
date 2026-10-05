import importlib.util
from pathlib import Path
import tempfile
import unittest
import wave

try:
    import numpy as np
except ModuleNotFoundError:
    np = None

if np is not None:
    p = Path(__file__).resolve().parents[1] / 'music_library_pilot_synthesis.py'
    spec = importlib.util.spec_from_file_location('synthesis', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)


@unittest.skipIf(np is None, 'requires isolated research NumPy')
class SynthesisTests(unittest.TestCase):
    def test_all_families_rates_and_shapes(self):
        for i in range(24):
            pcm, p = m.render(i, 0.25)
            self.assertEqual(pcm.shape, (round(p['sample_rate']*0.25), 2))
            self.assertEqual(pcm.dtype, np.dtype('<i2'))
            self.assertGreater(np.max(np.abs(pcm.astype(np.int32))), 0)
            self.assertLess(np.max(np.abs(pcm.astype(np.int32))), 32767)
            self.assertTrue(np.all(pcm[[0,-1]] == 0))

    def test_reproducibility(self):
        np.testing.assert_array_equal(m.render(7, 0.5)[0], m.render(7, 0.5)[0])

    def test_seeds_and_family_counts(self):
        self.assertEqual(len({m.parameters(i)['seed'] for i in range(24)}),24)
        self.assertEqual({m.parameters(i)['family'] for i in range(24)}, set(m.FAMILIES))

    def test_quiet_variant(self):
        pcm,p=m.render(5,0.5)
        self.assertAlmostEqual(p['peak_target'],0.65*10**(-24/20))
        self.assertLess(np.max(np.abs(pcm.astype(np.int32))),1400)

    def test_bad_index(self):
        for i in (-1,24,True,0.5):
            with self.assertRaises(ValueError):m.parameters(i)

    def test_bad_duration(self):
        for d in (0,-1,121,True,float('nan'),float('inf'),0.000001):
            with self.assertRaises(ValueError):m.render(0,d)

    def test_wav_pcm_roundtrip_and_no_clobber(self):
        pcm,p=m.render(0,0.1)
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'test.wav'
            m.write_wav(out,pcm,p['sample_rate'])
            with wave.open(str(out),'rb') as r:
                self.assertEqual(r.getnchannels(),2)
                self.assertEqual(r.getsampwidth(),2)
                self.assertEqual(r.getframerate(),p['sample_rate'])
                self.assertEqual(r.readframes(r.getnframes()),pcm.tobytes())
            with self.assertRaises(FileExistsError):m.write_wav(out,pcm,p['sample_rate'])


if __name__ == '__main__':unittest.main()
