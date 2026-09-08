"""Constructed saved-artifact audits; no real codec, native build or audio."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import perceptual_degradation_digital_canary_v5 as M
import perceptual_degradation_digital_canary_v5_artifact_audit as A
import test_perceptual_degradation_digital_canary_v5 as fixtures


class ArtifactAuditTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CanaryTest()
        self.fixture.setUp()
        self.plan = {**M.load_plan(), "cohort": copy.deepcopy(self.fixture.plan["cohort"])}
        self.bound = patch.object(M, "load_plan", return_value=self.plan)
        self.bound.start()
        M.claim_launch(self.fixture.parent, "e" * 40, "7")
        self.run = self.fixture.parent / "saved"
        self.run.mkdir()
        (self.run / "kernel").mkdir()
        kernel = b"constructed hash-only kernel fixture; never executable"
        (self.run / "kernel/correlation.dylib").write_bytes(kernel)
        self.replays = [self.fixture.replay(), self.fixture.replay()]
        self.execution = {"head": "e" * 40, "ci_run_id": "7",
                          "proposal_sha256": hashlib.sha256(M.PLAN.read_bytes()).hexdigest(),
                          "selected_source": self.fixture.source,
                          "kernel": {**self.plan["native_build"], "binary_sha256": hashlib.sha256(kernel).hexdigest()}}
        (self.run / "execution.json").write_bytes(A.canonical(self.execution))
        (self.run / "attribution.json").write_bytes((self.fixture.root / "attribution.json").read_bytes())
        self.save_reports()

    def tearDown(self):
        self.bound.stop()
        self.fixture.tearDown()

    def save_reports(self):
        for i, replay in enumerate(self.replays, 1):
            (self.run / f"replay-{i}.json").write_bytes(A.canonical(replay))
        report = M.summarize(self.replays)
        (self.run / "public-projection.json").write_bytes(A.canonical(report))

    def audit(self):
        return A.audit(M, self.run, self.fixture.root, "7", "e" * 40)

    def test_saved_readback_opens_only_selected_waveform(self):
        real_read, opened = Path.read_bytes, []
        def read(path):
            if path.suffix == ".wav":
                opened.append(path)
            return real_read(path)
        with patch.object(Path, "read_bytes", autospec=True, side_effect=read):
            result = self.audit()
        self.assertTrue(result["independent_artifact_audit_passed"])
        self.assertTrue(result["exact_retention_boundary_passed"])
        self.assertEqual([self.fixture.root / self.fixture.source["relative_path"]], opened)
        self.assertFalse(result["other_15_waveforms_read_by_auditor"])

    def test_extra_retained_entry_rejected(self):
        (self.run / "unplanned.txt").write_text("constructed extra fixture")
        with self.assertRaises(AssertionError):
            self.audit()

    def test_symlink_report_rejected(self):
        target = self.run / "replay-1.json"
        data = target.read_bytes()
        target.unlink()
        other = self.fixture.base / "report-fixture.json"
        other.write_bytes(data)
        target.symlink_to(other)
        with self.assertRaises(AssertionError):
            self.audit()

    def test_kernel_hash_change_rejected(self):
        (self.run / "kernel/correlation.dylib").write_bytes(b"changed constructed fixture")
        with self.assertRaises(AssertionError):
            self.audit()

    def test_selected_source_drift_rejected(self):
        source = self.fixture.root / self.fixture.source["relative_path"]
        data = source.read_bytes()
        source.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
        with self.assertRaises(AssertionError):
            self.audit()

    def test_saved_projection_change_rejected(self):
        path = self.run / "public-projection.json"
        projection = json.loads(path.read_bytes())
        projection["perceptual_support"] = True
        path.write_bytes(A.canonical(projection))
        with self.assertRaises(AssertionError):
            self.audit()

    def test_changed_codec_hash_is_preserved_as_nonrepeatable_result(self):
        self.replays[1]["cases"][2]["encoded_sha256"] = "d" * 64
        self.save_reports()
        result = self.audit()
        self.assertFalse(result["public_projection"]["deterministic_evidence_byte_identical"])
        self.assertEqual("bounded_canary_negative_or_incomplete", result["public_projection"]["state"])

    def test_missing_condition_rejected(self):
        changed = copy.deepcopy(self.replays[0])
        changed["cases"].pop()
        (self.run / "replay-1.json").write_bytes(A.canonical(changed))
        with self.assertRaises(AssertionError):
            self.audit()

    def test_source_identity_replacement_rejected(self):
        changed = copy.deepcopy(self.execution)
        changed["selected_source"] = self.fixture.records[0]
        (self.run / "execution.json").write_bytes(A.canonical(changed))
        with self.assertRaises(AssertionError):
            self.audit()

    def test_global_fallback_is_preserved_and_cannot_pass_primary_gate(self):
        self.replays[0]["cases"][0]["native_global_audit"]["fallback_candidates"] = 1
        self.save_reports()
        result = self.audit()["public_projection"]
        self.assertFalse(result["no_native_fallback_all_cases"])
        self.assertFalse(result["primary_technical_gate_passed"])
        self.assertEqual(1, result["replays"][0]["global_fallback_candidates"])

    def test_global_geometry_evidence_is_not_excluded_from_repeatability(self):
        self.replays[1]["cases"][0]["native_global_audit"]["geometry_sha256"] = "f"*64
        self.save_reports()
        self.assertFalse(self.audit()["public_projection"]["deterministic_evidence_byte_identical"])

    def test_launch_marker_tamper_or_missing_marker_rejected(self):
        marker = self.run.parent / (M.PROPOSAL_ID + ".launch.json")
        marker.write_bytes(A.canonical({"automatic_retry_authorized": True}))
        with self.assertRaises(AssertionError):
            self.audit()
        marker.unlink()
        with self.assertRaises(AssertionError):
            self.audit()


if __name__ == "__main__":
    unittest.main()
