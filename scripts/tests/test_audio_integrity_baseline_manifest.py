import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/compose-audio-integrity-baseline-manifest.py"
SPEC = importlib.util.spec_from_file_location("baseline_manifest", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BaselineManifestTests(unittest.TestCase):
    def write_components(self, root: Path) -> None:
        group_layout = {
            "audio-integrity-private-compact-training-20260731-001": (40, "private"),
            "audio-integrity-nsynth-sparse-training-20260731-001": (200, "nsynth-train"),
            "audio-integrity-public-tier-a-development-negatives-20260730-001": (48, "public-tier-a"),
            "audio-integrity-public-tier-a-controlled-transcodes-20260730-001": (48, "public-tier-a"),
            "audio-integrity-nsynth-hard-negatives-v1": (53, "nsynth-test"),
            "audio-integrity-external-transfer-sqam-20260731-001": (70, "sqam"),
            "audio-integrity-musdb18hq-controlled-20260731-001": (150, "musdb"),
            "audio-integrity-independent-controlled-v29-20260731-001": (36, "independent"),
        }
        for component in MODULE.COMPONENTS:
            manifest_path = root / component.relative_manifest
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            cases = []
            group_count, group_namespace = group_layout[component.corpus_id]
            for index in range(component.expected_cases):
                case_id = f"{component.source_domain}-{index:04d}"
                source_group = f"{group_namespace}-{index % group_count:04d}"
                cases.append(
                    {
                        "case_id": case_id,
                        "source_group": source_group,
                        "partition_group": source_group,
                        "relative_path": f"audio/{case_id}.flac",
                        "class": "fixture",
                        "split": "held_out" if index == 0 else "development",
                        "provenance_tier": "tier_a_confirmed_pcm",
                        "expectation": "negative",
                    }
                )
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "corpus_id": component.corpus_id,
                        "cases": cases,
                    }
                ),
                encoding="utf-8",
            )

    def test_compose_relabels_consumed_splits_and_keeps_paths_relative(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_components(root)
            manifest = MODULE.compose(root)
        self.assertEqual(len(manifest["cases"]), MODULE.EXPECTED_CASES)
        self.assertTrue(all(case["split"] == "development" for case in manifest["cases"]))
        self.assertTrue(
            all(case["evidence_partition"] == "observed_development" for case in manifest["cases"])
        )
        self.assertTrue(
            all(not Path(case["relative_path"]).is_absolute() for case in manifest["cases"])
        )
        self.assertFalse(manifest["holdout_scores_opened"])

    def test_compose_rejects_component_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_components(root)
            first = MODULE.COMPONENTS[0]
            manifest_path = root / first.relative_manifest
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["corpus_id"] = "unexpected"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected corpus_id"):
                MODULE.compose(root)


if __name__ == "__main__":
    unittest.main()
