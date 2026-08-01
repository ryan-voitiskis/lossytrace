import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "train-audio-integrity-crnn-domain-holdout.py"
)
SPEC = importlib.util.spec_from_file_location("audio_integrity_crnn", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def case(case_id, label, domain, group):
    return {
        "case_id": case_id,
        "_label": label,
        "_domain": domain,
        "partition_group": group,
    }


class CrnnDomainHoldoutTests(unittest.TestCase):
    def test_inner_validation_groups_are_domain_stratified_and_stable(self):
        cases = []
        for domain in ("a", "b", "outer"):
            for group_index in range(5):
                group = f"{domain}-{group_index}"
                cases.append(case(f"{group}-negative", 0, domain, group))
                cases.append(case(f"{group}-positive", 1, domain, group))
        first = MODULE.inner_validation_groups(cases, "outer", 1234)
        second = MODULE.inner_validation_groups(cases, "outer", 1234)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertEqual(
            {next(item["_domain"] for item in cases if item["partition_group"] == group) for group in first},
            {"a", "b"},
        )
        self.assertFalse(any(group.startswith("outer-") for group in first))

    def test_balanced_epoch_plan_balances_labels_deterministically(self):
        cases = [
            case("negative-a", 0, "a", "negative-a"),
            case("positive-a", 1, "a", "positive-a"),
            case("positive-b", 1, "a", "positive-b"),
            case("positive-c", 1, "a", "positive-c"),
        ]
        first = MODULE.balanced_epoch_plan(cases, 99, 2)
        second = MODULE.balanced_epoch_plan(cases, 99, 2)
        self.assertEqual(
            [(item["case_id"], occurrence) for item, occurrence in first],
            [(item["case_id"], occurrence) for item, occurrence in second],
        )
        labels = [item["_label"] for item, _ in first]
        self.assertEqual(labels.count(0), labels.count(1))
        self.assertEqual(len(labels), 6)

    def test_strict_boundary_and_metrics_exclude_all_observed_negatives(self):
        scores = [0.2, 0.4, 0.3, 0.8]
        labels = [0, 0, 1, 1]
        boundary = MODULE.strict_zero_false_positive_boundary(scores, labels)
        self.assertGreater(boundary, 0.4)
        metrics = MODULE.binary_metrics(scores, labels, boundary)
        self.assertEqual(metrics["false_positives"], 0)
        self.assertEqual(metrics["true_positives"], 1)
        self.assertEqual(metrics["recall"], 0.5)
        self.assertAlmostEqual(MODULE.roc_auc(scores, labels), 0.75)

    def test_case_window_starts_use_two_seconds_and_half_overlap(self):
        self.assertEqual(MODULE.case_window_starts(100, 100), [0])
        self.assertEqual(MODULE.case_window_starts(500, 100), [0, 100, 200, 300])

    def test_model_shape_and_parameterization_when_torch_is_available(self):
        try:
            import torch
            import torchaudio
            from torch import nn
        except ImportError:
            self.skipTest("research PyTorch environment is opt-in")
        model = MODULE.build_model(torch, torchaudio, nn)
        output = model(torch.zeros(2, MODULE.CLIP_SAMPLES))
        self.assertEqual(tuple(output.shape), (2, 2))
        self.assertEqual(model.lstm.hidden_size, 128)
        self.assertEqual(model.lstm.num_layers, 2)
        self.assertTrue(model.lstm.bidirectional)

    def test_audio_crop_resamples_and_has_exact_shape_when_stack_is_available(self):
        try:
            import numpy as np
            import soundfile as sf
            import torch
            import torchaudio
        except ImportError:
            self.skipTest("research PyTorch environment is opt-in")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.wav"
            samples = np.linspace(-0.5, 0.5, 48_000, dtype=np.float32)
            sf.write(path, samples, 16_000, subtype="PCM_16")
            result = MODULE.read_crop(
                {"case_id": "source", "_audio_path": str(path)},
                0.5,
                np=np,
                sf=sf,
                torch=torch,
                torchaudio=torchaudio,
            )
        self.assertEqual(tuple(result.shape), (MODULE.CLIP_SAMPLES,))
        self.assertTrue(bool(torch.isfinite(result).all()))


if __name__ == "__main__":
    unittest.main()
