import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/run-audio-integrity-codec-projection.py"
CONFIG_PATH = ROOT / "research/codec-projection/oracle-v1/config.json"
SPEC = importlib.util.spec_from_file_location("codec_projection_runner", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def negative(index: int) -> dict:
    group = index % MODULE.EXPECTED_NEGATIVE_GROUPS
    return {
        "case_id": f"negative-{index:04d}",
        "relative_path": f"audio/negative-{index:04d}.flac",
        "expectation": "negative",
        "class": "pcm",
        "source_group": f"negative-group-{group:03d}",
        "partition_group": f"negative-group-{group:03d}",
        "source_domain": "negative-domain",
        "provenance_tier": "tier_a_confirmed_pcm",
    }


def positive(index: int) -> dict:
    return {
        "case_id": f"positive-{index:04d}",
        "relative_path": f"audio/positive-{index:04d}.flac",
        "expectation": "controlled_positive",
        "class": "fixture_mp3_128_to_flac16",
        "source_group": f"positive-group-{index:03d}",
        "partition_group": f"positive-group-{index:03d}",
        "source_domain": "positive-domain",
        "provenance_tier": "tier_a_confirmed_pcm",
    }


class CodecProjectionRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = MODULE.load_and_validate_config(CONFIG_PATH)

    def test_frozen_selection_has_exact_inventory_and_stable_order(self):
        rows = [positive(index) for index in range(MODULE.EXPECTED_POSITIVE_CASES)]
        rows += [negative(index) for index in range(MODULE.EXPECTED_NEGATIVE_CASES)]
        rows += [
            {
                "case_id": "aac-control",
                "relative_path": "audio/aac-control.flac",
                "expectation": "controlled_positive",
                "class": "aac_lc_128",
                "source_group": "aac-control",
                "partition_group": "aac-control",
                "source_domain": "positive-domain",
                "provenance_tier": "tier_a_confirmed_pcm",
            }
        ]
        selected = MODULE.select_cases(list(reversed(rows)), self.config)
        self.assertEqual(len(selected), MODULE.EXPECTED_TOTAL_CASES)
        self.assertEqual(
            [row["case_id"] for row in selected],
            sorted(row["case_id"] for row in selected),
        )
        self.assertNotIn("aac-control", {row["case_id"] for row in selected})

    def test_canonical_json_is_byte_stable(self):
        first = MODULE.canonical_json({"z": [2, 1], "a": {"b": False}})
        second = MODULE.canonical_json({"a": {"b": False}, "z": [2, 1]})
        self.assertEqual(first, second)
        self.assertEqual(json.loads(first), {"a": {"b": False}, "z": [2, 1]})
        self.assertTrue(first.endswith(b"\n"))

    def test_resume_commitment_binds_case_metadata_and_audio(self):
        case = {
            "case_id": "case-a",
            "source_group": "group-a",
            "partition_group": "partition-a",
            "source_domain": "domain-a",
            "class": "pcm",
            "expectation": "negative",
            "provenance_tier": "tier_a_confirmed_pcm",
        }
        first = MODULE.commitment_for(case, "a" * 64, {"config_sha256": "b" * 64})
        second = MODULE.commitment_for(case, "a" * 64, {"config_sha256": "b" * 64})
        self.assertEqual(first, second)
        changed = MODULE.commitment_for(case, "c" * 64, {"config_sha256": "b" * 64})
        self.assertNotEqual(first, changed)

    def test_supported_measurement_requires_bounded_scores(self):
        measurement = {
            "schema_version": 1,
            "state": "codec_projection_raw_case_v1",
            "feature_version": 0,
            "public_verdict_enabled": False,
            "case_id": "case-a",
            "algorithm": self.config["algorithm"],
            "projection_performed": True,
            "support": {
                "supported": True,
                "supported_measurement_block_count": 1,
            },
            "scores": {
                "r1_cycle_residual_retention": 0.5,
                "r1_interquartile_range": 0.0,
                "r1_equivalent_db_median": 0.0,
                "r2_residual_directional_recurrence": 0.6,
                "r2_interquartile_range": 0.0,
            },
            "blocks": [
                {
                    "block_index": 0,
                    "signal_power": 0.1,
                    "first_residual_power": 0.01,
                    "second_residual_power": 0.01,
                    "r1_cycle_residual_retention": 0.5,
                    "r1_equivalent_db": 0.0,
                    "r2_residual_directional_recurrence": 0.6,
                }
            ],
        }
        MODULE.validate_measurement("case-a", measurement, self.config["algorithm"])
        measurement["scores"]["r1_cycle_residual_retention"] = 1.1
        with self.assertRaisesRegex(ValueError, "out of bounds"):
            MODULE.validate_measurement(
                "case-a", measurement, self.config["algorithm"]
            )


if __name__ == "__main__":
    unittest.main()
