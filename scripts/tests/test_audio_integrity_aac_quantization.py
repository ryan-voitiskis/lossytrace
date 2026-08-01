import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "evaluate-audio-integrity-aac-quantization.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audio_integrity_aac_quantization",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AacQuantizationEvaluationTests(unittest.TestCase):
    def external_corpus_fixture(self, root: Path):
        audio = root / "audio.flac"
        audio.write_bytes(b"lossless-fixture")
        case = {
            "case_id": "case-001",
            "source_group": "source-001",
            "relative_path": "audio.flac",
            "split": "held_out",
            "expectation": "negative",
        }
        (root / "manifest.json").write_text(
            json.dumps(
                {
                    "analysis_max_seconds": 30,
                    "cases": [case],
                }
            ),
            encoding="utf-8",
        )
        (root / "fingerprints.json").write_text(
            json.dumps(
                {
                    "case_sha256": {
                        "case-001": MODULE.sha256_file(audio),
                    }
                }
            ),
            encoding="utf-8",
        )
        (root / "seal.json").write_text(
            json.dumps(
                {
                    "state": "sealed_external_transfer_corpus",
                    "split": "held_out",
                    "release_heldout_labels_present": False,
                    "external_transfer_feature_scores_opened": False,
                    "release_gate_eligible": False,
                }
            ),
            encoding="utf-8",
        )

    def test_confusion_uses_strict_exclusive_boundary(self):
        rows = [
            {
                "state": "scored",
                "expectation": "negative",
                "aac_quantization_probability": 0.02,
            },
            {
                "state": "scored",
                "expectation": "controlled_positive",
                "aac_quantization_probability": 0.02,
            },
            {
                "state": "scored",
                "expectation": "controlled_positive",
                "aac_quantization_probability": 0.03,
            },
        ]
        result = MODULE.confusion(rows, 0.02)
        self.assertEqual(result["false_positives"], 0)
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(result["false_negatives"], 1)

    def test_summary_excludes_unsupported_cases_from_confusion(self):
        rows = [
            {
                "state": "unsupported_sample_rate",
                "expectation": "negative",
                "class": "pcm_16k",
            },
            {
                "state": "scored",
                "expectation": "negative",
                "class": "pcm_48k",
                "aac_quantization_probability": 0.04,
            },
            {
                "state": "scored",
                "expectation": "controlled_positive",
                "class": "aac",
                "aac_quantization_probability": 0.05,
            },
        ]
        result = MODULE.summarize(rows)
        self.assertEqual(result["unsupported_count"], 1)
        self.assertEqual(
            result["fixed_reference"]["false_positives"],
            1,
        )
        self.assertEqual(
            result["strict_zero_observed_false_positive"][
                "true_positives"
            ],
            1,
        )

    def test_summary_uses_selected_sampling_threshold(self):
        rows = [
            {
                "state": "scored",
                "expectation": "negative",
                "class": "pcm",
                "aac_quantization_probability": 0.018,
            },
            {
                "state": "scored",
                "expectation": "controlled_positive",
                "class": "aac",
                "aac_quantization_probability": 0.020,
            },
        ]
        result = MODULE.summarize(
            rows,
            MODULE.SAMPLING_THRESHOLDS[16],
        )
        self.assertEqual(
            result["fixed_reference"]["false_positives"],
            0,
        )
        self.assertEqual(
            result["fixed_reference"]["true_positives"],
            1,
        )

    def test_external_transfer_corpus_requires_explicit_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.external_corpus_fixture(root)
            with self.assertRaisesRegex(
                SystemExit,
                "development-only",
            ):
                MODULE.validate_corpus(root)
            commitment, cases, _ = MODULE.validate_corpus(
                root,
                external_transfer=True,
            )
            self.assertEqual(
                commitment["evaluation_kind"],
                "external_transfer",
            )
            self.assertEqual(len(cases), 1)

    def test_external_transfer_rejects_previously_opened_seal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.external_corpus_fixture(root)
            seal_path = root / "seal.json"
            seal = json.loads(seal_path.read_text(encoding="utf-8"))
            seal["external_transfer_feature_scores_opened"] = True
            seal_path.write_text(json.dumps(seal), encoding="utf-8")
            with self.assertRaisesRegex(
                SystemExit,
                "sealed external-transfer",
            ):
                MODULE.validate_corpus(
                    root,
                    external_transfer=True,
                )


if __name__ == "__main__":
    unittest.main()
