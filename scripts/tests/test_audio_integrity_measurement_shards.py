import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_script(module_name, file_name):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "scripts" / file_name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SHARD = load_script("measurement_shard", "shard-audio-integrity-manifest.py")
COMBINE = load_script("measurement_combine", "combine-audio-integrity-measurement-shards.py")
RUN = load_script("measurement_run", "run-audio-integrity-shards.py")


class MeasurementShardTests(unittest.TestCase):
    def manifest(self):
        return {
            "schema_version": 1,
            "corpus_id": "fixture",
            "corpus_version": 1,
            "analysis_max_seconds": 30,
            "repetitions": 1,
            "cases": [
                {
                    "case_id": f"case-{index}",
                    "source_group": f"group-{index // 2}",
                }
                for index in range(40)
            ],
        }

    def report(self, manifest):
        return {
            "schema_version": 1,
            "corpus_id": manifest["corpus_id"],
            "feature_version": 0,
            "runner_sha256": "runner",
            "harness_sha256": "harness",
            "gate_disposition": {"likely_lossy_derived_enabled": False},
            "results": [
                {
                    "case_id": case["case_id"],
                    "runner": {
                        "runtime_overhead_percent": 1.0,
                        "research_transform_grid_enabled": False,
                        "research_transform_grid_profile": None,
                        "transform_grid_probe": None,
                    },
                }
                for case in manifest["cases"]
            ],
        }

    def test_shards_keep_source_groups_intact_and_combine_exactly(self):
        full = self.manifest()
        shards = SHARD.shard_manifest(full, 4)
        locations = {}
        combine_input = []
        for index, shard in enumerate(shards):
            for case in shard["cases"]:
                prior = locations.setdefault(case["source_group"], index)
                self.assertEqual(prior, index)
            combine_input.append(
                (
                    Path(f"manifest-{index}.json"),
                    shard,
                    Path(f"report-{index}.json"),
                    self.report(shard),
                )
            )
        original_hash = COMBINE.sha256_file
        COMBINE.sha256_file = lambda path: path.name
        try:
            combined = COMBINE.combine(full, combine_input)
        finally:
            COMBINE.sha256_file = original_hash
        self.assertEqual(len(combined["results"]), len(full["cases"]))
        self.assertFalse(combined["gate_disposition"]["likely_lossy_derived_enabled"])

    def test_resume_validation_rejects_case_drift(self):
        manifest = self.manifest()
        report = self.report(manifest)
        RUN.validate_report(manifest, report)
        report["results"].pop()
        with self.assertRaisesRegex(ValueError, "cases differ"):
            RUN.validate_report(manifest, report)


if __name__ == "__main__":
    unittest.main()
