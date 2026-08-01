from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TORCH_AVAILABLE = importlib.util.find_spec("torch") is not None


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(
    TORCH_AVAILABLE,
    "PyTorch is optional for the standard repository test environment",
)
class CnnCacheMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.merger = load_script(
            "merge-audio-integrity-cnn-feature-caches.py"
        )
        cls.torch = cls.merger.torch
        cls.domain_trainer = load_script(
            "train-audio-integrity-cnn-domain-holdout.py"
        )

    def test_metadata_normalization_preserves_tensor_row_order(self) -> None:
        cases_by_id = {
            "a": {
                "case_id": "a",
                "source_group": "source-a",
                "partition_group": "partition-a",
                "class": "lossless",
                "expectation": "negative",
            },
            "b": {
                "case_id": "b",
                "source_group": "source-b",
                "partition_group": "partition-b",
                "class": "mp3",
                "expectation": "controlled_positive",
            },
        }
        metadata = []
        for clip_index in range(5):
            for case_id in ("a", "b"):
                case = cases_by_id[case_id]
                metadata.append(
                    {
                        "case_id": case_id,
                        "source_group": case["source_group"],
                        "partition_group": case["partition_group"],
                        "class": case["class"],
                        "expectation": case["expectation"],
                        "clip_index": clip_index,
                        "sample_rate": 44_100,
                    }
                )
        payload = {
            "features": self.torch.zeros(
                (
                    len(metadata),
                    self.merger.CNN.FRAME_SIZE // 2 + 1,
                    self.merger.CNN.IMAGE_WIDTH,
                ),
                dtype=self.torch.float16,
            ),
            "metadata": metadata,
        }

        normalized, case_ids = self.merger.validate_cache_metadata(
            cache=Path("fixture.pt"),
            payload=payload,
            cases_by_id=cases_by_id,
            case_domain={"a": "domain-a", "b": "domain-b"},
        )

        self.assertEqual(
            [(item["case_id"], item["clip_index"]) for item in normalized],
            [(item["case_id"], item["clip_index"]) for item in metadata],
        )
        self.assertEqual(
            [item["source_domain"] for item in normalized],
            ["domain-a", "domain-b"] * 5,
        )
        self.assertEqual(case_ids, {"a", "b"})

    def test_rejects_duplicate_clip_index(self) -> None:
        case = {
            "case_id": "a",
            "source_group": "source-a",
            "class": "lossless",
            "expectation": "negative",
        }
        metadata = [
            {
                **case,
                "clip_index": clip_index,
                "sample_rate": 44_100,
            }
            for clip_index in (0, 1, 2, 3, 3)
        ]
        payload = {
            "features": self.torch.zeros(
                (
                    len(metadata),
                    self.merger.CNN.FRAME_SIZE // 2 + 1,
                    self.merger.CNN.IMAGE_WIDTH,
                ),
                dtype=self.torch.float16,
            ),
            "metadata": metadata,
        }

        with self.assertRaises(SystemExit):
            self.merger.validate_cache_metadata(
                cache=Path("fixture.pt"),
                payload=payload,
                cases_by_id={"a": case},
                case_domain={"a": "domain-a"},
            )

    def test_content_residual_omits_constant_level_shift(self) -> None:
        batch = self.torch.rand((2, 1, 257, 172)) * 0.5 + 0.2
        shifted = batch + 0.1

        baseline = self.domain_trainer.transform_batch(
            batch,
            "absolute_v1",
        )
        shifted_baseline = self.domain_trainer.transform_batch(
            shifted,
            "absolute_v1",
        )
        residual = self.domain_trainer.transform_batch(
            batch,
            "content_residual_v1",
        )
        shifted_residual = self.domain_trainer.transform_batch(
            shifted,
            "content_residual_v1",
        )

        self.assertEqual(tuple(residual.shape), (2, 3, 257, 172))
        self.assertFalse(
            self.torch.allclose(baseline, shifted_baseline)
        )
        self.assertTrue(
            self.torch.allclose(
                residual,
                shifted_residual,
                atol=1.0e-5,
            )
        )

    def test_domain_holdout_split_is_disjoint_and_stratified(
        self,
    ) -> None:
        metadata = []
        for domain in ("a", "b", "c"):
            for group_index in range(5):
                metadata.append(
                    {
                        "partition_group": (
                            f"{domain}-{group_index}"
                        ),
                        "source_domain": domain,
                    }
                )

        train, validation, test = (
            self.domain_trainer.domain_holdout_split(
                metadata,
                "c",
                early_stop_group_fraction=0.20,
                early_stop_seed=7,
            )
        )

        self.assertFalse(train & validation)
        self.assertFalse(train & test)
        self.assertFalse(validation & test)
        self.assertEqual(
            train | validation | test,
            {
                f"{domain}-{group_index}"
                for domain in ("a", "b", "c")
                for group_index in range(5)
            },
        )
        self.assertEqual(test, {f"c-{index}" for index in range(5)})
        self.assertEqual(
            {group.split("-")[0] for group in validation},
            {"a", "b"},
        )

    def test_pair_dataset_matches_source_and_clip_index(self) -> None:
        metadata = []
        features = []
        for source_index in range(2):
            for clip_index in range(5):
                for expectation in (
                    "negative",
                    "controlled_positive",
                ):
                    metadata.append(
                        {
                            "case_id": (
                                f"{source_index}-{expectation}"
                            ),
                            "source_group": f"source-{source_index}",
                            "clip_index": clip_index,
                            "sample_rate": 48_000,
                            "expectation": expectation,
                        }
                    )
                    value = (
                        source_index * 100
                        + clip_index * 10
                        + (
                            1
                            if expectation
                            == "controlled_positive"
                            else 0
                        )
                    )
                    features.append(
                        self.torch.full(
                            (257, 172),
                            value,
                            dtype=self.torch.float16,
                        )
                    )
        dataset = self.domain_trainer.PairedDomainClipDataset(
            self.torch.stack(features),
            metadata,
            list(range(len(metadata))),
            seed=3,
            mask_probability=0.0,
            level_shift_probability=0.0,
        )

        self.assertEqual(len(dataset), 10)
        for item in range(len(dataset)):
            positive, negative = dataset[item]
            self.assertEqual(
                float(positive[0, 0, 0] - negative[0, 0, 0]),
                1.0,
            )

    def test_group_normalized_model_has_no_batch_norm(self) -> None:
        model = self.domain_trainer.LossyTraceCnn(3, "group_v1")

        self.assertFalse(
            any(
                isinstance(
                    module,
                    self.torch.nn.modules.batchnorm._BatchNorm,
                )
                for module in model.modules()
            )
        )
        output = model(self.torch.rand((2, 3, 257, 172)))
        self.assertEqual(tuple(output.shape), (2,))

    def test_domain_balancing_weights_equalize_total_mass(self) -> None:
        metadata = [
            {
                "source_domain": domain,
                "expectation": "negative",
                "sample_rate": 48_000,
            }
            for domain, count in (("large", 6), ("small", 2))
            for _index in range(count)
        ]
        dataset = self.domain_trainer.DomainClipDataset(
            self.torch.zeros((8, 257, 172)),
            metadata,
            list(range(8)),
            augment=False,
            seed=1,
            mask_probability=0.0,
            level_shift_probability=0.0,
        )

        weights = self.domain_trainer.domain_balancing_weights(
            dataset,
            metadata,
        )

        self.assertAlmostEqual(sum(weights[:6]), 1.0)
        self.assertAlmostEqual(sum(weights[6:]), 1.0)


if __name__ == "__main__":
    unittest.main()
