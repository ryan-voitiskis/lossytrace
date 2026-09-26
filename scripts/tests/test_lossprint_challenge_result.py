import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from audio_integrity_v2_baseline_common import assert_public_path_free


class ChallengeResultTests(unittest.TestCase):
    def setUp(self):
        directory = ROOT / "research/baselines/lossprint/evidence"
        self.result_path = directory / "challenge-result-20260927-001.json"
        self.result = json.loads(self.result_path.read_text())
        self.audit = json.loads((directory / "challenge-audit-20260927-001.json").read_text())

    def test_audit_binds_exact_result_and_auditor(self):
        self.assertEqual(self.audit["aggregate_sha256"], hashlib.sha256(self.result_path.read_bytes()).hexdigest())
        self.assertEqual(self.audit["auditor_sha256"], hashlib.sha256((ROOT / "scripts/audit_lossprint_challenge.py").read_bytes()).hexdigest())
        self.assertEqual(self.audit["private_records_sha256"], self.result["private_records_sha256"])
        self.assertTrue(self.audit["passed"])

    def test_failure_is_preserved_despite_technical_success(self):
        self.assertTrue(self.result["technical_passed"])
        self.assertFalse(self.result["continuation_passed"])
        self.assertEqual(self.result["status_counts"], {"supported": 1386})
        self.assertFalse(self.result["public_verdict_enabled"])
        self.assertFalse(self.result["independent_validation"])

    def test_primary_counts_match_independent_audit(self):
        for key in ("false_alert_cases", "detected_positive_cases", "family_correct_detected_cases"):
            self.assertEqual(self.result["case_metrics"][key], self.audit[key])
        self.assertEqual(sum(d["negative_alert_groups"] for d in self.result["domains"].values()), 6)
        self.assertEqual(sum(not d["continuation_passed"] for d in self.result["domains"].values()), 4)

    def test_counts_keep_case_denominators_and_bitrate_unavailability(self):
        self.assertEqual(self.result["case_metrics"]["positive_cases"], 381)
        self.assertEqual(self.result["case_metrics"]["negative_cases"], 336)
        self.assertEqual(self.result["bitrate"]["eligible_cases"], 0)
        self.assertIsNone(self.result["bitrate"]["accuracy"])

    def test_public_outputs_exclude_source_identities(self):
        assert_public_path_free(self.result)
        assert_public_path_free(self.audit)


if __name__ == "__main__":
    unittest.main()
