import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/evaluate-vamp-lossy-detector.py"
SPEC = importlib.util.spec_from_file_location("vamp_replay", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture_case():
    return {
        "case_id": "private-case-id",
        "source_group": "private-source-group",
        "partition_group": "private-partition-group",
        "source_domain": "fixture-domain",
        "split": "development",
        "provenance_tier": "synthetic",
        "class": "mp3_128",
        "expectation": "controlled_positive",
        "relative_path": "audio/fixture.wav",
    }


class VampReplayTests(unittest.TestCase):
    def test_parses_probabilities_and_applies_both_fixed_thresholds(self):
        probabilities = MODULE.parse_probabilities(
            "0.000: 0.49 Original\n1.000: 0.50 Lossy\n2.000: 0.90 Lossy\n"
        )
        result = MODULE.result_from_probabilities(
            fixture_case(), "a" * 64, probabilities
        )
        self.assertEqual(result["positive_window_fraction"], 2 / 3)
        self.assertTrue(result["detector_binary_label"])
        below = MODULE.result_from_probabilities(
            fixture_case(), "a" * 64, [0.1, 0.2, 0.3, 0.9]
        )
        self.assertTrue(below["detector_binary_label"])
        below = MODULE.result_from_probabilities(
            fixture_case(), "a" * 64, [0.1, 0.2, 0.3, 0.4]
        )
        self.assertFalse(below["detector_binary_label"])

    def test_rejects_missing_or_invalid_host_output(self):
        with self.assertRaisesRegex(ValueError, "no valid probabilities"):
            MODULE.parse_probabilities("not detector output")
        with self.assertRaisesRegex(ValueError, "no valid probabilities"):
            MODULE.parse_probabilities("0.000: 1.5 Lossy")

    def test_resume_binds_manifest_tools_case_and_audio_without_running_host(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audio = root / "audio/fixture.wav"
            audio.parent.mkdir()
            audio.write_bytes(b"deterministic fixture")
            partials = root / "partials"
            partials.mkdir()
            case = fixture_case()
            audio_sha256 = MODULE.sha256_file(audio)
            run_binding = {
                "manifest_sha256": "b" * 64,
                "detector": {"revision": MODULE.EXPECTED_REVISION},
            }
            result = MODULE.result_from_probabilities(
                case, audio_sha256, [0.2, 0.6, 0.7, 0.8]
            )
            MODULE.write_new(
                MODULE.partial_path(partials, case["case_id"]),
                {
                    "schema_version": 1,
                    "run_binding": run_binding,
                    "case_binding_sha256": MODULE.case_binding(case, audio_sha256),
                    "result": result,
                },
            )
            stderr = StringIO()
            with redirect_stderr(stderr):
                resumed = MODULE.evaluate_or_resume_case(
                    1,
                    1,
                    case,
                    root=root,
                    host=root / "host-does-not-run",
                    vamp_path=root,
                    plugin_key=MODULE.EXPECTED_PLUGIN_KEY,
                    run_binding=run_binding,
                    partial_directory=partials,
                )
            self.assertEqual(resumed, result)
            self.assertNotIn(case["case_id"], stderr.getvalue())
            self.assertNotIn(case["source_group"], stderr.getvalue())

    def test_resume_rejects_changed_audio_or_run_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audio = root / "audio/fixture.wav"
            audio.parent.mkdir()
            audio.write_bytes(b"first")
            partials = root / "partials"
            partials.mkdir()
            case = fixture_case()
            audio_sha256 = MODULE.sha256_file(audio)
            run_binding = {"manifest_sha256": "b" * 64}
            MODULE.write_new(
                MODULE.partial_path(partials, case["case_id"]),
                {
                    "schema_version": 1,
                    "run_binding": run_binding,
                    "case_binding_sha256": MODULE.case_binding(case, audio_sha256),
                    "result": MODULE.result_from_probabilities(
                        case, audio_sha256, [0.1]
                    ),
                },
            )
            audio.write_bytes(b"second")
            with self.assertRaisesRegex(ValueError, "partial binding differs"):
                MODULE.evaluate_or_resume_case(
                    1,
                    1,
                    case,
                    root=root,
                    host=root / "unused",
                    vamp_path=root,
                    plugin_key=MODULE.EXPECTED_PLUGIN_KEY,
                    run_binding=run_binding,
                    partial_directory=partials,
                )

    def test_manifest_gate_rejects_heldout_or_missing_boundary(self):
        manifest = {
            "evidence_partition": "observed_development",
            "holdout_scores_opened": False,
            "cases": [fixture_case()],
        }
        self.assertEqual(MODULE.validate_manifest(manifest, False), manifest["cases"])
        manifest["holdout_scores_opened"] = True
        with self.assertRaisesRegex(ValueError, "observed-development"):
            MODULE.validate_manifest(manifest, False)
        legacy = {"cases": [fixture_case()]}
        legacy["cases"][0]["split"] = "held_out"
        with self.assertRaisesRegex(ValueError, "held-out"):
            MODULE.validate_manifest(legacy, True)

    def test_partial_filename_does_not_expose_case_identity(self):
        path = MODULE.partial_path(Path("partials"), "private-case-id")
        self.assertNotIn("private-case-id", path.name)
        self.assertEqual(len(path.stem), 64)


if __name__ == "__main__":
    unittest.main()
