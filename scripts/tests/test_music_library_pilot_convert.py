import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

p=Path(__file__).resolve().parents[1]/'music_library_pilot_convert.py'
spec=importlib.util.spec_from_file_location('convert',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class ConversionTests(unittest.TestCase):
    def test_matrix(self):
        self.assertEqual(m.CASES,[('mp3',128),('mp3',192),('mp3',320),('aac',128),('aac',192),('aac',256)])

    def test_trim_exact_and_tail_only(self):
        raw=bytes(range(40))
        self.assertEqual(m.trim(raw,16,10),(raw,0))
        self.assertEqual(m.trim(raw,16,8),(raw[:32],2))

    def test_trim_never_pads(self):
        with self.assertRaises(ValueError):m.trim(b'\0'*40,16,11)

    def test_trim_frame_alignment_and_limit(self):
        with self.assertRaises(ValueError):m.trim(b'\0'*41,16,10)
        with self.assertRaises(ValueError):m.trim(b'\0'*4*(10+2049),16,10)

    def test_native_mono_trim_counts_frames_at_either_depth(self):
        for bits in (16, 24):
            stride = bits // 8
            raw = bytes(range(8 * stride))
            self.assertEqual(m.trim(raw, bits, 7, channels=1), (raw[:-stride], 1))
            with self.assertRaises(ValueError):
                m.trim(raw[:-1], bits, 7, channels=1)
        with self.assertRaises(ValueError):
            m.from_pcm(b'abc', 'unused.wav', 44100, 16, channels=1)
        for count in (0, 3, True):
            with self.assertRaises(ValueError):
                m.pcm_stride(24, count)

    def test_mp3_options(self):
        with patch.object(m,'ff') as ff:
            m.encode('in.wav','out.mp3','mp3',128)
            args=ff.call_args.args[0]
            self.assertEqual(args[args.index('-abr')+1],'0')
            self.assertEqual(args[args.index('-write_xing')+1],'1')
            self.assertEqual(args[args.index('-b:a')+1],'128k')

    def test_aac_options(self):
        with patch.object(m,'ff') as ff:
            m.encode('in.wav','out.m4a','aac',256)
            args=ff.call_args.args[0]
            self.assertEqual(args[args.index('-profile:a')+1],'aac_low')
            self.assertEqual(args[args.index('-aac_coder')+1],'twoloop')

    def test_unplanned_codec_rejected(self):
        with self.assertRaises(ValueError):m.encode('x','y','opus',128)

    def test_native_stream_validation(self):
        with patch.object(m,'probe',return_value={'streams':[{'sample_rate':'44100','channels':2,'codec_name':'aac'}]}):
            m.validate_stream('x',44100,'aac')
            with self.assertRaises(ValueError):m.validate_stream('x',48000,'aac')
            with self.assertRaises(ValueError):m.validate_stream('x',44100,'mp3')

    def test_no_clobber_and_scope(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(m,'ROOT',Path(temp)):
            out=Path(temp)/'new';m.private_output(out)
            with self.assertRaises(FileExistsError):m.private_output(out)
            with self.assertRaises(ValueError):m.private_output(Path(temp))
            with self.assertRaises(ValueError):m.private_output(Path(temp).parent/'outside')


if __name__=='__main__':unittest.main()
