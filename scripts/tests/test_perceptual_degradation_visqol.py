from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
PLAN_PATH = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "visqol-synthetic-replay-plan.json"
)
WORKFLOW = ROOT / ".github" / "workflows" / "visqol-synthetic.yml"
PATCH = (
    ROOT
    / "research"
    / "toolchains"
    / "patches"
    / "visqol-v3.3.3-reproducible-workspace.patch"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURES = load_module(
    "perceptual_degradation_visqol_fixtures",
    SCRIPTS / "perceptual_degradation_visqol_fixtures.py",
)
VALIDATOR = load_module(
    "validate_perceptual_degradation_visqol_plan",
    SCRIPTS / "validate-perceptual-degradation-visqol-plan.py",
)
sys.path.insert(0, str(SCRIPTS))
REPLAY = load_module(
    "perceptual_degradation_visqol_replay",
    SCRIPTS / "perceptual_degradation_visqol_replay.py",
)


class VisqolSyntheticPlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))

    def test_frozen_plan_is_valid_and_synthetic_only(self) -> None:
        self.assertEqual([], VALIDATOR.validate(self.plan))
        self.assertTrue(
            self.plan["authorization"]["synthetic_fixture_execution"]
        )
        self.assertFalse(
            self.plan["authorization"]["public_or_retained_audio_execution"]
        )
        self.assertIsNone(self.plan["visqol"]["binary_sha256"])
        self.assertEqual(4, len(self.plan["prior_attempts"]))
        self.assertTrue(
            all(
                not attempt["completed_evidence_record"]
                for attempt in self.plan["prior_attempts"]
            )
        )
        self.assertFalse(self.plan["prior_attempts"][-1]["synthetic_scores_parsed"])

    def test_fixture_generation_is_byte_identical_and_bound(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lossytrace-visqol-test-a-") as a:
            first = FIXTURES.generate(Path(a) / "audio")
            with tempfile.TemporaryDirectory(prefix="lossytrace-visqol-test-b-") as b:
                second = FIXTURES.generate(Path(b) / "audio")
                self.assertEqual(first, second)
            self.assertEqual(self.plan["fixture_generation"], first)
            for name in first["files"]:
                with wave.open(str(Path(a) / "audio" / name), "rb") as value:
                    self.assertEqual(48_000, value.getframerate())
                    self.assertEqual(2, value.getnchannels())
                    self.assertEqual(384_000, value.getnframes())

    def test_generator_refuses_to_replace_fixture(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lossytrace-visqol-test-") as temp:
            output = Path(temp) / "audio"
            FIXTURES.generate(output)
            with self.assertRaisesRegex(ValueError, "refusing to replace"):
                FIXTURES.generate(output)

    def test_replay_strips_paths_and_replays_exactly(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lossytrace-visqol-fake-") as temp:
            root = Path(temp)
            binary = root / "visqol-fake"
            binary.write_text(
                """#!/usr/bin/env python3
import json
import sys
args = sys.argv[1:]
def value(flag):
    return args[args.index(flag) + 1]
print("fake diagnostic for " + value("--reference_file"), file=sys.stderr)
payload = {
    "moslqo": 4.25,
    "vnsim": 0.875,
    "fvnsim": [0.8, 0.9],
    "patchSims": [{"similarity": 0.75}, {"similarity": 1.0}],
    "referenceFilepath": value("--reference_file"),
    "degradedFilepath": value("--degraded_file"),
}
with open(value("--output_debug"), "w", encoding="utf-8") as output:
    json.dump(payload, output, sort_keys=True)
""",
                encoding="utf-8",
            )
            binary.chmod(0o755)
            model = root / "model.txt"
            model.write_bytes(b"synthetic test model\n")
            plan = copy.deepcopy(self.plan)
            plan["visqol"]["audio_model_sha256"] = hashlib.sha256(
                model.read_bytes()
            ).hexdigest()
            report = REPLAY.replay(binary, model, plan)
            self.assertEqual(
                "visqol_synthetic_replay_passed_not_human_truth", report["state"]
            )
            self.assertEqual(4, len(report["results"]))
            self.assertTrue(
                all(item["numeric_replay_identical"] for item in report["results"])
            )
            self.assertTrue(all(item["stderr_observed"] for item in report["results"]))
            self.assertNotIn(temp, json.dumps(report))
            self.assertFalse(report["synthetic_scores_are_human_truth"])
            self.assertFalse(report["threshold_selected"])
            self.assertFalse(report["public_verdict_enabled"])

    def test_replay_rejects_nonzero_metric_exit_without_stderr_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lossytrace-visqol-fail-") as temp:
            root = Path(temp)
            binary = root / "visqol-fail"
            binary.write_text(
                "#!/bin/sh\nprintf 'sensitive diagnostic' >&2\nexit 7\n",
                encoding="utf-8",
            )
            binary.chmod(0o755)
            with self.assertRaisesRegex(ValueError, "ViSQOL failed with exit status 7"):
                REPLAY._run_case(
                    binary,
                    root / "model",
                    root / "reference.wav",
                    root / "degraded.wav",
                    root / "output.json",
                )

    def test_workflow_is_pinned_bounded_and_branch_scoped(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("codex/perceptual-degradation", source)
        self.assertIn("ubuntu-22.04", source)
        self.assertIn("--jobs=6", source)
        self.assertIn("--local_cpu_resources=6", source)
        self.assertIn("--compilation_mode=opt", source)
        self.assertIn("timeout-minutes: 90", source)
        self.assertIn("Install hash-bound NumPy bootstrap", source)
        self.assertIn("if: always()", source)
        self.assertIn("actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803", source)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", source)

    def test_workspace_patch_replaces_both_movable_or_dead_tags(self) -> None:
        source = PATCH.read_text(encoding="utf-8")
        self.assertIn("703bd9caab50b139428cea1aaff9974ebee5742e", source)
        self.assertIn("215105818dfde3174fe799600bb0f3cae233d0bf", source)
        self.assertIn('-    tag = "20211102"', source)
        self.assertIn('+    commit = "215105818dfde3174fe799600bb0f3cae233d0bf"', source)
        self.assertIn("https://distfiles.macports.org/armadillo/armadillo-9.860.2.tar.xz", source)
        self.assertIn("d856ea58c18998997bcae6689784d2d3eeb5daf1379d569fddc277fe046a996b", source)

    def test_no_audio_or_model_file_is_tracked(self) -> None:
        tracked = subprocess.run(
            [
                "git",
                "ls-files",
                "*.wav",
                "*.flac",
                "*.mp3",
                "*.aac",
                "*.opus",
                "*.tflite",
                "*.model",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual("", tracked)


if __name__ == "__main__":
    unittest.main()
