"""Generated tensors only. No real audio, checkpoint or optimizer step."""
import importlib.util
import math
from pathlib import Path
import unittest

try:
    import torch
except ModuleNotFoundError as exc:
    if exc.name != "torch":
        raise
    torch = None

if torch is not None:
    SCRIPT = Path(__file__).resolve().parents[1] / "music_verdict_candidate.py"
    SPEC = importlib.util.spec_from_file_location("music_verdict_candidate", SCRIPT)
    candidate = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(candidate)


@unittest.skipIf(torch is None, "requires isolated synthetic-requirements research environment")
class CandidateSyntheticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_threads = torch.get_num_threads()
        torch.set_num_threads(2)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.previous_threads)

    def signal(self, rate=44_100):
        t = torch.arange(4 * rate, dtype=torch.float32) / rate
        return (0.1 * torch.sin(2 * math.pi * 440 * t)).reshape(1, 1, -1)

    def test_intervals_native_frames_and_cap(self):
        for rate in candidate.SAMPLE_RATES:
            short = candidate.analysis_intervals(30 * rate, rate)
            long = candidate.analysis_intervals(300 * rate, rate)
            self.assertEqual(len(short), 7)
            self.assertEqual(len(long), 24)
            self.assertEqual(long[0], (0, 4 * rate))
            self.assertEqual(long[-1][1], 120 * rate)
            for intervals, end in ((short, 30 * rate), (long, 120 * rate)):
                for a, b in intervals:
                    self.assertEqual(b - a, 4 * rate)
                    self.assertLessEqual(b, end)
                self.assertTrue(all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])))

    def test_intervals_reject_unsupported_not_pad(self):
        for frames, rate in ((29 * 44100, 44100), (30 * 48000, 96000), (True, 44100),
                             (30.0 * 44100, 44100), (30 * 44100, 44100.0)):
            with self.subTest(frames=frames, rate=rate), self.assertRaises(ValueError):
                candidate.analysis_intervals(frames, rate)

    def test_frontend_native_shapes_and_rate_plane(self):
        for rate, plane in ((44_100, 0), (48_000, 1)):
            result = candidate.frontend(self.signal(rate), rate)
            self.assertEqual(tuple(result.shape), (1, 3, 1025, 1 + (4 * rate - 2048) // 512))
            self.assertTrue(torch.all(result[:, 2] == plane))
            self.assertTrue(torch.all(result[:, 1] == 0))

    def test_duplicate_mono_and_channel_swap_agree(self):
        mono = self.signal()
        duplicate = mono.repeat(1, 2, 1)
        torch.testing.assert_close(candidate.frontend(mono, 44100), candidate.frontend(duplicate, 44100))
        stereo = torch.cat((mono, 0.3 * mono.roll(29, dims=-1)), dim=1)
        torch.testing.assert_close(candidate.frontend(stereo, 44100), candidate.frontend(stereo.flip(1), 44100))

    def test_antiphase_is_not_discarded_as_silence(self):
        mono = self.signal()
        features = candidate.frontend(torch.cat((mono, -mono), dim=1), 44100)
        self.assertEqual(torch.count_nonzero(features[:, 0]).item(), 0)
        self.assertGreater(torch.count_nonzero(features[:, 1]).item(), 0)

    def test_joint_gain_normalization_above_floor(self):
        signal = self.signal()
        torch.testing.assert_close(candidate.frontend(signal, 44100),
                                   candidate.frontend(signal * 0.25, 44100), atol=1e-6, rtol=1e-5)

    def test_silence_and_very_quiet_inputs_stay_finite(self):
        for value in (0.0, 1e-12, 1e20):
            result = candidate.frontend(torch.full((1, 2, 4 * 44100), value), 44100)
            self.assertTrue(torch.isfinite(result).all())
            if value == 0:
                self.assertEqual(torch.count_nonzero(result).item(), 0)

    def test_frontend_rejects_nonfinite_wrong_type_channels_and_partial_windows(self):
        for value in (torch.zeros(1, 1, 44100), torch.zeros(1, 3, 4 * 44100),
                      torch.zeros(1, 1, 4 * 44100, dtype=torch.int16),
                      torch.full((1, 1, 4 * 44100), float("nan")), torch.zeros(0, 1, 4 * 44100)):
            with self.subTest(shape=value.shape), self.assertRaises(ValueError):
                candidate.frontend(value, 44100)

    def test_parameter_count_and_no_batchnorm_or_dropout(self):
        model = candidate.build_candidate()
        self.assertEqual(sum(p.numel() for p in model.parameters()), 217201)
        self.assertLess(sum(p.numel() for p in model.parameters()), 300000)
        self.assertFalse(any(isinstance(m, (torch.nn.BatchNorm2d, torch.nn.Dropout)) for m in model.modules()))
        self.assertEqual(sum(isinstance(m, torch.nn.Conv2d) for m in model.modules()), 8)

    def test_fixed_seed_initialization_and_rng_preservation(self):
        before = torch.random.get_rng_state().clone()
        first, second = candidate.build_candidate(), candidate.build_candidate()
        self.assertTrue(torch.equal(before, torch.random.get_rng_state()))
        for left, right in zip(first.parameters(), second.parameters()):
            self.assertTrue(torch.equal(left, right))

    def test_full_native_frontend_forward_both_rates(self):
        model = candidate.build_candidate().eval()
        with torch.inference_mode():
            for rate in candidate.SAMPLE_RATES:
                logits = model(candidate.frontend(self.signal(rate), rate))
                self.assertEqual(tuple(logits.shape), (1,))
                self.assertTrue(torch.isfinite(logits).all())

    def test_no_cross_sample_batch_statistics(self):
        model = candidate.build_candidate().eval()
        features = torch.zeros(1, 3, 32, 32)
        distracting = torch.full_like(features, 10)
        with torch.inference_mode():
            first = model(features)
            batched = model(torch.cat((features, distracting)))[:1]
        torch.testing.assert_close(first, batched, atol=1e-6, rtol=1e-5)

    def test_quartet_zero_logits_matches_hand_calculation(self):
        values = candidate.quartet_loss(torch.zeros(2, 4))
        self.assertAlmostEqual(values["bce"].item(), math.log(2), places=6)
        self.assertEqual(values["consistency"].item(), 0)
        self.assertAlmostEqual(values["loss"].item(), math.log(2), places=6)

    def test_quartet_penalty_pairs_same_label_and_gradients_are_finite(self):
        logits = torch.tensor([[0.0, 1.0, 2.0, 4.0]], requires_grad=True)
        values = candidate.quartet_loss(logits)
        self.assertEqual(values["consistency"].item(), (4 + 9) / 2)
        values["loss"].backward()
        self.assertTrue(torch.isfinite(logits.grad).all())
        self.assertTrue(torch.all(logits.grad != 0))

    def test_identical_within_label_scores_have_zero_consistency_penalty(self):
        values = candidate.quartet_loss(torch.tensor([[-3.0, 4.0, -3.0, 4.0]]))
        self.assertEqual(values["consistency"].item(), 0)

    def test_quartet_rejects_missing_members_and_nonfinite(self):
        for value in (torch.zeros(4), torch.zeros(1, 3), torch.full((1, 4), float("inf"))):
            with self.subTest(shape=value.shape), self.assertRaises(ValueError):
                candidate.quartet_loss(value)

    def test_file_score_uses_logits_and_requires_enough_windows(self):
        logits = torch.tensor([-10.0, 0, 1, 2, 3, 4])
        self.assertEqual(candidate.mean_window_logit(logits), 0)
        for bad in (logits[:5], torch.zeros(25), torch.full((6,), float("nan"))):
            with self.assertRaises(ValueError):
                candidate.mean_window_logit(bad)


if __name__ == "__main__":
    unittest.main()
