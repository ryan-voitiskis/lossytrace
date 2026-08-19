from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_source_trait_sparse_non_tonal_clean_capture_live_intake.py"
SPEC = importlib.util.spec_from_file_location("clean_capture_live_intake", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CleanCaptureLiveIntakeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)
        base = MODULE._load_module(
            MODULE._bound(cls.plan, "synthetic_intake_implementation"),
            "clean_capture_intake_test_base",
        )
        cls.manifest = copy.deepcopy(base.load_json(base.FIXTURE_PATH))
        cls.manifest["synthetic_fixture"] = False
        cls.manifest_bytes = MODULE.canonical_json_bytes(cls.manifest)

    def test_plan_and_predecessor_bindings_validate(self) -> None:
        self.assertEqual([], MODULE.validate_plan(self.plan))

    def test_valid_live_manifest_passes_all_eight_gates_without_audio(self) -> None:
        report = MODULE.build_private_report(self.plan, self.manifest, self.manifest_bytes)
        self.assertTrue(report["decision"]["live_delivery_metadata_accepted"])
        self.assertEqual(8, report["execution"]["gate_pass_count"])
        self.assertEqual(0, report["execution"]["audio_file_open_attempt_count"])
        self.assertFalse(report["audio_accessed"])
        self.assertTrue(all(not values for values in report["gate_errors"].values()))

    def test_public_projection_excludes_private_bindings_errors_and_manifest_values(self) -> None:
        private = MODULE.build_private_report(self.plan, self.manifest, self.manifest_bytes)
        public = MODULE.build_public_projection(self.plan, private)
        serialized = json.dumps(public, sort_keys=True)
        self.assertNotIn("private_input_binding", public)
        self.assertNotIn("gate_errors", public)
        for forbidden in (
            private["private_input_binding"]["manifest_sha256"],
            self.manifest["exact_member_id"],
            self.manifest["source_group_id"],
            self.manifest["file"]["logical_name"],
            self.manifest["file"]["sha256"],
            self.manifest["rights"]["rights_holder_identity"],
            self.manifest["capture"]["location_and_room_description"],
            self.manifest["capture"]["channels"][0]["microphone_make_model"],
        ):
            self.assertNotIn(forbidden, serialized)

    def test_manifest_tamper_rejects_without_raising_or_opening_audio(self) -> None:
        tampered = copy.deepcopy(self.manifest)
        tampered["processing"]["transformations"] = ["normalization"]
        tampered["capture"]["safe_non_hazardous_event_confirmed"] = False
        payload = MODULE.canonical_json_bytes(tampered)
        report = MODULE.build_private_report(self.plan, tampered, payload)
        self.assertFalse(report["decision"]["live_delivery_metadata_accepted"])
        self.assertFalse(report["gates"]["transformation_history"])
        self.assertFalse(report["gates"]["safety_declaration"])
        self.assertEqual(0, report["execution"]["audio_file_open_attempt_count"])

    def test_private_loader_requires_absolute_external_regular_non_synthetic_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_bytes(self.manifest_bytes)
            loaded, payload = MODULE.load_private_live_manifest(manifest, self.plan)
            self.assertEqual(self.manifest, loaded)
            self.assertEqual(self.manifest_bytes, payload)

            with self.assertRaisesRegex(ValueError, "absolute"):
                MODULE.load_private_live_manifest(Path("manifest.json"), self.plan)

            symlink = root / "manifest-link.json"
            symlink.symlink_to(manifest)
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                MODULE.load_private_live_manifest(symlink, self.plan)

            synthetic = root / "synthetic.json"
            synthetic.write_text(
                json.dumps({**self.manifest, "synthetic_fixture": True}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "synthetic_fixture false"):
                MODULE.load_private_live_manifest(synthetic, self.plan)

    def test_repository_manifest_and_output_paths_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_bytes(self.manifest_bytes)
            with self.assertRaisesRegex(ValueError, "outside the repository"):
                MODULE.load_private_live_manifest(manifest, self.plan)
            with self.assertRaisesRegex(ValueError, "outside the repository"):
                MODULE._validate_private_output_path(Path(directory) / "report.json", must_exist=False)

    def test_cli_produces_two_byte_identical_private_replays_and_checks_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            replay_one = root / "replay-one.json"
            replay_two = root / "replay-two.json"
            manifest.write_bytes(self.manifest_bytes)
            for output in (replay_one, replay_two):
                completed = subprocess.run(
                    [sys.executable, str(SCRIPT), "--manifest", str(manifest), "--private-output", str(output)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
                self.assertIn("accepted", completed.stdout)
            self.assertEqual(replay_one.read_bytes(), replay_two.read_bytes())
            checked = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--manifest",
                    str(manifest),
                    "--private-output",
                    str(replay_one),
                    "--check",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, checked.returncode, checked.stdout + checked.stderr)
            self.assertIn("validated", checked.stdout)

    def test_cli_without_live_manifest_fails_closed(self) -> None:
        completed = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)
        self.assertNotEqual(0, completed.returncode)

    def test_authority_and_binding_tamper_fail_closed(self) -> None:
        tampered = copy.deepcopy(self.plan)
        tampered["authority_received"]["outreach_authorized"] = True
        tampered["bindings"]["objective_audit"]["sha256"] = "0" * 64
        errors = MODULE.validate_plan(tampered)
        self.assertIn("received authority differs", errors)
        self.assertIn("binding hash differs: objective_audit", errors)


if __name__ == "__main__":
    unittest.main()
