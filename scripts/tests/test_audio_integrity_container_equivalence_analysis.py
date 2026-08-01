import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "analyze-audio-integrity-container-equivalence.py"
)
SPEC = importlib.util.spec_from_file_location("container_equivalence_analysis", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ContainerEquivalenceAnalysisTest(unittest.TestCase):
    def test_difference_summary_is_path_free_and_deterministic(self):
        summary = MODULE.summarize_differences([0.0, 0.25, 0.5], 1, 4)
        self.assertEqual(summary["pair_count"], 4)
        self.assertEqual(summary["null_mismatch_count"], 1)
        self.assertEqual(summary["maximum_absolute_difference"], 0.5)

    def test_empty_numeric_pairs_remain_explicit(self):
        summary = MODULE.summarize_differences([], 2, 2)
        self.assertIsNone(summary["p99_absolute_difference"])
        self.assertEqual(summary["null_mismatch_count"], 2)

    def test_wrapper_only_contract_is_explicit_for_unsupported_original(self):
        manifest = {
            "lossy_original_analysis": {
                "opus_96": {
                    "included": False,
                    "omission_reason": "decoder_has_no_opus_codec",
                }
            }
        }
        contract = MODULE.comparison_contract(manifest, "opus_96")
        self.assertEqual(contract["reference_role"], "lossless_flac16")
        self.assertEqual(
            contract["comparison_roles"],
            ("lossless_wav16", "lossless_aiff16"),
        )
        self.assertNotIn("lossy_original", contract["expected_roles"])

    def test_supported_original_contract_uses_every_lossless_wrapper(self):
        manifest = {
            "lossy_original_analysis": {
                "mp3_128": {"included": True, "omission_reason": None}
            }
        }
        contract = MODULE.comparison_contract(manifest, "mp3_128")
        self.assertEqual(contract["reference_role"], "lossy_original")
        self.assertEqual(contract["comparison_roles"], MODULE.WRAPPER_ROLES)
        self.assertIn("lossy_original", contract["expected_roles"])


if __name__ == "__main__":
    unittest.main()
