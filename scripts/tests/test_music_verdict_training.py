"""Artificial tensors only; optimizer mechanics, not a pilot/model experiment."""
import copy
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

try:
    import torch
except ModuleNotFoundError as exc:
    if exc.name != 'torch': raise
    torch = None

if torch is not None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import music_verdict_training as m
    import music_verdict_candidate as candidate


@unittest.skipIf(torch is None, 'requires isolated synthetic-requirements research environment')
class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.previous_threads = torch.get_num_threads(); torch.set_num_threads(2)

    def tearDown(self):
        torch.set_num_threads(self.previous_threads)

    def model(self):
        model = torch.nn.Sequential(torch.nn.AdaptiveAvgPool2d(1), torch.nn.Flatten(),
                                    torch.nn.Linear(3, 1), torch.nn.Flatten(0))
        with torch.no_grad():
            model[2].weight.fill_(0.1); model[2].bias.fill_(0.0)
        return model

    def data(self, count=16):
        q = torch.stack([torch.full((3, 16, 16), x) for x in (0., 1., 0.1, 1.1)])
        quartets = [m.Quartet('train-a' if i < 12 else 'train-b', q.clone()) for i in range(count)]
        selection = [m.SelectionFile('selection', y, tuple(torch.full((1, 3, 16, 16), float(y)) for _ in range(6))) for y in (0, 1)]
        return quartets, selection

    def test_partition_and_epochs(self):
        train, selection = self.data()
        with self.assertRaises(ValueError): m.fit_core(self.model(), train, selection, partition='evaluation')
        for epochs in (0, 21, True, 1.5):
            with self.assertRaises(ValueError): m.fit_core(self.model(), train, selection, epochs=epochs)

    def test_overlap_missing_classes_and_invalid_labels(self):
        train, selection = self.data()
        for bad in ([m.SelectionFile('train-a', s.label, s.windows) for s in selection], selection[:1],
                    [m.SelectionFile('selection', True, selection[0].windows), selection[1]]):
            with self.assertRaises(ValueError): m.validate_inputs(train, bad)

    def test_short_selection_window_count_and_malformed_features(self):
        train, selection = self.data()
        with self.assertRaises(ValueError): m.validate_inputs(train, [m.SelectionFile('selection', 0, ())])
        for features in (torch.zeros(3, 3, 16, 16), torch.full((4, 3, 16, 16), float('nan'))):
            with self.assertRaises(ValueError): m.validate_inputs([m.Quartet('train', features)], selection)

    def test_component_class_balanced_selection(self):
        _, selection = self.data(); model = self.model()
        expected = (math.log(2)+math.log1p(math.exp(-0.3)))/2
        self.assertAlmostEqual(m.class_balanced_selection_bce(model, selection), expected, places=7)
        self.assertAlmostEqual(m.class_balanced_selection_bce(model, selection+selection[:1]*5), expected, places=7)
        self.assertTrue(model.training)

    def test_gradient_accumulation_matches_weighted_full_batch(self):
        train, selection = self.data(); actual = self.model(); expected = copy.deepcopy(actual)
        train = [m.Quartet(item.group, item.features*(2 if item.group == 'train-b' else 1)) for item in train]
        optimizer = torch.optim.AdamW(expected.parameters(), lr=m.LEARNING_RATE, weight_decay=m.WEIGHT_DECAY)
        loss = sum(candidate.quartet_loss(expected(item.features).reshape(1, 4))['loss']/(2*(12 if i < 12 else 4))
                   for i, item in enumerate(train))
        loss.backward(); optimizer.step()
        result = m.fit_core(actual, train, selection, epochs=1)
        self.assertEqual(result['optimizer_steps'], 1)
        for a, b in zip(actual.parameters(), expected.parameters()): torch.testing.assert_close(a, b)

    def test_mean_file_logit_precedes_bce(self):
        _, selection = self.data(); model = self.model()
        windows = tuple(torch.full((1, 3, 16, 16), x) for x in (-10., -10., -10., 1., 1., 1.))
        selection[1] = m.SelectionFile('selection', 1, windows)
        expected = (math.log(2)+math.log1p(math.exp(1.35)))/2
        self.assertAlmostEqual(m.class_balanced_selection_bce(model, selection), expected, places=6)

    def test_nonfinite_gradient_stops_before_optimizer_update(self):
        train, selection = self.data(); model = self.model()
        before = copy.deepcopy(model.state_dict())
        next(model.parameters()).register_hook(lambda gradient: torch.full_like(gradient, float('nan')))
        with self.assertRaisesRegex(ValueError, 'nonfinite gradients'):
            m.fit_core(model, train, selection, epochs=1)
        for key, value in model.state_dict().items(): self.assertTrue(torch.equal(value, before[key]))

    def test_short_last_accumulation_is_recorded(self):
        train, selection = self.data(17)
        result = m.fit_core(self.model(), train, selection, epochs=1)
        self.assertEqual(result['optimizer_steps'], 2)
        self.assertEqual(result['history'][0]['last_accumulation_quartets'], 1)

    def test_best_state_restore_and_earliest_tie(self):
        train, selection = self.data(); first = self.model()
        m.fit_core(first, train, selection, epochs=1)
        for losses in ([1., 2.], [1., 1.]):
            model = self.model()
            with patch.object(m, 'class_balanced_selection_bce', side_effect=losses):
                result = m.fit_core(model, train, selection, epochs=2)
            self.assertEqual(result['selected_epoch'], 1)
            for a, b in zip(first.parameters(), model.parameters()): torch.testing.assert_close(a, b)

    def test_determinism_and_rng_preservation(self):
        train, selection = self.data(17); a = self.model(); b = copy.deepcopy(a)
        before = torch.random.get_rng_state().clone()
        left = m.fit_core(a, train, selection, epochs=2)
        right = m.fit_core(b, train, selection, epochs=2)
        self.assertEqual(left, right)
        self.assertTrue(torch.equal(before, torch.random.get_rng_state()))
        for x, y in zip(a.parameters(), b.parameters()): self.assertTrue(torch.equal(x, y))

    def test_real_candidate_small_tensor_optimizer_step(self):
        train, selection = self.data(1); model = candidate.build_candidate()
        before = {k: v.clone() for k, v in model.state_dict().items()}
        result = m.fit_core(model, train, selection, epochs=1)
        self.assertEqual(result['optimizer_steps'], 1)
        self.assertTrue(any(not torch.equal(before[k], v) for k, v in model.state_dict().items()))
        self.assertFalse(result['scientific_execution_authorized_by_this_function'])


if __name__ == '__main__': unittest.main()
