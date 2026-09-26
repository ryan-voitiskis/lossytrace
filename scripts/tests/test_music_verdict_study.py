"""Synthetic metadata tests; no corpus access or detector claims."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "music_verdict_study.py"
SPEC = importlib.util.spec_from_file_location("music_verdict_study", SCRIPT)
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)


def inventory():
    rows = []
    for partition, count in study.PARTITIONS.items():
        for index in range(count):
            identity = f"{partition}-{index}"
            rows.append({
                "source_id": identity,
                "partition": partition,
                "artist_ids": ["artist-" + identity],
                "session_ids": ["session-" + identity],
                "lineage_ids": ["work-" + identity],
                "provider_id": f"eval-{index % 3}" if partition == "evaluation" else "dev",
                "audio_sha256": hashlib.sha256(identity.encode()).hexdigest(),
                "consumed": partition == "train",
                "sealed": False,
                "real_finished_music": True,
                "provenance_status": "qualified_pcm_chain",
                "rights_status": "research_and_weights_cleared",
                "provenance_refs": ["synthetic fixture, not a real attestation"],
                "rights_refs": ["synthetic fixture, not a license"],
            })
    return {"schema_version": 1, "sources": rows}


class BoundsTest(unittest.TestCase):
    def test_zero_events_matches_closed_form(self):
        for n in (1, 30, 45, 47, 100, 299, 300, 10000):
            self.assertAlmostEqual(study.exact_upper(0, n), 1 - 0.05 ** (1 / n))

    def test_minimum_independent_sample(self):
        self.assertEqual(study.zero_alert_sample_minimum(), 299)
        self.assertGreater(study.exact_upper(0, 298), 0.01)
        self.assertLessEqual(study.exact_upper(0, 299), 0.01)
        self.assertGreater(study.exact_upper(1, 300), 0.01)

    def test_known_small_exact_cases(self):
        self.assertAlmostEqual(study.exact_upper(1, 2), math.sqrt(0.95), places=12)
        self.assertAlmostEqual(study.exact_lower(2, 2), math.sqrt(0.05), places=12)
        self.assertEqual(study.exact_lower(0, 10), 0)
        self.assertEqual(study.exact_upper(10, 10), 1)

    def test_cdf_matches_direct_binomial_sum(self):
        for n in (3, 10, 30):
            for k in range(n + 1):
                p = 0.37
                expected = sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                               for i in range(k + 1))
                self.assertAlmostEqual(study.binomial_cdf(k, n, p), expected, places=12)

    def test_bounds_monotonic_and_inverse(self):
        values = [study.exact_upper(k, 40) for k in range(40)]
        self.assertEqual(values, sorted(values))
        for k in (1, 10, 20, 39):
            self.assertAlmostEqual(study.binomial_cdf(k, 40, values[k]), 0.05, places=10)
            self.assertAlmostEqual(study.exact_lower(k, 40), 1 - study.exact_upper(40 - k, 40))

    def test_invalid_counts_and_probabilities(self):
        for k, n in ((0, 0), (-1, 2), (3, 2), (True, 2), (1, 2.0)):
            with self.assertRaises(ValueError):
                study.exact_upper(k, n)
        for p in (-0.1, 1.1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                study.binomial_cdf(0, 2, p)
        for alpha in (0, 1, float("nan")):
            with self.assertRaises(ValueError):
                study.exact_lower(1, 2, alpha)


class InventoryTest(unittest.TestCase):
    def setUp(self):
        self.doc = inventory()

    def result(self):
        return study.audit_inventory(self.doc)

    def test_metadata_pass_is_not_execution_or_provenance_pass(self):
        result = self.result()
        self.assertEqual(result["state"], "metadata_checks_passed")
        self.assertFalse(result["execution_ready"])
        self.assertFalse(result["provenance_truth_verified_by_this_tool"])
        self.assertFalse(result["public_verdict_enabled"])
        self.assertEqual(result["groups_by_partition"], study.PARTITIONS)

    def test_empty_cannot_pass(self):
        self.doc["sources"] = []
        self.assertEqual(self.result()["state"], "metadata_checks_failed")

    def test_transitive_grouping_catches_cross_partition_leak(self):
        a, b, c = self.doc["sources"][0], self.doc["sources"][1], self.doc["sources"][-1]
        b["artist_ids"] += a["artist_ids"]
        c["session_ids"] += b["session_ids"]
        self.assertEqual(self.result()["errors"]["cross_partition_identity_component"], 1)

    def test_shared_hash_catches_renamed_recording(self):
        self.doc["sources"][-1]["audio_sha256"] = self.doc["sources"][0]["audio_sha256"]
        self.assertIn("cross_partition_identity_component", self.result()["errors"])

    def test_multiple_evaluation_tracks_do_not_inflate_groups(self):
        a, b = self.doc["sources"][-2:]
        b["artist_ids"] = a["artist_ids"]
        result = self.result()
        self.assertEqual(result["groups_by_partition"]["evaluation"], 299)
        self.assertIn("insufficient_evaluation_groups", result["errors"])
        self.assertIn("multiple_representatives_in_calibration_or_evaluation", result["errors"])

    def test_duplicate_id_rejected(self):
        self.doc["sources"].append(copy.deepcopy(self.doc["sources"][0]))
        self.assertIn("duplicate_source_id", self.result()["errors"])

    def test_unknown_or_sealed_cannot_be_negative(self):
        for field, value, error in (
            ("provenance_status", "wav_file", "unqualified_negative_provenance"),
            ("sealed", True, "historically_sealed_source"),
            ("real_finished_music", False, "outside_finished_music_population"),
            ("rights_status", "free_download", "unqualified_research_rights"),
            ("artist_ids", [], "invalid_or_missing_metadata"),
            ("artist_ids", ["a", "a"], "invalid_or_missing_metadata"),
            ("provenance_refs", [], "invalid_or_missing_metadata"),
            ("consumed", "false", "invalid_or_missing_metadata"),
        ):
            with self.subTest(field=field):
                doc = inventory()
                doc["sources"][0][field] = value
                self.assertIn(error, study.audit_inventory(doc)["errors"])

    def test_consumed_calibration_or_evaluation_rejected(self):
        for row in self.doc["sources"]:
            if row["partition"] in {"calibration", "evaluation"}:
                row["consumed"] = True
        self.assertEqual(self.result()["errors"]["consumed_calibration_or_evaluation"], 400)

    def test_research_only_does_not_clear_weight_release(self):
        self.doc["sources"][0]["rights_status"] = "research_only"
        result = self.result()
        self.assertEqual(result["state"], "metadata_checks_passed")
        self.assertFalse(result["weight_rights_asserted_cleared_for_all_rows"])

    def test_new_provider_is_required(self):
        for row in self.doc["sources"]:
            if row["partition"] != "evaluation":
                row["provider_id"] = "eval-" + str(int(row["source_id"].rsplit("-", 1)[1]) % 3)
        self.assertIn("no_wholly_held_out_evaluation_provider", self.result()["errors"])

    def test_provider_stratum_requirements(self):
        for row in self.doc["sources"]:
            if row["partition"] == "evaluation":
                row["provider_id"] = "one-eval-provider"
        self.doc["sources"][-1]["provider_id"] = "small-eval-provider"
        result = self.result()
        self.assertIn("insufficient_evaluation_provider_strata", result["errors"])
        self.assertIn("undersized_evaluation_provider_stratum", result["errors"])

    def test_private_identifiers_not_in_public_output(self):
        encoded = json.dumps(self.result())
        for row in self.doc["sources"]:
            for key in ("source_id", "audio_sha256", "provider_id"):
                self.assertNotIn(row[key], encoded)
            for value in row["artist_ids"]:
                self.assertNotIn(value, encoded)

    def test_unknown_fields_rejected(self):
        self.doc["sources"][0]["path"] = "/private/should/not/be/opened.wav"
        self.assertIn("invalid_row_schema", self.result()["errors"])

    def test_invalid_envelopes(self):
        for doc in (None, [], {}, {"schema_version": True, "sources": []},
                    {"schema_version": 1, "sources": [], "extra": None}):
            with self.assertRaises(ValueError):
                study.audit_inventory(doc)

    def test_shared_secondary_performer_is_a_group_edge(self):
        self.doc["sources"][0]["artist_ids"].append("shared-drummer")
        self.doc["sources"][-1]["artist_ids"].append("shared-drummer")
        self.assertIn("cross_partition_identity_component", self.result()["errors"])

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            json.loads('{"sealed": true, "sealed": false}', object_pairs_hook=study._unique_object)

    def test_cli_power_and_invalid_input_do_not_open_audio(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)["minimum_zero_alert_groups"], 299)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.json"
            path.write_text('{"private_path": "secret', encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "--inventory", str(path)],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("secret", result.stdout + result.stderr)
            self.assertNotIn(directory, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
