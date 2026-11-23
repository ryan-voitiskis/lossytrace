"""Generated PCM only. Check lazy windows, alignment, and optimizer equivalence."""

from dataclasses import replace
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
HAVE_DEPS = all(importlib.util.find_spec(name) for name in ("torch", "soundfile", "numpy"))
if HAVE_DEPS:
    import numpy as np
    import soundfile as sf
    import torch
    import music_verdict_candidate as candidate
    import music_verdict_pcm_inputs as pcm
    import music_verdict_training as training


@unittest.skipUnless(HAVE_DEPS, "requires the isolated Torch and libsndfile research environment")
class PCMInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_threads = torch.get_num_threads()
        torch.set_num_threads(2)
        cls.folder = tempfile.TemporaryDirectory()
        cls.root = Path(cls.folder.name)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()
        torch.set_num_threads(cls.previous_threads)

    def case(self, state="baseline", condition="identity", partition="train",
             rate=44100, channels=1, bits=16, extension="wav"):
        path = self.root / f"{partition}-{state}-{condition}-{rate}-{channels}-{bits}.{extension}"
        if not path.exists():
            n = np.arange(rate * 30)
            phase = (2 * np.pi / rate) * (237 if partition == "train" else 347) * n
            wave = .07 * np.sin(phase) + .03 * np.sin(phase * (2 if state == "baseline" else 3))
            wave *= (1 if condition == "identity" else .5) * (1 + .5 * np.sin(phase * .003))
            samples = wave if channels == 1 else np.stack((wave, np.roll(wave, 7)), axis=1)
            pcm_integers = np.rint(samples * 2 ** (bits - 1)).astype(np.int32) << (32 - bits)
            sf.write(path, pcm_integers, rate, subtype=f"PCM_{bits}")
        return pcm.PCMCase(partition + "-group", partition + "-mix", partition, state, condition,
                           path, hashlib.sha256(path.read_bytes()).hexdigest(),
                           rate, channels, bits, rate * 30)

    def quartet(self):
        return pcm.FileQuartet(self.case(), self.case("mp3-192"), self.case(condition="gain"),
                               self.case("mp3-192", "gain"), first_frame=11111)

    def test_native_crop_order_and_shared_offset(self):
        quartet = self.quartet()
        clips = []
        for case in quartet.members:
            # Full-file read and direct slicing provide an independent crop reference.
            full, rate = sf.read(case.path, dtype="float32", always_2d=True)
            clip = full[11111:11111 + 4 * rate].T.copy()
            clips.append(torch.from_numpy(clip))
        expected = candidate.frontend(torch.stack(clips), rate)
        self.assertTrue(torch.equal(quartet.features, expected))

    def test_selection_reopens_and_preserves_wrapper_equivalence(self):
        args = dict(partition="selection", rate=48000, channels=2, bits=24)
        wav = self.case(**args)
        flac = self.case(extension="flac", **args)
        self.assertNotEqual(wav.sha256, flac.sha256)
        windows = flac.selection_file().windows
        self.assertEqual(len(windows), 7)
        full, rate = sf.read(wav.path, dtype="float32", always_2d=True)
        intervals = candidate.analysis_intervals(len(full), rate)
        for (start, end), a, b in zip(intervals, windows, windows, strict=True):
            expected = candidate.frontend(torch.from_numpy(full[start:end].T.copy()).unsqueeze(0), rate)
            self.assertTrue(torch.equal(a, expected) and torch.equal(b, a))

    def test_fail_closed_for_swapped_cases_short_crops_and_split_overlap(self):
        q = self.quartet()
        variants = [dict(coded=q.clean), dict(processed_coded=q.coded),
                    dict(coded=replace(q.coded, source_id="other")),
                    dict(coded=replace(q.coded, rate=48000, frames=30 * 48000)),
                    dict(coded=replace(q.coded, partition="selection")),
                    dict(first_frame=q.clean.frames), dict(first_frame=-1)]
        for change in variants:
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                replace(q, **change)
        with self.assertRaises(ValueError):
            q.clean.selection_file()
        s = replace(self.case(partition="selection"), group=q.group)
        with patch.object(pcm.PCMCase, "open", side_effect=AssertionError("unexpected read")):
            with self.assertRaisesRegex(ValueError, "overlap"):
                training.validate_inputs([q], [s.selection_file(), replace(s, state="mp3-192").selection_file()])

    def test_bytes_and_format_verified_at_read_time(self):
        c = self.case(partition="selection")
        for change, error in [(dict(sha256="0" * 64), "bytes"), (dict(bits=24), "header")]:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, error):
                next(iter(replace(c, **change).selection_file().windows))
        with self.assertRaises(ValueError):
            replace(c, partition="evaluation")

    def test_on_demand_matches_eager_training_and_selection(self):
        q = self.quartet()
        selection = [self.case(state=state, partition="selection").selection_file()
                     for state in ("baseline", "mp3-192")]
        eager = [training.SelectionFile(s.group, s.label, tuple(s.windows)) for s in selection]
        model = torch.nn.Sequential(torch.nn.AdaptiveAvgPool2d(1), torch.nn.Flatten(),
                                    torch.nn.Linear(3, 1), torch.nn.Flatten(0))
        reference = copy.deepcopy(model)
        before = torch.random.get_rng_state()
        a = training.fit_core(model, [q], selection, epochs=2)
        b = training.fit_core(reference, [training.Quartet(q.group, q.features)], eager, epochs=2)
        self.assertEqual(a, b)
        self.assertTrue(torch.equal(before, torch.random.get_rng_state()))
        for observed, expected in zip(model.parameters(), reference.parameters(), strict=True):
            self.assertTrue(torch.equal(observed, expected))
