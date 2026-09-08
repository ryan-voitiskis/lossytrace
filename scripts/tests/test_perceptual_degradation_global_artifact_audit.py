"""Constructed readback boundaries; no real audio or native execution."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import perceptual_degradation_global_artifact_audit as A
import perceptual_degradation_global_qualification as Q
import test_perceptual_degradation_global_qualification as fixtures


class GlobalArtifactAuditTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.run = Path(self.directory.name)/"run"
        self.run.mkdir(mode=0o700)
        (self.run/"kernel").mkdir(mode=0o700)
        self.binary = self.run/"kernel/correlation.dylib"
        self.binary.write_bytes(b"constructed inert library fixture")
        self.binary.chmod(0o500)
        self.rounds = fixtures.WorkloadQualificationTest().rounds()
        self.execution = {"head": A.HEAD, "plan_sha256": A.PLAN_SHA,
                          "kernel": {**Q.load_plan()["native_build"], "binary_sha256": hashlib.sha256(self.binary.read_bytes()).hexdigest()},
                          "synthetic_only": True, "locally_preregistered": True, "externally_preregistered": False}
        self.save()

    def save(self):
        records = {"execution.json": self.execution, "round-1.json": self.rounds[0], "round-2.json": self.rounds[1],
                   "result.json": Q.aggregate(self.rounds, ["passed"]*4)}
        for name, value in records.items():
            (self.run/name).write_bytes(A.canonical(value))
            (self.run/name).chmod(0o600)

    def audit(self, **kwargs):
        def git(args, **options):
            return A.HEAD.encode() if "rev-parse" in args else b""
        with patch.object(A.subprocess, "check_output", side_effect=git), \
                patch.object(A, "construction_hash", return_value="b"*64):
            return A.audit(Q.ROOT, self.run, **kwargs)

    def test_saved_readback_passes_without_native_or_waveform_io(self):
        with patch.object(Q.native, "Kernel", side_effect=AssertionError("native forbidden")), \
                patch.object(Q, "measure", side_effect=AssertionError("alignment forbidden")):
            result = self.audit(first_sha=A.sha((self.run/"round-1.json").read_bytes()))
        self.assertTrue(result["independent_saved_artifact_audit_passed"])
        self.assertEqual(16, result["recorded_input_hashes_verified"])
        self.assertTrue(result["first_round_snapshot_matched"])

    def test_small_independent_construction_hashes_match(self):
        for family in Q.FAMILIES:
            for frames in (1, 2, 11, 97):
                self.assertEqual(Q.input_hash(Q.fixture(family, frames)), A.construction_hash(family, frames))

    def test_technical_negative_is_auditable(self):
        self.rounds[0][1]["wall_seconds"] = 120.001
        self.save()
        result = self.audit()
        self.assertTrue(result["independent_saved_artifact_audit_passed"])
        self.assertEqual("synthetic_workload_negative_or_incomplete", result["public_result"]["state"])

    def test_extra_retained_entry_rejected(self):
        (self.run/"unplanned.txt").write_text("constructed extra")
        with self.assertRaises(AssertionError):
            self.audit()

    def test_changed_native_binary_rejected(self):
        self.binary.chmod(0o600)
        self.binary.write_bytes(b"changed constructed fixture")
        self.binary.chmod(0o500)
        with self.assertRaises(AssertionError):
            self.audit()

    def test_wrong_first_snapshot_or_source_hash_rejected(self):
        with self.assertRaises(AssertionError):
            self.audit(first_sha="0"*64)
        self.rounds[0][0]["input_sha256"] = "c"*64
        self.save()
        with self.assertRaises(AssertionError):
            self.audit()

    def test_fabricated_result_rejected(self):
        result = json.loads((self.run/"result.json").read_bytes())
        result["codec_executed"] = True
        (self.run/"result.json").write_bytes(A.canonical(result))
        with self.assertRaises(AssertionError):
            self.audit()

    def test_missing_slot_and_wrong_file_mode_rejected(self):
        changed = copy.deepcopy(self.rounds[0])
        changed.pop()
        (self.run/"round-1.json").write_bytes(A.canonical(changed))
        with self.assertRaises(AssertionError):
            self.audit()
        self.save()
        (self.run/"round-1.json").chmod(0o644)
        with self.assertRaises(AssertionError):
            self.audit()

    def test_symlink_report_rejected(self):
        original = self.run/"round-1.json"
        target = Path(self.directory.name)/"saved.json"
        original.rename(target)
        original.symlink_to(target)
        with self.assertRaises(AssertionError):
            self.audit()


if __name__ == "__main__":
    unittest.main()
