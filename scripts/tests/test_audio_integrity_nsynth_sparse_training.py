import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "stage-audio-integrity-nsynth-sparse-training.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audio_integrity_nsynth_sparse_training",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def instrument_notes(instrument, family, source):
    return [
        {
            "note_name": f"{instrument}-{index}",
            "instrument": instrument,
            "instrument_family": family,
            "instrument_source": source,
        }
        for index in range(MODULE.NOTES_PER_INSTRUMENT)
    ]


class NsynthSparseTrainingTests(unittest.TestCase):
    def test_subset_is_deterministic_and_covers_every_stratum(self):
        selected = {}
        instrument = 1
        for family in ("bass", "brass", "string"):
            for source in ("acoustic", "synthetic"):
                for _ in range(4):
                    selected[instrument] = instrument_notes(
                        instrument,
                        family,
                        source,
                    )
                    instrument += 1
        first = MODULE.select_instrument_subset(
            selected,
            12,
            seed="fixed",
        )
        second = MODULE.select_instrument_subset(
            selected,
            12,
            seed="fixed",
        )
        self.assertEqual(first, second)
        self.assertEqual(len(first), 12)
        observed = {
            (
                notes[0]["instrument_family"],
                notes[0]["instrument_source"],
            )
            for notes in first.values()
        }
        self.assertEqual(len(observed), 6)

    def test_subset_refuses_limit_smaller_than_strata(self):
        selected = {
            1: instrument_notes(1, "bass", "acoustic"),
            2: instrument_notes(2, "brass", "acoustic"),
            3: instrument_notes(3, "string", "synthetic"),
        }
        with self.assertRaisesRegex(ValueError, "smaller than"):
            MODULE.select_instrument_subset(
                selected,
                2,
                seed="fixed",
            )

    def test_subset_keeps_all_when_below_limit(self):
        selected = {
            2: instrument_notes(2, "bass", "acoustic"),
            1: instrument_notes(1, "bass", "acoustic"),
        }
        result = MODULE.select_instrument_subset(
            selected,
            3,
            seed="fixed",
        )
        self.assertEqual(list(result), [1, 2])

    def test_recipes_retain_two_pcm_controls_and_four_codecs(self):
        recipes = MODULE.recipes()
        self.assertEqual(len(recipes), 6)
        expectations = [recipe["expectation"] for recipe in recipes]
        self.assertEqual(expectations.count("negative"), 2)
        self.assertEqual(expectations.count("controlled_positive"), 4)
        self.assertEqual(
            MODULE.RETENTION_POLICY,
            "retain_for_future_versions",
        )

    def test_case_metadata_requires_unique_paired_groups_and_sealed_counts(self):
        cases = [
            {
                "case_id": "negative",
                "relative_path": "generated/negative.flac",
                "expectation": "negative",
                "source_group": "tier-b-nsynth-train-instrument-0001",
                "partition_group": "tier-b-nsynth-train-instrument-0001",
                "split": "development",
                "provenance_tier": "tier_b_trusted",
            },
            {
                "case_id": "positive",
                "relative_path": "generated/positive.flac",
                "expectation": "controlled_positive",
                "source_group": "tier-b-nsynth-train-instrument-0001",
                "partition_group": "tier-b-nsynth-train-instrument-0001",
                "split": "development",
                "provenance_tier": "tier_b_trusted",
            },
        ]
        fingerprints = {
            "negative": "0" * 64,
            "positive": "f" * 64,
        }
        seal = {
            "case_count": 2,
            "partition_count": 1,
            "negative_count": 1,
            "controlled_positive_count": 1,
        }
        self.assertEqual(
            MODULE.validate_case_metadata(cases, fingerprints, seal),
            [],
        )

        cases[1]["case_id"] = "negative"
        failures = MODULE.validate_case_metadata(cases, fingerprints, seal)
        self.assertIn("manifest contains duplicate case IDs", failures)
        self.assertIn("manifest and fingerprint case IDs differ", failures)

    def test_case_metadata_rejects_untrusted_or_mismatched_training_case(self):
        cases = [
            {
                "case_id": "bad",
                "relative_path": "../bad.flac",
                "expectation": "maybe",
                "source_group": "tier-b-nsynth-test-instrument-0001",
                "partition_group": "different",
                "split": "held_out",
                "provenance_tier": "tier_a",
            }
        ]
        failures = MODULE.validate_case_metadata(
            cases,
            {"bad": "not-a-hash"},
            {
                "case_count": 1,
                "partition_count": 0,
                "negative_count": 0,
                "controlled_positive_count": 0,
            },
        )
        self.assertIn("bad: invalid audio path", failures)
        self.assertIn("bad: invalid expectation", failures)
        self.assertIn("bad: source group differs", failures)
        self.assertIn("bad: partition group differs", failures)
        self.assertIn("bad: split differs", failures)
        self.assertIn("bad: provenance tier differs", failures)
        self.assertIn("'bad': invalid fingerprint", failures)


if __name__ == "__main__":
    unittest.main()
